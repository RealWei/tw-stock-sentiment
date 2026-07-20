"""K 線技術訊號偵測。皆為純函式：輸入由舊到新的序列，判斷最後一根是否觸發。

bar 格式: (open, high, low, close, volume)；帶日期的序列在 pipeline 層處理。
"""

PV_WINDOW = 20          # 價量背離的新高/新低視窗
EXTREME_WINDOW = 60     # 創高/創低、背離、高低檔判定視窗
HIGH_ZONE = 0.97        # 收盤 ≥ 60日高 × 0.97 視為「高檔」
LOW_ZONE = 1.03         # 收盤 ≤ 60日低 × 1.03 視為「低檔」


def rsi(closes, period=14):
    """Wilder RSI，回傳與 closes 等長的列表（暖身期為 None）。"""
    out = [None] * len(closes)
    if len(closes) <= period:
        return out
    gains = losses = 0.0
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        gains += max(diff, 0)
        losses += max(-diff, 0)
    avg_gain, avg_loss = gains / period, losses / period

    def value(g, l):
        if l == 0:
            return 100.0
        return 100.0 - 100.0 / (1.0 + g / l)

    out[period] = value(avg_gain, avg_loss)
    for i in range(period + 1, len(closes)):
        diff = closes[i] - closes[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(diff, 0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-diff, 0)) / period
        out[i] = value(avg_gain, avg_loss)
    return out


def price_volume_divergence(closes, volumes):
    """價創 20 日新高但量低於 20 日均量 → bearish；創新低量縮 → bullish。"""
    if len(closes) < PV_WINDOW or len(volumes) < PV_WINDOW:
        return None
    window_c = closes[-PV_WINDOW:]
    avg_vol = sum(volumes[-PV_WINDOW:]) / PV_WINDOW
    if volumes[-1] >= avg_vol:
        return None
    if closes[-1] >= max(window_c):
        return "bearish"
    if closes[-1] <= min(window_c):
        return "bullish"
    return None


def rsi_divergence(closes, period=14):
    """收盤創 60 日新高但 RSI 低於前波峰 → bearish；創新低但 RSI higher → bullish。"""
    if len(closes) < EXTREME_WINDOW + period:
        return None
    r = rsi(closes, period)
    window = closes[-EXTREME_WINDOW:]
    prev = closes[-EXTREME_WINDOW:-5]  # 排除最近 5 天找前波峰/谷
    if not prev:
        return None
    offset = len(closes) - EXTREME_WINDOW

    if closes[-1] >= max(window):
        j = offset + prev.index(max(prev))
        if closes[-1] > closes[j] and r[j] is not None and r[-1] is not None and r[-1] < r[j] - 0.5:
            return "bearish"
    if closes[-1] <= min(window):
        j = offset + prev.index(min(prev))
        if closes[-1] < closes[j] and r[j] is not None and r[-1] is not None and r[-1] > r[j] + 0.5:
            return "bullish"
    return None


def upper_shadow_at_high(bars):
    """盤中創 60 日新高、收盤留長上影線（≥2 倍實體且 ≥40% 振幅）→ bearish。"""
    if len(bars) < EXTREME_WINDOW + 1:
        return None
    o, h, l, c, _ = bars[-1]
    highs = [b[1] for b in bars[-EXTREME_WINDOW - 1:]]
    if h < max(highs):
        return None
    day_range = h - l
    if day_range <= 0:
        return None
    upper = h - max(o, c)
    body = abs(c - o)
    if upper >= 2 * body and upper >= 0.4 * day_range:
        return "bearish"
    return None


def _zone(bars):
    """最後一根收盤位於 60 日區間的高檔/低檔/中間。"""
    closes = [b[3] for b in bars[-EXTREME_WINDOW - 1:]]
    c = closes[-1]
    if c >= max(closes) * HIGH_ZONE:
        return "high"
    if c <= min(closes) * LOW_ZONE:
        return "low"
    return "mid"


def engulfing(bars):
    """高檔看空吞噬 / 低檔看多吞噬（實體吞噬前日實體）。"""
    if len(bars) < EXTREME_WINDOW + 2:
        return None
    po, _, _, pc, _ = bars[-2]
    o, _, _, c, _ = bars[-1]
    zone = _zone(bars)
    prev_body = abs(pc - po)
    body = abs(c - o)
    if prev_body == 0 or body <= prev_body:
        return None
    if zone == "high" and pc > po and c < o and o >= pc and c <= po:
        return "bearish"
    if zone == "low" and pc < po and c > o and o <= pc and c >= po:
        return "bullish"
    return None


