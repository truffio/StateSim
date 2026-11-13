"""The Timeline pane in a real browser, fed live by the real server and engine.

Everything is driven through the UI (buttons, switches, sliders) on the
example models. Skipped if Playwright or Chromium is missing.
"""

import pytest

from .test_browser import browser, open_page, panel, wait_active  # noqa: F401  (fixtures and helpers)

R = pytest.mark.req


def frame(pg):
    """Wait until the batched redraw has run."""
    pg.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")


def show(pg):
    pg.locator("#timeline-toggle").click()
    pg.wait_for_selector("#timeline", state="visible")


def ticks(pg):
    return pg.locator("#timeline .tl-tick")


def dots(pg):
    return pg.locator("#timeline .tl-dot")


def wait_count(pg, selector, n):
    pg.wait_for_function("([s, n]) => document.querySelectorAll(s).length === n", arg=[selector, n])


def tick_by_title(pg, text):
    """The transition tick whose tooltip (title element) contains text."""
    return pg.locator("#timeline .tl-tick", has=pg.locator("title", has_text=text))


def dot_by_name(pg, name, value):
    return pg.locator("#timeline .tl-dot", has=pg.locator("title", has_text=f"{name} = {value}"))


def click_centre(pg, loc):
    """Overlapping marks: click at the circle/rect centre with the mouse."""
    box = loc.bounding_box()
    pg.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)


def drive_autopilot2_to_ifcc(pg):
    """AP on, approach selected, 1000 ft, localiser then glide slope: Guidance source takes IFCC."""
    panel(pg).get_by_role("button", name="AP", exact=True).click()
    wait_active(pg, "No_Lateral_State", 2)
    pg.locator("#in-radio_altitude").fill("1000")
    panel(pg).get_by_role("button", name="APPR", exact=True).click()
    pg.locator(".switch", has_text="dmc_tracking_loc").click()
    wait_active(pg, "preLocTrk", 2)
    pg.locator(".switch", has_text="dmc_tracking_gs").click()
    wait_active(pg, "IFCC", 3)
    wait_active(pg, "LocTrk", 2)
    wait_active(pg, "GsTrk", 1)


@R("REQ-176", "REQ-188")
def test_timeline_button_toggles_pane_and_setting_survives_reload(open_page):
    pg = open_page("autopilot3")
    toggle = pg.locator("#timeline-toggle")
    assert toggle.get_attribute("aria-pressed") == "false"
    assert not pg.locator("#timeline").is_visible()
    show(pg)
    assert toggle.get_attribute("aria-pressed") == "true"
    pg.get_by_role("button", name="TOGA").click()                 # something to see after the reload
    pg.wait_for_selector("#timeline .tl-tick")
    n = ticks(pg).count()
    pg.reload()
    pg.wait_for_selector(".st.active")
    assert pg.locator("#timeline").is_visible()
    assert pg.locator("#timeline-toggle").get_attribute("aria-pressed") == "true"
    pg.wait_for_selector("#timeline .tl-tick")                    # the server sends the timeline on connect
    assert ticks(pg).count() == n
    pg.locator("#timeline-toggle").click()
    assert not pg.locator("#timeline").is_visible()
    assert pg.locator("#timeline-toggle").get_attribute("aria-pressed") == "false"
    pg.reload()
    pg.wait_for_selector(".st.active")
    assert not pg.locator("#timeline").is_visible()


