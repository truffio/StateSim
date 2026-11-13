"""statesim_server.Session: model description, messages, pulses, reset."""

from pathlib import Path

import pytest

from statesim import load_model
from statesim_server import Session, describe_model
from statesim_server.__main__ import parser

R = pytest.mark.req
EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def ap2():
    return Session(load_model(EXAMPLES / "autopilot2" / "master.csv"))


@pytest.fixture
def ap1():
    return Session(load_model(EXAMPLES / "autopilot" / "master.csv"))


@R("REQ-119", "REQ-120", "REQ-124")
def test_describe_model_layout(ap2):
    d = describe_model(ap2.model)
    assert [m["name"] for m in d["machines"]] == \
        ["state_ac", "state_vert", "state_lat", "guidance_src", "state_at"]   # master row order
    ac = d["machines"][0]
    assert ac["states"][:3] == ["Waiting TOGA", "Takeoff", "Climb"]
    assert ac["next"]["Descent"] == ["Approach", "Go Around"]
    assert ac["global"] == ["Touchdown", "EDM"]
    assert [g["name"] for g in d["groups"]] == \
        ["Aircraft", "Stick and Throttle", "DMC and CLAWS requests", "CLAWS availability"]
    panel_inputs = {i["name"] for g in d["groups"] for i in g["inputs"]}
    assert not panel_inputs & {"fd_on", "ap_on", "appr_selected", "EDM", "spd_sel"}  # on the panel
    (fcp,) = d["panels"]
    assert fcp["name"] == "fcp" and "<button" in fcp["html"]
    assert fcp["inputs"]["fd_on"]["widget"] == "toggle"
    assert fcp["inputs"]["hdg_sel"] == {"widget": "knob", "label": "HDG", "min": 0, "max": 359,
                                        "step": 1}
    capa = d["groups"][0]["inputs"][2]
    assert capa["widget"] == "dropdown" and capa["choices"][-1] == "LAND3"
    assert d["groups"][0]["wide"] is True                 # holds sliders


@R("REQ-120")
def test_self_transitions_are_not_next_states(tmp_path):
    (tmp_path / "S.csv").write_text(
        "transition_id,current_state,next_state,default_state,equation,result_variable,rationale,title,order\n"
        "1,A,A,A,True,r1,,,1\n1b,A,B,,False,r2,,,2\n", encoding="utf-8")
    (tmp_path / "master.csv").write_text("file_name,type,order,band\nS.csv,state_machine,1,10\n",
                                         encoding="utf-8")
    d = describe_model(load_model(tmp_path / "master.csv"))
    assert d["machines"][0]["next"] == {"A": ["B"], "B": []}


@R("REQ-125")
def test_set_writes_valid_values(ap2):
    assert ap2.handle({"type": "set", "name": "radio_altitude", "value": 1500}) is None
    assert ap2.handle({"type": "set", "name": "capa", "value": "APPR2"}) is None
    assert ap2.handle({"type": "set", "name": "fd_on", "value": True}) is None
    i = ap2.state()["inputs"]
    assert (i["radio_altitude"], i["capa"], i["fd_on"]) == (1500, "APPR2", True)


@R("REQ-125")
@pytest.mark.parametrize("name, value", [
    ("radio_altitude", 3000), ("radio_altitude", -5), ("radio_altitude", 2.5),
    ("radio_altitude", "high"), ("radio_altitude", True), ("capa", "LAND9"),
    ("fd_on", 1), ("nope", True), ("toga", True),
])
def test_set_rejects_invalid_values(ap2, name, value):
    before = ap2.state()["inputs"]
    assert ap2.handle({"type": "set", "name": name, "value": value})
    assert ap2.state()["inputs"] == before


@R("REQ-126")
def test_press_holds_input_for_one_slowest_band_period(tmp_path):
    (tmp_path / "inputs.csv").write_text(
        "variable_name,type,default_value,widget\npb,bool,false,momentary\n", encoding="utf-8")
    (tmp_path / "equations.csv").write_text(
        "equation,explanation,rationale,result_variable,band,order\n"
        "pb,,,fast,20,1\npb,,,slow,5,1\n", encoding="utf-8")
    (tmp_path / "master.csv").write_text(
        "file_name,type,order\nequations.csv,equations,\ninputs.csv,inputs,\n", encoding="utf-8")
    s = Session(load_model(tmp_path / "master.csv"))
    assert s.pulse_ticks == 4                      # tick rate 20 Hz, slowest band 5 Hz
    s.step()
    assert s.handle({"type": "press", "name": "pb"}) is None
    held = []
    for _ in range(6):
        s.step()
        held.append(s.engine.snapshot()["outputs"]["fast"])
    assert held == [True, True, True, True, False, False]
    assert s.state()["inputs"]["pb"] is False
    assert s.handle({"type": "press", "name": "fast"})          # not a push-button


@R("REQ-127")
def test_lit_follows_its_variable_not_the_click(ap1):
    ap1.step()
    ap1.handle({"type": "set", "name": "on_ground", "value": True})
    ap1.handle({"type": "press", "name": "ap_engage_pb"})
    ap1.step(); ap1.step()
    assert ap1.state()["lit"]["ap_engaged"] is False           # engage refused on ground
    ap1.handle({"type": "set", "name": "on_ground", "value": False})
    ap1.handle({"type": "press", "name": "ap_engage_pb"})
    ap1.step(); ap1.step(); ap1.step()
    assert ap1.state()["lit"]["ap_engaged"] is True


