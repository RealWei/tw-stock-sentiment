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

    assert "名單（自起始日起 90 個交易日）" in source
    assert 'id="wl-cal-from"' in source  # 溫度計起始日 picker
    assert "lo.setDate(lo.getDate() - 29)" not in source
    assert "grid-template-columns: repeat(15" in grid_rule
    assert "grid-template-rows: repeat(6" in grid_rule
    assert "grid-auto-flow: column" in grid_rule
    assert "data.days.slice(start, start + 90)" in source  # 自起始日起 90 個交易日
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


def test_regime_card_sits_above_watchlist_with_three_month_grid():
    source = HTML.read_text()
    grid_rule = _rule(source, ".rg-grid")

    assert source.index('id="mode-card"') < source.index('id="regime-card"') < source.index('id="watchlist-card"')
    assert "grid-template-columns: repeat(13" in grid_rule
    assert "grid-template-rows: repeat(5" in grid_rule
    assert "grid-auto-flow: column" in grid_rule
    assert 'fetch("data/regime.json")' in source


def test_regime_grid_has_a_start_date_picker_like_the_watchlist():
    source = HTML.read_text()
    card = source[source.index('id="regime-card"'):source.index('id="watchlist-card"')]

    assert 'class="wl-range" id="rg-cal-range"' in card
    assert 'id="rg-cal-from"' in card
    assert 'id="rg-cal-hint"' in card
    assert card.index('id="rg-legend"') < card.index('id="rg-hint"') < card.index('id="rg-signals"') < card.index('id="rg-reminders"')
    assert "data.days.slice(start, start + 65)" in source  # 自起始日起 65 個交易日（13×5）
    assert "rgFrom.onchange = drawRegimeGrid" in source


def test_regime_card_has_chip_small_multiples_between_legend_and_hints():
    source = HTML.read_text()
    card = source[source.index('id="regime-card"'):source.index('id="watchlist-card"')]

    assert card.index('id="rg-legend"') < card.index('id="rg-charts"') < card.index('id="rg-hint"')
    assert 'id="rg-hl"' in card and 'id="rg-table"' in card  # 今日重點列＋資料表（tooltip 不是唯一管道）
    assert "renderChipCharts(data, start, start + w.length)" in source  # 與方格共用日期窗口
    assert "--series-2: #eb6834" in source and "--series-2: #d95926" in source  # 明暗各選一階，已過 palette 驗證


def test_momentum_card_sits_between_regime_and_watchlist_with_meter_and_parts():
    source = HTML.read_text()

    assert source.index('id="regime-card"') < source.index('id="momentum-card"') < source.index('id="watchlist-card"')
    card = source[source.index('id="momentum-card"'):source.index('id="watchlist-card"')]
    assert 'id="mo-score"' in card and 'id="mo-dot"' in card and 'id="mo-parts"' in card
    assert 'id="mo-chart"' in card and 'id="mo-picks"' in card
    assert 'fetch("data/momentum.json")' in source
    assert "function renderMomentum(" in source
    assert "grid-template-columns" in _rule(source, ".mo-part")


def test_momentum_card_shows_an_independent_overheat_side():
    source = HTML.read_text()
    card = source[source.index('id="momentum-card"'):source.index('id="watchlist-card"')]

    assert 'id="mo-heat"' in card and 'id="mo-heat-parts"' in card and 'id="mo-heat-chart"' in card
    assert "mo.heat_level" in source
    assert "#9a6bff" in _rule(source, ".mo-badge.heat-hot")



TABS = ("overview", "nav", "regime", "momentum", "watchlist", "mood", "charts")


def _body():
    source = HTML.read_text()
    return source[source.index("<body>"):source.index("<script>")]


def test_every_big_block_is_its_own_tab_with_an_overview_first():
    body = _body()

    targets = re.findall(r'data-tab-target="([a-z]+)"', body)
    assert tuple(targets) == TABS
    for block in re.findall(r'^<div\b[^>]*>', body, flags=re.M):
        if 'id="error"' in block:
            continue
        assert re.search(r'data-tab="(%s)"' % "|".join(TABS), block), block
    tag = lambda el_id: re.search(r'<div\b[^>]*id="%s"[^>]*>' % el_id, body).group(0)  # noqa: E731
    expected = {"overview": "overview", "mode-card": "nav", "regime-card": "regime", "momentum-card": "momentum",
                "watchlist-card": "watchlist", "hero": "mood", "position-card": "mood", "cards": "mood",
                "signals": "charts", "money-card": "charts"}
    for el_id, tab in expected.items():
        assert 'data-tab="%s"' % tab in tag(el_id), el_id


def test_tabs_do_not_split_the_contents_of_a_big_block():
    body = _body()
    inside = lambda outer, nxt: body[body.index('id="%s"' % outer):body.index('id="%s"' % nxt)]  # noqa: E731

    assert 'id="hold-section"' in inside("mode-card", "regime-card")
    assert 'id="mo-picks"' in inside("momentum-card", "watchlist-card")
    assert 'id="mo-heat-chart"' in inside("momentum-card", "watchlist-card")
    watch = inside("watchlist-card", "hero")
    assert 'id="wl-form"' in watch and 'id="wl-calendars"' in watch and 'id="wl-list"' in watch


def test_overview_has_clickable_summary_tiles_and_local_only_tabs_start_hidden():
    source = HTML.read_text()
    body = _body()

    assert 'id="ov-tiles"' in body and 'id="ov-notes"' in body
    assert "function renderOverview(" in source and "function ovSet(" in source
    for tab in ("nav", "regime", "momentum", "watchlist"):
        assert re.search(r'<button[^>]*data-tab-target="%s"[^>]*hidden' % tab, body), tab
    assert "grid-template-columns" in _rule(source, "#ov-tiles")
    assert ".tab-off" in source
