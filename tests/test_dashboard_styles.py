import colorsys
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
    body = source[source.index("<body>"):source.index("<script>", source.index("<body>"))]

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
    assert "var(--heat)" in _rule(source, ".mo-badge.heat-hot")   # 過熱側用獨立的紫色



TABS = ("overview", "nav", "regime", "momentum", "watchlist", "analysis", "library", "mood", "charts")


def _body():
    source = HTML.read_text()
    return source[source.index("<body>"):source.index("<script>", source.index("<body>"))]


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


def test_analysis_tab_has_article_pane_and_collapsible_date_tree():
    source = HTML.read_text()
    body = _body()
    card = body[body.index('id="analysis-card"'):body.index('id="hero"')]

    assert 'data-tab="analysis"' in re.search(r'<div\b[^>]*id="analysis-card"[^>]*>', body).group(0)
    assert 'id="an-article"' in card and 'id="an-tree"' in card
    assert re.search(r'<button[^>]*data-tab-target="analysis"[^>]*hidden', body)
    assert 'fetch("data/analysis/index.json")' in source
    assert "function renderAnalysisTree(" in source and "function renderArticle(" in source
    assert "grid-template-columns" in _rule(source, ".an-layout")
    assert "<details" in source or "createElement(\"details\")" in source


def test_entry_dates_link_to_that_days_analysis_of_the_same_stock():
    source = HTML.read_text()

    assert "an-stock-${s.code}" in source or 'an-stock-" + s.code' in source
    assert "AN.codes" in source and "an-app-link" in source
    assert "async function loadArticle(d, remember, focusCode)" in source
    assert "scrollIntoView" in source[source.index("async function loadArticle"):]


def test_library_tab_has_project_switch_article_pane_and_the_same_date_tree():
    source = HTML.read_text()
    body = _body()
    card = body[body.index('id="library-card"'):body.index('id="hero"')]

    assert 'data-tab="library"' in re.search(r'<div\b[^>]*id="library-card"[^>]*>', body).group(0)
    assert 'id="lib-article"' in card and 'id="lib-tree"' in card and 'id="lib-projects"' in card and 'id="lib-filter"' in card
    assert re.search(r'<button[^>]*data-tab-target="library"[^>]*hidden', body)
    assert 'fetch("data/archive_index.json")' in source
    assert "function renderLibraryTree(" in source and "function renderLibraryArticle(" in source
    assert "DOMParser" in source and 'removeAttribute("style")' in source  # 內文 html 需清理


def test_library_renders_transcripts_with_audio_players_and_clickable_timestamps():
    source = HTML.read_text()
    lib = source[source.index("function markdownToHtml("):source.index("function selectLibraryProject(")]

    assert "<audio" in lib and "lib-ts" in lib
    assert "currentTime" in lib
    assert "a.file" in lib  # 逐字稿檔名不是 article.md


def test_qa_transcripts_have_edit_buttons_and_a_settings_panel_backed_by_the_local_api():
    source = HTML.read_text()

    assert 'qaApi("api/qa/edit"' in source and 'qaApi("api/qa/config"' in source and "api/qa?folder=" in source
    assert "lib-edit-btn" in source and "lib-settings" in source and "data-key" in source
    assert "lib-edited" in source   # 編輯框靠它決定是否顯示「還原」
    assert ".lib-edited" not in source[source.index("<style>"):source.index("</style>")]   # 修改過的段落外觀與一般段落相同
    assert "orphaned_edits" in source  # 對不上的手動修改要提示


def test_qa_editing_tells_the_user_why_when_the_api_is_unavailable():
    source = HTML.read_text()
    fn = source[source.index("async function initQaEditing("):source.index("function editParagraph(")]

    assert "r.status === 404" in fn and "請重新啟動" in fn   # 舊版伺服器不能再靜默隱藏按鈕
    assert "lib-warn" in fn


def test_qa_edit_button_stays_dim_instead_of_lighting_up():
    source = HTML.read_text()
    style = source[source.index("<style>"):source.index("</style>")]

    assert "opacity: 0.35" in _rule(source, "#lib-article .lib-line .lib-edit-btn")
    assert not re.search(r"lib-edit-btn:(hover|focus)|:hover \.lib-edit-btn", style)
    assert not re.search(r"\(hover: none\)[^}]*lib-edit-btn", style)


THEMES = {"light": "明亮", "paper": "紙本", "celadon": "青瓷", "dark": "深色", "night": "夜讀"}


