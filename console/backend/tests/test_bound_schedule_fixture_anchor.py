"""Deterministic old fixture race and its actual integration helper; no PG/model."""

from datetime import UTC, datetime, timedelta

import pytest
from agent_console.fixed_work_bound_policy import ScheduleWindow, compile_windows
from test_fixed_work_bound_composition_postgres import bound_schedule_fixture
from test_fixed_work_service_schedule import WORK

CLOCKS = [
    pytest.param(
        datetime(2026, 11, 28, 10, 4, 59, 829000, tzinfo=UTC),
        datetime(2026, 11, 28, 10, 5, 0, 668735, tzinfo=UTC),
        id="actual-microsecond-minute-boundary",
    ),
    pytest.param(
        datetime(2026, 11, 28, 23, 59, 59, 829000, tzinfo=UTC),
        datetime(2026, 11, 29, 0, 0, 0, 668735, tzinfo=UTC),
        id="utc-midnight-boundary",
    ),
]


@pytest.mark.parametrize("anchor,later", CLOCKS)
def test_old_two_clock_fixture_excludes_its_slot_by_microseconds(anchor, later):
    # Exact previous formulas, with the real unchanged production owner.
    trigger = dict(
        kind="SCHEDULE",
        timezone="UTC",
        cadence="DAILY",
        localTime=(anchor - timedelta(minutes=1)).strftime("%H:%M"),
    )
    window = ScheduleWindow(
        notBefore=later - timedelta(minutes=2),
        expiresAt=later + timedelta(hours=1),
        windowSeconds=600,
    )
    slot = (anchor - timedelta(minutes=1)).replace(second=0, microsecond=0)
    assert window.notBefore - slot == timedelta(microseconds=668735)
    with pytest.raises(
        ValueError, match="one to 128 complete bounded windows required"
    ):
        compile_windows(WORK, trigger, window)


@pytest.mark.parametrize("anchor,later", CLOCKS)
def test_actual_shared_fixture_helper_keeps_one_complete_original_window(anchor, later):
    trigger, not_before = bound_schedule_fixture(anchor)
    expiry = later + timedelta(hours=1)
    window = ScheduleWindow(notBefore=not_before, expiresAt=expiry, windowSeconds=600)
    slots = compile_windows(WORK, trigger, window)
    expected = (anchor - timedelta(minutes=1)).replace(second=0, microsecond=0)
    assert list(slots.values()) == [(expected, expected + timedelta(seconds=600))]
    assert window.notBefore == anchor - timedelta(minutes=2)
    assert window.expiresAt == expiry and window.windowSeconds == 600
    assert trigger == dict(
        kind="SCHEDULE",
        timezone="UTC",
        cadence="DAILY",
        localTime=(anchor - timedelta(minutes=1)).strftime("%H:%M"),
    )
