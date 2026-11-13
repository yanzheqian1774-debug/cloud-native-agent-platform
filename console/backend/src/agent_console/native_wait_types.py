"""Private opt-in checkpoint values; none is dispatch or execution authority."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .resource_use_domain import canonical_digest

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Identity = Annotated[str, Field(min_length=1, max_length=500)]


class FrozenValue(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class WaitIdentity(FrozenValue):
    namespace: Identity
    security_domain: Identity
    preparation_digest: Digest
    workflow_run_id: Identity
    task_id: Identity
    attempt_id: Identity
    command_id: Identity
    skill_invocation_id: Identity
    principal_id: Identity
    conversation_id: Identity

    @property
    def skill_key(self):
        return self.namespace, self.security_domain, self.skill_invocation_id


class EffectReference(FrozenValue):
    key: Identity
    request_digest: Digest
    result_digest: Digest


class WaitCheckpoint(FrozenValue):
    schema_version: Literal["native-human-wait.v1"] = "native-human-wait.v1"
    identity: WaitIdentity
    ordinal: Annotated[int, Field(ge=0, le=31)]
    root_key: Identity
    root_digest: Digest
    input_request_digest: Digest
    question_key: Identity
    question_digest: Digest
    worker_id: Identity
    startup_record_digest: Digest
    executor_id: Identity
    executor_revision: Identity
    executor_configuration_digest: Digest
    source_digest: Digest
    model_profile_digest: Digest
    scope_evidence_digest: Digest
    completed_effects: Annotated[tuple[EffectReference, ...], Field(max_length=64)]
    remaining_active_milliseconds: Annotated[int, Field(gt=0, le=600_000)]
    maximum_decisions: Annotated[int, Field(ge=1, le=32)]
    created_at: datetime
    human_expires_at: datetime
    authority_expires_at: datetime

    @model_validator(mode="after")
    def consistent(self):
        for value in (
            self.created_at,
            self.human_expires_at,
            self.authority_expires_at,
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("NATIVE_WAIT_TIMEZONE_REQUIRED")
        if not self.created_at < self.human_expires_at <= self.authority_expires_at:
            raise ValueError("NATIVE_WAIT_DEADLINE_INVALID")
        if self.ordinal + 1 >= self.maximum_decisions:
            raise ValueError("NATIVE_WAIT_NO_DECISION_REMAINING")
        if self.question_key != f"{self.root_key}:{self.ordinal}:INPUT":
            raise ValueError("NATIVE_WAIT_INPUT_KEY_MISMATCH")
        keys = [effect.key for effect in self.completed_effects]
        if len(keys) != len(set(keys)) or self.question_key in keys:
            raise ValueError("NATIVE_WAIT_EFFECT_REFERENCES_INVALID")
        if f"{self.root_key}:{self.ordinal}:MODEL" not in keys:
            raise ValueError("NATIVE_WAIT_DECISION_RECEIPT_REQUIRED")
        for key in keys:
            prefix, separator, kind = key.rpartition(":")
            root, _, ordinal = prefix.rpartition(":")
            if (
                not separator
                or root != self.root_key
                or not ordinal.isdecimal()
                or str(int(ordinal)) != ordinal
                or int(ordinal) > self.ordinal
                or kind not in {"MODEL", "TOOL", "INPUT", "VERIFY"}
                or (int(ordinal) == self.ordinal and kind != "MODEL")
            ):
                raise ValueError("NATIVE_WAIT_EFFECT_KEY_MISMATCH")
        return self

    @property
    def digest(self):
        return canonical_digest(self.model_dump(mode="json"))


class SkillJobWaiting(FrozenValue):
    """Positive nonterminal receipt, intercepted before any terminal conversion."""

    identity: WaitIdentity
    checkpoint_digest: Digest


class StopObservation(FrozenValue):
    checkpoint_digest: Digest
    command_id: Identity
    worker_id: Identity
    startup_record_digest: Digest
    process_identity_digest: Digest
    exit_receipt_digest: Digest
    stopped_at: datetime

    @model_validator(mode="after")
    def timezone(self):
        if self.stopped_at.tzinfo is None or self.stopped_at.utcoffset() is None:
            raise ValueError("NATIVE_WAIT_TIMEZONE_REQUIRED")
        return self


class ContinuationClaim(FrozenValue):
    checkpoint_digest: Digest
    answer_digest: Digest
    generation: Literal[1] = 1
    fence: Digest
    worker_id: Identity
    startup_record_digest: Digest


class ClaimObservation(FrozenValue):
    """Only the insertion winner may advance. A replay is strictly read-only."""

    newly_claimed: bool
    claim: ContinuationClaim


WaitState = Literal[
    "QUIESCING",
    "WAITING_FOR_USER",
    "ANSWER_SAVED",
    "CONTINUATION_CLAIMED",
    "ADVANCING",
    "COMPLETED",
    "EXPIRED",
    "BLOCKED",
]
