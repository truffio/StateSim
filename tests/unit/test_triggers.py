"""Structured trace fields and triggers (timeline T2, docs/future_timeline.md 1)."""

from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path

from statesim import Engine, ListTraceSink, constants, load_model

REPO = Path(__file__).resolve().parents[2]

SM_HEADER = ["transition_id", "current_state", "next_state", "default_state", "equation",
             "result_variable", "rationale", "title", "order", "action_type", "action"]


def _write(path: Path, header, rows) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def R(tid, cur, nxt, eq, rv, *, default="", order=1, kind="", action="", title=""):
    return [tid, cur, nxt, default, eq, rv, "", title, order, kind, action]


def build(tmp_path, sms, inputs=(), actions=None, equations=None, bands=None, init=None):
    """sms: {name: rows}; bands: {sm: hz} (default 10); equations:
    [(result, equation, band, order)]; init: {sm: action}."""
    bands = bands or {}
    init = init or {}
    master = []
    order = 10
    for name, rows in sms.items():
        _write(tmp_path / f"{name}.csv", SM_HEADER, rows)
        master.append([f"{name}.csv", "state_machine", order, bands.get(name, 10),
                       init.get(name, "")])
        order += 10
    if actions is not None:
        _write(tmp_path / "actions.csv", ["action", "statement", "rationale"],
               [[a, s, ""] for a, s in actions])
        master.append(["actions.csv", "actions", "", "", ""])
    if inputs:
        _write(tmp_path / "inputs.csv", ["variable_name", "type", "default_value", "widget"],
               [list(r) + [""] * (4 - len(r)) for r in inputs])
        master.append(["inputs.csv", "inputs", "", "", ""])
    if equations is not None:
        _write(tmp_path / "equations.csv",
               ["equation", "explanation", "rationale", "result_variable", "band", "order"],
               [[eq, "", "", rv, band, o] for rv, eq, band, o in equations])
        master.append(["equations.csv", "equations", "", "", ""])
    _write(tmp_path / "master.csv", ["file_name", "type", "order", "band", "init_action"],
           master)
    return tmp_path / "master.csv"


def engine(tmp_path, **kw):
    sink = ListTraceSink()
    return Engine(load_model(build(tmp_path, **kw)), sink), sink


def of(sink, kind, tick=None):
    return [e for e in sink.events if e.kind == kind and (tick is None or e.tick == tick)]


INPUTS = [("alt", "int", "0"), ("ap", "bool", "False"), ("go", "bool", "False"),
          ("n", "int", "0", "none")]


def test_single_band(tmp_path):
    sms = {"S": [R("1", "Ground", "Air", "S == 'Ground' and alt > 400", "r1",
                   default="Ground", title="Lift off"),
                 R("2", "Air", "Ground", "alt == 0", "r2", order=2)]}
    eng, sink = engine(tmp_path, sms=sms, inputs=INPUTS)
    eng.step()  # settles r2 False->True (alt == 0)
    r2 = [e for e in of(sink, "result", 1) if e.name == "r2"][0]
    assert r2.trigger == ()  # alt unchanged since the initial context
    sink.events.clear()
    eng.set_input("alt", 500)
    eng.step()
    inp, = of(sink, "input")
    assert (inp.name, inp.old, inp.new, inp.trigger, inp.label, inp.phase) == \
        ("alt", 0, 500, (), "", "")
    results = {e.name: e for e in of(sink, "result")}
    assert (results["r1"].old, results["r1"].new, results["r1"].trigger) == \
        (False, True, ("alt",))  # S read but excluded (own name)
    assert results["r2"].trigger == ("alt",)
    tr, = of(sink, "transition")
    assert (tr.component, tr.name, tr.old, tr.new, tr.label, tr.title, tr.trigger) == \
        ("S", "S", "Ground", "Air", "T1", "Lift off", ("alt",))
    assert 'T1 Ground->Air "Lift off"' in sink.lines()[-1]


def _two_band(tmp_path):
    # F at 10 Hz sets the tick rate; S at 2 Hz runs on ticks 1, 6, 11, ...
    sms = {"F": [R("1", "A", "B", "go", "f1", default="A")],
           "S": [R("1", "Off", "On", "ap", "s1", default="Off", order=1),
                 R("1", "Off", "On", "alt >= 0", "s2", order=2)]}
    eng, sink = engine(tmp_path, sms=sms, inputs=INPUTS, bands={"S": 2})
    eng.step()  # tick 1: s2 False->True
    return eng, sink


def test_two_bands_change_between_passes(tmp_path):
    eng, sink = _two_band(tmp_path)
    eng.step()
    eng.set_input("alt", 7)
    eng.step()
    eng.set_input("ap", True)
    eng.run(3)  # ticks 4..6; S runs on tick 6
    tr, = of(sink, "transition")
    assert tr.tick == 6 and tr.trigger == ("alt", "ap")
    s1, = [e for e in of(sink, "result", 6) if e.name == "s1"]
    assert s1.trigger == ("ap",)


def test_two_bands_change_reverted_between_passes(tmp_path):
    eng, sink = _two_band(tmp_path)
    eng.set_input("alt", 7)
    eng.step()
    eng.set_input("alt", 0)
    eng.set_input("ap", True)
    eng.run(4)  # S runs on tick 6
    tr, = of(sink, "transition")
    assert tr.tick == 6 and tr.trigger == ("ap",)


def test_timer_has_no_trigger(tmp_path):
    sms = {"S": [R("1", "Wait", "Done", "t >= 200 and tick > 0 and dt > 0", "r1",
                   default="Wait")]}
    eng, sink = engine(tmp_path, sms=sms, inputs=INPUTS)
    eng.run(4)
    tr, = of(sink, "transition")
    assert tr.tick == 3 and tr.trigger == ()
    assert of(sink, "result")[0].trigger == ()


