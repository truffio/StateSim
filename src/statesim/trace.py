"""Trace hook: records result changes, state transitions and set_input.

Line format (docs/decisions.md item 9)::

    tick=000012 t=1100.000 | AP | T3 OFF->ARMED "Arm" | alt=1000, ap_sw=True
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from os import PathLike
from typing import Protocol


@dataclass(frozen=True)
class TraceEvent:
    """One logged event.

    ``t`` is the exact absolute simulation time (Fraction milliseconds). ``component`` is
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
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, Fraction):
        return f"{float(value):.6f}"
    return str(value)


def format_event(event: TraceEvent) -> str:
    """One log line, no trailing newline:
    ``f"tick={tick:06d} t={float(t):.3f} | {component} | {action} | {values}"``
    where values is ``", ".join(f"{n}={format_value(v)}")`` over
    ``event.values`` in the order given (already sorted). When values is
    empty the line ends after the action (no trailing `` | ``).
    """
    head = f"tick={event.tick:06d} t={float(event.t):.3f} | {event.component} | {event.action}"
    if not event.values:
        return head
    values = ", ".join(f"{name}={format_value(value)}" for name, value in event.values)
    return f"{head} | {values}"


class FileTraceWriter:
    """TraceSink writing one ``format_event`` line per event to ``path``.

    Opens ``path`` for writing (truncating, UTF-8, ``newline="\\n"``) in the
    constructor; each emit writes the line plus "\\n" and flushes. ``close()``
    closes the file; usable as a context manager.
    """

    def __init__(self, path: str | PathLike[str]) -> None:
        self._file = open(path, "w", encoding="utf-8", newline="\n")

    def emit(self, event: TraceEvent) -> None:
        self._file.write(format_event(event) + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()

    def __enter__(self) -> "FileTraceWriter":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class ListTraceSink:
    """In-memory TraceSink; ``events`` is the list of emitted TraceEvents in
    emission order. ``lines()`` returns ``[format_event(e) for e in events]``.
    """

    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def emit(self, event: TraceEvent) -> None:
        self.events.append(event)

    def lines(self) -> list[str]:
        return [format_event(e) for e in self.events]
