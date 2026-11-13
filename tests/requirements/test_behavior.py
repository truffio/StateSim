"""Use-case tests: ordering, equations, state machines, bands, inputs, outputs."""

import pytest

from statesim import Engine, EvaluationError, ListTraceSink, load_model

from .helpers import E, T, build, engine_for, outputs_over, states_over

R = pytest.mark.req
GO = [("go", "bool", "False")]


def sub(tmp_path, name):
    d = tmp_path / name
    d.mkdir()
    return d


# ------------------------------------------------------------------ master
@R("REQ-004")
def test_master_order_orders_state_machines(tmp_path):
    p = ("P", [T("1", "OFF", "ON", "True", "p_r", default="OFF")], 2)
    q = ("Q", [T("1", "OFF", "ON", 'P == "ON"', "q_r", default="OFF")], 1)
    eng = engine_for(tmp_path, sms=[p, q])
    assert states_over(eng, 2, "Q") == ["OFF", "ON"]  # Q ran before P

    q2 = ("Q", q[1], 3)
    eng = engine_for(sub(tmp_path, "b"), sms=[p, q2])
    assert states_over(eng, 1, "Q") == ["ON"]  # Q ran after P


@R("REQ-005")
def test_state_machines_and_equations_share_ordering_space(tmp_path):
    eng = engine_for(
        tmp_path,
        sms=[("S", [T("1", "OFF", "ON", "go", "s_r", default="OFF")], 2)],
        equations=[E("a_seen", 'S == "ON"', order=1), E("b_seen", 'S == "ON"', order=3)],
        inputs=GO, master_order="eq_first")
    eng.set_input("go", True)
    eng.step()
    out = eng.snapshot()["outputs"]
    assert out["a_seen"] is False and out["b_seen"] is True
    eng.step()
    assert eng.snapshot()["outputs"]["a_seen"] is True


# --------------------------------------------------------------- equations
@R("REQ-013", "REQ-038")
def test_boolean_expression_over_inputs(tmp_path):
    eng = engine_for(tmp_path, equations=[E("hi", "alt > 100 and not ap_off")],
                     inputs=[("alt", "int", "0"), ("ap_off", "bool", "False")])
    eng.step()
    assert eng.snapshot()["outputs"]["hi"] is False
    eng.set_input("alt", 150)
    eng.step()
    assert eng.snapshot()["outputs"]["hi"] is True
    eng.set_input("ap_off", True)
    eng.step()
    assert eng.snapshot()["outputs"]["hi"] is False


@R("REQ-014", "REQ-055", "REQ-036")
def test_standalone_equation_recomputed_every_pass(tmp_path):
    eng = engine_for(tmp_path, equations=[E("x", "go")], inputs=GO)
    assert outputs_over(eng, 1, "x") == [False]
    eng.set_input("go", True)
    assert outputs_over(eng, 1, "x") == [True]
    eng.set_input("go", False)
    assert outputs_over(eng, 1, "x") == [False]


@R("REQ-015", "REQ-016")
def test_equation_results_reused_by_name(tmp_path):
    eng = engine_for(
        tmp_path,
        equations=[E("base", "go", order=1), E("derived", "base and not stop", order=2)],
        sms=[("S", [T("1", "OFF", "ON", "derived", "s_r", default="OFF")], 3)],
        inputs=GO + [("stop", "bool", "False")])
    eng.set_input("go", True)
    eng.step()
    snap = eng.snapshot()
    assert snap["outputs"]["derived"] is True      # used by another equation
    assert snap["states"]["S"] == "ON"             # used by a state machine


@R("REQ-018", "REQ-090", "REQ-091")
def test_row_results_updated_every_evaluation(tmp_path):
    rows = [T("1", "OFF", "ON", "go", "r1", default="OFF"),
            T("2", "ON", "OFF", "stop", "r2")]
    eng = engine_for(tmp_path, sms=[("S", rows)], equations=[E("e", "go")],
                     inputs=GO + [("stop", "bool", "False")])
    eng.set_input("go", True)
    eng.step()
    s = eng.snapshot()
    assert s["states"]["S"] == "ON" and s["outputs"] == {"e": True, "r1": True, "r2": False}
    eng.set_input("go", False)
    eng.step()
    s = eng.snapshot()
    assert s["states"]["S"] == "ON"             # no exit transition enabled
    assert s["outputs"]["r1"] is False         # still recomputed while in ON


