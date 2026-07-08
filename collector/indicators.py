"""從原始序列計算衍生指標。輸入序列一律由舊到新排序。"""

import math

TRADING_DAYS_PER_YEAR = 252


def bias_ratio(closes, window=240):
    """年線乖離率(%)：(最新收盤 − N 日均) / N 日均 × 100。資料不足回傳 None。"""
    if len(closes) < window:
        return None
    ma = sum(closes[-window:]) / window
    return (closes[-1] - ma) / ma * 100


def realized_vol(closes, window=20):
    """N 日歷史波動率（年化 %）。資料不足回傳 None。"""
    if len(closes) < window + 1:
        return None
    rets = [
        math.log(closes[i] / closes[i - 1])
        for i in range(len(closes) - window, len(closes))
    ]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(TRADING_DAYS_PER_YEAR) * 100


def rate_of_change(values, window=20):
    """N 日變化率(%)。資料不足回傳 None。"""
    if len(values) < window + 1:
        return None
    base = values[-window - 1]
    if base == 0:
        return None
    return (values[-1] - base) / base * 100
