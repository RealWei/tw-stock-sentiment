"""原始序列 → 衍生指標序列 → 每日快照（分數、總分、燈號）。"""

from datetime import date as date_type, timedelta

from collector.indicators import rate_of_change, realized_vol
from collector.scoring import composite_score, indicator_score, zone

PERCENTILE_YEARS = 3
# 日更指標容忍的最大落後天數（涵蓋春節長假）
DAILY_STALE_DAYS = 14

# id → (顯示名稱, invert: 越高越恐慌)
INDICATORS = {
    "pe": ("個股本益比中位數", False),
    "margin_roc20": ("融資餘額20日增減", False),
    "foreign_net_oi": ("外資台指期淨部位", False),
    "pc_oi_ratio": ("Put/Call未平倉比", True),
    "vol20": ("大盤20日波動率", True),
    "breadth_ma20": ("漲跌家數比(20日)", False),
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
    foreign_net_oi, pe, dividend_yield
    """
    derived = {}
    for passthrough in ("pe", "foreign_net_oi", "pc_oi_ratio"):
        if raw.get(passthrough):
            derived[passthrough] = list(raw[passthrough])

    if raw.get("taiex_close"):
        derived["vol20"] = _rolling(raw["taiex_close"], 20, realized_vol)

    if raw.get("margin_balance"):
        derived["margin_roc20"] = _rolling(raw["margin_balance"], 20, rate_of_change)

    if raw.get("breadth_ratio"):
        def ma(values, window):
            if len(values) < window:
                return None
            return sum(values[-window:]) / window
        derived["breadth_ma20"] = _rolling(raw["breadth_ratio"], 20, ma)

    return derived


def _latest_usable(series, as_of):
    """回傳 as_of 當日可用的最新 (date, value)；資料過期回傳 None。"""
    usable = sorted((d, v) for d, v in series if d <= as_of)
    if not usable:
        return None
    last_date, value = usable[-1]
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
    for ind_id, (_, invert) in INDICATORS.items():
        series = derived.get(ind_id, [])
        latest = _latest_usable(series, as_of)
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


# 依 2024-08 ~ 2026-07 波段回測選出的單邊指標組（詳見 README 權重分析）：
# 高點常見極端：外資期貨、融資增速、P/C 比
# 低點常見極端：波動率（最可靠）、本益比、融資增速、漲跌家數、P/C 比
GREED_GROUP = ("foreign_net_oi", "margin_roc20", "pc_oi_ratio")
FEAR_GROUP = ("vol20", "pe", "margin_roc20", "breadth_ma20", "pc_oi_ratio")
METER_ALIGN_DAYS = 5   # 各指標極端值常在轉折窗內不同天出現，取近 N 日最極端對齊
MIN_GROUP_SIZE = 3
OVERHEAT_METER = 80.0
COLD_METER = 15.0


def _side(snaps, group, pick):
    """對一組每日 scores dict 取各指標的極端值後平均。"""
    vals = []
    for ind in group:
        xs = [s.get(ind) for s in snaps if s.get(ind) is not None]
        if xs:
            vals.append(pick(xs))
    if len(vals) < MIN_GROUP_SIZE:
        return None
    return sum(vals) / len(vals)


def dual_meters(derived, as_of, align_days=METER_ALIGN_DAYS):
    """回傳 (過熱計, 恐慌計)：單邊指標組取近 N 日最極端分數的平均。"""
    all_dates = sorted({d for s in derived.values() for d, _ in s if d <= as_of})
    window = all_dates[-align_days:]
    if not window:
        return None, None
    snaps = [daily_snapshot(derived, d)["scores"] for d in window]
    return _side(snaps, GREED_GROUP, max), _side(snaps, FEAR_GROUP, min)


def zone_from_meters(greed, fear):
    """恐慌優先：崩盤期常伴隨部分過熱指標殘留高分。"""
    if fear is not None and fear <= COLD_METER:
        return "cold"
    if greed is not None and greed >= OVERHEAT_METER:
        return "overheat"
    if greed is None and fear is None:
        return None
    return "neutral"


def meters_series(derived):
    """全期間每日 (date, 過熱計, 恐慌計)，供走勢圖。"""
    all_dates = sorted({d for s in derived.values() for d, _ in s})
    scores_by_date = {d: daily_snapshot(derived, d)["scores"] for d in all_dates}
    out = []
    for i, d in enumerate(all_dates):
        snaps = [scores_by_date[w] for w in all_dates[max(0, i - METER_ALIGN_DAYS + 1) : i + 1]]
        greed = _side(snaps, GREED_GROUP, max)
        fear = _side(snaps, FEAR_GROUP, min)
        if greed is not None or fear is not None:
            out.append((d, greed, fear))
    return out


def composite_series(derived):
    """對每個出現過的交易日算總分，回傳 [(date, composite)]，供走勢圖用。"""
    all_dates = sorted({d for series in derived.values() for d, _ in series})
    out = []
    for as_of in all_dates:
        snap = daily_snapshot(derived, as_of)
        if snap["composite"] is not None:
            out.append((as_of, snap["composite"]))
    return out
