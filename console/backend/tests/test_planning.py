"""Focused contract tests for bounded canonical planning."""

import json
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

import pytest
from agent_console.planning import (
    DEPENDENCY_LIMIT,
    POLICY_VERSION,
    CanonicalWorkflowRevision,
    PlanningDecision,
    PlanningEngine,
    PlanningError,
    PlanningState,
    ProductSemanticCorrection,
    create_business_question,
)
from agent_console.planning_generator import SupplierQualityReferenceGenerator

NOW = datetime(2026, 8, 28, 8, 0, tzinfo=UTC)


def question(*, tenant="tenant.acme", domain="quality.restricted"):
    return create_business_question(
        request_id="request.q-1042",
        tenant_id=tenant,
        security_domain=domain,
        principal="human.reviewer",
        locale="en-US",
        scenario_id="supplier-quality",
        question="Assess supplier defect trends for lot Q-1042",
        created_at=NOW,
        provenance="product.question",
    )


def raw_candidate():
    return deepcopy(SupplierQualityReferenceGenerator().generate(question()))


def approve(engine, result, *, replay="replay.q-1042.r1", **overrides):
    request = engine.request_approval(result)
    args = {
        "tenant_id": result.question.tenant_id,
        "security_domain": result.question.security_domain,
        "actor": "human.reviewer",
        "decision": PlanningDecision.APPROVE,
        "decided_at": NOW,
        "replay_identity": replay,
        "reason_code": "BOUNDED_PLAN_ACCEPTED",
    }
    args.update(overrides)
    return request, engine.decide(result, request, **args)


def task(task_id, dependencies=(), ordinal=0):
    return {
        "id": task_id,
        "type": "ANALYZE",
        "purpose": f"Analyze {task_id}",
        "inputs": [],
        "outputs": [f"output-{task_id}"],
        "dependencies": list(dependencies),
        "constraints": [],
        "acceptance_conditions": [f"{task_id} is reviewable"],
        "risk": "LOW",
        "approval": "HUMAN",
        "unresolved": [],
        "ordinal": ordinal,
    }


def test_canonicalization_digest_and_order_are_deterministic() -> None:
    generator = SupplierQualityReferenceGenerator()
    first = PlanningEngine().generate(question(), generator)
    second = PlanningEngine().generate(question(), generator)

    assert first.workflow_candidate == second.workflow_candidate
    assert first.validation == second.validation
    assert first.workflow_candidate is not None
    assert len(first.workflow_candidate.candidate_digest) == 64
    assert first.workflow_candidate.policy_version == POLICY_VERSION

    permuted = raw_candidate()
    permuted["tasks"] = list(reversed(permuted["tasks"]))
    permuted["constraints"] = list(reversed(permuted["constraints"]))
    permuted["success_criteria"] = list(reversed(permuted["success_criteria"]))
    for task_value in permuted["tasks"]:
        for field in (
            "inputs",
            "outputs",
            "dependencies",
            "constraints",
            "acceptance_conditions",
        ):
            task_value[field] = list(reversed(task_value[field]))
    replay = PlanningEngine().validate(question(), permuted, generator)
    assert replay.workflow_candidate is not None
    assert replay.workflow_candidate.candidate_digest == (
        first.workflow_candidate.candidate_digest
    )
    assert replay.workflow_candidate.tasks == first.workflow_candidate.tasks


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (lambda raw: raw.pop("objective"), "UNKNOWN_OR_MISSING_FIELD"),
        (lambda raw: raw.update({"unknown": "value"}), "UNKNOWN_OR_MISSING_FIELD"),
        (
            lambda raw: raw["tasks"].append(deepcopy(raw["tasks"][0])),
            "DUPLICATE_TASK_ID",
        ),
        (
            lambda raw: raw["tasks"][0].update(
                {"dependencies": [raw["tasks"][0]["id"]]}
            ),
            "SELF_DEPENDENCY",
        ),
        (
            lambda raw: raw["tasks"][0].update({"dependencies": ["missing"]}),
            "MISSING_DEPENDENCY",
        ),
        (
            lambda raw: raw["tasks"][0].update({"type": "INVOKE_PROVIDER"}),
            "UNSUPPORTED_TASK_TYPE",
        ),
        (
            lambda raw: raw["tasks"][0].update({"unresolved": ["unknown role"]}),
            "UNKNOWN_REQUIREMENT",
        ),
    ],
)
def test_invalid_incomplete_unknown_and_unsupported_candidates_fail_closed(
    mutation, reason
) -> None:
    raw = raw_candidate()
    mutation(raw)
    result = PlanningEngine().validate(
        question(), raw, SupplierQualityReferenceGenerator()
    )

    assert result.workflow_candidate is None
    assert result.validation.approval_eligible is False
    assert result.validation.issues[0].reason_code == reason
    assert result.validation.state in {
        PlanningState.INVALID,
        PlanningState.UNSUPPORTED,
        PlanningState.UNKNOWN,
    }
    with pytest.raises(PlanningError, match="CANDIDATE_NOT_APPROVAL_ELIGIBLE"):
        PlanningEngine().request_approval(result)


