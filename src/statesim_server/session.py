"""One simulation session: the engine, run state, push-button pulses and the
messages exchanged with the browser. Synchronous and free of wall-clock time;
the server (server.py) decides when to call step()."""

from __future__ import annotations

import math
from fractions import Fraction
from html.parser import HTMLParser

from statesim import Engine, EvaluationError, Model, format_text
from statesim.timeline import Timeline, json_value
from statesim.scheduler import build_schedule

MODES = ("realtime", "fast")
MAX_DELTA = 2_000   # more new timeline items than this in one broadcast: send them all as a full timeline


class _FanOut:
    """Trace sink that passes every event to the user's sink (if any) and the timeline."""

    def __init__(self, user, timeline: Timeline) -> None:
        self.user = user
        self.timeline = timeline

    def emit(self, event) -> None:
        if self.user is not None:
            self.user.emit(event)
        self.timeline.emit(event)


def describe_model(model: Model) -> dict:
    """The static layout the browser builds once: machines and input groups."""
    machines = []
    for sm in model.state_machines:
        nxt: dict[str, list[str]] = {s: [] for s in sm.states}
        glob: list[str] = []
        for tr in sm.transitions:
            if tr.current_state is None:
                if tr.next_state not in glob:
                    glob.append(tr.next_state)
            elif tr.next_state != tr.current_state and tr.next_state not in nxt[tr.current_state]:
                nxt[tr.current_state].append(tr.next_state)
        machines.append({"name": sm.name, "label": sm.label, "states": list(sm.states), "next": nxt, "global": glob})

    groups: dict[str, dict] = {}
    for i in model.inputs:
        if i.panel or i.widget == "none":  # driven by a panel, or internal: no card
            continue
        g = groups.setdefault(i.group, {"name": i.group, "wide": False, "inputs": []})
        g["wide"] = g["wide"] or i.wide or i.widget == "slider"
        g["inputs"].append({
            "name": i.name, "label": i.label, "type": i.type_name, "widget": i.widget,
            "min": i.min, "max": i.max, "step": i.step, "choices": list(i.choices),
            "lit_by": i.lit_by or None,
        })
    by_name = {i.name: i for i in model.inputs}
    panels = [{
        "name": p.name, "html": p.html, "scale": p.scale,
        "inputs": {n: {"widget": by_name[n].widget, "label": by_name[n].label,
                       "min": by_name[n].min, "max": by_name[n].max, "step": by_name[n].step}
                   for n in p.inputs},
    } for p in model.panels]
    return {"type": "model", "machines": machines, "groups": list(groups.values()),
            "panels": panels, "inputs": input_meta(model), "recorder": recorder_panel(model),
            "source": model.master_path}


def input_meta(model: Model) -> dict[str, dict]:
    """Every input's report wording: label, plain-English description and unit
    (inputs CSV columns), widget and type. The FMA recording names its causes
    with these ("Approach button pressed", "Radio altitude set to 2500 ft")."""
    return {i.name: {"label": i.label, "description": i.description, "unit": i.unit,
                     "widget": i.widget, "type": i.type_name} for i in model.inputs}


def recorder_panel(model: Model) -> dict | None:
    """The FMA panel for the recording: the panel whose master CSV row has
    role "fma" (at most one). Its rows are drawn from its data-lit-by lights
    that are computed results. None when there is none (no recording buttons)."""
    labels = display_labels(model)
    for p in model.panels:
        lits = [v for v in p.lits if v in labels]
        if p.role == "fma" and lits:
            return {"name": p.name, "label": p.label or p.name, "html": p.html, "vars": lits}
    return None


