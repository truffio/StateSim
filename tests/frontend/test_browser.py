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
        ["Aircraft", "Flight Control Panel", "Stick and Throttle", "DMC and CLAWS requests",
         "CLAWS availability"]
    assert pg.locator(".card").nth(1).locator(".switch > span:first-child").all_text_contents() == \
        ["fd_on", "ap_on", "appr_selected"]


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
    assert card.locator(".st.next").all_text_contents() == ["Climb", "EDM", "Touchdown"]
    assert card.locator(".st.next-global").all_text_contents() == ["EDM", "Touchdown"]
    assert boxes(pg) == before
    pg.mouse.move(5, 5)
    assert pg.locator(".st.next").count() == 0
    card.locator(".st.active").focus()                           # keyboard
    assert card.locator(".st.next").count() == 3


@R("REQ-125")
def test_widgets_write_inputs(open_page):
    pg = open_page()
    pg.locator("#pause").click()
    pg.locator(".switch", has_text="fd_on").click()
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
    assert pg.locator("#in-fd_on").is_checked()
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
        "transition_id,current_state,next_state,default_state,equation,result_variable,rationale,title,band,order\n"
        "1,<b>A</b>,<img src=x onerror=alert(1)>,<b>A</b>,False,r,,,10,1\n", encoding="utf-8")
    (tmp_path / "inputs.csv").write_text(
        "variable_name,type,default_value,group,label\nx,bool,false,<i>G</i>,<u>lab</u>\n",
        encoding="utf-8")
    (tmp_path / "master.csv").write_text(
        "file_name,type,order\nM.csv,state_machine,1\ninputs.csv,inputs,\n", encoding="utf-8")
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
