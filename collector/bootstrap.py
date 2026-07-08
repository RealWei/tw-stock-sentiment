"""一次性歷史回補：抓近 2-3 年各指標歷史寫入 history.csv。

TWSE 端點一次一天，總請求量大，全程 sleep 節流；可重跑（upsert 冪等），
中斷後再執行會跳過已有日期。
"""

import csv
import io
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests

from collector import fetchers
from collector.storage import load_history, upsert

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "data" / "history.csv"

TAIFEX = "https://www.taifex.com.tw/cht/3"
SLEEP_TWSE = 3.2   # TWSE 對高頻率請求會封 IP，保守節流
SLEEP_TAIFEX = 2.0

# bias_240 需要多一年的收盤價當暖身
CLOSE_YEARS = 3
DAILY_YEARS = 2


def _roc_to_iso(roc_date):
    y, m, d = roc_date.split("/")
    return f"{int(y):04d}-{m}-{d}" if int(y) > 1911 else f"{int(y) + 1911}-{m}-{d}"


def parse_pc_ratio_csv(text):
    """TAIFEX Put/Call 比 CSV → [(iso_date, 未平倉量比率%)]。"""
    out = []
    for row in csv.reader(io.StringIO(text.strip())):
        if not row or row[0] == "日期":
            continue
        out.append((_roc_to_iso(row[0]), float(row[6])))
    return out


def parse_fut_contracts_csv(text):
    """TAIFEX 三大法人期貨 CSV → 外資臺股期貨 [(iso_date, 未平倉淨額口數)]。"""
    out = []
    for row in csv.reader(io.StringIO(text.strip())):
        if len(row) < 14 or row[0] == "日期":
            continue
        if row[1].strip() == "臺股期貨" and row[2].strip() == "外資及陸資":
            out.append((_roc_to_iso(row[0].strip()), float(row[13])))
    return out


def _month_starts(years):
    """由舊到新的每月一號清單。"""
    today = date.today()
    months = []
    cursor = date(today.year - years, today.month, 1)
    while cursor <= today:
        months.append(cursor)
        cursor = (cursor.replace(day=28) + timedelta(days=7)).replace(day=1)
    return months


def _trading_days(years):
    """近 N 年非週末日期，由舊到新。"""
    today = date.today()
    day = today - timedelta(days=years * 365)
    out = []
    while day <= today:
        if day.weekday() < 5:
            out.append(day)
        day += timedelta(days=1)
    return out


def bootstrap_taiex_closes(existing):
    have = {d for d, _ in existing.get("taiex_close", [])}
    for month in _month_starts(CLOSE_YEARS):
        if any(d.startswith(month.strftime("%Y-%m")) for d in have) and month.strftime(
            "%Y-%m"
        ) != date.today().strftime("%Y-%m"):
            continue
        closes = fetchers.fetch_taiex_closes(month.strftime("%Y%m%d"))
        if closes:
            upsert(HISTORY, "taiex_close", closes)
            print(f"  taiex_close {month:%Y-%m}: {len(closes)} 筆")
        time.sleep(SLEEP_TWSE)


def bootstrap_daily_twse(existing, name, fetch, transform):
    """逐日回補 TWSE 資料源。fetch(yyyymmdd) → tuple 或 None。"""
    have = {d for d, _ in existing.get(name, [])}
    days = [d for d in _trading_days(DAILY_YEARS) if d.isoformat() not in have]
    print(f"  {name}: 需回補 {len(days)} 天")
    for i, day in enumerate(days):
        try:
            result = fetch(day.strftime("%Y%m%d"))
        except Exception as exc:
            print(f"  {name} {day}: {exc}", file=sys.stderr)
            result = None
        if result:
            point = transform(result)
            if point:
                upsert(HISTORY, name, [point])
        if i % 50 == 0:
            print(f"  {name}: {i}/{len(days)} ({day})")
        time.sleep(SLEEP_TWSE)


def bootstrap_taifex_csv(name, path, parse, extra_params=None):
    """以 30 天為一段回補 TAIFEX CSV 資料源。查詢終點不可含當天，否則回傳錯誤頁。"""
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=DAILY_YEARS * 365)
    cursor = start
    while cursor <= end:
        window_end = min(cursor + timedelta(days=29), end)
        params = {
            "queryStartDate": cursor.strftime("%Y/%m/%d"),
            "queryEndDate": window_end.strftime("%Y/%m/%d"),
        }
        params.update(extra_params or {})
        resp = requests.post(f"{TAIFEX}/{path}", data=params, timeout=30)
        resp.raise_for_status()
        text = resp.content.decode("big5", errors="replace")
        if text.lstrip().startswith("<"):
            raise RuntimeError(f"{name} {params['queryStartDate']} 回傳錯誤頁而非 CSV")
        points = parse(text)
        if points:
            upsert(HISTORY, name, points)
        print(f"  {name} {cursor} ~ {window_end}: {len(points)} 筆")
        cursor = window_end + timedelta(days=1)
        time.sleep(SLEEP_TAIFEX)


def main():
    existing = load_history(HISTORY)

    print("回補加權指數收盤價（按月）")
    bootstrap_taiex_closes(existing)

    print("回補 Put/Call 未平倉比（30 天一段）")
    bootstrap_taifex_csv("pc_oi_ratio", "pcRatioDown", parse_pc_ratio_csv)

    print("回補外資台指期淨部位（30 天一段）")
    bootstrap_taifex_csv(
        "foreign_net_oi",
        "futContractsDateDown",
        parse_fut_contracts_csv,
        {"commodityId": "TXF"},
    )

    print("回補融資餘額（逐日，較久）")
    bootstrap_daily_twse(
        existing,
        "margin_balance",
        fetchers.fetch_margin_balance,
        lambda r: (r[0], r[1]),
    )

    print("回補漲跌家數（逐日，較久）")
    bootstrap_daily_twse(
        existing,
        "breadth_ratio",
        fetchers.fetch_breadth,
        lambda r: (r[0], r[1] / (r[1] + r[2])) if r[1] + r[2] else None,
    )

    print("回補本益比/殖利率中位數（每週三抽樣）")
    existing = load_history(HISTORY)
    have = {d for d, _ in existing.get("pe", [])}
    wednesdays = [d for d in _trading_days(DAILY_YEARS) if d.weekday() == 2 and d.isoformat() not in have]
    for i, day in enumerate(wednesdays):
        try:
            result = fetchers.fetch_pe_yield_medians(day.strftime("%Y%m%d"))
        except Exception as exc:
            print(f"  pe {day}: {exc}", file=sys.stderr)
            result = None
        if result:
            iso, pe, dy = result
            if iso == day.isoformat():  # 該端點對無資料日會回傳別天，需核對
                upsert(HISTORY, "pe", [(iso, pe)])
                upsert(HISTORY, "dividend_yield", [(iso, dy)])
        if i % 20 == 0:
            print(f"  pe: {i}/{len(wednesdays)} ({day})")
        time.sleep(SLEEP_TWSE)

    print("完成")


if __name__ == "__main__":
    main()