@R("REQ-128", "REQ-129")
def test_mode_pause_resume_step(ap2):
    assert ap2.state()["mode"] == "realtime"
    assert ap2.handle({"type": "mode", "mode": "fast"}) is None and ap2.mode == "fast"
    assert ap2.handle({"type": "mode", "mode": "warp"})
    assert ap2.handle({"type": "step"})                          # not paused
    ap2.handle({"type": "pause"})
    assert ap2.state()["paused"] is True
    t0 = ap2.engine.tick
    assert ap2.handle({"type": "step"}) is None and ap2.engine.tick == t0 + 1
    ap2.handle({"type": "resume"})
    assert ap2.paused is False
    assert ap2.handle({"type": "bogus"})


@R("REQ-130")
def test_reset_keeps_model_mode_and_pause(ap2):
    ap2.handle({"type": "mode", "mode": "fast"})
    ap2.handle({"type": "pause"})
    ap2.handle({"type": "press", "name": "toga"})
    ap2.handle({"type": "step"})
    ap2.handle({"type": "set", "name": "radio_altitude", "value": 500})
    assert ap2.state()["states"]["state_ac"] == "Takeoff"
    ap2.handle({"type": "reset"})
    st = ap2.state()
    assert st["states"]["state_ac"] == "Waiting TOGA"
    assert st["inputs"]["radio_altitude"] == 0 and st["inputs"]["toga"] is False
    assert (st["mode"], st["paused"], ap2.engine.tick) == ("fast", True, 0)
    assert ap2.releases == {}


@R("REQ-134")
def test_server_listens_on_localhost_by_default():
    args = parser().parse_args(["m.csv"])
    assert args.host == "127.0.0.1" and args.port == 8765



@R("REQ-142")
def test_toggle_flips_its_input(ap2):
    assert ap2.state()["inputs"]["fd_on"] is False
    assert ap2.handle({"type": "toggle", "name": "fd_on"}) is None
    assert ap2.state()["inputs"]["fd_on"] is True
    ap2.step(); ap2.step()
    assert ap2.state()["inputs"]["fd_on"] is True              # stays on (not a pulse)
    assert ap2.handle({"type": "toggle", "name": "fd_on"}) is None
    assert ap2.state()["inputs"]["fd_on"] is False
    assert ap2.handle({"type": "toggle", "name": "EDM"})       # momentary, not a toggle
    assert ap2.handle({"type": "toggle", "name": "nope"})


@R("REQ-143", "REQ-144")
def test_knob_values_are_checked_and_shown(ap2):
    assert ap2.handle({"type": "set", "name": "hdg_sel", "value": 359}) is None
    assert ap2.handle({"type": "set", "name": "hdg_sel", "value": 360})      # no wrap
    assert ap2.handle({"type": "set", "name": "alt_sel", "value": 2.5})      # int only
    st = ap2.state()
    assert st["inputs"]["hdg_sel"] == 359 and isinstance(st["inputs"]["hdg_sel"], int)
    assert st["values"] == {"alt_sel": 15000, "hdg_sel": 359, "spd_sel": 250, "vs_sel": 0}


class _Sink:
    def __init__(self):
        self.events = []

    def emit(self, event):
        self.events.append(event)


def _press_toga(s):
    s.handle({"type": "press", "name": "toga"})
    for _ in range(50):
        s.step()


@R("REQ-172", "REQ-173")
def test_timeline_and_user_trace_both_receive_events():
    sink = _Sink()
    s = Session(load_model(EXAMPLES / "autopilot2" / "master.csv"), sink)
    _press_toga(s)
    assert sink.events
    assert any(i["k"] == "tr" for i in s.timeline.all())
    msg = s.timeline_message()
    assert msg["type"] == "timeline" and msg["gen"] == 1 and msg["items"] == s.timeline.all()
    st = s.state()
    assert st["gen"] == 1 and isinstance(st["t"], float) and "states" in st


@R("REQ-174")
def test_reset_starts_a_new_timeline_with_next_gen(ap2):
    _press_toga(ap2)
    old = ap2.timeline
    assert old.all()
    ap2.reset()
    assert ap2.timeline is not old and ap2.timeline.gen == 2
    assert ap2.state()["gen"] == 2
    assert ap2.timeline_message()["gen"] == 2
    items, _ = ap2.take_new_items()
    assert items == ap2.timeline.all()          # nothing carried over from gen 1


@R("REQ-173")
def test_take_new_items_returns_each_item_once_in_order(ap2):
    ap2.handle({"type": "press", "name": "toga"})
    ap2.step()
    first, too_many = ap2.take_new_items()
    assert not too_many and first
    assert ap2.take_new_items() == ([], False)
    for _ in range(50):
        ap2.step()
    second, _ = ap2.take_new_items()
    ids = [i["id"] for i in first + second]
    assert ids == [i["id"] for i in ap2.timeline.all()]
    assert ids == sorted(set(ids))


@R("REQ-175")
def test_too_many_items_flagged(ap2, monkeypatch):
    import statesim_server.session as mod
    monkeypatch.setattr(mod, "MAX_DELTA", 2)
    _press_toga(ap2)
    n = len(ap2.timeline.all())
    assert n > 2
    items, too_many = ap2.take_new_items()
    assert too_many and len(items) == n
    assert ap2.take_new_items() == ([], False)
