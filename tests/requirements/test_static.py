"""Static checks over src/statesim."""

import ast
import re

import pytest

import statesim
from statesim import constants

from .helpers import SRC

R = pytest.mark.req

FILES = sorted(SRC.glob("*.py"))
TREES = {p.name: ast.parse(p.read_text(encoding="utf-8")) for p in FILES}


def imported_roots(tree):
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            out.add(node.module.split(".")[0])
    return out


def forbidden_found(forbidden):
    return {n: sorted(imported_roots(t) & forbidden) for n, t in TREES.items()
            if imported_roots(t) & forbidden}


@R("REQ-103")
def test_no_async_or_threads():
    bad = forbidden_found({"asyncio", "threading", "concurrent", "multiprocessing",
                           "_thread", "trio", "anyio", "gevent"})
    assert not bad
    for name, tree in TREES.items():
        for node in ast.walk(tree):
            assert not isinstance(node, (ast.AsyncFunctionDef, ast.Await, ast.AsyncFor,
                                         ast.AsyncWith)), name


@R("REQ-104", "REQ-063")
def test_no_wall_clock():
    assert not forbidden_found({"time", "datetime", "sched", "timeit", "calendar"})
    for name, tree in TREES.items():
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in {"sleep", "monotonic",
                                                                  "perf_counter", "time_ns"}:
                pytest.fail(f"{name}: wall-clock use {node.attr}")


@R("REQ-105")
def test_no_randomness():
    assert not forbidden_found({"random", "secrets", "uuid", "numpy"})


@R("REQ-106")
def test_python_only():
    files = [p for p in SRC.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    # code is Python only; the aircraft panel sets (HTML and CSV data) are not code
    data = [p for p in files if "aircraft" in p.relative_to(SRC).parts]
    assert files and all(p.suffix == ".py" for p in files if p not in data)
    assert all(p.suffix in (".html", ".csv") for p in data)


@R("REQ-081")
def test_importable_package():
    assert statesim.__path__
    for name in ("Engine", "load_model", "Model", "ModelError", "ListTraceSink",
                 "EvaluationError", "TraceSink", "format_event"):
        assert hasattr(statesim, name)


@R("REQ-047")
def test_scheduling_uses_exact_arithmetic():
    for fname in ("scheduler.py", "model.py"):
        tree = TREES[fname]
        for node in ast.walk(tree):
            assert not (isinstance(node, ast.Constant) and isinstance(node.value, float)), fname
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "float":
                pytest.fail(f"{fname}: float() in scheduling code")
    assert "Fraction" in (SRC / "scheduler.py").read_text(encoding="utf-8")


@R("REQ-054")
def test_no_set_or_dict_order_dependence():
    for name, tree in TREES.items():
        for node in ast.walk(tree):
            iters = []
            if isinstance(node, (ast.For, ast.AsyncFor)):
                iters.append(node.iter)
            elif isinstance(node, ast.comprehension):
                iters.append(node.iter)
            for it in iters:
                bad = isinstance(it, (ast.Set, ast.SetComp)) or (
                    isinstance(it, ast.Call) and getattr(it.func, "id", "")
                    in {"set", "frozenset"})
                assert not bad, f"{name}:{it.lineno} iterates a set"


@R("REQ-076")
def test_limits_are_named_constants():
    assert isinstance(constants.MAX_EQUATIONS, int)
    assert isinstance(constants.MAX_STATE_MACHINES, int)
    for name in ("loader.py", "engine.py", "model.py"):
        text = (SRC / name).read_text(encoding="utf-8")
        assert not re.search(r"\b10_?000\b", text), f"{name} hard-codes a limit"
    assert "MAX_EQUATIONS" in (SRC / "loader.py").read_text(encoding="utf-8")


@R("REQ-108")
def test_no_event_bus():
    for p in FILES:
        assert "event" not in p.stem and "bus" not in p.stem
    for name, tree in TREES.items():
        for node in ast.walk(tree):
            ident = getattr(node, "name", None) or getattr(node, "id", None) or ""
            assert not re.search(r"(?i)event_?bus|subscribe|publish|dispatcher|listener",
                                 str(ident)), f"{name}: {ident}"


@R("REQ-118")
def test_engine_does_not_depend_on_the_server():
    # The server is a separate package; the engine never imports it or a web library.
    assert not forbidden_found({"statesim_server", "websockets", "http", "socket", "webbrowser"})
    server = SRC.parent / "statesim_server"
    assert (server / "server.py").is_file() and not (SRC / "server.py").exists()
