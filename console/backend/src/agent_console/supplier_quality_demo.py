"""Bounded Package 7 live supplier-quality journey composition bridge.

The bridge owns process-local orchestration and replay state only. Package files
are inputs, not authorities, and every execution crosses the existing Planning,
Definition, Matching, Knowledge, Placement, Coordinator, Native Provider,
Evidence, Graph, and Live Journey seams.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from agent_operator.execution_coordinator import (
    EvidenceAvailability,
    ExecutionClassification,
    TaskEvidenceSubject,
    TaskExecutionContext,
    TaskExecutionCoordinator,
)
from agent_runtime.providers.native import NativeRuntimeProvider
from agent_runtime.providers.native.compatibility import (
    PROVIDER_PACKAGE,
    RUNTIME_TARGET,
)
from agent_runtime.providers.native.models import NativeInvocation

from agent_console.definition_authority import (
    InMemoryDefinitionAuthority,
    MatchAuthorizationAction,
    PublicationAction,
    RoleDescriptor,
    create_definition_version,
    create_match_authorization_decision,
    create_publication_decision,
)
from agent_console.execution_snapshot import assemble_execution_snapshot
from agent_console.graph_projection import (
    Cardinality,
    GraphLayer,
    NodeSpec,
    NodeType,
    Phase,
    ProjectionVisibility,
    RelationSpec,
    RelationType,
    SnapshotContext,
    build_graph,
)
from agent_console.knowledge_authorization import (
    AuthorizationAction,
    KnowledgeAuthorizationDecision,
)
from agent_console.knowledge_citations import assemble_citations
from agent_console.knowledge_evidence import (
    InMemoryKnowledgeEvidenceRepository,
    KnowledgeRetrievalEvidence,
)
from agent_console.knowledge_pack import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgePack,
    KnowledgeSection,
    KnowledgeStatus,
)
from agent_console.knowledge_retrieval import (
    RETRIEVAL_POLICY_VERSION,
    InMemoryKnowledgeSource,
    KnowledgeFilter,
    KnowledgeRetrievalRequest,
    retrieve,
)
from agent_console.live_journey import (
    JourneyConflict,
    JourneyNotFound,
    LiveJourneyCoordinator,
    LiveJourneyError,
    LiveJourneySeed,
    TrustedJourneyPrincipal,
)
from agent_console.live_journey_schemas import (
    JourneyCitation,
    JourneyIdentity,
    JourneyOutcome,
    JourneyProjection,
    JourneyRevision,
    JourneyTaskProjection,
    JourneyUnderstanding,
    LiveJourneyResponse,
)
from agent_console.matching import (
    MatchingRequest,
    MatchOutcome,
    PublishedRoleMatcher,
    RoleRequirement,
    TaskRoleRequirements,
)
from agent_console.planning import (
    CanonicalWorkflowRevision,
    PlanningDecision,
    PlanningEngine,
    PlanningResult,
    ProductSemanticCorrection,
    create_business_question,
)
from agent_console.planning_generator import SupplierQualityReferenceGenerator
from agent_console.runtime_placement import (
    DeclaredNativeTarget,
    MatchedDefinitionBinding,
    NativePlacementEvaluator,
    PlacementAuthorization,
    PlacementOutcome,
    TargetState,
    derive_runtime_requirement,
)
from agent_console.supplier_quality_demo_schemas import (
    SupplierQualityDemoCallCounts,
    SupplierQualityDemoResetRequest,
    SupplierQualityDemoResetResponse,
    SupplierQualityDemoStartRequest,
    SupplierQualityDemoStartResponse,
)

SCENARIO_ID = "s5-v0.2-supplier-quality-v1"
NAMESPACE = "s5-v02-supplier-quality-demo"
TENANT_ID = "tenant-a"
SECURITY_DOMAIN = "supplier-quality"
MATCH_PURPOSE = "published-role-matching"
KNOWLEDGE_PURPOSE = "supplier-quality-analysis"
AUTHORITY_REVISION = "s5-impl-037-v1"
AUTHORITY_TIME = datetime(2026, 8, 29, tzinfo=UTC)

_DIGEST = re.compile(r"[0-9a-f]{64}")
_SAFE_RELATIVE = re.compile(r"[A-Za-z0-9.][A-Za-z0-9._/-]{0,255}")
_MATERIALIZED_INPUTS = frozenset(
    {
        "scenario-pack-v1.json",
        "namespace.yaml",
        "data/supplier-quality-cases-v1.json",
        "catalog/descriptors-v1.json",
        "catalog/published-roles-v1.json",
        "history/synthetic-history-v1.json",
        "knowledge/knowledge-pack-v1.json",
        "knowledge/8d-procedure-v1.md",
    }
)
_DECLARED_INPUTS = _MATERIALIZED_INPUTS | {"bootstrap.sh", "reset.sh"}


class SupplierQualityDemoFailure(LiveJourneyError):
    reason_code = "SUPPLIER_QUALITY_DEMO_ERROR"

    def __init__(self, reason_code: str = "SUPPLIER_QUALITY_DEMO_ERROR") -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


class SupplierQualityDemoDenied(SupplierQualityDemoFailure):
    state = "DENIED"
    status_code = 403


class SupplierQualityDemoNotFound(SupplierQualityDemoFailure):
    state = "NOT_FOUND"
    status_code = 404


class SupplierQualityDemoConflict(SupplierQualityDemoFailure):
    state = "CONFLICT"
    status_code = 409


class SupplierQualityDemoUnavailable(SupplierQualityDemoFailure):
    state = "AUTHORITY_MISSING"
    status_code = 503


@dataclass(frozen=True, slots=True)
class MaterializedPackage:
    root: Path
    manifest: Mapping[str, Any]
    cases: Mapping[str, Any]
    descriptors: Mapping[str, Any]
    roles: Mapping[str, Any]
    knowledge_manifest: Mapping[str, Any]
    knowledge_text: str


@dataclass(slots=True)
class _CallCounts:
    planning_generator: int = 0
    matching_requests: int = 0
    knowledge_source_reads: int = 0
    placement_evaluations: int = 0
    coordinator_executions: int = 0
    native_provider_invocations: int = 0
    capability_gateway_invocations: int = 0
    fixture_executions: int = 0

    def snapshot(self) -> SupplierQualityDemoCallCounts:
        return SupplierQualityDemoCallCounts(
            planningGenerator=self.planning_generator,
            matchingRequests=self.matching_requests,
            knowledgeSourceReads=self.knowledge_source_reads,
            placementEvaluations=self.placement_evaluations,
            coordinatorExecutions=self.coordinator_executions,
            nativeProviderInvocations=self.native_provider_invocations,
            capabilityGatewayInvocations=self.capability_gateway_invocations,
            fixtureExecutions=self.fixture_executions,
        )


class _CountingGenerator(SupplierQualityReferenceGenerator):
    def __init__(self, counts: _CallCounts) -> None:
        self._counts = counts

    def generate(self, question):
        self._counts.planning_generator += 1
        return super().generate(question)


@dataclass(frozen=True, slots=True)
class _PipelineResult:
    revision: CanonicalWorkflowRevision
    placement_decision_id: str
    platform_execution_identity: str
    shared_snapshot_id: str
    graph_snapshot_id: str
    evidence_ids: tuple[str, ...]
    citations: tuple[JourneyCitation, ...]
    outcome: JourneyOutcome
    answer: str
    knowledge_state: str


@dataclass(slots=True)
class _JourneyRecord:
    journey_id: str
    replay_identity: str
    request_fingerprint: str
    reset_token: str
    root: Path
    package: MaterializedPackage
    canonical: CanonicalWorkflowRevision | None
    question: object
    display: LiveJourneyResponse
    counts_at_start: SupplierQualityDemoCallCounts
    active: bool = True
    pending: PlanningResult | None = None
    outcomes: list[JourneyOutcome] = field(default_factory=list)
    execution_evidence_ids: list[tuple[str, ...]] = field(default_factory=list)


class SupplierQualityDemoService:
    """Run the exact Package 7 scenario through existing internal authorities."""

    def __init__(
        self,
        *,
        materialized_root: Path | None,
        live_journeys: LiveJourneyCoordinator,
        clock: Callable[[], datetime] | None = None,
        opaque_id: Callable[[], str] | None = None,
        knowledge_action: AuthorizationAction = AuthorizationAction.ALLOW,
        knowledge_status: KnowledgeStatus = KnowledgeStatus.AVAILABLE,
        target_state: TargetState = TargetState.AVAILABLE,
        execution_authority_factory: Callable[
            [Callable[[], datetime], Callable[[], str]], Any
        ],
    ) -> None:
        self._configured_root = materialized_root
        self._live = live_journeys
        self._clock = clock or (lambda: datetime.now(UTC))
        self._opaque_id = opaque_id or (lambda: str(uuid4()))
        self._knowledge_action = knowledge_action
        self._knowledge_status = knowledge_status
        self._target_state = target_state
        self._planning = PlanningEngine()
        self._definition = InMemoryDefinitionAuthority(
            source_authority_revision=AUTHORITY_REVISION
        )
        self._knowledge_evidence = InMemoryKnowledgeEvidenceRepository()
        self._execution_authority = execution_authority_factory(
            self._clock, self._opaque_id
        )
        self._execution_evidence = self._execution_authority.evidence_repository
        self._counts = _CallCounts()
        self._records: dict[str, _JourneyRecord] = {}
        self._start_replays: dict[str, tuple[str, str]] = {}
        self._reset_secret = self._opaque_id()
        self._definitions_ready = False

    @property
    def counts(self) -> SupplierQualityDemoCallCounts:
        return self._counts.snapshot()

    @property
    def execution_evidence(self) -> tuple[Any, ...]:
        return self._execution_evidence.records

    def knowledge_evidence_count(self) -> int:
        return len(
            self._knowledge_evidence.records(
                tenant_id=TENANT_ID, security_domain=SECURITY_DOMAIN
            )
        )

    def outcome_history(self, journey_id: str) -> tuple[JourneyOutcome, ...]:
        record = self._records.get(journey_id)
        return () if record is None else tuple(record.outcomes)

    def owns(self, journey_id: str) -> bool:
        record = self._records.get(journey_id)
        return record is not None and record.active

    def start(
        self,
        request: SupplierQualityDemoStartRequest,
        principal: TrustedJourneyPrincipal,
    ) -> SupplierQualityDemoStartResponse:
        self._require_principal(principal)
        fingerprint = _sha(
            {
                "scenarioId": request.scenarioId,
                "question": request.question,
                "locale": request.locale,
                "tenantId": principal.tenant_id,
                "securityDomain": principal.security_domain,
            }
        )
        replay = self._start_replays.get(request.replayIdentity)
        if replay is not None:
            previous_fingerprint, journey_id = replay
            if previous_fingerprint != fingerprint:
                raise SupplierQualityDemoConflict("DEMO_START_REPLAY_MISMATCH")
            record = self._records[journey_id]
            if not record.active:
                raise SupplierQualityDemoConflict("DEMO_START_REPLAY_RESET")
            return self._start_response(record, record.display, replayed=True)

        package = self._load_package(principal)
        journey_id = f"supplier-quality-journey:{self._opaque_id()}"
        normalized_question = " ".join(request.question.split())
        supplier_terms = (
            "供应商",
            "质量",
            "交付",
            "缺陷",
            "整改",
            "supplier",
            "quality",
            "defect",
            "corrective",
        )
        if not any(term in normalized_question.lower() for term in supplier_terms):
            raise SupplierQualityDemoFailure("UNSUPPORTED_SUPPLIER_QUALITY_QUESTION")
        question = create_business_question(
            request_id=f"supplier-quality-request:{self._opaque_id()}",
            tenant_id=TENANT_ID,
            security_domain=SECURITY_DOMAIN,
            principal=principal.principal_id,
            locale=request.locale,
            scenario_id=SCENARIO_ID,
            question=normalized_question,
            created_at=self._clock(),
            provenance="package7-live-initiation",
        )
        generator = _CountingGenerator(self._counts)
        result = self._planning.generate(question, generator)
        candidate = result.workflow_candidate
        if candidate is None:
            raise SupplierQualityDemoFailure("QUESTION_PLANNING_INVALID")
        if "question" not in request.model_fields_set:
            approval = self._planning.request_approval(result)
            canonical = self._planning.decide(
                result,
                approval,
                tenant_id=TENANT_ID,
                security_domain=SECURITY_DOMAIN,
                actor=principal.principal_id,
                decision=PlanningDecision.APPROVE,
                decided_at=self._clock(),
                replay_identity=f"initial-approval:{journey_id}",
                reason_code="DEMO_INITIATION_EXACT_APPROVAL",
            )
            if canonical is None:
                raise SupplierQualityDemoUnavailable("PLANNING_APPROVAL_UNAVAILABLE")
            pipeline = self._execute_revision(package, canonical, principal)
            live = self._live.register_live(
                LiveJourneySeed(
                    journey_id=journey_id,
                    tenant_id=TENANT_ID,
                    security_domain=SECURITY_DOMAIN,
                    canonical_workflow_revision_id=canonical.canonical_workflow_revision_id,
                    canonical_digest=canonical.approved_candidate_digest,
                    approval_id=canonical.approval_id,
                    objective=canonical.intent_revision.objective,
                    task_ids=canonical.ordered_task_ids,
                    shared_snapshot_id=pipeline.shared_snapshot_id,
                    graph_snapshot_id=pipeline.graph_snapshot_id,
                    platform_execution_identity=pipeline.platform_execution_identity,
                    placement_decision_id=pipeline.placement_decision_id,
                    evidence_ids=pipeline.evidence_ids,
                    citations=pipeline.citations,
                    outcome=pipeline.outcome,
                    answer=pipeline.answer,
                    knowledge_state=pipeline.knowledge_state,
                )
            )
            reset_token = self._reset_token(journey_id)
            counts = self._counts.snapshot()
            record = _JourneyRecord(
                journey_id=journey_id,
                replay_identity=request.replayIdentity,
                request_fingerprint=fingerprint,
                reset_token=reset_token,
                root=package.root,
                package=package,
                canonical=canonical,
                question=question,
                display=live,
                counts_at_start=counts,
                outcomes=[pipeline.outcome],
                execution_evidence_ids=[pipeline.evidence_ids],
            )
            self._records[journey_id] = record
            self._start_replays[request.replayIdentity] = (fingerprint, journey_id)
            return self._start_response(record, live, replayed=False)
        live = self._draft_projection(journey_id, question, result, package, revision=1)
        reset_token = self._reset_token(journey_id)
        counts = self._counts.snapshot()
        record = _JourneyRecord(
            journey_id=journey_id,
            replay_identity=request.replayIdentity,
            request_fingerprint=fingerprint,
            reset_token=reset_token,
            root=package.root,
            package=package,
            canonical=None,
            question=question,
            display=live,
            counts_at_start=counts,
            pending=result,
        )
        self._records[journey_id] = record
        self._start_replays[request.replayIdentity] = (fingerprint, journey_id)
        return self._start_response(record, live, replayed=False)

    def get(
        self, journey_id: str, principal: TrustedJourneyPrincipal
    ) -> LiveJourneyResponse:
        return self._authorized_record(journey_id, principal).display

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
        record = self._authorized_record(journey_id, principal)
        current = record.display.successor
        predecessor = record.canonical
        if record.pending is not None:
            current_candidate = record.pending.workflow_candidate
            if (
                current_candidate is None
                or predecessor_digest != current_candidate.candidate_digest
            ):
                raise JourneyConflict("CORRECTION_BINDING_MISMATCH")
            if predecessor_revision_id != current.identity.canonicalWorkflowRevisionId:
                raise JourneyConflict("CORRECTION_BINDING_MISMATCH")
            normalized = " ".join(objective.split())
            if not normalized or len(normalized) > 500:
                raise SupplierQualityDemoFailure("INVALID_CORRECTION_PATCH")
            question = create_business_question(
                request_id=f"supplier-quality-correction:{self._opaque_id()}",
                tenant_id=TENANT_ID,
                security_domain=SECURITY_DOMAIN,
                principal=principal.principal_id,
                locale="zh-CN",
                scenario_id=SCENARIO_ID,
                question=normalized,
                created_at=self._clock(),
                provenance="deterministic-supplier-quality-correction",
            )
            generator = _CountingGenerator(self._counts)
            pending = self._planning.generate(question, generator)
            next_view = self._draft_projection(
                journey_id,
                question,
                pending,
                record.package,
                revision=current.revision + 1,
                predecessor=current,
            )
            record.pending = pending
            record.question = question
            record.display = next_view
            return next_view
        if predecessor is None:
            raise JourneyConflict("CORRECTION_AUTHORITY_MISSING")
        if (
            predecessor_revision_id != predecessor.canonical_workflow_revision_id
            or predecessor_digest != predecessor.approved_candidate_digest
        ):
            raise JourneyConflict("CORRECTION_BINDING_MISMATCH")
        normalized = " ".join(objective.split())
        if not normalized or len(normalized) > 500:
            raise SupplierQualityDemoFailure("INVALID_CORRECTION_PATCH")
        question = create_business_question(
            request_id=f"supplier-quality-correction:{self._opaque_id()}",
            tenant_id=TENANT_ID,
            security_domain=SECURITY_DOMAIN,
            principal=principal.principal_id,
            locale="en",
            scenario_id=SCENARIO_ID,
            question="Correct the approved Package 7 supplier quality objective",
            created_at=self._clock(),
            provenance="package7-live-correction",
        )
        generator = _CountingGenerator(self._counts)
        raw = dict(generator.generate(question))
        raw["objective"] = normalized
        correction = ProductSemanticCorrection(
            correction_id=f"product-correction:{self._opaque_id()}",
            tenant_id=TENANT_ID,
            security_domain=SECURITY_DOMAIN,
            principal=principal.principal_id,
            predecessor_revision_id=predecessor.canonical_workflow_revision_id,
            predecessor_digest=predecessor.approved_candidate_digest,
            affected_element_id=predecessor.intent_revision.intent_revision_id,
            field="objective",
            before=predecessor.intent_revision.objective,
            after=normalized,
            reason_code=reason_code.upper(),
        )
        pending = self._planning.corrected_successor(
            predecessor, correction, question, raw, generator
        )
        candidate = pending.workflow_candidate
        if candidate is None:
            raise SupplierQualityDemoFailure("CORRECTION_PLANNING_INVALID")
        identity = current.identity.model_copy(
            update={
                "canonicalWorkflowRevisionId": (
                    f"canonical-workflow-revision:{candidate.candidate_digest}"
                ),
                "canonicalDigest": candidate.candidate_digest,
                "approvalId": f"pending-approval:{candidate.candidate_digest}",
                "platformExecutionIdentity": None,
                "sharedSnapshotId": f"pending-snapshot:{candidate.candidate_digest}",
                "evidenceIds": [],
                "citationIds": [],
            }
        )
        successor = JourneyRevision(
            revision=current.revision + 1,
            predecessorRevisionId=predecessor.canonical_workflow_revision_id,
            objective=normalized,
            lifecycle="PENDING_APPROVAL",
            approvalState="PENDING",
            identity=identity,
            planTaskIds=list(candidate.ordered_task_ids),
            matchState="PARTIAL",
            placementState="UNAVAILABLE",
            knowledgeState="UNAVAILABLE",
            executionState="NOT_REQUESTED",
            answer=None,
            citations=[],
            outcome=None,
            limitationCodes=["FRESH_EXACT_DIGEST_APPROVAL_REQUIRED"],
        )
        record.pending = pending
        record.question = question
        record.display = self._live.register_authoritative_transition(
            journey_id,
            principal,
            predecessor=current,
            successor=successor,
            event_type="CORRECTION_ACCEPTED",
            stage="CORRECTION",
            status="ACCEPTED",
            terminal=False,
            reason_code=reason_code.upper(),
            localization_key="liveJourney.event.correctionAccepted",
        )
        return record.display

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
        record = self._authorized_record(journey_id, principal)
        if record.pending is None:
            raise JourneyConflict("APPROVAL_NOT_PENDING")
        candidate = record.pending.workflow_candidate
        if candidate is None or candidate_digest != candidate.candidate_digest:
            raise JourneyConflict("APPROVAL_DIGEST_MISMATCH")
        approval = self._planning.request_approval(record.pending)
        planning_decision = (
            PlanningDecision.APPROVE
            if decision == "APPROVE"
            else PlanningDecision.REJECT
            if decision == "REJECT"
            else None
        )
        if planning_decision is None:
            raise SupplierQualityDemoFailure("INVALID_APPROVAL_DECISION")
        canonical = self._planning.decide(
            record.pending,
            approval,
            tenant_id=TENANT_ID,
            security_domain=SECURITY_DOMAIN,
            actor=principal.principal_id,
            decision=planning_decision,
            decided_at=self._clock(),
            replay_identity=replay_identity,
            reason_code=reason_code,
            predecessor=record.canonical,
        )
        previous = record.display.predecessor or record.display.successor
        pending_view = record.display.successor
        if canonical is None:
            rejected = pending_view.model_copy(update={"approvalState": "REJECTED"})
            record.display = record.display.model_copy(update={"successor": rejected})
            return record.display
        record.canonical = canonical
        record.pending = None
        approved = pending_view.model_copy(
            update={
                "lifecycle": "EXECUTABLE",
                "approvalState": "APPROVED",
                "executionState": "NOT_REQUESTED",
                "identity": pending_view.identity.model_copy(
                    update={
                        "canonicalWorkflowRevisionId": (
                            canonical.canonical_workflow_revision_id
                        ),
                        "canonicalDigest": canonical.approved_candidate_digest,
                        "approvalId": canonical.approval_id,
                    }
                ),
                "limitationCodes": ["EXECUTION_REQUIRES_EXPLICIT_START"],
            }
        )
        superseded = (
            None
            if pending_view.predecessorRevisionId is None
            else previous.model_copy(update={"lifecycle": "SUPERSEDED"})
        )
        if self._live.owns(journey_id):
            record.display = self._live.register_authoritative_transition(
                journey_id,
                principal,
                predecessor=superseded,
                successor=approved,
                event_type="APPROVAL_RECORDED",
                stage="APPROVAL",
                status="APPROVED",
                terminal=False,
                reason_code=reason_code.upper(),
                localization_key="liveJourney.event.approvalRecorded",
            )
        else:
            record.display = record.display.model_copy(
                update={
                    "product": JourneyProjection(
                        projection="PRODUCT",
                        identity=approved.identity,
                        revision=approved,
                    ),
                    "technical": JourneyProjection(
                        projection="TECHNICAL",
                        identity=approved.identity,
                        revision=approved,
                    ),
                    "predecessor": superseded,
                    "successor": approved,
                }
            )
        return record.display

    def rerun(
        self,
        journey_id: str,
        principal: TrustedJourneyPrincipal,
        *,
        revision_id: str,
        digest: str,
    ) -> LiveJourneyResponse:
        record = self._authorized_record(journey_id, principal)
        current = record.display.successor
        if (
            current.lifecycle != "EXECUTABLE"
            or current.approvalState != "APPROVED"
            or record.canonical is None
            or revision_id != record.canonical.canonical_workflow_revision_id
            or digest != record.canonical.approved_candidate_digest
        ):
            raise JourneyConflict("RERUN_REVISION_DIGEST_MISMATCH")
        package = self._load_package(principal)
        predecessor = record.display.predecessor

        def publish_execution_start() -> None:
            authorized = current.model_copy(
                update={"executionState": "AUTHORIZED_HANDOFF"}
            )
            self._live.register_authoritative_transition(
                journey_id,
                principal,
                predecessor=predecessor,
                successor=authorized,
                event_type="EXECUTION_AUTHORIZED",
                stage="EXECUTION",
                status="AUTHORIZED",
                terminal=False,
                reason_code="EXACT_DIGEST_EXECUTION_AUTHORIZED",
                localization_key="liveJourney.event.executionAuthorized",
            )
            running = current.model_copy(update={"executionState": "RUNNING"})
            self._live.register_authoritative_transition(
                journey_id,
                principal,
                predecessor=predecessor,
                successor=running,
                event_type="EXECUTION_STARTED",
                stage="EXECUTION",
                status="STARTED",
                terminal=False,
                reason_code="EXISTING_EXECUTION_AUTHORITY_STARTED",
                localization_key="liveJourney.event.executionStarted",
            )

        first_execution = not self._live.owns(journey_id)
        pipeline = self._execute_revision(
            package,
            record.canonical,
            principal,
            before_execution=None if first_execution else publish_execution_start,
        )
        succeeded = pipeline.outcome.classification == "SUCCEEDED"
        completed = current.model_copy(
            update={
                "matchState": "MATCHED",
                "placementState": "PLACED",
                "knowledgeState": pipeline.knowledge_state,
                "executionState": "SUCCEEDED" if succeeded else "FAILED",
                "identity": current.identity.model_copy(
                    update={
                        "platformExecutionIdentity": (
                            pipeline.platform_execution_identity
                        ),
                        "sharedSnapshotId": pipeline.shared_snapshot_id,
                        "graphSnapshotId": pipeline.graph_snapshot_id,
                        "placementDecisionId": pipeline.placement_decision_id,
                        "evidenceIds": list(pipeline.evidence_ids),
                        "citationIds": [item.citationId for item in pipeline.citations],
                    }
                ),
                "answer": pipeline.answer,
                "citations": list(pipeline.citations),
                "outcome": pipeline.outcome,
                "limitationCodes": [],
                "projectedTasks": [
                    task.model_copy(update={"state": "SUCCEEDED"})
                    for task in current.projectedTasks
                ],
            }
        )
        record.outcomes.append(pipeline.outcome)
        record.execution_evidence_ids.append(pipeline.evidence_ids)
        if first_execution:
            seed = LiveJourneySeed(
                journey_id=journey_id,
                tenant_id=TENANT_ID,
                security_domain=SECURITY_DOMAIN,
                canonical_workflow_revision_id=record.canonical.canonical_workflow_revision_id,
                canonical_digest=record.canonical.approved_candidate_digest,
                approval_id=record.canonical.approval_id,
                objective=record.canonical.intent_revision.objective,
                task_ids=record.canonical.ordered_task_ids,
                shared_snapshot_id=pipeline.shared_snapshot_id,
                graph_snapshot_id=pipeline.graph_snapshot_id,
                platform_execution_identity=pipeline.platform_execution_identity,
                placement_decision_id=pipeline.placement_decision_id,
                evidence_ids=pipeline.evidence_ids,
                citations=pipeline.citations,
                outcome=pipeline.outcome,
                answer=pipeline.answer,
                knowledge_state=pipeline.knowledge_state,
            )
            self._live.register_live(seed)
            publish_execution_start()
        record.display = self._live.register_authoritative_transition(
            journey_id,
            principal,
            predecessor=predecessor,
            successor=completed,
            event_type="EXECUTION_SUCCEEDED" if succeeded else "EXECUTION_FAILED",
            stage="EXECUTION",
            status="SUCCEEDED" if succeeded else "FAILED",
            terminal=True,
            reason_code="EXISTING_EXECUTION_AUTHORITY_RESULT",
            localization_key=(
                "liveJourney.event.executionSucceeded"
                if succeeded
                else "liveJourney.event.executionFailed"
            ),
        )
        return record.display

    def _draft_projection(
        self,
        journey_id: str,
        question: Any,
        result: PlanningResult,
        package: MaterializedPackage,
        *,
        revision: int,
        predecessor: JourneyRevision | None = None,
    ) -> LiveJourneyResponse:
        candidate = result.workflow_candidate
        if candidate is None:
            raise SupplierQualityDemoFailure("QUESTION_PLANNING_INVALID")
        descriptors = {
            item["descriptorId"]: item for item in package.descriptors["descriptors"]
        }
        declarations = package.roles["roles"]
        analyst = next(
            item for item in declarations if "analyst" in item["definitionId"]
        )
        reviewer = next(
            item for item in declarations if "reviewer" in item["definitionId"]
        )
        tasks = []
        for index, task in enumerate(candidate.tasks):
            declaration = (
                reviewer if task.future_task_id == "review-quality-plan" else analyst
            )
            descriptor = descriptors[declaration["descriptorId"]]
            tasks.append(
                JourneyTaskProjection(
                    taskId=task.future_task_id,
                    title={
                        "collect-quality-inputs": "汇总质量证据",
                        "analyze-quality-exception": "分析质量异常与潜在根因",
                        "review-quality-plan": "审查整改计划并确认执行边界",
                    }[task.future_task_id],
                    purpose=(
                        f"针对业务问题 {question.question}: {task.business_purpose}"
                        if index == 0
                        else task.business_purpose
                    ),
                    inputs=list(task.inputs),
                    actions=[task.task_type],
                    dependencies=list(task.dependencies),
                    expectedOutputs=list(task.outputs),
                    completionConditions=list(task.acceptance_conditions),
                    approvalRequired=task.approval_classification == "HUMAN",
                    requiredRole="质量审核协调员"
                    if declaration is reviewer
                    else "供应商质量分析员",
                    matchedRole=descriptor["title"],
                    matchState="MATCHED",
                    definitionId=declaration["definitionId"],
                    definitionVersion=declaration["versionId"],
                    definitionDigest=None,
                    descriptorId=declaration["descriptorId"],
                    publicationState=declaration["lifecycle"],
                    matchAuthorization=declaration["matchability"],
                    publicationDecisionId=declaration["publicationDecisionId"],
                    skills=list(descriptor["skills"]),
                    mcpCapabilities=list(descriptor["capabilities"]),
                    knowledgeRefs=list(descriptor["knowledge"]),
                    runtimeRefs=list(descriptor["runtimes"]),
                    readiness="READY",
                    reasonCodes=["PUBLISHED_ROLE_DECLARATION_MATCHED"],
                    state="READY" if index == 0 else "WAITING_DEPENDENCY",
                )
            )
        digest = candidate.candidate_digest
        identity = JourneyIdentity(
            tenantId=TENANT_ID,
            securityDomain=SECURITY_DOMAIN,
            canonicalWorkflowRevisionId=f"workflow-candidate:{digest}",
            canonicalDigest=digest,
            sharedSnapshotId=f"draft-snapshot:{digest}",
            graphSnapshotId=f"draft-graph:{digest}",
            platformExecutionIdentity=None,
            approvalId=f"pending-approval:{digest}",
            placementDecisionId="NOT_BOUND",
            evidenceIds=[],
            citationIds=[],
        )
        understanding = JourneyUnderstanding(
            question=question.question,
            scope=[
                f"当前业务问题: {question.question}",
                "脱敏供应商质量案例",
                "交付质量、缺陷、根因、整改与改善验证",
            ],
            facts=["当前演示使用三个经过校验的脱敏质量案例"],
            assumptions=list(result.intent_candidate.assumptions),
            uncertainties=list(result.intent_candidate.uncertainties),
            expectedOutcome=list(candidate.intent_revision.success_criteria),
            provenance="DETERMINISTIC_DEMO_INTERPRETATION",
        )
        successor = JourneyRevision(
            revision=revision,
            predecessorRevisionId=(
                None
                if predecessor is None
                else predecessor.identity.canonicalWorkflowRevisionId
            ),
            objective=candidate.intent_revision.objective,
            lifecycle="PENDING_APPROVAL",
            approvalState="PENDING",
            identity=identity,
            planTaskIds=list(candidate.ordered_task_ids),
            matchState="MATCHED",
            placementState="UNAVAILABLE",
            knowledgeState="UNAVAILABLE",
            executionState="NOT_REQUESTED",
            answer=None,
            citations=[],
            outcome=None,
            limitationCodes=[
                "PROJECTED_TASKS_NOT_PERSISTED",
                "EXACT_APPROVAL_REQUIRED",
            ],
            understanding=understanding,
            decomposition=[f"围绕业务问题确认分析范围: {question.question}"]
            + [task.title for task in tasks]
            + ["执行获批计划并验证改善效果"],
            projectedTasks=tasks,
        )
        superseded = (
            None
            if predecessor is None
            else predecessor.model_copy(update={"lifecycle": "SUPERSEDED"})
        )
        product = JourneyProjection(
            projection="PRODUCT", identity=identity, revision=successor
        )
        technical = JourneyProjection(
            projection="TECHNICAL", identity=identity, revision=successor
        )
        return LiveJourneyResponse(
            journeyId=journey_id,
            state="LIVE",
            provenance="LIVE_EXECUTION",
            reasonCode="REVIEWABLE_DRAFT_READY",
            product=product,
            technical=technical,
            predecessor=superseded,
            successor=successor,
        )

    def reset(
        self,
        journey_id: str,
        request: SupplierQualityDemoResetRequest,
        principal: TrustedJourneyPrincipal,
    ) -> SupplierQualityDemoResetResponse:
        record = self._authorized_record(journey_id, principal)
        expected = self._reset_token(journey_id)
        if (
            request.scenarioId != SCENARIO_ID
            or request.namespace != NAMESPACE
            or request.tenantId != TENANT_ID
            or request.securityDomain != SECURITY_DOMAIN
            or not hmac.compare_digest(request.confirmationToken, expected)
            or not hmac.compare_digest(record.reset_token, expected)
        ):
            raise SupplierQualityDemoDenied("DEMO_RESET_CONFIRMATION_MISMATCH")
        if self._live.owns(journey_id):
            self._live.unregister_live(journey_id, principal)
        record.active = False
        self._start_replays.pop(record.replay_identity, None)
        return SupplierQualityDemoResetResponse(
            scenarioId=SCENARIO_ID,
            namespace=NAMESPACE,
            journeyId=journey_id,
        )

    def _start_response(
        self, record: _JourneyRecord, live: LiveJourneyResponse, *, replayed: bool
    ) -> SupplierQualityDemoStartResponse:
        return SupplierQualityDemoStartResponse(
            scenarioId=SCENARIO_ID,
            namespace=NAMESPACE,
            journeyId=record.journey_id,
            resetConfirmationToken=record.reset_token,
            replayed=replayed,
            callCounts=record.counts_at_start,
            live=live,
        )

    def _authorized_record(
        self, journey_id: str, principal: TrustedJourneyPrincipal
    ) -> _JourneyRecord:
        self._require_principal(principal)
        record = self._records.get(journey_id)
        if record is None or not record.active:
            raise JourneyNotFound()
        if self._live.owns(journey_id):
            self._live.get(journey_id, principal)
        return record

    @staticmethod
    def _require_principal(principal: TrustedJourneyPrincipal) -> None:
        if not principal.permits(TENANT_ID, SECURITY_DOMAIN):
            raise SupplierQualityDemoDenied("SUPPLIER_QUALITY_DEMO_ACCESS_DENIED")

    def _reset_token(self, journey_id: str) -> str:
        value = "\0".join(
            (SCENARIO_ID, NAMESPACE, journey_id, TENANT_ID, SECURITY_DOMAIN)
        )
        digest = hmac.new(
            self._reset_secret.encode(), value.encode(), hashlib.sha256
        ).hexdigest()
        return f"demo-reset:{digest}"

    def _load_package(self, principal: TrustedJourneyPrincipal) -> MaterializedPackage:
        root = self._configured_root
        if root is None:
            raise SupplierQualityDemoUnavailable("MATERIALIZED_ROOT_NOT_CONFIGURED")
        if not root.is_absolute() or root.name != NAMESPACE:
            raise SupplierQualityDemoFailure("MATERIALIZED_ROOT_INVALID")
        resolved = root.resolve()
        if resolved.name != NAMESPACE or not resolved.is_dir():
            raise SupplierQualityDemoFailure("MATERIALIZED_ROOT_INVALID")
        marker = _read_text(resolved, ".scenario-pack-scope")
        if marker.splitlines() != [
            f"scenario={SCENARIO_ID}",
            f"namespace={NAMESPACE}",
        ]:
            raise SupplierQualityDemoFailure("SCENARIO_SCOPE_MARKER_INVALID")
        checksum_text = _read_text(resolved, "checksums.sha256")
        manifest = _read_json(resolved, "scenario-pack-v1.json")
        self._validate_manifest(manifest)

        # Scope authorization precedes every business-data/Knowledge read.
        self._require_principal(principal)
        checksums = _parse_checksums(checksum_text)
        if set(checksums) != _DECLARED_INPUTS:
            raise SupplierQualityDemoFailure("CHECKSUM_MANIFEST_INVALID")
        for relative in sorted(_MATERIALIZED_INPUTS):
            content = _read_bytes(resolved, relative)
            if hashlib.sha256(content).hexdigest() != checksums[relative]:
                raise SupplierQualityDemoFailure("PACKAGE_CHECKSUM_MISMATCH")
        # Operational script entries are deliberately absent from the materialized
        # runtime tree. Their exact baseline digests remain bound by the validated
        # checksum manifest and are never executed by this bridge.
        if checksums["bootstrap.sh"] != (
            "634bdc2f3ef3a407ba58bd077ec65fcfdb7a699f75aed05b32c570d2ed56de10"
        ) or checksums["reset.sh"] != (
            "760c41b55c29aad85957332ff040cdc03037580a8d9331d8fe88e9e2dc090813"
        ):
            raise SupplierQualityDemoFailure("CHECKSUM_MANIFEST_INVALID")

        namespace = yaml.safe_load(_read_text(resolved, "namespace.yaml"))
        if not isinstance(namespace, dict) or namespace.get("kind") != "Namespace":
            raise SupplierQualityDemoFailure("NAMESPACE_MANIFEST_INVALID")
        metadata = namespace.get("metadata")
        if not isinstance(metadata, dict) or metadata.get("name") != NAMESPACE:
            raise SupplierQualityDemoFailure("NAMESPACE_MANIFEST_INVALID")
        package = MaterializedPackage(
            root=resolved,
            manifest=manifest,
            cases=_read_json(resolved, "data/supplier-quality-cases-v1.json"),
            descriptors=_read_json(resolved, "catalog/descriptors-v1.json"),
            roles=_read_json(resolved, "catalog/published-roles-v1.json"),
            knowledge_manifest=_read_json(resolved, "knowledge/knowledge-pack-v1.json"),
            knowledge_text=_read_text(resolved, "knowledge/8d-procedure-v1.md"),
        )
        self._validate_scoped_package(package)
        return package

    @staticmethod
    def _validate_manifest(manifest: Mapping[str, Any]) -> None:
        expected = {
            "schemaVersion": "supplier-quality-scenario-pack.v1",
            "scenarioId": SCENARIO_ID,
            "scenarioVersion": "v1",
            "namespace": NAMESPACE,
            "tenantId": TENANT_ID,
            "securityDomain": SECURITY_DOMAIN,
            "provenance": "DEMO_CONFIGURATION",
        }
        if any(manifest.get(key) != value for key, value in expected.items()):
            raise SupplierQualityDemoFailure("SCENARIO_MANIFEST_INVALID")
        semantic = dict(manifest)
        declared = semantic.pop("canonicalDigest", None)
        actual = hashlib.sha256(
            json.dumps(
                semantic,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        if declared != actual:
            raise SupplierQualityDemoFailure("SCENARIO_DIGEST_MISMATCH")
        live = manifest.get("liveExecution")
        side_effects = manifest.get("sideEffects")
        if (
            not isinstance(live, Mapping)
            or live.get("owner") != "EXISTING_PLATFORM_RUNTIME_ONLY"
            or live.get("recordsIncluded") != 0
            or live.get("fixtureFallback") != "PROHIBITED"
            or not isinstance(side_effects, Mapping)
            or any(side_effects.values())
        ):
            raise SupplierQualityDemoFailure("SCENARIO_AUTHORITY_INVALID")

    @staticmethod
    def _validate_scoped_package(package: MaterializedPackage) -> None:
        for value in (
            package.cases,
            package.descriptors,
            package.roles,
            package.knowledge_manifest,
        ):
            if (
                value.get("scenarioId", SCENARIO_ID) != SCENARIO_ID
                or value.get("tenantId") != TENANT_ID
                or value.get("securityDomain") != SECURITY_DOMAIN
            ):
                raise SupplierQualityDemoFailure("PACKAGE_SCOPE_MISMATCH")
        sanitation = package.cases.get("sanitation")
        cases = package.cases.get("cases")
        descriptors = package.descriptors.get("descriptors")
        roles = package.roles.get("roles")
        if (
            sanitation
            != {
                "containsPersonalData": False,
                "containsProductionData": False,
                "containsCredentials": False,
                "supplierNamesAreFictional": True,
            }
            or not isinstance(cases, list)
            or len(cases) != 3
            or not isinstance(descriptors, list)
            or len(descriptors) != 2
            or not isinstance(roles, list)
            or len(roles) != 2
            or package.roles.get("publicationAuthorityIncluded") is not False
            or package.roles.get("permissionGrantIncluded") is not False
        ):
            raise SupplierQualityDemoFailure("PACKAGE_SCHEMA_INVALID")
        knowledge = package.knowledge_manifest
        declared = knowledge.get("canonicalDigest")
        documents = knowledge.get("documents")
        if (
            declared
            != "8d05909929e2bf0f60113b40eef05d66956aab6213ae0709d43561ab16f528dc"
            or not isinstance(documents, list)
            or len(documents) != 1
        ):
            raise SupplierQualityDemoFailure("KNOWLEDGE_MANIFEST_INVALID")
        if hashlib.sha256(package.knowledge_text.encode()).hexdigest() != documents[
            0
        ].get("sha256"):
            raise SupplierQualityDemoFailure("KNOWLEDGE_DOCUMENT_DIGEST_MISMATCH")

    def _ensure_definitions(self, package: MaterializedPackage) -> None:
        if self._definitions_ready:
            return
        descriptors = {
            item["descriptorId"]: item for item in package.descriptors["descriptors"]
        }
        for declared in package.roles["roles"]:
            descriptor = descriptors[declared["descriptorId"]]
            role = RoleDescriptor.create(
                title=descriptor["title"],
                duties=descriptor["duties"],
                data=descriptor["data"],
                knowledge=descriptor["knowledge"],
                skills=descriptor["skills"],
                capabilities=descriptor["capabilities"],
                runtimes=descriptor["runtimes"],
            )
            version = create_definition_version(
                definition_id=declared["definitionId"],
                version_id=declared["versionId"],
                role=role,
                source_authoring_revision_id=(
                    f"package7:{package.manifest['canonicalDigest']}"
                ),
                source_authority_kind="supplier-quality-package",
                source_authority_revision=AUTHORITY_REVISION,
                source_authoring_state="APPROVED",
                tenant_id=TENANT_ID,
                security_domain=SECURITY_DOMAIN,
                provenance="package7-validated",
                created_at=AUTHORITY_TIME,
            )
            self._definition.register(version)
            self._definition.append_publication(
                create_publication_decision(
                    version=version,
                    decision_id=declared["publicationDecisionId"],
                    replay_identity=f"publication-replay:{version.definition_id}",
                    action=PublicationAction.PUBLISH,
                    actor="system:package7-bridge",
                    reason_code="VALIDATED_PACKAGE_DECLARATION",
                    policy_ref=declared["publicationPolicyRef"],
                    decided_at=AUTHORITY_TIME,
                    effective_at=AUTHORITY_TIME,
                    provenance="definition-authority",
                )
            )
            self._definition.append_match_authorization(
                create_match_authorization_decision(
                    version=version,
                    decision_id=f"match-authorization:{version.definition_id}:v1",
                    replay_identity=f"match-replay:{version.definition_id}",
                    purpose=MATCH_PURPOSE,
                    action=MatchAuthorizationAction.GRANT,
                    authority="definition-authority",
                    reason_code="EXACT_PURPOSE_AUTHORIZED",
                    policy_ref="published-role-matching-v1",
                    decided_at=AUTHORITY_TIME,
                    effective_at=AUTHORITY_TIME,
                    provenance="definition-authority",
                )
            )
        self._definitions_ready = True

    def _execute_revision(
        self,
        package: MaterializedPackage,
        revision: CanonicalWorkflowRevision,
        principal: TrustedJourneyPrincipal,
        *,
        before_execution: Callable[[], None] | None = None,
    ) -> _PipelineResult:
        self._ensure_definitions(package)
        requirements = []
        for task in revision.tasks:
            duty = (
                "review proposed containment"
                if task.future_task_id == "review-quality-plan"
                else "analyze supplier-quality exceptions"
            )
            requirements.append(
                TaskRoleRequirements(
                    task_requirement_id=task.task_requirement_id,
                    requirements=(
                        RoleRequirement.create(
                            requirement_id=f"role-requirement:{task.future_task_id}",
                            duties=(duty,),
                            data=("supplier-quality-cases-v1",),
                            knowledge=("supplier-quality-pack:v1",),
                            capabilities=("quality.read",),
                            runtimes=("native",),
                        ),
                    ),
                )
            )
        self._counts.matching_requests += 1
        matching = PublishedRoleMatcher(self._definition).match(
            MatchingRequest(
                canonical_workflow_revision_id=(
                    revision.canonical_workflow_revision_id
                ),
                approved_workflow_digest=revision.approved_candidate_digest,
                tenant_id=TENANT_ID,
                security_domain=SECURITY_DOMAIN,
                purpose=MATCH_PURPOSE,
                evaluation_time=self._clock(),
                tasks=tuple(requirements),
            )
        )
        if (
            matching.provider_calls
            or matching.runtime_calls
            or matching.credential_grants
            or matching.permission_grants
            or any(
                item.outcome is not MatchOutcome.MATCHED for item in matching.decisions
            )
        ):
            raise SupplierQualityDemoUnavailable("ROLE_MATCHING_UNAVAILABLE")
        decisions = {item.requirement_id: item for item in matching.decisions}
        bindings = tuple(
            MatchedDefinitionBinding(
                task.task_requirement_id,
                decisions[f"role-requirement:{task.future_task_id}"],
            )
            for task in revision.tasks
        )

        knowledge_pack, document = self._knowledge_pack(package)
        knowledge_decision = KnowledgeAuthorizationDecision.create(
            decision_id=f"knowledge-authorization:{self._opaque_id()}",
            replay_identity=f"knowledge-authorization-replay:{self._opaque_id()}",
            action=self._knowledge_action,
            tenant_id=TENANT_ID,
            security_domain=SECURITY_DOMAIN,
            purpose=KNOWLEDGE_PURPOSE,
            knowledge_pack_id=knowledge_pack.knowledge_pack_id,
            knowledge_pack_version=knowledge_pack.knowledge_pack_version,
            knowledge_pack_digest=knowledge_pack.canonical_digest,
            document_id=document.document_id,
            document_version=document.document_version,
            document_digest=document.content_digest,
            policy_version=RETRIEVAL_POLICY_VERSION,
            effective_at=AUTHORITY_TIME,
            expires_at=datetime(2027, 8, 29, tzinfo=UTC),
            authority="knowledge-authority",
        )
        knowledge_request = KnowledgeRetrievalRequest.create(
            request_id=f"knowledge-request:{self._opaque_id()}",
            canonical_workflow_revision_id=revision.canonical_workflow_revision_id,
            approved_workflow_digest=revision.approved_candidate_digest,
            task_requirement_id=revision.tasks[1].task_requirement_id,
            knowledge_binding_id="supplier-quality-pack:v1",
            tenant_id=TENANT_ID,
            security_domain=SECURITY_DOMAIN,
            purpose=KNOWLEDGE_PURPOSE,
            authorization_decision_id=knowledge_decision.decision_id,
            knowledge_pack_id=knowledge_pack.knowledge_pack_id,
            knowledge_pack_version=knowledge_pack.knowledge_pack_version,
            knowledge_pack_digest=knowledge_pack.canonical_digest,
            document_id=document.document_id,
            document_version=document.document_version,
            document_digest=document.content_digest,
            retrieval_policy_version=RETRIEVAL_POLICY_VERSION,
            query="containment root cause corrective action escalation",
            filters=(KnowledgeFilter.create(key="document_type", value="procedure"),),
            max_results=4,
            required=True,
        )
        source = InMemoryKnowledgeSource(knowledge_pack)
        knowledge_result = retrieve(
            request=knowledge_request,
            authorization=knowledge_decision,
            evaluation_time=self._clock(),
            source=source,
        )
        self._counts.knowledge_source_reads += source.read_count
        evidence = self._knowledge_evidence.append(
            KnowledgeRetrievalEvidence.from_result(
                request=knowledge_request,
                result=knowledge_result,
                provenance="live-execution",
            )
        )
        citations = assemble_citations(evidence)
        if not knowledge_result.successful or not citations:
            raise SupplierQualityDemoUnavailable(
                knowledge_result.reason_codes[0]
                if knowledge_result.reason_codes
                else "KNOWLEDGE_UNAVAILABLE"
            )
        journey_citations = tuple(
            JourneyCitation(
                citationId=item.citation_id,
                retrievalEvidenceId=item.evidence_id,
                authorizationDecisionId=item.authorization_decision_id,
                knowledgePackId=item.knowledge_pack_id,
                knowledgePackVersion=item.knowledge_pack_version,
                knowledgePackDigest=item.knowledge_pack_digest,
                documentId=document.document_id,
                documentVersion=item.document_version,
                documentDigest=item.document_digest,
                sectionId=item.section_id,
                chunkId=item.chunk_id,
                status=knowledge_result.status.value,
            )
            for item in citations
        )
        self._execution_authority.attach_knowledge_references(
            namespace=NAMESPACE,
            security_domain=SECURITY_DOMAIN,
            evidence_id=evidence.evidence_id,
            citation_ids=tuple(item.citationId for item in journey_citations),
        )

        runtime_requirement = derive_runtime_requirement(
            revision,
            bindings,
            required_capabilities=("quality.read",),
            required_providers=(PROVIDER_PACKAGE.distribution,),
            required_permissions=("supplier-quality.read",),
        )
        self._counts.placement_evaluations += 1
        placement = NativePlacementEvaluator().place(
            runtime_requirement,
            PlacementAuthorization(
                authorization_reference=revision.approval_id,
                tenant_id=TENANT_ID,
                security_domain=SECURITY_DOMAIN,
                permission_eligible=True,
                capability_eligible=True,
                provider_eligible=True,
            ),
            (
                DeclaredNativeTarget(
                    declaration_id="native-target:package7-live",
                    tenant_id=TENANT_ID,
                    security_domain=SECURITY_DOMAIN,
                    target=RUNTIME_TARGET,
                    provider_package=PROVIDER_PACKAGE,
                    core_version="0.1.0",
                    state=self._target_state,
                ),
            ),
        )
        if (
            placement.outcome is not PlacementOutcome.PLACED
            or placement.provider_call_count
            or placement.runtime_call_count
            or placement.gateway_call_count
            or placement.execution_coordinator_call_count
        ):
            raise SupplierQualityDemoUnavailable(placement.reason_codes[0])
        if before_execution is not None:
            before_execution()

        cases = tuple(package.cases["cases"])

        def invoke(
            platform_execution_identity: str,
            input_text: str,
            configuration: tuple[tuple[str, str], ...],
        ) -> NativeInvocation:
            self._counts.native_provider_invocations += 1
            if "collect-quality-inputs" in input_text:
                output = f"Collected {len(cases)} checksum-validated supplier cases."
            elif "analyze-quality-exception" in input_text:
                high = sum(item["severity"] == "HIGH" for item in cases)
                output = (
                    f"Analyzed {len(cases)} cases; {high} high-severity case requires "
                    "bounded containment and Human review."
                )
            else:
                output = (
                    "Reviewed the live analysis; retain governed citations and "
                    "escalate the overdue high-severity containment item."
                )
            native_id = hashlib.sha256(
                f"{platform_execution_identity}\0{input_text}\0{configuration}".encode()
            ).hexdigest()[:24]
            return NativeInvocation(output, f"native:{native_id}")

        provider = NativeRuntimeProvider(invoke)
        coordinator = TaskExecutionCoordinator(
            native_provider=provider,
            capability_gateway=None,
            evidence_repository=self._execution_evidence,
            security_domain=SECURITY_DOMAIN,
            clock=lambda: self._clock().isoformat().replace("+00:00", "Z"),
        )
        workflow_uid = f"workflow:{revision.approved_candidate_digest[:24]}"
        outcomes = []
        task_resources = []
        final_task_uid = ""
        definition_by_requirement = {
            binding.task_requirement_id: binding.match_decision for binding in bindings
        }
        for task in revision.tasks:
            selected = definition_by_requirement[task.task_requirement_id]
            definition_id = selected.selected_definition_id
            if definition_id is None:
                raise SupplierQualityDemoUnavailable("ROLE_MATCHING_UNAVAILABLE")
            task_uid = f"task:{task.future_task_id}:{revision.revision}"
            final_task_uid = task_uid
            envelope = self._execution_authority.create_envelope(
                namespace=NAMESPACE,
                definition_id=definition_id,
                task_id=task.future_task_id,
                binding_id=placement.decision_id,
                provider_ref=PROVIDER_PACKAGE.distribution,
                runtime_mode=RUNTIME_TARGET.name,
                package_ref=PROVIDER_PACKAGE.module,
                selection_reason=selected.decision_id,
                configuration={
                    "AGENT_NAME": definition_id,
                    "AGENT_NAMESPACE": NAMESPACE,
                    "AGENT_ROLE": definition_id,
                    "MODEL_PROVIDER": "mock",
                    "MODEL_NAME": "package7-live-computation",
                },
            )
            context = TaskExecutionContext(
                envelope=envelope,
                runtime_configuration={
                    "AGENT_NAME": definition_id,
                    "AGENT_NAMESPACE": NAMESPACE,
                    "AGENT_ROLE": definition_id,
                    "MODEL_PROVIDER": "mock",
                    "MODEL_NAME": "package7-live-computation",
                },
                capability_plan=None,
                evidence_subject=TaskEvidenceSubject(NAMESPACE, workflow_uid, task_uid),
            )
            self._counts.coordinator_executions += 1
            outcome = coordinator.execute(
                context=context,
                input_text=(
                    f"task={task.future_task_id};scenario={SCENARIO_ID};"
                    f"revision={revision.canonical_workflow_revision_id}"
                ),
            )
            if (
                outcome.classification is not ExecutionClassification.SUCCEEDED
                or outcome.evidence_availability is not EvidenceAvailability.AVAILABLE
                or outcome.result is None
            ):
                raise SupplierQualityDemoUnavailable(outcome.diagnostic)
            outcomes.append(outcome)
            task_resources.append(
                {
                    "metadata": {
                        "name": task.future_task_id,
                        "uid": task_uid,
                        "resourceVersion": str(revision.revision),
                    }
                }
            )
        if len(outcomes) != 3:
            raise SupplierQualityDemoUnavailable("EXECUTION_CARDINALITY_INVALID")

        execution_records = self._execution_evidence.records[-3:]
        evidence_ids = (
            evidence.evidence_id,
            *(item.evidence_record_id for item in execution_records),
        )
        final = outcomes[-1]
        outcome_digest = _sha(
            [
                revision.approved_candidate_digest,
                [item.platform_execution_identity for item in outcomes],
            ]
        )
        outcome_id = f"workflow-outcome:{outcome_digest}"
        journey_outcome = JourneyOutcome(
            outcomeId=outcome_id,
            classification="SUCCEEDED",
            summary=final.result or "Supplier quality live execution completed.",
            comparableMetric="supplierQualityCaseCount",
            comparableValue=float(len(cases)),
        )
        graph = self._graph(
            package,
            revision,
            bindings,
            final.platform_execution_identity,
            evidence_ids,
            outcome_id,
        )
        scope = self._execution_authority.scope(NAMESPACE, SECURITY_DOMAIN)
        high_water = self._execution_evidence.high_water_mark(scope)
        final_evidence = self._execution_evidence.read_execution(
            scope,
            final.platform_execution_identity,
            through_high_water_mark=high_water,
        )
        snapshot = assemble_execution_snapshot(
            scope=scope,
            workflow={
                "metadata": {
                    "name": "supplier-quality-workflow",
                    "uid": workflow_uid,
                    "resourceVersion": str(revision.revision),
                }
            },
            tasks=task_resources,
            evidence=final_evidence,
            evidence_high_water_mark=high_water,
            graph=graph,
            selected_task_identity=final_task_uid,
            stale=knowledge_result.status is KnowledgeStatus.STALE,
        )
        answer = " ".join(item.result or "" for item in outcomes)
        return _PipelineResult(
            revision=revision,
            placement_decision_id=placement.decision_id,
            platform_execution_identity=final.platform_execution_identity,
            shared_snapshot_id=snapshot.shared_snapshot_id,
            graph_snapshot_id=graph.graph_snapshot_id,
            evidence_ids=tuple(evidence_ids),
            citations=journey_citations,
            outcome=journey_outcome,
            answer=answer,
            knowledge_state=knowledge_result.status.value,
        )

    def _knowledge_pack(
        self, package: MaterializedPackage
    ) -> tuple[KnowledgePack, KnowledgeDocument]:
        metadata = package.knowledge_manifest
        document_metadata = metadata["documents"][0]
        chunk = KnowledgeChunk.create(
            chunk_id="chunk-8d-procedure-v1",
            ordinal=1,
            content=" ".join(package.knowledge_text.split()),
        )
        section = KnowledgeSection.create(
            section_id="section-8d-procedure",
            ordinal=1,
            title="Sanitized 8D Procedure",
            chunks=(chunk,),
        )
        document = KnowledgeDocument.create(
            document_id=document_metadata["documentId"],
            document_version=document_metadata["documentVersion"],
            document_type=document_metadata["documentType"],
            owner=metadata["owner"],
            classification=metadata["classification"],
            tenant_id=TENANT_ID,
            security_domain=SECURITY_DOMAIN,
            effective_at=datetime.fromisoformat(
                document_metadata["effectiveAt"].replace("Z", "+00:00")
            ),
            expires_at=datetime.fromisoformat(
                document_metadata["expiresAt"].replace("Z", "+00:00")
            ),
            status=self._knowledge_status,
            sections=(section,),
        )
        return (
            KnowledgePack.create(
                knowledge_pack_id=metadata["knowledgePackId"],
                knowledge_pack_version=metadata["knowledgePackVersion"],
                tenant_id=TENANT_ID,
                security_domain=SECURITY_DOMAIN,
                owner=metadata["owner"],
                classification=metadata["classification"],
                provenance="package7-validated",
                documents=(document,),
            ),
            document,
        )

    @staticmethod
    def _graph(
        package: MaterializedPackage,
        revision: CanonicalWorkflowRevision,
        bindings: tuple[MatchedDefinitionBinding, ...],
        platform_execution_identity: str,
        evidence_ids: tuple[str, ...],
        outcome_id: str,
    ):
        nodes = [
            NodeSpec(
                NodeType.BUSINESS_PROBLEM,
                SCENARIO_ID,
                "supplierQuality.graph.problem",
                phase=Phase.SUCCEEDED,
                evidence_ids=(evidence_ids[0],),
                visibility=ProjectionVisibility.PRODUCT,
            ),
            NodeSpec(
                NodeType.PLAN,
                revision.canonical_workflow_revision_id,
                "supplierQuality.graph.plan",
                phase=Phase.SUCCEEDED,
                evidence_ids=(revision.approval_id,),
            ),
            NodeSpec(
                NodeType.WORKFLOW,
                f"workflow:{revision.approved_candidate_digest[:24]}",
                "supplierQuality.graph.workflow",
                phase=Phase.SUCCEEDED,
                evidence_ids=evidence_ids[1:],
            ),
            NodeSpec(
                NodeType.KNOWLEDGE,
                package.knowledge_manifest["knowledgePackId"],
                "supplierQuality.graph.knowledge",
                phase=Phase.SUCCEEDED,
                evidence_ids=(evidence_ids[0],),
            ),
            NodeSpec(
                NodeType.RUNTIME_REALIZATION,
                RUNTIME_TARGET.target,
                "supplierQuality.graph.runtime",
                phase=Phase.SUCCEEDED,
                evidence_ids=evidence_ids[1:],
                visibility=ProjectionVisibility.TECHNICAL,
            ),
            NodeSpec(
                NodeType.OUTCOME,
                outcome_id,
                "supplierQuality.graph.outcome",
                phase=Phase.SUCCEEDED,
                evidence_ids=evidence_ids[1:],
            ),
        ]
        for task, binding, task_evidence in zip(
            revision.tasks, bindings, evidence_ids[1:], strict=True
        ):
            nodes.append(
                NodeSpec(
                    NodeType.TASK,
                    task.future_task_id,
                    f"supplierQuality.graph.task.{task.future_task_id}",
                    phase=Phase.SUCCEEDED,
                    evidence_ids=(task_evidence,),
                )
            )
            selected = binding.match_decision.selected_definition_id
            if selected is not None and selected not in {
                item.entity_id for item in nodes
            }:
                nodes.append(
                    NodeSpec(
                        NodeType.DEFINITION,
                        selected,
                        "supplierQuality.graph.definition",
                        phase=Phase.SUCCEEDED,
                        evidence_ids=(binding.match_decision.decision_id,),
                        visibility=ProjectionVisibility.TECHNICAL,
                    )
                )
        workflow_id = f"workflow:{revision.approved_candidate_digest[:24]}"
        relations = [
            _relation(
                SCENARIO_ID,
                revision.canonical_workflow_revision_id,
                RelationType.DECOMPOSES_TO,
                GraphLayer.PLAN,
                (revision.approval_id,),
                visibility=ProjectionVisibility.PRODUCT,
            ),
            _relation(
                revision.canonical_workflow_revision_id,
                workflow_id,
                RelationType.TRIGGERS,
                GraphLayer.PLAN,
                (revision.approval_id,),
            ),
            _relation(
                workflow_id,
                outcome_id,
                RelationType.PRODUCES,
                GraphLayer.DATA_EVIDENCE,
                evidence_ids[1:],
            ),
        ]
        for task, binding, task_evidence in zip(
            revision.tasks, bindings, evidence_ids[1:], strict=True
        ):
            relations.append(
                _relation(
                    workflow_id,
                    task.future_task_id,
                    RelationType.CONTAINS,
                    GraphLayer.PLAN,
                    (task_evidence,),
                    cardinality=Cardinality.ONE_TO_MANY,
                    observed_target_count=3,
                )
            )
            selected = binding.match_decision.selected_definition_id
            if selected is not None:
                relations.append(
                    _relation(
                        task.future_task_id,
                        selected,
                        RelationType.ASSIGNED_TO,
                        GraphLayer.ASSIGNMENT,
                        (binding.match_decision.decision_id,),
                        visibility=ProjectionVisibility.TECHNICAL,
                    )
                )
        relations.append(
            _relation(
                revision.tasks[1].future_task_id,
                package.knowledge_manifest["knowledgePackId"],
                RelationType.REFERENCES,
                GraphLayer.DATA_EVIDENCE,
                (evidence_ids[0],),
            )
        )
        return build_graph(
            SnapshotContext(
                authoritative_input_id=package.manifest["canonicalDigest"],
                approved_plan_revision=revision.canonical_workflow_revision_id,
                execution_snapshot_id=platform_execution_identity,
                security_domain=SECURITY_DOMAIN,
            ),
            nodes,
            relations,
        )


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def _parse_checksums(value: str) -> dict[str, str]:
    result = {}
    for line in value.splitlines():
        parts = line.split("  ", 1)
        if len(parts) != 2:
            raise SupplierQualityDemoFailure("CHECKSUM_MANIFEST_INVALID")
        digest, relative = parts
        if (
            _DIGEST.fullmatch(digest) is None
            or _SAFE_RELATIVE.fullmatch(relative) is None
            or relative.startswith("/")
            or ".." in Path(relative).parts
            or relative in result
        ):
            raise SupplierQualityDemoFailure("CHECKSUM_MANIFEST_INVALID")
        result[relative] = digest
    return result


def _bounded_path(root: Path, relative: str) -> Path:
    if (
        _SAFE_RELATIVE.fullmatch(relative) is None
        or relative.startswith("/")
        or ".." in Path(relative).parts
    ):
        raise SupplierQualityDemoFailure("PACKAGE_PATH_INVALID")
    candidate = (root / relative).resolve()
    if candidate.parent != root and root not in candidate.parents:
        raise SupplierQualityDemoFailure("PACKAGE_PATH_INVALID")
    return candidate


def _read_bytes(root: Path, relative: str) -> bytes:
    path = _bounded_path(root, relative)
    if not path.is_file():
        raise SupplierQualityDemoFailure("PACKAGE_INPUT_MISSING")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise SupplierQualityDemoUnavailable("PACKAGE_INPUT_UNAVAILABLE") from exc


def _read_text(root: Path, relative: str) -> str:
    try:
        return _read_bytes(root, relative).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SupplierQualityDemoFailure("PACKAGE_INPUT_ENCODING_INVALID") from exc


def _read_json(root: Path, relative: str) -> Mapping[str, Any]:
    try:
        value = json.loads(_read_text(root, relative))
    except json.JSONDecodeError as exc:
        raise SupplierQualityDemoFailure("PACKAGE_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise SupplierQualityDemoFailure("PACKAGE_JSON_INVALID")
    return value


def _relation(
    source: str,
    target: str,
    relation_type: RelationType,
    layer: GraphLayer,
    evidence_ids: Sequence[str],
    *,
    visibility: ProjectionVisibility = ProjectionVisibility.BOTH,
    cardinality: Cardinality = Cardinality.ONE_TO_ONE,
    observed_target_count: int = 1,
) -> RelationSpec:
    return RelationSpec(
        source_entity_id=source,
        target_entity_id=target,
        relation_types=(relation_type,),
        layer=layer,
        declared_cardinality=cardinality,
        state=Phase.SUCCEEDED,
        evidence_ids=tuple(evidence_ids),
        projection_visibility=visibility,
        semantic_discriminator=f"{source}:{relation_type.value}:{target}",
        tenant_or_security_domain=SECURITY_DOMAIN,
        observed_source_count=1,
        observed_target_count=observed_target_count,
    )
