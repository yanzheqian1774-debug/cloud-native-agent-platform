"""Focused Package 3 Runtime Requirement and Native placement tests."""

from dataclasses import replace
from pathlib import Path

import pytest
from agent_console.matching import MatchOutcome, RoleMatchDecision
from agent_console.planning import (
    CanonicalWorkflowRevision,
    IntentRevision,
    PlanningState,
    TaskRequirement,
)
from agent_console.runtime_placement import (
    CONTRACT_VERSION,
    MAX_BINDINGS,
    MAX_EVALUATIONS,
    MAX_SERIALIZED_REQUEST_BYTES,
    DeclaredNativeTarget,
    MatchedDefinitionBinding,
    NativePlacementEvaluator,
    PlacementAuthorization,
    PlacementError,
    PlacementOutcome,
    TargetState,
    derive_runtime_requirement,
    validate_binding_count,
    validate_evaluation_count,
    validate_reason_count,
    validate_serialized_request_size,
)
from agent_runtime.providers.native.compatibility import (
    PROVIDER_PACKAGE,
    RUNTIME_TARGET,
)
from agent_runtime.providers.native.models import (
    ProviderPackageIdentity,
    RuntimeTargetIdentity,
)


def task(index: int) -> TaskRequirement:
    return TaskRequirement(
        task_requirement_id=f"task-{index}",
        future_task_id=f"future-task-{index}",
        intent_revision_id="intent-r1",
        task_type="ANALYZE",
        business_purpose="Analyze quality",
        inputs=("quality-data",),
        outputs=("quality-result",),
        dependencies=(),
        constraints=(),
        acceptance_conditions=("validated",),
        risk_classification="LOW",
        approval_classification="HUMAN",
        unresolved_requirements=(),
        canonical_ordinal=index,
    )


def revision(task_count: int = 1) -> CanonicalWorkflowRevision:
    tasks = tuple(task(index) for index in range(task_count))
    intent = IntentRevision(
        intent_id="intent",
        intent_revision_id="intent-r1",
        revision=1,
        predecessor_revision_id=None,
        schema_version="planning.v1",
        policy_version="supplier-quality.v1",
        source_question_id="question-1",
        objective="Analyze quality",
        constraints=(),
        success_criteria=("validated",),
        canonical_digest="b" * 64,
    )
    return CanonicalWorkflowRevision(
        canonical_workflow_revision_id="canonical-workflow-r1",
        revision=1,
        predecessor_revision_id=None,
        tenant_id="tenant-a",
        security_domain="quality",
        approved_candidate_digest="a" * 64,
        approval_id="approval-1",
        policy_version="supplier-quality.v1",
        intent_revision=intent,
        tasks=tasks,
        ordered_task_ids=tuple(item.task_requirement_id for item in tasks),
        limitations=(),
        matching_eligible=True,
    )


def decision(index: int, *, outcome: MatchOutcome = MatchOutcome.MATCHED):
    selected = outcome is MatchOutcome.MATCHED
    return RoleMatchDecision(
        decision_id=f"match-{index}",
        requirement_id=f"role-{index}",
        outcome=outcome,
        snapshot_id="snapshot-1",
        selected_definition_id=f"definition-{index}" if selected else None,
        selected_version_id="v1" if selected else None,
        selected_definition_digest="c" * 64 if selected else None,
        tied_candidates=(),
        missing_requirements=() if selected else (f"role-{index}",),
        reason_codes=("MATCHED",) if selected else ("ROLE_GAP",),
    )


def bindings(task_count: int = 1):
    return tuple(
        MatchedDefinitionBinding(f"task-{index}", decision(index))
        for index in range(task_count)
    )


def requirement(task_count: int = 1):
    return derive_runtime_requirement(
        revision(task_count),
        bindings(task_count),
        required_capabilities=("quality.read",),
        required_providers=("native-provider",),
        required_permissions=("runtime.place",),
    )


def authorization(**overrides):
    values = {
        "authorization_reference": "placement-auth-1",
        "tenant_id": "tenant-a",
        "security_domain": "quality",
        "permission_eligible": True,
        "capability_eligible": True,
        "provider_eligible": True,
    }
    values.update(overrides)
    return PlacementAuthorization(**values)