def test_cycles_are_rejected_without_dropping_edges() -> None:
    raw = raw_candidate()
    raw["tasks"][0]["dependencies"] = ["review-quality-plan"]
    result = PlanningEngine().validate(
        question(), raw, SupplierQualityReferenceGenerator()
    )
    assert result.workflow_candidate is None
    assert result.validation.issues[0].reason_code == "DEPENDENCY_CYCLE"


def dependency_candidate(edge_count):
    raw = raw_candidate()
    tasks = [task(f"task-{index:02}", ordinal=index) for index in range(32)]
    edges = 0
    for successor in range(1, len(tasks)):
        for predecessor in range(successor):
            if edges == edge_count:
                break
            tasks[successor]["dependencies"].append(f"task-{predecessor:02}")
            edges += 1
        if edges == edge_count:
            break
    raw["tasks"] = tasks
    assert edges == edge_count
    return raw


def serialized_candidate(target_size):
    raw = raw_candidate()
    padding_lists = [
        task_value[field]
        for task_value in raw["tasks"]
        for field in ("inputs", "constraints")
    ]
    counter = 0
    while len(json.dumps(raw, default=str)) < target_size - 700:
        destination = padding_lists[counter % len(padding_lists)]
        if len(destination) >= 32:
            counter += 1
            continue
        destination.append(f"pad-{counter:03}-" + "x" * 390)
        counter += 1
    destination = next(item for item in padding_lists if len(item) < 32)
    current = len(json.dumps(raw, default=str))
    probe = f"pad-{counter:03}-z"
    destination.append(probe)
    overhead = len(json.dumps(raw, default=str)) - current - len(probe)
    destination.pop()
    desired_length = target_size - 200 - current - overhead
    assert 1 <= desired_length <= 500
    destination.append("p" * desired_length)
    current = len(json.dumps(raw, default=str))
    difference = target_size - current
    objective = raw["objective"]
    assert difference >= 0 and len(objective) + difference <= 500
    raw["objective"] = objective + "x" * difference
    assert len(json.dumps(raw, default=str)) == target_size
    return raw


def test_dependency_ceiling_accepts_128_and_rejects_129() -> None:
    engine = PlanningEngine()
    accepted = engine.validate(
        question(),
        dependency_candidate(DEPENDENCY_LIMIT),
        SupplierQualityReferenceGenerator(),
    )
    rejected = engine.validate(
        question(),
        dependency_candidate(DEPENDENCY_LIMIT + 1),
        SupplierQualityReferenceGenerator(),
    )

    assert accepted.validation.approval_eligible is True
    assert rejected.validation.approval_eligible is False
    assert rejected.validation.issues[0].reason_code == "DEPENDENCY_LIMIT_EXCEEDED"


def test_task_ceiling_accepts_32_and_rejects_33_without_truncation() -> None:
    engine = PlanningEngine()
    accepted_raw = dependency_candidate(31)
    rejected_raw = deepcopy(accepted_raw)
    rejected_raw["tasks"].append(task("task-32", ordinal=32))

    accepted = engine.validate(
        question(), accepted_raw, SupplierQualityReferenceGenerator()
    )
    rejected = engine.validate(
        question(), rejected_raw, SupplierQualityReferenceGenerator()
    )
    assert accepted.workflow_candidate is not None
    assert len(accepted.workflow_candidate.tasks) == 32
    assert rejected.workflow_candidate is None
    assert rejected.validation.issues[0].reason_code == "INPUT_LIMIT_EXCEEDED"


def test_serialized_ceiling_accepts_32000_and_rejects_32001_without_truncation():
    engine = PlanningEngine()
    accepted = engine.validate(
        question(), serialized_candidate(32_000), SupplierQualityReferenceGenerator()
    )
    rejected = engine.validate(
        question(), serialized_candidate(32_001), SupplierQualityReferenceGenerator()
    )
    assert accepted.workflow_candidate is not None
    assert rejected.workflow_candidate is None
    assert rejected.validation.issues[0].reason_code == "INPUT_LIMIT_EXCEEDED"


