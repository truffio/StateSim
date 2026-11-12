"""Tool-level constants (spec: supported_logic.tool_constraints)."""

from __future__ import annotations

# Limits. Equations inside state machine files (one per SM CSV row) count
# toward MAX_EQUATIONS together with the standalone equations.
MAX_EQUATIONS: int = 10_000
MAX_STATE_MACHINES: int = 10_000

# Context names provided by the engine; no input, result_variable or state
# machine may use them.
RESERVED_NAMES: frozenset[str] = frozenset({"tick", "t", "dt"})

# Master CSV.
MASTER_COLUMNS: tuple[str, ...] = ("file_name", "type", "order", "band")
# order and band are used (and required) on state_machine rows only.
# Optional master column for panel rows: display size factor (default 1).
MASTER_SCALE_COLUMN = "scale"
# Optional master column: display name of a state machine (front end only).
MASTER_NAME_COLUMN = "name"
TYPE_STATE_MACHINE = "state_machine"
TYPE_EQUATIONS = "equations"
TYPE_INPUTS = "inputs"
TYPE_PANEL = "panel"
FILE_TYPES: tuple[str, ...] = (TYPE_STATE_MACHINE, TYPE_EQUATIONS, TYPE_INPUTS, TYPE_PANEL)
# Panel files (HTML) bind elements to variables with these attributes.
PANEL_INPUT_ATTR = "data-input"      # a button or knob that writes an input
PANEL_SHOW_ATTR = "data-show"        # shows a variable's value
PANEL_FORMAT_ATTR = "data-format"    # printf-like format for data-show
PANEL_LIT_ATTR = "data-lit-by"       # lit while the variable is true
# Widgets of inputs driven by a panel (inputs CSV "panel" column).
PANEL_WIDGETS: tuple[str, ...] = ("momentary", "toggle", "knob")

# Definition CSV columns (required headers; extra columns are ignored).
STATE_MACHINE_COLUMNS: tuple[str, ...] = (
    "transition_id",
    "current_state",
    "next_state",
    "default_state",
    "equation",
    "result_variable",
    "rationale",
    "title",
    "order",
)
EQUATIONS_COLUMNS: tuple[str, ...] = (
    "equation",
    "explanation",
    "rationale",
    "result_variable",
    "band",
    "order",
)
INPUTS_COLUMNS: tuple[str, ...] = ("variable_name", "type", "default_value")
# Optional display columns of the inputs CSV (front end only).
INPUTS_DISPLAY_COLUMNS: tuple[str, ...] = (
    "group", "widget", "label", "min", "max", "step", "choices", "lit_by", "wide", "panel",
)
INPUT_TYPES: tuple[str, ...] = ("bool", "int", "float", "str", "enum")
# Allowed widgets per input type; the first is the default (for int/float the
# default is "slider" when min and max are given, else "number").
INPUT_WIDGETS: dict[str, tuple[str, ...]] = {
    "bool": ("switch", "momentary", "lit", "toggle"),
    "int": ("slider", "number", "knob"),
    "float": ("slider", "number", "knob"),
    "enum": ("dropdown",),
    "str": ("text",),
}
DEFAULT_INPUT_GROUP = "Inputs"
CHOICES_SEPARATOR = "|"

# Trace component names for events that do not belong to a state machine.
EQUATIONS_COMPONENT = "EQ"
INPUT_COMPONENT = "INPUT"
