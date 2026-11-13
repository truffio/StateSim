"""Unit tests for statesim.loader (CSVs built inline with tmp_path)."""

from __future__ import annotations

from fractions import Fraction

import pytest

from statesim import constants
from statesim.errors import ModelError
from statesim.loader import load_model

SM_HDR = "transition_id,current_state,next_state,default_state,equation,result_variable,rationale,title,band,order\n"
EQ_HDR = "equation,explanation,rationale,result_variable,band,order\n"
IN_HDR = "variable_name,type,default_value\n"

GOOD_SM = SM_HDR + (
    "1,OFF,ARMED,OFF,ap_sw,r1,why,Arm,20,2\n"
    "1,OFF,ARMED,,alt > 5,r2,why,,20,1\n"
    "2,,OFF,,not ap_sw,r3,why,Reset,20,0\n"
    "10,ARMED,ENGAGED,,ok,r4,,,20,5\n"
    "3,ARMED,ENGAGED,,ok2,r5,,,20,5\n"
)


# State machine files are written in SM_HDR form (with a band column) for
# readability; write() moves the band to _BANDS and master() puts it in the
# master CSV, where the loader expects it.
_BANDS: dict[tuple[str, str], str] = {}


def write(tmp_path, name, text):
    if text.startswith(SM_HDR):
        lines = text.split("\n")
        cells = [ln.split(",") for ln in lines[1:] if ln]
        if cells:
            _BANDS[(str(tmp_path), name)] = cells[0][8]
        text = "\n".join(",".join(c[:8] + c[9:]) for c in [lines[0].split(",")] + cells) + "\n"
    (tmp_path / name).write_text(text, encoding="utf-8")


def master(tmp_path, rows, text=None):
    def with_band(r):
        f = r.split(",")
        if len(f) == 3 and f[1] == "state_machine":
            f.append(_BANDS.get((str(tmp_path), f[0]), "20"))
        return ",".join(f)
    body = "file_name,type,order,band\n" + "".join(with_band(r) + "\n" for r in rows)
    write(tmp_path, "master.csv", text if text is not None else body)
    return tmp_path / "master.csv"


def err(tmp_path, m=None):
    with pytest.raises(ModelError) as ei:
        load_model(m or tmp_path / "master.csv")
    return ei.value


def sm_model(tmp_path, sm_text, name="AP.csv"):
    write(tmp_path, name, sm_text)
    return master(tmp_path, [f"{name},state_machine,1"])


def test_full_model(tmp_path):
    write(tmp_path, "AP.csv", GOOD_SM)
    write(tmp_path, "eq.csv", EQ_HDR + "a and b,expl,rat,x,30,1\n,,,,,\ny > 1,,,z,0.5,3/2\n")
    write(tmp_path, "in.csv", IN_HDR + "alt,int,1000\nap_sw,bool,True\nname,str,hello\nf,str,\n")
    m = master(tmp_path, ["AP.csv,state_machine,2", "eq.csv,equations,", "in.csv,inputs,"])
    model = load_model(m)
    assert model.master_path == str(m)
    sm = model.state_machines[0]
    assert sm.name == "AP" and sm.default_state == "OFF"
    assert sm.band_hz == 20 and sm.master_order == 2
    assert sm.states == ("OFF", "ARMED", "ENGAGED")
    assert sm.source == "master.csv:2"
    # sorted by (order, id): T2(0), T1(min 1), T3(5, numeric 3<10), T10
    assert [t.id for t in sm.transitions] == ["2", "1", "3", "10"]
    t2, t1 = sm.transitions[0], sm.transitions[1]
    assert t2.current_state is None and t2.next_state == "OFF"
    assert t1.current_state == "OFF" and t1.title == "Arm"
    assert [r.result_variable for r in t1.rows] == ["r2", "r1"]
    assert t1.rows[0].source == "AP.csv:3"
    assert [e.result_variable for e in model.equations] == ["x", "z"]
    assert model.equations[1].band_hz == Fraction(1, 2)
    assert model.equations[1].order == Fraction(3, 2)
    assert model.equations[0].explanation == "expl"
    assert model.equations[0].source == "eq.csv:2"
    assert model.equations[1].source == "eq.csv:4"  # blank row skipped
    d = {i.name: i for i in model.inputs}
    assert d["alt"].default == 1000 and d["alt"].type_name == "int"
    assert d["ap_sw"].default is True
    assert d["name"].default == "hello"
    assert d["f"].default == ""
    # LCM of 20, 30, 1/2 = 60
    assert model.tick_hz == 60


