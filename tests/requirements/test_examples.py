"""The examples/ CSV sets used by the notebooks are part of the test suite."""

import sys
from pathlib import Path

import pytest

from statesim import Engine, ListTraceSink, load_model

R = pytest.mark.req
EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def ap():
    sys.path.insert(0, str(EXAMPLES / "autopilot"))
    try:
        from plant import plant_step
    finally:
        sys.path.pop(0)
    trace = ListTraceSink()
    eng = Engine(load_model(EXAMPLES / "autopilot" / "master.csv"), trace=trace)
    return eng, trace, plant_step


def pulse(eng, name):
    eng.set_input(name, True)
    eng.step()
    eng.set_input(name, False)


def fly(eng, plant_step, ticks):
    for _ in range(ticks):
        plant_step(eng, 0.05)
        eng.step()


@R("REQ-015", "REQ-016", "REQ-021", "REQ-109", "REQ-110")
def test_autopilot_climb_capture_hold(ap):
    eng, trace, plant_step = ap
    eng.step()
    pulse(eng, "ap_engage_pb")
    assert eng.snapshot()["states"]["AP"] == "VS"
    pulse(eng, "alt_arm_pb")
    assert eng.snapshot()["states"]["AP"] == "ALT_ARMED"
    modes = []
    for _ in range(2000):
        fly(eng, plant_step, 1)
        s = eng.snapshot()
        if s["states"]["AP"] != (modes[-1][0] if modes else "ALT_ARMED"):
            modes.append((s["states"]["AP"], s["inputs"]["alt"], s["outputs"]["fma_alt_star"]))
    assert [m[0] for m in modes] == ["ALT_CAP", "ALT_HOLD"]
    cap_alt, hold_alt = modes[0][1], modes[1][1]
    assert 9795 <= cap_alt <= 9805                 # 200 ft zone at 1500 fpm
    assert hold_alt >= 9980                        # within 20 ft
    assert modes[0][2] is True and modes[1][2] is False   # FMA same pass as the state


@R("REQ-021", "REQ-026", "REQ-032", "REQ-109", "REQ-110")
def test_autopilot_monitor_disconnect_and_interlock(ap):
    eng, trace, plant_step = ap
    eng.step()
    eng.set_input("alt", 10000.0)
    eng.step()
    pulse(eng, "ap_engage_pb")
    pulse(eng, "alt_arm_pb")                       # inhibited: already at alt
    assert eng.snapshot()["states"]["AP"] == "VS"
    eng.set_input("sel_alt", 12000.0)
    pulse(eng, "alt_arm_pb")
    eng.set_input("sel_alt", 10000.0)              # zone reached at once
    fly(eng, plant_step, 400)
    assert eng.snapshot()["states"]["AP"] == "ALT_HOLD"
    eng.set_input("alt", 9700.0)                   # 300 ft upset
    fly(eng, plant_step, 2)
    assert eng.snapshot()["outputs"]["mon_alt_dev"] is True
    fly(eng, plant_step, 400)
    assert eng.snapshot()["outputs"]["mon_alt_dev"] is False
    eng.set_input("hyd_ok", False)                 # global disconnect
    eng.step()
    s = eng.snapshot()
    assert s["states"]["AP"] == "DISC_WARN" and s["outputs"]["master_warning"] is True
    pulse(eng, "warn_ack_pb")
    pulse(eng, "ap_engage_pb")                     # interlock: no hydraulics
    s = eng.snapshot()
    assert s["states"]["AP"] == "OFF" and s["outputs"]["eng_ok"] is False
