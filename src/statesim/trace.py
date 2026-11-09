"""Trace hook: records result changes, state transitions and set_input.

Line format (docs/decisions.md item 9)::

    tick=000012 t=0.240000 | AP | T3 OFF->ARMED "Arm" | alt=1000, ap_sw=True
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from os import PathLike
from typing import Protocol


@dataclass(frozen=True)
class TraceEvent:
    """One logged event.

    ``t`` is the exact simulation time (Fraction seconds). ``component`` is
    the state machine name, constants.EQUATIONS_COMPONENT for standalone
    equations, or constants.INPUT_COMPONENT for set_input. ``action`` is the
    description text (see Engine for the exact forms). ``values`` are
    (name, value) pairs sorted by name.
    """

    tick: int
    t: Fraction
    component: str
    action: str
    values: tuple[tuple[str, object], ...]


class TraceSink(Protocol):
    """Anything that accepts TraceEvents."""

    def emit(self, event: TraceEvent) -> None: ...


def format_value(value: object) -> str:
    """``repr()`` for str (so states show as 'ENGAGED'), ``f"{float(v):.6f}"``
    for Fraction, ``str()`` for everything else (True, 1000, 2.5)."""
    raise NotImplementedError


def format_event(event: TraceEvent) -> str:
    """One log line, no trailing newline:
    ``f"tick={tick:06d} t={float(t):.6f} | {component} | {action} | {values}"``
    where values is ``", ".join(f"{n}={format_value(v)}")`` over
    ``event.values`` in the order given (already sorted). When values is
    empty the line ends after the action (no trailing `` | ``).
    """
    raise NotImplementedError


class FileTraceWriter:
    """TraceSink writing one ``format_event`` line per event to ``path``.

    Opens ``path`` for writing (truncating, UTF-8, ``newline="\\n"``) in the
    constructor; each emit writes the line plus "\\n" and flushes. ``close()``
    closes the file; usable as a context manager.
    """

    def __init__(self, path: str | PathLike[str]) -> None:
        raise NotImplementedError

    def emit(self, event: TraceEvent) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError

    def __enter__(self) -> "FileTraceWriter":
        raise NotImplementedError

    def __exit__(self, *exc: object) -> None:
        raise NotImplementedError


class ListTraceSink:
    """In-memory TraceSink; ``events`` is the list of emitted TraceEvents in
    emission order. ``lines()`` returns ``[format_event(e) for e in events]``.
    """

    def __init__(self) -> None:
        raise NotImplementedError

    def emit(self, event: TraceEvent) -> None:
        raise NotImplementedError

    def lines(self) -> list[str]:
        raise NotImplementedError