def test_no_equations_or_inputs_rows(tmp_path):
    m = sm_model(tmp_path, GOOD_SM)
    model = load_model(m)
    assert model.equations == () and model.inputs == ()
    assert model.tick_hz == 20


def test_empty_master_gives_tick_1(tmp_path):
    m = master(tmp_path, [])
    model = load_model(m)
    assert model.state_machines == () and model.tick_hz == 1


def test_bom_whitespace_and_extra_columns_crlf(tmp_path):
    text = (
        "﻿transition_id , current_state,next_state,default_state,equation,"
        "result_variable,rationale,title,order,extra\r\n"
        " 1 , OFF , ON , OFF , a , r1 ,,, 1 ,zzz\r\n"
    )
    (tmp_path / "S.csv").write_bytes(text.encode("utf-8"))
    (tmp_path / "master.csv").write_bytes(
        "﻿file_name,type,order,band\r\nS.csv,state_machine,1, 10 \r\n".encode("utf-8")
    )
    model = load_model(tmp_path / "master.csv")
    sm = model.state_machines[0]
    assert sm.default_state == "OFF" and sm.transitions[0].id == "1"
    assert sm.transitions[0].current_state == "OFF"


def test_master_order_and_fraction_orders(tmp_path):
    write(tmp_path, "B.csv", GOOD_SM)
    write(tmp_path, "A.csv", GOOD_SM.replace(",r1,", ",q1,").replace(",r2,", ",q2,").replace(",r3,", ",q3,").replace(",r4,", ",q4,").replace(",r5,", ",q5,"))
    m = master(tmp_path, ["B.csv,state_machine,1/2", "A.csv,state_machine,0.25"])
    model = load_model(m)
    assert [s.name for s in model.state_machines] == ["B", "A"]
    assert [s.master_order for s in model.state_machines] == [Fraction(1, 2), Fraction(1, 4)]


def test_paths_relative_to_master_dir(tmp_path):
    sub = tmp_path / "cfg"
    sub.mkdir()
    write(sub, "AP.csv", GOOD_SM)
    (sub / "m.csv").write_text("file_name,type,order,band\nAP.csv,state_machine,1,20\n",
                               encoding="utf-8")
    assert load_model(str(sub / "m.csv")).state_machines[0].name == "AP"


def test_input_default_parsing(tmp_path):
    lines = ["a,float,1.5", "b,str,'q'", "c,str,[1; 2]", "d,int,-3", "e,str,abc",
             "f,bool,false", "g,bool,TRUE", "h,bool,1", "i,bool,0", "j,bool,False", "k,str,"]
    write(tmp_path, "in.csv", IN_HDR + "\n".join(lines) + "\n")
    m = master(tmp_path, ["in.csv,inputs,"])
    d = {i.name: i.default for i in load_model(m).inputs}
    assert d == {"a": 1.5, "b": "'q'", "c": "[1; 2]", "d": -3, "e": "abc", "f": False,
                 "g": True, "h": True, "i": False, "j": False, "k": ""}
    assert type(d["f"]) is bool and type(d["d"]) is int and type(d["a"]) is float


@pytest.mark.parametrize("row", [
    "a,bool,maybe", "a,bool,", "a,int,1.5", "a,int,x", "a,float,abc", "a,float,",
    "a,list,[1]", "a,,1", "a,Int,1",
])
def test_input_default_bad_value_or_type(tmp_path, row):
    write(tmp_path, "in.csv", IN_HDR + "ok,int,1" + chr(10) + row + chr(10))
    m = master(tmp_path, ["in.csv,inputs,"])
    e = err(tmp_path, m)
    assert e.source == "in.csv:3"


