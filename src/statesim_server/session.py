"""One simulation session: the engine, run state, push-button pulses and the
messages exchanged with the browser. Synchronous and free of wall-clock time;
the server (server.py) decides when to call step()."""

from __future__ import annotations

from fractions import Fraction

from statesim import Engine, Model
from statesim.timeline import Timeline
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
            "panels": panels}


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
        self.timeline = Timeline(gen=1)
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
        self.timeline = Timeline(gen=self.timeline.gen + 1)
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
            self.step()
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
            elif kind == "int":
                if isinstance(value, bool) or float(value) != int(float(value)):
                    raise ValueError
                value = int(float(value))
            elif kind == "float":
                if isinstance(value, bool):
                    raise ValueError
                value = float(value)
            elif kind == "enum":
                if value not in i.choices:
                    raise ValueError
            elif not isinstance(value, str):
                raise ValueError
        except (TypeError, ValueError):
            return f"invalid value {value!r} for {kind} input {name!r}"
        if kind in ("int", "float"):
            if (i.min is not None and value < i.min) or (i.max is not None and value > i.max):
                return f"{value!r} is outside {name!r} min/max"
        self.engine.set_input(name, value)
        return None

    def timeline_message(self) -> dict:
        """The whole timeline so far, for a client that connects or after a reset."""
        return {"type": "timeline", "gen": self.timeline.gen, "items": self.timeline.all()}

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
            "inputs": snap["inputs"],
            "lit": {v: bool(self._value(snap, v)) for v in self.lit_vars},
            "values": {v: self._value(snap, v) for v in self.shown_vars},
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
