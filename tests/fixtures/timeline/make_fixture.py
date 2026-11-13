"""Writes autopilot3_items.json: a scripted autoland on examples/autopilot3,
as the front end receives it ({"machines", "gen", "items"}).

Run from the repository root: python tests/fixtures/timeline/make_fixture.py

The items come from the real recorder (statesim.Timeline) attached to the
session, so the fixture shows the true cause links.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from statesim import Timeline, load_model  # noqa: E402
from statesim_server.session import Session, describe_model  # noqa: E402

OUT = Path(__file__).with_name("autopilot3_items.json")


def scenario(s: Session) -> None:
    def run(n=3):
        for _ in range(n):
            s.step()

    def press(name):
        s.handle({"type": "press", "name": name}); run()

    def setv(name, v):
        assert s.handle({"type": "set", "name": name, "value": v}) is None
        run()

    run(2)
    press("TOGA")
    setv("ground_speed", 130); setv("radio_altitude", 100)
    press("AP_btn")
    setv("radio_altitude", 2500); setv("radio_altitude", 2000)
    press("APPR_btn")
    setv("radio_altitude", 1400)
    setv("dmc_tracking_loc", True); setv("dmc_tracking_gs", True)
    setv("dmc_tracking_loc", True); setv("dmc_tracking_gs", True)
    setv("radio_altitude", 700); setv("radio_altitude", 150); setv("radio_altitude", 40)
    setv("claws_req_flare", True); setv("radio_altitude", 0)
    setv("ground_time_gt_2s", True)
    setv("ground_speed", 100); setv("ground_speed", 20); setv("ground_speed", 0)
    run(20)


def main() -> None:
    model = load_model(ROOT / "examples" / "autopilot3" / "master.csv")
    timeline = Timeline()
    s = Session(model, timeline)
    scenario(s)
    items = timeline.all()
    doc = {"machines": describe_model(model)["machines"], "gen": timeline.gen, "items": items}
    OUT.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{OUT.name}: {len(items)} items")


if __name__ == "__main__":
    main()
