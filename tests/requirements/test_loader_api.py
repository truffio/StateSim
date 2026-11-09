"""Loader, load checks, limits, time and API requirement tests (mostly unit-level)."""

import builtins
import dataclasses
from fractions import Fraction

import pytest

import statesim.constants as constants
import statesim.loader as loader_mod
from statesim import Engine, ModelError, load_model
from statesim.scheduler import build_schedule

from .helpers import E, EQ_HEADER, SM_HEADER, T, _write, build, engine_for

R = pytest.mark.req
GO = [("go", "bool", "False")]
ONE = ("S", [T("1", "OFF", "ON", "go", "r1", default="OFF")])


# ------------------------------------------------------------------ master
@R("REQ-001", "REQ-002", "REQ-003", "REQ-009", "REQ-010", "REQ-011", "REQ-012", "REQ-048")
def test_load_builds_model_from_master(tmp_path):
    model = load_model(build(tmp_path, sms=[ONE, ("T2", [T("1", "A", "B", "go", "r2", default="A")], 2)],
                             equations=[E("e", "go", band=20, order=3)], inputs=GO))
    assert [s.name for s in model.state_machines] == ["S", "T2"]
    assert [e.result_variable for e in model.equations] == ["e"]
    assert model.equations[0].order == 3 and model.equations[0].band_hz == 20
    assert [i.name for i in model.inputs] == ["go"] and model.inputs[0].default is False
    assert model.state_machines[1].master_order == 2
    with pytest.raises(dataclasses.FrozenInstanceError):
        model.tick_hz = 5


@R("REQ-006")
def test_order_ignored_for_equations_and_inputs_rows(tmp_path):
    build(tmp_path, sms=[ONE], equations=[E("e", "go")], inputs=GO)
    _write(tmp_path / "master.csv", ["file_name", "type", "order"],
           [["S.csv", "state_machine", "1"], ["equations.csv", "equations", "zzz"],
            ["inputs.csv", "inputs", "-7"]])
    assert load_model(tmp_path / "master.csv").equations


@R("REQ-007", "REQ-040")
def test_band_comes_from_definition_files(tmp_path):
    model = load_model(build(tmp_path, sms=[("S", [T("1", "OFF", "ON", "go", "r1", default="OFF", band=25)])],
                             inputs=GO))
    assert model.state_machines[0].band_hz == Fraction(25)


@R("REQ-025", "REQ-030", "REQ-031")
def test_global_default_and_self_transition(tmp_path):
    rows = [T("1", "ON", "ON", "go", "r1", default="ON"), T("2", "", "ON", "False", "r2")]
    model = load_model(build(tmp_path, sms=[("S", rows)], inputs=GO))
    sm = model.state_machines[0]
    assert sm.default_state == "ON"
    assert {t.id: t.current_state for t in sm.transitions} == {"1": "ON", "2": None}
    assert sm.transitions[0].next_state == "ON"


@R("REQ-032")
def test_expression_used_as_written(tmp_path):
    eng = engine_for(tmp_path, sms=[("S", [T("1", "OFF", "ON", "not go", "r1", default="OFF")])],
                     inputs=GO)
    eng.step()
    assert eng.snapshot()["states"]["S"] == "ON"


@R("REQ-033")
def test_multiple_state_machines(tmp_path):
    sms = [(f"M{i}", [T("1", "A", "B", "True", f"r{i}", default="A")], i) for i in range(5)]
    eng = engine_for(tmp_path, sms=sms)
    eng.step()
    assert set(eng.snapshot()["states"].values()) == {"B"} and len(eng.snapshot()["states"]) == 5


@R("REQ-037")
def test_result_variable_cannot_shadow_input(tmp_path):
    with pytest.raises(ModelError):
        load_model(build(tmp_path, equations=[E("go", "True")], inputs=GO))


@R("REQ-039")
def test_input_defaults_converted(tmp_path):
    model = load_model(build(tmp_path, equations=[E("e", "True")],
                             inputs=[("a", "bool", "True"), ("b", "int", "7"),
                                     ("c", "float", "1.5")]))
    d = {i.name: i.default for i in model.inputs}
    assert d == {"a": True, "b": 7, "c": 1.5}
    assert [type(d[k]) for k in "abc"] == [bool, int, float]


@R("REQ-045", "REQ-046")
def test_tick_rate_is_lcm_and_periods_are_whole(tmp_path):
    model = load_model(build(tmp_path, equations=[E("a", "True", band=20), E("b", "True", band=30),
                                                  E("c", "True", band="1/2")]))
    assert model.tick_hz == 60
    sched = {it.name: it.period_ticks for it in build_schedule(model)}
    assert sched == {"a": 3, "b": 2, "c": 120}
    assert all(isinstance(v, int) for v in sched.values())


@R("REQ-053")
def test_schedule_sorted_by_band_then_order(tmp_path):
    model = load_model(build(tmp_path, equations=[E("lo", "True", band=10, order=1),
                                                  E("hi2", "True", band=20, order=2),
                                                  E("hi1", "True", band=20, order=1)]))
    assert [i.name for i in build_schedule(model)] == ["hi1", "hi2", "lo"]


