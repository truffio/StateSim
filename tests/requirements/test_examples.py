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


@R("REQ-015", "REQ-021", "REQ-026", "REQ-028")
def test_autopilot2_a220_autoland_sequence():
    eng = Engine(load_model(EXAMPLES / "autopilot2" / "master.csv"))

    def run(n=3, **inputs):
        for k, v in inputs.items():
            eng.set_input(k, v)
        eng.run(n)
        return eng.snapshot()["states"]

    assert run(1)["state_ac"] == "Waiting TOGA"
    run(2, toga=True)
    assert run(1, toga=False)["state_ac"] == "Takeoff"
    assert run(ground_speed=30)["state_at"] == "Active"
    s = run(fd_on=True, ap_on=True, radio_altitude=500)
    assert (s["state_ac"], s["state_vert"], s["state_lat"]) == ("Climb", "No_Vertical_State", "No_Lateral_State")
    assert run(radio_altitude=2500)["state_ac"] == "Cruise"
    assert run(radio_altitude=1400)["state_ac"] == "Descent"
    assert run(appr_selected=True)["state_ac"] == "Approach"
    s = run(dmc_tracking_loc=True, dmc_tracking_gs=True)
    assert (s["guidance_src"], s["state_lat"], s["state_vert"], s["state_ac"]) == \
        ("IFCC", "LocTrk", "GsTrk", "Final Approach")
    assert run(radio_altitude=700)["state_lat"] == "Align_Armed"
    s = run(radio_altitude=150)
    assert (s["state_lat"], s["state_vert"]) == ("Align", "Flare_Armed")
    s = run(radio_altitude=40)
    assert (s["state_lat"], s["state_at"]) == ("Rollout_Armed", "Retard")
    assert run(radio_altitude=0)["state_lat"] == "Rollout"
    s = run(claws_req_flare=True)
    assert (s["state_vert"], s["state_ac"]) == ("Flare_Active", "Touchdown")   # via Greasing
    s = run(ground_time_gt_2s=True)
    assert (s["state_vert"], s["state_ac"], s["state_at"]) == ("Nosedown", "Landed", "Idle")
    s = run(ground_speed=20)
    assert s["guidance_src"] == "DMC" and s["state_vert"] != "Nosedown"
