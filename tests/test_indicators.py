import math

import pytest

from collector.indicators import bias_ratio, realized_vol, rate_of_change


class TestBiasRatio:
    def test_close_above_moving_average_is_positive(self):
        closes = [100.0] * 239 + [100.0, 110.0]
        # 240 日均 =（239 個 100 + 一個 110）平均之前的最後 240 筆
        result = bias_ratio(closes, window=240)
        ma = (100.0 * 239 + 110.0) / 240
        assert result == pytest.approx((110.0 - ma) / ma * 100)

    def test_insufficient_history_returns_none(self):
        assert bias_ratio([100.0] * 10, window=240) is None


class TestRealizedVol:
    def test_constant_prices_have_zero_vol(self):
        assert realized_vol([100.0] * 30, window=20) == 0.0

    def test_annualized_vol_of_alternating_returns(self):
        # 每日 +1%/-1% 交替，日報酬標準差已知，年化 = std * sqrt(252)
        closes = [100.0]
        for i in range(30):
            closes.append(closes[-1] * (1.01 if i % 2 == 0 else 0.99))
        result = realized_vol(closes, window=20)
        rets = [math.log(closes[i] / closes[i - 1]) for i in range(-20, 0)]
        mean = sum(rets) / len(rets)
        std = math.sqrt(sum((r - mean) ** 2 for r in rets) / (len(rets) - 1))
        assert result == pytest.approx(std * math.sqrt(252) * 100)

    def test_insufficient_history_returns_none(self):
        assert realized_vol([100.0] * 5, window=20) is None


class TestRateOfChange:
    def test_20_day_change_percent(self):
        values = [100.0] * 20 + [120.0]
        assert rate_of_change(values, window=20) == pytest.approx(20.0)

    def test_insufficient_history_returns_none(self):
        assert rate_of_change([100.0] * 5, window=20) is None
