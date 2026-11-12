"""CSV files -> immutable Model, with load-time checks (docs/decisions.md 13-15)."""

from __future__ import annotations

import csv
from dataclasses import replace
from html.parser import HTMLParser
from fractions import Fraction
from os import PathLike
from pathlib import Path

from . import constants
from .errors import ModelError
from .model import (
    EquationDef,
    InputDef,
    Model,
    PanelDef,
    StateMachine,
    Transition,
    TransitionRow,
    compute_tick_hz,
    transition_sort_key,
)


def _read_csv(
    path: Path, display: str, required: tuple[str, ...]
) -> list[tuple[int, dict[str, str]]]:
    """Return (line, row) pairs; cells stripped, blank rows skipped."""
    try:
        fh = open(path, encoding="utf-8-sig", newline="")
    except OSError as e:
        raise ModelError(f"cannot read file: {e.strerror or e}", display) from None
    with fh:
        reader = csv.reader(fh)
        header: list[str] | None = None
        rows: list[tuple[int, dict[str, str]]] = []
        try:
            for cells in reader:
                if header is None:
                    header = [c.strip() for c in cells]
                    missing = [c for c in required if c not in header]
                    if missing:
                        raise ModelError(
                            "missing required column(s): " + ", ".join(missing),
                            f"{display}:1",
                        )
                    continue
                cells = [c.strip() for c in cells]
                if not any(cells):
                    continue
                row = {h: (cells[i] if i < len(cells) else "") for i, h in enumerate(header)}
                rows.append((reader.line_num, row))
        except csv.Error as e:
            raise ModelError(f"malformed CSV: {e}", f"{display}:{reader.line_num}") from None
    if header is None:
        raise ModelError("missing required column(s): " + ", ".join(required), f"{display}:1")
    return rows


def _fraction(text: str, what: str, source: str) -> Fraction:
    if text == "":
        raise ModelError(f"{what} is empty", source)
    try:
        return Fraction(text)
    except (ValueError, ZeroDivisionError):
        raise ModelError(f"invalid {what} {text!r}", source) from None


def _band(text: str, source: str) -> Fraction:
    b = _fraction(text, "band", source)
    if b <= 0:
        raise ModelError(f"band must be > 0 Hz, got {text}", source)
    return b


def _check_expr(src: str, source: str) -> None:
    if src == "":
        raise ModelError("equation is empty", source)
    try:
        compile(src, "<expr>", "eval")
    except SyntaxError as e:
        raise ModelError(f"invalid expression {src!r}: {e.msg}", source) from None
    except (ValueError, MemoryError, RecursionError) as e:
        raise ModelError(f"invalid expression {src!r}: {e}", source) from None


class _Names:
    """Registry enforcing identifier/reserved/unique rules."""

    def __init__(self) -> None:
        self.seen: dict[str, str] = {}

    def add(self, name: str, kind: str, source: str) -> None:
        if name == "":
            raise ModelError(f"{kind} is empty", source)
        if not name.isidentifier():
            raise ModelError(f"{kind} {name!r} is not a valid identifier", source)
        if name in constants.RESERVED_NAMES:
            raise ModelError(f"{kind} {name!r} is a reserved name", source)
        if name in self.seen:
            raise ModelError(
                f"duplicate name {name!r} ({kind}; first defined at {self.seen[name]})",
                source,
            )
        self.seen[name] = source


_BOOLS = {"true": True, "false": False, "1": True, "0": False}


def _parse_default(text: str, type_name: str, source: str) -> object:
    """Convert an inputs-CSV default_value according to its type column."""
    kind = type_name.strip()
    try:
        if kind == "bool":
            return _BOOLS[text.lower()]
        if kind == "int":
            return int(text)
        if kind == "float":
            return float(text)
        if kind in ("str", "enum"):
            return text
    except (KeyError, ValueError):
        raise ModelError(
            f"cannot convert default_value {text!r} to {kind}", source
        ) from None
    raise ModelError(
        f"unknown input type {type_name!r} (expected bool, int, float, str or enum)", source
    )


def _num(text: str, what: str, source: str) -> float | None:
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        raise ModelError(f"invalid {what} {text!r}", source) from None