@R("REQ-019")
def test_all_rows_evaluated_without_short_circuit(tmp_path):
    rows = [T("1", "OFF", "ON", "False", "ra", default="OFF", order=1),
            T("1", "OFF", "ON", "go", "rb", order=2),
            T("2", "ON", "OFF", "go", "rc", order=3)]
    eng = engine_for(tmp_path, sms=[("S", rows)], inputs=GO)
    eng.set_input("go", True)
    eng.step()
    assert eng.snapshot()["outputs"] == {"ra": False, "rb": True, "rc": True}


@R("REQ-021")
def test_transition_rows_are_anded(tmp_path):
    rows = [T("1", "OFF", "ON", "a", "ra", default="OFF"), T("1", "OFF", "ON", "b", "rb")]
    eng = engine_for(tmp_path, sms=[("S", rows)],
                     inputs=[("a", "bool", "False"), ("b", "bool", "False")])
    eng.set_input("a", True)
    assert states_over(eng, 1, "S") == ["OFF"]
    eng.set_input("b", True)
    assert states_over(eng, 1, "S") == ["ON"]


@R("REQ-022", "REQ-020")
def test_transitions_with_different_row_counts(tmp_path):
    rows = [T("1", "A", "B", "x", "r1", default="A"),
            T("2", "B", "C", "x", "r2"), T("2", "B", "C", "y", "r3"), T("2", "B", "C", "z", "r4")]
    path = build(tmp_path, sms=[("S", rows)], inputs=[(n, "bool", "True") for n in "xyz"])
    model = load_model(path)
    assert [len(t.rows) for t in model.state_machines[0].transitions] == [1, 3]
    eng = Engine(model)
    assert states_over(eng, 2, "S") == ["B", "C"]


@R("REQ-023", "REQ-024")
def test_non_global_transition_needs_current_state(tmp_path):
    rows = [T("1", "OFF", "ON", "go", "r1", default="OFF"), T("2", "ON", "DONE", "fin", "r2")]
    eng = engine_for(tmp_path, sms=[("S", rows)], inputs=GO + [("fin", "bool", "False")])
    eng.set_input("fin", True)
    assert states_over(eng, 2, "S") == ["OFF", "OFF"]   # fin true but not in ON
    eng.set_input("go", True)
    assert states_over(eng, 2, "S") == ["ON", "DONE"]


@R("REQ-026")
def test_global_transition_fires_from_any_state(tmp_path):
    rows = [T("1", "OFF", "ON", "go", "r1", default="OFF"), T("9", "", "RESET", "rst", "r9")]
    for start_on in (False, True):
        d = sub(tmp_path, str(start_on))
        eng = engine_for(d, sms=[("S", rows)], inputs=GO + [("rst", "bool", "False")])
        if start_on:
            eng.set_input("go", True)
            eng.step()
            assert eng.snapshot()["states"]["S"] == "ON"
        eng.set_input("rst", True)
        assert states_over(eng, 1, "S") == ["RESET"]


@R("REQ-027", "REQ-028")
def test_no_precedence_first_enabled_in_order_wins(tmp_path):
    def rows(g_order, t_order):
        return [T("T", "OFF", "LOCAL", "True", "r1", default="OFF", order=t_order),
                T("G", "", "GLOBAL", "True", "r2", order=g_order)]
    eng = engine_for(tmp_path, sms=[("S", rows(1, 2))])
    assert states_over(eng, 1, "S") == ["GLOBAL"]
    eng = engine_for(sub(tmp_path, "b"), sms=[("S", rows(2, 1))])
    assert states_over(eng, 1, "S") == ["LOCAL"]
    # row order in the file does not matter, only the order column
    eng = engine_for(sub(tmp_path, "c"), sms=[("S", list(reversed(rows(1, 2))))])
    assert states_over(eng, 1, "S") == ["GLOBAL"]


@R("REQ-056")
def test_at_most_one_state_change_per_pass(tmp_path):
    rows = [T("1", "A", "B", "True", "r1", default="A"), T("2", "B", "C", "True", "r2")]
    eng = engine_for(tmp_path, sms=[("S", rows)])
    assert states_over(eng, 3, "S") == ["B", "C", "C"]


