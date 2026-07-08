import pytest

from collector.scoring import (
    percentile_rank,
    indicator_score,
    composite_score,
    zone,
)


class TestPercentileRank:
    def test_value_above_all_history_is_100(self):
        assert percentile_rank([1, 2, 3, 4], 5) == 100.0

    def test_value_below_all_history_is_0(self):
        assert percentile_rank([1, 2, 3, 4], 0) == 0.0

    def test_value_in_middle(self):
        assert percentile_rank([1, 2, 3, 4], 2.5) == 50.0

    def test_tie_uses_midrank(self):
        # 1 個比 2 小、1 個等於 2 → (1 + 0.5) / 4 = 37.5
        assert percentile_rank([1, 2, 3, 4], 2) == 37.5

    def test_empty_history_raises(self):
        with pytest.raises(ValueError):
            percentile_rank([], 1)


class TestIndicatorScore:
    def test_greed_direction_keeps_percentile(self):
        assert indicator_score([1, 2, 3, 4], 5, invert=False) == 100.0

    def test_fear_direction_inverts_percentile(self):
        # VIX 很高 → 恐慌 → 分數低
        assert indicator_score([1, 2, 3, 4], 5, invert=True) == 0.0


class TestCompositeScore:
    def test_equal_weighted_mean(self):
        assert composite_score({"pe": 80.0, "vix": 20.0}) == 50.0

    def test_missing_indicator_is_ignored(self):
        assert composite_score({"pe": 80.0, "vix": 20.0, "pcr": None}) == 50.0

    def test_all_missing_returns_none(self):
        assert composite_score({"pe": None}) is None


class TestZone:
    def test_80_or_above_is_overheat(self):
        assert zone(80.0) == "overheat"

    def test_20_or_below_is_cold(self):
        assert zone(20.0) == "cold"

    def test_middle_is_neutral(self):
        assert zone(50.0) == "neutral"
