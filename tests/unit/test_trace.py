"""Unit tests for statesim.trace (log line format, sinks)."""

from __future__ import annotations

from fractions import Fraction

import pytest

from statesim.trace import (
    FileTraceWriter,
    ListTraceSink,
    TraceEvent,
    TraceSink,
    format_event,
    format_value,
)


def _event(
    tick: int = 12,
    t: Fraction = Fraction(1100),
    component: str = "AP",
    action: str = 'T3 OFF->ARMED "title"',
    values: tuple[tuple[str, object], ...] = (("alt", 1000), ("ap_sw", True)),
) -> TraceEvent:
    return TraceEvent(tick=tick, t=t, component=component, action=action, values=values)


# --- format_value -----------------------------------------------------------


def test_format_value_str_uses_repr() -> None:
    assert format_value("ENGAGED") == "'ENGAGED'"


def test_format_value_fraction_is_six_decimals() -> None:
    assert format_value(Fraction(1, 3)) == "0.333333"
    assert format_value(Fraction(6, 25)) == "0.240000"


def test_format_value_other_types_use_str() -> None:
    assert format_value(True) == "True"
    assert format_value(False) == "False"
    assert format_value(1000) == "1000"
    assert format_value(2.5) == "2.5"


def test_format_value_int_is_not_fraction_formatted() -> None:
    # An int must not be rendered with six decimals.
    assert format_value(3) == "3"


# --- format_event -----------------------------------------------------------


def test_format_event_matches_decisions_example() -> None:
    line = format_event(_event())
    assert line == 'tick=000012 t=1100.000 | AP | T3 OFF->ARMED "title" | alt=1000, ap_sw=True'


def test_format_event_without_values_has_no_trailing_separator() -> None:
    line = format_event(_event(values=()))
    assert line == 'tick=000012 t=1100.000 | AP | T3 OFF->ARMED "title"'
    assert not line.endswith("|")
    assert not line.endswith(" ")


def test_format_event_has_no_newline() -> None:
    assert "\n" not in format_event(_event())


def test_format_event_tick_is_zero_padded_to_six() -> None:
    assert format_event(_event(tick=0, values=())).startswith("tick=000000 ")
    assert format_event(_event(tick=1234567, values=())).startswith("tick=1234567 ")


def test_format_event_time_uses_three_decimals_exact_fraction() -> None:
    line = format_event(_event(t=Fraction(1000, 3), values=()))
    assert " t=333.333 " in line


def test_format_event_values_rendered_in_given_order_with_types() -> None:
    event = _event(
        action="x",
        values=(("a", "ON"), ("b", Fraction(1, 2)), ("c", 7)),
    )
    assert format_event(event).endswith(" | a='ON', b=0.500000, c=7")


def test_format_event_input_action_line() -> None:
    event = _event(
        tick=5,
        t=Fraction(50),
        component="INPUT",
        action="set alt 0->1000",
        values=(("alt", 1000),),
    )
    assert format_event(event) == "tick=000005 t=50.000 | INPUT | set alt 0->1000 | alt=1000"


# --- ListTraceSink ----------------------------------------------------------


def test_list_sink_starts_empty() -> None:
    sink = ListTraceSink()
    assert sink.events == []
    assert sink.lines() == []


def test_list_sink_keeps_events_in_emission_order() -> None:
    sink = ListTraceSink()
    first = _event(tick=1, values=())
    second = _event(tick=2, values=())
    sink.emit(first)
    sink.emit(second)
    assert sink.events == [first, second]


def test_list_sink_lines_match_format_event() -> None:
    sink = ListTraceSink()
    events = [_event(tick=1), _event(tick=2, values=())]
    for e in events:
        sink.emit(e)
    assert sink.lines() == [format_event(e) for e in events]


def test_list_sink_satisfies_protocol_by_duck_typing() -> None:
    sink: TraceSink = ListTraceSink()
    sink.emit(_event())
    assert len(sink.lines()) == 1  # type: ignore[attr-defined]


# --- FileTraceWriter --------------------------------------------------------


def test_file_writer_writes_one_line_per_event(tmp_path) -> None:
    path = tmp_path / "trace.log"
    events = [_event(tick=1), _event(tick=2, values=())]
    writer = FileTraceWriter(path)
    for e in events:
        writer.emit(e)
    writer.close()

    expected = "\n".join(format_event(e) for e in events) + "\n"
    assert path.read_bytes() == expected.encode("utf-8")


def test_file_writer_uses_lf_newlines(tmp_path) -> None:
    path = tmp_path / "trace.log"
    with FileTraceWriter(path) as writer:
        writer.emit(_event())
        writer.emit(_event(tick=13))
    raw = path.read_bytes()
    assert b"\r" not in raw
    assert raw.count(b"\n") == 2


def test_file_writer_flushes_on_each_emit(tmp_path) -> None:
    path = tmp_path / "trace.log"
    writer = FileTraceWriter(path)
    try:
        writer.emit(_event(values=()))
        # Readable before close: emit must flush.
        assert path.read_text(encoding="utf-8") == format_event(_event(values=())) + "\n"
    finally:
        writer.close()


def test_file_writer_truncates_existing_file(tmp_path) -> None:
    path = tmp_path / "trace.log"
    path.write_text("stale content\n", encoding="utf-8")
    with FileTraceWriter(path):
        pass
    assert path.read_text(encoding="utf-8") == ""


def test_file_writer_context_manager_closes_file(tmp_path) -> None:
    path = tmp_path / "trace.log"
    with FileTraceWriter(path) as writer:
        assert isinstance(writer, FileTraceWriter)
        writer.emit(_event())
    assert writer._file.closed


def test_file_writer_close_is_idempotent(tmp_path) -> None:
    writer = FileTraceWriter(tmp_path / "trace.log")
    writer.close()
    writer.close()  # must not raise


def test_file_writer_is_utf8(tmp_path) -> None:
    path = tmp_path / "trace.log"
    with FileTraceWriter(path) as writer:
        writer.emit(_event(action="T1 A->B \"Zustand äö\""))
    assert "äö" in path.read_text(encoding="utf-8")


def test_file_writer_is_deterministic(tmp_path) -> None:
    events = [_event(tick=i, t=Fraction(i, 7), values=(("x", i),)) for i in range(5)]
    outputs = []
    for name in ("a.log", "b.log"):
        path = tmp_path / name
        with FileTraceWriter(path) as writer:
            for e in events:
                writer.emit(e)
        outputs.append(path.read_bytes())
    assert outputs[0] == outputs[1]


@pytest.mark.req("REQ-160", "REQ-165")
def test_structured_fields_default_and_do_not_change_the_line():
    from fractions import Fraction
    plain = TraceEvent(3, Fraction(200), "AP", 'T1 OFF->ON "Go"', (("sw", True),))
    for f, v in (("kind", ""), ("name", ""), ("old", None), ("new", None), ("trigger", ()),
                 ("label", ""), ("title", ""), ("phase", "")):
        assert getattr(plain, f) == v
    rich = TraceEvent(3, Fraction(200), "AP", 'T1 OFF->ON "Go"', (("sw", True),), kind="transition",
                      name="AP", old="OFF", new="ON", trigger=("sw",), label="T1", title="Go")
    assert format_event(rich) == format_event(plain)