def test_exact_approval_binding_replay_and_rejection_fail_closed() -> None:
    engine = PlanningEngine()
    result = engine.generate(question(), SupplierQualityReferenceGenerator())
    request, canonical = approve(engine, result)
    assert isinstance(canonical, CanonicalWorkflowRevision)
    assert canonical.matching_eligible is True
    assert canonical.lifecycle == PlanningState.CANONICALIZED
    assert (
        engine.decide(
            result,
            request,
            tenant_id=result.question.tenant_id,
            security_domain=result.question.security_domain,
            actor="human.reviewer",
            decision=PlanningDecision.APPROVE,
            decided_at=NOW,
            replay_identity="replay.q-1042.r1",
            reason_code="BOUNDED_PLAN_ACCEPTED",
        )
        == canonical
    )

    conflicts = (
        {"actor": "human.other"},
        {"decision": PlanningDecision.REJECT},
        {"decided_at": datetime(2026, 8, 29, tzinfo=UTC)},
        {"reason_code": "DIFFERENT_REASON"},
    )
    for conflict in conflicts:
        with pytest.raises(PlanningError, match="APPROVAL_REPLAY_MISMATCH"):
            approve(engine, result, **conflict)

    rejected_engine = PlanningEngine()
    rejected_result = rejected_engine.generate(
        question(), SupplierQualityReferenceGenerator()
    )
    _, rejected = approve(
        rejected_engine,
        rejected_result,
        decision=PlanningDecision.REJECT,
        replay="replay.q-1042.reject",
    )
    assert rejected is None


@pytest.mark.parametrize(
    ("tenant", "domain", "reason"),
    [
        ("tenant.other", "quality.restricted", "TENANT_SCOPE_MISMATCH"),
        ("tenant.acme", "quality.other", "SECURITY_DOMAIN_SCOPE_MISMATCH"),
    ],
)
def test_approval_is_tenant_and_security_domain_isolated(tenant, domain, reason):
    engine = PlanningEngine()
    result = engine.generate(question(), SupplierQualityReferenceGenerator())
    request = engine.request_approval(result)
    with pytest.raises(PlanningError, match=reason):
        engine.decide(
            result,
            request,
            tenant_id=tenant,
            security_domain=domain,
            actor="human.reviewer",
            decision=PlanningDecision.APPROVE,
            decided_at=NOW,
            replay_identity="replay.scope-mismatch",
            reason_code="BOUNDED_PLAN_ACCEPTED",
        )


def test_digest_policy_and_request_substitution_fail_closed() -> None:
    engine = PlanningEngine()
    result = engine.generate(question(), SupplierQualityReferenceGenerator())
    request = engine.request_approval(result)

    forged = deepcopy(request)
    object.__setattr__(forged, "candidate_digest", "0" * 64)
    with pytest.raises(PlanningError, match="INVALID_APPROVAL_REQUEST"):
        engine.decide(
            result,
            forged,
            tenant_id=result.question.tenant_id,
            security_domain=result.question.security_domain,
            actor="human.reviewer",
            decision=PlanningDecision.APPROVE,
            decided_at=NOW,
            replay_identity="replay.forged",
            reason_code="BOUNDED_PLAN_ACCEPTED",
        )

    for field in ("candidate_digest", "policy_version"):
        value = "0" * 64 if field == "candidate_digest" else "different.policy"
        substituted = replace(request, **{field: value})
        engine._requests[request.approval_request_id] = substituted
        with pytest.raises(PlanningError, match="APPROVAL_BINDING_MISMATCH"):
            engine.decide(
                result,
                substituted,
                tenant_id=result.question.tenant_id,
                security_domain=result.question.security_domain,
                actor="human.reviewer",
                decision=PlanningDecision.APPROVE,
                decided_at=NOW,
                replay_identity=f"replay.{field}",
                reason_code="BOUNDED_PLAN_ACCEPTED",
            )


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"actor": ""}, "INVALID_APPROVAL_ACTOR"),
        ({"decision": "APPROVE"}, "INVALID_APPROVAL_DECISION"),
        ({"decided_at": datetime(2026, 8, 28)}, "INVALID_APPROVAL_TIMESTAMP"),
        (
            {"decided_at": datetime(2026, 8, 28, tzinfo=timezone(timedelta(hours=8)))},
            "INVALID_APPROVAL_TIMESTAMP",
        ),
        ({"replay_identity": ""}, "INVALID_REPLAY_IDENTITY"),
    ],
)
def test_missing_or_malformed_approval_fields_fail_closed(override, reason):
    engine = PlanningEngine()
    result = engine.generate(question(), SupplierQualityReferenceGenerator())
    with pytest.raises(PlanningError, match=reason):
        approve(engine, result, **override)


