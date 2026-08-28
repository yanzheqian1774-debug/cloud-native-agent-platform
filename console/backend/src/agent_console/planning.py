"""Internal bounded intent and canonical planning boundary for v0.2.

The values in this module are in-memory planning records.  They are not public
DTOs, Kubernetes resources, executable Workflows, or persistence contracts.
Only an exactly approved canonical revision is eligible for a future matcher.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Protocol

QUESTION_TEXT_LIMIT = 2_000
ITEM_TEXT_LIMIT = 500
TASK_LIMIT = 32
DEPENDENCY_LIMIT = 128
SERIALIZED_CANDIDATE_LIMIT = 32_000
SCHEMA_VERSION = "planning.v1"
POLICY_VERSION = "supplier-quality.v1"
DIGEST_ALGORITHM = "sha256-canonical-json-nfc-v1"

_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,199}$")
_LOCALE = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
_SECRET = re.compile(
    r"(?:api[_-]?key|authorization|bearer|credential|password|secret|token)",
    re.IGNORECASE,
)
_SUPPORTED_TASK_TYPES = frozenset(
    {"COLLECT", "ANALYZE", "VALIDATE", "SUMMARIZE", "REVIEW"}
)


class PlanningError(ValueError):
    """Stable disclosure-safe planning failure."""


class PlanningState(StrEnum):
    DRAFT = "DRAFT"
    GENERATED = "GENERATED"
    VALIDATING = "VALIDATING"
    VALID = "VALID"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    CANONICALIZED = "CANONICALIZED"
    INVALID = "INVALID"
    UNSUPPORTED = "UNSUPPORTED"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class IssueSeverity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"


class SupportState(StrEnum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class PlanningDecision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class CandidateGenerator(Protocol):
    """Port for inert candidate generation; implementations grant no authority."""

    generator_id: str
    generator_version: str

    def generate(self, question: BusinessQuestion) -> Mapping[str, object]: ...


@dataclass(frozen=True, slots=True)
class BusinessQuestion:
    request_id: str
    tenant_id: str
    security_domain: str
    principal: str
    locale: str
    scenario_id: str
    question: str
    created_at: datetime
    provenance: str


@dataclass(frozen=True, slots=True)
class IntentCandidate:
    candidate_id: str
    source_question_id: str
    generator_id: str
    generator_version: str
    objective: str
    constraints: tuple[str, ...]
    success_criteria: tuple[str, ...]
    assumptions: tuple[str, ...]
    uncertainties: tuple[str, ...]
    raw_tasks: tuple[Mapping[str, object], ...]
    lifecycle: PlanningState = PlanningState.GENERATED


@dataclass(frozen=True, slots=True)
class IntentRevision:
    intent_id: str
    intent_revision_id: str
    revision: int
    predecessor_revision_id: str | None
    schema_version: str
    policy_version: str
    source_question_id: str
    objective: str
    constraints: tuple[str, ...]
    success_criteria: tuple[str, ...]
    canonical_digest: str


@dataclass(frozen=True, slots=True)
class TaskRequirement:
    task_requirement_id: str
    future_task_id: str
    intent_revision_id: str
    task_type: str
    business_purpose: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    dependencies: tuple[str, ...]
    constraints: tuple[str, ...]
    acceptance_conditions: tuple[str, ...]
    risk_classification: str
    approval_classification: str
    unresolved_requirements: tuple[str, ...]
    canonical_ordinal: int


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    reason_code: str
    severity: IssueSeverity
    element_id: str
    support_state: SupportState


@dataclass(frozen=True, slots=True)
class ValidationReport:
    candidate_digest: str | None
    policy_version: str
    issues: tuple[ValidationIssue, ...]
    approval_eligible: bool
    state: PlanningState


@dataclass(frozen=True, slots=True)
class WorkflowCandidate:
    workflow_candidate_id: str
    revision: int
    predecessor_revision_id: str | None
    tenant_id: str
    security_domain: str
    intent_revision: IntentRevision
    tasks: tuple[TaskRequirement, ...]
    ordered_task_ids: tuple[str, ...]
    candidate_digest: str
    policy_version: str
    generator_id: str
    generator_version: str
    limitations: tuple[str, ...]
    lifecycle: PlanningState


@dataclass(frozen=True, slots=True)
class PlanningResult:
    question: BusinessQuestion
    intent_candidate: IntentCandidate
    workflow_candidate: WorkflowCandidate | None
    validation: ValidationReport


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    approval_request_id: str
    tenant_id: str
    security_domain: str
    candidate_digest: str
    policy_version: str
    purpose: str


@dataclass(frozen=True, slots=True)
class ApprovalDecisionRecord:
    approval_id: str
    request_id: str
    candidate_digest: str
    policy_version: str
    actor: str
    decision: PlanningDecision
    decided_at: datetime
    replay_identity: str
    reason_code: str


@dataclass(frozen=True, slots=True)
class CanonicalWorkflowRevision:
    canonical_workflow_revision_id: str
    revision: int
    predecessor_revision_id: str | None
    tenant_id: str
    security_domain: str
    approved_candidate_digest: str
    approval_id: str
    policy_version: str
    intent_revision: IntentRevision
    tasks: tuple[TaskRequirement, ...]
    ordered_task_ids: tuple[str, ...]
    limitations: tuple[str, ...]
    matching_eligible: bool
    lifecycle: PlanningState = PlanningState.CANONICALIZED


@dataclass(frozen=True, slots=True)
class ProductSemanticCorrection:
    correction_id: str
    tenant_id: str
    security_domain: str
    principal: str
    predecessor_revision_id: str
    predecessor_digest: str
    affected_element_id: str
    field: str
    before: str
    after: str
    reason_code: str


def _fail(code: str) -> PlanningError:
    return PlanningError(code)


def _text(value: object, code: str, *, limit: int = ITEM_TEXT_LIMIT) -> str:
    if not isinstance(value, str):
        raise _fail(code)
    normalized = " ".join(unicodedata.normalize("NFC", value).split())
    if not normalized or len(normalized) > limit:
        raise _fail(code if not normalized else "INPUT_LIMIT_EXCEEDED")
    if any(unicodedata.category(char) == "Cc" for char in normalized):
        raise _fail("INVALID_CONTROL_CHARACTER")
    if _SECRET.search(normalized):
        raise _fail("SECRET_SHAPED_VALUE_REJECTED")
    return normalized


def _identifier(value: object, code: str) -> str:
    normalized = _text(value, code, limit=200).lower()
    if not _IDENTIFIER.fullmatch(normalized):
        raise _fail(code)
    return normalized


def _timestamp(value: object, code: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _fail(code)
    offset = value.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise _fail(code)
    return value


def _string_items(
    value: object, code: str, *, allow_empty: bool = True
) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise _fail(code)
    if len(value) > TASK_LIMIT:
        raise _fail("INPUT_LIMIT_EXCEEDED")
    items = tuple(_text(item, code) for item in value)
    if not allow_empty and not items:
        raise _fail(code)
    if len(set(items)) != len(items):
        raise _fail("AMBIGUOUS_DUPLICATE_VALUE")
    return tuple(sorted(items))


def create_business_question(
    *,
    request_id: object,
    tenant_id: object,
    security_domain: object,
    principal: object,
    locale: object,
    scenario_id: object,
    question: object,
    created_at: object,
    provenance: object,
) -> BusinessQuestion:
    normalized_locale = _text(locale, "INVALID_LOCALE", limit=35)
    if not _LOCALE.fullmatch(normalized_locale):
        raise _fail("INVALID_LOCALE")
    return BusinessQuestion(
        request_id=_identifier(request_id, "INVALID_REQUEST_ID"),
        tenant_id=_identifier(tenant_id, "INVALID_TENANT"),
        security_domain=_identifier(security_domain, "INVALID_SECURITY_DOMAIN"),
        principal=_identifier(principal, "INVALID_PRINCIPAL"),
        locale=normalized_locale.lower(),
        scenario_id=_identifier(scenario_id, "INVALID_SCENARIO"),
        question=_text(question, "INVALID_QUESTION", limit=QUESTION_TEXT_LIMIT),
        created_at=_timestamp(created_at, "INVALID_QUESTION_TIMESTAMP"),
        provenance=_identifier(provenance, "INVALID_PROVENANCE"),
    )


def _canonical_value(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return [_canonical_value(item) for item in value]
    if isinstance(value, list):
        return [_canonical_value(item) for item in value]
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_value(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if value is None or isinstance(value, (bool, int)):
        return value
    raise _fail("NON_CANONICAL_VALUE")


def canonical_json(value: object) -> str:
    return json.dumps(
        _canonical_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def _parse_intent_candidate(
    question: BusinessQuestion,
    raw: Mapping[str, object],
    generator: CandidateGenerator,
) -> IntentCandidate:
    if not isinstance(raw, Mapping):
        raise _fail("MALFORMED_CANDIDATE")
    try:
        encoded = json.dumps(raw, default=str)
    except (TypeError, ValueError, RecursionError) as exc:
        raise _fail("MALFORMED_CANDIDATE") from exc
    if len(encoded) > SERIALIZED_CANDIDATE_LIMIT:
        raise _fail("INPUT_LIMIT_EXCEEDED")
    allowed = {
        "objective",
        "constraints",
        "success_criteria",
        "assumptions",
        "uncertainties",
        "tasks",
    }
    if set(raw) != allowed:
        raise _fail("UNKNOWN_OR_MISSING_FIELD")
    tasks = raw["tasks"]
    if not isinstance(tasks, Sequence) or isinstance(tasks, (str, bytes)):
        raise _fail("INVALID_TASKS")
    if (
        not tasks
        or len(tasks) > TASK_LIMIT
        or not all(isinstance(item, Mapping) for item in tasks)
    ):
        raise _fail("INVALID_TASKS" if not tasks else "INPUT_LIMIT_EXCEEDED")
    semantic = {
        "question": question.request_id,
        "generator": [generator.generator_id, generator.generator_version],
        "candidate": raw,
    }
    return IntentCandidate(
        candidate_id=f"intent-candidate:{_digest(semantic)}",
        source_question_id=question.request_id,
        generator_id=_identifier(generator.generator_id, "INVALID_GENERATOR"),
        generator_version=_identifier(
            generator.generator_version, "INVALID_GENERATOR_VERSION"
        ),
        objective=_text(raw["objective"], "INVALID_OBJECTIVE"),
        constraints=_string_items(raw["constraints"], "INVALID_CONSTRAINTS"),
        success_criteria=_string_items(
            raw["success_criteria"], "INVALID_SUCCESS_CRITERIA", allow_empty=False
        ),
        assumptions=_string_items(raw["assumptions"], "INVALID_ASSUMPTIONS"),
        uncertainties=_string_items(raw["uncertainties"], "INVALID_UNCERTAINTIES"),
        raw_tasks=tuple(dict(item) for item in tasks),
    )


def _parse_tasks(
    candidate: IntentCandidate, intent_revision_id: str
) -> tuple[TaskRequirement, ...]:
    allowed = {
        "id",
        "type",
        "purpose",
        "inputs",
        "outputs",
        "dependencies",
        "constraints",
        "acceptance_conditions",
        "risk",
        "approval",
        "unresolved",
        "ordinal",
    }
    parsed: list[TaskRequirement] = []
    seen: set[str] = set()
    dependency_count = 0
    for raw in candidate.raw_tasks:
        if set(raw) != allowed:
            raise _fail("UNKNOWN_OR_MISSING_TASK_FIELD")
        task_id = _identifier(raw["id"], "INVALID_TASK_ID")
        if task_id in seen:
            raise _fail("DUPLICATE_TASK_ID")
        seen.add(task_id)
        task_type = _identifier(raw["type"], "INVALID_TASK_TYPE").upper()
        if task_type not in _SUPPORTED_TASK_TYPES:
            raise _fail("UNSUPPORTED_TASK_TYPE")
        dependencies = tuple(
            _identifier(item, "INVALID_DEPENDENCY")
            for item in _string_items(raw["dependencies"], "INVALID_DEPENDENCIES")
        )
        dependency_count += len(dependencies)
        if dependency_count > DEPENDENCY_LIMIT:
            raise _fail("DEPENDENCY_LIMIT_EXCEEDED")
        if task_id in dependencies:
            raise _fail("SELF_DEPENDENCY")
        ordinal = raw["ordinal"]
        if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 0:
            raise _fail("INVALID_TASK_ORDINAL")
        parsed.append(
            TaskRequirement(
                task_requirement_id=(
                    f"task-requirement:{intent_revision_id}:{task_id}"
                ),
                future_task_id=task_id,
                intent_revision_id=intent_revision_id,
                task_type=task_type,
                business_purpose=_text(raw["purpose"], "INVALID_TASK_PURPOSE"),
                inputs=_string_items(raw["inputs"], "INVALID_TASK_INPUTS"),
                outputs=_string_items(
                    raw["outputs"], "INVALID_TASK_OUTPUTS", allow_empty=False
                ),
                dependencies=tuple(sorted(dependencies)),
                constraints=_string_items(
                    raw["constraints"], "INVALID_TASK_CONSTRAINTS"
                ),
                acceptance_conditions=_string_items(
                    raw["acceptance_conditions"],
                    "INVALID_ACCEPTANCE_CONDITIONS",
                    allow_empty=False,
                ),
                risk_classification=_identifier(raw["risk"], "INVALID_RISK").upper(),
                approval_classification=_identifier(
                    raw["approval"], "INVALID_APPROVAL_CLASSIFICATION"
                ).upper(),
                unresolved_requirements=_string_items(
                    raw["unresolved"], "INVALID_UNRESOLVED_REQUIREMENTS"
                ),
                canonical_ordinal=ordinal,
            )
        )
    for task in parsed:
        missing = set(task.dependencies) - seen
        if missing:
            raise _fail("MISSING_DEPENDENCY")
        if task.unresolved_requirements:
            raise _fail("UNKNOWN_REQUIREMENT")
    return tuple(parsed)


def _ordered_tasks(tasks: tuple[TaskRequirement, ...]) -> tuple[str, ...]:
    by_id = {task.future_task_id: task for task in tasks}
    indegree = {task_id: 0 for task_id in by_id}
    successors: dict[str, list[str]] = defaultdict(list)
    for task in tasks:
        for predecessor in task.dependencies:
            indegree[task.future_task_id] += 1
            successors[predecessor].append(task.future_task_id)
    ready = sorted(
        (by_id[item] for item, count in indegree.items() if count == 0),
        key=lambda item: (item.canonical_ordinal, item.future_task_id),
    )
    ordered: list[str] = []
    while ready:
        task = ready.pop(0)
        ordered.append(task.future_task_id)
        for successor in sorted(successors[task.future_task_id]):
            indegree[successor] -= 1
            if indegree[successor] == 0:
                ready.append(by_id[successor])
                ready.sort(
                    key=lambda item: (item.canonical_ordinal, item.future_task_id)
                )
    if len(ordered) != len(tasks):
        raise _fail("DEPENDENCY_CYCLE")
    return tuple(ordered)


def _semantic_task(task: TaskRequirement) -> Mapping[str, object]:
    return {
        "taskRequirementId": task.task_requirement_id,
        "futureTaskId": task.future_task_id,
        "intentRevisionId": task.intent_revision_id,
        "taskType": task.task_type,
        "businessPurpose": task.business_purpose,
        "inputs": task.inputs,
        "outputs": task.outputs,
        "dependencies": task.dependencies,
        "constraints": task.constraints,
        "acceptanceConditions": task.acceptance_conditions,
        "riskClassification": task.risk_classification,
        "approvalClassification": task.approval_classification,
        "unresolvedRequirements": task.unresolved_requirements,
        "canonicalOrdinal": task.canonical_ordinal,
    }


class PlanningEngine:
    """In-memory candidate, approval, and immutable successor coordinator."""

    def __init__(self, *, policy_version: str = POLICY_VERSION) -> None:
        self.policy_version = _identifier(policy_version, "INVALID_POLICY_VERSION")
        self._results: dict[str, PlanningResult] = {}
        self._requests: dict[str, ApprovalRequest] = {}
        self._decisions: dict[str, ApprovalDecisionRecord] = {}
        self._canonical: dict[str, CanonicalWorkflowRevision] = {}
        self._superseded: set[str] = set()

    def generate(
        self, question: BusinessQuestion, generator: CandidateGenerator
    ) -> PlanningResult:
        if not isinstance(question, BusinessQuestion):
            raise _fail("INVALID_QUESTION")
        raw = generator.generate(question)
        return self.validate(question, raw, generator)

    def validate(
        self,
        question: BusinessQuestion,
        raw: Mapping[str, object],
        generator: CandidateGenerator,
        *,
        predecessor: CanonicalWorkflowRevision | None = None,
    ) -> PlanningResult:
        if predecessor is not None:
            self._assert_scope(
                question.tenant_id, question.security_domain, predecessor
            )
        try:
            candidate = _parse_intent_candidate(question, raw, generator)
            intent_number = 1 if predecessor is None else predecessor.revision + 1
            intent_id = f"intent:{question.request_id}"
            intent_seed = {
                "schemaVersion": SCHEMA_VERSION,
                "policyVersion": self.policy_version,
                "intentId": intent_id,
                "revision": intent_number,
                "predecessor": (
                    None
                    if predecessor is None
                    else predecessor.intent_revision.intent_revision_id
                ),
                "questionId": question.request_id,
                "objective": candidate.objective,
                "constraints": candidate.constraints,
                "successCriteria": candidate.success_criteria,
                "tenantId": question.tenant_id,
                "securityDomain": question.security_domain,
            }
            intent_digest = _digest(intent_seed)
            intent_revision_id = f"intent-revision:{intent_digest}"
            intent = IntentRevision(
                intent_id=intent_id,
                intent_revision_id=intent_revision_id,
                revision=intent_number,
                predecessor_revision_id=(
                    None
                    if predecessor is None
                    else predecessor.intent_revision.intent_revision_id
                ),
                schema_version=SCHEMA_VERSION,
                policy_version=self.policy_version,
                source_question_id=question.request_id,
                objective=candidate.objective,
                constraints=candidate.constraints,
                success_criteria=candidate.success_criteria,
                canonical_digest=intent_digest,
            )
            tasks = _parse_tasks(candidate, intent_revision_id)
            ordered_ids = _ordered_tasks(tasks)
            task_by_id = {task.future_task_id: task for task in tasks}
            tasks = tuple(task_by_id[task_id] for task_id in ordered_ids)
            semantic = {
                "schemaVersion": SCHEMA_VERSION,
                "digestAlgorithm": DIGEST_ALGORITHM,
                "policyVersion": self.policy_version,
                "tenantId": question.tenant_id,
                "securityDomain": question.security_domain,
                "intent": intent_seed,
                "tasks": tuple(_semantic_task(task) for task in tasks),
                "orderedTaskIds": ordered_ids,
                "predecessor": (
                    None
                    if predecessor is None
                    else predecessor.canonical_workflow_revision_id
                ),
            }
            digest = _digest(semantic)
            workflow = WorkflowCandidate(
                workflow_candidate_id=f"workflow-candidate:{digest}",
                revision=intent_number,
                predecessor_revision_id=(
                    None
                    if predecessor is None
                    else predecessor.canonical_workflow_revision_id
                ),
                tenant_id=question.tenant_id,
                security_domain=question.security_domain,
                intent_revision=intent,
                tasks=tasks,
                ordered_task_ids=ordered_ids,
                candidate_digest=digest,
                policy_version=self.policy_version,
                generator_id=candidate.generator_id,
                generator_version=candidate.generator_version,
                limitations=("FUTURE_MATCHING_ONLY", "NON_EXECUTABLE"),
                lifecycle=PlanningState.VALID,
            )
            report = ValidationReport(
                candidate_digest=digest,
                policy_version=self.policy_version,
                issues=(),
                approval_eligible=True,
                state=PlanningState.VALID,
            )
        except PlanningError as exc:
            reason = str(exc)
            state = (
                PlanningState.UNSUPPORTED
                if reason.startswith("UNSUPPORTED")
                else PlanningState.UNKNOWN
                if reason.startswith("UNKNOWN")
                else PlanningState.INVALID
            )
            fallback = IntentCandidate(
                candidate_id="intent-candidate:invalid",
                source_question_id=question.request_id,
                generator_id=_identifier(generator.generator_id, "INVALID_GENERATOR"),
                generator_version=_identifier(
                    generator.generator_version, "INVALID_GENERATOR_VERSION"
                ),
                objective="INVALID",
                constraints=(),
                success_criteria=(),
                assumptions=(),
                uncertainties=(),
                raw_tasks=(),
                lifecycle=state,
            )
            report = ValidationReport(
                candidate_digest=None,
                policy_version=self.policy_version,
                issues=(
                    ValidationIssue(
                        reason_code=reason,
                        severity=IssueSeverity.ERROR,
                        element_id=question.request_id,
                        support_state=(
                            SupportState.UNSUPPORTED
                            if state == PlanningState.UNSUPPORTED
                            else SupportState.UNKNOWN
                            if state == PlanningState.UNKNOWN
                            else SupportState.SUPPORTED
                        ),
                    ),
                ),
                approval_eligible=False,
                state=state,
            )
            result = PlanningResult(question, fallback, None, report)
            self._results[fallback.candidate_id] = result
            return result
        result = PlanningResult(question, candidate, workflow, report)
        self._results[workflow.workflow_candidate_id] = result
        return result

    def request_approval(self, result: PlanningResult) -> ApprovalRequest:
        workflow = result.workflow_candidate
        if workflow is None or not result.validation.approval_eligible:
            raise _fail("CANDIDATE_NOT_APPROVAL_ELIGIBLE")
        request_id = f"planning-approval-request:{workflow.candidate_digest}"
        request = ApprovalRequest(
            approval_request_id=request_id,
            tenant_id=workflow.tenant_id,
            security_domain=workflow.security_domain,
            candidate_digest=workflow.candidate_digest,
            policy_version=workflow.policy_version,
            purpose="CANONICAL_PLANNING",
        )
        self._requests[request_id] = request
        return request

    def decide(
        self,
        result: PlanningResult,
        request: ApprovalRequest,
        *,
        tenant_id: object,
        security_domain: object,
        actor: object,
        decision: object,
        decided_at: object,
        replay_identity: object,
        reason_code: object,
        predecessor: CanonicalWorkflowRevision | None = None,
    ) -> CanonicalWorkflowRevision | None:
        workflow = result.workflow_candidate
        if workflow is None or not result.validation.approval_eligible:
            raise _fail("CANDIDATE_NOT_APPROVAL_ELIGIBLE")
        trusted_tenant = _identifier(tenant_id, "INVALID_TENANT")
        trusted_domain = _identifier(security_domain, "INVALID_SECURITY_DOMAIN")
        if trusted_tenant != workflow.tenant_id:
            raise _fail("TENANT_SCOPE_MISMATCH")
        if trusted_domain != workflow.security_domain:
            raise _fail("SECURITY_DOMAIN_SCOPE_MISMATCH")
        stored_request = self._requests.get(request.approval_request_id)
        if stored_request != request:
            raise _fail("INVALID_APPROVAL_REQUEST")
        if (
            request.candidate_digest != workflow.candidate_digest
            or request.policy_version != workflow.policy_version
            or request.tenant_id != workflow.tenant_id
            or request.security_domain != workflow.security_domain
        ):
            raise _fail("APPROVAL_BINDING_MISMATCH")
        if predecessor is not None:
            self._assert_scope(
                workflow.tenant_id, workflow.security_domain, predecessor
            )
            if workflow.revision != predecessor.revision + 1:
                raise _fail("SUCCESSOR_REVISION_MISMATCH")
            if (
                workflow.predecessor_revision_id
                != predecessor.canonical_workflow_revision_id
            ):
                raise _fail("SUCCESSOR_LINK_MISMATCH")
        elif workflow.predecessor_revision_id is not None:
            raise _fail("SUCCESSOR_PREDECESSOR_REQUIRED")
        actor_value = _identifier(actor, "INVALID_APPROVAL_ACTOR")
        replay_value = _identifier(replay_identity, "INVALID_REPLAY_IDENTITY")
        reason_value = _identifier(reason_code, "INVALID_APPROVAL_REASON").upper()
        timestamp = _timestamp(decided_at, "INVALID_APPROVAL_TIMESTAMP")
        if not isinstance(decision, PlanningDecision):
            raise _fail("INVALID_APPROVAL_DECISION")
        approval_identity = {
            "request": request.approval_request_id,
            "replay": replay_value,
        }
        approval_id = f"planning-approval:{_digest(approval_identity)}"
        record = ApprovalDecisionRecord(
            approval_id=approval_id,
            request_id=request.approval_request_id,
            candidate_digest=request.candidate_digest,
            policy_version=request.policy_version,
            actor=actor_value,
            decision=decision,
            decided_at=timestamp,
            replay_identity=replay_value,
            reason_code=reason_value,
        )
        existing = self._decisions.get(replay_value)
        if existing is not None:
            if existing != record:
                raise _fail("APPROVAL_REPLAY_MISMATCH")
            return self._canonical.get(existing.approval_id)
        self._decisions[replay_value] = record
        if decision == PlanningDecision.REJECT:
            return None
        revision = workflow.revision
        canonical = CanonicalWorkflowRevision(
            canonical_workflow_revision_id=f"canonical-workflow-revision:{workflow.candidate_digest}",
            revision=revision,
            predecessor_revision_id=(
                None
                if predecessor is None
                else predecessor.canonical_workflow_revision_id
            ),
            tenant_id=workflow.tenant_id,
            security_domain=workflow.security_domain,
            approved_candidate_digest=workflow.candidate_digest,
            approval_id=record.approval_id,
            policy_version=workflow.policy_version,
            intent_revision=workflow.intent_revision,
            tasks=workflow.tasks,
            ordered_task_ids=workflow.ordered_task_ids,
            limitations=workflow.limitations,
            matching_eligible=True,
        )
        self._canonical[record.approval_id] = canonical
        if predecessor is not None:
            self._superseded.add(predecessor.canonical_workflow_revision_id)
        return canonical

    def corrected_successor(
        self,
        predecessor: CanonicalWorkflowRevision,
        correction: ProductSemanticCorrection,
        question: BusinessQuestion,
        raw: Mapping[str, object],
        generator: CandidateGenerator,
    ) -> PlanningResult:
        self._assert_scope(question.tenant_id, question.security_domain, predecessor)
        if (
            correction.tenant_id != predecessor.tenant_id
            or correction.security_domain != predecessor.security_domain
            or correction.predecessor_revision_id
            != predecessor.canonical_workflow_revision_id
            or correction.predecessor_digest != predecessor.approved_candidate_digest
        ):
            raise _fail("CORRECTION_BINDING_MISMATCH")
        _identifier(correction.correction_id, "INVALID_CORRECTION_ID")
        _identifier(correction.principal, "INVALID_CORRECTION_PRINCIPAL")
        _identifier(correction.reason_code, "INVALID_CORRECTION_REASON")
        before = _text(correction.before, "INVALID_CORRECTION_BEFORE")
        after = _text(correction.after, "INVALID_CORRECTION_AFTER")
        if before == after:
            raise _fail("INVALID_CORRECTION_PATCH")
        if correction.field != "objective":
            raise _fail("UNSUPPORTED_CORRECTION_FIELD")
        if (
            correction.affected_element_id
            != predecessor.intent_revision.intent_revision_id
        ):
            raise _fail("INVALID_CORRECTION_TARGET")
        if before != predecessor.intent_revision.objective:
            raise _fail("CORRECTION_BEFORE_MISMATCH")
        if not isinstance(raw, Mapping) or raw.get("objective") != after:
            raise _fail("CORRECTION_AFTER_MISMATCH")
        return self.validate(question, raw, generator, predecessor=predecessor)

    @staticmethod
    def _assert_scope(
        tenant_id: str,
        security_domain: str,
        revision: CanonicalWorkflowRevision,
    ) -> None:
        if tenant_id != revision.tenant_id:
            raise _fail("TENANT_SCOPE_MISMATCH")
        if security_domain != revision.security_domain:
            raise _fail("SECURITY_DOMAIN_SCOPE_MISMATCH")

    def mark_superseded(
        self,
        predecessor: CanonicalWorkflowRevision,
        successor: CanonicalWorkflowRevision,
    ) -> CanonicalWorkflowRevision:
        self._assert_scope(successor.tenant_id, successor.security_domain, predecessor)
        if (
            successor.predecessor_revision_id
            != predecessor.canonical_workflow_revision_id
        ):
            raise _fail("SUCCESSOR_LINK_MISMATCH")
        self._superseded.add(predecessor.canonical_workflow_revision_id)
        return replace(
            predecessor,
            matching_eligible=False,
            lifecycle=PlanningState.SUPERSEDED,
        )

    def is_matching_eligible(self, revision: CanonicalWorkflowRevision) -> bool:
        """Return current internal eligibility without mutating revision history."""
        return (
            revision.matching_eligible
            and revision.lifecycle == PlanningState.CANONICALIZED
            and revision.canonical_workflow_revision_id not in self._superseded
        )
