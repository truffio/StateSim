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
        plant_step(eng, 0.1)            # one tick = 100 ms at 10 Hz
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



@R("REQ-145")
def test_autopilot2_appr_light_latches_from_descent_to_landed():
    eng = Engine(load_model(EXAMPLES / "autopilot2" / "master.csv"))

    def run(n=3, **inputs):
        for k, v in inputs.items():
            eng.set_input(k, v)
        eng.run(n)
        s = eng.snapshot()
        return s["states"]["state_ac"], s["outputs"]["appr_light"]

    run(1)
    eng.set_input("toga", True); run(1); eng.set_input("toga", False)
    run(ground_speed=30)
    run(fd_on=True, ap_on=True, radio_altitude=500)
    assert run(radio_altitude=2500) == ("Cruise", False)
    assert run(appr_selected=True) == ("Cruise", False)        # not in Descent: off
    run(appr_selected=False)
    assert run(radio_altitude=1400) == ("Descent", False)
    assert run(appr_selected=True) == ("Approach", True)       # APPR in Descent: on
    assert run(appr_selected=False) == ("Approach", True)      # stays on
    assert run(dmc_tracking_loc=True, dmc_tracking_gs=True) == ("Final Approach", True)
    assert run(radio_altitude=0, claws_req_flare=True, ground_time_gt_2s=True) == ("Landed", False)
    eng2 = Engine(eng._model)                                   # reset: start values
    assert eng2.snapshot()["outputs"]["appr_light"] is False


@R("REQ-154", "REQ-155", "REQ-157", "REQ-158")
def test_autopilot3_autoland_with_actions():
    """examples/autopilot3 (converted from the previous tool with its set_vars
    as actions), flown through a front-end session: buttons are pulses."""
    from statesim_server.session import Session
    s = Session(load_model(EXAMPLES / "autopilot3" / "master.csv"))

    def run(n=3, press=None, **inputs):
        if press:
            assert s.handle({"type": "press", "name": press}) is None
        for k, v in inputs.items():
            assert s.handle({"type": "set", "name": k, "value": v}) is None
        for _ in range(n):
            s.step()
        snap = s.engine.snapshot()
        return snap["states"], snap["inputs"], snap["outputs"]

    st, i, _ = run(press="TOGA")
    assert (st["state_ac"], st["state_fd"], st["state_at"]) == ("Takeoff", "FD-engaged", "Hold armed")
    assert i["fd_on"] and i["at_on"] and s.state()["lit"]["fd_on"]
    st, _, _ = run(ground_speed=130)
    assert st["state_at"] == "Hold"
    st, i, _ = run(radio_altitude=100)
    assert st["state_ac"] == "Climb"
    assert (i["ground_speed"], i["on_ground"]) == (0, False)          # set by the climb action
    st, i, _ = run(press="AP_btn")
    assert st["state_ap"] == "AP-engaged" and i["ap_on"]
    run(radio_altitude=2500)
    st, _, _ = run(radio_altitude=2000)
    assert st["state_ac"] == "Descent"
    st, i, _ = run(press="APPR_btn")
    assert st["state_ac"] == "APPR armed" and not i["appr_on"]
    st, i, _ = run(radio_altitude=1400, dmc_tracking_loc=True)
    assert (st["state_ac"], st["state_lat"], i["appr_on"]) == ("Approach", "preLocTrk", True)
    st, i, out = run(dmc_tracking_gs=True)
    assert (st["guidance_src"], st["state_ac"], st["state_lat"], st["state_vert"]) == \
        ("IFCC", "Final Approach", "LocTrk", "GsTrk")
    assert i["ifcc_in_control"] and not i["dmc_tracking_loc"] and not i["dmc_tracking_gs"]
    assert out["fma_vnav_engaged_1_gs"] and out["fma_tm_engaged_spd"]
    run(radio_altitude=700)
    st, _, _ = run(radio_altitude=40)
    assert (st["state_lat"], st["state_vert"]) == ("Rollout_Armed", "Flare_Armed")
    st, _, out = run(claws_req_flare=True)
    assert (st["state_ac"], st["state_vert"], st["state_at"]) == ("Greasing", "Flare_Active", "Retard")
    assert out["fma_tm_engaged_retard"]
    st, i, _ = run(radio_altitude=0)
    assert (st["state_ac"], st["state_lat"]) == ("Touchdown", "Rollout")
    assert (i["ground_speed"], i["on_ground"], i["rollout_active"]) == (140, True, True)
    st, i, _ = run(ground_time_gt_2s=True)
    assert (st["state_vert"], st["state_at"], i["claws_req_flare"]) == ("Nosedown", "Idle", False)
    st, _, _ = run(ground_speed=100)
    assert st["state_ac"] == "Landed"
    st, i, _ = run(1, ground_speed=20)                             # IFCC hands back to DMC
    assert st["guidance_src"] == "DMC" and i["ifcc_in_control_prev"] is True
    st, i, _ = run(1)                                              # one-pass pulse (during of DMC)
    assert i["ifcc_in_control_prev"] is False
    assert (st["state_lat"], st["state_vert"]) == ("No_Lateral_State", "No_Vertical_State")
    st, _, _ = run(ground_speed=0)
    assert st["state_ac"] == "Waiting TOGA"
