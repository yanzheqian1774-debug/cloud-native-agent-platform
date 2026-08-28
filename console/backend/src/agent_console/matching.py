"""Deterministic read-only Package 2 published-role matcher."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from enum import StrEnum

from agent_console.definition_authority import (
    IDENTIFIER_LIMIT,
    SEMANTIC_TEXT_LIMIT,
    SNAPSHOT_CONTRACT_VERSION,
    EffectiveDefinition,
    EffectiveDefinitionCatalogProvider,
    EffectiveDefinitionCatalogSnapshot,
    canonical_digest,
    canonical_json,
    effective_snapshot_identity,
)

MAX_TASKS = 32
MAX_REQUIREMENTS_PER_TASK = 32
MAX_CANDIDATES_PER_REQUIREMENT = 64
MAX_EVALUATIONS = 2_048
MAX_REASONS = 32
MAX_SERIALIZED_REQUEST_BYTES = 32 * 1024
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")


class MatchingError(ValueError):
    """Stable matcher failure that contains no denied candidate metadata."""


class MatchOutcome(StrEnum):
    MATCHED = "MATCHED"
    ROLE_GAP = "ROLE_GAP"


def _fail(code: str) -> MatchingError:
    return MatchingError(code)


def validate_serialized_matching_request_size(size: int) -> None:
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise _fail("MALFORMED_MATCHING_REQUEST")
    if size > MAX_SERIALIZED_REQUEST_BYTES:
        raise _fail("MATCHING_REQUEST_PAYLOAD_LIMIT_EXCEEDED")


def validate_candidate_evaluation_count(count: int) -> None:
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise _fail("MALFORMED_MATCHING_REQUEST")
    if count > MAX_EVALUATIONS:
        raise _fail("EVALUATION_LIMIT_EXCEEDED")


def _identifier(value: object) -> str:
    if not isinstance(value, str):
        raise _fail("MALFORMED_MATCHING_REQUEST")
    normalized = unicodedata.normalize("NFC", value)
    if len(normalized) > IDENTIFIER_LIMIT:
        raise _fail("IDENTIFIER_LIMIT_EXCEEDED")
    if _IDENTIFIER.fullmatch(normalized) is None:
        raise _fail("MALFORMED_MATCHING_REQUEST")
    return normalized


def _semantic_text(value: object) -> str:
    if not isinstance(value, str):
        raise _fail("MALFORMED_MATCHING_REQUEST")
    normalized = " ".join(unicodedata.normalize("NFC", value).split())
    if len(normalized) > SEMANTIC_TEXT_LIMIT:
        raise _fail("SEMANTIC_TEXT_LIMIT_EXCEEDED")
    if not normalized:
        raise _fail("MALFORMED_MATCHING_REQUEST")
    return normalized


@dataclass(frozen=True, slots=True)
class RoleRequirement:
    requirement_id: str
    duties: tuple[str, ...] = ()
    data: tuple[str, ...] = ()
    knowledge: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    runtimes: tuple[str, ...] = ()

    @classmethod
    def create(cls, *, requirement_id: str, **coverage) -> RoleRequirement:
        normalized = {}
        for field in (
            "duties",
            "data",
            "knowledge",
            "skills",
            "capabilities",
            "runtimes",
        ):
            raw_values = coverage.get(field, ())
            if isinstance(raw_values, (str, bytes)):
                raise _fail("MALFORMED_MATCHING_REQUEST")
            try:
                values = tuple(_semantic_text(value) for value in raw_values)
            except TypeError as exc:
                raise _fail("MALFORMED_MATCHING_REQUEST") from exc
            if len(set(values)) != len(values):
                raise _fail("AMBIGUOUS_REQUIREMENT")
            normalized[field] = tuple(sorted(values))
        return cls(requirement_id=_identifier(requirement_id), **normalized)


@dataclass(frozen=True, slots=True)
class TaskRoleRequirements:
    task_requirement_id: str
    requirements: tuple[RoleRequirement, ...]


@dataclass(frozen=True, slots=True)
class MatchingRequest:
    canonical_workflow_revision_id: str
    approved_workflow_digest: str
    tenant_id: str
    security_domain: str
    purpose: str
    evaluation_time: object
    tasks: tuple[TaskRoleRequirements, ...]


@dataclass(frozen=True, slots=True)
class CandidateScore:
    definition_id: str
    version_id: str
    definition_digest: str
    score: int


@dataclass(frozen=True, slots=True)
class RoleMatchDecision:
    decision_id: str
    requirement_id: str
    outcome: MatchOutcome
    snapshot_id: str
    selected_definition_id: str | None
    selected_version_id: str | None
    selected_definition_digest: str | None
    tied_candidates: tuple[CandidateScore, ...]
    missing_requirements: tuple[str, ...]
    reason_codes: tuple[str, ...]
    advisory_only: bool = True
    execution_authorized: bool = False


@dataclass(frozen=True, slots=True)
class MatchingResult:
    snapshot_id: str
    decisions: tuple[RoleMatchDecision, ...]
    provider_calls: int
    runtime_calls: int
    credential_grants: int
    permission_grants: int


class PublishedRoleMatcher:
    def __init__(self, provider: EffectiveDefinitionCatalogProvider) -> None:
        if provider is None or not hasattr(provider, "snapshot"):
            raise _fail("DEFINITION_AUTHORITY_MISSING")
        self._provider = provider

    def match(self, request: MatchingRequest) -> MatchingResult:
        if not isinstance(request, MatchingRequest):
            raise _fail("MALFORMED_MATCHING_REQUEST")
        for identity in (
            request.canonical_workflow_revision_id,
            request.approved_workflow_digest,
            request.tenant_id,
            request.security_domain,
            request.purpose,
        ):
            _identifier(identity)
        if any(not isinstance(task, TaskRoleRequirements) for task in request.tasks):
            raise _fail("MALFORMED_MATCHING_REQUEST")
        tasks = tuple(sorted(request.tasks, key=lambda item: item.task_requirement_id))
        if len(tasks) > MAX_TASKS:
            raise _fail("TASK_LIMIT_EXCEEDED")
        if len({item.task_requirement_id for item in tasks}) != len(tasks):
            raise _fail("DUPLICATE_TASK_REQUIREMENT")
        for task in tasks:
            _identifier(task.task_requirement_id)
            if len(task.requirements) > MAX_REQUIREMENTS_PER_TASK:
                raise _fail("REQUIREMENT_LIMIT_EXCEEDED")
            if len({item.requirement_id for item in task.requirements}) != len(
                task.requirements
            ):
                raise _fail("DUPLICATE_ROLE_REQUIREMENT")
            for requirement in task.requirements:
                self._validate_requirement(requirement)
        semantic = {
            "workflowRevisionId": request.canonical_workflow_revision_id,
            "workflowDigest": request.approved_workflow_digest,
            "tenantId": request.tenant_id,
            "securityDomain": request.security_domain,
            "purpose": request.purpose,
            "evaluationTime": request.evaluation_time,
            "tasks": tuple(
                {
                    "taskRequirementId": task.task_requirement_id,
                    "requirements": tuple(
                        asdict(item)
                        for item in sorted(
                            task.requirements, key=lambda req: req.requirement_id
                        )
                    ),
                }
                for task in tasks
            ),
        }
        validate_serialized_matching_request_size(
            len(canonical_json(semantic).encode("utf-8"))
        )
        snapshot = self._provider.snapshot(
            tenant_id=request.tenant_id,
            security_domain=request.security_domain,
            purpose=request.purpose,
            evaluation_time=request.evaluation_time,
            workflow_revision_id=request.canonical_workflow_revision_id,
            workflow_digest=request.approved_workflow_digest,
        )
        self._validate_snapshot(snapshot, request)
        requirements = tuple(
            requirement
            for task in tasks
            for requirement in sorted(
                task.requirements, key=lambda item: item.requirement_id
            )
        )
        if len(snapshot.definitions) > MAX_CANDIDATES_PER_REQUIREMENT:
            raise _fail("CANDIDATE_LIMIT_EXCEEDED")
        validate_candidate_evaluation_count(
            len(requirements) * len(snapshot.definitions)
        )
        decisions = tuple(
            self._match_one(requirement, snapshot) for requirement in requirements
        )
        return MatchingResult(snapshot.snapshot_id, decisions, 0, 0, 0, 0)

    @staticmethod
    def _validate_requirement(requirement: RoleRequirement) -> None:
        if not isinstance(requirement, RoleRequirement):
            raise _fail("MALFORMED_MATCHING_REQUEST")
        _identifier(requirement.requirement_id)
        for values in (
            requirement.duties,
            requirement.data,
            requirement.knowledge,
            requirement.skills,
            requirement.capabilities,
            requirement.runtimes,
        ):
            if tuple(sorted(_semantic_text(value) for value in values)) != values:
                raise _fail("AMBIGUOUS_REQUIREMENT")
            if len(set(values)) != len(values):
                raise _fail("AMBIGUOUS_REQUIREMENT")

    @staticmethod
    def _validate_snapshot(
        snapshot: EffectiveDefinitionCatalogSnapshot, request: MatchingRequest
    ) -> None:
        if (
            not isinstance(snapshot, EffectiveDefinitionCatalogSnapshot)
            or not snapshot.complete
            or snapshot.snapshot_contract_version != SNAPSHOT_CONTRACT_VERSION
        ):
            raise _fail("DEFINITION_CATALOG_UNAVAILABLE")
        if snapshot.tenant_id != request.tenant_id:
            raise _fail("TENANT_SCOPE_MISMATCH")
        if snapshot.security_domain != request.security_domain:
            raise _fail("SECURITY_DOMAIN_SCOPE_MISMATCH")
        if (
            snapshot.purpose != request.purpose
            or snapshot.evaluation_time != request.evaluation_time
            or snapshot.workflow_revision_id != request.canonical_workflow_revision_id
            or snapshot.workflow_digest != request.approved_workflow_digest
        ):
            raise _fail("MALFORMED_AUTHORITY_RECORD")
        ordered = tuple(
            sorted(
                snapshot.definitions,
                key=lambda item: (
                    item.version.definition_id,
                    item.version.version_id,
                    item.version.definition_digest,
                ),
            )
        )
        if ordered != snapshot.definitions or len(set(ordered)) != len(ordered):
            raise _fail("CONFLICTING_AUTHORITY_RECORDS")
        for item in ordered:
            item.version.validate()
            for identity in (
                item.publication_decision_id,
                item.match_authorization_decision_id,
                item.version.source_authority_revision,
            ):
                _identifier(identity)
            if item.version.tenant_id != snapshot.tenant_id:
                raise _fail("TENANT_SCOPE_MISMATCH")
            if item.version.security_domain != snapshot.security_domain:
                raise _fail("SECURITY_DOMAIN_SCOPE_MISMATCH")
        expected_references = tuple(
            sorted(
                reference
                for item in ordered
                for reference in (
                    item.publication_decision_id,
                    item.match_authorization_decision_id,
                )
            )
        )
        if snapshot.decision_references != expected_references:
            raise _fail("MALFORMED_AUTHORITY_RECORD")
        expected_snapshot_id = effective_snapshot_identity(
            tenant_id=snapshot.tenant_id,
            security_domain=snapshot.security_domain,
            purpose=snapshot.purpose,
            evaluation_time=snapshot.evaluation_time,
            workflow_revision_id=snapshot.workflow_revision_id,
            workflow_digest=snapshot.workflow_digest,
            source_authority_revision=snapshot.source_authority_revision,
            definitions=snapshot.definitions,
        )
        if snapshot.snapshot_id != expected_snapshot_id:
            raise _fail("MALFORMED_AUTHORITY_RECORD")

    def _match_one(
        self,
        requirement: RoleRequirement,
        snapshot: EffectiveDefinitionCatalogSnapshot,
    ) -> RoleMatchDecision:
        scored = tuple(
            score
            for score in (
                self._score(requirement, candidate)
                for candidate in snapshot.definitions
            )
            if score is not None
        )
        if not scored:
            reasons = ("ROLE_GAP", "NO_ELIGIBLE_ROLE_COVERS_REQUIREMENT")
            return self._decision(
                requirement,
                snapshot,
                MatchOutcome.ROLE_GAP,
                None,
                (),
                (requirement.requirement_id,),
                reasons,
            )
        ranked = tuple(
            sorted(
                scored,
                key=lambda item: (
                    -item.score,
                    item.definition_id,
                    item.version_id,
                    item.definition_digest,
                ),
            )
        )
        top_score = ranked[0].score
        ties = tuple(item for item in ranked if item.score == top_score)
        reasons = ["FULL_REQUIRED_COVERAGE", "DETERMINISTIC_SELECTION"]
        if len(ties) > 1:
            reasons.append("STABLE_TIE_BROKEN_BY_DEFINITION_VERSION_IDENTITY")
        selected = ties[0]
        return self._decision(
            requirement,
            snapshot,
            MatchOutcome.MATCHED,
            selected,
            ties,
            (),
            tuple(reasons),
        )

    @staticmethod
    def _score(
        requirement: RoleRequirement, candidate: EffectiveDefinition
    ) -> CandidateScore | None:
        role = candidate.version.role
        fields = (
            (requirement.duties, role.duties),
            (requirement.data, role.data),
            (requirement.knowledge, role.knowledge),
            (requirement.skills, role.skills),
            (requirement.capabilities, role.capabilities),
            (requirement.runtimes, role.runtimes),
        )
        if any(
            not set(required).issubset(set(available)) for required, available in fields
        ):
            return None
        score = sum(len(required) for required, _ in fields)
        return CandidateScore(
            candidate.version.definition_id,
            candidate.version.version_id,
            candidate.version.definition_digest,
            score,
        )

    @staticmethod
    def _decision(
        requirement: RoleRequirement,
        snapshot: EffectiveDefinitionCatalogSnapshot,
        outcome: MatchOutcome,
        selected: CandidateScore | None,
        ties: tuple[CandidateScore, ...],
        missing: tuple[str, ...],
        reasons: tuple[str, ...],
    ) -> RoleMatchDecision:
        if len(reasons) > MAX_REASONS:
            raise _fail("REASON_LIMIT_EXCEEDED")
        for reason in reasons:
            _identifier(reason)
        payload = {
            "requirementId": requirement.requirement_id,
            "snapshotId": snapshot.snapshot_id,
            "outcome": outcome,
            "selected": selected,
            "ties": ties,
            "missing": missing,
            "reasons": reasons,
        }
        decision_id = canonical_digest(payload, domain="role-match-decision-v1")
        return RoleMatchDecision(
            decision_id=decision_id,
            requirement_id=requirement.requirement_id,
            outcome=outcome,
            snapshot_id=snapshot.snapshot_id,
            selected_definition_id=None if selected is None else selected.definition_id,
            selected_version_id=None if selected is None else selected.version_id,
            selected_definition_digest=(
                None if selected is None else selected.definition_digest
            ),
            tied_candidates=ties,
            missing_requirements=missing,
            reason_codes=reasons,
        )
