"""各資料源的抓取與解析。解析函式獨立成純函式以便測試。"""

import requests

TWSE = "https://www.twse.com.tw/rwd/zh"
TAIFEX_API = "https://openapi.taifex.com.tw/v1"

HEADERS = {"User-Agent": "tw-market-sentiment-dashboard/1.0"}
TIMEOUT = 30


def _get_json(url, params=None):
    resp = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _roc_to_iso(roc_date):
    """'115/07/01' 或 '20260707'（西元）→ '2026-07-01'。"""
    if "/" in roc_date:
        y, m, d = roc_date.split("/")
        return f"{int(y) + 1911}-{m}-{d}"
    return f"{roc_date[:4]}-{roc_date[4:6]}-{roc_date[6:]}"


def _num(s):
    return float(str(s).replace(",", ""))


# ---- 融資餘額（TWSE 信用交易統計） ----

def parse_margin_balance(payload):
    """回傳 (date, 融資金額今日餘額仟元)。"""
    date = payload["date"]
    iso = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    for table in payload["tables"]:
        for row in table.get("data", []):
            if row[0] == "融資金額(仟元)":
                return iso, int(_num(row[5]))
    raise ValueError("融資金額(仟元) row not found")


def fetch_margin_balance(date_yyyymmdd):
    payload = _get_json(
        f"{TWSE}/marginTrading/MI_MARGN",
        {"date": date_yyyymmdd, "selectType": "MS", "response": "json"},
    )
    if payload.get("stat") != "OK":
        return None
    return parse_margin_balance(payload)


# ---- 漲跌家數（TWSE 大盤統計資訊，取「股票」欄） ----

def parse_breadth(payload):
    """回傳 (date, 上漲家數, 下跌家數, 跌停家數)，只計股票不含 ETF/權證。

    跌停家數取「下跌(跌停)」股票欄括號內的值，供價量背離的
    鎖死型量縮過濾（跌停鎖死＝賣不掉造成的量縮，不是賣壓衰竭）。
    """
    date = payload["date"]
    iso = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    up = down = limit_down = None
    for table in payload["tables"]:
        if table.get("title") == "漲跌證券數合計":
            for row in table["data"]:
                cell = row[2]
                count = int(_num(cell.split("(")[0]))
                if row[0].startswith("上漲"):
                    up = count
                elif row[0].startswith("下跌"):
                    down = count
                    limit_down = int(_num(cell.split("(")[1].rstrip(")"))) if "(" in cell else 0
    if up is None or down is None:
        raise ValueError("漲跌證券數合計 table not found")
    return iso, up, down, limit_down


def fetch_breadth(date_yyyymmdd):
    payload = _get_json(
        f"{TWSE}/afterTrading/MI_INDEX",
        {"date": date_yyyymmdd, "type": "MS", "response": "json"},
    )
    if payload.get("stat") != "OK":
        return None
    return parse_breadth(payload)


# ---- 加權指數收盤價（TWSE 每月市場成交資訊） ----

def parse_taiex_closes(payload):
    """回傳該月每日 [(iso_date, 收盤指數), ...]。"""
    fields = payload["fields"]
    date_idx = fields.index("日期")
    close_idx = fields.index("發行量加權股價指數")
    return [
        (_roc_to_iso(row[date_idx]), _num(row[close_idx]))
        for row in payload["data"]
    ]


def fetch_taiex_month(date_yyyymmdd):
    """該月加權指數收盤與成交金額：{"closes": [...], "volumes": [...]}。"""
    payload = _get_json(
        f"{TWSE}/afterTrading/FMTQIK",
        {"date": date_yyyymmdd, "response": "json"},
    )
    if payload.get("stat") != "OK":
        return {"closes": [], "volumes": []}
    return {
        "closes": parse_taiex_closes(payload),
        "volumes": parse_taiex_volumes(payload),
    }


# ---- 加權指數 OHLC 與成交值、櫃買指數 OHLC / 收盤 / 成交值 ----

def parse_taiex_ohlc(payload):
    """回傳該月 [(iso_date, open, high, low, close), ...]。"""
    fields = payload["fields"]
    idx = [fields.index(k) for k in ("日期", "開盤指數", "最高指數", "最低指數", "收盤指數")]
    return [
        (_roc_to_iso(row[idx[0]]), *(_num(row[i]) for i in idx[1:]))
        for row in payload["data"]
    ]


