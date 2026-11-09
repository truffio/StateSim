"""Unit tests for statesim.scheduler (docs/decisions.md items 1, 4, 5)."""

from fractions import Fraction

import pytest

from statesim.model import EquationDef, Model, StateMachine, compute_tick_hz
from statesim.scheduler import build_schedule, due_items


def _sm(name, hz, order):
    return StateMachine(
        name=name,
        default_state="OFF",
        band_hz=Fraction(hz),
        master_order=Fraction(order),
        states=("OFF",),
        transitions=(),
        source=f"master.csv:{name}",
    )


def _eq(name, hz, order):
    return EquationDef(
        result_variable=name,
        equation="True",
        band_hz=Fraction(hz),
        order=Fraction(order),
        explanation="",
        rationale="",
        source=f"eq.csv:{name}",
    )


def _model(sms=(), eqs=()):
    bands = [s.band_hz for s in sms] + [e.band_hz for e in eqs]
    return Model(
        state_machines=tuple(sms),
        equations=tuple(eqs),
        inputs=(),
        tick_hz=compute_tick_hz(bands),
        master_path="master.csv",
    )


def _names(items):
    return [it.name for it in items]


def test_tick_hz_and_periods_for_20_and_30_hz():
    m = _model(sms=[_sm("A", 20, 1), _sm("B", 30, 1)])
    assert m.tick_hz == 60
    sched = build_schedule(m)
    periods = {it.name: it.period_ticks for it in sched}
    assert periods == {"A": 3, "B": 2}
    assert all(type(it.period_ticks) is int for it in sched)


def test_higher_frequency_band_sorts_first_regardless_of_order():
    # 20Hz item has the smaller order, but the 30Hz band must still come first.
    m = _model(sms=[_sm("slow", 20, 0), _sm("fast", 30, 99)])
    assert _names(build_schedule(m)) == ["fast", "slow"]


def test_order_within_band_ascending_not_declaration_order():
    m = _model(eqs=[_eq("late", 20, 5), _eq("early", 20, 1), _eq("mid", 20, 3)])
    assert _names(build_schedule(m)) == ["early", "mid", "late"]


def test_ties_broken_by_master_row_then_csv_row():
    # Same band and order: state machines (master rows) come before the
    # equations row, and equations keep CSV row order.
    m = _model(sms=[_sm("S1", 20, 2), _sm("S2", 20, 2)], eqs=[_eq("e2", 20, 2), _eq("e1", 20, 2)])
    sched = build_schedule(m)
    assert _names(sched) == ["S1", "S2", "e2", "e1"]
    assert [it.seq for it in sched] == [0, 1, 2, 3]


def test_equations_and_state_machines_share_order_space():
    m = _model(sms=[_sm("SM", 20, 2)], eqs=[_eq("low", 20, 1), _eq("high", 20, 3)])
    assert _names(build_schedule(m)) == ["low", "SM", "high"]


def test_equation_expanded_to_one_item_per_equation_with_kind():
    m = _model(sms=[_sm("SM", 20, 1)], eqs=[_eq("q1", 30, 1), _eq("q2", 30, 2)])
    sched = build_schedule(m)
    assert [(it.kind, it.name) for it in sched] == [
        ("equation", "q1"),
        ("equation", "q2"),
        ("state_machine", "SM"),
    ]
    assert len(sched) == 3


def test_build_schedule_is_deterministic():
    m = _model(sms=[_sm("A", 20, 1), _sm("B", 30, 1)], eqs=[_eq("e", 20, 1)])
    assert build_schedule(m) == build_schedule(m)


def test_due_items_20_and_30_hz_over_first_six_ticks():
    m = _model(sms=[_sm("slow20", 20, 1), _sm("fast30", 30, 1)])
    sched = build_schedule(m)
    due = {t: _names(due_items(sched, t)) for t in range(1, 7)}
    assert due == {
        1: ["fast30", "slow20"],  # every band runs on tick 1, 30Hz first
        2: [],
        3: ["fast30"],
        4: ["slow20"],
        5: ["fast30"],
        6: [],
    }


def test_due_items_preserves_schedule_order():
    m = _model(eqs=[_eq("c", 20, 3), _eq("a", 20, 1), _eq("b", 20, 2)])
    sched = build_schedule(m)
    assert _names(due_items(sched, 1)) == ["a", "b", "c"]


def test_due_items_empty_schedule():
    assert due_items((), 1) == ()


def test_due_items_rejects_tick_below_one():
    sched = build_schedule(_model(eqs=[_eq("e", 20, 1)]))
    with pytest.raises(ValueError):
        due_items(sched, 0)


def test_non_integer_period_raises():
    # tick_hz 60 with a 7Hz band gives period 60/7, which is not an int.
    m = Model(
        state_machines=(),
        equations=(_eq("e", 7, 1),),
        inputs=(),
        tick_hz=Fraction(60),
        master_path="master.csv",
    )
    with pytest.raises(ValueError):
        build_schedule(m)


def test_fractional_band_frequency_period():
    # tick_hz = lcm(1/2, 1/3) = 1 Hz, so periods are 2 and 3 ticks.
    m = _model(eqs=[_eq("half", "1/2", 1), _eq("third", "1/3", 1)])
    assert m.tick_hz == 1
    periods = {it.name: it.period_ticks for it in build_schedule(m)}
    assert periods == {"half": 2, "third": 3}
