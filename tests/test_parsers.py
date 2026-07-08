import json
from pathlib import Path

from collector.fetchers import (
    parse_margin_balance,
    parse_breadth,
    parse_taiex_closes,
    parse_put_call_oi_ratio,
    parse_foreign_futures_net_oi,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text())


def test_parse_margin_balance_returns_today_balance_in_thousands():
    date, balance = parse_margin_balance(load("mi_margn.json"))
    assert date == "2026-07-07"
    assert balance == 610_945_256


def test_parse_breadth_uses_stock_column():
    date, up, down = parse_breadth(load("mi_index_ms.json"))
    assert date == "2026-07-07"
    assert up == 128
    assert down == 892


def test_parse_taiex_closes_converts_roc_dates():
    closes = parse_taiex_closes(load("fmtqik.json"))
    assert closes[0] == ("2026-07-01", 47018.99)
    assert all(d.startswith("2026-07") for d, _ in closes)


def test_parse_put_call_oi_ratio_returns_series():
    series = parse_put_call_oi_ratio(load("put_call_ratio.json"))
    assert ("2026-07-07", 98.68) in series


def test_parse_foreign_futures_net_oi_picks_tx_foreign():
    date, net = parse_foreign_futures_net_oi(load("fut_inst.json"))
    assert date == "2026-07-07"
    assert net == -80042


def test_parse_pe_yield_medians_skips_non_numeric():
    from collector.fetchers import parse_pe_yield_medians

    date, pe, dy = parse_pe_yield_medians(load("bwibbu_d.json"))
    assert date == "2026-07-07"
    # fixture 前 12 檔中台泥本益比為 '-'，需排除後取中位數
    assert pe > 0
    assert dy > 0


def load_csv(name):
    return (FIXTURES / name).read_text()


def test_parse_pc_ratio_csv_takes_oi_ratio_column():
    from collector.bootstrap import parse_pc_ratio_csv

    series = parse_pc_ratio_csv(load_csv("pc_ratio_down.csv"))
    assert ("2026-06-30", 134.93) in series
    assert len(series) == 21  # 22 行含表頭


def test_parse_fut_contracts_csv_picks_tx_foreign_net_oi():
    from collector.bootstrap import parse_fut_contracts_csv

    series = parse_fut_contracts_csv(load_csv("fut_contracts_down.csv"))
    assert ("2026-06-25", -81051.0) in series
