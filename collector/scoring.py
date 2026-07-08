"""指標計分：歷史百分位 → 方向統一 → 等權合成 → 燈號。"""

OVERHEAT_THRESHOLD = 80.0
COLD_THRESHOLD = 20.0


def percentile_rank(history, value):
    """value 在 history 中的百分位（0-100），同值採 midrank。"""
    if not history:
        raise ValueError("history must not be empty")
    less = sum(1 for h in history if h < value)
    equal = sum(1 for h in history if h == value)
    return (less + 0.5 * equal) / len(history) * 100.0


def indicator_score(history, value, invert):
    """單一指標分數；invert=True 表示該指標越高越恐慌（如 VIX），需反轉。"""
    p = percentile_rank(history, value)
    return 100.0 - p if invert else p


def composite_score(scores):
    """等權平均，忽略缺值；全缺回傳 None。"""
    present = [s for s in scores.values() if s is not None]
    if not present:
        return None
    return sum(present) / len(present)


def zone(score):
    if score >= OVERHEAT_THRESHOLD:
        return "overheat"
    if score <= COLD_THRESHOLD:
        return "cold"
    return "neutral"
