"""The page in a real browser (Playwright, Chromium). Skipped if unavailable."""

import pytest

from .conftest import EXAMPLES

sync_api = pytest.importorskip("playwright.sync_api")
R = pytest.mark.req


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:                       # browser not installed
            pytest.skip(f"Chromium not available: {e}")
        yield b
        b.close()


@pytest.fixture
def open_page(browser, server_url):
    pages = []

    def go(example="autopilot2", master=None):
        url = server_url(master or EXAMPLES / example / "master.csv")
        pg = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(url)
        pg.wait_for_selector(".st.active")
        pages.append((pg, errors))
        return pg

    yield go
    for pg, errors in pages:
        assert errors == []
        pg.close()


def panel(pg):
    return pg.locator(".panel-host")


def active(pg, machine_index=0):
    return pg.locator(".sm").nth(machine_index).locator(".st.active").text_content()


def wait_active(pg, state, machine_index=0):
    pg.wait_for_function(
        "([i, s]) => document.querySelectorAll('.sm')[i].querySelector('.st.active').textContent === s",
        arg=[machine_index, state])


def boxes(pg):
    loc = pg.locator(".st")
    return [loc.nth(i).bounding_box() for i in range(loc.count())]


@R("REQ-119", "REQ-120", "REQ-121", "REQ-124", "REQ-136")
def test_layout_built_from_model(open_page):
    pg = open_page()
    assert pg.locator(".sm h3").all_text_contents() == \
        ["Aircraft phase of flight", "Vertical guidance", "Lateral guidance", "Guidance source",
         "Autothrust"]
    assert pg.locator(".sm").first.locator(".st").all_text_contents()[:3] == \
        ["Waiting TOGA", "Takeoff", "Climb"]
    for i in range(5):
        assert pg.locator(".sm").nth(i).locator(".st.active").count() == 1
    assert pg.locator(".card h2").all_text_contents() == \
        ["Aircraft", "Stick and Throttle", "DMC and CLAWS requests", "CLAWS availability"]
    assert pg.locator(".card").nth(2).locator(".switch > span:first-child").all_text_contents()[:2] == \
        ["dmc_tracking_loc", "dmc_tracking_gs"]


@R("REQ-123")
def test_no_equations_rates_or_time_on_screen(open_page):
    text = open_page().locator("body").inner_text()
    for hidden in ("==", "radio_altitude < ", " Hz", "tick", "rationale"):
        assert hidden not in text


@R("REQ-126", "REQ-121")
def test_push_button_pulse_moves_the_state_machine(open_page):
    pg = open_page()
    assert active(pg) == "Waiting TOGA"
    pg.get_by_role("button", name="TOGA").click()
    wait_active(pg, "Takeoff")
    pg.wait_for_timeout(300)
    assert active(pg) == "Takeoff"


@R("REQ-122")
def test_hover_active_highlights_next_states_without_moving_anything(open_page):
    pg = open_page()
    pg.locator("#pause").click()
    pg.get_by_role("button", name="TOGA").click()
    pg.locator("#step").click()
    wait_active(pg, "Takeoff")
    card = pg.locator(".sm").first
    before = boxes(pg)
    card.locator(".st", has_text="Cruise").hover()               # inactive: nothing
    assert pg.locator(".st.next").count() == 0
    card.locator(".st.active").hover()
    assert card.locator(".st.next").all_text_contents() == ["Climb"]   # not global targets
    assert card.locator(".st.next-global").count() == 0
    assert boxes(pg) == before
    pg.mouse.move(5, 5)
    assert pg.locator(".st.next").count() == 0
    card.locator(".st.active").focus()                           # keyboard
    assert card.locator(".st.next").count() == 1


@R("REQ-125")
def test_widgets_write_inputs(open_page):
    pg = open_page()
    pg.locator("#pause").click()
    pg.locator(".switch", has_text="dmc_tracking_loc").click()
    panel(pg).get_by_role("button", name="FD").first.click()          # toggle on the panel
    pg.locator("#in-radio_altitude").focus()
    pg.keyboard.press("ArrowRight")
    pg.keyboard.press("ArrowRight")
    pg.select_option("#in-capa", "APPR1")
    pg.wait_for_timeout(300)
    pg.locator("#step").click()
    wait_active(pg, "No_Vertical_State", 1)                      # fd_on reached the engine
    vals = pg.locator(".card").first.locator(".val")
    assert vals.nth(0).text_content() == "0"                     # ground_speed untouched
    assert vals.nth(1).text_content() == "10"                    # two steps of 5
    assert pg.locator("#in-dmc_tracking_loc").is_checked()
    assert pg.locator("#in-capa").input_value() == "APPR1"


