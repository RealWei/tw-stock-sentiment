"""每日收集主程式：抓資料 → 更新 history.csv → 產出 docs/data/*.json → 判斷通知。"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector import fetchers
from collector.notify import notification_message, send_telegram, should_notify
from collector.pipeline import (
    INDICATORS,
    composite_series,
    daily_snapshot,
    derive_indicator_series,
    dual_meters,
    meters_series,
    zone_from_meters,
)
from collector.signals import scan_market, support_resistance
from collector.storage import load_history, upsert

MARKETS = {"taiex": "加權指數", "tpex": "櫃買指數"}
DIRECTION_TEXT = {"bearish": "偏空", "bullish": "偏多"}

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "data" / "history.csv"
STATE = ROOT / "data" / "state.json"
DOCS_DATA = ROOT / "docs" / "data"

TAIPEI = timezone(timedelta(hours=8))
FAILURE_ALERT_THRESHOLD = 2


def fetch_all(today_yyyymmdd):
    """抓所有每日資料源，回傳 {raw_name: [(date, value)]} 與失敗清單。"""
    updates, failures = {}, []

    def attempt(name, fn):
        try:
            return fn()
        except Exception as exc:  # 單一來源失敗不中斷其他來源
            failures.append(f"{name}: {exc}")
            return None

    margin = attempt("margin_balance", lambda: fetchers.fetch_margin_balance(today_yyyymmdd))
    if margin:
        updates["margin_balance"] = [margin]

    breadth = attempt("breadth_ratio", lambda: fetchers.fetch_breadth(today_yyyymmdd))
    if breadth:
        date, up, down, limit_down = breadth
        if limit_down is not None:
            updates["taiex_limit_down"] = [(date, float(limit_down))]
        if up + down:
            updates["breadth_ratio"] = [(date, up / (up + down))]

    month = attempt("taiex_close", lambda: fetchers.fetch_taiex_month(today_yyyymmdd))
    if month and month["closes"]:
        updates["taiex_close"] = month["closes"]
        updates["taiex_volume"] = month["volumes"]

    taiex_ohlc = attempt("taiex_ohlc", lambda: fetchers.fetch_taiex_ohlc(today_yyyymmdd))
    if taiex_ohlc:
        updates["taiex_open"] = [(d, o) for d, o, h, l, c in taiex_ohlc]
        updates["taiex_high"] = [(d, h) for d, o, h, l, c in taiex_ohlc]
        updates["taiex_low"] = [(d, l) for d, o, h, l, c in taiex_ohlc]

    tpex_ohlc = attempt("tpex_ohlc", fetchers.fetch_tpex_ohlc)
    if tpex_ohlc:
        updates["tpex_open"] = [(d, o) for d, o, h, l, c in tpex_ohlc]
        updates["tpex_high"] = [(d, h) for d, o, h, l, c in tpex_ohlc]
        updates["tpex_low"] = [(d, l) for d, o, h, l, c in tpex_ohlc]
        updates["tpex_close"] = [(d, c) for d, o, h, l, c in tpex_ohlc]

    tpex_day = attempt(
        "tpex_volume",
        lambda: fetchers.fetch_tpex_highlight(
            f"{today_yyyymmdd[:4]}/{today_yyyymmdd[4:6]}/{today_yyyymmdd[6:]}"
        ),
    )
    if tpex_day:
        date, close, volume = tpex_day
        updates.setdefault("tpex_close", []).append((date, close))
        updates["tpex_volume"] = [(date, volume)]

    pc = attempt("pc_oi_ratio", fetchers.fetch_put_call_oi_ratio)
    if pc:
        updates["pc_oi_ratio"] = pc

    foreign = attempt("foreign_net_oi", fetchers.fetch_foreign_futures_net_oi)
    if foreign:
        updates["foreign_net_oi"] = [foreign]

    valuation = attempt("pe_yield", lambda: fetchers.fetch_pe_yield_medians(today_yyyymmdd))
    if valuation:
        date, pe, _ = valuation
        updates["pe"] = [(date, pe)]

    return updates, failures


def build_signal_report(raw):
    """從原始序列產生各市場技術訊號與撐壓位階。"""
    report = {}
    for mkt, label in MARKETS.items():
        close_series = raw.get(f"{mkt}_close", [])
        entry = {"name": label, "events": [], "levels": None}
        if len(close_series) >= 30:
            dates = [d for d, _ in close_series]
            closes = [v for _, v in close_series]
            by_date = dict(close_series)
            opens = dict(raw.get(f"{mkt}_open", []))
            highs = dict(raw.get(f"{mkt}_high", []))
            lows = dict(raw.get(f"{mkt}_low", []))
            ohlc = {
                d: (opens[d], highs[d], lows[d], by_date[d])
                for d in dates
                if d in opens and d in highs and d in lows
            }
            volumes = dict(raw.get(f"{mkt}_volume", []))
            limit_down = dict(raw.get("taiex_limit_down", [])) if mkt == "taiex" else None
            events = scan_market(dates, closes, volumes, ohlc, limit_down=limit_down)
            events.sort(key=lambda e: e["date"], reverse=True)
            entry["events"] = events
            entry["levels"] = support_resistance(closes)
        report[mkt] = entry
    return report


def notify_new_signals(report, state):
    """對「最新交易日」的新訊號發 Telegram（去重記在 state）。"""
    seen = set(state.get("notified_signals", []))
    lines, keys = [], []
    for mkt, entry in report.items():
        if not entry["events"]:
            continue
        latest_date = entry["events"][0]["date"]
        for e in entry["events"]:
            if e["date"] != latest_date:
                continue
            key = f"{e['date']}|{mkt}|{e['id']}|{e['direction']}"
            if key in seen:
                continue
            keys.append(key)
            lines.append(
                f"・{entry['name']}：{e['name']}（{DIRECTION_TEXT[e['direction']]}，{e['date']}）"
            )
    if not lines:
        return
    if send_telegram("📡 技術訊號\n" + "\n".join(lines)):
        # 送達才記錄，未設定/失敗時下次重試；只保留近 200 筆避免無限成長
        state["notified_signals"] = (state.get("notified_signals", []) + keys)[-200:]


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"zone": None, "consecutive_failures": 0}


def save_state(state):
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def write_outputs(snapshot, derived):
    DOCS_DATA.mkdir(parents=True, exist_ok=True)

    latest = {
        "date": snapshot["date"],
        "composite": snapshot["composite"],
        "greed": snapshot.get("greed"),
        "fear": snapshot.get("fear"),
        "zone": snapshot["zone"],
        "indicators": [
            {
                "id": ind_id,
                "name": name,
                "invert": invert,
                "value": snapshot["values"][ind_id],
                "score": snapshot["scores"][ind_id],
                "updated": snapshot["updated"][ind_id],
            }
            for ind_id, (name, invert) in INDICATORS.items()
        ],
    }
    (DOCS_DATA / "latest.json").write_text(
        json.dumps(latest, ensure_ascii=False, indent=1)
    )

    series = {
        "composite": composite_series(derived),
        "meters": meters_series(derived),
        "indicators": {
            ind_id: derived.get(ind_id, []) for ind_id in INDICATORS
        },
    }
    (DOCS_DATA / "series.json").write_text(json.dumps(series, ensure_ascii=False))


def main():
    now = datetime.now(TAIPEI)
    today = now.strftime("%Y%m%d")
    print(f"收集 {now:%Y-%m-%d} 台北時間 {now:%H:%M}")

    updates, failures = fetch_all(today)
    for name, points in updates.items():
        upsert(HISTORY, name, points)
        print(f"  {name}: +{len(points)} 筆（最新 {points[-1][0]}）")
    for f in failures:
        print(f"  失敗 {f}", file=sys.stderr)

    raw = load_history(HISTORY)
    if not raw:
        print("尚無任何歷史資料", file=sys.stderr)
        sys.exit(1)

    derived = derive_indicator_series(raw)
    as_of = now.strftime("%Y-%m-%d")
    snapshot = daily_snapshot(derived, as_of)
    greed, fear = dual_meters(derived, as_of)
    snapshot["greed"], snapshot["fear"] = greed, fear
    meter_zone = zone_from_meters(greed, fear)
    if meter_zone is not None:  # 雙計優先，資料不足時退回總分燈號
        snapshot["zone"] = meter_zone
    write_outputs(snapshot, derived)
    if greed is not None and fear is not None:
        print(f"過熱計 {greed:.0f} / 恐慌計 {fear:.0f}")

    signal_report = build_signal_report(raw)
    (DOCS_DATA / "signals.json").write_text(
        json.dumps({"generated": now.strftime("%Y-%m-%d"), "markets": signal_report},
                   ensure_ascii=False)
    )
    total_events = sum(len(m["events"]) for m in signal_report.values())
    print(f"技術訊號：近 30 日共 {total_events} 筆")
    comp = snapshot["composite"]
    print(f"總分: {comp:.1f} ({snapshot['zone']})" if comp is not None else "總分: 資料不足")

    state = load_state()
    if failures:
        state["consecutive_failures"] += 1
        if state["consecutive_failures"] >= FAILURE_ALERT_THRESHOLD:
            send_telegram(
                f"⚠️ 台股儀表板資料收集已連續 {state['consecutive_failures']} 天失敗：\n"
                + "\n".join(failures)
            )
    else:
        state["consecutive_failures"] = 0

    if snapshot["zone"] is not None and should_notify(state["zone"], snapshot["zone"]):
        send_telegram(notification_message(snapshot))
        print(f"已通知：{state['zone']} → {snapshot['zone']}")
    if snapshot["zone"] is not None:
        state["zone"] = snapshot["zone"]

    notify_new_signals(signal_report, state)
    save_state(state)


if __name__ == "__main__":
    main()