def _input_def(r: dict[str, str], default: object, src: str) -> InputDef:
    """Build an InputDef, validating the optional display columns."""
    kind = r["type"].strip()
    get = lambda c: r.get(c, "").strip()  # noqa: E731
    lo, hi, step = _num(get("min"), "min", src), _num(get("max"), "max", src),         _num(get("step"), "step", src)
    choices = tuple(c.strip() for c in get("choices").split(constants.CHOICES_SEPARATOR)
                    if c.strip())
    allowed = constants.INPUT_WIDGETS[kind]
    widget = get("widget")
    if widget == "":
        widget = ("slider" if lo is not None and hi is not None else "number")             if kind in ("int", "float") else allowed[0]
    if widget not in allowed:
        raise ModelError(f"widget {widget!r} not allowed for type {kind} "
                         f"(expected {', '.join(allowed)})", src)
    if kind in ("int", "float"):
        if widget == "slider" and (lo is None or hi is None):
            raise ModelError("a slider needs min and max", src)
        if lo is not None and hi is not None and lo >= hi:
            raise ModelError(f"min {lo:g} must be below max {hi:g}", src)
        if step is not None and step <= 0:
            raise ModelError(f"step must be > 0, got {step:g}", src)
        if (lo is not None and default < lo) or (hi is not None and default > hi):
            raise ModelError(f"default_value {default!r} outside min/max", src)
    elif get("min") or get("max") or get("step"):
        raise ModelError("min, max and step apply to int and float inputs only", src)
    if kind == "enum":
        if not choices:
            raise ModelError("an enum input needs choices (separated by '|')", src)
        if default not in choices:
            raise ModelError(f"default_value {default!r} is not one of the choices", src)
    elif choices:
        raise ModelError("choices apply to enum inputs only", src)
    lit_by = get("lit_by")
    panel = get("panel")
    if panel and widget not in constants.PANEL_WIDGETS:
        raise ModelError(f"widget {widget!r} cannot be used on a panel "
                         f"(expected {', '.join(constants.PANEL_WIDGETS)})", src)
    if widget in ("toggle", "knob") and not panel:
        raise ModelError(f"the {widget} widget is for panel inputs (set the panel column)", src)
    if widget == "knob" and (lo is None or hi is None):
        raise ModelError("a knob needs min and max", src)
    if widget == "lit" and not lit_by:
        raise ModelError("a lit push-button needs lit_by", src)
    if lit_by and widget != "lit":
        raise ModelError("lit_by applies to the lit widget only", src)
    wide = get("wide").lower()
    if wide not in ("", *_BOOLS):
        raise ModelError(f"invalid wide {get('wide')!r} (expected true or false)", src)
    return InputDef(
        name=r["variable_name"], type_name=kind, default=default, source=src,
        group=get("group") or constants.DEFAULT_INPUT_GROUP, widget=widget,
        label=get("label") or r["variable_name"], min=lo, max=hi, step=step,
        choices=choices, lit_by=lit_by, wide=_BOOLS[wide] if wide else False,
        panel=panel,
    )


class _PanelParser(HTMLParser):
    """Collects (attribute, variable, line) for the panel binding attributes."""

    WATCH = (constants.PANEL_INPUT_ATTR, constants.PANEL_SHOW_ATTR, constants.PANEL_LIT_ATTR)

    def __init__(self) -> None:
        super().__init__()
        self.found: list[tuple[str, str, int]] = []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k in self.WATCH:
                self.found.append((k, (v or "").strip(), self.getpos()[0]))

    handle_startendtag = handle_starttag


def _panel_scale(text: str, source: str) -> float:
    """Master CSV ``scale`` of a panel row: a positive number, default 1."""
    if text == "":
        return 1
    try:
        value = float(text)
    except ValueError:
        raise ModelError(f"invalid scale {text!r}", source) from None
    if not value > 0:
        raise ModelError(f"scale must be > 0, got {text}", source)
    return value