def candidate(index: int = 0, **overrides):
    values = {
        "declaration_id": f"native-target-{index:03d}",
        "tenant_id": "tenant-a",
        "security_domain": "quality",
        "target": RUNTIME_TARGET,
        "provider_package": PROVIDER_PACKAGE,
        "core_version": "0.1.0",
        "state": TargetState.AVAILABLE,
    }
    values.update(overrides)
    return DeclaredNativeTarget(**values)


def place(*, auth=None, candidates=None, runtime_requirement=None):
    return NativePlacementEvaluator().place(
        runtime_requirement or requirement(),
        auth or authorization(),
        (candidate(),) if candidates is None else candidates,
    )


def test_requirement_is_immutable_digest_bound_and_exactly_scoped() -> None:
    value = requirement()
    assert value.contract_version == CONTRACT_VERSION
    assert value.canonical_workflow_revision_id == "canonical-workflow-r1"
    assert value.approved_workflow_digest == "a" * 64
    assert value.tenant_id == "tenant-a"
    assert value.security_domain == "quality"
    assert value.native_target_name == RUNTIME_TARGET.name
    assert value.native_target_version == RUNTIME_TARGET.exact_version
    assert value.native_target_profile == RUNTIME_TARGET.profile
    assert value.requirement_id.endswith(value.canonical_digest)
    with pytest.raises(AttributeError):
        value.tenant_id = "tenant-b"


@pytest.mark.parametrize(
    ("changed", "reason"),
    [
        ({"lifecycle": PlanningState.APPROVED}, "APPROVED_CANONICAL_WORKFLOW_REQUIRED"),
        ({"matching_eligible": False}, "APPROVED_CANONICAL_WORKFLOW_REQUIRED"),
        ({"approved_candidate_digest": "x" * 64}, "INVALID_APPROVED_WORKFLOW_DIGEST"),
    ],
)
def test_only_exact_approved_workflow_is_consumed(changed, reason) -> None:
    with pytest.raises(PlacementError, match=reason):
        derive_runtime_requirement(
            replace(revision(), **changed),
            bindings(),
            required_capabilities=("quality.read",),
            required_providers=("native-provider",),
            required_permissions=("runtime.place",),
        )


def test_match_decisions_are_complete_advisory_inputs_not_authorization() -> None:
    with pytest.raises(PlacementError, match="INCOMPLETE_OR_GAPPED_MATCH"):
        derive_runtime_requirement(
            revision(),
            (
                MatchedDefinitionBinding(
                    "task-0", decision(0, outcome=MatchOutcome.ROLE_GAP)
                ),
            ),
            required_capabilities=("quality.read",),
            required_providers=("native-provider",),
            required_permissions=("runtime.place",),
        )
    escalated = replace(decision(0), advisory_only=False, execution_authorized=True)
    with pytest.raises(PlacementError, match="MATCH_AUTHORITY_ESCALATION_REJECTED"):
        derive_runtime_requirement(
            revision(),
            (MatchedDefinitionBinding("task-0", escalated),),
            required_capabilities=("quality.read",),
            required_providers=("native-provider",),
            required_permissions=("runtime.place",),
        )


def test_requirement_and_decision_are_deterministic_under_permutation() -> None:
    first = derive_runtime_requirement(
        revision(2),
        bindings(2),
        required_capabilities=("quality.write", "quality.read"),
        required_providers=("native-provider",),
        required_permissions=("runtime.execute", "runtime.place"),
    )
    second = derive_runtime_requirement(
        revision(2),
        tuple(reversed(bindings(2))),
        required_capabilities=("quality.read", "quality.write"),
        required_providers=("native-provider",),
        required_permissions=("runtime.place", "runtime.execute"),
    )
    assert first == second
    candidates = (
        candidate(1, state=TargetState.UNAVAILABLE),
        candidate(0),
    )
    evaluator = NativePlacementEvaluator()
    assert evaluator.place(first, authorization(), candidates) == evaluator.place(
        first, authorization(), tuple(reversed(candidates))
    )


