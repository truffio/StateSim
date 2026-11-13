"""Unit tests for statesim.timeline (T3, #15): items and cause folding.

Built from hand-made TraceEvents, in the shape the engine emits them
(docs/timeline_plan.md, Contracts). One end-to-end test at the bottom runs
the real engine and is skipped until the engine fills ``TraceEvent.kind``.
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import pytest

from statesim import Engine, ListTraceSink, Timeline, load_model
from statesim.trace import TraceEvent

ROOT = Path(__file__).resolve().parents[2]
ACTIONS = ROOT / "examples" / "actions" / "master.csv"


def _t(tick: int) -> Fraction:
    return Fraction(tick - 1) * 100


def inp(tick, name, old, new):
    return TraceEvent(tick, _t(tick), "INPUT", f"set {name} {old!r}->{new!r}",
                      ((name, new),), kind="input", name=name, old=old, new=new)


def res(tick, comp, name, old, new, trigger=()):
    return TraceEvent(tick, _t(tick), comp, f"{name} {old}->{new}", (),
                      kind="result", name=name, old=old, new=new, trigger=tuple(trigger))


def tr(tick, sm, label, old, new, trigger=(), title=""):
    return TraceEvent(tick, _t(tick), sm, f'{label} {old}->{new} "{title}"', (),
                      kind="transition", name=sm, old=old, new=new,
                      trigger=tuple(trigger), label=label, title=title)


def act(tick, sm, phase, name, old, new, label="ACT"):
    return TraceEvent(tick, _t(tick), sm, f"{label}: set {name} {old!r}->{new!r}", (),
                      kind="action", name=name, old=old, new=new, label=label, phase=phase)


def feed(tl: Timeline, *events: TraceEvent) -> Timeline:
    for e in events:
        tl.emit(e)
    return tl


# --- inputs -------------------------------------------------------------------


def test_empty_timeline() -> None:
    tl = Timeline()
    assert (tl.gen, tl.last_id, tl.all(), tl.items_since(0)) == (1, 0, [], [])
    assert Timeline(gen=7).gen == 7


def test_input_item_shape() -> None:
    tl = feed(Timeline(), inp(3, "alt", 0, 1000))
    assert tl.all() == [
        {"k": "in", "id": 1, "t": 200.0, "tick": 3, "name": "alt", "value": 1000}
    ]
    assert isinstance(tl.all()[0]["t"], float)
    assert tl.last_id == 1


def test_unchanged_input_is_skipped() -> None:
    tl = feed(Timeline(), inp(1, "sw", False, False), inp(1, "alt", 5, 5))
    assert tl.all() == [] and tl.last_id == 0


def test_unchanged_input_keeps_previous_origin() -> None:
    tl = feed(Timeline(),
              inp(1, "sw", False, True),
              inp(2, "sw", True, True),
              tr(3, "M", "T1", "A", "B", ["sw"]))
    assert [i["id"] for i in tl.all()] == [1, 2]
    assert tl.all()[1]["causes"] == [1]


def test_input_same_value_other_type_is_a_change() -> None:
    tl = feed(Timeline(), inp(1, "x", 1, True), inp(1, "y", 1, 1.0))
    assert [(i["name"], i["value"]) for i in tl.all()] == [("x", True), ("y", 1.0)]


# --- transitions and causes ---------------------------------------------------


def test_transition_item_shape_and_cause_from_input() -> None:
    tl = feed(Timeline(),
              inp(1, "sw", False, True),
              tr(2, "AP", "T2", "OFF", "ON", ["sw"], title="Engage"))
    assert tl.all()[1] == {
        "k": "tr", "id": 2, "t": 100.0, "tick": 2, "sm": "AP", "tid": "T2",
        "title": "Engage", "from": "OFF", "to": "ON", "causes": [1], "writes": [],
    }
    assert tl.last_id == 2


def test_cause_folds_through_equation_result() -> None:
    tl = feed(Timeline(),
              inp(1, "alt", 0, 1000),
              res(2, "EQ", "high", False, True, ["alt"]),
              res(2, "M", "m_t1", False, True, ["high"]),
              tr(2, "M", "T1", "A", "B", ["high"]))
    items = tl.all()
    assert [i["k"] for i in items] == ["in", "tr"]  # results give no item
    assert items[1]["causes"] == [1]


def test_cause_folds_through_two_equations_and_merges_inputs() -> None:
    tl = feed(Timeline(),
              inp(1, "a", 0, 1),
              inp(1, "b", 0, 1),
              res(2, "EQ", "x", 0, 1, ["a"]),
              res(2, "EQ", "y", 0, 2, ["b", "x"]),
              tr(2, "M", "T1", "A", "B", ["y"]))
    assert tl.all()[-1]["causes"] == [1, 2]


def test_chain_of_two_machines() -> None:
    tl = feed(Timeline(),
              inp(1, "sw", False, True),
              tr(2, "A", "T1", "A0", "A1", ["sw"]),
              tr(2, "B", "T1", "B0", "B1", ["A"]),
              tr(3, "C", "G1", "C0", "C1", ["B"]))
    a, b, c = tl.all()[1:]
    assert (a["id"], a["causes"]) == (2, [1])
    assert (b["id"], b["causes"]) == (3, [2])
    assert (c["id"], c["causes"], c["tid"]) == (4, [3], "G1")


def test_timer_transition_has_no_causes() -> None:
    tl = feed(Timeline(),
              inp(1, "sw", False, True),
              tr(50, "M", "T3", "A", "B", []))
    assert tl.all()[1]["causes"] == []


def test_unknown_trigger_name_gives_no_cause() -> None:
    tl = feed(Timeline(), tr(1, "M", "T1", "A", "B", ["never_written"]))
    assert tl.all()[0]["causes"] == []


def test_result_with_empty_trigger_clears_origins() -> None:
    tl = feed(Timeline(),
              inp(1, "alt", 0, 1000),
              res(2, "EQ", "high", False, True, ["alt"]),
              res(5, "EQ", "high", True, False, []),  # e.g. a time-based change
              tr(5, "M", "T1", "A", "B", ["high"]))
    assert tl.all()[1]["causes"] == []


def test_causes_are_sorted_and_deterministic() -> None:
    def build(order):
        tl = Timeline()
        feed(tl, *(inp(1, n, 0, 1) for n in ("d", "a", "c", "b", "e")))
        return feed(tl, tr(2, "M", "T1", "A", "B", order)).all()

    first = build(["a", "b", "c", "d", "e"])
    assert first[-1]["causes"] == [1, 2, 3, 4, 5]
    assert build(["e", "c", "a", "d", "b"]) == first
    assert json.dumps(build(["a", "b", "c", "d", "e"])) == json.dumps(first)


# --- action writes ------------------------------------------------------------


def test_exit_writes_held_then_entry_writes_appended() -> None:
    tl = feed(Timeline(),
              inp(1, "alt", 500, 0),
              res(2, "M", "m_t4", False, True, ["alt"]),
              act(2, "M", "exit", "speed", 0, 60, "LANDING"),
              act(2, "M", "exit", "flaps", 1, 0, "LANDING"))
    assert len(tl.all()) == 1  # exit writes alone give no item
    feed(tl, tr(2, "M", "T4", "Cruise", "Ground", ["alt"]))
    item = tl.all()[1]
    assert item["writes"] == [["speed", 60], ["flaps", 0]]
    feed(tl, act(2, "M", "entry", "brake", False, True, "ROLLOUT"))
    assert item["writes"] == [["speed", 60], ["flaps", 0], ["brake", True]]
    assert item is tl.all()[1] and tl.last_id == 2


def test_written_vars_take_the_transition_as_origin() -> None:
    tl = feed(Timeline(),
              inp(1, "alt", 500, 0),
              inp(1, "speed", 10, 0),                       # origin of speed: id 2
              act(2, "M", "exit", "speed", 0, 60),
              tr(2, "M", "T4", "Cruise", "Ground", ["alt"]),  # id 3
              act(2, "M", "entry", "brake", False, True),
              tr(3, "X", "T1", "X0", "X1", ["speed"]),
              tr(3, "Y", "T1", "Y0", "Y1", ["brake"]))
    x, y = tl.all()[-2:]
    assert x["causes"] == [3]
    assert y["causes"] == [3]


def test_exit_writes_are_per_machine() -> None:
    tl = feed(Timeline(),
              act(2, "A", "exit", "va", 0, 1),
              act(2, "B", "exit", "vb", 0, 1),
              tr(2, "B", "T1", "B0", "B1"),
              tr(2, "A", "T1", "A0", "A1"))
    b, a = tl.all()
    assert b["writes"] == [["vb", 1]]
    assert a["writes"] == [["va", 1]]


def test_stale_exit_writes_are_discarded() -> None:
    tl = feed(Timeline(),
              act(2, "M", "exit", "old", 0, 1),   # no transition followed in tick 2
              tr(3, "M", "T1", "A", "B"))
    assert tl.all()[0]["writes"] == []
    tl = feed(Timeline(),
              act(2, "M", "exit", "old", 0, 1),
              act(3, "M", "exit", "new", 0, 1),
              tr(3, "M", "T1", "A", "B"))
    assert tl.all()[0]["writes"] == [["new", 1]]


def test_held_exits_are_cleared_after_the_transition() -> None:
    tl = feed(Timeline(),
              act(2, "M", "exit", "v", 0, 1),
              tr(2, "M", "T1", "A", "B"),
              tr(2, "M", "T2", "B", "C"))
    assert [i["writes"] for i in tl.all()] == [[["v", 1]], []]


def test_entry_write_only_joins_a_transition_of_the_same_tick() -> None:
    tl = feed(Timeline(),
              tr(2, "M", "T1", "A", "B"),
              act(3, "M", "entry", "late", 0, 1),
              tr(4, "X", "T1", "X0", "X1", ["late"]))
    m, x = tl.all()
    assert m["writes"] == []
    assert x["causes"] == [1]  # origin still the machine's last transition


def test_during_and_init_writes_take_last_transition_as_origin() -> None:
    tl = feed(Timeline(),
              act(1, "M", "init", "speed", 5, 0, "START"),
              act(1, "M", "during", "count", 0, 1, "TIMER"),
              tr(2, "X", "T1", "X0", "X1", ["speed", "count"]))
    assert tl.all() == [tl.all()[0]] and tl.all()[0]["causes"] == []  # no transition yet

    tl = feed(Timeline(),
              inp(1, "sw", False, True),
              tr(2, "M", "T1", "Ground", "Climb", ["sw"]),          # id 2
              act(3, "M", "during", "count", 0, 1, "TIMER"),
              act(4, "M", "during", "count", 1, 2, "TIMER"),
              res(4, "M", "m_t3", False, True, ["count"]),
              tr(4, "M", "T3", "Climb", "Cruise", ["count"]),       # id 3
              act(5, "N", "init", "other", 1, 0, "START"),
              tr(6, "X", "T1", "X0", "X1", ["other"]))
    items = tl.all()
    assert [i["k"] for i in items] == ["in", "tr", "tr", "tr"]  # no item for the writes
    assert items[1]["writes"] == [] and items[2]["writes"] == []
    assert items[2]["causes"] == [2]
    assert items[3]["causes"] == []  # machine N never changed state


def test_during_write_replaces_an_input_origin() -> None:
    tl = feed(Timeline(),
              inp(1, "count", 0, 9),
              act(2, "M", "during", "count", 9, 10),
              tr(3, "X", "T1", "X0", "X1", ["count"]))
    assert tl.all()[1]["causes"] == []


# --- old-style events, values, cap ---------------------------------------------


def test_old_style_events_are_ignored() -> None:
    tl = feed(Timeline(),
              TraceEvent(1, Fraction(0), "INPUT", "set sw False->True", (("sw", True),)),
              TraceEvent(2, Fraction(100), "AP", 'T1 OFF->ON ""', (("sw", True),)))
    assert tl.all() == [] and tl.last_id == 0


def test_values_are_json_serialisable() -> None:
    tl = feed(Timeline(),
              inp(1, "f", Fraction(0), Fraction(1, 4)),
              inp(1, "tup", (), (1, 2)),
              inp(1, "none", 1, None),
              inp(1, "b", False, True),
              inp(1, "x", 0.0, 2.5),
              act(2, "M", "exit", "frac", 0, Fraction(3, 2)),
              tr(2, "M", "T1", "A", "B", ["f", "tup"]),
              act(2, "M", "entry", "obj", 0, {1, }))
    items = tl.all()
    assert [i["value"] for i in items[:5]] == [0.25, "(1, 2)", None, True, 2.5]
    assert items[3]["value"] is True
    assert items[5]["writes"] == [["frac", 1.5], ["obj", "{1}"]]
    assert json.loads(json.dumps(items)) == items
    assert json.loads(json.dumps(tl.items_since(3))) == items[3:]


def test_cap_drops_oldest_and_ids_keep_counting() -> None:
    tl = Timeline(cap=3)
    assert tl.cap == 3
    for n in range(1, 6):
        tl.emit(inp(n, "v", n - 1, n))
    assert [i["id"] for i in tl.all()] == [3, 4, 5]
    assert tl.last_id == 5
    assert [i["id"] for i in tl.items_since(0)] == [3, 4, 5]
    assert [i["id"] for i in tl.items_since(3)] == [4, 5]
    assert [i["id"] for i in tl.items_since(4)] == [5]
    assert tl.items_since(5) == [] and tl.items_since(99) == []
    feed(tl, tr(6, "M", "T1", "A", "B", ["v"]))
    assert tl.all()[-1]["id"] == 6 and tl.all()[-1]["causes"] == [5]


def test_causes_may_reference_dropped_ids() -> None:
    tl = feed(Timeline(cap=1), inp(1, "sw", False, True), tr(2, "M", "T1", "A", "B", ["sw"]))
    assert tl.all() == tl.items_since(0) == tl.items_since(1)
    assert tl.all()[0]["id"] == 2 and tl.all()[0]["causes"] == [1]


def test_entry_write_reaches_a_transition_even_when_cap_is_small() -> None:
    tl = feed(Timeline(cap=1),
              tr(2, "M", "T1", "A", "B"),
              act(2, "M", "entry", "v", 0, 1),
              tr(2, "N", "T1", "A", "B", ["v"]))  # drops M's item
    assert tl.all()[0]["causes"] == [1]


def test_returned_lists_are_copies() -> None:
    tl = feed(Timeline(), inp(1, "a", 0, 1), inp(1, "b", 0, 1))
    tl.all().clear()
    tl.items_since(0).pop()
    assert len(tl.all()) == 2 and len(tl.items_since(0)) == 2


def test_origin_sets_stay_bounded() -> None:
    from statesim.timeline import MAX_ORIGINS

    tl = Timeline()
    for n in range(1, 3 * MAX_ORIGINS + 1):  # acc feeds back into itself
        feed(tl, inp(n, "a", n - 1, n), res(n, "EQ", "acc", n - 1, n, ["a", "acc"]))
    feed(tl, tr(999, "M", "T1", "A", "B", ["acc"]))
    causes = tl.all()[-1]["causes"]
    assert causes == list(range(2 * MAX_ORIGINS + 1, 3 * MAX_ORIGINS + 1))  # newest kept


def test_two_timelines_are_independent() -> None:
    a = feed(Timeline(), inp(1, "sw", False, True))
    b = feed(Timeline(gen=2), tr(2, "M", "T1", "A", "B", ["sw"]))
    assert b.all()[0]["id"] == 1 and b.all()[0]["causes"] == []
    assert a.last_id == 1 and b.gen == 2


# --- end to end with the real engine -------------------------------------------


def _engine_fills_kind() -> bool:
    sink = ListTraceSink()
    engine = Engine(load_model(ACTIONS), trace=sink)
    engine.set_input("toga", True)
    return bool(sink.events) and sink.events[0].kind != ""


@pytest.mark.skipif(not _engine_fills_kind(),
                    reason="engine does not fill TraceEvent.kind yet (T2, #14)")
def test_actions_example_end_to_end() -> None:
    tl = Timeline()
    engine = Engine(load_model(ACTIONS), trace=tl)
    engine.step()
    engine.set_input("toga", True)             # item 1
    engine.step()                              # item 2: Ground -> Takeoff
    engine.set_input("radio_altitude", 500)    # item 3
    engine.step()                              # item 4: Takeoff -> Climb
    engine.run(60)                             # item 5: Climb -> Cruise after 50 passes
    engine.set_input("radio_altitude", 500)    # unchanged: no item
    engine.set_input("radio_altitude", 0)      # item 6
    engine.step()                              # item 7: Cruise -> Ground

    items = tl.all()
    assert json.loads(json.dumps(items)) == items
    assert [i["id"] for i in items] == list(range(1, 8)) and tl.last_id == 7
    assert [i["k"] for i in items] == ["in", "tr", "in", "tr", "tr", "in", "tr"]
    assert [(i["name"], i["value"]) for i in items if i["k"] == "in"] == [
        ("toga", True), ("radio_altitude", 500), ("radio_altitude", 0)]

    trs = [i for i in items if i["k"] == "tr"]
    assert {i["sm"] for i in trs} == {"phase"}
    assert [(i["tid"], i["from"], i["to"], i["tick"]) for i in trs] == [
        ("T1", "Ground", "Takeoff", 2), ("T2", "Takeoff", "Climb", 3),
        ("T3", "Climb", "Cruise", 54), ("T4", "Cruise", "Ground", 64)]
    assert [i["t"] for i in trs] == [100.0, 200.0, 5300.0, 6300.0]
    assert trs[0]["title"] == "Takeoff roll"

    t1, t2, t3, t4 = trs
    assert t1["causes"] == [1]                      # the TOGA press
    assert t2["causes"] == [t1["id"], 3]            # radio_altitude 500, one pass after entering Takeoff
    assert t3["causes"] == [t2["id"]]               # climb_ticks, counted since T2 entered Climb
    assert t4["causes"] == [6]                      # radio_altitude 0
    assert t1["writes"] == [["ground_speed", 140]]  # entry
    assert t2["writes"][0] == ["ground_speed", 0]   # entry
    assert t3["writes"] == []                       # during writes are not shown
    assert t4["writes"] == [["ground_speed", 60]]   # exit