class _LitText(HTMLParser):
    """Collects the text inside each element bound with data-lit-by."""

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
            "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__()
        self.open: list[tuple[str, str | None]] = []     # (tag, lit variable or None)
        self.text: dict[str, str] = {}
        self.named: dict[str, str] = {}     # aria-label or title, for an element with no text

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID:
            return
        a = dict(attrs)
        var = a.get("data-lit-by")
        self.open.append((tag, var))
        if var:
            self.text.setdefault(var, "")
            self.named.setdefault(var, a.get("aria-label") or a.get("title") or "")

    def handle_endtag(self, tag):
        while self.open:
            if self.open.pop()[0] == tag:
                break

    def handle_data(self, data):
        for _tag, var in self.open:
            if var:
                self.text[var] += data


def display_labels(model: Model) -> dict[str, str]:
    """Result variables shown on a panel -> how the text timeline names them.

    A data-lit-by result is named by its panel and the text it lights, e.g.
    "Flight mode annunciator: SPD (fma_tm_engaged_spd)"; a data-show result
    by its panel and name. Inputs and states are left out: input changes and
    transitions are already in the timeline.
    """
    plain = {i.name for i in model.inputs} | {sm.name for sm in model.state_machines}
    labels: dict[str, str] = {}
    for p in model.panels:
        parser = _LitText()
        parser.feed(p.html)
        panel = p.label or p.name
        for var in p.lits:
            if var in plain or var in labels:
                continue
            text = " ".join(parser.text.get(var, "").split()) or parser.named.get(var, "")
            labels[var] = f"{panel}: {text} ({var})" if text else f"{panel}: {var}"
        for var in p.shows:
            if var not in plain and var not in labels:
                labels[var] = f"{panel}: {var}"
    return labels


