"""Inputs CSV display columns and the enum type (loader)."""

import pytest

from statesim import ModelError, load_model

R = pytest.mark.req
HEAD = "variable_name,type,default_value,group,widget,label,min,max,step,choices,lit_by,wide\n"


def model(tmp_path, rows, header=HEAD, equations=None):
    (tmp_path / "inputs.csv").write_text(header + rows, encoding="utf-8")
    master = "file_name,type,order\ninputs.csv,inputs,\n"
    if equations:
        (tmp_path / "equations.csv").write_text(
            "equation,explanation,rationale,result_variable,band,order\n" + equations, encoding="utf-8")
        master += "equations.csv,equations,\n"
    (tmp_path / "master.csv").write_text(master, encoding="utf-8")
    return load_model(tmp_path / "master.csv")


@R("REQ-114")
def test_display_columns_are_read(tmp_path):
    m = model(tmp_path, "alt,float,100,Aircraft,slider,Altitude,0,1000,10,,,true\n")
    i = m.inputs[0]
    assert (i.group, i.widget, i.label, i.min, i.max, i.step, i.wide) == \
        ("Aircraft", "slider", "Altitude", 0, 1000, 10, True)


@R("REQ-114")
def test_files_without_display_columns_still_load_with_defaults(tmp_path):
    m = model(tmp_path, "a,bool,false\nn,int,3\ns,str,x\n",
              header="variable_name,type,default_value\n")
    a, n, s = m.inputs
    assert (a.group, a.widget, a.label) == ("Inputs", "switch", "a")
    assert n.widget == "number" and n.min is None
    assert s.widget == "text"


@R("REQ-114")
def test_default_widgets(tmp_path):
    m = model(tmp_path, "n,int,3,,,,0,10,,,,\nb,bool,true,,,,,,,,,\ne,enum,B,,,,,,,A|B,,\n")
    assert [i.widget for i in m.inputs] == ["slider", "switch", "dropdown"]


@R("REQ-115")
def test_enum_choices_and_default(tmp_path):
    i = model(tmp_path, "capa,enum,LAND3,,dropdown,,,,,NONE | APPR1 |LAND3,,\n").inputs[0]
    assert i.choices == ("NONE", "APPR1", "LAND3") and i.default == "LAND3"


@R("REQ-115", "REQ-116")
@pytest.mark.parametrize("row, message", [
    ("e,enum,X,,,,,,,A|B,,\n", "not one of the choices"),
    ("e,enum,A,,,,,,,,,\n", "needs choices"),
    ("b,bool,false,,slider,,,,,,,\n", "not allowed for type bool"),
    ("n,int,1,,slider,,,,,,,\n", "needs min and max"),
    ("n,int,1,,,,5,5,,,,\n", "must be below max"),
    ("n,int,20,,,,0,10,,,,\n", "outside min/max"),
    ("n,float,1,,,,0,10,0,,,\n", "step must be > 0"),
    ("b,bool,false,,,,0,1,,,,\n", "int and float inputs only"),
    ("s,str,x,,,,,,,A|B,,\n", "enum inputs only"),
    ("b,bool,false,,lit,,,,,,,\n", "needs lit_by"),
    ("b,bool,false,,switch,,,,,,x,\n", "lit widget only"),
    ("b,bool,false,,lit,,,,,,nowhere,\n", "not a known variable"),
    ("b,bool,false,,,,,,,,,maybe\n", "invalid wide"),
    ("n,int,1,,,,x,,,,,\n", "invalid min"),
])
def test_invalid_display_definitions_are_rejected(tmp_path, row, message):
    with pytest.raises(ModelError) as ei:
        model(tmp_path, row)
    assert message in str(ei.value) and "inputs.csv:2" in str(ei.value)


@R("REQ-116")
def test_lit_by_may_name_an_equation_result(tmp_path):
    m = model(tmp_path, "pb,bool,false,,lit,AP,,,,,engaged,\n", equations="pb,x,x,engaged,10,1\n")
    assert m.inputs[0].lit_by == "engaged"


@R("REQ-136")
def test_master_name_column_sets_state_machine_display_name(tmp_path):
    sm = ("transition_id,current_state,next_state,default_state,equation,result_variable,"
          "rationale,title,band,order\n1,A,B,A,False,r,,,10,1\n")
    (tmp_path / "S.csv").write_text(sm, encoding="utf-8")
    (tmp_path / "T.csv").write_text(sm.replace(",r,", ",r2,"), encoding="utf-8")
    (tmp_path / "master.csv").write_text(
        "file_name,type,order,name\nS.csv,state_machine,1,Speed modes\nT.csv,state_machine,2,\n",
        encoding="utf-8")
    s, t = load_model(tmp_path / "master.csv").state_machines
    assert (s.name, s.display_name, s.label) == ("S", "Speed modes", "Speed modes")
    assert (t.name, t.label) == ("T", "T")                 # no name: the file name
