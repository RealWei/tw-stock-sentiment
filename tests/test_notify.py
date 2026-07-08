from collector.notify import notification_message, should_notify


class TestShouldNotify:
    def test_entering_extreme_zone_notifies(self):
        assert should_notify("neutral", "overheat") is True
        assert should_notify("neutral", "cold") is True

    def test_leaving_extreme_zone_notifies(self):
        assert should_notify("overheat", "neutral") is True

    def test_no_change_stays_silent(self):
        assert should_notify("neutral", "neutral") is False
        assert should_notify("overheat", "overheat") is False

    def test_first_run_without_previous_state_stays_silent(self):
        assert should_notify(None, "neutral") is False

    def test_first_run_directly_in_extreme_notifies(self):
        assert should_notify(None, "overheat") is True


class TestNotificationMessage:
    def test_overheat_message_mentions_reduce(self):
        snap = {
            "date": "2026-07-08",
            "composite": 85.2,
            "zone": "overheat",
            "scores": {"margin_roc20": 97.0, "vol20": 60.0},
            "values": {"margin_roc20": 15.3, "vol20": 18.0},
        }
        msg = notification_message(snap)
        assert "過熱" in msg
        assert "85" in msg
        assert "減碼" in msg
        # 達 95 百分位的單項指標要列出
        assert "融資餘額20日增減" in msg

    def test_cold_message_mentions_add(self):
        snap = {
            "date": "2026-07-08",
            "composite": 12.0,
            "zone": "cold",
            "scores": {"vol20": 3.0},
            "values": {"vol20": 45.0},
        }
        msg = notification_message(snap)
        assert "過冷" in msg
        assert "加碼" in msg
        assert "大盤20日波動率" in msg