def test_exact_native_target_places_and_emits_only_inert_handoff() -> None:
    result = place()
    assert result.outcome is PlacementOutcome.PLACED
    assert result.selected_target == RUNTIME_TARGET
    assert result.handoff is not None
    assert result.handoff.selected_target == RUNTIME_TARGET
    assert result.reason_codes == ("NATIVE_TARGET_PLACED",)
    assert (
        result.provider_call_count,
        result.runtime_call_count,
        result.gateway_call_count,
        result.execution_coordinator_call_count,
    ) == (0, 0, 0, 0)


@pytest.mark.parametrize(
    ("candidates", "reason"),
    [
        ((), "NATIVE_TARGET_MISSING"),
        ((object(),), "MALFORMED_TARGET_STATE"),
        ((candidate(state=TargetState.STALE),), "NATIVE_TARGET_STALE"),
        ((candidate(state=TargetState.UNKNOWN),), "NATIVE_TARGET_UNKNOWN"),
        ((candidate(state=TargetState.UNAVAILABLE),), "NATIVE_TARGET_UNAVAILABLE"),
        (
            (candidate(target=RuntimeTargetIdentity("other", "1", "external")),),
            "RUNTIME_IDENTITY_UNSUPPORTED",
        ),
        (
            (candidate(target=replace(RUNTIME_TARGET, exact_version="0.1.1")),),
            "RUNTIME_VERSION_UNSUPPORTED",
        ),
        (
            (candidate(target=replace(RUNTIME_TARGET, profile="other")),),
            "RUNTIME_PROFILE_UNSUPPORTED",
        ),
        (
            (
                candidate(
                    provider_package=ProviderPackageIdentity("other", "1", "runtime")
                ),
            ),
            "PROVIDER_PACKAGE_MISMATCH",
        ),
    ],
)
def test_missing_malformed_stale_unavailable_and_incompatible_fail_closed(
    candidates, reason
) -> None:
    result = place(candidates=candidates)
    assert result.outcome is PlacementOutcome.BLOCKED
    assert result.selected_target is None
    assert result.handoff is None
    assert result.reason_codes == (reason,)


def test_external_family_cannot_be_masked_by_available_native_target() -> None:
    external = candidate(1, target=RuntimeTargetIdentity("openclaw", "1", "external"))
    result = place(candidates=(candidate(0), external))
    assert result.outcome is PlacementOutcome.BLOCKED
    assert result.reason_codes == ("RUNTIME_IDENTITY_UNSUPPORTED",)
    assert result.evaluation_count == 0


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"tenant_id": "tenant-b"}, "TENANT_SCOPE_MISMATCH"),
        ({"security_domain": "finance"}, "SECURITY_DOMAIN_SCOPE_MISMATCH"),
        ({"permission_eligible": False}, "PERMISSION_NOT_ELIGIBLE"),
        ({"capability_eligible": False}, "CAPABILITY_NOT_ELIGIBLE"),
        ({"provider_eligible": False}, "PROVIDER_NOT_ELIGIBLE"),
    ],
)
def test_authorization_and_scope_fail_before_target_evaluation(
    overrides, reason
) -> None:
    result = place(auth=authorization(**overrides), candidates=(object(),))
    assert result.reason_codes == (reason,)
    assert result.evaluation_count == 0
    assert result.provider_call_count == result.runtime_call_count == 0


def test_target_scope_mismatch_fails_closed() -> None:
    assert place(candidates=(candidate(tenant_id="tenant-b"),)).reason_codes == (
        "TENANT_SCOPE_MISMATCH",
    )
    assert place(candidates=(candidate(security_domain="finance"),)).reason_codes == (
        "SECURITY_DOMAIN_SCOPE_MISMATCH",
    )


def test_replay_is_exact_and_substitution_is_rejected() -> None:
    first = place()
    assert first == place()
    substituted = replace(requirement(), tenant_id="tenant-b")
    with pytest.raises(PlacementError, match="RUNTIME_REQUIREMENT_DIGEST_MISMATCH"):
        place(runtime_requirement=substituted)