@R("REQ-127")
def test_lit_push_button_follows_the_logic(open_page):
    pg = open_page("autopilot")
    ap = pg.get_by_role("button", name="AP", exact=True)
    pg.locator(".switch", has_text="on_ground").click()
    pg.wait_for_timeout(200)
    ap.click()
    pg.wait_for_timeout(400)
    assert ap.get_attribute("aria-pressed") == "false"           # refused on ground
    pg.locator(".switch", has_text="on_ground").click()
    pg.wait_for_timeout(200)
    ap.click()
    pg.wait_for_function("document.querySelector('.pb.lit').classList.contains('on')")
    assert ap.get_attribute("aria-pressed") == "true"


@R("REQ-128", "REQ-129", "REQ-130")
def test_run_controls(open_page):
    pg = open_page()
    fast = pg.locator("#mode-fast")
    assert pg.locator("#mode-realtime").get_attribute("aria-pressed") == "true"
    fast.click()
    pg.wait_for_function("document.querySelector('#mode-fast').getAttribute('aria-pressed') === 'true'")
    assert pg.locator("#step").is_disabled()
    pg.locator("#pause").click()
    pg.wait_for_function("document.querySelector('#pause').textContent === 'Resume'")
    assert pg.locator("#step").is_enabled()
    pg.get_by_role("button", name="TOGA").click()
    pg.locator("#step").click()
    wait_active(pg, "Takeoff")
    pg.locator("#reset").click()
    wait_active(pg, "Waiting TOGA")
    assert pg.locator("#pause").text_content() == "Resume"       # still paused
    assert fast.get_attribute("aria-pressed") == "true"          # mode kept
    pg.locator("#pause").click()
    pg.wait_for_function("document.querySelector('#pause').textContent === 'Pause'")


@R("REQ-132")
def test_splitter_resizes_panes(open_page):
    pg = open_page()

    def width():
        return pg.locator("#left").bounding_box()["width"]

    def drag(x_from, x_to):
        y = 450
        pg.mouse.move(x_from, y)
        pg.mouse.down()
        pg.mouse.move(x_to, y, steps=5)
        pg.mouse.up()

    assert width() == 440
    x = pg.locator("#splitter").bounding_box()["x"] + 4
    drag(x, x + 100)
    assert width() == 540
    pg.locator("#splitter").focus()
    pg.keyboard.press("ArrowLeft")
    assert width() == 520
    x = pg.locator("#splitter").bounding_box()["x"] + 4
    drag(x, 0)
    assert width() == 280                                         # left minimum
    x = pg.locator("#splitter").bounding_box()["x"] + 4
    drag(x, 1440)
    assert width() == 1440 - 240                                  # right keeps 240 px


@R("REQ-133")
def test_names_are_shown_as_text(open_page, tmp_path):
    (tmp_path / "M.csv").write_text(
        "transition_id,current_state,next_state,default_state,equation,result_variable,rationale,title,order\n"
        "1,<b>A</b>,<img src=x onerror=alert(1)>,<b>A</b>,False,r,,,1\n", encoding="utf-8")
    (tmp_path / "inputs.csv").write_text(
        "variable_name,type,default_value,group,label\nx,bool,false,<i>G</i>,<u>lab</u>\n",
        encoding="utf-8")
    (tmp_path / "master.csv").write_text(
        "file_name,type,order,band\nM.csv,state_machine,1,10\ninputs.csv,inputs,,\n",
        encoding="utf-8")
    pg = open_page(master=tmp_path / "master.csv")
    assert pg.locator(".st").all_text_contents() == ["<b>A</b>", "<img src=x onerror=alert(1)>"]
    assert pg.locator(".card h2").text_content() == "<i>G</i>"
    assert pg.locator(".switch > span:first-child").text_content() == "<u>lab</u>"
    assert pg.locator("img, b, i, u").count() == 0