def _theme_tokens(source, theme):
    block = re.search(r':root\[data-theme="' + theme + r'"\]\s*\{([^}]+)\}', source)
    assert block, f"missing theme block: {theme}"
    return dict(re.findall(r"(--[\w-]+|color-scheme):\s*([^;]+);", block.group(1)))


def _luminance(hex_color):
    rgb = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a, b):
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_header_has_a_theme_picker_that_is_applied_before_first_paint():
    source = HTML.read_text()
    head = source[:source.index("<body>")]
    header = source[source.index("<header>"):source.index("</header>")]

    assert 'id="theme-select"' in header
    assert re.findall(r'<option value="(\w+)"', header) == ["auto", *THEMES]
    assert all(name in header for name in ["跟隨系統", *THEMES.values()])
    assert "<script>" in head and "dataset.theme" in head and '"dashboard-theme"' in head   # 繪製前套用，避免先閃預設色
    assert "prefers-color-scheme: dark" in head   # auto 跟隨系統明暗


def test_every_theme_defines_the_same_complete_token_set():
    source = HTML.read_text()
    tokens = {theme: _theme_tokens(source, theme) for theme in THEMES}
    expected = set(tokens["light"])

    assert {"--on-fill", "--card-top", "--heat", "--heat-wash", "color-scheme"} <= expected
    for theme, values in tokens.items():
        assert set(values) == expected, theme
        assert values["color-scheme"] == ("dark" if theme in ("dark", "night") else "light")


def test_every_theme_keeps_text_readable():
    source = HTML.read_text()
    for theme in THEMES:
        t = _theme_tokens(source, theme)
        for bg in (t["--surface-1"], t["--page"]):
            assert _contrast(t["--text-primary"], bg) >= 12, theme
            assert _contrast(t["--text-secondary"], bg) >= 7, theme
            assert _contrast(t["--text-muted"], bg) >= 4.5, theme   # 頂欄日期、頁尾直接在 page 上
        for ink in ("--accent", "--hot", "--good", "--warn", "--heat"):   # 色字都在卡片內
            assert _contrast(t[ink], t["--surface-1"]) >= 4.5, (theme, ink)
        for fill in ("--accent", "--hot", "--good", "--heat"):
            assert _contrast(t["--on-fill"], t[fill]) >= 4.5, (theme, fill)


def test_colored_fills_use_the_theme_on_fill_color_instead_of_hard_coded_white():
    source = HTML.read_text()
    style = source[source.index("<style>"):source.index("</style>")]

    assert not re.search(r"color:\s*(#fff\b|#ffffff\b|rgba\(255,\s*255,\s*255)", style)
    assert "#9a6bff" not in source   # 過熱紫改用 --heat，隨主題調整
    assert "@media (prefers-color-scheme" not in style   # 明暗由 data-theme 決定，auto 也解析成 light/dark


def test_qa_editing_is_attached_from_one_place_so_buttons_are_never_doubled():
    source = HTML.read_text()
    load = source[source.index("async function loadLibraryArticle("):source.index("function renderLibraryArticle(")]

    assert source.count("initQaEditing(") == 2   # 定義＋唯一呼叫點（ping 晚到時另行補掛會與這裡重複）
    assert "await LIB.api" in load


def test_accent_is_blue_or_teal_and_its_wash_is_the_same_hue():
    source = HTML.read_text()
    for theme in THEMES:
        t = _theme_tokens(source, theme)
        rgb = tuple(int(t["--accent"][i:i + 2], 16) for i in (1, 3, 5))
        hue = colorsys.rgb_to_hls(*(c / 255 for c in rgb))[0] * 360

        assert 180 <= hue <= 215, (theme, t["--accent"], hue)   # 藍／青色系，不用紫
        assert t["--cold"] == t["--accent"], theme
        assert t["--cold-wash"].startswith("rgba(%d,%d,%d," % rgb), theme


def test_article_layouts_fit_phone_width_even_with_long_urls():
    source = HTML.read_text()

    narrow = source[source.index("@media (max-width: 860px) {"):]
    narrow = narrow[:narrow.index("\n}\n")]

    assert "grid-template-columns: minmax(0, 1fr)" in _rule(narrow, ".an-layout")   # 1fr 會被長網址撐到 760px
    assert "overflow-wrap: anywhere" in _rule(source, "#lib-article .lib-body")
    assert source.index("@media (max-width: 860px) {") > source.index("#lib-tree {")   # 要寫在列表基本樣式之後才蓋得過