def test_chain_through_equation(tmp_path):
    sms = {"S": [R("1", "Low", "High", "high", "r1", default="Low")]}
    eng, sink = engine(tmp_path, sms=sms, inputs=INPUTS,
                       equations=[("high", "alt > 400", 10, 1)])
    eng.step()
    eng.set_input("alt", 500)
    eng.step()
    eq = [e for e in of(sink, "result") if e.name == "high"][0]
    assert (eq.component, eq.old, eq.new, eq.trigger) == (constants.EQUATIONS_COMPONENT, False, True, ("alt",))
    tr, = of(sink, "transition")
    assert tr.trigger == ("high",)


def test_set_before_first_step(tmp_path):
    sms = {"S": [R("1", "Low", "High", "alt > 400", "r1", default="Low")]}
    eng, sink = engine(tmp_path, sms=sms, inputs=INPUTS,
                       equations=[("e", "alt + 1", 10, 1)])
    eng.set_input("alt", 500)
    eng.step()
    assert [e for e in of(sink, "result") if e.name == "e"][0].trigger == ("alt",)
    assert of(sink, "transition")[0].trigger == ("alt",)


def test_own_entry_write_is_not_a_trigger(tmp_path):
    sms = {"S": [R("1", "Ground", "Air", "alt > 400", "r1", default="Ground",
                   kind="entry", action="SET_N"),
                 R("2", "Air", "Ground", "n == 5 and go", "r2", order=2)]}
    eng, sink = engine(tmp_path, sms=sms, inputs=INPUTS, actions=[("SET_N", "n = 5")])
    eng.set_input("alt", 500)
    eng.step()
    eng.set_input("go", True)
    eng.step()
    r2, = [e for e in of(sink, "result", 2) if e.name == "r2"]
    assert r2.trigger == ("go",)
    tr, = of(sink, "transition", 2)
    assert tr.trigger == ("go",)


def test_action_phases(tmp_path):
    sms = {"S": [R("1", "Ground", "Air", "alt > 400", "r1", default="Ground",
                   kind="entry", action="EN"),
                 R("1", "Ground", "Air", "True", "r1b", order=2, kind="exit", action="EX"),
                 R("2", "Air", "Ground", "alt == 0", "r2", order=3, kind="during",
                   action="DU")]}
    eng, sink = engine(tmp_path, sms=sms, inputs=INPUTS, init={"S": "IN"},
                       actions=[("IN", "n = 1"), ("EX", "n = 2"), ("EN", "n = 3"),
                                ("DU", "n += 10")])
    eng.set_input("alt", 500)
    eng.run(2)
    acts = [(e.label, e.phase, e.name, e.old, e.new, e.trigger, e.title)
            for e in of(sink, "action")]
    assert acts == [("IN", "init", "n", 0, 1, (), ""),
                    ("EX", "exit", "n", 1, 2, (), ""),
                    ("EN", "entry", "n", 2, 3, (), ""),
                    ("DU", "during", "n", 3, 13, (), "")]
    # init before the rows; exit before the transition event, entry after it
    order = [e.phase or e.kind for e in sink.events if e.tick == 1]
    assert order == ["init", "result", "result", "exit", "transition", "entry"]


def _fields(events):
    return [(e.tick, e.component, e.action, e.values, e.kind, e.name, e.old, e.new,
             e.trigger, e.label, e.title, e.phase) for e in events]


def test_deterministic_in_process(tmp_path):
    def run(d):
        d.mkdir()
        sms = {"S": [R("1", "Off", "On", "ap and alt > 0 and go", "r1", default="Off")]}
        eng, sink = engine(d, sms=sms, inputs=INPUTS)
        for name, value in (("go", True), ("alt", 3), ("ap", True)):
            eng.set_input(name, value)
            eng.step()
        return _fields(sink.events)
    a, b = run(tmp_path / "a"), run(tmp_path / "b")
    assert a == b
    assert a[-1][4] == "transition" and a[-1][8] == ("ap",)  # go, alt seen earlier


_CHILD = """
import json, sys
from pathlib import Path
from statesim import Engine, ListTraceSink, load_model
master = Path(sys.argv[1])
steps = json.loads((master.parent / "expected.json").read_text(encoding="utf-8"))["steps"]
sink = ListTraceSink()
eng = Engine(load_model(master), sink)
for step in steps:
    for k, v in step.get("set_inputs", {}).items():
        eng.set_input(k, v)
    eng.step()
for e in sink.events:
    print(repr((e.kind, e.name, e.old, e.new, e.trigger, e.label, e.title, e.phase)))
"""


def test_hash_seed_independent():
    master = REPO / "tests" / "fixtures" / "ap_engage" / "master.csv"
    outs = set()
    for seed in (0, 1, 12345):
        env = dict(os.environ, PYTHONHASHSEED=str(seed), PYTHONPATH=str(REPO / "src"))
        out = subprocess.run([sys.executable, "-c", _CHILD, str(master)], env=env,
                             capture_output=True, text=True, check=True, cwd=REPO).stdout
        outs.add(out)
    out = outs.pop()
    assert not outs and "'transition'" in out and "'input'" in out


def test_headless_matches_traced(tmp_path):
    sms = {"S": [R("1", "Ground", "Air", "alt > 400", "r1", default="Ground")]}
    model = load_model(build(tmp_path, sms=sms, inputs=INPUTS))
    a, b = Engine(model), Engine(model, ListTraceSink())
    for e in (a, b):
        e.set_input("alt", 500)
        e.run(3)
    assert a.snapshot() == b.snapshot()
