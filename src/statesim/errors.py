"""Exception types for statesim."""

from __future__ import annotations


class ModelError(Exception):
    """Raised for any load-time problem in the model definition files.

    Covers CSV structure problems, expression syntax errors and the load
    checks listed in docs/decisions.md (14). ``source`` locates the problem
    as ``"file:line"`` (file name as written in the master CSV, or the master
    file's own name; line numbers are 1-based physical CSV lines, header is
    line 1). ``source`` may be ``None`` for model-wide problems (e.g. limits).

    ``str(err)`` is ``"<source>: <msg>"`` when ``source`` is set, else ``msg``.
    """

    def __init__(self, msg: str, source: str | None = None) -> None:
        self.msg = msg
        self.source = source
        super().__init__(f"{source}: {msg}" if source else msg)


class EvaluationError(Exception):
    """Raised by ``Engine.step()`` when an expression fails at run time.

    Wraps the original exception (available as ``__cause__``). ``source`` is
    the ``"file:line"`` of the equation or transition row, ``tick`` the tick
    being run and ``item`` the schedule item (state machine name or standalone
    equation result variable). ``str(err)`` is
    ``"<source>: tick <tick>, <item>: <ExcType>: <text>"``.
    """

    def __init__(self, source: str, tick: int, item: str, original: BaseException) -> None:
        self.source = source
        self.tick = tick
        self.item = item
        self.original = original
        super().__init__(
            f"{source}: tick {tick}, {item}: {type(original).__name__}: {original}"
        )
