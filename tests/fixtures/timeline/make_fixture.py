"""Writes autopilot3_items.json: a scripted autoland on examples/autopilot3,
as the front end receives it ({"machines", "gen", "items"}).

Run from the repository root: python tests/fixtures/timeline/make_fixture.py

Until the Timeline recorder exists (T3, #15) the items are built from the
text trace with naive causes (the latest earlier item whose name the
transition's values mention). T3 switches this script to the real recorder.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from statesim import ListTraceSink, load_model  # noqa: E402
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


TR = re.compile(r'^(\S+) (.+)->(.+) "(.*)"$')
SET = re.compile(r"^set (\S+) (.+)->(.+)$")
WRITE = re.compile(r"^(\S+): set (\S+) (.+)->(.+)$")


def naive_items(events, sm_names) -> list[dict]:
    items: list[dict] = []
    last: dict[str, int] = {}          # name -> id of the item that last produced it
    for e in events:
        t = float(e.t)
        if e.component == "INPUT":
            m = SET.match(e.action)
            old, new = ast.literal_eval(m[2]), ast.literal_eval(m[3])
            if old == new and type(old) is type(new):
                continue
            items.append({"k": "in", "id": len(items) + 1, "t": t, "tick": e.tick,
                          "name": m[1], "value": new})
            last[m[1]] = len(items)
        elif e.component in sm_names:
            w = WRITE.match(e.action)
            if w:
                if items and items[-1]["k"] == "tr" and items[-1]["sm"] == e.component \
                        and items[-1]["tick"] == e.tick:
                    items[-1]["writes"].append([w[2], ast.literal_eval(w[4])])
                continue
            m = TR.match(e.action)
            if not m:
                continue                # a row result
            names = {n for n, _ in e.values}
            causes = sorted({last[n] for n in names if n in last and n != e.component})
            items.append({"k": "tr", "id": len(items) + 1, "t": t, "tick": e.tick,
                          "sm": e.component, "tid": m[1], "title": m[4],
                          "from": m[2], "to": m[3], "causes": causes[-2:], "writes": []})
            last[e.component] = len(items)
    return items


def main() -> None:
    model = load_model(ROOT / "examples" / "autopilot3" / "master.csv")
    sink = ListTraceSink()
    s = Session(model, sink)
    scenario(s)
    sm_names = {sm.name for sm in model.state_machines}
    items = naive_items(sink.events, sm_names)
    doc = {"machines": describe_model(model)["machines"], "gen": 1, "items": items}
    OUT.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{OUT.name}: {len(items)} items")


if __name__ == "__main__":
    main()
