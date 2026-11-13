"""The Timeline pane in a real browser, fed with the fixture items.

The server does not send timeline data yet (T5), so the items of
tests/fixtures/timeline/autopilot3_items.json are given to the page's
timeline object directly. Skipped if Playwright or Chromium is missing.
Set STATESIM_SHOTS to a directory to keep screenshots.
"""

import json
import os
from pathlib import Path

import pytest

from .conftest import EXAMPLES, ROOT

sync_api = pytest.importorskip("playwright.sync_api")

FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "timeline" / "autopilot3_items.json")
                     .read_text(encoding="utf-8"))
MACHINES = FIXTURE["machines"]
TRS = [i for i in FIXTURE["items"] if i["k"] == "tr"]
INS = [i for i in FIXTURE["items"] if i["k"] == "in"]
SHOTS = os.environ.get("STATESIM_SHOTS")


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
def page(browser, server_url):
    url = server_url(EXAMPLES / "autopilot3" / "master.csv")
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = context.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(url)
    pg.wait_for_selector(".st.active")
    pg.locator("#pause").click()                     # a still page: nothing moves under the pointer
    yield pg
    assert errors == []
    context.close()


def shot(pg, name):
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        pg.screenshot(path=str(Path(SHOTS) / f"{name}.png"))


def frame(pg):
    """Wait until the batched redraw has run."""
    pg.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")


def feed(pg, items=None, t=None):
    items = FIXTURE["items"] if items is None else items
    pg.evaluate("([gen, items, t]) => { timeline.reset(gen, items); timeline.add([], t); }",
                [FIXTURE["gen"], items, items[-1]["t"] + 500 if t is None else t])
    frame(pg)


def show(pg):
    pg.locator("#timeline-toggle").click()
    pg.wait_for_selector("#timeline", state="visible")


def pane_height(pg):
    return pg.locator("#timeline").bounding_box()["height"]


def tick(pg, item):
    return pg.locator(f"#timeline .tl-tick[data-id='{item['id']}']")


def test_hidden_by_default_and_toggle_is_remembered(page):
    pg = page
    toggle = pg.locator("#timeline-toggle")
    assert toggle.text_content() == "Timeline"
    assert toggle.get_attribute("aria-pressed") == "false"
    assert not pg.locator("#timeline").is_visible()
    assert not pg.locator("#timeline-splitter").is_visible()
    layout = pg.locator(".layout").bounding_box()

    show(pg)
    assert toggle.get_attribute("aria-pressed") == "true"
    assert pg.locator("#timeline").get_attribute("aria-label") == "Timeline"
    assert pane_height(pg) == 260
    assert pg.locator("#timeline").bounding_box()["width"] == 1440
    assert pg.locator("#timeline-splitter").is_visible()
    assert pg.evaluate("localStorage.getItem('statesim.timelineShown')") == "1"

    pg.reload()
    pg.wait_for_selector(".st.active")
    assert pg.locator("#timeline").is_visible()                    # remembered
    assert pg.locator("#timeline-toggle").get_attribute("aria-pressed") == "true"

    pg.locator("#timeline-toggle").click()
    assert not pg.locator("#timeline").is_visible()
    assert pg.locator(".layout").bounding_box() == layout          # the page is as before
    pg.reload()
    pg.wait_for_selector(".st.active")
    assert not pg.locator("#timeline").is_visible()


@pytest.mark.req("REQ-177")
def test_splitter_resizes_and_remembers_the_height(page):
    pg = page
    show(pg)
    bar = pg.locator("#timeline-splitter")
    assert bar.get_attribute("role") == "separator"
    assert bar.get_attribute("aria-orientation") == "horizontal"
    bar.focus()
    pg.keyboard.press("ArrowUp")
    assert pane_height(pg) == 280
    pg.keyboard.press("ArrowDown")
    pg.keyboard.press("ArrowDown")
    assert pane_height(pg) == 240

    def drag(to_y):
        box = bar.bounding_box()
        pg.mouse.move(box["x"] + 300, box["y"] + 4)
        pg.mouse.down()
        pg.mouse.move(box["x"] + 300, to_y, steps=4)
        pg.mouse.up()

    drag(bar.bounding_box()["y"] + 4 - 100)
    assert pane_height(pg) == 340
    assert pg.evaluate("localStorage.getItem('statesim.timelineHeight')") == "340"
    drag(2000)                                                      # limits: 120 px to 70% of the window
    assert pane_height(pg) == 120
    drag(-2000)
    assert pane_height(pg) == 630
    pg.reload()
    pg.wait_for_selector(".st.active")
    assert pane_height(pg) == 630