@R("REQ-029", "REQ-089")
def test_state_machine_starts_in_default_state(tmp_path):
    eng = engine_for(tmp_path, sms=[("S", [T("1", "IDLE", "RUN", "go", "r1", default="IDLE")])],
                     inputs=GO)
    assert eng.snapshot()["states"] == {"S": "IDLE"}
    assert eng.snapshot()["tick"] == 0
    eng.step()
    assert eng.snapshot()["states"] == {"S": "IDLE"}


@R("REQ-034")
def test_state_machines_share_context(tmp_path):
    a = ("A", [T("1", "OFF", "ON", "go", "a_r", default="OFF")], 1)
    b = ("B", [T("1", "OFF", "ON", "a_r", "b_r", default="OFF")], 2)
    eng = engine_for(tmp_path, sms=[a, b], inputs=GO)
    eng.set_input("go", True)
    eng.step()
    assert eng.snapshot()["states"] == {"A": "ON", "B": "ON"}


@R("REQ-035")
def test_inputs_start_at_defaults(tmp_path):
    eng = engine_for(tmp_path, equations=[E("x", "True")],
                     inputs=[("i", "int", "5"), ("b", "bool", "True"), ("f", "float", "2.5")])
    inp = eng.snapshot()["inputs"]
    assert inp == {"b": True, "f": 2.5, "i": 5}
    assert type(inp["i"]) is int and type(inp["b"]) is bool


@R("REQ-036")
def test_set_input_visible_next_evaluation(tmp_path):
    eng = engine_for(tmp_path, equations=[E("x", "n >= 3")], inputs=[("n", "int", "0")])
    eng.step()
    eng.set_input("n", 3)
    assert eng.snapshot()["inputs"]["n"] == 3
    assert outputs_over(eng, 1, "x") == [True]


# ------------------------------------------------------------------- bands
def _bands(path, expr="tick >= 2"):
    return engine_for(path, equations=[E("a", expr, band=20), E("b", expr, band=30)])


@R("REQ-041", "REQ-042", "REQ-043", "REQ-044", "REQ-057")
def test_20hz_and_30hz_coexist(tmp_path):
    # tick_hz = 60: band 20 runs on ticks 1,4,7; band 30 on ticks 1,3,5,7
    assert outputs_over(_bands(tmp_path), 7, "a") == [False, False, False, True, True, True, True]
    eng = _bands(sub(tmp_path, "b"))
    assert outputs_over(eng, 7, "b") == [False, False, True, True, True, True, True]


@R("REQ-058")
def test_all_bands_run_on_first_step(tmp_path):
    # Per docs/decisions.md the first step() is tick 1 (t = 0 ms) and runs every band.
    eng = _bands(tmp_path, "tick == 1 and t == 0")
    eng.step()
    assert eng.snapshot()["outputs"] == {"a": True, "b": True}
    eng.step()  # tick 2: neither band due, values retained
    assert eng.snapshot()["outputs"] == {"a": True, "b": True}
    eng.step()  # tick 3: only band 30 recomputed
    assert eng.snapshot()["outputs"] == {"a": True, "b": False}
    eng.step()  # tick 4: band 20 recomputed
    assert eng.snapshot()["outputs"] == {"a": False, "b": False}


@R("REQ-041")
def test_non_multiple_and_fractional_bands(tmp_path):
    eng = engine_for(tmp_path, equations=[E("a", "tick >= 2", band=7),
                                          E("b", "tick >= 2", band="1/2")])
    eng.run(1)
    assert eng.snapshot()["outputs"] == {"a": False, "b": False}


@R("REQ-062")
def test_t_and_dt_available_in_equations(tmp_path):
    eng = engine_for(tmp_path, equations=[E("dt20", "dt * 20 == 1000", band=20),
                                          E("dt30", "dt * 30 == 1000", band=30),
                                          E("late", "t >= 500", band=20)])
    eng.step()
    o = eng.snapshot()["outputs"]
    assert o["dt20"] and o["dt30"] and not o["late"]


