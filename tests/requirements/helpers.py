"""Helpers for requirement tests: scenario runner and inline model builder."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from statesim import Engine, ListTraceSink, ModelError, load_model

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
SRC = Path(__file__).resolve().parents[2] / "src" / "statesim"


# ---------------------------------------------------------------- scenarios
def scenario_dir(name: str) -> Path:
    d = FIXTURES / name
    if not (d / "master.csv").exists():
        pytest.skip(f"scenario fixture {name!r} not available")
    return d


def load_expected(name: str) -> dict:
    d = scenario_dir(name)
    return json.loads((d / "expected.json").read_text(encoding="utf-8"))


def _contains(actual, expected, path=""):
    """Assert ``expected`` is a subset of ``actual`` (dicts recursively)."""
    if isinstance(expected, dict):
        for k, v in expected.items():
            assert k in actual, f"{path}/{k} missing in {actual!r}"
            _contains(actual[k], v, f"{path}/{k}")
    else:
        assert actual == expected, f"{path}: expected {expected!r}, got {actual!r}"


def run_scenario(name: str) -> Engine:
    """Load fixtures/<name>, replay expected.json steps, return the engine."""
    d = scenario_dir(name)
    exp = load_expected(name)
    engine = Engine(load_model(d / "master.csv"))
    for i, step in enumerate(exp["steps"]):
        for k, v in step.get("set_inputs", {}).items():
            engine.set_input(k, v)
        engine.step()
        _contains(engine.snapshot(), step["expect"], f"step{i}")
    return engine


def run_error_scenario(name: str) -> None:
    d = scenario_dir(name)
    exp = load_expected(name)
    with pytest.raises(ModelError) as ei:
        load_model(d / "master.csv")
    text = str(ei.value)
    assert exp["error_contains"] in text
    assert exp["source_contains"] in text


# ------------------------------------------------------------ inline models
def _write(path: Path, header: list[str], rows: list[list]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


SM_HEADER = ["transition_id", "current_state", "next_state", "default_state",
             "equation", "result_variable", "rationale", "title", "band", "order"]
EQ_HEADER = ["equation", "explanation", "rationale", "result_variable", "band", "order"]


def T(tid, cur, nxt, eq, rv, *, default="", order=1, title="", band=10):
    """One state machine CSV row."""
    return [tid, cur, nxt, default, eq, rv, "", title, band, order]


def E(rv, eq, *, band=10, order=1):
    """One standalone equation CSV row."""
    return [eq, "", "", rv, band, order]


def build(tmp_path: Path, sms=(), equations=None, inputs=None,
          master_order=None) -> Path:
    """Write a model and return the master path.

    sms: list of (name, rows) or (name, rows, master_order).
    equations: list of E(...) rows or None.  inputs: list of (name, type, default).
    master_order: "eq_first" puts the equations row before the SMs.
    """
    master = []
    for item in sms:
        name, rows = item[0], item[1]
        order = item[2] if len(item) > 2 else 1
        _write(tmp_path / f"{name}.csv", SM_HEADER, rows)
        master.append([f"{name}.csv", "state_machine", order])
    if equations is not None:
        _write(tmp_path / "equations.csv", EQ_HEADER, equations)
        row = ["equations.csv", "equations", ""]
        master.insert(0, row) if master_order == "eq_first" else master.append(row)
    if inputs is not None:
        _write(tmp_path / "inputs.csv", ["variable_name", "type", "default_value"],
               [list(r) for r in inputs])
        master.append(["inputs.csv", "inputs", ""])
    _write(tmp_path / "master.csv", ["file_name", "type", "order"], master)
    return tmp_path / "master.csv"


def engine_for(tmp_path, trace=None, **kw) -> Engine:
    return Engine(load_model(build(tmp_path, **kw)), trace) if trace else \
        Engine(load_model(build(tmp_path, **kw)))


def simple_sm(name="S", eq="go", rv="s_go", band=10):
    """OFF -> ON when ``eq``; ON -> OFF never (extra transition keeps ON used)."""
    return (name, [T("1", "OFF", "ON", eq, rv, default="OFF", band=band)])


def states_over(engine: Engine, ticks: int, sm: str) -> list[str]:
    out = []
    for _ in range(ticks):
        engine.step()
        out.append(engine.snapshot()["states"][sm])
    return out


def outputs_over(engine: Engine, ticks: int, var: str) -> list:
    out = []
    for _ in range(ticks):
        engine.step()
        out.append(engine.snapshot()["outputs"][var])
    return out
