"""Expression compilation and evaluation (Python syntax, plain eval).

No sandboxing or AST inspection: equation authors are trusted (spec
explicit_non_goals).
"""

from __future__ import annotations

import builtins
from types import CodeType
from typing import Mapping

from .errors import ModelError


def compile_expr(src: str, source: str) -> CodeType:
    """Compile ``src`` with ``compile(src, source, "eval")``.

    Leading/trailing whitespace is stripped first. Raises
    ``ModelError(<message including the SyntaxError text>, source)`` on a
    syntax error or an empty expression. ``source`` is the "file:line" of the
    defining CSV row.
    """
    text = src.strip()
    if not text:
        raise ModelError("empty expression", source)
    try:
        return compile(text, source, "eval")
    except SyntaxError as exc:
        raise ModelError(f"invalid expression {text!r}: {exc.msg}", source) from exc


def eval_expr(code: CodeType, ctx: Mapping[str, object]) -> bool:
    """Evaluate ``code`` as ``bool(eval(code, {"__builtins__": builtins}, ctx))``
    where ``builtins`` is the ``builtins`` module. ``ctx`` is the engine's live
    context dict (inputs, result variables, state machine states, tick, t,
    dt). Exceptions from the expression (e.g. NameError) propagate unchanged.
    """
    return bool(eval(code, {"__builtins__": builtins}, ctx))


def names_used(code: CodeType) -> tuple[str, ...]:
    """Sorted, de-duplicated names referenced by ``code`` (from
    ``code.co_names``, recursing into nested code objects in ``co_consts``,
    e.g. comprehensions). Used to pick the variable values written to the
    trace. May include builtins/attribute names; callers filter to names
    present in the context.
    """
    found: set[str] = set()
    stack: list[CodeType] = [code]
    while stack:
        current = stack.pop()
        found.update(current.co_names)
        for const in current.co_consts:
            if isinstance(const, CodeType):
                stack.append(const)
    return tuple(sorted(found))
