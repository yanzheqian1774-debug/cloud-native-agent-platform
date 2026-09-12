"""Internal durable OpenClaw correlation values.

These values extend the PostgreSQL Execution Authority.  They are not a public
Runtime Contract and provider correlations are not ownership attestation.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum

from agent_core.execution_contract import (
    CommandId,
    Generation,
    PlacementId,
    RuntimeInstanceId,
    ScopeIdentity,
)


class OpenClawBindingError(ValueError):
    """Stable, non-disclosing binding validation failure."""


class AssociationStatus(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    MATCHED = "MATCHED"
    MISMATCHED = "MISMATCHED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


def _text(value: object, code: str, *, maximum: int = 512) -> str:
    if not isinstance(value, str):
        raise OpenClawBindingError(code)
    normalized = unicodedata.normalize("NFC", value).strip()
    if not normalized or len(normalized.encode()) > maximum:
        raise OpenClawBindingError(code)
    return normalized


def _digest(value: object, code: str) -> str:
    normalized = _text(value, code, maximum=64)
    if len(normalized) != 64 or any(c not in "0123456789abcdef" for c in normalized):
        raise OpenClawBindingError(code)
    return normalized


def _time(value: object, code: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise OpenClawBindingError(code)
    return value.astimezone(UTC)


def canonical_payload_digest(value: object) -> str:
    payload = json.dumps(
        asdict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=lambda item: (
            item.value
            if isinstance(item, (StrEnum, Generation))
            else item.isoformat().replace("+00:00", "Z")
            if isinstance(item, datetime)
            else str(item)
        ),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class OpenClawRuntimeBinding:
    scope: ScopeIdentity
    runtime_instance_id: RuntimeInstanceId
    placement_id: PlacementId
    gateway_digest: str
    agent_id: str
    canonical_workspace: str
    workspace_host: str
    workspace_storage_domain: str
    source_version: str
    authorization_decision_id: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.scope, ScopeIdentity):
            raise OpenClawBindingError("INVALID_BINDING_SCOPE")
        if not isinstance(self.runtime_instance_id, RuntimeInstanceId):
            raise OpenClawBindingError("INVALID_RUNTIME_INSTANCE_ID")
        if not isinstance(self.placement_id, PlacementId):
            raise OpenClawBindingError("INVALID_PLACEMENT_ID")
        object.__setattr__(
            self,
            "gateway_digest",
            _digest(self.gateway_digest, "INVALID_GATEWAY_DIGEST"),
        )
        for name in (
            "agent_id",
            "canonical_workspace",
            "workspace_host",
            "workspace_storage_domain",
            "source_version",
            "authorization_decision_id",
        ):
            object.__setattr__(
                self, name, _text(getattr(self, name), "INVALID_OPENCLAW_BINDING")
            )
        object.__setattr__(
            self, "recorded_at", _time(self.recorded_at, "INVALID_RECORDED_AT")
        )


@dataclass(frozen=True, slots=True)
class OpenClawGenerationBinding:
    scope: ScopeIdentity
    runtime_instance_id: RuntimeInstanceId
    generation: Generation
    session_key: str
    session_id: str
    command_id: CommandId
    idempotency_key: str
    command_payload_digest: str
    association_status: AssociationStatus
    observation_high_water: int
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.scope, ScopeIdentity):
            raise OpenClawBindingError("INVALID_BINDING_SCOPE")
        if not isinstance(self.runtime_instance_id, RuntimeInstanceId):
            raise OpenClawBindingError("INVALID_RUNTIME_INSTANCE_ID")
        if not isinstance(self.generation, Generation):
            raise OpenClawBindingError("INVALID_GENERATION")
        if not isinstance(self.command_id, CommandId):
            raise OpenClawBindingError("INVALID_COMMAND_ID")
        for name in ("session_key", "session_id", "idempotency_key"):
            object.__setattr__(
                self, name, _text(getattr(self, name), "INVALID_OPENCLAW_GENERATION")
            )
        object.__setattr__(
            self,
            "command_payload_digest",
            _digest(self.command_payload_digest, "INVALID_COMMAND_PAYLOAD_DIGEST"),
        )
        if not isinstance(self.association_status, AssociationStatus):
            raise OpenClawBindingError("INVALID_ASSOCIATION_STATUS")
        if (
            not isinstance(self.observation_high_water, int)
            or isinstance(self.observation_high_water, bool)
            or self.observation_high_water < 0
        ):
            raise OpenClawBindingError("INVALID_OBSERVATION_HIGH_WATER")
        object.__setattr__(
            self, "recorded_at", _time(self.recorded_at, "INVALID_RECORDED_AT")
        )


@dataclass(frozen=True, slots=True)
class OpenClawBindingObservation:
    scope: ScopeIdentity
    runtime_instance_id: RuntimeInstanceId
    generation: Generation
    high_water: int
    association_status: AssociationStatus
    observed_at: datetime
    freshness_deadline: datetime
    source_version: str
    reason_code: str
    gateway_matched: bool
    agent_matched: bool
    workspace_matched: bool
    session_matched: bool

    def __post_init__(self) -> None:
        if not isinstance(self.scope, ScopeIdentity):
            raise OpenClawBindingError("INVALID_BINDING_SCOPE")
        if not isinstance(self.runtime_instance_id, RuntimeInstanceId):
            raise OpenClawBindingError("INVALID_RUNTIME_INSTANCE_ID")
        if not isinstance(self.generation, Generation):
            raise OpenClawBindingError("INVALID_GENERATION")
        if (
            not isinstance(self.high_water, int)
            or isinstance(self.high_water, bool)
            or self.high_water < 1
        ):
            raise OpenClawBindingError("INVALID_OBSERVATION_HIGH_WATER")
        if not isinstance(self.association_status, AssociationStatus):
            raise OpenClawBindingError("INVALID_ASSOCIATION_STATUS")
        object.__setattr__(
            self, "observed_at", _time(self.observed_at, "INVALID_OBSERVED_AT")
        )
        object.__setattr__(
            self,
            "freshness_deadline",
            _time(self.freshness_deadline, "INVALID_FRESHNESS_DEADLINE"),
        )
        if self.freshness_deadline <= self.observed_at:
            raise OpenClawBindingError("INVALID_FRESHNESS_DEADLINE")
        for name in ("source_version", "reason_code"):
            object.__setattr__(
                self, name, _text(getattr(self, name), "INVALID_BINDING_OBSERVATION")
            )
        for name in (
            "gateway_matched",
            "agent_matched",
            "workspace_matched",
            "session_matched",
        ):
            if not isinstance(getattr(self, name), bool):
                raise OpenClawBindingError("INVALID_BINDING_OBSERVATION")
        if self.association_status is AssociationStatus.MATCHED and not all(
            (
                self.gateway_matched,
                self.agent_matched,
                self.workspace_matched,
                self.session_matched,
            )
        ):
            raise OpenClawBindingError("INCOMPLETE_MATCHED_OBSERVATION")
