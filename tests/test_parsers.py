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
