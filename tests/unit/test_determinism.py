"""Determinism tests: repeat runs, hash seeds, CSV row order, no clock/random."""

from __future__ import annotations

import csv
import json
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from statesim import Engine, ListTraceSink, load_model

R = pytest.mark.req

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tests" / "fixtures"
RUN_SCENARIOS = sorted(
    p.name for p in FIXTURES.iterdir()
    if (p / "expected.json").exists() and "steps" in json.loads(
        (p / "expected.json").read_text(encoding="utf-8"))
)


def run_scenario(master: Path):
    """Replay the scenario steps; return (log lines, snapshots)."""
    steps = json.loads((master.parent / "expected.json").read_text(encoding="utf-8"))["steps"]
    sink = ListTraceSink()
    eng = Engine(load_model(master), sink)
    snaps = []
    for step in steps:
        for k, v in step.get("set_inputs", {}).items():
            eng.set_input(k, v)
        eng.step()
        snaps.append(eng.snapshot())
    return sink.lines(), snaps


def test_run_scenarios_found():
    assert len(RUN_SCENARIOS) == 8


@pytest.mark.parametrize("name", RUN_SCENARIOS)
@R("REQ-101", "REQ-102")
def test_same_scenario_twice_identical(name):
    master = FIXTURES / name / "master.csv"
    l1, s1 = run_scenario(master)
    l2, s2 = run_scenario(master)
    assert "\n".join(l1).encode() == "\n".join(l2).encode()
    assert json.dumps(s1, sort_keys=False) == json.dumps(s2, sort_keys=False)
    assert s1 == s2


_CHILD = r"""
import json, sys
from pathlib import Path
from statesim import Engine, ListTraceSink, load_model
master = Path(sys.argv[1])
steps = json.loads((master.parent / "expected.json").read_text(encoding="utf-8"))["steps"]
sink = ListTraceSink()
eng = Engine(load_model(master), sink)
snaps = []
for step in steps:
    for k, v in step.get("set_inputs", {}).items():
        eng.set_input(k, v)
    eng.step()
    snaps.append(eng.snapshot())
sys.stdout.write("\n".join(sink.lines()) + "\n" + json.dumps(snaps))
"""


def _child(name, seed):
    env = dict(os.environ, PYTHONHASHSEED=str(seed), PYTHONPATH=str(REPO / "src"))
    out = subprocess.run(
        [sys.executable, "-c", _CHILD, str(FIXTURES / name / "master.csv")],
        env=env, capture_output=True, text=True, check=True, cwd=REPO,
    )
    return out.stdout


@pytest.mark.parametrize("name", ["ap_engage", "multirate", "reuse_equation"])
@R("REQ-054", "REQ-101", "REQ-102")
def test_hash_seed_independent(name):
    outs = {seed: _child(name, seed) for seed in (0, 1, 12345)}
    assert len(outs[0].splitlines()) > 3
    assert outs[0] == outs[1] == outs[12345]
    in_process = run_scenario(FIXTURES / name / "master.csv")
    assert outs[0].split("\n", 1)[0] == in_process[0][0]


def _distinct_orders(master: Path) -> bool:
    """True when every (band, order) item key in the model is unique."""
    d = master.parent
    seen = set()
    with open(master, newline="", encoding="utf-8") as f:
        for m in csv.DictReader(f):
            if m["type"] == "inputs":
                continue
            with open(d / m["file_name"], newline="", encoding="utf-8") as g:
                rows = list(csv.DictReader(g))
            if m["type"] == "state_machine":
                keys = [(rows[0]["band"], m["order"])]
                row_orders = [r["order"] for r in rows]
                if len(set(row_orders)) != len(row_orders):
                    return False
            else:
                keys = [(r["band"], r["order"]) for r in rows]
            for k in keys:
                if k in seen:
                    return False
                seen.add(k)
    return True


def _shuffle_file(path: Path, rng: random.Random):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header, body = rows[0], rows[1:]
    rng.shuffle(body)
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([header] + body)


SHUFFLE_OK = [n for n in RUN_SCENARIOS if _distinct_orders(FIXTURES / n / "master.csv")]


def test_shuffle_candidates_checked():
    # All 8 run scenarios have all-distinct (band, order) keys (checked by script).
    assert SHUFFLE_OK == RUN_SCENARIOS


@pytest.mark.parametrize("name", SHUFFLE_OK)
@R("REQ-102")
def test_csv_row_order_irrelevant(name, tmp_path):
    base, _ = run_scenario(FIXTURES / name / "master.csv")
    for seed in range(5):
        d = tmp_path / f"s{seed}"
        shutil.copytree(FIXTURES / name, d)
        rng = random.Random(seed)
        with open(d / "master.csv", newline="", encoding="utf-8") as f:
            for m in csv.DictReader(f):
                if m["type"] in ("state_machine", "equations"):
                    _shuffle_file(d / m["file_name"], rng)
        lines, _ = run_scenario(d / "master.csv")
        assert lines == base, f"{name} seed {seed}"


@pytest.mark.parametrize("name", RUN_SCENARIOS)
@R("REQ-104", "REQ-105")
def test_no_wall_clock_or_random(name, monkeypatch):
    base, _ = run_scenario(FIXTURES / name / "master.csv")

    def boom(*a, **k):
        raise AssertionError("forbidden nondeterministic call")

    for mod, attrs in (
        (time, ["time", "time_ns", "monotonic", "monotonic_ns", "perf_counter",
                "perf_counter_ns", "process_time"]),
        (random, ["random", "randint", "choice", "shuffle", "uniform", "seed",
                  "getrandbits", "randrange", "sample"]),
    ):
        for a in attrs:
            monkeypatch.setattr(mod, a, boom)
    lines, _ = run_scenario(FIXTURES / name / "master.csv")
    assert lines == base
