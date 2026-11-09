"""Runtime: context, state machine states, tick; the public API seam.

Behavior is defined by docs/decisions.md; summary of the contract below.
"""

from __future__ import annotations

from fractions import Fraction

from .model import Model
from .trace import TraceSink


class Engine:
    """Executes a Model deterministically.

    Construction (``Engine(model, trace=None)``):
      * Compiles every equation and transition-row equation once with
        evaluator.compile_expr (code objects live on the Engine, not the
        Model) and builds the schedule with scheduler.build_schedule.
      * Context dict initialised with: every input at its InputDef.default;
        every result_variable (standalone and SM rows) = False; every state
        machine name = its default_state; tick = 0; t = Fraction(0);
        dt = Fraction(0) (overwritten per item before evaluation).
      * Nothing is logged at construction.

    step():
      1. tick += 1; ctx["tick"] = tick; ctx["t"] = Fraction(tick) / tick_hz
         (exact, never accumulated).
      2. For each item in scheduler.due_items(schedule, tick), in order, set
         ctx["dt"] = 1 / item.band_hz, then:
         * equation: value = eval_expr(code, ctx); if value != previous,
           store it and emit TraceEvent(component=constants.EQUATIONS_COMPONENT,
           action=f"{name} {old}->{new}", values=used names).
         * state machine (one unit): evaluate ALL rows of ALL transitions
           (no short-circuit), transitions in model order, rows in model
           order; each row's result is written to the context immediately
           (visible to later rows) and a change is logged with component =
           SM name, action = f"{result_variable} {old}->{new}". Then the
           first transition (model order) whose current_state is None or
           equals the current state and whose rows are all True wins; at
           most one fires. If it is global and next_state == current state
           it is a no-op (not logged) and still ends the selection. Otherwise
           ctx[SM name] = next_state (visible immediately) and a TraceEvent is
           emitted with component = SM name, action =
           f'{label} {old}->{new} "{title}"' where label is the transition id,
           prefixed with "T" when the id starts with a digit, and title is
           Transition.title. A non-global self-transition (current ==
           next) fires and is logged.
         * values for all events = sorted (name, ctx value) pairs for the
           names used by the expression(s) involved (all rows of the winning
           transition for a state change) that exist in the context.

    set_input(name, value): KeyError if ``name`` is not a declared input.
    Sets ctx[name] = value (no type coercion) and always emits TraceEvent at
    the current tick/t with component = constants.INPUT_COMPONENT, action =
    f"set {name} {old!r}->{value!r}", values = ((name, value),).
    """

    def __init__(self, model: Model, trace: TraceSink | None = None) -> None:
        raise NotImplementedError

    @property
    def tick(self) -> int:
        """Number of completed steps (0 before the first step)."""
        raise NotImplementedError

    @property
    def t(self) -> Fraction:
        """Exact simulation time in seconds: Fraction(tick) / model.tick_hz."""
        raise NotImplementedError

    def step(self) -> None:
        """Advance one tick and run every due item (see class docstring)."""
        raise NotImplementedError

    def run(self, ticks: int) -> None:
        """Call step() ``ticks`` times (ticks >= 0; 0 is a no-op)."""
        raise NotImplementedError

    def snapshot(self) -> dict:
        """Return a fresh, independent dict:
        ``{"tick": int, "t": float(t), "states": {sm_name: state},
        "outputs": {result_variable: bool}, "inputs": {name: value}}``.
        Each inner dict has keys sorted by name. ``outputs`` covers all
        result variables (standalone equations and SM rows).
        """
        raise NotImplementedError

    def set_input(self, name: str, value: object) -> None:
        """Write an external input (see class docstring). KeyError if unknown."""
        raise NotImplementedError
