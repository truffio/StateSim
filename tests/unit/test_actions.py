"""Actions (setvar): actions CSV, state machine action columns, init_action."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from statesim import Engine, ListTraceSink, ModelError, load_model
from statesim_server.session import Session, describe_model

SM_HEADER = ["transition_id", "current_state", "next_state", "default_state", "equation",
             "result_variable", "rationale", "title", "order", "action_type", "action"]


def _write(path: Path, header, rows) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def R(tid, cur, nxt, eq, rv, *, default="", order=1, kind="", action="", title=""):
    """One state machine row with the two action columns."""
    return [tid, cur, nxt, default, eq, rv, "", title, order, kind, action]


def build(tmp_path, sms, actions=None, inputs=(), equations=None, init=None):
    """sms: {name: rows}. actions: [(action, statement)]. inputs: [(name, type,
    default, widget)]. equations: [(result, equation, order)]. init: {sm: action}."""
    init = init or {}
    master = []
    order = 10
    for name, rows in sms.items():
        _write(tmp_path / f"{name}.csv", SM_HEADER, rows)
        master.append([f"{name}.csv", "state_machine", order, 10, init.get(name, "")])
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
               [[eq, "", "", rv, 10, o] for rv, eq, o in equations])
        master.append(["equations.csv", "equations", "", "", ""])
    _write(tmp_path / "master.csv", ["file_name", "type", "order", "band", "init_action"],
           master)
    return tmp_path / "master.csv"


def engine(tmp_path, trace=None, **kw):
    return Engine(load_model(build(tmp_path, **kw)), trace)


def load_error(tmp_path, **kw) -> str:
    with pytest.raises(ModelError) as ei:
        load_model(build(tmp_path, **kw))
    return str(ei.value)


# Ground -> Air when alt > 400 (entry SPEED_ZERO); Air -> Ground when alt == 0.
def takeoff_sm(entry="SPEED_ZERO", exit_="", during=""):
    rows = [R("1", "Ground", "Air", "alt > 400", "r1", default="Ground", order=1,
              kind="entry" if entry else "", action=entry)]
    if exit_:
        rows.append(R("1", "Ground", "Air", "True", "r1b", order=2, kind="exit",
                      action=exit_))
    rows.append(R("2", "Air", "Ground", "alt == 0", "r2", order=3,
                  kind="during" if during else "", action=during))
    return {"S": rows}


INPUTS = [("alt", "int", "0"), ("speed", "int", "140"), ("n", "int", "0", "none")]


# ------------------------------------------------------------------ loading
@pytest.mark.req("REQ-148", "REQ-153")
def test_model_carries_actions(tmp_path):
    m = load_model(build(tmp_path, sms=takeoff_sm(exit_="EX", during="TICK"),
                         actions=[("SPEED_ZERO", "speed = 0"), ("EX", "n = 5"),
                                  ("TICK", "n += 1"), ("SPEED_ZERO", "n = 0")],
                         inputs=INPUTS))
    a = {x.name: x for x in m.actions}
    assert [s.statement for s in a["SPEED_ZERO"].statements] == ["speed = 0", "n = 0"]
    assert a["TICK"].statements[0].targets == ("n",)
    sm = m.state_machines[0]
    t1 = sm.transitions[0]
    assert (t1.entry_action, t1.exit_action) == ("SPEED_ZERO", "EX")
    assert sm.during_action("Air") == "TICK" and sm.during_action("Ground") == ""


def test_existing_models_need_no_action_columns(tmp_path):
    m = load_model(Path("examples/autopilot2/master.csv"))
    assert m.actions == ()


@pytest.mark.req("REQ-149")
@pytest.mark.parametrize("stmt, msg", [
    ("", "statement is empty"),
    ("speed = ", "invalid statement"),
    ("speed = 0; n = 1", "single statement"),
    ("speed == 0", "not an assignment"),
    ("print(speed)", "not an assignment"),
    ("speed.x = 1", "plain variable names"),
    ("a, b = 1, 2", "plain variable names"),
])
def test_bad_statement(tmp_path, stmt, msg):
    text = load_error(tmp_path, sms=takeoff_sm(), actions=[("SPEED_ZERO", stmt)],
                      inputs=INPUTS)
    assert msg in text and "actions.csv:2" in text


@pytest.mark.req("REQ-149")
def test_chained_and_augmented_assignments(tmp_path):
    m = load_model(build(tmp_path, sms=takeoff_sm(),
                         actions=[("SPEED_ZERO", "speed = n = 0"), ("SPEED_ZERO", "n -= 2")],
                         inputs=INPUTS))
    assert [s.targets for s in m.actions[0].statements] == [("speed", "n"), ("n",)]


@pytest.mark.req("REQ-151")
def test_targets_must_be_inputs(tmp_path):
    text = load_error(tmp_path, sms=takeoff_sm(), actions=[("SPEED_ZERO", "r1 = True")],
                      inputs=INPUTS)
    assert "writes 'r1', which is not an input" in text
    text = load_error(tmp_path, sms=takeoff_sm(), actions=[("SPEED_ZERO", "S = 'Air'")],
                      inputs=INPUTS)
    assert "writes 'S', which is not an input" in text
    text = load_error(tmp_path, sms=takeoff_sm(), actions=[("SPEED_ZERO", "zz = 1")],
                      inputs=INPUTS)
    assert "writes 'zz', which is not declared" in text and "widget none" in text


@pytest.mark.req("REQ-153")
@pytest.mark.parametrize("row, msg", [
    (R("1", "Ground", "Air", "x", "r1", default="Ground", kind="entry"),
     "action_type is set but action is empty"),
    (R("1", "Ground", "Air", "x", "r1", default="Ground", action="A"), "needs an action_type"),
    (R("1", "Ground", "Air", "x", "r1", default="Ground", kind="onentry", action="A"),
     "unknown action_type 'onentry'"),
    (R("1", "Ground", "Air", "x", "r1", default="Ground", kind="entry", action="B"),
     "action 'B' is not defined"),
    (R("1", "", "Air", "x", "r1", default="Ground", kind="during", action="A"),
     "a during action needs a current_state"),
])
def test_bad_action_columns(tmp_path, row, msg):
    text = load_error(tmp_path, sms={"S": [row]}, actions=[("A", "speed = 0")], inputs=INPUTS)
    assert msg in text and "S.csv:2" in text


@pytest.mark.req("REQ-154")
def test_one_entry_and_one_exit_per_transition(tmp_path):
    rows = [R("1", "Ground", "Air", "x", "r1", default="Ground", kind="entry", action="A"),
            R("1", "Ground", "Air", "y", "r2", kind="entry", action="A")]
    assert "transition '1' already has entry action 'A'" in load_error(
        tmp_path, sms={"S": rows}, actions=[("A", "speed = 0")], inputs=INPUTS)


@pytest.mark.req("REQ-155")
def test_one_during_action_per_state(tmp_path):
    rows = [R("1", "Ground", "Air", "x", "r1", default="Ground", kind="during", action="A"),
            R("2", "Ground", "Air", "y", "r2", kind="during", action="A"),   # same: fine
            R("3", "Ground", "Air", "z", "r3", kind="during", action="B")]
    text = load_error(tmp_path, sms={"S": rows},
                      actions=[("A", "speed = 0"), ("B", "speed = 1")], inputs=INPUTS)
    assert "state 'Ground' already has during action 'A'" in text and "S.csv:4" in text


@pytest.mark.req("REQ-156")
def test_init_action_checks(tmp_path):
    assert "action 'NOPE' is not defined" in load_error(
        tmp_path, sms=takeoff_sm(), actions=[("SPEED_ZERO", "speed = 0")], inputs=INPUTS,
        init={"S": "NOPE"})
    _write(tmp_path / "master.csv", ["file_name", "type", "init_action"],
           [["inputs.csv", "inputs", "X"]])
    with pytest.raises(ModelError, match="state_machine rows only"):
        load_model(tmp_path / "master.csv")


@pytest.mark.req("REQ-148")
def test_one_actions_file(tmp_path):
    build(tmp_path, sms=takeoff_sm(), actions=[("SPEED_ZERO", "speed = 0")], inputs=INPUTS)
    with open(tmp_path / "master.csv", "a", newline="") as f:
        csv.writer(f).writerow(["actions.csv", "actions", "", "", ""])
    with pytest.raises(ModelError, match="more than one 'actions' row"):
        load_model(tmp_path / "master.csv")


# ------------------------------------------------------------------ running
@pytest.mark.req("REQ-154", "REQ-157")
def test_entry_action_sets_input_when_transition_fires(tmp_path):
    e = engine(tmp_path, sms=takeoff_sm(), actions=[("SPEED_ZERO", "speed = 0")],
               inputs=INPUTS)
    e.run(3)
    assert e.snapshot()["inputs"]["speed"] == 140
    e.set_input("alt", 500)
    e.step()
    s = e.snapshot()
    assert s["states"]["S"] == "Air" and s["inputs"]["speed"] == 0
    e.set_input("speed", 90)        # the user can move it again afterwards
    e.run(3)
    assert e.snapshot()["inputs"]["speed"] == 90


@pytest.mark.req("REQ-154")
def test_exit_runs_before_and_entry_after_state_change(tmp_path):
    e = engine(tmp_path, sms=takeoff_sm(entry="EN", exit_="EX"),
               actions=[("EX", "seen_exit = S"), ("EN", "seen_entry = S")],
               inputs=INPUTS + [("seen_exit", "str", "", "none"),
                                ("seen_entry", "str", "", "none")])
    e.set_input("alt", 500)
    e.step()
    i = e.snapshot()["inputs"]
    assert (i["seen_exit"], i["seen_entry"]) == ("Ground", "Air")


@pytest.mark.req("REQ-150")
def test_statements_run_in_row_order(tmp_path):
    e = engine(tmp_path, sms=takeoff_sm(),
               actions=[("SPEED_ZERO", "n = 2"), ("SPEED_ZERO", "n = n * 10"),
                        ("SPEED_ZERO", "n += 1")], inputs=INPUTS)
    e.set_input("alt", 500)
    e.step()
    assert e.snapshot()["inputs"]["n"] == 21


@pytest.mark.req("REQ-155")
def test_during_runs_only_while_staying(tmp_path):
    e = engine(tmp_path, sms=takeoff_sm(entry="", during="TICK"),
               actions=[("TICK", "n += 1")], inputs=INPUTS)
    e.set_input("alt", 500)
    e.step()                          # enters Air: no during on this pass
    assert e.snapshot()["inputs"]["n"] == 0
    e.run(3)                          # stays in Air: during each pass
    assert e.snapshot()["inputs"]["n"] == 3
    e.set_input("alt", 0)
    e.step()                          # leaves Air: no during
    e.run(2)                          # Ground has no during action
    assert e.snapshot()["inputs"]["n"] == 3


@pytest.mark.req("REQ-155")
def test_global_self_transition_counts_as_staying(tmp_path):
    rows = [R("G", "", "Air", "hold", "g", order=1, kind="entry", action="BUMP"),
            R("1", "Air", "Ground", "True", "r1", default="Air", order=2,
              kind="during", action="TICK")]
    e = engine(tmp_path, sms={"S": rows}, actions=[("TICK", "n += 1"), ("BUMP", "n += 100")],
               inputs=INPUTS + [("hold", "bool", "true")])
    e.run(2)
    assert e.snapshot()["states"]["S"] == "Air" and e.snapshot()["inputs"]["n"] == 2


@pytest.mark.req("REQ-154")
def test_self_transition_runs_exit_and_entry_not_during(tmp_path):
    rows = [R("1", "A", "A", "True", "r1", default="A", order=1, kind="entry", action="EN"),
            R("1", "A", "A", "True", "r1b", order=2, kind="exit", action="EX"),
            R("2", "A", "A", "False", "r2", order=3, kind="during", action="DU")]
    e = engine(tmp_path, sms={"S": rows},
               actions=[("EN", "n += 1"), ("EX", "n += 10"), ("DU", "n += 100")],
               inputs=INPUTS)
    e.run(2)
    assert e.snapshot()["inputs"]["n"] == 22


@pytest.mark.req("REQ-156")
def test_init_action_runs_once_on_first_pass_only_when_set(tmp_path):
    kw = dict(sms=takeoff_sm(entry="", during="TICK"),
              actions=[("TICK", "n += 1"), ("START", "speed = 7"), ("START", "n = 50")],
              inputs=INPUTS)
    e = engine(tmp_path, **kw)
    e.run(2)
    assert e.snapshot()["inputs"]["speed"] == 140          # default: no init action
    e = engine(tmp_path / ".", init={"S": "START"}, **kw)
    e.step()
    assert e.snapshot()["inputs"] == {"alt": 0, "n": 50, "speed": 7}
    e.set_input("speed", 100)
    e.run(2)
    assert e.snapshot()["inputs"]["speed"] == 100           # not repeated


@pytest.mark.req("REQ-157")
def test_writes_visible_to_later_items_same_pass(tmp_path):
    e = engine(tmp_path, sms=takeoff_sm(), actions=[("SPEED_ZERO", "speed = 0")],
               inputs=INPUTS, equations=[("stopped", "speed == 0", 50)])
    e.set_input("alt", 500)
    e.step()
    assert e.snapshot()["outputs"]["stopped"] is True


@pytest.mark.req("REQ-157")
def test_action_writes_are_logged(tmp_path):
    sink = ListTraceSink()
    e = engine(tmp_path, trace=sink, sms=takeoff_sm(exit_="EX"),
               actions=[("SPEED_ZERO", "speed = 0"), ("SPEED_ZERO", "n = 0"), ("EX", "n = 3")],
               inputs=INPUTS)
    e.set_input("alt", 500)
    e.step()
    actions = [ev.action for ev in sink.events if ev.component == "S"]
    assert actions == ["r1 False->True", "r1b False->True", "EX: set n 0->3",
                       'T1 Ground->Air ""', "SPEED_ZERO: set speed 140->0",
                       "SPEED_ZERO: set n 3->0"]
    ev = sink.events[-2]
    assert ev.values == (("speed", 0),)


def test_runtime_error_in_action_has_location(tmp_path):
    from statesim import EvaluationError
    e = engine(tmp_path, sms=takeoff_sm(), actions=[("SPEED_ZERO", "speed = 1 / n")],
               inputs=INPUTS)
    e.set_input("alt", 500)
    with pytest.raises(EvaluationError, match=r"actions.csv:2: tick 1, S: ZeroDivisionError"):
        e.step()


# ---------------------------------------------------------------- front end
@pytest.mark.req("REQ-152", "REQ-158")
def test_internal_variable_has_no_card_and_controls_follow_actions(tmp_path):
    m = load_model(build(tmp_path, sms=takeoff_sm(), actions=[("SPEED_ZERO", "speed = 0")],
                         inputs=INPUTS))
    shown = [i["name"] for g in describe_model(m)["groups"] for i in g["inputs"]]
    assert "n" not in shown and "speed" in shown
    s = Session(m)
    s.handle({"type": "set", "name": "alt", "value": 500})
    s.step()
    assert s.state()["inputs"]["speed"] == 0


@pytest.mark.req("REQ-152")
def test_internal_widget_allowed_for_every_type(tmp_path):
    m = load_model(build(tmp_path, sms=takeoff_sm(), actions=[("SPEED_ZERO", "speed = 0")],
                         inputs=INPUTS + [("b", "bool", "false", "none"),
                                          ("f", "float", "1.5", "none"),
                                          ("s", "str", "x", "none")]))
    assert all(i.widget == "none" for i in m.inputs if i.name in "nbfs")


@pytest.mark.req("REQ-154", "REQ-155", "REQ-156")
def test_actions_example():
    e = Engine(load_model(Path(__file__).resolve().parents[2] / "examples/actions/master.csv"))

    def snap():
        s = e.snapshot()
        return s["states"]["phase"], s["inputs"]["ground_speed"]

    e.set_input("ground_speed", 30)
    e.step()                                     # init_action START
    assert snap() == ("Ground", 0)
    e.set_input("toga", True)
    e.step()
    assert snap() == ("Takeoff", 140)
    e.set_input("toga", False)
    e.set_input("radio_altitude", 500)
    e.step()
    assert snap() == ("Climb", 0)
    e.run(50)
    assert snap() == ("Climb", 0) and e.snapshot()["inputs"]["climb_ticks"] == 50
    e.step()
    assert snap() == ("Cruise", 0)
    e.set_input("radio_altitude", 0)
    e.step()
    assert snap() == ("Ground", 60)
