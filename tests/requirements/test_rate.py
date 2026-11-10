"""Computation-rate tests: every item is evaluated exactly at its band rate,
continuously, over long runs (equations and state machines alike)."""

from collections import defaultdict
from fractions import Fraction

import pytest

from statesim import Engine, ListTraceSink

from .helpers import E, T, engine_for

R = pytest.mark.req
GO = [("go", "bool", "False")]


def count_passes(monkeypatch, eng):
    """Record the ticks on which each item (equation or state machine) runs.

    Wraps Engine._eval; a state machine evaluates several rows per pass, so
    ticks are stored in a set per item.
    """
    seen = defaultdict(set)
    orig = Engine._eval

    def spy(self, code, source, item):
        seen[item].add(self._tick)
        return orig(self, code, source, item)

    monkeypatch.setattr(Engine, "_eval", spy)
    return seen


@R("REQ-043", "REQ-044", "REQ-057", "REQ-111", "REQ-113")
def test_every_item_runs_exactly_at_its_band_rate_over_long_run(tmp_path, monkeypatch):
    # Bands 1, 5, 7, 20, 30 Hz -> tick rate 420 Hz. Run 10 s (4200 ticks).
    eqs = [E("e1", "True", band=1), E("e7", "True", band=7),
           E("e20", "True", band=20), E("e30a", "True", band=30, order=1),
           E("e30b", "True", band=30, order=2)]
    sm = ("S", [T("1", "A", "B", "go", "r1", default="A", band=5),
                T("2", "B", "A", "not go", "r2", band=5, order=2)], 1)
    eng = engine_for(tmp_path, equations=eqs, sms=[sm], inputs=GO)
    seen = count_passes(monkeypatch, eng)
    seconds = 10
    eng.run(420 * seconds)
    for item, hz in [("e1", 1), ("e7", 7), ("e20", 20), ("e30a", 30), ("e30b", 30), ("S", 5)]:
        ticks = sorted(seen[item])
        assert len(ticks) == hz * seconds, item
        period = 420 // hz
        assert ticks == [1 + k * period for k in range(hz * seconds)], item
        # evaluation instants in ms are exact multiples of the period: no drift
        times = [Fraction(tk - 1) * 1000 / 420 for tk in ticks]
        assert times[-1] == Fraction(1000, hz) * (hz * seconds - 1), item
    assert seen["e30a"] == seen["e30b"]          # same band, same rate


@R("REQ-055", "REQ-113", "REQ-064")
def test_continuous_square_wave_over_long_run(tmp_path):
    # 10 Hz equation toggling every 500 ms; an unrelated 30 Hz band changes the
    # tick rate. Over 20 s the output must toggle 39 times, always at t = k*500.
    trace = ListTraceSink()
    eng = engine_for(tmp_path, trace=trace,
                     equations=[E("sq", "(t // 500) % 2 == 1", band=10),
                                E("noise", "True", band=30)])
    eng.run(30 * 20)                               # tick rate 30 Hz, 20 s
    toggles = [ev for ev in trace.events if ev.action.startswith("sq ")]
    assert len(toggles) == 39
    assert [ev.t for ev in toggles] == [Fraction(500 * k) for k in range(1, 40)]


@R("REQ-111", "REQ-043")
def test_state_machine_reacts_only_on_its_band_passes(tmp_path):
    # SM at 2 Hz (period 500 ms) next to a 20 Hz equation (tick rate 20 Hz).
    sm = ("S", [T("1", "OFF", "ON", "go", "r_on", default="OFF", band=2),
                T("2", "ON", "OFF", "not go", "r_off", band=2, order=2)], 1)
    eng = engine_for(tmp_path, sms=[sm], equations=[E("fast", "go", band=20)],
                     inputs=GO)
    eng.step()                                     # tick 1: both run
    eng.set_input("go", True)
    states, fast = [], []
    for _ in range(10):                            # ticks 2..11
        eng.step()
        s = eng.snapshot()
        states.append(s["states"]["S"])
        fast.append(s["outputs"]["fast"])
    assert fast == [True] * 10                     # 20 Hz sees it at once
    # 2 Hz band runs on ticks 1, 11, 21 ...: the SM changes only at tick 11
    assert states == ["OFF"] * 9 + ["ON"]


@R("REQ-112", "REQ-043")
def test_input_pulse_between_passes_is_not_seen_by_slow_band(tmp_path):
    # 1 Hz and 10 Hz bands, tick rate 10 Hz. A 300 ms pulse on ticks 2..4 falls
    # between two 1 Hz passes (ticks 1 and 11).
    eng = engine_for(tmp_path, inputs=GO,
                     equations=[E("slow", "go", band=1), E("fast", "go", band=10)])
    slow, fast = [], []
    for tick in range(1, 31):
        if tick in (2, 5):
            eng.set_input("go", tick == 2)
        eng.step()
        o = eng.snapshot()["outputs"]
        slow.append(o["slow"])
        fast.append(o["fast"])
    assert fast[1:4] == [True, True, True] and not any(fast[4:])
    assert not any(slow)                           # 1 Hz never sampled it


@R("REQ-019", "REQ-055", "REQ-113")
def test_rows_track_inputs_continuously_while_state_is_unchanged(tmp_path):
    # The OFF->ON transition needs go AND arm. go toggles every pass, arm stays
    # False: the state never changes but r_go follows go on every pass.
    rows = [T("1", "OFF", "ON", "go", "r_go", default="OFF", order=1),
            T("1", "OFF", "ON", "arm", "r_arm", order=2)]
    eng = engine_for(tmp_path, sms=[("S", rows)],
                     inputs=GO + [("arm", "bool", "False")])
    seen = []
    for k in range(200):
        eng.set_input("go", k % 2 == 0)
        eng.step()
        s = eng.snapshot()
        assert s["states"]["S"] == "OFF"
        seen.append(s["outputs"]["r_go"])
    assert seen == [k % 2 == 0 for k in range(200)]


@R("REQ-043", "REQ-113")
def test_item_evaluation_times_independent_of_other_bands(tmp_path, monkeypatch):
    """Adding bands changes the tick rate but not when (in ms) an item runs."""
    def run(path, extra):
        eqs = [E("x", "True", band=4)] + [E(f"n{b}", "True", band=b) for b in extra]
        eng = engine_for(path, equations=eqs)
        seen = count_passes(monkeypatch, eng)
        hz = eng._tick_hz
        eng.run(int(hz) * 5)
        return [Fraction(tk - 1) * 1000 / hz for tk in sorted(seen["x"])]

    a = run(tmp_path, [])
    (tmp_path / "b").mkdir()
    b = run(tmp_path / "b", [3, 7, 25])
    assert a == b == [Fraction(250 * k) for k in range(20)]
