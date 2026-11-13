from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.fixed_work_authoring import TriggerDraft
from agent_console.fixed_work_service_schedule import due_events, scheduled_event
from agent_console.plan_suggestion_domain import ExactReference

WORK = ExactReference(resource_id="work:1", revision_id="revision:1", digest="a" * 64)


def trigger(zone="Asia/Shanghai", clock="09:00", cadence="DAILY"):
    return TriggerDraft(
        kind="SCHEDULE", timezone=zone, localTime=clock, cadence=cadence
    )


def test_stable_work_revision_scoped_slot_weekends_and_no_backfill():
    event, slot = scheduled_event(WORK, trigger(), date(2026, 11, 14))
    assert slot == datetime(2026, 11, 14, 1, tzinfo=UTC)
    assert scheduled_event(WORK, trigger(), date(2026, 11, 14)) == (event, slot)
    assert (
        scheduled_event(
            WORK.model_copy(update={"revision_id": "revision:2"}),
            trigger(),
            date(2026, 11, 14),
        )[0]
        != event
    )
    assert scheduled_event(WORK, trigger(cadence="WEEKDAY"), date(2026, 11, 14)) is None
    policy = SimpleNamespace(
        enabled=True,
        expiresAt=slot + timedelta(hours=1),
        allowedEventIds=(event,),
        eventWindows={event: (slot, slot + timedelta(minutes=1))},
    )
    assert due_events(policy, slot) == (event,)
    assert due_events(policy, slot - timedelta(seconds=1)) == ()
    assert due_events(policy, slot + timedelta(minutes=1)) == ()
    policy.enabled = False
    assert due_events(policy, slot) == ()


@pytest.mark.parametrize(
    "day,clock", [(date(2026, 3, 8), "02:30"), (date(2026, 11, 1), "01:30")]
)
def test_dst_ambiguity_or_gap_requires_explicit_business_choice(day, clock):
    with pytest.raises(AuthorityError, match="AMBIGUOUS_OR_MISSING_LOCAL_TIME"):
        scheduled_event(WORK, trigger("America/New_York", clock), day)


def test_disabled_composition_neither_reads_policy_nor_attaches_budget():
    from agent_console.fixed_work_service_runtime import ServicePlanningRuntime

    budget = SimpleNamespace()
    service = SimpleNamespace(
        application=SimpleNamespace(repository=object()), budget=budget
    )

    def unavailable():
        raise AssertionError("disabled policy must not be read")

    runtime = ServicePlanningRuntime(service, object(), unavailable)
    assert not hasattr(budget, "service_planning_admission")
    with pytest.raises(AuthorityError, match="SERVICE_DISABLED"):
        runtime.begin(None, "unknown")
    with pytest.raises(AuthorityError, match="SERVICE_DISABLED"):
        runtime.tick(None, now=datetime.now(UTC))


def test_continuation_requires_plan_read_before_owner_lookup():
    from agent_console.fixed_work_service_continuation import ServiceCycleContinuation
    from agent_console.readonly_continuation import ReadonlyContinuation

    class Denied:
        def require(self, principal, owner, action, target):
            assert (owner, action, target) == ("PLAN", "READ", "plan:v2:private")
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    def forbidden(_):
        raise AssertionError("Plan owner must not be read before permission")

    readonly = ReadonlyContinuation.__new__(ReadonlyContinuation)
    readonly.automation = SimpleNamespace(bound_app=forbidden)
    registry = SimpleNamespace(
        _policy=lambda: SimpleNamespace(allowedEventIds=("event",))
    )
    owner = ServiceCycleContinuation(registry, readonly, enabled=True)
    call = SimpleNamespace(
        connection=object(),
        context=SimpleNamespace(
            principal_id="service:test",
            scope=SimpleNamespace(tenant_id="t", security_domain="d"),
        ),
        path={"proposal_id": "private"},
        authority=Denied(),
    )
    with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
        owner.continue_once(call, "event")
