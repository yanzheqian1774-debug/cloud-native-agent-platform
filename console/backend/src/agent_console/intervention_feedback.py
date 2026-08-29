"""Append-only intervention and outcome feedback records for Package 6A.

This bounded in-memory service records facts only. It has no planning, matching,
placement, Knowledge, policy, authorization, Outcome, Evidence, or execution effect.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from agent_console.intervention_feedback_schemas import (
    InterventionCaptureCommand,
    InterventionEventRecord,
    InterventionFeedbackIdentity,
    InterventionFeedbackProjection,
    InterventionFeedbackResponse,
    InterventionLifecycleCommand,
    OutcomeFeedbackCommand,
    OutcomeFeedbackRecord,
    OutcomeFeedbackView,
)

_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+-]{0,255}")
_DIGEST = re.compile(r"[0-9a-f]{64}")
_LIFECYCLE_REASON = {
    "EXCLUDED": "LIFECYCLE_EXCLUSION",
    "RETAINED": "LIFECYCLE_RETENTION",
    "TOMBSTONED": "LIFECYCLE_TOMBSTONE",
}
_TRANSITIONS = {
    "RECORDED": frozenset({"EXCLUDED", "RETAINED", "TOMBSTONED"}),
    "EXCLUDED": frozenset({"RETAINED", "TOMBSTONED"}),
    "RETAINED": frozenset({"EXCLUDED", "TOMBSTONED"}),
    "TOMBSTONED": frozenset(),
}


class InterventionFeedbackFailure(ValueError):
    state = "INVALID"
    reason_code = "INTERVENTION_FEEDBACK_INVALID"
    status_code = 422

    def __init__(self, reason_code: str | None = None):
        self.reason_code = reason_code or self.reason_code
        super().__init__(self.reason_code)


class CaptureDenied(InterventionFeedbackFailure):
    state = "DENIED"
    reason_code = "INTERVENTION_FEEDBACK_ACCESS_DENIED"
    status_code = 403


class CaptureNotFound(InterventionFeedbackFailure):
    state = "NOT_FOUND"
    reason_code = "INTERVENTION_FEEDBACK_NOT_FOUND"
    status_code = 404


class CaptureConflict(InterventionFeedbackFailure):
    state = "CONFLICT"
    reason_code = "INTERVENTION_FEEDBACK_CONFLICT"
    status_code = 409


class CaptureUnavailable(InterventionFeedbackFailure):
    state = "UNAVAILABLE"
    reason_code = "INTERVENTION_FEEDBACK_REPOSITORY_UNAVAILABLE"
    status_code = 503


@dataclass(frozen=True, slots=True)
class TrustedCapturePrincipal:
    principal_id: str
    tenant_id: str
    security_domain: str
    authorized: bool

    def permits(self, tenant_id: str, security_domain: str) -> bool:
        return (
            self.authorized
            and bool(self.principal_id)
            and self.tenant_id == tenant_id
            and self.security_domain == security_domain
        )


@dataclass(frozen=True, slots=True)
class TrustedInterventionTarget:
    journey_id: str
    tenant_id: str
    security_domain: str
    provenance: str
    predecessor_revision_id: str | None
    predecessor_digest: str | None
    successor_revision_id: str
    successor_digest: str
    platform_execution_identity: str | None
    outcome_id: str | None
    execution_evidence_ids: tuple[str, ...]


class InterventionFeedbackRepository(Protocol):
    def append_intervention(
        self, record: InterventionEventRecord
    ) -> InterventionEventRecord: ...

    def append_feedback(
        self, record: OutcomeFeedbackRecord
    ) -> OutcomeFeedbackRecord: ...

    def interventions(
        self, *, tenant_id: str, security_domain: str, journey_id: str
    ) -> tuple[InterventionEventRecord, ...]: ...

    def feedback(
        self, *, tenant_id: str, security_domain: str, journey_id: str
    ) -> tuple[OutcomeFeedbackRecord, ...]: ...


class InMemoryInterventionFeedbackRepository:
    """Bounded append-only repository with no durability or deletion claim."""

    def __init__(self) -> None:
        self._interventions: tuple[InterventionEventRecord, ...] = ()
        self._feedback: tuple[OutcomeFeedbackRecord, ...] = ()

    def append_intervention(
        self, record: InterventionEventRecord
    ) -> InterventionEventRecord:
        for existing in self._interventions:
            if existing.recordId != record.recordId:
                continue
            if existing.recordDigest == record.recordDigest:
                return existing
            raise CaptureConflict("INTERVENTION_RECORD_ID_CONFLICT")
        self._interventions = (*self._interventions, record)
        return record

    def append_feedback(self, record: OutcomeFeedbackRecord) -> OutcomeFeedbackRecord:
        for existing in self._feedback:
            if existing.feedbackId != record.feedbackId:
                continue
            if existing.feedbackDigest == record.feedbackDigest:
                return existing
            raise CaptureConflict("OUTCOME_FEEDBACK_ID_CONFLICT")
        self._feedback = (*self._feedback, record)
        return record

    def interventions(
        self, *, tenant_id: str, security_domain: str, journey_id: str
    ) -> tuple[InterventionEventRecord, ...]:
        return tuple(
            item
            for item in self._interventions
            if item.tenantId == tenant_id
            and item.securityDomain == security_domain
            and item.journeyId == journey_id
        )

    def feedback(
        self, *, tenant_id: str, security_domain: str, journey_id: str
    ) -> tuple[OutcomeFeedbackRecord, ...]:
        return tuple(
            item
            for item in self._feedback
            if item.tenantId == tenant_id
            and item.securityDomain == security_domain
            and item.journeyId == journey_id
        )


def _identifier(value: object, reason_code: str) -> str:
    if not isinstance(value, str):
        raise InterventionFeedbackFailure(reason_code)
    normalized = unicodedata.normalize("NFC", value)
    if _IDENTIFIER.fullmatch(normalized) is None:
        raise InterventionFeedbackFailure(reason_code)
    return normalized


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


class InterventionFeedbackService:
    """Authorization-first fact capture over upstream-issued immutable identities."""

    def __init__(
        self,
        repository: InterventionFeedbackRepository | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._repository = repository or InMemoryInterventionFeedbackRepository()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: uuid.uuid4().hex)
        self._intervention_replays: dict[
            tuple[str, ...], tuple[str, InterventionEventRecord]
        ] = {}
        self._feedback_replays: dict[
            tuple[str, ...], tuple[str, OutcomeFeedbackRecord]
        ] = {}

    @staticmethod
    def _authorize(
        principal: TrustedCapturePrincipal, target: TrustedInterventionTarget
    ) -> None:
        if not principal.permits(target.tenant_id, target.security_domain):
            raise CaptureDenied()

    @staticmethod
    def _validate_target(target: TrustedInterventionTarget) -> None:
        for value in (
            target.journey_id,
            target.tenant_id,
            target.security_domain,
            target.successor_revision_id,
            target.platform_execution_identity,
            target.outcome_id,
            *target.execution_evidence_ids,
        ):
            _identifier(value, "INTERVENTION_TARGET_INVALID")
        if target.predecessor_revision_id is not None:
            _identifier(target.predecessor_revision_id, "INTERVENTION_TARGET_INVALID")
        if target.provenance not in {"LIVE_EXECUTION", "SYNTHETIC_PREVIEW"}:
            raise InterventionFeedbackFailure("CAPTURE_PROVENANCE_INVALID")
        if (
            target.predecessor_digest is not None
            and _DIGEST.fullmatch(target.predecessor_digest) is None
        ):
            raise InterventionFeedbackFailure("INTERVENTION_TARGET_INVALID")
        if _DIGEST.fullmatch(target.successor_digest) is None:
            raise InterventionFeedbackFailure("INTERVENTION_TARGET_INVALID")
        if not target.execution_evidence_ids or len(target.execution_evidence_ids) > 32:
            raise InterventionFeedbackFailure("INTERVENTION_TARGET_INVALID")
        if len(set(target.execution_evidence_ids)) != len(
            target.execution_evidence_ids
        ):
            raise InterventionFeedbackFailure("INTERVENTION_TARGET_INVALID")

    def _decision_time(self) -> str:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise CaptureUnavailable("CAPTURE_CLOCK_INVALID")
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")

    def _issued_id(self, prefix: str) -> str:
        suffix = _identifier(self._id_factory(), "CAPTURE_ID_FACTORY_INVALID")
        return f"{prefix}:{suffix}"

    @staticmethod
    def _record_semantic(record: InterventionEventRecord) -> dict[str, object]:
        return record.model_dump(exclude={"recordDigest"}, mode="json")

    @staticmethod
    def _feedback_semantic(record: OutcomeFeedbackRecord) -> dict[str, object]:
        return record.model_dump(exclude={"feedbackDigest"}, mode="json")

    def _verify_intervention(self, record: object) -> InterventionEventRecord:
        if not isinstance(record, InterventionEventRecord):
            raise CaptureUnavailable("CAPTURE_REPOSITORY_CORRUPT")
        if record.recordDigest != _canonical_digest(self._record_semantic(record)):
            raise CaptureUnavailable("CAPTURE_REPOSITORY_CORRUPT")
        return record

    def _verify_feedback(self, record: object) -> OutcomeFeedbackRecord:
        if not isinstance(record, OutcomeFeedbackRecord):
            raise CaptureUnavailable("CAPTURE_REPOSITORY_CORRUPT")
        if record.feedbackDigest != _canonical_digest(self._feedback_semantic(record)):
            raise CaptureUnavailable("CAPTURE_REPOSITORY_CORRUPT")
        return record

    def _interventions(
        self, target: TrustedInterventionTarget
    ) -> tuple[InterventionEventRecord, ...]:
        try:
            records = self._repository.interventions(
                tenant_id=target.tenant_id,
                security_domain=target.security_domain,
                journey_id=target.journey_id,
            )
        except InterventionFeedbackFailure:
            raise
        except Exception as exc:
            raise CaptureUnavailable() from exc
        verified = tuple(self._verify_intervention(item) for item in records)
        return tuple(
            item
            for item in verified
            if item.successorRevisionId == target.successor_revision_id
            and item.platformExecutionIdentity == target.platform_execution_identity
            and item.outcomeId == target.outcome_id
            and item.executionEvidenceIds == target.execution_evidence_ids
            and item.provenance == target.provenance
        )

    def _feedback(
        self, target: TrustedInterventionTarget
    ) -> tuple[OutcomeFeedbackRecord, ...]:
        try:
            records = self._repository.feedback(
                tenant_id=target.tenant_id,
                security_domain=target.security_domain,
                journey_id=target.journey_id,
            )
        except InterventionFeedbackFailure:
            raise
        except Exception as exc:
            raise CaptureUnavailable() from exc
        verified = tuple(self._verify_feedback(item) for item in records)
        return tuple(
            item
            for item in verified
            if item.canonicalWorkflowRevisionId == target.successor_revision_id
            and item.platformExecutionIdentity == target.platform_execution_identity
            and item.outcomeId == target.outcome_id
            and item.evidenceId in target.execution_evidence_ids
            and item.provenance == target.provenance
        )

    @staticmethod
    def _assert_current_binding(
        target: TrustedInterventionTarget,
        *,
        predecessor_revision_id: str,
        successor_revision_id: str,
        outcome_id: str,
        evidence_id: str,
    ) -> None:
        if target.predecessor_revision_id is None:
            raise CaptureConflict("INTERVENTION_PREDECESSOR_REQUIRED")
        if (
            predecessor_revision_id != target.predecessor_revision_id
            or successor_revision_id != target.successor_revision_id
            or outcome_id != target.outcome_id
            or evidence_id not in target.execution_evidence_ids
        ):
            raise CaptureConflict("INTERVENTION_TARGET_STALE_OR_MISMATCHED")

    def capture_intervention(
        self,
        principal: TrustedCapturePrincipal,
        target: TrustedInterventionTarget,
        command: InterventionCaptureCommand,
    ) -> InterventionEventRecord:
        self._authorize(principal, target)
        self._validate_target(target)
        self._assert_current_binding(
            target,
            predecessor_revision_id=command.predecessorRevisionId,
            successor_revision_id=command.successorRevisionId,
            outcome_id=command.outcomeId,
            evidence_id=command.evidenceId,
        )
        if command.correctionPatchReference == "NO_PATCH" and command.eventKind != (
            "RESULT_FEEDBACK_PROVIDED"
        ):
            raise InterventionFeedbackFailure("CORRECTION_PATCH_REFERENCE_REQUIRED")
        fingerprint = _canonical_digest(command.model_dump(mode="json"))
        replay_key = (
            target.tenant_id,
            target.security_domain,
            target.journey_id,
            target.successor_revision_id,
            command.eventKind,
            command.affectedElementReference,
        )
        replay = self._intervention_replays.get(replay_key)
        if replay is not None:
            if replay[0] == fingerprint:
                return replay[1]
            raise CaptureConflict("INTERVENTION_REPLAY_CONFLICT")
        event_id = self._issued_id("intervention-event")
        record_id = self._issued_id("intervention-record")
        values = {
            "recordId": record_id,
            "interventionEventId": event_id,
            "recordDigest": "",
            "lifecycle": "RECORDED",
            "supersedesRecordId": None,
            "journeyId": target.journey_id,
            "predecessorRevisionId": target.predecessor_revision_id,
            "predecessorRevisionDigest": target.predecessor_digest,
            "successorRevisionId": target.successor_revision_id,
            "successorRevisionDigest": target.successor_digest,
            "affectedElementReference": command.affectedElementReference,
            "correctionPatchReference": command.correctionPatchReference,
            "eventKind": command.eventKind,
            "reasonCode": command.reasonCode,
            "principalId": principal.principal_id,
            "decisionTime": self._decision_time(),
            "tenantId": target.tenant_id,
            "securityDomain": target.security_domain,
            "platformExecutionIdentity": target.platform_execution_identity,
            "outcomeId": target.outcome_id,
            "executionEvidenceIds": target.execution_evidence_ids,
            "provenance": target.provenance,
            "optimizationUseConsentDecision": (command.optimizationUseConsentDecision),
        }
        draft = InterventionEventRecord.model_validate(values)
        record = draft.model_copy(
            update={"recordDigest": _canonical_digest(self._record_semantic(draft))}
        )
        try:
            appended = self._repository.append_intervention(record)
        except InterventionFeedbackFailure:
            raise
        except Exception as exc:
            raise CaptureUnavailable() from exc
        verified = self._verify_intervention(appended)
        self._intervention_replays[replay_key] = (fingerprint, verified)
        return verified

    def append_intervention_lifecycle(
        self,
        principal: TrustedCapturePrincipal,
        target: TrustedInterventionTarget,
        intervention_event_id: str,
        command: InterventionLifecycleCommand,
    ) -> InterventionEventRecord:
        self._authorize(principal, target)
        self._validate_target(target)
        event_id = _identifier(intervention_event_id, "INTERVENTION_EVENT_ID_INVALID")
        records = tuple(
            item
            for item in self._interventions(target)
            if item.interventionEventId == event_id
        )
        if not records:
            raise CaptureNotFound()
        latest = records[-1]
        if (
            latest.successorRevisionId != target.successor_revision_id
            or latest.outcomeId != target.outcome_id
            or latest.platformExecutionIdentity != target.platform_execution_identity
        ):
            raise CaptureConflict("INTERVENTION_TARGET_STALE_OR_MISMATCHED")
        if latest.lifecycle == command.lifecycle:
            return latest
        if command.lifecycle not in _TRANSITIONS[latest.lifecycle]:
            raise CaptureConflict("INTERVENTION_LIFECYCLE_CONFLICT")
        values = latest.model_dump(mode="json")
        values.update(
            {
                "recordId": self._issued_id("intervention-record"),
                "recordDigest": "",
                "lifecycle": command.lifecycle,
                "supersedesRecordId": latest.recordId,
                "reasonCode": _LIFECYCLE_REASON[command.lifecycle],
                "principalId": principal.principal_id,
                "decisionTime": self._decision_time(),
            }
        )
        draft = InterventionEventRecord.model_validate(values)
        record = draft.model_copy(
            update={"recordDigest": _canonical_digest(self._record_semantic(draft))}
        )
        try:
            appended = self._repository.append_intervention(record)
        except InterventionFeedbackFailure:
            raise
        except Exception as exc:
            raise CaptureUnavailable() from exc
        return self._verify_intervention(appended)

    def capture_feedback(
        self,
        principal: TrustedCapturePrincipal,
        target: TrustedInterventionTarget,
        command: OutcomeFeedbackCommand,
    ) -> OutcomeFeedbackRecord:
        self._authorize(principal, target)
        self._validate_target(target)
        if (
            command.outcomeId != target.outcome_id
            or command.evidenceId not in target.execution_evidence_ids
        ):
            raise CaptureConflict("OUTCOME_FEEDBACK_TARGET_STALE_OR_MISMATCHED")
        if len(set(command.reasonCodes)) != len(command.reasonCodes):
            raise InterventionFeedbackFailure("DUPLICATE_FEEDBACK_REASON")
        supersedes = command.supersedesFeedbackId or "NONE"
        fingerprint = _canonical_digest(command.model_dump(mode="json"))
        replay_key = (
            target.tenant_id,
            target.security_domain,
            target.journey_id,
            target.outcome_id or "",
            command.evidenceId,
            supersedes,
        )
        records = tuple(
            item
            for item in self._feedback(target)
            if item.outcomeId == target.outcome_id
            and item.evidenceId == command.evidenceId
        )
        current = records[-1] if records else None
        if current is None and command.supersedesFeedbackId is not None:
            raise CaptureConflict("OUTCOME_FEEDBACK_SUPERSESSION_MISMATCH")
        if current is not None and command.supersedesFeedbackId is None:
            if (
                current.assessment == command.assessment
                and current.reasonCodes == tuple(command.reasonCodes)
            ):
                self._feedback_replays[replay_key] = (fingerprint, current)
                return current
            raise CaptureConflict("OUTCOME_FEEDBACK_SUPERSESSION_REQUIRED")
        replay = self._feedback_replays.get(replay_key)
        if replay is not None:
            if replay[0] == fingerprint:
                return replay[1]
            raise CaptureConflict("OUTCOME_FEEDBACK_REPLAY_CONFLICT")
        if current is not None and command.supersedesFeedbackId != current.feedbackId:
            raise CaptureConflict("OUTCOME_FEEDBACK_SUPERSESSION_MISMATCH")
        values = {
            "feedbackId": self._issued_id("outcome-feedback"),
            "feedbackDigest": "",
            "revision": 1 if current is None else current.revision + 1,
            "supersedesFeedbackId": None if current is None else current.feedbackId,
            "journeyId": target.journey_id,
            "canonicalWorkflowRevisionId": target.successor_revision_id,
            "platformExecutionIdentity": target.platform_execution_identity,
            "outcomeId": target.outcome_id,
            "evidenceId": command.evidenceId,
            "assessment": command.assessment,
            "reasonCodes": tuple(command.reasonCodes),
            "principalId": principal.principal_id,
            "decisionTime": self._decision_time(),
            "tenantId": target.tenant_id,
            "securityDomain": target.security_domain,
            "provenance": target.provenance,
        }
        draft = OutcomeFeedbackRecord.model_validate(values)
        record = draft.model_copy(
            update={"feedbackDigest": _canonical_digest(self._feedback_semantic(draft))}
        )
        try:
            appended = self._repository.append_feedback(record)
        except InterventionFeedbackFailure:
            raise
        except Exception as exc:
            raise CaptureUnavailable() from exc
        verified = self._verify_feedback(appended)
        self._feedback_replays[replay_key] = (fingerprint, verified)
        return verified

    def project(
        self,
        principal: TrustedCapturePrincipal,
        target: TrustedInterventionTarget,
    ) -> InterventionFeedbackResponse:
        self._authorize(principal, target)
        self._validate_target(target)
        interventions = self._interventions(target)
        feedback = self._feedback(target)
        superseded = {
            item.supersedesFeedbackId
            for item in feedback
            if item.supersedesFeedbackId is not None
        }
        feedback_views = tuple(
            OutcomeFeedbackView(
                lifecycle=(
                    "SUPERSEDED" if item.feedbackId in superseded else "RECORDED"
                ),
                record=item,
            )
            for item in feedback
        )
        identity = InterventionFeedbackIdentity(
            journeyId=target.journey_id,
            tenantId=target.tenant_id,
            securityDomain=target.security_domain,
            predecessorRevisionId=target.predecessor_revision_id,
            successorRevisionId=target.successor_revision_id,
            platformExecutionIdentity=target.platform_execution_identity,
            outcomeId=target.outcome_id,
            evidenceIds=target.execution_evidence_ids,
            provenance=target.provenance,
        )
        product = InterventionFeedbackProjection(
            projection="PRODUCT",
            identity=identity,
            interventions=interventions,
            outcomeFeedback=feedback_views,
        )
        technical = InterventionFeedbackProjection(
            projection="TECHNICAL",
            identity=identity,
            interventions=interventions,
            outcomeFeedback=feedback_views,
        )
        return InterventionFeedbackResponse(product=product, technical=technical)
