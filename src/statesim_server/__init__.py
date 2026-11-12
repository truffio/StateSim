"""StateSim front end server: runs a model and serves its web page.

Install with ``pip install -e ".[server]"`` and start with
``python -m statesim_server path/to/master.csv``.
"""

from .session import Session, describe_model

__all__ = ["Session", "describe_model"]
