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