class Session:
    """Owns the Engine and everything the controls can change."""

    def __init__(self, model: Model, trace=None) -> None:
        self.model = model
        self.trace = trace
        self.inputs = {i.name: i for i in model.inputs}
        schedule = build_schedule(model)
        # A pulse lasts one period of the slowest band, so every band sees it.
        self.pulse_ticks = max((it.period_ticks for it in schedule), default=1)
        self.lit_vars = sorted({i.lit_by for i in model.inputs if i.lit_by}
                               | {v for p in model.panels for v in p.lits})
        # Variables a panel shows (data-show): sent with every state message.
        self.shown_vars = sorted({v for p in model.panels for v in p.shows})
        self.mode = "realtime"
        self.paused = False
        self.displays = display_labels(model)
        self.timeline = Timeline(gen=1, watch=self.displays)
        self.engine = Engine(model, _FanOut(trace, self.timeline))
        self.releases: dict[str, int] = {}
        self._taken = (self.timeline.gen, 0)   # (gen, last item id already handed out)

    # ------------------------------------------------------------- running
    @property
    def tick_hz(self) -> Fraction:
        return Fraction(self.model.tick_hz)

    def step(self) -> None:
        """Run one tick, then end any pulse that has lasted pulse_ticks."""
        self.engine.step()
        tick = self.engine.tick
        for name, at in list(self.releases.items()):
            if tick >= at:
                del self.releases[name]
                self.engine.set_input(name, False)

    def reset(self) -> None:
        """Back to start values; keeps the model, run mode and pause state."""
        self.timeline = Timeline(gen=self.timeline.gen + 1, watch=self.displays)
        self.engine = Engine(self.model, _FanOut(self.trace, self.timeline))
        self.releases.clear()

    # ------------------------------------------------------------ messages
    def handle(self, msg: dict) -> str | None:
        """Apply one browser message. Returns an error text or None.

        Messages: {"type": "set", "name", "value"}, {"type": "press", "name"},
        {"type": "toggle", "name"} (flips a toggle button's bool input),
        {"type": "mode", "mode": "realtime"|"fast"}, {"type": "pause"},
        {"type": "resume"}, {"type": "step"}, {"type": "reset"}.
        """
        kind = msg.get("type")
        if kind in ("set", "toggle", "press") and not isinstance(msg.get("name"), str):
            return f"{kind}: name must be a string, not {msg.get('name')!r}"
        if kind == "set":
            return self._set(msg.get("name"), msg.get("value"))
        if kind == "toggle":
            name = msg.get("name")
            i = self.inputs.get(name)
            if i is None or i.widget != "toggle":
                return f"{name!r} is not a toggle button"
            self.engine.set_input(name, not self.engine.snapshot()["inputs"][name])
            return None
        if kind == "press":
            name = msg.get("name")
            i = self.inputs.get(name)
            if i is None or i.widget not in ("momentary", "lit"):
                return f"{name!r} is not a push-button"
            if self.engine.snapshot()["inputs"][name] is not True:
                self.engine.set_input(name, True)
            self.releases[name] = self.engine.tick + self.pulse_ticks
            return None
        if kind == "mode":
            if msg.get("mode") not in MODES:
                return f"unknown mode {msg.get('mode')!r}"
            self.mode = msg["mode"]
            return None
        if kind == "pause":
            self.paused = True
            return None
        if kind == "resume":
            self.paused = False
            return None
        if kind == "step":
            if not self.paused:
                return "step is only available while paused"
            try:
                self.step()
            except EvaluationError as exc:        # stays paused; Reset gives a working run
                return f"Paused: {exc}"
            return None
        if kind == "reset":
            self.reset()
            return None
        return f"unknown message type {kind!r}"

    def _set(self, name, value) -> str | None:
        i = self.inputs.get(name)
        if i is None:
            return f"unknown input {name!r}"
        if i.widget in ("momentary", "lit"):
            return f"{name!r} is a push-button; use press"
        kind = i.type_name
        try:
            if kind == "bool":
                if not isinstance(value, bool):
                    raise ValueError
            elif kind in ("int", "float"):
                # a JSON number only (not a bool, not text), and finite: NaN would
                # pass min/max and Infinity is not valid JSON in the state messages
                if isinstance(value, bool) or not isinstance(value, (int, float))                         or not math.isfinite(value):
                    raise ValueError
                if kind == "int":
                    if value != int(value):
                        raise ValueError
                    value = int(value)
                else:
                    value = float(value)
            elif kind == "enum":
                if value not in i.choices:
                    raise ValueError
            elif not isinstance(value, str):
                raise ValueError
        except (TypeError, ValueError, OverflowError):
            return f"invalid value {value!r} for {kind} input {name!r}"
        if kind in ("int", "float"):
            if (i.min is not None and value < i.min) or (i.max is not None and value > i.max):
                return f"{value!r} is outside {name!r} min/max"
        self.engine.set_input(name, value)
        return None

    def timeline_message(self) -> dict:
        """The whole timeline so far, for a client that connects or after a reset."""
        return {"type": "timeline", "gen": self.timeline.gen, "items": self.timeline.all()}

    def timeline_text(self) -> str:
        """The current run's timeline as plain text (statesim.format_text)."""
        labels = {sm.name: sm.label for sm in self.model.state_machines}
        title = f"StateSim timeline: {self.model.master_path} (run {self.timeline.gen})"
        return format_text(self.timeline.all(), labels, title, self.displays)

    def take_new_items(self) -> tuple[list[dict], bool]:
        """Items added since the previous call (each is returned once, in order),
        and whether there are too many (more than MAX_DELTA) for a delta."""
        tl = self.timeline
        gen, last = self._taken
        if gen != tl.gen:
            last = 0
        items = tl.items_since(last)
        self._taken = (tl.gen, tl.last_id)
        return items, len(items) > MAX_DELTA

    def state(self) -> dict:
        """The changing values the browser shows."""
        snap = self.engine.snapshot()
        return {
            "type": "state",
            "states": snap["states"],
            "inputs": {n: json_value(v) for n, v in snap["inputs"].items()},
            "lit": {v: bool(self._value(snap, v)) for v in self.lit_vars},
            "values": {v: json_value(self._value(snap, v)) for v in self.shown_vars},
            "mode": self.mode,
            "paused": self.paused,
            "t": snap["t"],
            "gen": self.timeline.gen,
        }

    @staticmethod
    def _value(snap: dict, name: str):
        for part in ("outputs", "inputs", "states"):
            if name in snap[part]:
                return snap[part][name]
        return False
