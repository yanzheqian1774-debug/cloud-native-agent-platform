"""Internal immutable Runtime Requirement and bounded Native placement.

This module is an in-memory decision boundary.  It does not invoke a Provider,
Runtime, gateway, execution coordinator, Kubernetes API, or persistence layer.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from enum import StrEnum

from agent_runtime.providers.native.compatibility import (
    RUNTIME_TARGET,
    validate_compatibility,
)
from agent_runtime.providers.native.models import (
    CompatibilityMode,
    CompatibilityRequest,
    ProviderPackageIdentity,
    RuntimeTargetIdentity,
)

from agent_console.definition_authority import canonical_digest, canonical_json
from agent_console.matching import MatchOutcome, RoleMatchDecision
from agent_console.planning import CanonicalWorkflowRevision, PlanningState

CONTRACT_VERSION = "runtime-requirement.v1"
DECISION_VERSION = "native-placement-decision.v1"
MAX_TASKS = 32
MAX_REQUIREMENTS_PER_TASK = 32
MAX_BINDINGS = 1_024
MAX_CANDIDATES = 64
MAX_EVALUATIONS = 2_048
MAX_REASONS = 32
MAX_SERIALIZED_REQUEST_BYTES = 32 * 1024
IDENTIFIER_LIMIT = 200
SEMANTIC_TEXT_LIMIT = 500
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+-]{0,199}")
_DIGEST = re.compile(r"[0-9a-f]{64}")


class PlacementError(ValueError):
    """Stable fail-closed request error."""


class TargetState(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class PlacementOutcome(StrEnum):
    PLACED = "PLACED"
    BLOCKED = "BLOCKED"


def _fail(code: str) -> PlacementError:
    return PlacementError(code)


def _identifier(value: object, code: str = "MALFORMED_PLACEMENT_REQUEST") -> str:
    if not isinstance(value, str):
        raise _fail(code)
    normalized = unicodedata.normalize("NFC", value)
    if len(normalized) > IDENTIFIER_LIMIT:
        raise _fail("IDENTIFIER_LIMIT_EXCEEDED")
    if _IDENTIFIER.fullmatch(normalized) is None:
        raise _fail(code)
    return normalized


def _semantic_set(value: object, code: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise _fail(code)
    normalized = []
    for item in value:
        if not isinstance(item, str):
            raise _fail(code)
        text = " ".join(unicodedata.normalize("NFC", item).split())
        if not text:
            raise _fail(code)
        if len(text) > SEMANTIC_TEXT_LIMIT:
            raise _fail("SEMANTIC_TEXT_LIMIT_EXCEEDED")
        normalized.append(text)
    if len(set(normalized)) != len(normalized):
        raise _fail("AMBIGUOUS_PLACEMENT_INPUT")
    return tuple(sorted(normalized))


def validate_binding_count(count: int) -> None:
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise _fail("MALFORMED_PLACEMENT_REQUEST")
    if count > MAX_BINDINGS:
        raise _fail("BINDING_LIMIT_EXCEEDED")


def validate_evaluation_count(count: int) -> None:
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise _fail("MALFORMED_PLACEMENT_REQUEST")
    if count > MAX_EVALUATIONS:
        raise _fail("EVALUATION_LIMIT_EXCEEDED")


def validate_serialized_request_size(size: int) -> None:
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise _fail("MALFORMED_PLACEMENT_REQUEST")
    if size > MAX_SERIALIZED_REQUEST_BYTES:
        raise _fail("PLACEMENT_REQUEST_PAYLOAD_LIMIT_EXCEEDED")


def validate_reason_count(count: int) -> None:
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise _fail("MALFORMED_PLACEMENT_REQUEST")
    if count > MAX_REASONS:
        raise _fail("REASON_LIMIT_EXCEEDED")


@dataclass(frozen=True, slots=True)
class MatchedDefinitionBinding:
    task_requirement_id: str
    match_decision: RoleMatchDecision


@dataclass(frozen=True, slots=True)
class PlacementAuthorization:
    authorization_reference: str
    tenant_id: str
    security_domain: str
    permission_eligible: bool
    capability_eligible: bool
    provider_eligible: bool


@dataclass(frozen=True, slots=True)
class DeclaredNativeTarget:
    declaration_id: str
    tenant_id: str
    security_domain: str
    target: RuntimeTargetIdentity
    provider_package: ProviderPackageIdentity
    core_version: str
    state: TargetState


@dataclass(frozen=True, slots=True)
class RuntimeRequirement:
    requirement_id: str
    contract_version: str
    canonical_workflow_revision_id: str
    approved_workflow_digest: str
    tenant_id: str
    security_domain: str
    task_definition_bindings: tuple[tuple[str, str, str, str, str], ...]
    native_target_name: str
    native_target_version: str
    native_target_profile: str
    required_capabilities: tuple[str, ...]
    required_providers: tuple[str, ...]
    required_permissions: tuple[str, ...]
    canonical_digest: str


@dataclass(frozen=True, slots=True)
class NativePlacementHandoff:
    requirement_id: str
    decision_id: str
    selected_target: RuntimeTargetIdentity


@dataclass(frozen=True, slots=True)
class NativePlacementDecision:
    decision_id: str
    decision_version: str
    decision_digest: str
    requirement_id: str
    requirement_digest: str
    outcome: PlacementOutcome
    selected_target: RuntimeTargetIdentity | None
    authorization_reference: str
    reason_codes: tuple[str, ...]
    evaluation_count: int
    provider_call_count: int = 0
    runtime_call_count: int = 0
    gateway_call_count: int = 0
    execution_coordinator_call_count: int = 0
    handoff: NativePlacementHandoff | None = None


def derive_runtime_requirement(
    revision: CanonicalWorkflowRevision,
    bindings: tuple[MatchedDefinitionBinding, ...],
    *,
    required_capabilities: tuple[str, ...],
    required_providers: tuple[str, ...],
    required_permissions: tuple[str, ...],
) -> RuntimeRequirement:
    """Derive one canonical requirement from approved and advisory-only inputs."""
    if not isinstance(revision, CanonicalWorkflowRevision):
        raise _fail("CANONICAL_WORKFLOW_REQUIRED")
    if (
        revision.lifecycle is not PlanningState.CANONICALIZED
        or not revision.matching_eligible
        or not revision.approval_id
    ):
        raise _fail("APPROVED_CANONICAL_WORKFLOW_REQUIRED")
    _identifier(revision.canonical_workflow_revision_id)
    _identifier(revision.tenant_id)
    _identifier(revision.security_domain)
    if _DIGEST.fullmatch(revision.approved_candidate_digest) is None:
        raise _fail("INVALID_APPROVED_WORKFLOW_DIGEST")
    if not revision.tasks or len(revision.tasks) > MAX_TASKS:
        raise _fail("TASK_LIMIT_EXCEEDED")
    task_ids = tuple(task.task_requirement_id for task in revision.tasks)
    if len(set(task_ids)) != len(task_ids):
        raise _fail("DUPLICATE_TASK_REQUIREMENT")
    if not isinstance(bindings, tuple):
        raise _fail("MALFORMED_MATCH_BINDING")
    validate_binding_count(len(bindings))
    counts = {task_id: 0 for task_id in task_ids}
    canonical_bindings = []
    seen_requirements = set()
    for binding in bindings:
        if not isinstance(binding, MatchedDefinitionBinding):
            raise _fail("MALFORMED_MATCH_BINDING")
        task_id = _identifier(binding.task_requirement_id)
        if task_id not in counts:
            raise _fail("MATCH_TASK_BINDING_MISMATCH")
        decision = binding.match_decision
        if not isinstance(decision, RoleMatchDecision):
            raise _fail("MALFORMED_MATCH_DECISION")
        if decision.requirement_id in seen_requirements:
            raise _fail("DUPLICATE_MATCH_DECISION")
        seen_requirements.add(decision.requirement_id)
        counts[task_id] += 1
        if counts[task_id] > MAX_REQUIREMENTS_PER_TASK:
            raise _fail("REQUIREMENT_LIMIT_EXCEEDED")
        if (
            decision.outcome is not MatchOutcome.MATCHED
            or decision.selected_definition_id is None
            or decision.selected_version_id is None
            or decision.selected_definition_digest is None
            or decision.missing_requirements
        ):
            raise _fail("INCOMPLETE_OR_GAPPED_MATCH")
        if not decision.advisory_only or decision.execution_authorized:
            raise _fail("MATCH_AUTHORITY_ESCALATION_REJECTED")
        if _DIGEST.fullmatch(decision.selected_definition_digest) is None:
            raise _fail("INVALID_DEFINITION_DIGEST")
        canonical_bindings.append(
            (
                task_id,
                _identifier(decision.requirement_id),
                _identifier(decision.selected_definition_id),
                _identifier(decision.selected_version_id),
                decision.selected_definition_digest,
            )
        )
    if any(count == 0 for count in counts.values()):
        raise _fail("INCOMPLETE_MATCH_DECISIONS")
    canonical_bindings = sorted(canonical_bindings)
    capabilities = _semantic_set(
        required_capabilities, "INVALID_CAPABILITY_REQUIREMENT"
    )
    providers = _semantic_set(required_providers, "INVALID_PROVIDER_REQUIREMENT")
    permissions = _semantic_set(required_permissions, "INVALID_PERMISSION_REQUIREMENT")
    if not capabilities or not providers or not permissions:
        raise _fail("ELIGIBILITY_REQUIREMENTS_REQUIRED")
    payload = {
        "contractVersion": CONTRACT_VERSION,
        "workflowRevisionId": revision.canonical_workflow_revision_id,
        "workflowDigest": revision.approved_candidate_digest,
        "tenantId": revision.tenant_id,
        "securityDomain": revision.security_domain,
        "taskDefinitionBindings": canonical_bindings,
        "nativeTarget": asdict(RUNTIME_TARGET),
        "requiredCapabilities": capabilities,
        "requiredProviders": providers,
        "requiredPermissions": permissions,
    }
    validate_serialized_request_size(len(canonical_json(payload).encode("utf-8")))
    digest = canonical_digest(payload, domain=CONTRACT_VERSION)
    return RuntimeRequirement(
        requirement_id=f"runtime-requirement:{digest}",
        contract_version=CONTRACT_VERSION,
        canonical_workflow_revision_id=revision.canonical_workflow_revision_id,
        approved_workflow_digest=revision.approved_candidate_digest,
        tenant_id=revision.tenant_id,
        security_domain=revision.security_domain,
        task_definition_bindings=tuple(canonical_bindings),
        native_target_name=RUNTIME_TARGET.name,
        native_target_version=RUNTIME_TARGET.exact_version or "",
        native_target_profile=RUNTIME_TARGET.profile,
        required_capabilities=capabilities,
        required_providers=providers,
        required_permissions=permissions,
        canonical_digest=digest,
    )


class NativePlacementEvaluator:
    """Authorization-first selector over a read-only declared-target snapshot."""

    def place(
        self,
        requirement: RuntimeRequirement,
        authorization: PlacementAuthorization,
        candidates: tuple[DeclaredNativeTarget, ...],
    ) -> NativePlacementDecision:
        if not isinstance(requirement, RuntimeRequirement):
            raise _fail("RUNTIME_REQUIREMENT_REQUIRED")
        self._validate_requirement(requirement)
        if not isinstance(authorization, PlacementAuthorization):
            raise _fail("PLACEMENT_AUTHORIZATION_REQUIRED")
        reference = _identifier(authorization.authorization_reference)
        if authorization.tenant_id != requirement.tenant_id:
            return self._blocked(requirement, reference, "TENANT_SCOPE_MISMATCH", 0)
        if authorization.security_domain != requirement.security_domain:
            return self._blocked(
                requirement, reference, "SECURITY_DOMAIN_SCOPE_MISMATCH", 0
            )
        for eligible, reason in (
            (authorization.permission_eligible, "PERMISSION_NOT_ELIGIBLE"),
            (authorization.capability_eligible, "CAPABILITY_NOT_ELIGIBLE"),
            (authorization.provider_eligible, "PROVIDER_NOT_ELIGIBLE"),
        ):
            if eligible is not True:
                return self._blocked(requirement, reference, reason, 0)
        if not isinstance(candidates, tuple):
            return self._blocked(requirement, reference, "MALFORMED_TARGET_STATE", 0)
        if len(candidates) > MAX_CANDIDATES:
            raise _fail("CANDIDATE_LIMIT_EXCEEDED")
        ordered = []
        for candidate in candidates:
            if not isinstance(candidate, DeclaredNativeTarget):
                return self._blocked(
                    requirement, reference, "MALFORMED_TARGET_STATE", len(ordered)
                )
            try:
                _identifier(candidate.declaration_id)
            except PlacementError:
                return self._blocked(
                    requirement, reference, "MALFORMED_TARGET_STATE", len(ordered)
                )
            ordered.append(candidate)
        ordered.sort(key=lambda item: item.declaration_id)
        if len({item.declaration_id for item in ordered}) != len(ordered):
            return self._blocked(requirement, reference, "CONFLICTING_TARGET_STATE", 0)
        if not ordered:
            return self._blocked(requirement, reference, "NATIVE_TARGET_MISSING", 0)
        validate_evaluation_count(len(ordered))
        for candidate in ordered:
            if not isinstance(candidate.target, RuntimeTargetIdentity):
                return self._blocked(
                    requirement, reference, "MALFORMED_TARGET_STATE", 0
                )
            if candidate.target.name != RUNTIME_TARGET.name:
                return self._blocked(
                    requirement, reference, "RUNTIME_IDENTITY_UNSUPPORTED", 0
                )
        failures = []
        for count, candidate in enumerate(ordered, 1):
            reason = self._candidate_failure(requirement, candidate)
            if reason is None:
                return self._placed(requirement, reference, candidate.target, count)
            failures.append(reason)
        return self._blocked(
            requirement,
            reference,
            sorted(failures)[0] if failures else "NATIVE_TARGET_UNAVAILABLE",
            len(ordered),
        )

    @staticmethod
    def _validate_requirement(requirement: RuntimeRequirement) -> None:
        payload = {
            "contractVersion": requirement.contract_version,
            "workflowRevisionId": requirement.canonical_workflow_revision_id,
            "workflowDigest": requirement.approved_workflow_digest,
            "tenantId": requirement.tenant_id,
            "securityDomain": requirement.security_domain,
            "taskDefinitionBindings": requirement.task_definition_bindings,
            "nativeTarget": {
                "name": requirement.native_target_name,
                "exact_version": requirement.native_target_version,
                "profile": requirement.native_target_profile,
            },
            "requiredCapabilities": requirement.required_capabilities,
            "requiredProviders": requirement.required_providers,
            "requiredPermissions": requirement.required_permissions,
        }
        expected = canonical_digest(payload, domain=CONTRACT_VERSION)
        if (
            requirement.contract_version != CONTRACT_VERSION
            or requirement.canonical_digest != expected
            or requirement.requirement_id != f"runtime-requirement:{expected}"
        ):
            raise _fail("RUNTIME_REQUIREMENT_DIGEST_MISMATCH")

    @staticmethod
    def _candidate_failure(
        requirement: RuntimeRequirement, candidate: DeclaredNativeTarget
    ) -> str | None:
        if candidate.tenant_id != requirement.tenant_id:
            return "TENANT_SCOPE_MISMATCH"
        if candidate.security_domain != requirement.security_domain:
            return "SECURITY_DOMAIN_SCOPE_MISMATCH"
        if not isinstance(candidate.state, TargetState):
            return "MALFORMED_TARGET_STATE"
        if candidate.state is TargetState.STALE:
            return "NATIVE_TARGET_STALE"
        if candidate.state is TargetState.UNKNOWN:
            return "NATIVE_TARGET_UNKNOWN"
        if candidate.state is not TargetState.AVAILABLE:
            return "NATIVE_TARGET_UNAVAILABLE"
        decision = validate_compatibility(
            CompatibilityRequest(
                provider_package=candidate.provider_package,
                runtime_target=candidate.target,
                core_version=candidate.core_version,
                platform_execution_identity=requirement.requirement_id,
            )
        )
        if (
            not decision.accepted
            or decision.mode is not CompatibilityMode.EXACT_MATCH
            or decision.effective_runtime != RUNTIME_TARGET
        ):
            return decision.reason.value
        return None

    def _placed(
        self,
        requirement: RuntimeRequirement,
        reference: str,
        target: RuntimeTargetIdentity,
        evaluations: int,
    ) -> NativePlacementDecision:
        return self._decision(
            requirement,
            reference,
            PlacementOutcome.PLACED,
            target,
            ("NATIVE_TARGET_PLACED",),
            evaluations,
        )

    def _blocked(
        self,
        requirement: RuntimeRequirement,
        reference: str,
        reason: str,
        evaluations: int,
    ) -> NativePlacementDecision:
        return self._decision(
            requirement,
            reference,
            PlacementOutcome.BLOCKED,
            None,
            (reason,),
            evaluations,
        )

    @staticmethod
    def _decision(
        requirement: RuntimeRequirement,
        reference: str,
        outcome: PlacementOutcome,
        target: RuntimeTargetIdentity | None,
        reasons: tuple[str, ...],
        evaluations: int,
    ) -> NativePlacementDecision:
        validate_reason_count(len(reasons))
        validate_evaluation_count(evaluations)
        payload = {
            "decisionVersion": DECISION_VERSION,
            "requirementId": requirement.requirement_id,
            "requirementDigest": requirement.canonical_digest,
            "outcome": outcome,
            "selectedTarget": target,
            "authorizationReference": reference,
            "reasonCodes": reasons,
            "evaluationCount": evaluations,
            "providerCallCount": 0,
            "runtimeCallCount": 0,
            "gatewayCallCount": 0,
            "executionCoordinatorCallCount": 0,
        }
        digest = canonical_digest(payload, domain=DECISION_VERSION)
        decision_id = f"native-placement-decision:{digest}"
        handoff = (
            None
            if target is None
            else NativePlacementHandoff(requirement.requirement_id, decision_id, target)
        )
        return NativePlacementDecision(
            decision_id=decision_id,
            decision_version=DECISION_VERSION,
            decision_digest=digest,
            requirement_id=requirement.requirement_id,
            requirement_digest=requirement.canonical_digest,
            outcome=outcome,
            selected_target=target,
            authorization_reference=reference,
            reason_codes=reasons,
            evaluation_count=evaluations,
            handoff=handoff,
        )