def fetch_taiex_ohlc(date_yyyymmdd):
    payload = _get_json(
        f"{TWSE}/TAIEX/MI_5MINS_HIST",
        {"date": date_yyyymmdd, "response": "json"},
    )
    if payload.get("stat") != "OK":
        return []
    return parse_taiex_ohlc(payload)


def parse_taiex_volumes(payload):
    """FMTQIK → 該月 [(iso_date, 成交金額元), ...]。"""
    fields = payload["fields"]
    date_idx = fields.index("日期")
    amt_idx = fields.index("成交金額")
    return [
        (_roc_to_iso(row[date_idx]), _num(row[amt_idx]))
        for row in payload["data"]
    ]


def parse_tpex_ohlc(payload):
    """TPEX openapi tpex_index（當月）→ [(iso_date, o, h, l, c), ...]。"""
    return [
        (
            _roc_to_iso(row["Date"]),
            _num(row["Open"]),
            _num(row["High"]),
            _num(row["Low"]),
            _num(row["Close"]),
        )
        for row in payload
    ]


def fetch_tpex_ohlc():
    return parse_tpex_ohlc(_get_json("https://www.tpex.org.tw/openapi/v1/tpex_index"))


def parse_tpex_highlight(payload):
    """TPEX highlight（單日彙總）→ (iso_date, 收市指數, 總成交值佰萬元)。"""
    date = payload["date"]
    iso = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    table = payload["tables"][0]
    row = dict(zip(table["fields"], table["data"][0]))
    return iso, _num(row["收市指數"]), _num(row["本日總成交值(佰萬元)"])


def fetch_tpex_highlight(date_slash):
    """date_slash 格式 YYYY/MM/DD。非交易日回傳 None。"""
    payload = _get_json(
        "https://www.tpex.org.tw/www/zh-tw/afterTrading/highlight",
        {"date": date_slash, "response": "json"},
    )
    tables = payload.get("tables") or [{}]
    if not tables[0].get("data"):
        return None
    return parse_tpex_highlight(payload)


# ---- 台指選擇權 Put/Call 未平倉比（TAIFEX OpenAPI） ----

def parse_put_call_oi_ratio(payload):
    """回傳 [(iso_date, PutCallOIRatio%), ...]。"""
    return [
        (_roc_to_iso(row["Date"]), _num(row["PutCallOIRatio%"]))
        for row in payload
    ]


def fetch_put_call_oi_ratio():
    return parse_put_call_oi_ratio(_get_json(f"{TAIFEX_API}/PutCallRatio"))


# ---- 大盤估值代理：上市個股本益比/殖利率中位數（TWSE BWIBBU_d） ----

def parse_pe_yield_medians(payload):
    """回傳 (date, 本益比中位數, 殖利率中位數)。'-' 等非數值排除。"""
    from statistics import median

    date = payload["date"]
    iso = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    fields = payload["fields"]
    pe_idx = fields.index("本益比")
    dy_idx = fields.index("殖利率(%)")

    def numeric(rows, idx):
        out = []
        for row in rows:
            try:
                out.append(_num(row[idx]))
            except ValueError:
                continue
        return out

    pes = numeric(payload["data"], pe_idx)
    dys = numeric(payload["data"], dy_idx)
    if not pes or not dys:
        raise ValueError("no numeric PE/yield rows")
    return iso, median(pes), median(dys)


def fetch_pe_yield_medians(date_yyyymmdd):
    payload = _get_json(
        f"{TWSE}/afterTrading/BWIBBU_d",
        {"date": date_yyyymmdd, "selectType": "ALL", "response": "json"},
    )
    if payload.get("stat") != "OK":
        return None
    return parse_pe_yield_medians(payload)


# ---- 外資台指期未平倉淨部位（TAIFEX OpenAPI 三大法人） ----

def parse_foreign_futures_net_oi(payload):
    """回傳 (iso_date, 外資臺股期貨多空未平倉口數淨額)。"""
    for row in payload:
        if row["ContractCode"] == "臺股期貨" and row["Item"] == "外資及陸資":
            return _roc_to_iso(row["Date"]), int(_num(row["OpenInterest(Net)"]))
    raise ValueError("外資臺股期貨 row not found")


def fetch_foreign_futures_net_oi():
    payload = _get_json(
        f"{TAIFEX_API}/MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate"
    )
    return parse_foreign_futures_net_oi(payload)
