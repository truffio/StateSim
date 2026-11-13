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
    value according to ``type_name`` (bool, int, float, str or enum; anything
    else is a load error). ``type_name`` is the raw ``type`` column. An enum
    is a str restricted to ``choices``.

    The display columns (group, widget, label, min, max, step, choices,
    lit_by, wide) are optional; see constants.INPUT_WIDGETS for the widgets
    allowed per type and their defaults.
    """

    name: str
    type_name: str
    default: object
    source: str
    # Display columns (all optional in the CSV; used by the front end only).
    group: str = "Inputs"
    widget: str = ""
    label: str = ""
    min: float | None = None
    max: float | None = None
    step: float | None = None
    choices: tuple[str, ...] = ()
    lit_by: str = ""
    wide: bool = False
    panel: str = ""          # panel file that drives this input (no card), else ""


@dataclass(frozen=True)
class PanelDef:
    """One aircraft panel (an HTML file listed in the master CSV).

    ``html`` is the file text. ``inputs``, ``shows`` and ``lits`` are the
    variable names bound by its data-input, data-show and data-lit-by
    attributes, in document order without repeats. ``lines`` maps
    (attribute, variable) to the line of its first use (error messages).
    """

    name: str
    file: str
    html: str
    inputs: tuple[str, ...]
    shows: tuple[str, ...]
    lits: tuple[str, ...]
    source: str
    lines: tuple[tuple[str, str, int], ...] = ()
    scale: float = 1         # master CSV "scale" column: display size factor (display only)
    label: str = ""          # master CSV "name" column: display name (display only)

    def line_of(self, attr: str, var: str) -> int:
        return next((n for a, v, n in self.lines if a == attr and v == var), 1)


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
class ActionStatement:
    """One row of the actions CSV: a single Python assignment statement.

    ``targets`` are the variable names it writes (each an input), in the
    order they appear in the statement.
    """

    statement: str
    targets: tuple[str, ...]
    rationale: str
    source: str


@dataclass(frozen=True)
class ActionDef:
    """All rows of the actions CSV sharing one ``action`` name, in file order
    (the order they run in). ``source`` is the first row."""

    name: str
    statements: tuple[ActionStatement, ...]
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
    # Actions run when this transition fires (state machine action columns):
    # exit before the state changes, entry after. "" = none.
    exit_action: str = ""
    entry_action: str = ""

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
    current state (a str). ``display_name`` is the optional master CSV
    ``name`` column (display only). ``master_order`` is the master CSV ``order``.
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
    display_name: str = ""
    # (state, action) pairs: the action run on each pass spent in that state
    # when no transition fires (state machine "during" rows).
    during_actions: tuple[tuple[str, str], ...] = ()
    # master CSV init_action: run once on the machine's first pass ("" = none).
    init_action: str = ""

    def during_action(self, state: str) -> str:
        """The during action of ``state``, else ""."""
        return next((a for s, a in self.during_actions if s == state), "")

    @property
    def label(self) -> str:
        """Name shown to people: the master CSV ``name`` column, else ``name``."""
        return self.display_name or self.name


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
    panels: tuple[PanelDef, ...] = ()
    actions: tuple[ActionDef, ...] = ()   # actions CSV, by first appearance


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
