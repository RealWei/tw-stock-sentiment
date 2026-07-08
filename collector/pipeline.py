"""原始序列 → 衍生指標序列 → 每日快照（分數、總分、燈號）。"""

from datetime import date as date_type, timedelta

from collector.indicators import bias_ratio, rate_of_change
from collector.scoring import composite_score, indicator_score, zone

PERCENTILE_YEARS = 3
# 日更指標容忍的最大落後天數（涵蓋春節長假）
DAILY_STALE_DAYS = 14

# id → (顯示名稱, invert: 越高越恐慌, cadence)
INDICATORS = {
    "pe": ("大盤本益比", False, "monthly"),
    "dividend_yield": ("大盤殖利率", True, "monthly"),
    "margin_roc20": ("融資餘額20日增減", False, "daily"),
    "foreign_net_oi": ("外資台指期淨部位", False, "daily"),
    "pc_oi_ratio": ("Put/Call未平倉比", True, "daily"),
    "vix": ("台指VIX", True, "daily"),
    "bias_240": ("大盤年線乖離率", False, "daily"),
    "breadth_ma20": ("漲跌家數比(20日)", False, "daily"),
}


def _rolling(series, window, fn):
    """對 (date, value) 序列做滾動計算，回傳有值的 (date, result)。"""
    out = []
    values = [v for _, v in series]
    for i in range(len(series)):
        result = fn(values[: i + 1], window)
        if result is not None:
            out.append((series[i][0], result))
    return out


def derive_indicator_series(raw):
    """raw {name: [(date, value)]} → {indicator_id: [(date, value)]}。

    原始序列: taiex_close, margin_balance, breadth_ratio, pc_oi_ratio,
    foreign_net_oi, vix, pe, dividend_yield
    """
    derived = {}
    for passthrough in ("pe", "dividend_yield", "foreign_net_oi", "pc_oi_ratio", "vix"):
        if raw.get(passthrough):
            derived[passthrough] = list(raw[passthrough])

    if raw.get("taiex_close"):
        derived["bias_240"] = _rolling(raw["taiex_close"], 240, bias_ratio)

    if raw.get("margin_balance"):
        derived["margin_roc20"] = _rolling(raw["margin_balance"], 20, rate_of_change)

    if raw.get("breadth_ratio"):
        def ma(values, window):
            if len(values) < window:
                return None
            return sum(values[-window:]) / window
        derived["breadth_ma20"] = _rolling(raw["breadth_ratio"], 20, ma)

    return derived


def _latest_usable(series, as_of, cadence):
    """回傳 as_of 當日可用的最新 (date, value)；日更指標過期回傳 None。"""
    usable = sorted((d, v) for d, v in series if d <= as_of)
    if not usable:
        return None
    last_date, value = usable[-1]
    if cadence == "daily":
        limit = date_type.fromisoformat(as_of) - timedelta(days=DAILY_STALE_DAYS)
        if date_type.fromisoformat(last_date) < limit:
            return None
    return last_date, value


def daily_snapshot(derived, as_of):
    """derived {indicator_id: [(date, value)]} → 當日分數快照。"""
    window_start = (
        date_type.fromisoformat(as_of) - timedelta(days=PERCENTILE_YEARS * 365)
    ).isoformat()

    values, scores, updated = {}, {}, {}
    for ind_id, (_, invert, cadence) in INDICATORS.items():
        series = derived.get(ind_id, [])
        latest = _latest_usable(series, as_of, cadence)
        if latest is None:
            values[ind_id] = None
            scores[ind_id] = None
            updated[ind_id] = None
            continue
        last_date, value = latest
        history = [v for d, v in series if window_start <= d <= as_of]
        values[ind_id] = value
        scores[ind_id] = indicator_score(history, value, invert)
        updated[ind_id] = last_date

    composite = composite_score(scores)
    return {
        "date": as_of,
        "values": values,
        "scores": scores,
        "updated": updated,
        "composite": composite,
        "zone": zone(composite) if composite is not None else None,
    }


def composite_series(derived):
    """對每個出現過的交易日算總分，回傳 [(date, composite)]，供走勢圖用。"""
    all_dates = sorted({d for series in derived.values() for d, _ in series})
    out = []
    for as_of in all_dates:
        snap = daily_snapshot(derived, as_of)
        if snap["composite"] is not None:
            out.append((as_of, snap["composite"]))
    return out
