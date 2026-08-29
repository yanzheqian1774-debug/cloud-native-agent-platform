"""Bounded Product live-planning and immutable-correction coordinator.

This module owns no persistence or upstream authority. It accepts backend-issued
Package 1--4 identities, validates their shared scope, and coordinates exact-digest
approval and an existing execution-authority handoff in memory.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from agent_console.live_journey_schemas import (
    JourneyCitation,
    JourneyIdentity,
    JourneyOutcome,
    JourneyProjection,
    JourneyRevision,
    LiveJourneyResponse,
)

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+-]{0,255}")
_DIGEST = re.compile(r"[0-9a-f]{64}")


class LiveJourneyError(ValueError):
    state = "ERROR"
    reason_code = "LIVE_JOURNEY_ERROR"
    status_code = 422


class JourneyDenied(LiveJourneyError):
    state = "DENIED"
    reason_code = "LIVE_JOURNEY_ACCESS_DENIED"
    status_code = 403


class JourneyNotFound(LiveJourneyError):
    state = "NOT_FOUND"
    reason_code = "LIVE_JOURNEY_NOT_FOUND"
    status_code = 404


class JourneyAuthorityMissing(LiveJourneyError):
    state = "AUTHORITY_MISSING"
    reason_code = "LIVE_JOURNEY_AUTHORITY_MISSING"
    status_code = 503


class JourneyConflict(LiveJourneyError):
    reason_code = "LIVE_JOURNEY_CONFLICT"
    status_code = 409


def _identifier(value: object, code: str) -> str:
    if not isinstance(value, str):
        raise LiveJourneyError(code)
    normalized = unicodedata.normalize("NFC", value)
    if _ID.fullmatch(normalized) is None:
        raise LiveJourneyError(code)
    return normalized


def _digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class TrustedJourneyPrincipal:
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
class LiveJourneySeed:
    journey_id: str
    tenant_id: str
    security_domain: str
    canonical_workflow_revision_id: str
    canonical_digest: str
    approval_id: str
    objective: str
    task_ids: tuple[str, ...]
    shared_snapshot_id: str
    graph_snapshot_id: str
    platform_execution_identity: str
    placement_decision_id: str
    evidence_ids: tuple[str, ...]
    citations: tuple[JourneyCitation, ...]
    outcome: JourneyOutcome
    answer: str
    provenance: str = "LIVE_EXECUTION"
    knowledge_state: str = "AVAILABLE"
    placement_state: str = "PLACED"


class ExistingExecutionAuthority(Protocol):
    def rerun(
        self, *, revision_id: str, digest: str, tenant_id: str, security_domain: str
    ) -> AuthorizedRerunResult: ...


@dataclass(frozen=True, slots=True)
class AuthorizedRerunResult:
    platform_execution_identity: str
    shared_snapshot_id: str
    graph_snapshot_id: str
    evidence_ids: tuple[str, ...]
    citations: tuple[JourneyCitation, ...]
    outcome: JourneyOutcome
    answer: str
    knowledge_state: str = "AVAILABLE"


class UnavailableExecutionAuthority:
    def rerun(self, **_: str) -> AuthorizedRerunResult:
        raise JourneyAuthorityMissing("EXECUTION_AUTHORITY_UNAVAILABLE")


class LiveJourneyCoordinator:
    """Coordinates presentation and commands without replacing upstream owners."""

    def __init__(self, execution_authority: ExistingExecutionAuthority | None = None):
        self._execution = execution_authority or UnavailableExecutionAuthority()
        self._journeys: dict[str, tuple[JourneyRevision | None, JourneyRevision]] = {}
        self._provenance: dict[str, str] = {}
        self._replays: dict[str, tuple[str, str]] = {}

    def register_live(self, seed: LiveJourneySeed) -> LiveJourneyResponse:
        if seed.provenance != "LIVE_EXECUTION":
            raise LiveJourneyError("LIVE_PROVENANCE_REQUIRED")
        if not _DIGEST.fullmatch(seed.canonical_digest):
            raise LiveJourneyError("INVALID_CANONICAL_DIGEST")
        identifiers = (
            seed.journey_id,
            seed.tenant_id,
            seed.security_domain,
            seed.canonical_workflow_revision_id,
            seed.approval_id,
            seed.shared_snapshot_id,
            seed.graph_snapshot_id,
            seed.platform_execution_identity,
            seed.placement_decision_id,
            *seed.task_ids,
            *seed.evidence_ids,
        )
        for value in identifiers:
            _identifier(value, "INVALID_LIVE_AUTHORITY_IDENTITY")
        for citation in seed.citations:
            if citation.status not in {"AVAILABLE", "STALE"}:
                raise LiveJourneyError("INVALID_LIVE_CITATION_STATE")
        if seed.knowledge_state not in {"AVAILABLE", "STALE"} and (
            seed.citations or seed.answer
        ):
            raise LiveJourneyError("KNOWLEDGE_FAILURE_CANNOT_PRODUCE_ANSWER")
        identity = JourneyIdentity(
            tenantId=seed.tenant_id,
            securityDomain=seed.security_domain,
            canonicalWorkflowRevisionId=seed.canonical_workflow_revision_id,
            canonicalDigest=seed.canonical_digest,
            sharedSnapshotId=seed.shared_snapshot_id,
            graphSnapshotId=seed.graph_snapshot_id,
            platformExecutionIdentity=seed.platform_execution_identity,
            approvalId=seed.approval_id,
            placementDecisionId=seed.placement_decision_id,
            evidenceIds=list(seed.evidence_ids),
            citationIds=[item.citationId for item in seed.citations],
        )
        revision = JourneyRevision(
            revision=1,
            predecessorRevisionId=None,
            objective=seed.objective,
            lifecycle="EXECUTABLE",
            approvalState="APPROVED",
            identity=identity,
            planTaskIds=list(seed.task_ids),
            matchState="MATCHED",
            placementState=seed.placement_state,
            knowledgeState=seed.knowledge_state,
            executionState="SUCCEEDED",
            answer=seed.answer,
            citations=list(seed.citations),
            outcome=seed.outcome,
            limitationCodes=[],
        )
        self._journeys[seed.journey_id] = (None, revision)
        self._provenance[seed.journey_id] = seed.provenance
        return self.get(seed.journey_id, self._system_principal(seed))

    @staticmethod
    def _system_principal(seed: LiveJourneySeed) -> TrustedJourneyPrincipal:
        return TrustedJourneyPrincipal(
            "system:registration", seed.tenant_id, seed.security_domain, True
        )

    def _authorized(
        self, journey_id: str, principal: TrustedJourneyPrincipal
    ) -> tuple[JourneyRevision | None, JourneyRevision]:
        pair = self._journeys.get(journey_id)
        if pair is None:
            raise JourneyNotFound
        current = pair[1]
        identity = current.identity
        if not principal.permits(identity.tenantId, identity.securityDomain):
            raise JourneyDenied
        return pair

    def get(
        self, journey_id: str, principal: TrustedJourneyPrincipal
    ) -> LiveJourneyResponse:
        predecessor, successor = self._authorized(journey_id, principal)
        provenance = self._provenance[journey_id]
        state = "STALE" if successor.knowledgeState == "STALE" else "LIVE"
        product = JourneyProjection(
            projection="PRODUCT", identity=successor.identity, revision=successor
        )
        technical = JourneyProjection(
            projection="TECHNICAL", identity=successor.identity, revision=successor
        )
        return LiveJourneyResponse(
            journeyId=journey_id,
            state=state,
            provenance=provenance,
            reasonCode="LIVE_JOURNEY_READY"
            if state == "LIVE"
            else "LIVE_KNOWLEDGE_STALE",
            product=product,
            technical=technical,
            predecessor=predecessor,
            successor=successor,
        )

    def correct(
        self,
        journey_id: str,
        principal: TrustedJourneyPrincipal,
        *,
        predecessor_revision_id: str,
        predecessor_digest: str,
        objective: str,
        reason_code: str,
    ) -> LiveJourneyResponse:
        predecessor, current = self._authorized(journey_id, principal)
        del predecessor
        if current.lifecycle == "PENDING_APPROVAL":
            raise JourneyConflict("SUCCESSOR_ALREADY_PENDING")
        if (
            predecessor_revision_id != current.identity.canonicalWorkflowRevisionId
            or predecessor_digest != current.identity.canonicalDigest
        ):
            raise JourneyConflict("CORRECTION_BINDING_MISMATCH")
        normalized = " ".join(unicodedata.normalize("NFC", objective).split())
        if not normalized or len(normalized) > 500 or normalized == current.objective:
            raise LiveJourneyError("INVALID_CORRECTION_PATCH")
        _identifier(reason_code.upper(), "INVALID_CORRECTION_REASON")
        semantic = {
            "schemaVersion": "live-journey.v1",
            "tenantId": current.identity.tenantId,
            "securityDomain": current.identity.securityDomain,
            "predecessorRevisionId": predecessor_revision_id,
            "predecessorDigest": predecessor_digest,
            "objective": normalized,
            "tasks": current.planTaskIds,
        }
        digest = _digest(semantic)
        revision_id = f"canonical-workflow-revision:{digest}"
        identity = current.identity.model_copy(
            update={
                "canonicalWorkflowRevisionId": revision_id,
                "canonicalDigest": digest,
                "sharedSnapshotId": f"journey-snapshot:{digest}",
                "platformExecutionIdentity": None,
                "approvalId": f"pending-approval:{digest}",
                "evidenceIds": [],
                "citationIds": [],
            }
        )
        successor = JourneyRevision(
            revision=current.revision + 1,
            predecessorRevisionId=current.identity.canonicalWorkflowRevisionId,
            objective=normalized,
            lifecycle="PENDING_APPROVAL",
            approvalState="PENDING",
            identity=identity,
            planTaskIds=current.planTaskIds,
            matchState="MATCHED",
            placementState=current.placementState,
            knowledgeState="UNAVAILABLE",
            executionState="NOT_REQUESTED",
            answer=None,
            citations=[],
            outcome=None,
            limitationCodes=["FRESH_EXACT_DIGEST_APPROVAL_REQUIRED"],
        )
        immutable_predecessor = current.model_copy(update={"lifecycle": "SUPERSEDED"})
        self._journeys[journey_id] = (immutable_predecessor, successor)
        return self.get(journey_id, principal)

    def approve(
        self,
        journey_id: str,
        principal: TrustedJourneyPrincipal,
        *,
        candidate_digest: str,
        decision: str,
        reason_code: str,
        replay_identity: str,
    ) -> LiveJourneyResponse:
        predecessor, successor = self._authorized(journey_id, principal)
        if successor.lifecycle != "PENDING_APPROVAL":
            raise JourneyConflict("APPROVAL_NOT_PENDING")
        if candidate_digest != successor.identity.canonicalDigest:
            raise JourneyConflict("APPROVAL_DIGEST_MISMATCH")
        _identifier(reason_code.upper(), "INVALID_APPROVAL_REASON")
        replay = _identifier(replay_identity, "INVALID_REPLAY_IDENTITY")
        replay_value = (candidate_digest, decision)
        existing = self._replays.get(replay)
        if existing is not None and existing != replay_value:
            raise JourneyConflict("APPROVAL_REPLAY_MISMATCH")
        self._replays[replay] = replay_value
        if decision == "REJECT":
            rejected = successor.model_copy(update={"approvalState": "REJECTED"})
            self._journeys[journey_id] = (predecessor, rejected)
        elif decision == "APPROVE":
            approval_seed = {
                "digest": candidate_digest,
                "actor": principal.principal_id,
                "replay": replay,
                "reason": reason_code.upper(),
                "decidedAt": datetime.now(UTC).isoformat(),
            }
            approval_id = f"planning-approval:{_digest(approval_seed)}"
            approved = successor.model_copy(
                update={
                    "lifecycle": "EXECUTABLE",
                    "approvalState": "APPROVED",
                    "identity": successor.identity.model_copy(
                        update={"approvalId": approval_id}
                    ),
                    "limitationCodes": [],
                }
            )
            self._journeys[journey_id] = (predecessor, approved)
        else:
            raise LiveJourneyError("INVALID_APPROVAL_DECISION")
        return self.get(journey_id, principal)

    def rerun(
        self,
        journey_id: str,
        principal: TrustedJourneyPrincipal,
        *,
        revision_id: str,
        digest: str,
    ) -> LiveJourneyResponse:
        predecessor, successor = self._authorized(journey_id, principal)
        if successor.lifecycle != "EXECUTABLE" or successor.approvalState != "APPROVED":
            raise JourneyConflict("EXACT_APPROVAL_REQUIRED")
        if (
            revision_id != successor.identity.canonicalWorkflowRevisionId
            or digest != successor.identity.canonicalDigest
        ):
            raise JourneyConflict("RERUN_REVISION_DIGEST_MISMATCH")
        result = self._execution.rerun(
            revision_id=revision_id,
            digest=digest,
            tenant_id=successor.identity.tenantId,
            security_domain=successor.identity.securityDomain,
        )
        if not isinstance(result, AuthorizedRerunResult):
            raise JourneyAuthorityMissing("EXECUTION_AUTHORITY_RESULT_INVALID")
        for value in (
            result.platform_execution_identity,
            result.shared_snapshot_id,
            result.graph_snapshot_id,
            *result.evidence_ids,
        ):
            _identifier(value, "INVALID_EXECUTION_AUTHORITY_IDENTITY")
        if result.knowledge_state not in {"AVAILABLE", "STALE"} and (
            result.citations or result.answer
        ):
            raise JourneyAuthorityMissing("EXECUTION_AUTHORITY_RESULT_INVALID")
        rerunning = successor.model_copy(
            update={
                "executionState": (
                    "SUCCEEDED"
                    if result.outcome.classification == "SUCCEEDED"
                    else "FAILED"
                ),
                "identity": successor.identity.model_copy(
                    update={
                        "platformExecutionIdentity": result.platform_execution_identity,
                        "sharedSnapshotId": result.shared_snapshot_id,
                        "graphSnapshotId": result.graph_snapshot_id,
                        "evidenceIds": list(result.evidence_ids),
                        "citationIds": [item.citationId for item in result.citations],
                    }
                ),
                "knowledgeState": result.knowledge_state,
                "answer": result.answer,
                "citations": list(result.citations),
                "outcome": result.outcome,
                "limitationCodes": ["EXISTING_EXECUTION_AUTHORITY_RESULT"],
            }
        )
        self._journeys[journey_id] = (predecessor, rerunning)
        return self.get(journey_id, principal)