# ---------------------------------------------------------------- errors


def test_master_missing_column(tmp_path):
    m = master(tmp_path, [], text="file_name,order\n")
    e = err(tmp_path, m)
    assert e.source == "master.csv:1" and "type" in e.msg


def test_empty_master_file(tmp_path):
    m = master(tmp_path, [], text="")
    assert err(tmp_path, m).source == "master.csv:1"


def test_unknown_type(tmp_path):
    m = master(tmp_path, ["x.csv,bogus,1"])
    assert err(tmp_path, m).source == "master.csv:2"


def test_sm_row_requires_order(tmp_path):
    write(tmp_path, "AP.csv", GOOD_SM)
    m = master(tmp_path, ["AP.csv,state_machine,"])
    assert err(tmp_path, m).source == "master.csv:2"
    m = master(tmp_path, ["AP.csv,state_machine,abc"])
    assert err(tmp_path, m).source == "master.csv:2"


def test_missing_listed_file(tmp_path):
    m = master(tmp_path, ["nope.csv,state_machine,1"])
    e = err(tmp_path, m)
    assert e.source == "master.csv:2" and "nope.csv" in e.msg


def test_two_equations_rows(tmp_path):
    write(tmp_path, "e1.csv", EQ_HDR)
    write(tmp_path, "e2.csv", EQ_HDR)
    m = master(tmp_path, ["e1.csv,equations,", "e2.csv,equations,"])
    assert err(tmp_path, m).source == "master.csv:3"


def test_two_inputs_rows(tmp_path):
    write(tmp_path, "i1.csv", IN_HDR)
    write(tmp_path, "i2.csv", IN_HDR)
    m = master(tmp_path, ["i1.csv,inputs,", "i2.csv,inputs,"])
    assert err(tmp_path, m).source == "master.csv:3"


def test_duplicate_sm_name(tmp_path):
    write(tmp_path, "AP.csv", GOOD_SM)
    (tmp_path / "sub").mkdir()
    write(tmp_path, "sub/AP.csv", GOOD_SM)
    m = master(tmp_path, ["AP.csv,state_machine,1", "sub/AP.csv,state_machine,2"])
    e = err(tmp_path, m)
    assert e.source == "master.csv:3" and "AP" in e.msg


def test_missing_sm_column(tmp_path):
    m = sm_model(tmp_path, "transition_id,current_state\n1,A\n")
    e = err(tmp_path, m)
    assert e.source == "AP.csv:1" and "next_state" in e.msg


def test_missing_equations_and_inputs_column(tmp_path):
    write(tmp_path, "eq.csv", "equation,result_variable\n")
    m = master(tmp_path, ["eq.csv,equations,"])
    assert err(tmp_path, m).source == "eq.csv:1"
    write(tmp_path, "in.csv", "variable_name,type\n")
    m = master(tmp_path, ["in.csv,inputs,"])
    assert err(tmp_path, m).source == "in.csv:1"


def test_syntax_error_in_sm_equation(tmp_path):
    bad = GOOD_SM.replace("alt > 5", "alt >")
    e = err(tmp_path, sm_model(tmp_path, bad))
    assert e.source == "AP.csv:3" and "alt >" in e.msg


def test_syntax_error_in_standalone_equation(tmp_path):
    write(tmp_path, "eq.csv", EQ_HDR + "a and b,,,x,10,1\n(a,,,y,10,2\n")
    m = master(tmp_path, ["eq.csv,equations,"])
    assert err(tmp_path, m).source == "eq.csv:3"


def test_statement_not_expression_is_error(tmp_path):
    write(tmp_path, "eq.csv", EQ_HDR + "x = 1,,,y,10,1\n")
    m = master(tmp_path, ["eq.csv,equations,"])
    assert err(tmp_path, m).source == "eq.csv:2"


