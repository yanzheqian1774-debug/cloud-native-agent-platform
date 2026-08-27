"""Immutable, allowlisted Native execution evidence domain."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class EvidenceValidationError(ValueError):
    """Bounded validation failure that never echoes rejected content."""


class AuthorizationDecision(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EvidenceEventType(StrEnum):
    RUNTIME_OUTCOME = "RUNTIME_OUTCOME"
    CAPABILITY_OUTCOME = "CAPABILITY_OUTCOME"
    EXECUTION_OUTCOME = "EXECUTION_OUTCOME"


class OutcomeClassification(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    DENIED = "DENIED"
    UNKNOWN = "UNKNOWN"


class ReferenceType(StrEnum):
    EVIDENCE = "EVIDENCE"
    CITATION = "CITATION"


class ReferenceVisibility(StrEnum):
    PRODUCT = "PRODUCT"
    TECHNICAL = "TECHNICAL"
    BOTH = "BOTH"
    DETAIL_ONLY = "DETAIL_ONLY"


MAX_TEXT = 512
MAX_REFS = 32
_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,127}")
_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}")
_SENSITIVE = re.compile(
    r"(?:api[_-]?key|authorization|bearer|credential|password|secret|token|"
    r"raw[_-]?(?:prompt|input|output|request|response|arguments?)|stack[_-]?trace|"
    r"environment[_-]?dump|host[_-]?path)",
    re.IGNORECASE,
)
_HOST_PATH = re.compile(r"(?:^|\s)(?:/Users/|/home/|/private/|[A-Za-z]:\\)")


def _text(value: object, code: str, *, stable_code: bool = False) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_TEXT:
        raise EvidenceValidationError(code)
    normalized = unicodedata.normalize("NFC", value)
    if _SENSITIVE.search(normalized) or _HOST_PATH.search(normalized):
        raise EvidenceValidationError("PROHIBITED_EVIDENCE_CONTENT")
    pattern = _CODE if stable_code else _IDENTITY
    if pattern.fullmatch(normalized) is None:
        raise EvidenceValidationError(code)
    return normalized


def _optional_text(
    value: object | None, code: str, *, stable_code: bool = False
) -> str | None:
    return None if value is None else _text(value, code, stable_code=stable_code)


def _timestamp(value: object, code: str) -> str:
    if not isinstance(value, str) or len(value) > 64:
        raise EvidenceValidationError(code)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvidenceValidationError(code) from exc
    if parsed.tzinfo is None:
        raise EvidenceValidationError(code)
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def canonical_json(value: object) -> str:
    """Serialize normalized evidence for stable hashing and snapshot identity."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class AuthorizedReference:
    """One independently authorized reference decision recorded as evidence."""

    reference_identity: str
    reference_type: ReferenceType
    namespace: str
    security_domain: str
    authorization_decision: AuthorizationDecision
    reason_code: str
    visibility: ReferenceVisibility
    source_identity: str
    provenance: str

    def __post_init__(self) -> None:
        for name in (
            "reference_identity",
            "namespace",
            "security_domain",
            "source_identity",
            "provenance",
        ):
            object.__setattr__(
                self, name, _text(getattr(self, name), "INVALID_REFERENCE")
            )
        object.__setattr__(
            self,
            "reason_code",
            _text(self.reason_code, "INVALID_REFERENCE_REASON", stable_code=True),
        )
        if not isinstance(self.reference_type, ReferenceType):
            raise EvidenceValidationError("INVALID_REFERENCE_TYPE")
        if self.authorization_decision not in {
            AuthorizationDecision.ALLOW,
            AuthorizationDecision.DENY,
        }:
            raise EvidenceValidationError("INVALID_REFERENCE_AUTHORIZATION")
        if not isinstance(self.visibility, ReferenceVisibility):
            raise EvidenceValidationError("INVALID_REFERENCE_VISIBILITY")

    @property
    def canonical_payload(self) -> dict[str, str]:
        return {
            "reference_identity": self.reference_identity,
            "reference_type": self.reference_type.value,
            "namespace": self.namespace,
            "security_domain": self.security_domain,
            "authorization_decision": self.authorization_decision.value,
            "reason_code": self.reason_code,
            "visibility": self.visibility.value,
            "source_identity": self.source_identity,
            "provenance": self.provenance,
        }

    @classmethod
    def from_allowlisted(cls, source: Mapping[str, object]) -> AuthorizedReference:
        if not isinstance(source, Mapping) or set(source) != {
            "reference_identity",
            "reference_type",
            "namespace",
            "security_domain",
            "authorization_decision",
            "reason_code",
            "visibility",
            "source_identity",
            "provenance",
        }:
            raise EvidenceValidationError("INVALID_REFERENCE_AUTHORIZATION")
        try:
            return cls(
                reference_identity=source["reference_identity"],  # type: ignore[arg-type]
                reference_type=ReferenceType(source["reference_type"]),
                namespace=source["namespace"],  # type: ignore[arg-type]
                security_domain=source["security_domain"],  # type: ignore[arg-type]
                authorization_decision=AuthorizationDecision(
                    source["authorization_decision"]
                ),
                reason_code=source["reason_code"],  # type: ignore[arg-type]
                visibility=ReferenceVisibility(source["visibility"]),
                source_identity=source["source_identity"],  # type: ignore[arg-type]
                provenance=source["provenance"],  # type: ignore[arg-type]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise EvidenceValidationError("INVALID_REFERENCE_AUTHORIZATION") from exc


@dataclass(frozen=True, slots=True)
class ExecutionEvidenceRecord:
    """One immutable normalized event; repository metadata is non-canonical."""

    evidence_record_id: str
    namespace: str
    security_domain: str
    platform_execution_identity: str
    workflow_identity: str
    task_identity: str
    attempt_ordinal: int
    event_ordinal: int
    event_type: EvidenceEventType
    occurred_at: str
    runtime_classification: str
    selected_instance_identity: str
    capability_identity: str | None
    authorization_decision: AuthorizationDecision
    reason_code: str
    provider_correlation_id: str | None
    provider_call_count: int
    outcome_classification: OutcomeClassification
    outcome_reference: str | None = None
    references: tuple[AuthorizedReference, ...] = ()
    limitation_code: str | None = None
    supersedes_record_id: str | None = None
    schema_version: int = 1
    storage_sequence: int | None = None
    recorded_at: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "evidence_record_id",
            "namespace",
            "security_domain",
            "platform_execution_identity",
            "workflow_identity",
            "task_identity",
            "runtime_classification",
            "selected_instance_identity",
        ):
            object.__setattr__(
                self, name, _text(getattr(self, name), "INVALID_EVIDENCE")
            )
        for name in ("attempt_ordinal", "event_ordinal", "provider_call_count"):
            value = getattr(self, name)
            minimum = 0 if name == "provider_call_count" else 1
            if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
                raise EvidenceValidationError("INVALID_EVIDENCE_ORDINAL")
        if self.schema_version != 1:
            raise EvidenceValidationError("UNSUPPORTED_EVIDENCE_SCHEMA")
        if not isinstance(self.event_type, EvidenceEventType):
            raise EvidenceValidationError("INVALID_EVENT_TYPE")
        if not isinstance(self.authorization_decision, AuthorizationDecision):
            raise EvidenceValidationError("INVALID_AUTHORIZATION_DECISION")
        if not isinstance(self.outcome_classification, OutcomeClassification):
            raise EvidenceValidationError("INVALID_OUTCOME_CLASSIFICATION")
        object.__setattr__(
            self, "occurred_at", _timestamp(self.occurred_at, "INVALID_OCCURRED_AT")
        )
        object.__setattr__(
            self,
            "reason_code",
            _text(self.reason_code, "INVALID_REASON_CODE", stable_code=True),
        )
        for name, code in (
            ("capability_identity", "INVALID_CAPABILITY_IDENTITY"),
            ("provider_correlation_id", "INVALID_PROVIDER_CORRELATION"),
            ("outcome_reference", "INVALID_OUTCOME_REFERENCE"),
            ("supersedes_record_id", "INVALID_SUPERSESSION"),
        ):
            object.__setattr__(self, name, _optional_text(getattr(self, name), code))
        object.__setattr__(
            self,
            "limitation_code",
            _optional_text(
                self.limitation_code, "INVALID_LIMITATION_CODE", stable_code=True
            ),
        )
        if (
            not isinstance(self.references, (tuple, list))
            or len(self.references) > MAX_REFS
        ):
            raise EvidenceValidationError("INVALID_REFERENCE_AUTHORIZATION")
        references = tuple(self.references)
        if not all(isinstance(item, AuthorizedReference) for item in references):
            raise EvidenceValidationError("INVALID_REFERENCE_AUTHORIZATION")
        if len(
            {(item.reference_type, item.reference_identity) for item in references}
        ) != len(references):
            raise EvidenceValidationError("DUPLICATE_REFERENCE_AUTHORIZATION")
        object.__setattr__(
            self,
            "references",
            tuple(
                sorted(
                    references,
                    key=lambda item: (
                        item.reference_type.value,
                        item.reference_identity,
                    ),
                )
            ),
        )
        if self.authorization_decision is AuthorizationDecision.DENY and (
            self.provider_call_count != 0
            or any(
                item.authorization_decision is AuthorizationDecision.ALLOW
                for item in references
            )
        ):
            raise EvidenceValidationError("DENY_REQUIRES_ZERO_PROVIDER_EFFECTS")
        if self.storage_sequence is not None and (
            not isinstance(self.storage_sequence, int)
            or isinstance(self.storage_sequence, bool)
            or self.storage_sequence < 1
        ):
            raise EvidenceValidationError("INVALID_STORAGE_SEQUENCE")
        if self.recorded_at is not None:
            object.__setattr__(
                self, "recorded_at", _timestamp(self.recorded_at, "INVALID_RECORDED_AT")
            )

    @property
    def canonical_payload(self) -> Mapping[str, Any]:
        """Stable producer evidence; excludes all repository-assigned metadata."""
        return MappingProxyType(
            {
                "schema_version": self.schema_version,
                "evidence_record_id": self.evidence_record_id,
                "namespace": self.namespace,
                "security_domain": self.security_domain,
                "platform_execution_identity": self.platform_execution_identity,
                "workflow_identity": self.workflow_identity,
                "task_identity": self.task_identity,
                "attempt_ordinal": self.attempt_ordinal,
                "event_ordinal": self.event_ordinal,
                "event_type": self.event_type.value,
                "occurred_at": self.occurred_at,
                "runtime_classification": self.runtime_classification,
                "selected_instance_identity": self.selected_instance_identity,
                "capability_identity": self.capability_identity,
                "authorization_decision": self.authorization_decision.value,
                "reason_code": self.reason_code,
                "provider_correlation_id": self.provider_correlation_id,
                "provider_call_count": self.provider_call_count,
                "outcome_classification": self.outcome_classification.value,
                "outcome_reference": self.outcome_reference,
                "references": [item.canonical_payload for item in self.references],
                "limitation_code": self.limitation_code,
                "supersedes_record_id": self.supersedes_record_id,
            }
        )

    @property
    def payload_digest(self) -> str:
        return hashlib.sha256(
            canonical_json(dict(self.canonical_payload)).encode()
        ).hexdigest()

    def with_repository_metadata(
        self, *, storage_sequence: int, recorded_at: str
    ) -> ExecutionEvidenceRecord:
        return replace(self, storage_sequence=storage_sequence, recorded_at=recorded_at)

    @classmethod
    def from_allowlisted(cls, source: Mapping[str, object]) -> ExecutionEvidenceRecord:
        if not isinstance(source, Mapping) or set(source) != _PRODUCER_FIELDS:
            raise EvidenceValidationError("UNKNOWN_OR_MISSING_EVIDENCE_FIELD")
        values = dict(source)
        references = values.get("references")
        if not isinstance(references, (tuple, list)):
            raise EvidenceValidationError("INVALID_REFERENCE_AUTHORIZATION")
        values["references"] = tuple(
            item
            if isinstance(item, AuthorizedReference)
            else AuthorizedReference.from_allowlisted(item)  # type: ignore[arg-type]
            for item in references
        )
        try:
            values["event_type"] = EvidenceEventType(values["event_type"])
            values["authorization_decision"] = AuthorizationDecision(
                values["authorization_decision"]
            )
            values["outcome_classification"] = OutcomeClassification(
                values["outcome_classification"]
            )
        except (TypeError, ValueError) as exc:
            raise EvidenceValidationError("INVALID_EVIDENCE") from exc
        return cls(**values)  # type: ignore[arg-type]


_PRODUCER_FIELDS = {
    name
    for name in ExecutionEvidenceRecord.__dataclass_fields__
    if name not in {"storage_sequence", "recorded_at"}
}