def doji_at_high(bars):
    """高檔十字星（實體 ≤10% 振幅且有基本振幅）→ bearish 警訊。"""
    if len(bars) < EXTREME_WINDOW + 1:
        return None
    o, h, l, c, _ = bars[-1]
    if _zone(bars) != "high":
        return None
    day_range = h - l
    if day_range < c * 0.005:  # 振幅太小不算
        return None
    if abs(c - o) <= 0.1 * day_range:
        return "bearish"
    return None


SIGNALS = {
    "pv_divergence": "價量背離",
    "rsi_divergence": "RSI 背離",
    "upper_shadow": "創高留上影線",
    "engulfing": "吞噬形態",
    "doji": "高檔十字星",
}


LIMIT_DOWN_HIGH = 50    # 跌停家數絕對高位（約 5% 上市股票）


def scan_market(dates, closes, volumes, ohlc, lookback=30, limit_down=None):
    """掃描最後 lookback 個交易日的訊號。

    dates/closes 等長由舊到新；volumes、ohlc 為 date → 值的 dict（可缺）。
    缺 OHLC 的日期以收盤價代 K 棒（歷史高低點退化為收盤高低點），
    但 K 棒形態（上影線/吞噬/十字星）只在當日有真實 OHLC 時評估。

    limit_down：date → 當日跌停家數（股票，不含權證/ETF）。偏多價量背離
    的量縮有兩種相反成因——賣壓衰竭 vs 跌停鎖死賣不掉；當日跌停家數
    仍在增加或處於絕對高位時，量縮判定為鎖死型，壓掉偏多訊號。
    無資料的日期不過濾（序列自 2026-07 起累積）。
    """
    events = []
    vol_list = [volumes.get(d) for d in dates]
    bars = []
    for i, d in enumerate(dates):
        o, h, l, c = ohlc.get(d, (closes[i],) * 4)
        bars.append((o, h, l, c, vol_list[i]))

    start = max(1, len(dates) - lookback)
    for i in range(start, len(dates)):
        prefix_c = closes[: i + 1]
        prefix_bars = bars[: i + 1]
        date = dates[i]

        window_vols = vol_list[i - PV_WINDOW + 1 : i + 1]
        if len(window_vols) == PV_WINDOW and all(v is not None for v in window_vols):
            direction = price_volume_divergence(prefix_c, window_vols)
            if direction == "bullish" and limit_down:
                ld = limit_down.get(date)
                ld_prev = limit_down.get(dates[i - 1]) if i else None
                locked = ld is not None and (
                    ld >= LIMIT_DOWN_HIGH or (ld_prev is not None and ld > ld_prev)
                )
                if locked:
                    direction = None  # 鎖死型量縮：跌停未收斂，非賣壓衰竭
            if direction:
                events.append({"date": date, "id": "pv_divergence", "direction": direction})

        direction = rsi_divergence(prefix_c)
        if direction:
            events.append({"date": date, "id": "rsi_divergence", "direction": direction})

        if dates[i] in ohlc:
            for sig_id, fn in (
                ("upper_shadow", upper_shadow_at_high),
                ("engulfing", engulfing),
                ("doji", doji_at_high),
            ):
                direction = fn(prefix_bars)
                if direction:
                    events.append({"date": date, "id": sig_id, "direction": direction})

    for e in events:
        e["name"] = SIGNALS[e["id"]]
    return events


def support_resistance(closes):
    """近 60/240 日高低點與 20/60/240 日均線位階。"""
    levels = {"close": closes[-1]}
    for window in (60, 240):
        if len(closes) >= window:
            levels[f"high{window}"] = max(closes[-window:])
            levels[f"low{window}"] = min(closes[-window:])
    for window in (20, 60, 240):
        if len(closes) >= window:
            levels[f"ma{window}"] = sum(closes[-window:]) / window
    c = closes[-1]
    for key in list(levels):
        if key == "close":
            continue
        base = levels[key]
        if base:
            levels[f"dist_{key}_pct"] = (c - base) / base * 100
    return levels
