"""Logging and determinism requirement tests."""

from fractions import Fraction

import pytest

from statesim import Engine, FileTraceWriter, ListTraceSink, load_model

from .helpers import E, T, build

R = pytest.mark.req

SMS = [("AP", [T("3", "OFF", "ARMED", "ap_sw and alt > 500", "armed_r", default="OFF",
                 title="Arm"),
               T("4", "ARMED", "OFF", "not ap_sw", "off_r")])]
INPUTS = [("ap_sw", "bool", "False"), ("alt", "int", "0")]


def make(tmp_path, trace):
    model = load_model(build(tmp_path, sms=SMS, equations=[E("high", "alt > 500")],
                             inputs=INPUTS))
    return Engine(model, trace)


def script(eng):
    eng.step()
    eng.set_input("alt", 1000)
    eng.set_input("ap_sw", True)
    eng.run(3)
    eng.set_input("ap_sw", False)
    eng.run(3)


@R("REQ-094", "REQ-095", "REQ-096", "REQ-097", "REQ-098", "REQ-100")
def test_state_change_logged_with_context(tmp_path):
    sink = ListTraceSink()
    eng = make(tmp_path, sink)
    script(eng)
    changes = [e for e in sink.events if e.component == "AP" and "->" in e.action
               and e.action.startswith("T")]
    assert [c.action.split(" ")[1] for c in changes] == ["OFF->ARMED", "ARMED->OFF"]
    first = changes[0]
    assert first.tick == 2 and first.t == Fraction(2, 10)          # timestamp
    assert first.component == "AP"                                  # component name
    assert first.action == 'T3 OFF->ARMED "Arm"'                    # description
    assert dict(first.values) == {"alt": 1000, "ap_sw": True}       # triggering values
    assert list(first.values) == sorted(first.values)
    line = sink.lines()[sink.events.index(first)]
    assert line == 'tick=000002 t=0.200000 | AP | T3 OFF->ARMED "Arm" | alt=1000, ap_sw=True'


@R("REQ-094", "REQ-097")
def test_result_changes_and_set_input_logged(tmp_path):
    sink = ListTraceSink()
    eng = make(tmp_path, sink)
    eng.set_input("alt", 600)
    eng.step()
    comps = [(e.component, e.action) for e in sink.events]
    assert ("INPUT", "set alt 0->600") in comps
    assert ("EQ", "high False->True") in comps


@R("REQ-099")
def test_plain_text_log_file(tmp_path):
    log = tmp_path / "out.log"
    d = tmp_path / "m"
    d.mkdir()
    sink = ListTraceSink()
    with FileTraceWriter(log) as writer:
        script(make(d, writer))
    d2 = tmp_path / "m2"
    d2.mkdir()
    script(make(d2, sink))
    assert log.read_text(encoding="utf-8").splitlines() == sink.lines()
    assert sink.lines()


def _run_twice(tmp_path):
    results = []
    for name in ("one", "two"):
        d = tmp_path / name
        d.mkdir()
        sink = ListTraceSink()
        eng = make(d, sink)
        snaps = []
        for i in range(12):
            if i == 2:
                eng.set_input("alt", 1000)
                eng.set_input("ap_sw", True)
            if i == 8:
                eng.set_input("ap_sw", False)
            eng.step()
            snaps.append(eng.snapshot())
        results.append((snaps, sink.lines()))
    return results


@R("REQ-101")
def test_identical_runs_identical_snapshots(tmp_path):
    (s1, _), (s2, _) = _run_twice(tmp_path)
    assert s1 == s2


@R("REQ-102")
def test_identical_runs_identical_logs(tmp_path):
    (_, l1), (_, l2) = _run_twice(tmp_path)
    assert l1 == l2 and len(l1) > 3
