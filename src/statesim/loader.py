"""CSV files -> immutable Model, with load-time checks (docs/decisions.md 13-15)."""

from __future__ import annotations

from os import PathLike

from .model import Model


def load_model(master_csv: str | PathLike[str]) -> Model:
    """Read the master CSV and every file it lists; return a frozen Model.

    CSV reading: ``csv.DictReader`` on files opened with encoding
    ``utf-8-sig`` and ``newline=""``; cells are whitespace-stripped; rows
    whose cells are all empty are skipped; extra columns are ignored; a
    missing required column (constants.*_COLUMNS) is a ModelError. Sources
    are ``"<file_name as written in master>:<line>"`` (master rows use the
    master file's name); line = 1-based physical line, header = line 1.

    Master CSV (columns file_name, type, order):
      * ``type`` in constants.FILE_TYPES, else ModelError.
      * ``file_name`` is resolved relative to the master file's directory.
      * ``order`` is required (parsed as Fraction) on state_machine rows and
        ignored on other rows.
      * At most one ``equations`` row and at most one ``inputs`` row (zero
        is allowed). A missing listed file is a ModelError.
      * State machine name = file stem; duplicate names are a ModelError.

    Parsing:
      * ``band`` -> Fraction(text) (accepts "20", "0.5", "1/3"); must be > 0.
      * ``order`` -> Fraction(text).
      * Inputs ``default_value`` -> ast.literal_eval, fallback raw string
        (empty cell -> "").
      * State machine rows are grouped by transition_id (stripped string);
        an empty ``current_state`` means global (None). Rows within a
        transition sorted by (order, CSV row); transitions sorted by
        (min row order, model.transition_sort_key(id)).
      * StateMachine.states: default state first, then other names in order
        of first appearance (current_state / next_state, CSV row order).

    Load checks (each raises ModelError with the offending source):
      * Every equation compiles (evaluator.compile_expr); code is discarded.
      * Duplicate transition_id: rows sharing a transition_id disagree on
        current_state or next_state.
      * Unknown state: a non-empty current_state that is neither the
        default state nor the next_state of any transition (unreachable).
      * Exactly one non-empty default_state cell per state machine file
        (an empty file therefore fails).
      * All rows of a state machine file share one band.
      * Names: result_variable, input variable_name and state machine names
        must be identifiers, must not be in constants.RESERVED_NAMES, and
        must be unique across all of them (duplicate result_variable across
        or within files, input/result clash, SM-name clash are errors).
        Empty equation or result_variable cells are errors.
      * Limits: len(state machines) > MAX_STATE_MACHINES, or standalone
        equations + all state machine rows > MAX_EQUATIONS.

    Model.tick_hz = model.compute_tick_hz(all equation and SM bands).
    """
    raise NotImplementedError