def _load_panel(path: Path, display: str, source: str) -> PanelDef:
    """Read a panel HTML file and collect its variable bindings."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:
        raise ModelError(f"cannot read file: {e}", display) from None
    parser = _PanelParser()
    parser.feed(text)
    parser.close()
    groups: dict[str, list[str]] = {a: [] for a in _PanelParser.WATCH}
    lines: list[tuple[str, str, int]] = []
    for attr, var, line in parser.found:
        if not var:
            raise ModelError(f"{attr} is empty", f"{display}:{line}")
        if var not in groups[attr]:
            groups[attr].append(var)
            lines.append((attr, var, line))
    return PanelDef(name=Path(display).stem, file=display, html=text,
                    inputs=tuple(groups[constants.PANEL_INPUT_ATTR]),
                    shows=tuple(groups[constants.PANEL_SHOW_ATTR]),
                    lits=tuple(groups[constants.PANEL_LIT_ATTR]),
                    source=source, lines=tuple(lines))


def _check_panels(panels: list[PanelDef], inputs: list[InputDef], known: set[str]) -> None:
    """Every panel binding names a real variable, and panel inputs agree with
    the inputs CSV ``panel`` column in both directions."""
    by_name = {i.name: i for i in inputs}
    files = {p.file for p in panels}
    for i in inputs:
        if i.panel and i.panel not in files:
            raise ModelError(f"panel {i.panel!r} is not listed in the master CSV", i.source)
    for p in panels:
        def where(attr, var):
            return f"{p.file}:{p.line_of(attr, var)}"
        for v in p.inputs:
            i = by_name.get(v)
            if i is None:
                raise ModelError(f"data-input {v!r} is not an input",
                                 where(constants.PANEL_INPUT_ATTR, v))
            if i.panel != p.file:
                raise ModelError(f"input {v!r} must have panel={p.file} in the inputs CSV",
                                 where(constants.PANEL_INPUT_ATTR, v))
        for attr, names in ((constants.PANEL_SHOW_ATTR, p.shows),
                            (constants.PANEL_LIT_ATTR, p.lits)):
            for v in names:
                if v not in known:
                    raise ModelError(f"{attr} {v!r} is not a known variable", where(attr, v))
        for i in inputs:
            if i.panel == p.file and i.name not in p.inputs:
                raise ModelError(f"input {i.name!r} has panel={p.file} but the panel has no "
                                 f"data-input for it", i.source)


def names_of(inputs, equations, state_machines) -> set[str]:
    """Every variable name a model defines."""
    out = {i.name for i in inputs} | {e.result_variable for e in equations}
    for sm in state_machines:
        out.add(sm.name)
        out |= {r.result_variable for t in sm.transitions for r in t.rows}
    return out


def _load_state_machine(
    path: Path, display: str, master_order: Fraction, master_source: str, names: _Names,
    master_row: int = 0, band: Fraction = Fraction(1),
) -> tuple[StateMachine, int]:
    """Load one state machine file. Its band comes from the master CSV."""
    stem = Path(display).stem
    rows = _read_csv(path, display, constants.STATE_MACHINE_COLUMNS)
    if rows and "band" in rows[0][1]:
        raise ModelError("band is set in the master CSV, not in the state machine file",
                         f"{display}:1")

    default_state: str | None = None
    groups: dict[str, dict] = {}
    appearance: list[str] = []
    next_states: set[str] = set()
    cur_refs: list[tuple[str, str]] = []

    for idx, (line, r) in enumerate(rows):
        src = f"{display}:{line}"
        tid = r["transition_id"]
        if tid == "":
            raise ModelError("transition_id is empty", src)
        nxt = r["next_state"]
        if nxt == "":
            raise ModelError("next_state is empty", src)
        cur = r["current_state"]
        if r["default_state"]:
            if default_state is not None:
                raise ModelError(
                    f"more than one default_state specified ({default_state!r} already set)",
                    src,
                )
            default_state = r["default_state"]
        order = _fraction(r["order"], "order", src)
        _check_expr(r["equation"], src)
        names.add(r["result_variable"], "result_variable", src)

        g = groups.get(tid)
        if g is None:
            g = groups[tid] = {"cur": cur, "next": nxt, "rows": []}
        elif g["cur"] != cur or g["next"] != nxt:
            raise ModelError(
                f"duplicate transition_id {tid!r}: rows disagree on current_state/next_state",
                src,
            )
        g["rows"].append(
            (
                order,
                idx,
                TransitionRow(
                    equation=r["equation"],
                    result_variable=r["result_variable"],
                    order=order,
                    rationale=r["rationale"],
                    title=r["title"],
                    source=src,
                ),
            )
        )
        if cur:
            appearance.append(cur)
            cur_refs.append((cur, src))
        appearance.append(nxt)
        next_states.add(nxt)

    if default_state is None:
        raise ModelError("no default_state specified", f"{display}:1")

    for cur, src in cur_refs:
        if cur != default_state and cur not in next_states:
            raise ModelError(f"unknown state {cur!r} (never entered)", src)

    states = [default_state]
    for s in appearance:
        if s not in states:
            states.append(s)

    transitions = []
    for tid, g in groups.items():
        trows = tuple(x[2] for x in sorted(g["rows"], key=lambda x: (x[0], x[1])))
        transitions.append(
            Transition(id=tid, current_state=g["cur"] or None, next_state=g["next"], rows=trows)
        )
    transitions.sort(key=lambda tr: (tr.order, transition_sort_key(tr.id)))

    sm = StateMachine(
        name=stem,
        default_state=default_state,
        band_hz=band,
        master_order=master_order,
        states=tuple(states),
        transitions=tuple(transitions),
        source=master_source,
        master_row=master_row,
    )
    return sm, len(rows)


def load_model(master_csv: str | PathLike[str]) -> Model:
    """Read the master CSV and every file it lists; return a frozen Model.

    See docs/decisions.md Parts A and B for the full contract. Raises
    ModelError (with a ``file:line`` source) for any load problem.
    """
    master_path = Path(master_csv)
    master_name = master_path.name
    base = master_path.parent
    mrows = _read_csv(master_path, master_name, ("file_name", "type"))

    entries: list[tuple[str, str, Fraction | None, str]] = []
    band_of: dict[str, Fraction] = {}
    row_of: dict[str, int] = {}
    label_of: dict[str, str] = {}
    scale_of: dict[str, float] = {}
    seen_single: dict[str, str] = {}
    for line, r in mrows:
        src = f"{master_name}:{line}"
        ftype = r["type"]
        if ftype not in constants.FILE_TYPES:
            raise ModelError(
                f"unknown type {ftype!r} (expected one of {', '.join(constants.FILE_TYPES)})",
                src,
            )
        fname = r["file_name"]
        if fname == "":
            raise ModelError("file_name is empty", src)
        order: Fraction | None = None
        if ftype == constants.TYPE_STATE_MACHINE:
            order = _fraction(r.get("order", ""), "order", src)
            band_of[src] = _band(r.get("band", ""), src)
        else:
            if ftype == constants.TYPE_PANEL:
                entries.append((fname, ftype, order, src))
                row_of[src] = line
                label_of[src] = r.get("name", "")
                scale_of[src] = _panel_scale(r.get("scale", ""), src)
                continue
            if ftype in seen_single:
                raise ModelError(
                    f"more than one {ftype!r} row (first at {seen_single[ftype]})", src
                )
            seen_single[ftype] = src
        entries.append((fname, ftype, order, src))
        row_of[src] = line
        label_of[src] = r.get("name", "")

    n_sm = sum(1 for e in entries if e[1] == constants.TYPE_STATE_MACHINE)
    if n_sm > constants.MAX_STATE_MACHINES:
        raise ModelError(
            f"too many state machines ({n_sm} > {constants.MAX_STATE_MACHINES})", None
        )

    names = _Names()
    sm_names: set[str] = set()
    for fname, ftype, _o, src in entries:
        if ftype == constants.TYPE_STATE_MACHINE:
            stem = Path(fname).stem
            if stem in sm_names:
                raise ModelError(f"duplicate state machine name {stem!r}", src)
            sm_names.add(stem)
            names.add(stem, "state machine name", src)

    state_machines: list[StateMachine] = []
    equations: list[EquationDef] = []
    inputs: list[InputDef] = []
    panels: list[PanelDef] = []
    sm_rows = 0

    eq_row = 1 << 60
    for fname, ftype, order, src in entries:
        path = base / fname
        if not path.is_file():
            raise ModelError(f"file not found: {fname}", src)
        if ftype == constants.TYPE_STATE_MACHINE:
            assert order is not None
            sm, n = _load_state_machine(path, fname, order, src, names, row_of[src],
                                        band_of[src])
            state_machines.append(replace(sm, display_name=label_of[src]))
            sm_rows += n
        elif ftype == constants.TYPE_EQUATIONS:
            eq_row = row_of[src]
            for line, r in _read_csv(path, fname, constants.EQUATIONS_COLUMNS):
                rsrc = f"{fname}:{line}"
                _check_expr(r["equation"], rsrc)
                names.add(r["result_variable"], "result_variable", rsrc)
                equations.append(
                    EquationDef(
                        result_variable=r["result_variable"],
                        equation=r["equation"],
                        band_hz=_band(r["band"], rsrc),
                        order=_fraction(r["order"], "order", rsrc),
                        explanation=r["explanation"],
                        rationale=r["rationale"],
                        source=rsrc,
                    )
                )
        elif ftype == constants.TYPE_PANEL:
            panels.append(replace(_load_panel(path, fname, src), scale=scale_of[src]))
        else:
            for line, r in _read_csv(path, fname, constants.INPUTS_COLUMNS):
                rsrc = f"{fname}:{line}"
                names.add(r["variable_name"], "input variable_name", rsrc)
                default = _parse_default(r["default_value"], r["type"], rsrc)
                inputs.append(_input_def(r, default, rsrc))

    known = names_of(inputs, equations, state_machines)
    for i in inputs:
        if i.lit_by and i.lit_by not in known:
            raise ModelError(f"lit_by {i.lit_by!r} is not a known variable", i.source)
    _check_panels(panels, inputs, known)

    if len(equations) + sm_rows > constants.MAX_EQUATIONS:
        raise ModelError(
            f"too many equations ({len(equations) + sm_rows} > {constants.MAX_EQUATIONS})",
            None,
        )

    tick_hz = compute_tick_hz([e.band_hz for e in equations] + [s.band_hz for s in state_machines])
    return Model(
        state_machines=tuple(state_machines),
        equations=tuple(equations),
        inputs=tuple(inputs),
        tick_hz=tick_hz,
        master_path=str(master_csv),
        equations_master_row=eq_row,
        panels=tuple(panels),
    )
