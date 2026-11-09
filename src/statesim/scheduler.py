"""Execution plan, built once at load (docs/decisions.md items 1, 4, 5)."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from .model import Model


@dataclass(frozen=True)
class ScheduleItem:
    """One schedulable unit: a standalone equation or a whole state machine.

    ``name`` is the equation's result_variable or the state machine name.
    ``order`` is EquationDef.order or StateMachine.master_order (one shared
    ordering space within a band). ``period_ticks`` = model.tick_hz / band_hz
    (always a positive int). ``seq`` is the declaration index used to break
    (band, order) ties: items are enumerated in master-file row order; a
    state_machine row yields one item, the equations row yields one item per
    equation in CSV row order; seq is the 0-based position in that
    enumeration (inputs rows yield nothing).
    """

    kind: Literal["equation", "state_machine"]
    name: str
    band_hz: Fraction
    order: Fraction
    period_ticks: int
    seq: int


def build_schedule(model: Model) -> tuple[ScheduleItem, ...]:
    """Return every equation and state machine of ``model`` as ScheduleItems,
    sorted by the key ``(-band_hz, order, seq)``: higher frequency first,
    then ascending ``order``, then declaration ``seq``. Never depends on dict
    or set iteration order. Pure function of the model.
    """
    items: list[ScheduleItem] = []
    for sm in model.state_machines:
        items.append(
            ScheduleItem(
                kind="state_machine",
                name=sm.name,
                band_hz=sm.band_hz,
                order=sm.master_order,
                period_ticks=_period_ticks(model.tick_hz, sm.band_hz, sm.name),
                seq=len(items),
            )
        )
    for eq in model.equations:
        items.append(
            ScheduleItem(
                kind="equation",
                name=eq.result_variable,
                band_hz=eq.band_hz,
                order=eq.order,
                period_ticks=_period_ticks(model.tick_hz, eq.band_hz, eq.result_variable),
                seq=len(items),
            )
        )
    items.sort(key=lambda it: (-it.band_hz, it.order, it.seq))
    return tuple(items)


def _period_ticks(tick_hz: Fraction, band_hz: Fraction, name: str) -> int:
    ratio = Fraction(tick_hz) / Fraction(band_hz)
    if ratio.denominator != 1 or ratio < 1:
        raise ValueError(f"{name}: tick_hz {tick_hz} / band_hz {band_hz} is not a positive int")
    return int(ratio)


def due_items(schedule: tuple[ScheduleItem, ...], tick: int) -> tuple[ScheduleItem, ...]:
    """Items to run on ``tick`` (tick >= 1, the value after step() increments
    it): those with ``(tick - 1) % period_ticks == 0``, so every band runs on
    tick 1. Preserves ``schedule`` order (already sorted by build_schedule).
    """
    if tick < 1:
        raise ValueError(f"tick must be >= 1, got {tick}")
    return tuple(it for it in schedule if (tick - 1) % it.period_ticks == 0)