def test_lanes_ticks_and_input_dots(page):
    pg = page
    show(pg)
    feed(pg)
    assert pg.locator("#timeline .tl-label").all_text_contents() == ["Inputs"] + [m["label"] for m in MACHINES]
    assert pg.locator("#timeline .tl-tick").count() == len(TRS)
    assert pg.locator("#timeline .tl-dot").count() == len(INS)
    assert pg.locator("#timeline .tl-bar").count() >= len(MACHINES)
    first = TRS[0]
    assert tick(pg, first).locator("text").text_content() == first["tid"]
    assert tick(pg, first).locator("title").text_content() == \
        f"{first['tid']}: {first['title']} ({first['from']} -> {first['to']})"
    dot = pg.locator(f"#timeline .tl-dot[data-id='{INS[0]['id']}']")
    assert dot.locator("title").text_content() == f"{INS[0]['name']} = true"
    assert "0 s" in pg.locator("#timeline .tl-axis-text").all_text_contents()
    cursor = pg.locator("#timeline .tl-cursor")                     # at the current time
    assert cursor.get_attribute("visibility") is None and float(cursor.get_attribute("x1")) > 140
    assert not pg.locator("#timeline .tl-live").is_visible()        # following the run
    shot(pg, "lanes")

    tick(pg, first).hover()                         # hover: tooltip and cause lines
    frame(pg)
    assert first["title"] in pg.locator("#timeline .tl-tip").text_content()
    assert pg.locator("#timeline .tl-cause").count() == len(first["causes"])
    shot(pg, "hover")


def test_click_opens_sequence_chart_and_escape_closes_it(page):
    pg = page
    show(pg)
    feed(pg)
    first = TRS[0]
    chart = pg.locator("#timeline .tl-chart")
    assert not chart.is_visible()
    tick(pg, first).click()
    frame(pg)
    assert chart.is_visible()
    assert chart.locator(".tl-arrow").count() >= 1
    assert chart.locator(".tl-life-text").first.text_content() == "Inputs"
    assert chart.locator(".tl-seq-tr").first.locator(".tl-seq-tid").text_content() == first["tid"]
    assert "sel" in tick(pg, first).get_attribute("class").split()
    assert pg.locator("#timeline .tl-cause").count() == len(first["causes"])
    shot(pg, "chart")
    pg.keyboard.press("Escape")
    assert not chart.is_visible()
    frame(pg)
    assert pg.locator("#timeline .tl-tick.sel").count() == 0

    dot_id = first["causes"][0]                                     # an input: itself, then what it caused
    box = pg.locator(f"#timeline .tl-dot[data-id='{dot_id}'] circle").bounding_box()
    pg.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)   # dots can overlap
    frame(pg)
    assert chart.is_visible()
    assert chart.locator(".tl-seq-in").count() >= 1
    assert chart.locator(f".tl-seq-tr[data-id='{first['id']}']").count() == 1
    chart.locator(".tl-close").click()
    assert not chart.is_visible()


def test_reset_clears_and_scrolling_back_stops_following(page):
    pg = page
    show(pg)
    feed(pg)
    tick(pg, TRS[0]).click()
    frame(pg)
    assert pg.locator("#timeline .tl-chart").is_visible()
    pg.evaluate("gen => timeline.state({gen: gen, t: 0, tl: []})", FIXTURE["gen"] + 1)   # as after Reset
    frame(pg)
    assert pg.locator("#timeline .tl-tick").count() == 0
    assert pg.locator("#timeline .tl-dot").count() == 0
    assert not pg.locator("#timeline .tl-chart").is_visible()
    assert pg.locator("#timeline .tl-label").count() == 1 + len(MACHINES)

    feed(pg, t=60000)                                               # a minute in: the items are out of view
    assert pg.locator("#timeline .tl-tick").count() == 0
    box = pg.locator("#timeline .tl-svg").bounding_box()
    pg.mouse.move(box["x"] + 600, box["y"] + 100)
    pg.mouse.wheel(0, -100000)                                      # scroll back to the start
    frame(pg)
    assert pg.locator("#timeline .tl-tick").count() > 0
    live = pg.locator("#timeline .tl-live")
    assert live.is_visible()
    shot(pg, "scrolled_back")
    live.click()
    frame(pg)
    assert not live.is_visible()
    assert pg.locator("#timeline .tl-tick").count() == 0


def test_many_items_stay_bounded(page):
    pg = page
    show(pg)
    m = MACHINES[1]
    a, b = m["states"][:2]
    items = [{"k": "tr", "id": i + 1, "t": i * 1.0, "tick": i, "sm": m["name"], "tid": f"T{i % 2 + 1}",
              "title": "", "from": (a, b)[i % 2], "to": (b, a)[i % 2], "causes": [i] if i else [],
              "writes": []} for i in range(20000)]
    feed(pg, items=items, t=20000)
    assert pg.evaluate("timeline.count") == 20000
    assert pg.locator("#timeline .tl-svg *").count() < 3000          # only what can be told apart is drawn
    shot(pg, "dense")