@R("REQ-061", "REQ-062")
def test_t_is_absolute_ms_and_dt_is_period_ms(tmp_path):
    eng = engine_for(tmp_path, equations=[E("t_ok", "t * 30 == (tick - 1) * 1000", band=10),
                                          E("dt_ok", "dt * 3 == 1000", band=3)])
    for _ in range(7):
        eng.step()
        o = eng.snapshot()["outputs"]
        assert o["t_ok"] is True
        assert eng.snapshot()["t"] == pytest.approx((eng.tick - 1) * 1000 / 30)
    # dt_ok is also true on the 3 Hz item's first run (ideal delta, not 0)
    assert o["dt_ok"] is True


@R("REQ-064")
def test_timer_expressed_with_t(tmp_path):
    rows = [T("1", "WAIT", "DONE", "t >= 500", "r1", default="WAIT")]
    eng = engine_for(tmp_path, sms=[("S", rows)])  # 10 Hz: t = (tick - 1) * 100 ms
    assert states_over(eng, 7, "S") == ["WAIT"] * 5 + ["DONE"] * 2


@R("REQ-064", "REQ-061")
def test_timer_time_independent_of_other_bands(tmp_path):
    """`t >= 2000` on a 1 Hz equation fires at the same simulation time whether
    or not an unrelated 20 Hz band exists (t is absolute ms, not tick-derived
    from the LCM rate)."""
    def first_true_time(path, extra):
        eqs = [E("timer", "t >= 2000", band=1)]
        if extra:
            eqs.append(E("noise", "True", band=20))
        eng = engine_for(path, equations=eqs)
        for _ in range(200):
            eng.step()
            if eng.snapshot()["outputs"]["timer"]:
                return eng.t
        raise AssertionError("timer never fired")

    alone = first_true_time(sub(tmp_path, "a"), False)
    with_20 = first_true_time(sub(tmp_path, "b"), True)
    assert alone == with_20 == 2000


# --------------------------------------------------------------- execution
@R("REQ-013")
def test_comprehension_sees_context_names(tmp_path):
    eng = engine_for(tmp_path, equations=[E("big", "any(v > lim for v in [1, 2])"),
                                          E("fn", "(lambda q: q > lim)(2)")],
                     inputs=[("lim", "int", "1")])
    eng.step()
    assert eng.snapshot()["outputs"] == {"big": True, "fn": True}
    eng.set_input("lim", 5)
    eng.step()
    assert eng.snapshot()["outputs"] == {"big": False, "fn": False}
    assert "__builtins__" not in eng.snapshot()["inputs"]


@R("REQ-013")
def test_runtime_error_is_wrapped_with_location(tmp_path):
    rows = [T("1", "A", "B", "missing_name > 1", "r1", default="A")]
    eng = engine_for(tmp_path, sms=[("S", rows)])
    with pytest.raises(EvaluationError) as ei:
        eng.step()
    e = ei.value
    assert e.source == "S.csv:2" and e.tick == 1 and e.item == "S"
    assert isinstance(e.__cause__, NameError)
    assert "S.csv:2" in str(e) and "tick 1" in str(e)
    d = tmp_path / "eq"
    d.mkdir()
    eng = engine_for(d, equations=[E("ok", "True"), E("bad", "1 / zero", order=2)],
                     inputs=[("zero", "int", "0")])
    with pytest.raises(EvaluationError) as ei:
        eng.step()
    assert ei.value.source == "equations.csv:3" and ei.value.item == "bad"
    assert isinstance(ei.value.__cause__, ZeroDivisionError)


@R("REQ-031")
def test_global_self_transition_is_noop_that_wins_and_is_not_logged(tmp_path):
    sink = ListTraceSink()
    rows = [T("1", "", "A", "True", "g", default="A", order=1),     # global A -> A
            T("2", "A", "B", "True", "r", order=2)]                  # later, also enabled
    eng = engine_for(tmp_path, trace=sink, sms=[("S", rows)])
    assert states_over(eng, 3, "S") == ["A", "A", "A"]   # no-op won each pass
    assert eng.snapshot()["outputs"] == {"g": True, "r": True}
    assert not [e for e in sink.events if "A->" in e.action]  # no transition logged
    assert [e.action for e in sink.events] == ["g False->True", "r False->True"]


