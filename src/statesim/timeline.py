"""Timeline recorder: turns trace events into JSON-ready timeline items.

Contract (docs/timeline_plan.md, T0); implemented in T3 (issue #15).

A ``Timeline`` is a TraceSink. It keeps two kinds of items, each a plain dict
with a sequential integer ``id`` (starting at 1, never reused) and ``t`` as
float milliseconds:

* transition: ``{"k": "tr", "id", "t", "tick", "sm", "tid", "title",
  "from", "to", "causes": [ids], "writes": [[var, value], ...]}``
* input change: ``{"k": "in", "id", "t", "tick", "name", "value"}``; a
  ``set_input`` that leaves the value unchanged gives no item.

``causes`` are the ids of the input changes and transitions that produced
the names in the transition's ``trigger``, folded through equations and row
results (see docs/future_timeline.md section 2). ``writes`` are the exit and
entry action writes of that transition, in the order they ran. Ids in
``causes`` may refer to items already dropped by the cap.

Only the most recent ``cap`` items are kept (the oldest are dropped).
"""

from __future__ import annotations

from .trace import TraceEvent

DEFAULT_CAP = 20_000


class Timeline:
    """Records timeline items from trace events.

    ``gen`` identifies the run (the session sets a new one on Reset);
    ``last_id`` is the id of the newest item (0 when empty).
    """

    def __init__(self, gen: int = 1, cap: int = DEFAULT_CAP) -> None:
        self.gen = gen
        self.cap = cap
        self.last_id = 0

    def emit(self, event: TraceEvent) -> None:
        """Accept one trace event (TraceSink protocol)."""
        raise NotImplementedError("T3 (#15)")

    def items_since(self, last_id: int) -> list[dict]:
        """Items with id > last_id that are still kept, oldest first."""
        raise NotImplementedError("T3 (#15)")

    def all(self) -> list[dict]:
        """Every kept item, oldest first."""
        raise NotImplementedError("T3 (#15)")
