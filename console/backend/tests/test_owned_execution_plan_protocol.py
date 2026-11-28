"""Selection remains explicit even when retaining an already adopted tuple."""

from types import SimpleNamespace as NS

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.owned_business_policy import OwnedBusinessPolicy
from agent_console.owned_business_resource_adapter import OwnedResourceWork
from agent_console.owned_resource_assembly import (
    MODE,
    require_selection_rebinding,
    selection_work,
)
from agent_console.plan_suggestion_domain import (
    ConfirmedPlanRevision,
    ExactReference,
    FlexiblePlanSemantics,
)
from test_owned_business_policy import document
from test_planning_contracts import modern


def values():
    p = OwnedBusinessPolicy.model_validate(document())
    scope = p.scopes[0].model_copy(update={"trustedAssemblyAdoption": MODE})
    p = p.model_copy(update={"scopes": (scope,)})
    raw = modern()
    current = ExactReference(
        resource_id="employee:adopted", revision_id="r1", digest="b" * 64
    )
    for r in raw["requirements"]:
        if r["kind"] == "EMPLOYEE":
            r["selected"] = current.model_dump(mode="json")
    plan = ConfirmedPlanRevision(
        plan_id="plan:existing",
        version=3,
        source_proposal_id="plan:existing",
        source_proposal_revision=3,
        source_proposal_digest="c" * 64,
        predecessor_digest="d" * 64,
        semantics=FlexiblePlanSemantics.model_validate(raw),
    )
    scope = scope.model_copy(update={"employees": (current,)})
    work = OwnedResourceWork(
        namespace=p.tenantId,
        securityDomain=p.securityDomain,
        subject=p.subjectId,
        problem=plan.semantics.target.problem,
        sourceContentDigests=(scope.sourceContentDigest,),
        expiresAt=p.expiresAt,
        admissionId="admit",
        admissionRecordDigest="e" * 64,
        admissionPolicyDigest=p.digest,
        businessScope=scope,
        assemblyAdoption={
            "plan": dict(resource_id=plan.plan_id, revision_id="3", digest=plan.digest),
            "digest": "f" * 64,
        },
    )
    return p, work, plan, current


def test_confirming_current_inherited_tuple_still_produces_explicit_new_plan_proof(
    monkeypatch,
):
    p, work, plan, current = values()
    reader = NS(policy=p, generation=36, recovery_epoch=1)
    calls = []
    monkeypatch.setattr(
        "agent_console.owned_resource_assembly.ensure_no_pending_execution",
        lambda *a: None,
    )

    def assembly(*args, **kw):
        calls.append(kw)
        return work.businessScope, []

    monkeypatch.setattr("agent_console.owned_resource_assembly.read_assembly", assembly)
    automation = NS(owned_business=NS(work_reader=reader))
    call = NS(connection="readonly", context=NS(principal_id=p.subjectId))
    candidate, proof = selection_work(automation, call, work, plan, current)
    assert candidate.businessScope.employees == (current,)
    assert proof is not None and proof["previousPlan"]["digest"] == plan.digest
    assert calls == [
        {"selecting": False, "ontology_successor": None, "_ontology_evidence": {}}
    ]


@pytest.mark.parametrize("damage", ["goal", "task", "business_rule"])
def test_selection_local_candidate_cannot_edit_any_business_semantics(damage):
    _, work, plan, _ = values()
    raw = plan.semantics.model_dump(mode="json")
    if damage == "goal":
        raw["title"] += " different goal"
    elif damage == "task":
        raw["tasks"][0]["title"] += " additional task meaning"
    else:
        raw["business_rules"].append("different business rule")
    candidate = plan.model_copy(
        update={"semantics": FlexiblePlanSemantics.model_validate(raw)}
    )
    with pytest.raises(AuthorityError, match="SELECTION_PLAN_CHANGED"):
        require_selection_rebinding(work, plan, candidate)
