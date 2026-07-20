import re
from pathlib import Path


HTML = Path(__file__).parents[1] / "docs" / "index.html"


def _rule(source, selector):
    match = re.search(re.escape(selector) + r"\s*\{([^}]+)\}", source)
    assert match, f"missing CSS rule: {selector}"
    return match.group(1)


def test_frequent_watchlist_name_uses_mesh_gradient_without_legacy_shimmer():
    source = HTML.read_text()
    rule = _rule(source, ".wl-name.freq5")

    assert "var(--hot)" not in rule
    assert rule.count("radial-gradient(") >= 3
    assert "background-clip: text" in rule
    assert "wl-name-shimmer" not in source


def test_holding_row_uses_centered_identity_and_stacked_detail_rows():
    source = HTML.read_text()

    assert "grid-template-columns: minmax(140px, 170px) minmax(0, 1fr) 24px" in _rule(source, ".hold-row")
    assert "align-items: center" in _rule(source, ".hold-identity")
    assert 'identity.className = "hold-identity"' in source
    assert 'details.className = "hold-details"' in source
    assert 'statusRow.className = "hold-info-row hold-status-row"' in source
    assert "statusRow.append(lvl, s, stage)" in source
    assert 'techRow.className = "hold-info-row hold-tech-row"' in source
    assert "row.append(identity, details, del)" in source
    assert "hold-info-label" not in source


def test_navigation_and_watchlist_are_the_first_two_dashboard_cards():
    source = HTML.read_text()
    body = source[source.index("<body>"):source.index("<script>")]

    assert body.count('id="mode-card"') == 1
    assert body.count('id="watchlist-card"') == 1
    assert body.index('id="mode-card"') < body.index('id="watchlist-card"')
    assert body.index('id="watchlist-card"') < body.index('id="hero"')


def test_empty_watchlist_text_uses_warning_color_instead_of_risk_red():
    source = HTML.read_text()
    rule = _rule(source, ".wl-row .none")

    assert "var(--warn)" in rule
    assert "var(--hot)" not in rule


def test_watchlist_renders_the_full_90_trading_day_payload():
    source = HTML.read_text()
    grid_rule = _rule(source, ".wl-cal-grid")

    assert "近 90 個交易日名單" in source
    assert "lo.setDate(lo.getDate() - 29)" not in source
    assert "grid-template-columns: repeat(15" in grid_rule
    assert "grid-template-rows: repeat(6" in grid_rule
    assert "grid-auto-flow: column" in grid_rule
    assert "const gridDays = data.days.slice(-90)" in source
    assert "for (const e of gridDays)" in source
    assert 'day.textContent = e.date.slice(5).replace("-", "/")' in source
    assert "for (const m0 of months)" not in source


def test_watchlist_renders_every_daily_light_at_the_bottom_of_each_cell():
    source = HTML.read_text()
    light_row_rule = _rule(source, ".wl-lights")
    cell_rule = _rule(source, ".wl-cell")

    assert "display: flex" in cell_rule
    assert "flex-direction: column" in cell_rule
    assert "margin-top: auto" in light_row_rule
    assert "padding-top: 6px" in light_row_rule
    assert "for (const level of (e.lights" in source
    assert "cell.appendChild(lights)" in source
    assert "格底圓點＝每條當日燈號" in source
