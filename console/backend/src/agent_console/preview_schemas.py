"""Versioned bounded DTOs for the internal execution preview boundary."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schemaVersion: Literal[1] = 1
    state: Literal["COMPLETE", "PARTIAL", "STALE"]
    sharedSnapshotId: str = Field(max_length=128)
    graphSnapshotId: str = Field(max_length=128)
    platformExecutionIdentity: str = Field(max_length=256)
    snapshot: dict[str, Any]


class PreviewError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schemaVersion: Literal[1] = 1
    state: Literal["DENIED", "NOT_FOUND", "AUTHORITY_MISSING", "ERROR"]
    reasonCode: str = Field(max_length=128)
    message: str = Field(max_length=256)