def test_task_limit_accepts_32_and_rejects_33() -> None:
    assert len(requirement(32).task_definition_bindings) == 32
    with pytest.raises(PlacementError, match="TASK_LIMIT_EXCEEDED"):
        requirement(33)


def test_per_task_requirement_limit_accepts_32_and_rejects_33() -> None:
    accepted = tuple(
        MatchedDefinitionBinding("task-0", decision(index)) for index in range(32)
    )
    assert (
        len(
            derive_runtime_requirement(
                revision(),
                accepted,
                required_capabilities=("quality.read",),
                required_providers=("native-provider",),
                required_permissions=("runtime.place",),
            ).task_definition_bindings
        )
        == 32
    )
    with pytest.raises(PlacementError, match="REQUIREMENT_LIMIT_EXCEEDED"):
        derive_runtime_requirement(
            revision(),
            (*accepted, MatchedDefinitionBinding("task-0", decision(32))),
            required_capabilities=("quality.read",),
            required_providers=("native-provider",),
            required_permissions=("runtime.place",),
        )


@pytest.mark.parametrize(
    ("validator", "maximum", "reason"),
    [
        (validate_binding_count, MAX_BINDINGS, "BINDING_LIMIT_EXCEEDED"),
        (validate_evaluation_count, MAX_EVALUATIONS, "EVALUATION_LIMIT_EXCEEDED"),
        (validate_reason_count, 32, "REASON_LIMIT_EXCEEDED"),
        (
            validate_serialized_request_size,
            MAX_SERIALIZED_REQUEST_BYTES,
            "PLACEMENT_REQUEST_PAYLOAD_LIMIT_EXCEEDED",
        ),
    ],
)
def test_numeric_ceilings_accept_maximum_and_reject_plus_one(
    validator, maximum, reason
) -> None:
    validator(maximum)
    with pytest.raises(PlacementError, match=reason):
        validator(maximum + 1)


def test_candidate_limit_accepts_64_and_rejects_65() -> None:
    unavailable = tuple(
        candidate(index, state=TargetState.UNAVAILABLE) for index in range(64)
    )
    result = place(candidates=unavailable)
    assert result.evaluation_count == 64
    with pytest.raises(PlacementError, match="CANDIDATE_LIMIT_EXCEEDED"):
        place(candidates=(*unavailable, candidate(64)))


def test_identifier_and_semantic_limits_accept_maximum_and_reject_plus_one() -> None:
    accepted = replace(revision(), tenant_id="t" * 200)
    accepted_bindings = (
        MatchedDefinitionBinding(
            "task-0", replace(decision(0), requirement_id="r" * 200)
        ),
    )
    value = derive_runtime_requirement(
        accepted,
        accepted_bindings,
        required_capabilities=("c" * 500,),
        required_providers=("native-provider",),
        required_permissions=("runtime.place",),
    )
    assert len(value.tenant_id) == 200
    with pytest.raises(PlacementError, match="IDENTIFIER_LIMIT_EXCEEDED"):
        derive_runtime_requirement(
            replace(revision(), tenant_id="t" * 201),
            bindings(),
            required_capabilities=("quality.read",),
            required_providers=("native-provider",),
            required_permissions=("runtime.place",),
        )
    with pytest.raises(PlacementError, match="SEMANTIC_TEXT_LIMIT_EXCEEDED"):
        derive_runtime_requirement(
            revision(),
            bindings(),
            required_capabilities=("c" * 501,),
            required_providers=("native-provider",),
            required_permissions=("runtime.place",),
        )


def test_package_four_and_side_effecting_boundaries_are_absent() -> None:
    source = Path(__file__).parents[1] / "src/agent_console/runtime_placement.py"
    text = source.read_text(encoding="utf-8")
    for prohibited in (
        "knowledge_retrieval",
        "NativeRuntimeProvider",
        "TaskExecutionCoordinator",
        "CapabilityGateway",
        "kubernetes",
    ):
        assert prohibited not in text