@R("REQ-135")
def test_push_button_look_and_press_feedback(open_page):
    pg = open_page()
    toga = pg.get_by_role("button", name="TOGA")
    style = lambda: toga.evaluate(   # noqa: E731
        "e => { const s = getComputedStyle(e); return [s.backgroundColor, s.borderTopColor]; }")
    assert style() == ["rgb(246, 248, 250)", "rgb(28, 36, 48)"]   # light grey, dark outline
    toga.click()
    assert "pressed" in toga.get_attribute("class")
    assert style() == ["rgb(220, 240, 250)", "rgb(0, 92, 153)"]   # light blue, blue outline
    pg.wait_for_timeout(700)
    assert "pressed" not in toga.get_attribute("class")
    assert style() == ["rgb(246, 248, 250)", "rgb(28, 36, 48)"]


@R("REQ-137")
def test_divider_position_is_remembered(open_page):
    pg = open_page()
    width = lambda: pg.locator("#left").bounding_box()["width"]   # noqa: E731
    pg.locator("#splitter").focus()
    for _ in range(3):
        pg.keyboard.press("ArrowRight")
    assert width() == 500
    pg.reload()
    pg.wait_for_selector(".st.active")
    assert width() == 500
    x = pg.locator("#splitter").bounding_box()["x"] + 4
    pg.mouse.move(x, 450); pg.mouse.down(); pg.mouse.move(x - 100, 450, steps=5); pg.mouse.up()
    pg.reload()
    pg.wait_for_selector(".st.active")
    assert width() == 400
    pg.evaluate("localStorage.setItem('statesim.leftPaneWidth', '5000')")   # too wide for the window
    pg.reload()
    pg.wait_for_selector(".st.active")
    assert width() == 1440 - 240



# ------------------------------------------------------------------ panels
@R("REQ-139")
def test_panel_in_full_width_top_pane(open_page):
    pg = open_page()
    top = pg.locator("#top").bounding_box()
    assert top["x"] == 0 and top["y"] == 0 and top["width"] == 1440
    host = panel(pg).bounding_box()
    assert host["width"] == pytest.approx(1185 * 0.75, abs=25)   # master scale 0.75
    assert pg.locator(".layout").bounding_box()["y"] >= top["height"] - 1
    for label in ("FD", "HDG", "NAV", "APPR", "AP", "AT", "XFR", "EDM", "FLC", "ALT", "VNAV", "VS", "FPA"):
        assert panel(pg).get_by_role("button", name=label, exact=True).count() >= 1
    assert panel(pg).get_by_role("slider").count() == 4


@R("REQ-139", "REQ-147")
def test_panel_scale_and_narrow_windows(browser, server_url):
    url = server_url(EXAMPLES / "autopilot2" / "master.csv")
    sizes = {}
    for vw in (1000, 450):
        pg = browser.new_page(viewport={"width": vw, "height": 900})
        pg.goto(url)
        pg.wait_for_selector(".st.active")
        pg.wait_for_timeout(300)
        host = pg.locator(".panel-host").bounding_box()
        sizes[vw] = (host["width"], host["height"])
        assert host["width"] <= vw - 24 + 1 and host["x"] >= 0   # never overflows
        pg.close()
    assert sizes[1000][0] == pytest.approx(1185 * 0.75, abs=25)  # scale 0.75 fits: unchanged
    assert sizes[450][0] < sizes[1000][0]                        # too narrow: smaller still
    ratio = lambda wh: wh[0] / wh[1]                              # noqa: E731
    assert ratio(sizes[450]) == pytest.approx(ratio(sizes[1000]), rel=0.03)   # proportions kept


