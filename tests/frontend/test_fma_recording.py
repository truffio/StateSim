"""FMA recording (recording.js, recorder.html): Start/Stop, rows, editable
preview and Save PNG, against the real server on examples/autopilot3."""

import pytest

from .test_browser import browser, open_page  # noqa: F401  (fixtures)

R = pytest.mark.req


def send(pg, msg, wait=900):
    pg.evaluate("m => send(m)", msg)
    pg.wait_for_timeout(wait)


def record(pg, steps):
    """Reset, Start, run the steps, Stop; returns the report window."""
    pg.locator("#reset").click()
    pg.wait_for_timeout(400)
    pg.locator("#rec-start").click()
    assert pg.locator("#rec-stop").is_visible() and not pg.locator("#rec-start").is_visible()
    for m in steps:
        send(pg, m)
    with pg.context.expect_page() as info:
        pg.locator("#rec-stop").click()
    w = info.value
    w.wait_for_selector(".rc-rec")
    return w


TAKEOFF = [
    {"type": "press", "name": "TOGA"},
    {"type": "set", "name": "ground_speed", "value": 130},
    {"type": "set", "name": "radio_altitude", "value": 100},
    {"type": "set", "name": "radio_altitude", "value": 150},     # changes nothing on the FMA
    {"type": "press", "name": "AP_btn"},
]


@R("REQ-192")
def test_buttons_only_with_an_fma_panel(open_page):
    pg = open_page("autopilot3")
    assert pg.locator("#rec-start").is_visible() and not pg.locator("#rec-stop").is_visible()
    pg2 = open_page("autopilot2")                    # its FCP lights are inputs: no FMA panel
    assert not pg2.locator("#rec-start").is_visible() and not pg2.locator("#rec-stop").is_visible()


@R("REQ-193", "REQ-194", "REQ-195", "REQ-196")
def test_rows_are_the_inputs_that_changed_the_fma(open_page):
    pg = open_page("autopilot3")
    w = record(pg, TAKEOFF)
    labels = w.locator(".rc-label").all_text_contents()
    assert labels == ["Start of the manoeuvre", "TOGA button pressed", "Ground speed set to 130 kt",
                      "Radio altitude set to 100 ft", "Autopilot button pressed"]
    recs = w.locator(".rc-rec")
    assert recs.nth(0).locator(".fma").count() == 0           # the blank start FMA is not drawn
    assert recs.nth(1).locator(".fma .m.lit").count() > 0     # the real FMA panel, lit
    assert "TO" in recs.nth(1).locator(".fma .m.lit").all_text_contents()
    lefts = [recs.nth(k).evaluate("e => e.getBoundingClientRect().left") for k in range(5)]
    assert lefts == sorted(lefts) and lefts[4] > lefts[0]     # the compact staircase
    assert "compact layout" in w.locator(".rc-meta").text_content()
    w.close()


@R("REQ-197", "REQ-198")
def test_preview_edits_and_save_png(open_page):
    pg = open_page("autopilot3")
    w = record(pg, TAKEOFF)
    w.locator(".rc-title").click()
    w.keyboard.press("Control+A")
    w.keyboard.type("Takeoff check")
    w.locator(".rc-label").nth(4).click()
    w.keyboard.press("Control+A")
    w.keyboard.type("Crew engages the autopilot")
    with w.expect_download() as d:
        w.locator("#save").click()
    full = w.evaluate("window.lastPng")
    assert d.value.suggested_filename.startswith("Takeoff check - ") and d.value.suggested_filename.endswith(".png")
    assert full["width"] > 1000 and full["size"] > 10000
    # hide a row and drag the last one up: the image gets shorter, the order follows
    rec = w.locator(".rc-rec").nth(2)
    rec.hover()
    rec.locator("button", has_text="Hide").click()
    assert w.locator(".rc-rec.rc-hidden").count() == 1
    w.locator(".rc-rec").nth(4).locator(".rc-grip").drag_to(w.locator(".rc-rec").nth(1), target_position={"x": 5, "y": 2})
    assert w.locator(".rc-label").all_text_contents()[1] == "Crew engages the autopilot"
    with w.expect_download():
        w.locator("#save").click()
    assert w.evaluate("window.lastPng")["height"] < full["height"]
    # undo and reset to the recording
    w.locator("#undo").click()
    assert w.locator(".rc-label").all_text_contents()[1] == "TOGA button pressed"
    w.locator("#reset").click()
    assert w.locator(".rc-rec.rc-hidden").count() == 0
    assert w.locator(".rc-label").all_text_contents()[4] == "Autopilot button pressed"
    w.close()


@R("REQ-199")
def test_no_fma_change_gives_a_note(open_page):
    pg = open_page("autopilot3")
    w = record(pg, [{"type": "set", "name": "radio_altitude", "value": 50}])
    assert w.locator(".rc-rec").count() == 1
    assert "no FMA change during the recording" in w.locator(".rc-meta").text_content()
    w.close()


@R("REQ-195")
def test_cause_is_followed_back_to_the_input(open_page):
    """A change caused by an earlier input (through a transition) is labelled
    with that input, not with the input that happened to come before it."""
    pg = open_page("autopilot3")
    rows = pg.evaluate("""() => StateSimRecorder.buildRows({t: 0, lit: []}, [
        {k: "in", id: 1, t: 100, name: "TOGA", value: true},
        {k: "in", id: 2, t: 150, name: "TOGA", value: false},
        {k: "in", id: 3, t: 200, name: "radio_altitude", value: 50},
        {k: "tr", id: 4, t: 300, sm: "state_ac", causes: [1]},
        {k: "dp", id: 5, t: 300, name: "fma_a", value: true, causes: [4]},
      ], ["fma_a"], {TOGA: {widget: "momentary", description: "TOGA button"},
                     radio_altitude: {type: "int", description: "Radio altitude", unit: "ft"}})""")
    assert [r["label"] for r in rows] == ["Start of the manoeuvre", "TOGA button pressed"]
    assert rows[1]["lit"] == ["fma_a"]
