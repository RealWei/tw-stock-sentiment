from collector.storage import load_history, upsert
from collector.pipeline import derive_indicator_series, daily_snapshot


class TestStorage:
    def test_upsert_and_load_round_trip(self, tmp_path):
        path = tmp_path / "history.csv"
        upsert(path, "taiex_close", [("2026-07-01", 47018.99)])
        upsert(path, "taiex_close", [("2026-07-02", 46744.16)])
        history = load_history(path)
        assert history["taiex_close"] == [
            ("2026-07-01", 47018.99),
            ("2026-07-02", 46744.16),
        ]

    def test_upsert_same_date_overwrites(self, tmp_path):
        path = tmp_path / "history.csv"
        upsert(path, "vix", [("2026-07-01", 20.0)])
        upsert(path, "vix", [("2026-07-01", 21.5)])
        assert load_history(path)["vix"] == [("2026-07-01", 21.5)]


class TestDeriveIndicatorSeries:
    def test_breadth_ratio_smoothed_over_20_days(self):
        raw = {"breadth_ratio": [(f"2026-01-{d:02d}", 0.5) for d in range(1, 26)]}
        derived = derive_indicator_series(raw)
        # 前 19 筆資料不足無值，之後每筆為前 20 筆平均
        assert len(derived["breadth_ma20"]) == 6
        assert derived["breadth_ma20"][-1] == ("2026-01-25", 0.5)

    def test_raw_passthrough_indicators(self):
        raw = {"pc_oi_ratio": [("2026-07-01", 98.68)]}
        derived = derive_indicator_series(raw)
        assert derived["pc_oi_ratio"] == [("2026-07-01", 98.68)]


class TestDailySnapshot:
    def test_composite_and_zone_from_derived_series(self):
        # 兩個假指標，今天的值都在歷史高檔 → 總分高 → 過熱
        dates = [f"2025-{m:02d}-01" for m in range(1, 13)] + ["2026-07-08"]
        greed = {  # invert=False，遞增 → 今天是最高 → 100 分
            "margin_roc20": [(d, i) for i, d in enumerate(dates)],
            "vol20": [(d, 30 - i) for i, d in enumerate(dates)],  # invert=True，遞減 → 也貪婪
        }
        snap = daily_snapshot(greed, "2026-07-08")
        assert snap["date"] == "2026-07-08"
        assert snap["scores"]["margin_roc20"] > 90
        assert snap["scores"]["vol20"] > 90
        assert snap["composite"] > 90
        assert snap["zone"] == "overheat"

    def test_indicator_without_today_value_uses_recent_latest(self):
        # 當日沒資料但 14 天內有 → 沿用最近一筆（且不受輸入排序影響）
        series = {"pe": [("2026-07-06", 25.0), ("2026-07-01", 20.0), ("2026-06-20", 15.0)]}
        snap = daily_snapshot(series, "2026-07-08")
        assert snap["values"]["pe"] == 25.0

    def test_stale_daily_indicator_is_excluded(self):
        # 日更指標超過 5 個交易日沒資料 → 視為缺值不計分
        series = {"pc_oi_ratio": [("2026-05-01", 100.0), ("2026-05-02", 110.0)]}
        snap = daily_snapshot(series, "2026-07-08")
        assert snap["scores"]["pc_oi_ratio"] is None


class TestCompositeSeries:
    def test_returns_score_for_each_trading_date(self):
        from collector.pipeline import composite_series

        dates = [f"2026-01-{d:02d}" for d in range(1, 11)]
        derived = {"pc_oi_ratio": [(d, float(i)) for i, d in enumerate(dates)]}
        series = composite_series(derived)
        assert [d for d, _ in series] == dates
        # 遞增序列 → 最後一天分數最高（invert=True 的 P/C 比會反轉 → 最低）
        assert series[-1][1] < series[0][1]


class TestDualMeters:
    def test_meters_align_staggered_extremes_within_5_days(self):
        from collector.pipeline import dual_meters

        dates = [f"2026-{m:02d}-{d:02d}" for m in range(1, 7) for d in range(1, 29)]
        n = len(dates)
        # 過熱組指標各自在最後 5 天內「不同天」創極端（新高或反向指標新低）
        derived = {}
        for k, ind in enumerate(["foreign_net_oi", "margin_roc20", "pc_oi_ratio"]):
            sign = -1.0 if ind == "pc_oi_ratio" else 1.0  # 反向指標用遞減
            vals = [sign * float(i) for i in range(n)]
            vals[-1 - k] = sign * float(n + 10)  # 極端日錯開在最後 5 天內
            vals[-1] = vals[-1] if k == 0 else sign * float(n - 30)  # 當天本身不極端
            derived[ind] = list(zip(dates, vals))
        greed, fear = dual_meters(derived, dates[-1])
        assert greed is not None and greed > 90

    def test_meters_need_at_least_3_indicators(self):
        from collector.pipeline import dual_meters

        dates = [f"2026-01-{d:02d}" for d in range(1, 29)]
        derived = {"vol20": [(d, 1.0) for d in dates]}
        greed, fear = dual_meters(derived, dates[-1])
        assert greed is None
        assert fear is None

    def test_zone_from_meters(self):
        from collector.pipeline import zone_from_meters

        assert zone_from_meters(85.0, 50.0) == "overheat"
        assert zone_from_meters(50.0, 10.0) == "cold"
        assert zone_from_meters(50.0, 50.0) == "neutral"
        assert zone_from_meters(None, None) is None
        # 兩邊同時極端 → 恐慌優先（避免高波動期誤報過熱）
        assert zone_from_meters(85.0, 10.0) == "cold"
