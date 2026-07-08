import pytest

from collector.signals import (
    rsi,
    price_volume_divergence,
    rsi_divergence,
    upper_shadow_at_high,
    engulfing,
    doji_at_high,
    support_resistance,
)


def flat_bars(n, price=100.0, volume=1000.0):
    """(o, h, l, c, v) 平盤序列。"""
    return [(price, price, price, price, volume) for _ in range(n)]


class TestRsi:
    def test_all_gains_is_100(self):
        closes = [float(i) for i in range(1, 30)]
        assert rsi(closes, period=14)[-1] == pytest.approx(100.0)

    def test_warmup_period_is_none(self):
        closes = [float(i) for i in range(1, 30)]
        result = rsi(closes, period=14)
        assert result[13] is None
        assert result[14] is not None

    def test_alternating_moves_near_50(self):
        closes = [100 + (1 if i % 2 else 0) for i in range(40)]
        assert 30 < rsi(closes, period=14)[-1] < 70


class TestPriceVolumeDivergence:
    def test_new_high_on_shrinking_volume_is_bearish(self):
        closes = [100.0 + i * 0.1 for i in range(19)] + [103.0]  # 今天創 20 日新高
        volumes = [1000.0] * 19 + [500.0]  # 量遠低於均量
        assert price_volume_divergence(closes, volumes) == "bearish"

    def test_new_high_on_heavy_volume_is_no_signal(self):
        closes = [100.0 + i * 0.1 for i in range(19)] + [103.0]
        volumes = [1000.0] * 19 + [1500.0]
        assert price_volume_divergence(closes, volumes) is None

    def test_new_low_on_shrinking_volume_is_bullish(self):
        closes = [100.0 - i * 0.1 for i in range(19)] + [97.0]
        volumes = [1000.0] * 19 + [500.0]
        assert price_volume_divergence(closes, volumes) == "bullish"

    def test_no_new_extreme_is_no_signal(self):
        closes = [100.0] * 19 + [100.5]
        closes[10] = 105.0
        volumes = [1000.0] * 20
        assert price_volume_divergence(closes, volumes) is None


class TestRsiDivergence:
    def test_higher_high_with_lower_rsi_is_bearish(self):
        # 前段猛漲到 120（RSI 高），拉回後緩漲創新高 121.4（RSI 較低）
        closes = [100.0] * 45
        closes += [100.0 + i * 2 for i in range(1, 11)]     # 猛漲到 120
        closes += [120 - i * 1.5 for i in range(1, 8)]      # 拉回到 ~109.5
        closes += [109.5 + i * 0.85 for i in range(1, 15)]  # 緩漲到 ~121.4 創新高
        assert rsi_divergence(closes) == "bearish"

    def test_flat_series_is_no_signal(self):
        assert rsi_divergence([100.0] * 80) is None


class TestUpperShadowAtHigh:
    def test_new_high_with_long_upper_shadow_signals(self):
        bars = flat_bars(60)
        # 盤中衝到 112 創新高，收盤幾乎平盤：上影線遠大於實體
        bars.append((100.0, 112.0, 99.5, 100.5, 1000.0))
        assert upper_shadow_at_high(bars) == "bearish"

    def test_new_high_strong_close_is_no_signal(self):
        bars = flat_bars(60)
        bars.append((100.0, 112.0, 99.5, 111.5, 1000.0))  # 收最高附近
        assert upper_shadow_at_high(bars) is None

    def test_long_shadow_without_new_high_is_no_signal(self):
        bars = flat_bars(60, price=200.0)  # 歷史高檔在 200
        bars.append((100.0, 112.0, 99.5, 100.5, 1000.0))
        assert upper_shadow_at_high(bars) is None


class TestEngulfing:
    def test_bearish_engulfing_at_high(self):
        bars = [(100 + i * 0.5,) * 4 + (1000.0,) for i in range(60)]  # 緩漲至高檔
        bars.append((129.0, 130.0, 128.8, 129.8, 1000.0))  # 紅 K
        bars.append((130.0, 130.2, 128.0, 128.5, 1000.0))  # 黑 K 吞噬前日實體
        assert engulfing(bars) == "bearish"

    def test_bullish_engulfing_at_low(self):
        bars = [(130 - i * 0.5,) * 4 + (1000.0,) for i in range(60)]  # 緩跌至低檔
        bars.append((101.0, 101.2, 100.0, 100.2, 1000.0))  # 黑 K
        bars.append((100.0, 102.0, 99.8, 101.5, 1000.0))   # 紅 K 吞噬
        assert engulfing(bars) == "bullish"

    def test_engulfing_mid_range_is_no_signal(self):
        # 區間 90-110 震盪、收在中間 → 非高低檔，吞噬不觸發
        bars = [(p,) * 4 + (1000.0,) for _ in range(30) for p in (90.0, 110.0)]
        bars.append((100.0, 100.2, 99.8, 100.1, 1000.0))
        bars.append((100.2, 100.3, 99.5, 99.6, 1000.0))
        assert engulfing(bars) is None


class TestDojiAtHigh:
    def test_doji_near_high_signals(self):
        bars = [(100 + i * 0.5,) * 4 + (1000.0,) for i in range(60)]
        top = bars[-1][3]
        bars.append((top, top + 1.5, top - 1.5, top + 0.05, 1000.0))  # 十字星
        assert doji_at_high(bars) == "bearish"

    def test_doji_mid_range_is_no_signal(self):
        bars = flat_bars(60, price=200.0)
        bars.append((100.0, 101.5, 98.5, 100.05, 1000.0))
        assert doji_at_high(bars) is None


class TestSupportResistance:
    def test_levels_and_distances(self):
        closes = [100.0] * 239 + [90.0, 110.0]
        levels = support_resistance(closes)
        assert levels["close"] == 110.0
        assert levels["high60"] == 110.0
        assert levels["low60"] == 90.0
        assert levels["ma20"] == pytest.approx((100.0 * 18 + 90 + 110) / 20)
        assert levels["high240"] == 110.0
        # 距 60 日低點 +22.2%
        assert levels["dist_low60_pct"] == pytest.approx((110 - 90) / 90 * 100)

    def test_insufficient_history_omits_long_windows(self):
        levels = support_resistance([100.0] * 70)
        assert "high60" in levels
        assert "high240" not in levels


class TestScanMarket:
    def test_emits_pv_event_on_last_day_without_ohlc(self):
        from collector.signals import scan_market

        n = 100
        dates = [f"2026-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}" for i in range(n)]
        closes = [100.0 + i * 0.1 for i in range(n - 1)] + [115.0]  # 末日創高
        volumes = {d: 1000.0 for d in dates}
        volumes[dates[-1]] = 400.0  # 量縮
        events = scan_market(dates, closes, volumes, ohlc={}, lookback=10)
        assert any(e["id"] == "pv_divergence" and e["date"] == dates[-1] and e["direction"] == "bearish" for e in events)

    def test_candle_signals_need_ohlc(self):
        from collector.signals import scan_market

        n = 100
        dates = [f"2026-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}" for i in range(n)]
        closes = [100.0] * (n - 1) + [100.5]
        ohlc = {dates[-1]: (100.0, 112.0, 99.5, 100.5)}  # 創高長上影
        events = scan_market(dates, closes, {}, ohlc=ohlc, lookback=5)
        assert any(e["id"] == "upper_shadow" and e["direction"] == "bearish" for e in events)
