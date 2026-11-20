"""Exact confirmed-source policy successor; v1 records remain unchanged."""

from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .fixed_work_authoring import TriggerDraft
from .fixed_work_service_policy import ServicePlanningPolicy


class ScheduleWindow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    notBefore: datetime
    expiresAt: datetime
    windowSeconds: int = Field(strict=True, ge=1, le=3600)

    @model_validator(mode="after")
    def bounded(self):
        if (
            self.notBefore.tzinfo is None
            or self.expiresAt.tzinfo is None
            or not self.notBefore < self.expiresAt
            or self.expiresAt - self.notBefore > timedelta(days=128)
        ):
            raise ValueError("explicit aware window of at most 128 days required")
        return self


def compile_windows(work, trigger, window: ScheduleWindow):
    """Pure preview only. Returns no policy, credentials, grants or enable flag."""
    from zoneinfo import ZoneInfo

    from .fixed_work_service_schedule import scheduled_event

    trigger = TriggerDraft.model_validate(trigger)
    if trigger.kind != "SCHEDULE":
        raise ValueError("event matching is not configured")
    zone = ZoneInfo(trigger.timezone)
    day = window.notBefore.astimezone(zone).date()
    last = window.expiresAt.astimezone(zone).date()
    result = {}
    while day <= last:
        slot = scheduled_event(work, trigger, day)
        if slot is not None:
            event, instant = slot
            end = instant + timedelta(seconds=window.windowSeconds)
            if window.notBefore <= instant and end <= window.expiresAt:
                result[event] = (instant.astimezone(UTC), end.astimezone(UTC))
        day += timedelta(days=1)
    if not 1 <= len(result) <= 128:
        raise ValueError("one to 128 complete bounded windows required")
    return result


class BoundServicePlanningPolicy(ServicePlanningPolicy):
    schemaVersion: Literal["fixed-work-service-planning.v2"]
    sourceBindingDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    scheduleWindow: ScheduleWindow

    @model_validator(mode="after")
    def within_policy(self):
        if self.scheduleWindow.expiresAt > self.expiresAt:
            raise ValueError("schedule cannot outlive policy")
        return self
