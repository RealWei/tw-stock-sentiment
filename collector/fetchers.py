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
    """回傳 (date, 上漲家數, 下跌家數)，只計股票不含 ETF/權證。"""
    date = payload["date"]
    iso = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    up = down = None
    for table in payload["tables"]:
        if table.get("title") == "漲跌證券數合計":
            for row in table["data"]:
                count = int(_num(row[2].split("(")[0]))
                if row[0].startswith("上漲"):
                    up = count
                elif row[0].startswith("下跌"):
                    down = count
    if up is None or down is None:
        raise ValueError("漲跌證券數合計 table not found")
    return iso, up, down


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


def fetch_taiex_closes(date_yyyymmdd):
    payload = _get_json(
        f"{TWSE}/afterTrading/FMTQIK",
        {"date": date_yyyymmdd, "response": "json"},
    )
    if payload.get("stat") != "OK":
        return []
    return parse_taiex_closes(payload)


# ---- 台指選擇權 Put/Call 未平倉比（TAIFEX OpenAPI） ----

def parse_put_call_oi_ratio(payload):
    """回傳 [(iso_date, PutCallOIRatio%), ...]。"""
    return [
        (_roc_to_iso(row["Date"]), _num(row["PutCallOIRatio%"]))
        for row in payload
    ]


def fetch_put_call_oi_ratio():
    return parse_put_call_oi_ratio(_get_json(f"{TAIFEX_API}/PutCallRatio"))


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