def test_empty_equation_and_result_variable(tmp_path):
    write(tmp_path, "eq.csv", EQ_HDR + ",,,y,10,1\n")
    assert err(tmp_path, master(tmp_path, ["eq.csv,equations,"])).source == "eq.csv:2"
    write(tmp_path, "eq.csv", EQ_HDR + "a,,,,10,1\n")
    assert err(tmp_path, master(tmp_path, ["eq.csv,equations,"])).source == "eq.csv:2"


def test_transition_id_disagreement(tmp_path):
    bad = SM_HDR + (
        "1,OFF,ARMED,OFF,a,r1,,,20,1\n"
        "1,OFF,ENGAGED,,b,r2,,,20,2\n"
    )
    e = err(tmp_path, sm_model(tmp_path, bad))
    assert e.source == "AP.csv:3" and "duplicate transition_id" in e.msg
    bad = SM_HDR + (
        "1,OFF,ARMED,OFF,a,r1,,,20,1\n"
        "1,ARMED,ARMED,,b,r2,,,20,2\n"
    )
    assert err(tmp_path, sm_model(tmp_path, bad)).source == "AP.csv:3"


def test_empty_transition_id_and_next_state(tmp_path):
    bad = SM_HDR + ",OFF,ON,OFF,a,r1,,,20,1\n"
    assert err(tmp_path, sm_model(tmp_path, bad)).source == "AP.csv:2"
    bad = SM_HDR + "1,OFF,,OFF,a,r1,,,20,1\n"
    assert err(tmp_path, sm_model(tmp_path, bad)).source == "AP.csv:2"


def test_unknown_state(tmp_path):
    bad = SM_HDR + (
        "1,OFF,ON,OFF,a,r1,,,20,1\n"
        "2,GHOST,OFF,,b,r2,,,20,2\n"
    )
    e = err(tmp_path, sm_model(tmp_path, bad))
    assert e.source == "AP.csv:3" and "GHOST" in e.msg


def test_global_transition_does_not_need_current_state(tmp_path):
    ok = SM_HDR + "1,,ON,OFF,a,r1,,,20,1\n"
    assert load_model(sm_model(tmp_path, ok)).state_machines[0].states == ("OFF", "ON")


def test_no_default_state(tmp_path):
    bad = SM_HDR + "1,OFF,ON,,a,r1,,,20,1\n"
    assert err(tmp_path, sm_model(tmp_path, bad)).source == "AP.csv:1"


def test_empty_sm_file_fails(tmp_path):
    assert err(tmp_path, sm_model(tmp_path, SM_HDR)).source == "AP.csv:1"


def test_two_default_states(tmp_path):
    bad = SM_HDR + (
        "1,OFF,ON,OFF,a,r1,,,20,1\n"
        "2,ON,OFF,ON,b,r2,,,20,2\n"
    )
    assert err(tmp_path, sm_model(tmp_path, bad)).source == "AP.csv:3"


def test_band_column_in_sm_file_is_rejected(tmp_path):
    (tmp_path / "AP.csv").write_text(SM_HDR + "1,OFF,ON,OFF,a,r1,,,20,1\n", encoding="utf-8")
    e = err(tmp_path, master(tmp_path, ["AP.csv,state_machine,1,20"]))
    assert e.source == "AP.csv:1" and "master CSV" in str(e)


def test_sm_band_comes_from_master(tmp_path):
    write(tmp_path, "AP.csv", GOOD_SM)
    m = master(tmp_path, ["AP.csv,state_machine,1,7.5"])
    assert load_model(m).state_machines[0].band_hz == Fraction(15, 2)


@pytest.mark.parametrize("band", ["0", "-5", "abc", "", "1/0"])
def test_bad_band(tmp_path, band):
    write(tmp_path, "AP.csv", SM_HDR + "1,OFF,ON,OFF,a,r1,,,20,1\n")
    e = err(tmp_path, master(tmp_path, [f"AP.csv,state_machine,1,{band}"]))
    assert e.source == "master.csv:2"


