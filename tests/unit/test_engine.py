"""Unit tests for statesim.engine.Engine."""

from fractions import Fraction

import pytest

from statesim import Engine, ListTraceSink, load_model
from tests.requirements.helpers import E, T, build


def eng(tmp_path, trace=None, **kw):
    return Engine(load_model(build(tmp_path, **kw)), trace)


def test_tick_t_dt_math(tmp_path):
    e = eng(
        tmp_path,
        equations=[E("a", "tick >= 1", band=10),
                   E("b", "dt == 1/3 or True", band=3)],
    )
    assert e.tick == 0 and e.t == 0
    e.step()
    assert e.tick == 1 and e.t == Fraction(1, 30)
    e.run(2)
    assert e.tick == 3 and e.t == Fraction(1, 10)
    assert e.snapshot()["t"] == float(Fraction(1, 10))
    e.run(0)
    assert e.tick == 3


def test_reserved_names_in_context(tmp_path):
    e = eng(tmp_path, equations=[E("ok", "tick == 2 and t * 5 == 1 and dt * 10 == 1")])
    e.run(2)
    assert e.snapshot()["outputs"]["ok"] is True


def test_initial_state_and_inputs(tmp_path):
    e = eng(tmp_path, sms=[("S", [T("1", "OFF", "ON", "go", "r", default="OFF")])],
            inputs=[("go", "bool", "False"), ("alt", "int", "5")])
    s = e.snapshot()
    assert s == {"tick": 0, "t": 0.0, "states": {"S": "OFF"}, "outputs": {"r": False},
                 "inputs": {"alt": 5, "go": False}}
    assert list(s["inputs"]) == ["alt", "go"]


def test_set_input_and_unknown(tmp_path):
    sink = ListTraceSink()
    e = eng(tmp_path, trace=sink, sms=[("S", [T("1", "OFF", "ON", "go", "r", default="OFF")])],
            inputs=[("go", "bool", "False")])
    with pytest.raises(KeyError):
        e.set_input("nope", 1)
    e.set_input("go", True)
    assert sink.lines() == ["tick=000000 t=0.000000 | INPUT | set go False->True | go=True"]
    e.step()
    assert e.snapshot()["states"]["S"] == "ON"


def test_snapshot_is_fresh(tmp_path):
    e = eng(tmp_path, inputs=[("go", "bool", "False")])
    s = e.snapshot()
    s["inputs"]["go"] = 99
    assert e.snapshot()["inputs"]["go"] is False


def test_trace_emission(tmp_path):
    sink = ListTraceSink()
    e = eng(tmp_path, trace=sink,
            sms=[("S", [T("3", "OFF", "ON", "go and alt > 1", "r", default="OFF", title="Arm")])],
            inputs=[("go", "bool", "True"), ("alt", "int", "5")])
    e.step()
    assert sink.lines() == [
        "tick=000001 t=0.100000 | S | r False->True | alt=5, go=True",
        'tick=000001 t=0.100000 | S | T3 OFF->ON "Arm" | alt=5, go=True',
    ]
    e.step()
    assert len(sink.events) == 2  # no change, no event


def test_one_transition_per_pass_and_no_short_circuit(tmp_path):
    rows = [
        T("1", "A", "B", "True", "r1", default="A", order=1),
        T("2", "B", "C", "True", "r2", order=2),
    ]
    e = eng(tmp_path, sms=[("S", rows)])
    e.step()
    s = e.snapshot()
    assert s["states"]["S"] == "B"
    assert s["outputs"] == {"r1": True, "r2": True}  # r2 evaluated although not fired
    e.step()
    assert e.snapshot()["states"]["S"] == "C"


def test_global_self_transition_is_noop_and_wins(tmp_path):
    sink = ListTraceSink()
    rows = [
        T("1", "", "A", "True", "g", default="A", order=1),
        T("2", "A", "B", "True", "r", order=2),
    ]
    e = eng(tmp_path, trace=sink, sms=[("S", rows)])
    e.run(3)
    assert e.snapshot()["states"]["S"] == "A"
    assert not any("->" in ev.action and ev.action.startswith("T") for ev in sink.events)