@R("REQ-172", "REQ-173", "REQ-178", "REQ-179", "REQ-180", "REQ-181", "REQ-182")
def test_lanes_grow_live_while_running(open_page):
    pg = open_page("autopilot3")
    show(pg)
    labels = pg.locator("#timeline .tl-label").all_text_contents()
    assert labels[0] == "Inputs"
    assert labels[1:] == pg.locator(".sm h3").all_text_contents()  # one lane per machine, master order
    assert ticks(pg).count() == 0 and dots(pg).count() == 0
    pg.get_by_role("button", name="TOGA").click()                 # items arrive in the state messages
    pg.wait_for_selector("#timeline .tl-tick")
    pg.wait_for_function("document.querySelectorAll('#timeline .tl-dot').length >= 2")   # TOGA = true, then false
    pg.locator("#pause").click()
    frame(pg)
    assert dot_by_name(pg, "TOGA", "true").count() == 1
    assert dot_by_name(pg, "TOGA", "false").count() == 1
    assert dot_by_name(pg, "TOGA", "true").locator("text").text_content() == "TOGA"
    ac = tick_by_title(pg, "Waiting TOGA -> Takeoff")
    assert ac.count() == 1
    assert ac.locator(".tl-tid").text_content() == "T1"           # labelled with the transition id
    assert "Ac accelerating to VR" in ac.locator("title").text_content()
    assert pg.locator("#timeline .tl-bar").count() >= len(labels) - 1   # a bar per lane at least
    assert pg.locator("#timeline .tl-cursor").count() == 1
    assert not pg.locator("#timeline .tl-live").is_visible()      # following the run
    before = ticks(pg).count()
    pg.get_by_role("button", name="AP", exact=True).click()       # more input, more ticks
    pg.locator("#step").click()
    pg.locator("#step").click()
    wait_active(pg, "AP-engaged", 2)
    pg.wait_for_function("n => document.querySelectorAll('#timeline .tl-tick').length > n", arg=before)


@R("REQ-174", "REQ-186", "REQ-187")
def test_reset_clears_lanes_and_chart(open_page):
    pg = open_page("autopilot3")
    show(pg)
    pg.get_by_role("button", name="TOGA").click()
    pg.wait_for_selector("#timeline .tl-tick")
    pg.locator("#pause").click()
    frame(pg)
    tick_by_title(pg, "Waiting TOGA -> Takeoff").click()
    frame(pg)
    assert pg.locator("#timeline .tl-chart").is_visible()
    pg.locator("#reset").click()
    wait_active(pg, "Waiting TOGA")
    wait_count(pg, "#timeline .tl-tick", 0)
    assert dots(pg).count() == 0
    assert not pg.locator("#timeline .tl-chart").is_visible()
    assert pg.locator("#timeline .tl-label").count() == 1 + pg.locator(".sm").count()   # lanes stay, empty
    pg.reload()                                                   # the new run is the only one the server knows
    pg.wait_for_selector(".st.active")
    assert ticks(pg).count() == 0 and dots(pg).count() == 0


@R("REQ-168", "REQ-183", "REQ-184", "REQ-185", "REQ-186", "REQ-189")
def test_autopilot2_guidance_source_chain_in_sequence_chart(open_page):
    pg = open_page("autopilot2")
    show(pg)
    drive_autopilot2_to_ifcc(pg)
    pg.locator("#pause").click()
    frame(pg)
    gs = tick_by_title(pg, "DMC -> IFCC")                          # Guidance source T1
    lat = tick_by_title(pg, "preLocTrk -> LocTrk")                 # Lateral guidance T3
    assert gs.count() == 1 and lat.count() == 1
    vert = tick_by_title(pg, "preGsTrk -> GsTrk")                  # Vertical guidance T3, one pass later
    assert vert.count() == 1
    gs_id, lat_id, vert_id = (x.get_attribute("data-id") for x in (gs, lat, vert))
    assert int(gs_id) < int(lat_id) < int(vert_id)

    gs.click()
    frame(pg)
    chart = pg.locator("#timeline .tl-chart")
    assert chart.is_visible()
    assert "sel" in gs.get_attribute("class").split()
    # The real chain on autopilot2: Guidance source T1 -> Lateral guidance T3, and Vertical guidance T3
    # (GsTrk) one pass later: it was waiting for ifcc_in_control and fired when Vertical entered preGsTrk
    # (gate rule, REQ-189). Phase of flight changes by its own inputs (dmc_tracking_loc/gs).
    rows = chart.locator(".tl-seq-tr")
    assert rows.evaluate_all("rs => rs.map(r => r.dataset.id)") == [gs_id, lat_id, vert_id]
    assert rows.evaluate_all("rs => rs.map(r => r.querySelector('.tl-seq-tid').textContent)") == ["T1", "T3", "T3"]
    lifelines = chart.locator(".tl-life-text").all_text_contents()
    assert lifelines[0] == "Inputs"
    assert sorted(lifelines[1:]) == ["Guidance source", "Lateral guidance", "Vertical guidance"]
    assert chart.locator(".tl-arrow").count() >= 2                 # an arrow per cause
    assert chart.locator(".tl-seq-row.tl-seq-in").count() == 0       # the chain starts at the clicked tick, no input row
    # the cause lines of the selected tick, and the lines of the chained one
    assert pg.locator("#timeline .tl-cause").count() >= 1
    pg.keyboard.press("Escape")
    assert not chart.is_visible()
    frame(pg)
    assert pg.locator("#timeline .tl-tick.sel").count() == 0

    lat.click()                                                    # the lateral tick: its cause is the Guidance source tick
    frame(pg)
    assert chart.is_visible()
    assert chart.locator(".tl-seq-tr").evaluate_all("rs => rs.map(r => r.dataset.id)") == [lat_id]
    chart.locator(".tl-close").click()
    assert not chart.is_visible()


