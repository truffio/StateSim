"""Timeline recorder: turns trace events into JSON-ready timeline items.

Contract (docs/timeline_plan.md, T0); implemented in T3 (issue #15).

A ``Timeline`` is a TraceSink. It keeps two kinds of items, each a plain dict
with a sequential integer ``id`` (starting at 1, never reused) and ``t`` as
float milliseconds:

* transition: ``{"k": "tr", "id", "t", "tick", "sm", "tid", "title",
  "from", "to", "causes": [ids], "writes": [[var, value], ...]}``
* display change: ``{"k": "dp", "id", "t", "tick", "name", "value",
  "causes": [ids]}`` for a result variable in ``watch`` (a value shown on a
  panel, such as an FMA mode text), each time it changes. The pane ignores
  these items; the text timeline lists them. They are never a cause.
* input change: ``{"k": "in", "id", "t", "tick", "name", "value"}``; a
  ``set_input`` that leaves the value unchanged gives no item.

``causes`` are the ids of the input changes and transitions that produced
the names in the transition's ``trigger``, folded through equations and row
results (see docs/future_timeline.md section 2). ``writes`` are the exit and
entry action writes of that transition, in the order they ran. Ids in
``causes`` may refer to items already dropped by the cap.

Only the most recent ``cap`` items are kept (the oldest are dropped).

How the recorder works (all state is per ``Timeline``; nothing is global):

* ``origins[var]`` is the small set of item ids (input changes and
  transitions) that last produced the value of ``var``. A ``result`` event
  gives no item: it sets ``origins[var]`` to the union of the origins of its
  ``trigger`` names, which is how equations pass a cause through.
* Exit action writes arrive before their transition: they are held per state
  machine and attached when that machine's transition arrives in the same
  tick. Entry writes arrive after it and are appended to the item already
  stored. So a transition's dict is mutated after it was added; this is safe
  because the engine emits the entry writes in the same tick, inside the same
  ``step()`` call, before any consumer can read the items.
* ``during`` and ``init`` writes give no item; the written variable takes the
  machine's last transition as its origin (none if it never changed state).
* An origin set never holds more than ``MAX_ORIGINS`` ids (the newest are
  kept), so memory stays bounded even if results feed back into themselves.
* Values are made JSON-ready: bool, int, float, str and None are kept,
  ``Fraction`` becomes float, anything else becomes ``str(value)``.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Iterable
from fractions import Fraction

from .trace import TraceEvent

DEFAULT_CAP = 20_000
MAX_ORIGINS = 64

_NO_ORIGIN: frozenset[int] = frozenset()


def json_value(value: object) -> object:
    """A value that JSON can carry: bool/int/str/None and finite floats
    unchanged, Fraction -> float (``t`` and ``dt`` written by an action),
    NaN/Infinity -> their str() (not valid JSON), anything else -> str()."""
    if isinstance(value, Fraction):
        value = float(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if value is None or isinstance(value, (bool, int, str)):
        return value
    return str(value)


_json_value = json_value


class Timeline:
    """Records timeline items from trace events.

    ``gen`` identifies the run (the session sets a new one on Reset);
    ``last_id`` is the id of the newest item (0 when empty).
    """

    def __init__(self, gen: int = 1, cap: int = DEFAULT_CAP,
                 watch: Iterable[str] = ()) -> None:
        self.gen = gen
        self.cap = cap
        # result variables shown on a panel (e.g. the FMA): their changes
        # become "dp" items, so the text timeline records what was displayed
        self.watch = frozenset(watch)
        self.last_id = 0
        self._items: deque[dict] = deque(maxlen=max(0, cap))
        self._origins: dict[str, frozenset[int]] = {}
        # sm -> (tick, [[var, value], ...]): exit writes waiting for their transition
        self._held: dict[str, tuple[int, list[list]]] = {}
        # sm -> (tick, item) of that machine's latest transition
        self._last_tr: dict[str, tuple[int, dict]] = {}

    # -- TraceSink ---------------------------------------------------------

    def emit(self, event: TraceEvent) -> None:
        """Accept one trace event (TraceSink protocol)."""
        kind = event.kind
        if kind == "input":
            self._on_input(event)
        elif kind == "result":
            self._origins[event.name] = self._union(event.trigger)
            if event.name in self.watch:
                self._items.append({
                    "k": "dp", "id": self._next_id(), "t": float(event.t), "tick": event.tick,
                    "name": event.name, "value": _json_value(event.new),
                    "causes": sorted(self._origins[event.name]),
                })
        elif kind == "transition":
            self._on_transition(event)
        elif kind == "action":
            self._on_action(event)
        # kind "" (old-style event) or unknown: ignored

    # -- readers -----------------------------------------------------------

    def items_since(self, last_id: int) -> list[dict]:
        """Items with id > last_id that are still kept, oldest first."""
        out: list[dict] = []
        for item in reversed(self._items):
            if item["id"] <= last_id:
                break
            out.append(item)
        out.reverse()
        return out

    def all(self) -> list[dict]:
        """Every kept item, oldest first."""
        return list(self._items)

    # -- internals ---------------------------------------------------------

    def _next_id(self) -> int:
        self.last_id += 1
        return self.last_id

    def _union(self, names) -> frozenset[int]:
        origins = self._origins
        out: set[int] = set()
        for n in names:
            out |= origins.get(n, _NO_ORIGIN)
        if len(out) > MAX_ORIGINS:
            out = set(sorted(out)[-MAX_ORIGINS:])
        return frozenset(out)

    def _on_input(self, e: TraceEvent) -> None:
        if e.old == e.new and type(e.old) is type(e.new):
            return
        item_id = self._next_id()
        self._items.append({
            "k": "in", "id": item_id, "t": float(e.t), "tick": e.tick,
            "name": e.name, "value": _json_value(e.new),
        })
        self._origins[e.name] = frozenset((item_id,))

    def _on_transition(self, e: TraceEvent) -> None:
        sm = e.component
        causes = sorted(self._union(e.trigger))
        writes: list[list] = []
        held = self._held.pop(sm, None)
        if held is not None and held[0] == e.tick:
            writes = held[1]
        item_id = self._next_id()
        item = {
            "k": "tr", "id": item_id, "t": float(e.t), "tick": e.tick,
            "sm": sm, "tid": e.label, "title": e.title,
            "from": _json_value(e.old), "to": _json_value(e.new),
            "causes": causes, "writes": writes,
        }
        self._items.append(item)
        origin = frozenset((item_id,))
        self._origins[sm] = origin
        for var, _value in writes:
            self._origins[var] = origin
        self._last_tr[sm] = (e.tick, item)

    def _on_action(self, e: TraceEvent) -> None:
        sm = e.component
        write = [e.name, _json_value(e.new)]
        if e.phase == "exit":
            held = self._held.get(sm)
            if held is None or held[0] != e.tick:  # stale exits are dropped
                held = self._held[sm] = (e.tick, [])
            held[1].append(write)
            return
        last = self._last_tr.get(sm)
        if e.phase == "entry" and last is not None and last[0] == e.tick:
            last[1]["writes"].append(write)
        # entry (attached above), during, init, or an entry with no transition
        # in this tick: the origin is the machine's last transition, if any
        self._origins[e.name] = (
            frozenset((last[1]["id"],)) if last is not None else _NO_ORIGIN
        )


# ------------------------------------------------------------------ text
def _text_value(value: object) -> str:
    """Values as in the trace: strings quoted, everything else with str()."""
    return repr(value) if isinstance(value, str) else str(value)


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" + ("" if n == 1 else "s")


def format_text(items: list[dict], labels: dict[str, str] | None = None,
                title: str = "", displays: dict[str, str] | None = None) -> str:
    """The timeline as plain text: a readable reconstruction of the run.

    One entry per item, in time order, each starting with ``#<id>`` and the
    time in seconds:

    * an input change: ``INPUT  <name> = <value>``;
    * a display change (a ``dp`` item, e.g. an FMA mode text):
      ``DISPLAY  <label> on`` / ``off`` (``= <value>`` when not a bool),
      then what caused it;
    * a transition: ``<machine>  <tid>  <from> -> <to>  "<title>"``, then
      ``caused by:`` the items that led to it (``#id`` plus a short name) or
      ``no recorded cause`` (a timer, or a value already true at the start),
      then ``writes:`` its exit and entry action writes, if any.

    ``labels`` maps a state machine name to its display name (the master
    CSV ``name``); a machine without one is shown by its name. ``title`` is
    the first line (for example the master file). Causes dropped by the cap
    are shown as ``#id (no longer kept)``.
    """
    labels = labels or {}
    displays = displays or {}
    by_id = {it["id"]: it for it in items}

    def machine(sm: str) -> str:
        label = labels.get(sm) or sm
        return label if label == sm else f"{label} ({sm})"

    def short(it: dict) -> str:
        if it["k"] == "in":
            return f"#{it['id']} input {it['name']} = {_text_value(it['value'])}"
        return f"#{it['id']} {labels.get(it['sm']) or it['sm']} {it['tid']} -> {it['to']}"

    inputs = sum(1 for it in items if it["k"] == "in")
    shown = sum(1 for it in items if it["k"] == "dp")
    counts = [_count(inputs, "input change"), _count(len(items) - inputs - shown, "transition")]
    if shown:
        counts.append(_count(shown, "display change"))
    lines = [title or "StateSim timeline",
             ", ".join(counts) + "; times in seconds.",
             "Each transition and display change lists what caused it (inputs and other",
             "transitions, through any equations); transitions also list what their",
             "actions wrote."]
    if items and items[0]["id"] > 1:
        lines.append(f"Items #1 to #{items[0]['id'] - 1} are no longer kept "
                     "(only the most recent are).")
    lines.append("")
    width = len(str(items[-1]["id"])) + 1 if items else 2
    pad = " " * (width + 2 + 8 + 4)        # under the machine name: "#id", time, " s  "
    for it in items:
        head = f"{'#' + str(it['id']):<{width}}  {it['t'] / 1000:8.3f} s  "
        if it["k"] == "in":
            lines.append(f"{head}INPUT  {it['name']} = {_text_value(it['value'])}")
            continue
        if it["k"] == "dp":
            v = it["value"]
            state = ("on" if v else "off") if isinstance(v, bool) else f"= {_text_value(v)}"
            lines.append(f"{head}DISPLAY  {displays.get(it['name']) or it['name']} {state}")
            lines.append(f"{pad}caused by: " + "; ".join(
                short(by_id[c]) if c in by_id else f"#{c} (no longer kept)" for c in it["causes"])
                if it["causes"] else f"{pad}no recorded cause")
            continue
        text = f"{head}{machine(it['sm'])}  {it['tid']}  {it['from']} -> {it['to']}"
        if it.get("title"):
            text += f'  "{it["title"]}"'
        lines.append(text)
        if it["causes"]:
            causes = [short(by_id[c]) if c in by_id else f"#{c} (no longer kept)"
                      for c in it["causes"]]
            lines.append(f"{pad}caused by: " + "; ".join(causes))
        else:
            lines.append(f"{pad}no recorded cause (a timer, or true from the start)")
        if it["writes"]:
            lines.append(f"{pad}writes: " + ", ".join(
                f"{var} = {_text_value(value)}" for var, value in it["writes"]))
    return "\n".join(lines) + "\n"
