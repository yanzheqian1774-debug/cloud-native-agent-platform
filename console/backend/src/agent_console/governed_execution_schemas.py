"""Strict wire contracts for the internal governed execution entry."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StartGovernedExecution(_StrictModel):
    planId: str = Field(min_length=1, max_length=200)
    planVersion: int = Field(ge=1)
    planDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    approvalId: str = Field(min_length=1, max_length=200)
    assignmentId: str = Field(min_length=1, max_length=200)
    digitalEmployeeInstanceId: str = Field(min_length=1, max_length=200)
    taskId: str = Field(min_length=1, max_length=200)
    skillId: str = Field(min_length=1, max_length=200)
    skillRevisionId: str = Field(min_length=1, max_length=200)
    skillDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    operation: str = Field(min_length=1, max_length=200)
    idempotencyKey: str = Field(min_length=1, max_length=200)
    input: dict[str, Any]