def test_correction_creates_fresh_unapproved_successor_and_preserves_predecessor() -> (
    None
):
    engine = PlanningEngine()
    original_result = engine.generate(question(), SupplierQualityReferenceGenerator())
    _, predecessor = approve(engine, original_result)
    assert predecessor is not None
    predecessor_snapshot = deepcopy(predecessor)
    corrected_raw = raw_candidate()
    corrected_raw["objective"] = (
        "Assess and explain the bounded supplier quality question"
    )
    correction = ProductSemanticCorrection(
        correction_id="correction.q-1042.objective",
        tenant_id=predecessor.tenant_id,
        security_domain=predecessor.security_domain,
        principal="human.reviewer",
        predecessor_revision_id=predecessor.canonical_workflow_revision_id,
        predecessor_digest=predecessor.approved_candidate_digest,
        affected_element_id=predecessor.intent_revision.intent_revision_id,
        field="objective",
        before=predecessor.intent_revision.objective,
        after=corrected_raw["objective"],
        reason_code="OBJECTIVE_CLARIFIED",
    )

    successor_result = engine.corrected_successor(
        predecessor,
        correction,
        question(),
        corrected_raw,
        SupplierQualityReferenceGenerator(),
    )
    assert predecessor == predecessor_snapshot
    assert successor_result.workflow_candidate is not None
    assert successor_result.workflow_candidate.candidate_digest != (
        predecessor.approved_candidate_digest
    )
    assert successor_result.validation.approval_eligible is True
    successor_request = engine.request_approval(successor_result)
    wrong_predecessor = replace(
        predecessor,
        canonical_workflow_revision_id="canonical-workflow-revision:other",
    )
    with pytest.raises(PlanningError, match="SUCCESSOR_LINK_MISMATCH"):
        engine.decide(
            successor_result,
            successor_request,
            tenant_id=predecessor.tenant_id,
            security_domain=predecessor.security_domain,
            actor="human.reviewer",
            decision=PlanningDecision.APPROVE,
            decided_at=NOW,
            replay_identity="replay.wrong-predecessor",
            reason_code="BOUNDED_PLAN_ACCEPTED",
            predecessor=wrong_predecessor,
        )
    successor_request, successor = approve(
        engine,
        successor_result,
        replay="replay.q-1042.r2",
        predecessor=predecessor,
    )
    assert successor_request.candidate_digest != predecessor.approved_candidate_digest
    assert successor is not None
    assert (
        successor.predecessor_revision_id == predecessor.canonical_workflow_revision_id
    )
    assert engine.is_matching_eligible(successor) is True
    assert engine.is_matching_eligible(predecessor) is False
    superseded = engine.mark_superseded(predecessor, successor)
    assert superseded.matching_eligible is False
    assert superseded.lifecycle == PlanningState.SUPERSEDED
    assert predecessor == predecessor_snapshot


@pytest.mark.parametrize(
    ("tenant", "domain", "reason"),
    [
        ("tenant.other", "quality.restricted", "TENANT_SCOPE_MISMATCH"),
        ("tenant.acme", "quality.other", "SECURITY_DOMAIN_SCOPE_MISMATCH"),
    ],
)
def test_successor_access_is_tenant_and_security_domain_isolated(
    tenant, domain, reason
) -> None:
    engine = PlanningEngine()
    original = engine.generate(question(), SupplierQualityReferenceGenerator())
    _, predecessor = approve(engine, original)
    assert predecessor is not None
    correction = ProductSemanticCorrection(
        correction_id="correction.q-1042.objective",
        tenant_id=predecessor.tenant_id,
        security_domain=predecessor.security_domain,
        principal="human.reviewer",
        predecessor_revision_id=predecessor.canonical_workflow_revision_id,
        predecessor_digest=predecessor.approved_candidate_digest,
        affected_element_id=predecessor.intent_revision.intent_revision_id,
        field="objective",
        before=predecessor.intent_revision.objective,
        after="Changed objective",
        reason_code="OBJECTIVE_CLARIFIED",
    )
    with pytest.raises(PlanningError, match=reason):
        engine.corrected_successor(
            predecessor,
            correction,
            question(tenant=tenant, domain=domain),
            raw_candidate(),
            SupplierQualityReferenceGenerator(),
        )