def test_article_lists_sit_above_the_text_on_narrow_screens_without_floating_over_it():
    source = HTML.read_text()
    narrow = source[source.index("@media (max-width: 860px) {"):]
    narrow = narrow[:narrow.index("\n}\n")]
    rule = _rule(narrow, "#an-tree, #lib-tree")
    load = source[source.index("async function loadLibraryArticle("):source.index("function renderLibraryArticle(")]

    assert "order: -1" in rule and "position: static" in rule   # sticky 列表會蓋住內文
    assert 'scrollBelowHeader(el("lib-article"))' in load   # 選文章後捲到內文，不是列表
    assert "scrollBy(0, -" not in source   # 頂欄高度隨螢幕寬度變，不寫死位移


def test_transcript_text_uses_the_full_width_on_phones():
    source = HTML.read_text()
    phone = source[source.index("@media (max-width: 600px) {  /* 手機逐字稿"):]
    phone = phone[:phone.index("\n}\n")]

    assert "grid-row: 2" in phone and "grid-column: 1 / -1" in phone   # 時間碼與「修改」一列，內文在下一列用滿寬度


def test_failure_point_dash_style_applies_to_the_line_not_its_label():
    source = HTML.read_text()

    assert "stroke-dasharray" in _rule(source, ".kchart line.anchor")
    assert ".kchart .anchor {" not in source   # 會連標籤 <text class="lbl anchor"> 一起描上虛線外框


def test_list_temperature_chart_shows_recent_and_background_averages_of_daily_points():
    source = HTML.read_text()
    body = _body()
    block = source[source.index("// 名單溫度走勢"):source.index("// 個股頻率標色")]

    assert "觀察 ≥5 檔 +2／1–4 檔 +1／只剩稍微觀察 −1／掛零 −2" in body and "0 以上＝健康" not in body
    assert re.findall(r'<button type="button" data-ma="(\d)"', body) == ["3", "5"]   # 近況的平滑天數可切換
    assert "trailingMean(points, scoreMa)" in block and "trailingMean(points, 20)" in block   # 近況＋背景，用完整序列算
    assert "second:" in block and "var(--series-2)" in block               # 背景線用第二個系列色
    assert "bars:" in block and "ticks: [-2, -1, 0, 1, 2]" in block        # 柱＝當日給分
    assert "from: -2, to: -0.5" in block and "極冷" in block               # 極冷區標示，不叫警戒
    assert '"wl-score-ma"' in block


def test_each_stock_analysis_is_collapsed_and_reachable_from_a_clickable_index_on_top():
    source = HTML.read_text()
    render = source[source.index("function renderArticle("):source.index("function initAnalysis(")]
    load = source[source.index("async function loadArticle("):source.index("function renderArticle(")]

    assert 'h("details", "an-stock")' in render and ".open = true" not in render   # 每檔預設摺疊
    assert "an-index" in render and "盯盤名單" in render and "今日觀察" in render and "今日稍微觀察" in render
    assert "openStock(s.code)" in render                                            # 點清單 → 展開並跳到該檔
    assert "function openStock(" in source and "openStock(focusCode)" in load       # 入選日期連結也會展開
    assert "list-style: none" in _rule(source, "#an-article .an-stock > summary")


def test_add_conditions_block_is_left_out_when_the_analysis_has_nothing_to_say():
    source = HTML.read_text()
    render = source[source.index("function renderArticle("):source.index("function initAnalysis(")]

    assert '["加碼條件", s.add]' in render and "if (!items.length) continue;" in render


def test_holdings_show_live_prices_and_todays_alerts_refreshed_every_30_seconds():
    source = HTML.read_text()
    live = source[source.index("function applyLive("):source.index("function initHoldForm(")]

    assert 'fetch("data/live.json", { cache: "no-store" })' in live and "setInterval(pollLive, 30000)" in source
    assert "hold-live" in live and "hold-alert" in live
    assert "item.date !== today" in live                       # 不是今天的報價不顯示
    assert "applyLive(LIVE)" in source[source.index("function renderHoldings("):source.index("function applyLive(")]   # 重畫持股列後補回
    assert "var(--good)" in _rule(source, ".hold-alert.add") and "var(--hot)" in _rule(source, ".hold-alert.reduce")
