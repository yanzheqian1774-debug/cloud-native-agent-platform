"""Bound schedule and default-off composition; no clocks or models advanced."""

from datetime import UTC, datetime, timedelta

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.fixed_work_bound_composition import compose_bound_cycle_service
from agent_console.fixed_work_bound_policy import ScheduleWindow, compile_windows
from pydantic import ValidationError
from test_fixed_work_service_schedule import WORK, trigger


def test_two_days_compile_to_exact_revision_and_complete_windows():
    window = ScheduleWindow(
        notBefore=datetime(2026, 11, 19, tzinfo=UTC),
        expiresAt=datetime(2026, 11, 21, tzinfo=UTC),
        windowSeconds=60,
    )
    slots = compile_windows(WORK, trigger(), window)
    assert len(slots) == 2
    assert list(slots.values()) == [
        (
            datetime(2026, 11, day, 1, tzinfo=UTC),
            datetime(2026, 11, day, 1, 1, tzinfo=UTC),
        )
        for day in (19, 20)
    ]
    assert slots == compile_windows(WORK, trigger(), window)
    assert not set(slots) & set(
        compile_windows(
            WORK.model_copy(update={"revision_id": "another"}), trigger(), window
        )
    )
    assert all(end <= window.expiresAt for _, end in slots.values())


@pytest.mark.parametrize("day,clock", [(8, "02:30"), (1, "01:30")])
def test_dst_gap_or_fold_not_guessed(day, clock):
    month = 3 if day == 8 else 11
    start = datetime(2026, month, day, tzinfo=UTC)
    window = ScheduleWindow(
        notBefore=start, expiresAt=start + timedelta(days=1), windowSeconds=60
    )
    with pytest.raises(AuthorityError, match="AMBIGUOUS_OR_MISSING"):
        compile_windows(WORK, trigger("America/New_York", clock), window)


@pytest.mark.parametrize(
    "change",
    [
        dict(windowSeconds=0),
        dict(windowSeconds=3601),
        dict(notBefore=datetime(2026, 1, 1)),
        dict(expiresAt=datetime(2027, 1, 1, tzinfo=UTC)),
    ],
)
def test_finite_aware_bounds(change):
    with pytest.raises(ValidationError):
        ScheduleWindow(
            **{
                **dict(
                    notBefore=datetime(2026, 1, 1, tzinfo=UTC),
                    expiresAt=datetime(2026, 1, 2, tzinfo=UTC),
                    windowSeconds=60,
                ),
                **change,
            }
        )


def test_no_event_matching_or_empty_partial_slot():
    window = ScheduleWindow(
        notBefore=datetime(2026, 11, 19, 1, tzinfo=UTC),
        expiresAt=datetime(2026, 11, 19, 1, 0, 30, tzinfo=UTC),
        windowSeconds=60,
    )
    with pytest.raises(ValueError, match="complete bounded"):
        compile_windows(WORK, trigger(), window)
    with pytest.raises(ValueError, match="event matching"):
        compile_windows(WORK, dict(kind="EVENT", eventDescription="收到新文档"), window)


def test_bound_composition_off_does_not_read_or_start_any_owner():
    def forbidden():
        raise AssertionError("disabled composition read a credential")

    assert (
        compose_bound_cycle_service(
            foundation=None,
            planning_factory=None,
            readonly_owner=None,
            policy_path="/not-read",
            credential_reader=forbidden,
        )
        is None
    )


def test_policy_loader_keeps_malformed_document_closed(tmp_path):
    from agent_console.fixed_work_service_policy import ServicePlanningPolicy

    path = tmp_path / "policy.json"
    path.write_text("[]")
    path.chmod(0o600)
    with pytest.raises(AuthorityError, match="POLICY_UNAVAILABLE"):
        ServicePlanningPolicy.load(path)
