"""Strict language-neutral contract for bounded live journey events."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agent_console.live_journey_schemas import JourneyIdentity

JourneyEventType = Literal[
    "JOURNEY_REGISTERED",
    "CORRECTION_ACCEPTED",
    "APPROVAL_RECORDED",
    "EXECUTION_AUTHORIZED",
    "EXECUTION_STARTED",
    "EXECUTION_SUCCEEDED",
    "EXECUTION_FAILED",
    "JOURNEY_STALE",
    "JOURNEY_UNAVAILABLE",
    "JOURNEY_ERROR",
    "RESUME_UNAVAILABLE",
]
JourneyStage = Literal["JOURNEY", "CORRECTION", "APPROVAL", "EXECUTION", "RESUME"]
JourneyStatus = Literal[
    "REGISTERED",
    "ACCEPTED",
    "APPROVED",
    "REJECTED",
    "AUTHORIZED",
    "STARTED",
    "SUCCEEDED",
    "FAILED",
    "STALE",
    "UNAVAILABLE",
    "ERROR",
]


class StrictStreamModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class JourneyEventPayload(StrictStreamModel):
    """Allowlisted transition facts; never accepts arbitrary metadata."""

    revision: int | None = Field(default=None, ge=1)
    approvalId: str | None = Field(default=None, max_length=200)
    platformExecutionIdentity: str | None = Field(default=None, max_length=200)
    sharedSnapshotId: str | None = Field(default=None, max_length=200)
    graphSnapshotId: str | None = Field(default=None, max_length=200)
    evidenceIds: list[str] = Field(default_factory=list, max_length=64)
    citationIds: list[str] = Field(default_factory=list, max_length=64)
    limitationCodes: list[str] = Field(default_factory=list, max_length=32)

    @field_validator(
        "approvalId",
        "platformExecutionIdentity",
        "sharedSnapshotId",
        "graphSnapshotId",
    )
    @classmethod
    def validate_optional_identifier(cls, value: str | None) -> str | None:
        if value is not None and (not value or len(value) > 200):
            raise ValueError("STREAM_IDENTIFIER_INVALID")
        return value

    @field_validator("evidenceIds", "citationIds", "limitationCodes")
    @classmethod
    def validate_identifiers(cls, values: list[str]) -> list[str]:
        if any(not value or len(value) > 200 for value in values):
            raise ValueError("STREAM_IDENTIFIER_INVALID")
        return values

    @model_validator(mode="after")
    def validate_serialized_bounds(self) -> JourneyEventPayload:
        payload = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        if len(payload) > 16 * 1024:
            raise ValueError("STREAM_PAYLOAD_TOO_LARGE")
        return self


class JourneyEventEnvelope(StrictStreamModel):
    schemaVersion: Literal["journey-event.v1"] = "journey-event.v1"
    journeyId: str = Field(min_length=1, max_length=200)
    eventId: str = Field(min_length=1, max_length=200)
    sequence: int = Field(gt=0)
    occurredAt: datetime
    eventType: JourneyEventType
    stage: JourneyStage
    status: JourneyStatus
    terminal: bool
    reasonCode: str = Field(min_length=1, max_length=200)
    localizationKey: str = Field(min_length=1, max_length=200)
    provenance: Literal["LIVE_EXECUTION"] = "LIVE_EXECUTION"
    identity: JourneyIdentity
    payload: JourneyEventPayload

    @field_validator("occurredAt")
    @classmethod
    def validate_aware_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("STREAM_OCCURRED_AT_MUST_BE_AWARE")
        if value.utcoffset().total_seconds() != 0:
            raise ValueError("STREAM_OCCURRED_AT_MUST_BE_UTC")
        return value

    @field_validator("identity")
    @classmethod
    def validate_identity_bounds(cls, value: JourneyIdentity) -> JourneyIdentity:
        dumped = value.model_dump()
        for field_value in dumped.values():
            values = field_value if isinstance(field_value, list) else [field_value]
            if any(
                isinstance(item, str) and (not item or len(item) > 200)
                for item in values
            ):
                raise ValueError("STREAM_IDENTIFIER_INVALID")
        return value

    @model_validator(mode="after")
    def validate_serialized_bounds(self) -> JourneyEventEnvelope:
        payload = json.dumps(
            self.payload.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        envelope = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        if len(payload) > 16 * 1024:
            raise ValueError("STREAM_PAYLOAD_TOO_LARGE")
        if len(envelope) > 32 * 1024:
            raise ValueError("STREAM_ENVELOPE_TOO_LARGE")
        return self


def serialize_envelope(envelope: JourneyEventEnvelope) -> str:
    """Return the canonical bytes used for duplicate and replay comparison."""
    return json.dumps(
        envelope.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
