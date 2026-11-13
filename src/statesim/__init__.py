"""statesim: deterministic engine for CSV-defined state machines and equations."""

from . import constants
from .engine import Engine
from .errors import EvaluationError, ModelError
from .loader import load_model
from .model import Model
from .timeline import Timeline
from .trace import FileTraceWriter, ListTraceSink, TraceEvent, TraceSink, format_event

__all__ = [
    "load_model",
    "Engine",
    "Model",
    "TraceEvent",
    "FileTraceWriter",
    "ListTraceSink",
    "Timeline",
    "ModelError",
    "EvaluationError",
    "TraceSink",
    "format_event",
    "constants",
]