@R("REQ-159")
def test_panels_stay_on_one_row(browser, server_url):
    """autopilot3: the FMA stays to the right of the FCP at any width."""
    url = server_url(EXAMPLES / "autopilot3" / "master.csv")
    widths = {}
    for vw in (1600, 900):
        pg = browser.new_page(viewport={"width": vw, "height": 900})
        pg.goto(url)
        pg.wait_for_selector(".st.active")
        pg.wait_for_timeout(300)
        fcp, fma = (h.bounding_box() for h in pg.locator(".panel-host").all())
        assert fma["x"] >= fcp["x"] + fcp["width"]                 # on the right
        assert fma["y"] == pytest.approx(fcp["y"], abs=1)           # same row, top-aligned
        assert fma["x"] + fma["width"] <= vw - 12 + 1               # never overflows
        widths[vw] = (fcp["width"], fma["width"])
        pg.close()
    assert widths[900][0] < widths[1600][0]                         # narrow: both smaller,
    assert widths[900][0] / widths[900][1] == pytest.approx(        # by the same factor
        widths[1600][0] / widths[1600][1], rel=0.03)


@R("REQ-142")
def test_panel_toggle_buttons_flip_their_input(open_page):
    pg = open_page()
    left_fd, right_fd = panel(pg).get_by_role("button", name="FD").all()
    left_fd.click()
    wait_active(pg, "No_Vertical_State", 1)                        # fd_on true
    assert left_fd.get_attribute("aria-pressed") == "true"
    assert right_fd.get_attribute("aria-pressed") == "true"         # same variable
    right_fd.click()
    wait_active(pg, "Vertical_State_0", 1)                         # fd_on false again
    assert "pressed" in right_fd.get_attribute("class")             # press feedback


@R("REQ-143", "REQ-144")
def test_knobs_turn_within_limits_and_show_formatted_values(open_page):
    pg = open_page()
    hdg = panel(pg).get_by_role("slider", name="HDG")
    readout = panel(pg).locator("[data-show=hdg_sel]")
    assert readout.text_content() == "090"
    hdg.focus()
    pg.keyboard.press("ArrowUp")
    pg.keyboard.press("PageUp")
    pg.wait_for_function("document.querySelector('.panel-host').shadowRoot"
                         ".querySelector('[data-show=hdg_sel]').textContent === '101'")
    pg.keyboard.press("End")
    pg.keyboard.press("ArrowUp")                                     # stops at 359
    pg.wait_for_function("document.querySelector('.panel-host').shadowRoot"
                         ".querySelector('[data-show=hdg_sel]').textContent === '359'")
    assert hdg.get_attribute("aria-valuenow") == "359"
    pg.keyboard.press("Home")
    pg.keyboard.press("ArrowDown")                                   # stops at 0
    pg.wait_for_function("document.querySelector('.panel-host').shadowRoot"
                         ".querySelector('[data-show=hdg_sel]').textContent === '000'")
    vs = panel(pg).get_by_role("slider", name="VS")
    box = vs.bounding_box()
    pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    pg.mouse.wheel(0, 100)                                           # wheel down: -100 fpm
    pg.wait_for_function("document.querySelector('.panel-host').shadowRoot"
                         ".querySelector('[data-show=vs_sel]').textContent === '-0100'")
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    pg.mouse.move(cx, cy - 6)                                        # press on the knob,
    pg.mouse.down()
    pg.mouse.move(cx + 60, cy, steps=8)                              # pointer to 3 o'clock
    pg.mouse.up()                                                    # mark follows: 225/270 of range
    pg.wait_for_function("document.querySelector('.panel-host').shadowRoot"
                         ".querySelector('[data-show=vs_sel]').textContent === '+4000'")
    pg.mouse.move(cx, cy - 6)
    pg.mouse.down()
    pg.mouse.move(cx + 60, cy + 1, steps=4)
    pg.mouse.move(cx + 20, cy + 60, steps=4)                         # into the bottom dead zone
    pg.mouse.up()                                                    # stays at the nearer end
    pg.wait_for_function("document.querySelector('.panel-host').shadowRoot"
                         ".querySelector('[data-show=vs_sel]').textContent === '+6000'")
    pg.locator("#pause").click()
    pg.locator("#step").click()
    pg.wait_for_timeout(200)
    assert pg.evaluate("1") == 1


@R("REQ-144")
def test_readout_formats(open_page):
    pg = open_page()
    fmt = lambda v, f: pg.evaluate("([v, f]) => StateSimPanels.format(v, f)", [v, f])  # noqa: E731
    assert fmt(90, "%03d") == "090"
    assert fmt(0, "%+05d") == "+0000"
    assert fmt(-500, "%+05d") == "-0500"
    assert fmt(1500, "%+05d") == "+1500"
    assert fmt(250, "%d") == "250"
    assert fmt(3.14159, "%.2f") == "3.14"
    assert fmt("ALT", "%s*") == "ALT*"
    assert fmt(7, "%4d|%-4d|") == "   7|7   |"


