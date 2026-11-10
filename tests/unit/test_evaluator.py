"""Unit tests for statesim.evaluator."""

from __future__ import annotations

import pytest

from statesim.errors import ModelError
from statesim.evaluator import compile_expr, eval_expr, names_used


def _run(src: str, ctx: dict) -> bool:
    return eval_expr(compile_expr(src, "test.csv:2"), ctx)


def test_truthiness_of_plain_values():
    assert _run("x", {"x": 1}) is True
    assert _run("x", {"x": 0}) is False
    assert _run("x", {"x": ""}) is False
    assert _run("x", {"x": "text"}) is True
    assert _run("x", {"x": None}) is False
    assert _run("x", {"x": []}) is False


def test_result_is_always_bool():
    assert _run("x + 1", {"x": 4}) is True
    assert _run("x or 0", {"x": 0}) is False


def test_and_or_not():
    ctx = {"a": True, "b": False}
    assert _run("a and b", ctx) is False
    assert _run("a or b", ctx) is True
    assert _run("not b", ctx) is True
    assert _run("not a", ctx) is False
    assert _run("(a or b) and not b", ctx) is True


def test_comparisons_numeric():
    assert _run("alt >= 1000", {"alt": 1000}) is True
    assert _run("alt < 1000", {"alt": 1000}) is False
    assert _run("0 < t <= 2", {"t": 1.5}) is True


def test_string_equality_for_state():
    code = compile_expr('AP == "ENGAGED"', "m.csv:3")
    assert eval_expr(code, {"AP": "ENGAGED"}) is True
    assert eval_expr(code, {"AP": "OFF"}) is False
    assert eval_expr(code, {"AP": "engaged"}) is False


def test_string_inequality_and_single_quotes():
    code = compile_expr("AP != 'OFF'", "m.csv:3")
    assert eval_expr(code, {"AP": "ARMED"}) is True
    assert eval_expr(code, {"AP": "OFF"}) is False


def test_surrounding_whitespace_is_stripped():
    assert _run("   a and b \n", {"a": True, "b": True}) is True


def test_builtins_are_available():
    assert _run("len(s) == 3", {"s": "abc"}) is True
    assert _run("abs(x) > 1", {"x": -2}) is True


def test_context_is_used_not_copied():
    ctx = {"x": False}
    code = compile_expr("x", "m.csv:1")
    assert eval_expr(code, ctx) is False
    ctx["x"] = True
    assert eval_expr(code, ctx) is True


def test_syntax_error_raises_model_error_with_source():
    with pytest.raises(ModelError) as info:
        compile_expr("a and (", "equations.csv:7")
    assert info.value.source == "equations.csv:7"
    assert "equations.csv:7" in str(info.value)
    assert info.value.msg


def test_empty_expression_raises_model_error():
    with pytest.raises(ModelError) as info:
        compile_expr("   ", "equations.csv:4")
    assert info.value.source == "equations.csv:4"


def test_undefined_name_raises_name_error():
    code = compile_expr("missing > 0", "m.csv:1")
    with pytest.raises(NameError):
        eval_expr(code, {})


def test_names_used_sorted_and_unique():
    code = compile_expr("b and a or b and not c", "m.csv:1")
    assert names_used(code) == ("a", "b", "c")


def test_names_used_includes_comprehension_names():
    code = compile_expr("any(v > limit for v in values)", "m.csv:1")
    names = names_used(code)
    assert "values" in names
    assert "limit" in names
    assert "any" in names
    assert list(names) == sorted(names)


def test_names_used_empty_for_constant():
    assert names_used(compile_expr("True", "m.csv:1")) == ()