# -------------------------------------------------------------------- time
@R("REQ-059", "REQ-060", "REQ-061")
def test_tick_is_integer_and_increments_at_step_start(tmp_path):
    eng = engine_for(tmp_path, equations=[E("first", "tick == 1"), E("slow", "t >= 0.2", band=5),
                                          E("fast", "True", band=10)])
    assert eng.tick == 0 and isinstance(eng.tick, int)
    eng.step()
    assert eng.tick == 1 and eng.snapshot()["outputs"]["first"] is True
    assert eng.t == Fraction(1, 10)  # tick_hz = 10
    eng.run(3)
    assert eng.tick == 4 and eng.t == Fraction(4, 10)
    assert eng.snapshot()["t"] == pytest.approx(0.4)


# --------------------------------------------------------------- loadcheck
@R("REQ-065")
def test_syntax_error_rejected(tmp_path):
    with pytest.raises(ModelError):
        load_model(build(tmp_path, equations=[E("e", "a and (")]))


@R("REQ-066", "REQ-071")
def test_transition_id_rows_must_agree(tmp_path):
    rows = [T("1", "A", "B", "x", "r1", default="A"), T("1", "A", "C", "y", "r2")]
    with pytest.raises(ModelError, match="S.csv"):
        load_model(build(tmp_path, sms=[("S", rows)]))
    rows = [T("1", "A", "B", "x", "r1", default="A"), T("1", "B", "B", "y", "r2")]
    d = tmp_path / "x"
    d.mkdir()
    with pytest.raises(ModelError):
        load_model(build(d, sms=[("S", rows)]))


@R("REQ-067", "REQ-072")
def test_unknown_state_rejected(tmp_path):
    rows = [T("1", "A", "B", "x", "r1", default="A"), T("2", "GHOST", "A", "x", "r2")]
    with pytest.raises(ModelError):
        load_model(build(tmp_path, sms=[("S", rows)]))
    d = tmp_path / "d"
    d.mkdir()
    with pytest.raises(ModelError):  # default state not used by any transition
        load_model(build(d, sms=[("S", [T("1", "A", "B", "x", "r1", default="Z")])]))


@R("REQ-068", "REQ-069", "REQ-070")
def test_default_state_and_band_rules(tmp_path):
    cases = {
        "none": [T("1", "A", "B", "x", "r1")],
        "two": [T("1", "A", "B", "x", "r1", default="A"), T("2", "B", "A", "x", "r2", default="A")],
        "bands": [T("1", "A", "B", "x", "r1", default="A", band=10),
                  T("2", "B", "A", "x", "r2", band=20)],
    }
    for name, rows in cases.items():
        d = tmp_path / name
        d.mkdir()
        with pytest.raises(ModelError):
            load_model(build(d, sms=[("S", rows)]))


@R("REQ-077")
@pytest.mark.parametrize("band", ["0", "-5", "abc", ""])
def test_bad_band_rejected(tmp_path, band):
    with pytest.raises(ModelError):
        load_model(build(tmp_path, equations=[E("e", "True", band=band)]))


def _patch_limit(monkeypatch, name, value):
    monkeypatch.setattr(constants, name, value)
    monkeypatch.setattr(loader_mod, name, value, raising=False)


@R("REQ-073", "REQ-075")
def test_max_equations_counts_transition_rows(tmp_path, monkeypatch):
    _patch_limit(monkeypatch, "MAX_EQUATIONS", 3)
    rows = [T("1", "A", "B", "x", "r1", default="A"), T("2", "B", "A", "x", "r2")]
    load_model(build(tmp_path, sms=[("S", rows)], equations=[E("e1", "True")]))  # 3 == limit
    d = tmp_path / "over"
    d.mkdir()
    with pytest.raises(ModelError):
        load_model(build(d, sms=[("S", rows)], equations=[E("e1", "True"), E("e2", "True")]))
    d = tmp_path / "over2"
    d.mkdir()
    rows3 = rows + [T("3", "B", "A", "x", "r3")]
    with pytest.raises(ModelError):  # only transition rows exceed it
        load_model(build(d, sms=[("S", rows3)], equations=[E("e1", "True")]))


@R("REQ-074")
def test_max_state_machines(tmp_path, monkeypatch):
    _patch_limit(monkeypatch, "MAX_STATE_MACHINES", 2)
    mk = lambda n: [(f"M{i}", [T("1", "A", "B", "True", f"r{i}", default="A")], i) for i in range(n)]
    load_model(build(tmp_path, sms=mk(2)))
    d = tmp_path / "over"
    d.mkdir()
    with pytest.raises(ModelError):
        load_model(build(d, sms=mk(3)))


# ----------------------------------------------------------------- compile
@R("REQ-079", "REQ-080")
def test_expressions_compiled_once(tmp_path, monkeypatch):
    model = load_model(build(tmp_path, sms=[ONE], equations=[E("e", "go or not go")], inputs=GO))
    calls = []
    real = builtins.compile

    def counting(*a, **k):
        calls.append(a[0])
        return real(*a, **k)

    monkeypatch.setattr(builtins, "compile", counting)
    eng = Engine(model)
    n = len(calls)
    assert n >= 2  # one per expression
    eng.run(20)
    assert len(calls) == n


# --------------------------------------------------------------------- api
@R("REQ-082", "REQ-083", "REQ-084", "REQ-085", "REQ-086")
def test_public_api(tmp_path):
    eng = Engine(load_model(build(tmp_path, sms=[ONE], inputs=GO)))
    eng.step()
    assert eng.tick == 1
    eng.run(4)
    assert eng.tick == 5
    eng.run(0)
    assert eng.tick == 5
    eng.set_input("go", True)
    assert eng.snapshot()["inputs"]["go"] is True