@R("REQ-145", "REQ-146")
def test_panel_lights_scripts_and_style_isolation(open_page, tmp_path):
    (tmp_path / "S.csv").write_text(
        "transition_id,current_state,next_state,default_state,equation,result_variable,rationale,title,order\n"
        "1,OFF,ON,OFF,go,r_on,,,1\n2,ON,OFF,,not go,r_off,,,2\n", encoding="utf-8")
    (tmp_path / "equations.csv").write_text(
        "equation,explanation,rationale,result_variable,band,order\nS == 'ON',,,on_light,10,5\n",
        encoding="utf-8")
    (tmp_path / "inputs.csv").write_text(
        "variable_name,type,default_value,widget,panel\ngo,bool,false,toggle,p.html\n", encoding="utf-8")
    (tmp_path / "p.html").write_text(
        "<html><head><style>body { background: red; } button { color: rgb(1, 2, 3); }"
        " .lit { outline: 3px solid lime; }</style>"
        "<script>window.panelScriptRan = true;</script></head><body>"
        "<button data-input=\"go\" data-lit-by=\"on_light\" onclick=\"window.inlineRan = true\">GO</button>"
        "</body></html>", encoding="utf-8")
    (tmp_path / "master.csv").write_text(
        "file_name,type,order,band\nS.csv,state_machine,1,10\nequations.csv,equations,,\n"
        "inputs.csv,inputs,,\np.html,panel,,\n", encoding="utf-8")
    pg = open_page(master=tmp_path / "master.csv")
    go = panel(pg).get_by_role("button", name="GO")
    assert "lit" not in (go.get_attribute("class") or "")
    go.click()
    wait_active(pg, "ON")
    pg.wait_for_function("document.querySelector('.panel-host').shadowRoot"
                         ".querySelector('button').classList.contains('lit')")   # light follows logic
    assert pg.evaluate("window.panelScriptRan === undefined && window.inlineRan === undefined")
    body_bg = pg.evaluate("getComputedStyle(document.body).backgroundColor")
    assert body_bg != "rgb(255, 0, 0)"                                # panel CSS stays inside
    page_btn = pg.locator("#pause").evaluate("e => getComputedStyle(e).color")
    assert page_btn != "rgb(1, 2, 3)"
    assert go.evaluate("e => getComputedStyle(e).color") == "rgb(1, 2, 3)"



@R("REQ-145")
def test_appr_light_on_the_fcp(open_page):
    pg = open_page()
    appr = panel(pg).get_by_role("button", name="APPR")
    pg.locator("#pause").click()
    assert "lit" not in (appr.get_attribute("class") or "")
    appr.click()                                                   # not in Descent: no light
    pg.locator("#step").click()
    pg.wait_for_timeout(300)
    assert "lit" not in (appr.get_attribute("class") or "")


@pytest.mark.req("REQ-125")
def test_switches_low_in_a_card_do_not_scroll_the_page(open_page):
    """#45: turning off a switch low in a long card (law_rollout and below on
    autopilot3) must not scroll the page and hide the top pane."""
    pg = open_page("autopilot3")
    top = pg.locator("#top")
    y0 = top.bounding_box()["y"]
    names = pg.evaluate("() => [...document.querySelectorAll('.switch input')].map(i => i.id)")
    laws = [n for n in names if n.startswith("in-law_")]
    assert len(laws) >= 8
    for n in laws:
        pg.locator(f"label.switch:has(#{n})").click()
        pg.wait_for_timeout(50)
        scrolled = pg.evaluate("""() => [document.scrollingElement.scrollTop, document.body.scrollTop,
                                          document.documentElement.scrollTop]""")
        assert scrolled == [0, 0, 0], f"{n}: page scrolled {scrolled}"
        assert top.bounding_box()["y"] == y0, f"{n}: the top pane moved"
    assert pg.evaluate("() => [...document.querySelectorAll('.switch input')].filter(i => i.id.startsWith('in-law_') && i.checked).length") == 0
