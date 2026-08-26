"""Internal, in-memory Digital Employee authoring boundary for v0.2.

This module is not an HTTP DTO, public contract, persistence layer, or publish
API.  It deliberately requires an explicit Human decision before an immutable
definition revision can become effective.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from typing import Any

MAX_TEXT = 2_000
MAX_ITEMS = 32
MAX_ITEM_TEXT = 500
MAX_SERIALIZED_INPUT = 32_000
_SECRET = re.compile(
    r"(?:api[_-]?key|authorization|bearer|credential|password|secret|token)",
    re.IGNORECASE,
)


class AuthoringError(ValueError):
    """Stable, redacted failure from the internal authoring boundary."""


class AuthoringState(StrEnum):
    DRAFT = "DRAFT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class ApprovalDecision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class ChangeType(StrEnum):
    ADD = "ADD"
    REMOVE = "REMOVE"
    REPLACE = "REPLACE"


@dataclass(frozen=True, slots=True)
class RuntimePreference:
    requested: str
    evidence_state: str


@dataclass(frozen=True, slots=True)
class DigitalEmployeeValues:
    definition_id: str
    display_name: str
    role_title: str
    role_description: str
    business_responsibilities: tuple[str, ...]
    allowed_capabilities: tuple[str, ...]
    prohibited_activities: tuple[str, ...]
    runtime_preference: RuntimePreference
    knowledge_binding_ref: str | None
    status_code: str
    reason_code: str


@dataclass(frozen=True, slots=True)
class FieldChange:
    field: str
    change_type: ChangeType
    before: Any
    after: Any


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    actor: str
    decision: ApprovalDecision
    decided_at: datetime
    source_revision: str


@dataclass(frozen=True, slots=True)
class AuthoringRevision:
    revision: str
    source_revision: str | None
    state: AuthoringState
    values: DigitalEmployeeValues
    diff: tuple[FieldChange, ...]
    ai_assisted: bool
    approval: ApprovalRecord | None = None


_DIFF_FIELDS = (
    "display_name",
    "role_title",
    "role_description",
    "business_responsibilities",
    "allowed_capabilities",
    "prohibited_activities",
    "runtime_preference",
    "knowledge_binding_ref",
    "status_code",
    "reason_code",
)


def _required_text(value: object, code: str, *, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AuthoringError(code)
    if len(value) > limit:
        raise AuthoringError("INPUT_LIMIT_EXCEEDED")
    if _SECRET.search(value):
        raise AuthoringError("SECRET_SHAPED_VALUE_REJECTED")
    return value


def _items(value: object, code: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise AuthoringError(code)
    if not value or len(value) > MAX_ITEMS:
        raise AuthoringError(code if not value else "INPUT_LIMIT_EXCEEDED")
    result = tuple(_required_text(item, code, limit=MAX_ITEM_TEXT) for item in value)
    if len(set(result)) != len(result):
        raise AuthoringError("AMBIGUOUS_DUPLICATE_VALUE")
    return result


def normalize_values(raw: Mapping[str, object]) -> DigitalEmployeeValues:
    """Validate and defensively copy caller input into immutable values."""
    if not isinstance(raw, Mapping):
        raise AuthoringError("MALFORMED_INPUT")
    try:
        encoded = json.dumps(raw, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise AuthoringError("MALFORMED_INPUT") from exc
    if len(encoded) > MAX_SERIALIZED_INPUT:
        raise AuthoringError("INPUT_LIMIT_EXCEEDED")
    allowed = {
        "definition_id",
        "display_name",
        "role_title",
        "role_description",
        "business_responsibilities",
        "allowed_capabilities",
        "prohibited_activities",
        "runtime_preference",
        "knowledge_binding_ref",
        "status_code",
        "reason_code",
    }
    if set(raw) != allowed:
        raise AuthoringError("MALFORMED_OR_AMBIGUOUS_FIELDS")
    runtime = raw["runtime_preference"]
    if not isinstance(runtime, Mapping) or set(runtime) != {
        "requested",
        "evidence_state",
    }:
        raise AuthoringError("MALFORMED_RUNTIME_PREFERENCE")
    knowledge_ref = raw["knowledge_binding_ref"]
    if knowledge_ref is not None:
        knowledge_ref = _required_text(knowledge_ref, "INVALID_KNOWLEDGE_REFERENCE")
    return DigitalEmployeeValues(
        definition_id=_required_text(raw["definition_id"], "INVALID_DEFINITION_ID"),
        display_name=_required_text(raw["display_name"], "INVALID_DISPLAY_NAME"),
        role_title=_required_text(raw["role_title"], "INVALID_ROLE_TITLE"),
        role_description=_required_text(
            raw["role_description"], "INVALID_ROLE_DESCRIPTION"
        ),
        business_responsibilities=_items(
            raw["business_responsibilities"], "INVALID_RESPONSIBILITIES"
        ),
        allowed_capabilities=_items(
            raw["allowed_capabilities"], "INVALID_ALLOWED_CAPABILITIES"
        ),
        prohibited_activities=_items(
            raw["prohibited_activities"], "INVALID_PROHIBITED_ACTIVITIES"
        ),
        runtime_preference=RuntimePreference(
            requested=_required_text(runtime["requested"], "INVALID_RUNTIME"),
            evidence_state=_required_text(
                runtime["evidence_state"], "INVALID_RUNTIME_EVIDENCE"
            ),
        ),
        knowledge_binding_ref=knowledge_ref,
        status_code=_required_text(raw["status_code"], "INVALID_STATUS_CODE"),
        reason_code=_required_text(raw["reason_code"], "INVALID_REASON_CODE"),
    )


def deterministic_diff(
    before: DigitalEmployeeValues, after: DigitalEmployeeValues
) -> tuple[FieldChange, ...]:
    """Return a bounded field-ordered immutable Diff."""
    changes = []
    for field in _DIFF_FIELDS:
        old = getattr(before, field)
        new = getattr(after, field)
        if old == new:
            continue
        if old is None:
            change_type = ChangeType.ADD
        elif new is None:
            change_type = ChangeType.REMOVE
        else:
            change_type = ChangeType.REPLACE
        changes.append(FieldChange(field, change_type, old, new))
    return tuple(changes)


def _revision(values: DigitalEmployeeValues, source_revision: str | None) -> str:
    payload = {
        "sourceRevision": source_revision,
        "definitionId": values.definition_id,
        **{field: getattr(values, field) for field in _DIFF_FIELDS},
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return f"rev-{sha256(encoded.encode()).hexdigest()[:24]}"


class AuthoringBackend:
    """Bounded in-memory lifecycle candidate; no implicit persistence/publish."""

    def __init__(self, effective: Mapping[str, object]) -> None:
        values = normalize_values(effective)
        revision = _revision(values, None)
        self._effective = AuthoringRevision(
            revision, None, AuthoringState.APPROVED, values, (), False
        )
        self._revisions: dict[str, AuthoringRevision] = {revision: self._effective}

    @property
    def effective(self) -> AuthoringRevision:
        return self._effective

    def create_draft(
        self, candidate: Mapping[str, object], *, ai_assisted: bool = False
    ) -> AuthoringRevision:
        values = normalize_values(candidate)
        if values.definition_id != self._effective.values.definition_id:
            raise AuthoringError("DEFINITION_ID_MISMATCH")
        diff = deterministic_diff(self._effective.values, values)
        if not diff:
            raise AuthoringError("EMPTY_DIFF")
        revision = _revision(values, self._effective.revision)
        existing = self._revisions.get(revision)
        if existing is not None:
            return existing
        draft = AuthoringRevision(
            revision,
            self._effective.revision,
            AuthoringState.DRAFT,
            values,
            diff,
            ai_assisted,
        )
        self._revisions[revision] = draft
        return draft

    def request_review(self, revision: str) -> AuthoringRevision:
        current = self._get(revision)
        if current.state == AuthoringState.REVIEW_REQUIRED:
            return current
        if current.state != AuthoringState.DRAFT:
            raise AuthoringError("INVALID_REVISION_STATE")
        reviewed = replace(current, state=AuthoringState.REVIEW_REQUIRED)
        self._revisions[revision] = reviewed
        return reviewed

    def decide(
        self,
        revision: str,
        *,
        actor: str,
        decision: ApprovalDecision,
        decided_at: datetime,
        source_revision: str,
    ) -> AuthoringRevision:
        current = self._get(revision)
        actor = _required_text(actor, "INVALID_APPROVAL_ACTOR", limit=200)
        if not isinstance(decision, ApprovalDecision) or not isinstance(
            decided_at, datetime
        ):
            raise AuthoringError("INVALID_APPROVAL_DECISION")
        if decided_at.tzinfo is None or decided_at.utcoffset() is None:
            raise AuthoringError("INVALID_APPROVAL_TIMESTAMP")
        if not isinstance(source_revision, str) or not source_revision.strip():
            raise AuthoringError("SOURCE_REVISION_REQUIRED")
        if source_revision != current.source_revision:
            raise AuthoringError("STALE_SOURCE_REVISION")
        if current.approval is not None:
            if (
                current.approval.actor == actor
                and current.approval.decision == decision
                and current.approval.source_revision == source_revision
            ):
                return current
            raise AuthoringError("REVISION_ALREADY_DECIDED")
        if current.state == AuthoringState.SUPERSEDED:
            raise AuthoringError("SUPERSEDED_REVISION")
        if current.state != AuthoringState.REVIEW_REQUIRED:
            raise AuthoringError("HUMAN_REVIEW_REQUIRED")
        if current.source_revision != self._effective.revision:
            superseded = replace(current, state=AuthoringState.SUPERSEDED)
            self._revisions[revision] = superseded
            raise AuthoringError("SUPERSEDED_REVISION")
        approval = ApprovalRecord(actor, decision, decided_at, source_revision)
        terminal = replace(
            current,
            state=(
                AuthoringState.APPROVED
                if decision == ApprovalDecision.APPROVE
                else AuthoringState.REJECTED
            ),
            approval=approval,
        )
        self._revisions[revision] = terminal
        if decision == ApprovalDecision.APPROVE:
            self._effective = terminal
            for key, item in tuple(self._revisions.items()):
                if item.state in {AuthoringState.DRAFT, AuthoringState.REVIEW_REQUIRED}:
                    self._revisions[key] = replace(
                        item, state=AuthoringState.SUPERSEDED
                    )
        return terminal

    def _get(self, revision: str) -> AuthoringRevision:
        try:
            return self._revisions[revision]
        except (KeyError, TypeError) as exc:
            raise AuthoringError("REVISION_NOT_FOUND") from exc