@R("REQ-181", "REQ-184")
def test_clicking_an_input_dot_shows_what_it_caused(open_page):
    pg = open_page("autopilot2")
    show(pg)
    drive_autopilot2_to_ifcc(pg)
    pg.locator("#pause").click()
    frame(pg)
    dot = dot_by_name(pg, "dmc_tracking_gs", "true")
    assert dot.count() == 1
    assert "dmc_tracking_gs = true" in dot.locator("title").text_content()
    click_centre(pg, dot.locator("circle"))
    frame(pg)
    chart = pg.locator("#timeline .tl-chart")
    assert chart.is_visible()
    assert chart.locator(".tl-seq-row.tl-seq-in").count() == 1
    gs_id = tick_by_title(pg, "DMC -> IFCC").get_attribute("data-id")
    ids = chart.locator(".tl-seq-tr").evaluate_all("rs => rs.map(r => r.dataset.id)")
    assert gs_id in ids                                            # the input led to Guidance source T1 (and on to Lateral T3)
    got = sorted(pg.locator(f"#timeline .tl-tick[data-id='{i}'] title").text_content().split(" (")[1] for i in ids)
    assert got == sorted(["No_Vertical_State -> preGsTrk)", "DMC -> IFCC)", "preLocTrk -> LocTrk)",
                          "preGsTrk -> GsTrk)"])
    pg.keyboard.press("Escape")
    assert not chart.is_visible()


@R("REQ-183")
def test_hovering_a_transition_with_causes_draws_cause_lines(open_page):
    pg = open_page("autopilot2")
    show(pg)
    drive_autopilot2_to_ifcc(pg)
    pg.locator("#pause").click()
    frame(pg)
    assert pg.locator("#timeline .tl-cause").count() == 0          # nothing drawn until hovered
    pg.mouse.move(5, 5)
    lat = tick_by_title(pg, "preLocTrk -> LocTrk")                 # caused by Guidance source T1
    lat.hover()
    frame(pg)
    assert "tl-pointing" in pg.locator("#timeline .tl-svg").get_attribute("class")
    lines = pg.locator("#timeline .tl-cause")
    # one line from Guidance source T1; a second one (from Lateral's own entry into preLocTrk) only when
    # the two clicks landed in consecutive passes (gate rule, REQ-189)
    assert lines.count() in (1, 2)
    assert set(lines.evaluate_all("ls => ls.map(l => l.dataset.to)")) == {lat.get_attribute("data-id")}
    assert tick_by_title(pg, "DMC -> IFCC").get_attribute("data-id") in \
        lines.evaluate_all("ls => ls.map(l => l.dataset.from)")
    assert pg.locator("#timeline .tl-tip").text_content().startswith("T3")
    pg.mouse.move(5, 5)
    frame(pg)
    assert pg.locator("#timeline .tl-cause").count() == 0
    assert "Rollout" not in pg.locator("#timeline").inner_text() and "==" not in pg.locator("#timeline").inner_text()   # no equations


@R("REQ-190")
def test_save_as_text_downloads_the_run(open_page):
    pg = open_page("autopilot3")
    save = pg.locator("#timeline-save")
    assert not save.is_visible()                       # only with the pane
    show(pg)
    assert save.is_visible()
    pg.get_by_role("button", name="TOGA").click()
    pg.wait_for_selector("#timeline .tl-tick")
    with pg.expect_download() as info:
        save.click()
    text = open(info.value.path(), encoding="utf-8").read()
    assert info.value.suggested_filename == "statesim-timeline.txt"
    assert "INPUT  TOGA = True" in text
    assert "Aircraft (state_ac)  T1  Waiting TOGA -> Takeoff" in text
    assert "caused by: #1 input TOGA = True" in text
