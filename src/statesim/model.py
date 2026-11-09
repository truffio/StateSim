"""Immutable model: the shared contract between loader, scheduler and engine.

Numeric choice: every band frequency, ``order`` value and ``tick_hz`` is a
``fractions.Fraction`` (exact arithmetic; "20" -> Fraction(20), "0.5" ->
Fraction(1, 2)). Fractions compare equal to ints (``Fraction(20) == 20``).

``source`` fields are ``"file:line"`` strings (see errors.ModelError).
Compiled code objects are NOT stored here; the Engine compiles expressions
in its constructor.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import gcd, lcm
from typing import Iterable


@dataclass(frozen=True)
class InputDef:
    """One row of the inputs CSV.

    ``default`` is the ``default_value`` column converted to a Python native
    value according to ``type_name`` (bool, int, float or str; anything else
    is a load error). ``type_name`` is the raw ``type`` column.
    """

    name: str
    type_name: str
    default: object
    source: str


@dataclass(frozen=True)
class EquationDef:
    """One row of the standalone equations CSV."""

    result_variable: str
    equation: str
    band_hz: Fraction
    order: Fraction
    explanation: str
    rationale: str
    source: str


@dataclass(frozen=True)
class TransitionRow:
    """One row (equation) of a state machine CSV.

    ``order`` is the row's ``order`` column; it orders transitions within the
    state machine (min over a transition's rows) and rows within a transition.
    """

    equation: str
    result_variable: str
    order: Fraction
    rationale: str
    title: str
    source: str


@dataclass(frozen=True)
class Transition:
    """All rows sharing one ``transition_id`` (their equations are ANDed).

    ``current_state is None`` means a global transition. ``rows`` are sorted
    by (row.order, CSV row). ``id`` is the raw transition_id string.
    """

    id: str
    current_state: str | None
    next_state: str
    rows: tuple[TransitionRow, ...]

    @property
    def order(self) -> Fraction:
        """Min ``order`` over the rows (primary sort key of transitions)."""
        return min(r.order for r in self.rows)

    @property
    def title(self) -> str:
        """First non-empty row title, else ""."""
        return next((r.title for r in self.rows if r.title), "")


@dataclass(frozen=True)
class StateMachine:
    """One state machine file.

    ``name`` is the file stem; it is also the context variable holding the
    current state (a str). ``master_order`` is the master CSV ``order``.
    ``states`` lists every state name in first-appearance order, default
    state first. ``transitions`` are sorted by (Transition.order,
    transition_sort_key(id)). ``source`` is the master CSV row
    (``"<master file name>:<line>"``).
    """

    name: str
    default_state: str
    band_hz: Fraction
    master_order: Fraction
    states: tuple[str, ...]
    transitions: tuple[Transition, ...]
    source: str
    master_row: int = 0


@dataclass(frozen=True)
class Model:
    """The complete loaded definition.

    ``state_machines`` are in master-file row order; ``equations`` and
    ``inputs`` in CSV row order. ``tick_hz`` = compute_tick_hz(all band
    frequencies of equations and state machines); Fraction(1) if there are
    none. ``master_path`` is the master CSV path as passed to load_model.
    ``StateMachine.master_row`` and ``equations_master_row`` are the master
    file line numbers of those rows; the scheduler uses them to break
    (band, order) ties. (Defaults: SM 0, equations after everything.)
    """

    state_machines: tuple[StateMachine, ...]
    equations: tuple[EquationDef, ...]
    inputs: tuple[InputDef, ...]
    tick_hz: Fraction
    master_path: str
    equations_master_row: int = 1 << 60


def transition_sort_key(transition_id: str) -> tuple[int, int | str]:
    """Natural tie-break key for transition ids: numeric ids sort numerically
    and before non-numeric ids, which sort as strings ("2" < "10" < "A")."""
    s = transition_id.strip()
    try:
        return (0, int(s))
    except ValueError:
        return (1, s)


def compute_tick_hz(bands: Iterable[Fraction | int]) -> Fraction:
    """Exact LCM of positive rational frequencies.

    lcm(a/b, c/d) = lcm(a, c) / gcd(b, d) (with reduced fractions). Every
    band then divides the result into a whole number of ticks:
    period_ticks = tick_hz / band_hz is an int. Returns Fraction(1) for an
    empty iterable. Raises ValueError for a non-positive band.
    """
    num, den = 0, 0
    for b in bands:
        f = Fraction(b)
        if f <= 0:
            raise ValueError(f"band must be > 0 Hz, got {b}")
        num = f.numerator if num == 0 else lcm(num, f.numerator)
        den = f.denominator if den == 0 else gcd(den, f.denominator)
    return Fraction(1) if num == 0 else Fraction(num, den)
