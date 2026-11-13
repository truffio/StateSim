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


# ---- timeline: the cause chain on the real examples (Session + Timeline) ----

def _session(example):
    from statesim_server.session import Session
    return Session(load_model(EXAMPLES / example / "master.csv"))


def _press(s, name):
    """A push-button pulse as the UI does it: the engine sees it for one pass."""
    assert s.handle({"type": "press", "name": name}) is None
    s.step()


def _run(s, n):
    for _ in range(n):
        s.step()


def _find(items, **kw):
    out = [i for i in items if all(i.get(k) == v for k, v in kw.items())]
    assert len(out) == 1, (kw, out)
    return out[0]


def _autopilot3_scenario():
    """AP_btn pressed first on autopilot3, then ten more passes."""
    s = _session("autopilot3")
    s.step()
    _press(s, "AP_btn")
    _run(s, 10)
    return s.timeline.all()


@R("REQ-166", "REQ-168", "REQ-169")
def test_timeline_autopilot3_ap_press_engages_ap_then_fd_through_ap_on():
    items = _autopilot3_scenario()
    btn = _find(items, k="in", name="AP_btn", value=True)
    ap = _find(items, k="tr", sm="state_ap", tid="T1")
    fd = _find(items, k="tr", sm="state_fd", tid="T2")      # FD engaged by the AP, not by FD_btn/TOGA
    assert btn["id"] < ap["id"] < fd["id"]
    assert ap["causes"] == [btn["id"]]                      # the AP_btn input item
    assert ap["writes"] == [["ap_on", True]]                # entry action STATE_AP_T1
    assert fd["causes"] == [ap["id"]]                       # read ap_on, written by the AP transition
    assert fd["writes"] == [["fd_on", True]]
    # Vertical and Lateral leave their start states because the AP engaged
    for sm, to in (("state_vert", "No_Vertical_State"), ("state_lat", "No_Lateral_State")):
        tr = _find(items, k="tr", sm=sm, tid="T1")
        assert (tr["to"], tr["causes"]) == (to, [ap["id"]])


@R("REQ-166", "REQ-168", "REQ-169")
def test_timeline_autopilot3_toga_engages_fd_and_unlocks_vertical_lateral():
    s = _session("autopilot3")
    s.step()
    _press(s, "TOGA")
    _run(s, 5)
    items = s.timeline.all()
    toga = _find(items, k="in", name="TOGA", value=True)
    assert _find(items, k="tr", sm="state_ac", tid="T1")["causes"] == [toga["id"]]
    fd = _find(items, k="tr", sm="state_fd", tid="T3")      # FD already on from TOGA ...
    assert fd["causes"] == [toga["id"]] and fd["writes"] == [["fd_on", True]]
    for sm in ("state_vert", "state_lat"):                  # ... so those leave their start state by it
        assert _find(items, k="tr", sm=sm, tid="T1")["causes"] == [fd["id"]]
    _press(s, "AP_btn")                                     # AP press later: AP engages, FD does not move again
    _run(s, 5)
    items = s.timeline.all()
    btn = _find(items, k="in", name="AP_btn", value=True)
    ap = _find(items, k="tr", sm="state_ap", tid="T1")
    assert ap["causes"] == [btn["id"]]
    assert [i for i in items if i["k"] == "tr" and i["sm"] == "state_fd"] == [fd]


@R("REQ-167", "REQ-166")
def test_timeline_same_value_input_gives_no_item():
    s = _session("autopilot3")
    s.step()
    s.handle({"type": "set", "name": "capa", "value": "LAND3"})     # already its default
    s.step()
    assert s.timeline.all() == []
    s.handle({"type": "set", "name": "capa", "value": "APPR1"})
    s.step()
    assert [(i["k"], i["name"], i["value"]) for i in s.timeline.all()] == [("in", "capa", "APPR1")]


@R("REQ-161", "REQ-166")
def test_timeline_self_driven_transition_has_no_causes():
    s = _session("actions")                    # T3 reads climb_ticks, counted by the machine's own during action
    s.step()
    _press(s, "toga")
    s.handle({"type": "set", "name": "radio_altitude", "value": 500})
    _run(s, 60)
    items = s.timeline.all()
    t1 = _find(items, k="tr", sm="phase", tid="T1")
    t2 = _find(items, k="tr", sm="phase", tid="T2")
    t3 = _find(items, k="tr", sm="phase", tid="T3")
    assert t1["id"] < t2["id"] < t3["id"]
    assert t1["causes"] != [] and t2["causes"] != []        # the driven ones are caused by inputs
    assert t3["causes"] == []                  # nothing outside the machine changed: 5 s of climb
    assert t2["writes"] == [["ground_speed", 0]]            # climb_ticks = 0 changes nothing: no write
    assert not any(i["k"] == "in" and i["name"] == "climb_ticks" for i in items)   # during writes: no item


@R("REQ-161", "REQ-162", "REQ-163")
def test_timeline_timer_only_transition_has_no_causes(tmp_path):
    (tmp_path / "M.csv").write_text(
        "transition_id,current_state,next_state,default_state,equation,result_variable,rationale,title,order\n"
        "T1,Idle,Done,Idle,t >= 500,m_t1_1,,Timer elapsed,1\n", encoding="utf-8")
    (tmp_path / "inputs.csv").write_text("variable_name,type,default_value\nx,int,0\n", encoding="utf-8")
    (tmp_path / "master.csv").write_text(
        "file_name,type,order,band,name\nM.csv,state_machine,1,10,M\ninputs.csv,inputs,,,\n", encoding="utf-8")
    from statesim_server.session import Session
    s = Session(load_model(tmp_path / "master.csv"))
    _run(s, 10)
    tr = _find(s.timeline.all(), k="tr", sm="M", tid="T1")
    assert (tr["from"], tr["to"], tr["causes"]) == ("Idle", "Done", [])


@R("REQ-166")
def test_timeline_same_scenario_twice_gives_identical_items():
    a, b = _autopilot3_scenario(), _autopilot3_scenario()
    assert a == b and len(a) >= 6
    assert [i["id"] for i in a] == list(range(1, len(a) + 1))       # sequential ids


@R("REQ-172", "REQ-173", "REQ-174")
def test_session_hands_out_each_item_once_and_reset_starts_a_new_gen():
    s = _session("autopilot3")
    s.step()
    _press(s, "AP_btn")
    _run(s, 5)
    items, too_many = s.take_new_items()
    assert items == s.timeline.all() and not too_many
    assert s.take_new_items() == ([], False)                        # nothing twice
    msg = s.timeline_message()
    assert (msg["type"], msg["gen"], msg["items"]) == ("timeline", 1, items)
    assert s.state()["gen"] == 1 and s.state()["t"] == s.engine.snapshot()["t"]
    s.handle({"type": "reset"})
    assert s.timeline_message() == {"type": "timeline", "gen": 2, "items": []}
    assert s.state()["gen"] == 2