def test_bad_band_standalone_and_bad_order(tmp_path):
    write(tmp_path, "eq.csv", EQ_HDR + "a,,,x,0,1\n")
    assert err(tmp_path, master(tmp_path, ["eq.csv,equations,"])).source == "eq.csv:2"
    write(tmp_path, "eq.csv", EQ_HDR + "a,,,x,10,first\n")
    assert err(tmp_path, master(tmp_path, ["eq.csv,equations,"])).source == "eq.csv:2"
    write(tmp_path, "eq.csv", EQ_HDR + "a,,,x,10,\n")
    assert err(tmp_path, master(tmp_path, ["eq.csv,equations,"])).source == "eq.csv:2"


@pytest.mark.parametrize("name", ["tick", "t", "dt", "1abc", "a b", "a-b"])
def test_bad_result_variable_names(tmp_path, name):
    write(tmp_path, "eq.csv", EQ_HDR + f"a,,,{name},10,1\n")
    e = err(tmp_path, master(tmp_path, ["eq.csv,equations,"]))
    assert e.source == "eq.csv:2"


@pytest.mark.parametrize("name", ["tick", "t", "dt", "9x", "a b"])
def test_bad_input_names(tmp_path, name):
    write(tmp_path, "in.csv", IN_HDR + f"{name},int,0\n")
    e = err(tmp_path, master(tmp_path, ["in.csv,inputs,"]))
    assert e.source == "in.csv:2"


def test_duplicate_result_variable_across_files(tmp_path):
    write(tmp_path, "AP.csv", GOOD_SM)
    write(tmp_path, "eq.csv", EQ_HDR + "a,,,r3,10,1\n")
    m = master(tmp_path, ["AP.csv,state_machine,1", "eq.csv,equations,"])
    e = err(tmp_path, m)
    assert e.source == "eq.csv:2" and "r3" in e.msg


def test_duplicate_result_variable_within_equations(tmp_path):
    write(tmp_path, "eq.csv", EQ_HDR + "a,,,x,10,1\nb,,,x,10,2\n")
    assert err(tmp_path, master(tmp_path, ["eq.csv,equations,"])).source == "eq.csv:3"


def test_duplicate_result_variable_within_sm(tmp_path):
    bad = SM_HDR + (
        "1,OFF,ON,OFF,a,r1,,,20,1\n"
        "2,ON,OFF,,b,r1,,,20,2\n"
    )
    assert err(tmp_path, sm_model(tmp_path, bad)).source == "AP.csv:3"


def test_duplicate_input_names(tmp_path):
    write(tmp_path, "in.csv", IN_HDR + "a,int,1\na,int,2\n")
    assert err(tmp_path, master(tmp_path, ["in.csv,inputs,"])).source == "in.csv:3"


def test_input_clashes_with_result_variable(tmp_path):
    write(tmp_path, "eq.csv", EQ_HDR + "a,,,x,10,1\n")
    write(tmp_path, "in.csv", IN_HDR + "x,int,1\n")
    m = master(tmp_path, ["eq.csv,equations,", "in.csv,inputs,"])
    assert err(tmp_path, m).source == "in.csv:2"


def test_sm_name_clashes_with_input_and_result(tmp_path):
    write(tmp_path, "in.csv", IN_HDR + "AP,int,1\n")
    write(tmp_path, "AP.csv", GOOD_SM)
    m = master(tmp_path, ["AP.csv,state_machine,1", "in.csv,inputs,"])
    assert err(tmp_path, m).source == "in.csv:2"
    write(tmp_path, "eq.csv", EQ_HDR + "a,,,AP,10,1\n")
    m = master(tmp_path, ["AP.csv,state_machine,1", "eq.csv,equations,"])
    assert err(tmp_path, m).source == "eq.csv:2"


def test_sm_name_must_be_identifier_and_not_reserved(tmp_path):
    write(tmp_path, "my-sm.csv", GOOD_SM)
    m = master(tmp_path, ["my-sm.csv,state_machine,1"])
    assert err(tmp_path, m).source == "master.csv:2"
    write(tmp_path, "t.csv", GOOD_SM)
    m = master(tmp_path, ["t.csv,state_machine,1"])
    assert err(tmp_path, m).source == "master.csv:2"