@R("REQ-031")
def test_non_global_self_transition_fires_and_is_logged(tmp_path):
    sink = ListTraceSink()
    rows = [T("1", "A", "A", "True", "r", default="A")]
    eng = engine_for(tmp_path, trace=sink, sms=[("S", rows)])
    eng.step()
    assert eng.snapshot()["states"]["S"] == "A"
    assert any(e.action.startswith("T1 A->A") for e in sink.events)


@R("REQ-049", "REQ-050", "REQ-052")
def test_later_item_sees_earlier_result_same_pass(tmp_path):
    # CSV lists the dependent first; the order column decides.
    eqs = [E("y", "x", order=2), E("x", "go", order=1)]
    eng = engine_for(tmp_path, equations=eqs, inputs=GO)
    eng.set_input("go", True)
    eng.step()
    assert eng.snapshot()["outputs"] == {"x": True, "y": True}


@R("REQ-051", "REQ-052")
def test_earlier_item_sees_previous_pass_value(tmp_path):
    eqs = [E("y", "x", order=1), E("x", "go", order=2)]  # y depends on x but runs first
    eng = engine_for(tmp_path, equations=eqs, inputs=GO)
    eng.set_input("go", True)
    eng.step()
    assert eng.snapshot()["outputs"] == {"x": True, "y": False}
    eng.step()
    assert eng.snapshot()["outputs"] == {"x": True, "y": True}


@R("REQ-109", "REQ-110")
def test_command_and_monitoring_layers_same_pass(tmp_path):
    cmd = ("CMD", [T("1", "OFF", "ENGAGED", "go", "cmd_r", default="OFF")], 1)
    eng = engine_for(tmp_path, sms=[cmd], equations=[E("mon", 'CMD == "ENGAGED"', order=2)],
                     inputs=GO)
    eng.set_input("go", True)
    eng.step()
    s = eng.snapshot()
    assert s["states"]["CMD"] == "ENGAGED" and s["outputs"]["mon"] is True


# ----------------------------------------------------------------- outputs
@R("REQ-085", "REQ-089", "REQ-090", "REQ-091")
def test_snapshot_contents(tmp_path):
    eng = engine_for(tmp_path, sms=[("S", [T("1", "A", "B", "go", "sr", default="A")])],
                     equations=[E("e", "go")], inputs=GO)
    snap = eng.snapshot()
    assert set(snap) >= {"tick", "t", "states", "outputs", "inputs"}
    assert snap["states"] == {"S": "A"}
    assert set(snap["outputs"]) == {"sr", "e"}
    assert snap["inputs"] == {"go": False} and snap["tick"] == 0 and snap["t"] == 0.0
    eng.set_input("go", True)
    eng.step()
    snap = eng.snapshot()
    assert snap["outputs"] == {"sr": True, "e": True} and snap["states"] == {"S": "B"}
    assert snap["tick"] == 1 and snap["t"] == 0.0
    eng.step()
    assert eng.snapshot()["t"] == 100.0  # float milliseconds


@R("REQ-092")
def test_snapshot_is_a_copy(tmp_path):
    eng = engine_for(tmp_path, sms=[("S", [T("1", "A", "B", "go", "sr", default="A")])], inputs=GO)
    snap = eng.snapshot()
    snap["states"]["S"] = "HACKED"
    snap["outputs"]["sr"] = "HACKED"
    snap["inputs"]["go"] = "HACKED"
    snap["tick"] = 99
    again = eng.snapshot()
    assert again["states"]["S"] == "A" and again["outputs"]["sr"] is False
    assert again["inputs"]["go"] is False and again["tick"] == 0
    assert again["states"] is not snap["states"]
    # values are deep-copied: mutating a mutable input value in a snapshot is harmless
    eng.set_input("go", [1, 2])
    s1 = eng.snapshot()
    s1["inputs"]["go"].append(3)
    assert eng.snapshot()["inputs"]["go"] == [1, 2]
    eng.set_input("go", True)
    eng.set_input("go", True)
    eng.step()
    assert eng.snapshot()["states"]["S"] == "B"


@R("REQ-093")
def test_set_input_unknown_name_raises_keyerror(tmp_path):
    eng = engine_for(tmp_path, equations=[E("e", "go")], inputs=GO)
    with pytest.raises(KeyError):
        eng.set_input("nope", 1)
    with pytest.raises(KeyError):
        eng.set_input("e", True)  # result variables are not inputs
