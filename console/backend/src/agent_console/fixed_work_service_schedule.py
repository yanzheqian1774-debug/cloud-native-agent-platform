"""Pure bounded slot computation. No timer, backfill, credentials or invocation."""

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from .digital_employee_definition import digest
from .fixed_work_authoring import TriggerDraft
from .fixed_work_service_admission import require


def scheduled_event(work, trigger: TriggerDraft, local_date):
    """Return a stable per-work UTC slot; reject ambiguous/nonexistent wall time.

    An operator's bounded service policy still has to independently include the
    returned event and dispatch window. Saving natural-language configuration
    does not authorize this slot or start a timer.
    """
    require(trigger.kind == "SCHEDULE", "FIXED_WORK_NOT_A_SCHEDULE")
    if trigger.cadence == "WEEKDAY" and local_date.weekday() >= 5:
        return None
    zone = ZoneInfo(trigger.timezone)
    hour, minute = map(int, trigger.localTime.split(":"))
    wall = datetime.combine(local_date, time(hour, minute))
    possible = {
        wall.replace(tzinfo=zone, fold=fold).astimezone(UTC)
        for fold in (0, 1)
        if wall.replace(tzinfo=zone, fold=fold)
        .astimezone(UTC)
        .astimezone(zone)
        .replace(tzinfo=None)
        == wall
    }
    require(len(possible) == 1, "FIXED_WORK_AMBIGUOUS_OR_MISSING_LOCAL_TIME")
    slot = possible.pop()
    event = "schedule:" + digest([work.model_dump(mode="json"), slot.isoformat()])
    return event, slot


def due_events(policy, now):
    """No missed-slot replay: return only explicitly approved windows open now."""
    require(now.tzinfo is not None)
    if not policy.enabled or now >= policy.expiresAt:
        return ()
    return tuple(
        sorted(
            event
            for event in policy.allowedEventIds
            if policy.eventWindows[event][0] <= now < policy.eventWindows[event][1]
        )
    )