def test_max_state_machines(tmp_path, monkeypatch):
    write(tmp_path, "A.csv", GOOD_SM)
    write(tmp_path, "B.csv", GOOD_SM.replace(",r1,", ",q1,").replace(",r2,", ",q2,").replace(",r3,", ",q3,").replace(",r4,", ",q4,").replace(",r5,", ",q5,"))
    m = master(tmp_path, ["A.csv,state_machine,1", "B.csv,state_machine,2"])
    monkeypatch.setattr(constants, "MAX_STATE_MACHINES", 2)
    assert len(load_model(m).state_machines) == 2
    monkeypatch.setattr(constants, "MAX_STATE_MACHINES", 1)
    e = err(tmp_path, m)
    assert e.source is None and "state machines" in e.msg


def test_max_equations_counts_sm_rows_and_standalone(tmp_path, monkeypatch):
    write(tmp_path, "AP.csv", GOOD_SM)  # 5 rows
    write(tmp_path, "eq.csv", EQ_HDR + "a,,,x,10,1\nb,,,y,10,2\n")  # 2
    m = master(tmp_path, ["AP.csv,state_machine,1", "eq.csv,equations,"])
    monkeypatch.setattr(constants, "MAX_EQUATIONS", 7)
    load_model(m)
    monkeypatch.setattr(constants, "MAX_EQUATIONS", 6)
    e = err(tmp_path, m)
    assert e.source is None and "equations" in e.msg


def test_error_str_format(tmp_path):
    m = master(tmp_path, ["x.csv,bogus,1"])
    assert str(err(tmp_path, m)).startswith("master.csv:2: ")


def test_non_utf8_csv_is_a_model_error_with_line(tmp_path):
    """#29: a CSV saved as cp1252 (Excel 'CSV') gives file:line, not UnicodeDecodeError."""
    (tmp_path / "master.csv").write_text("file_name,type,order,band\nm.csv,state_machine,1,10\n", encoding="utf-8")
    text = ("transition_id,current_state,next_state,default_state,equation,result_variable,rationale,title,order\n"
            "1,A,B,A,True,r1,,Temp > 30 °C,1\n")
    (tmp_path / "m.csv").write_bytes(text.encode("cp1252"))
    with pytest.raises(ModelError) as e:
        load_model(tmp_path / "master.csv")
    assert "not UTF-8" in str(e.value) and "m.csv:2" in str(e.value)


def test_utf8_with_bom_still_loads(tmp_path):
    (tmp_path / "master.csv").write_text("file_name,type,order,band\nm.csv,state_machine,1,10\n", encoding="utf-8")
    text = ("transition_id,current_state,next_state,default_state,equation,result_variable,rationale,title,order\n"
            "1,A,B,A,True,r1,,Temp > 30 °C,1\n")
    (tmp_path / "m.csv").write_bytes(text.encode("utf-8-sig"))
    assert load_model(tmp_path / "master.csv").state_machines[0].transitions[0].title == "Temp > 30 °C"


@pytest.mark.parametrize("row", [
    "a,float,nan,,slider,,0,10,",
    "a,float,inf,,number,,,,",
    "a,float,1,,number,,nan,,",
    "a,float,1,,number,,,inf,",
    "a,float,1,,number,,0,10,nan",
])
def test_non_finite_float_definitions_are_load_errors(tmp_path, row):
    """#30: nan/inf would skip the min/max checks and break the JSON messages."""
    (tmp_path / "master.csv").write_text("file_name,type,order,band\nm.csv,state_machine,1,10\ninputs.csv,inputs,,\n",
                                         encoding="utf-8")
    (tmp_path / "m.csv").write_text("transition_id,current_state,next_state,default_state,equation,result_variable,"
                                    "rationale,title,order\n1,A,B,A,True,r1,,,1\n", encoding="utf-8")
    (tmp_path / "inputs.csv").write_text("variable_name,type,default_value,group,widget,label,min,max,step\n" + row + "\n",
                                         encoding="utf-8")
    with pytest.raises(ModelError) as e:
        load_model(tmp_path / "master.csv")
    assert "inputs.csv:2" in str(e.value)
