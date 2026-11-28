"""Explicit assembly capability; legacy policies keep their canonical bytes."""

from copy import deepcopy
from types import SimpleNamespace as NS

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.owned_business_policy import OwnedBusinessPolicy
from agent_console.owned_business_resource_adapter import (
    OwnedResourceWork,
    evidence,
    require_plan,
)
from agent_console.owned_resource_assembly import (
    MODE,
    selection_semantics,
    selection_work,
)
from agent_console.resource_use_domain import canonical_digest
from test_owned_business_policy import document


def test_legacy_absent_and_explicit_null_capability_keep_scope_and_policy_digest():
    raw = document()
    base = OwnedBusinessPolicy.model_validate(raw)
    dumped = base.model_dump(mode="json")
    assert "trustedAssemblyAdoption" not in dumped["scopes"][0]
    with_null = deepcopy(raw)
    with_null["scopes"][0]["trustedAssemblyAdoption"] = None
    parsed = OwnedBusinessPolicy.model_validate(with_null)
    assert parsed.model_dump(mode="json") == dumped
    assert parsed.digest == base.digest == canonical_digest(dumped)
    enabled = deepcopy(raw)
    enabled["scopes"][0]["trustedAssemblyAdoption"] = MODE
    adopted = OwnedBusinessPolicy.model_validate(enabled)
    assert adopted.digest != base.digest
    assert (
        adopted.model_dump(mode="json")["scopes"][0]["trustedAssemblyAdoption"] == MODE
    )


def test_disabled_selection_does_not_read_publish_grant_or_derive_new_resources():
    from agent_console.plan_suggestion_domain import ExactReference

    p = OwnedBusinessPolicy.model_validate(document())
    scope = p.scopes[0]
    work = OwnedResourceWork(
        namespace=p.tenantId,
        securityDomain=p.securityDomain,
        subject=p.subjectId,
        problem=scope.source,
        sourceContentDigests=(scope.sourceContentDigest,),
        expiresAt=p.expiresAt,
        admissionId="a",
        admissionRecordDigest="a" * 64,
        admissionPolicyDigest=p.digest,
        businessScope=scope,
    )
    new = ExactReference(resource_id="employee:new", revision_id="r1", digest="b" * 64)
    with pytest.raises(AuthorityError, match="OWNED_BUSINESS_RESOURCE_NOT_AUTHORIZED"):
        selection_work(NS(), NS(), work, NS(), new)
    assert selection_work(NS(), NS(), work, NS(), scope.employees[0]) == (work, None)
    assert "assemblyAdoption" not in evidence(work)
    assert "assemblyAdoption" not in work.model_dump(mode="json")


def test_projected_work_cannot_authorize_a_different_plan():
    from agent_console.plan_suggestion_domain import ExactReference

    p = OwnedBusinessPolicy.model_validate(document())
    scope = p.scopes[0]
    plan = ExactReference(resource_id="plan:chosen", revision_id="2", digest="b" * 64)
    work = OwnedResourceWork(
        namespace=p.tenantId,
        securityDomain=p.securityDomain,
        subject=p.subjectId,
        problem=scope.source,
        sourceContentDigests=(scope.sourceContentDigest,),
        expiresAt=p.expiresAt,
        admissionId="a",
        admissionRecordDigest="a" * 64,
        admissionPolicyDigest=p.digest,
        businessScope=scope,
        assemblyAdoption={"plan": plan.model_dump(mode="json"), "digest": "c" * 64},
    )
    with pytest.raises(AuthorityError, match="OWNED_ASSEMBLY_PLAN_CHANGED"):
        require_plan(work, NS(plan_id="plan:chosen", version=1, digest="d" * 64))
    assert evidence(work)["assemblyAdoption"]["plan"] == plan.model_dump(mode="json")


def test_selection_rebinds_exact_members_without_editing_target_tasks_or_rules():
    from agent_console.plan_suggestion_domain import FlexiblePlanSemantics
    from test_pending_member_requirements import sample

    raw, _, old_skill, _ = sample()
    raw["requirements"][-1]["selected"] = old_skill.model_dump(mode="json")
    original = FlexiblePlanSemantics.model_validate(raw)
    p = OwnedBusinessPolicy.model_validate(document())
    # Required resolution uses the exact selected composition, not arbitrary latest.
    out = selection_semantics(original, p.scopes[0])
    assert isinstance(out, FlexiblePlanSemantics)
    assert out.target == original.target
    assert out.tasks == original.tasks
    assert out.boundaries == original.boundaries
    assert out.business_rules == original.business_rules

    assert out.requirements[-1].selected == p.scopes[0].skills[0]


@pytest.mark.parametrize(
    "damage",
    [
        None,
        "source",
        "runtime",
        "member_kind",
        "executor",
        "io",
        "agent_model",
        "unpublished",
        "skill_without_ontology_successor",
    ],
)
def test_same_scope_composition_contract_rejects_expansion(monkeypatch, damage):
    """Pure contract faults; real permissions/publication are covered by PG chain."""
    import json

    from agent_console.digital_employee_definition import (
        CompositionMember,
        EmployeeRevision,
        MemberKind,
    )
    from agent_console.digital_employee_definition_postgres import (
        PostgresEmployeeDefinitionRepository,
    )
    from agent_console.execution_domain import ScopeIdentity
    from agent_console.native_document_resource_bundle import resource_content
    from agent_console.owned_resource_assembly import read_assembly
    from agent_console.plan_suggestion_domain import ExactReference, PlanningError
    from agent_console.resource_automation_policy import source_digest
    from test_native_document_tools import SOURCE

    policy = OwnedBusinessPolicy.model_validate(document())
    original = policy.scopes[0]
    content = resource_content(SOURCE, rule_bound=True)
    from hashlib import sha256

    raw = json.dumps(SOURCE)
    content["knowledge"] = {
        "documents": [
            {
                "contentDigest": sha256(raw.encode()).hexdigest(),
                "chunks": [{"content": raw}],
            }
        ]
    }
    original = original.model_copy(
        update={"sourceContentDigest": source_digest(content["knowledge"])}
    )
    scope = ScopeIdentity(policy.tenantId, policy.securityDomain)
    new_agent = ExactReference(
        resource_id="agent:new", revision_id="r2", digest="c" * 64
    )
    new_employee = ExactReference(
        resource_id="employee:new", revision_id="r2", digest="d" * 64
    )
    refs = {
        "knowledge": original.source,
        "runtime": original.runtimes[0],
        "agent": new_agent,
        "skill": original.skills[0],
    }
    if damage == "source":
        refs["knowledge"] = refs["knowledge"].model_copy(
            update={"resource_id": "knowledge:other"}
        )
    if damage == "runtime":
        refs["runtime"] = refs["runtime"].model_copy(
            update={"revision_id": "different-model-profile"}
        )
    if damage in {"executor", "io", "skill_without_ontology_successor"}:
        refs["skill"] = refs["skill"].model_copy(update={"revision_id": "new-skill"})
    members = tuple(
        CompositionMember(
            MemberKind("RUNTIME_PROFILE" if k == "runtime" else k.upper()),
            r.resource_id,
            r.revision_id,
            r.digest,
        )
        for k, r in refs.items()
    )
    if damage == "member_kind":
        members += (CompositionMember(MemberKind.MCP, "mcp:new", "r1", "a" * 64),)
    employee = EmployeeRevision(
        scope,
        new_employee.resource_id,
        new_employee.revision_id,
        "Same source reviewer",
        ("same document review",),
        members,
    )
    records = {
        (k.upper(), r): deepcopy(content[k]) for k, r in refs.items() if k != "runtime"
    }
    records["RUNTIME", refs["runtime"]] = deepcopy(content["runtime"])
    records["SKILL", original.skills[0]] = deepcopy(content["skill"])
    records["AGENT", original.agents[0]] = deepcopy(content["agent"])
    if damage == "executor":
        records["SKILL", refs["skill"]]["operations"][0][
            "executorConfigurationDigest"
        ] = "0" * 64
    if damage == "io":
        records["SKILL", refs["skill"]]["operations"][0]["inputSchema"][
            "additionalProperties"
        ] = True
    if damage == "agent_model":
        records["AGENT", new_agent]["bindings"]["model"] = {
            "kind": "MODEL",
            "resourceId": "unapproved",
        }

    def published(c, s, kind, ref, **kwargs):
        if damage == "unpublished" and kind == "EMPLOYEE":
            raise PlanningError("CANDIDATE_VERSION_UNAVAILABLE")
        if kind == "EMPLOYEE":
            return employee.record, "ordinary role"
        return records[kind, ref], kind

    monkeypatch.setattr(
        "agent_console.owned_resource_assembly.require_current_employee",
        lambda *a: None,
    )
    monkeypatch.setattr(
        "agent_console.owned_resource_assembly.read_published", published
    )
    monkeypatch.setattr(
        PostgresEmployeeDefinitionRepository, "validate_members", lambda *a, **kw: None
    )
    actions = tuple(
        NS(
            skill=original.skills[0],
            operation=o["name"],
            executor_id=o["executorId"],
            executor_revision=o["executorRevision"],
            executor_digest=o["executorConfigurationDigest"],
        )
        for o in content["skill"]["operations"]
    )
    monkeypatch.setattr(
        "agent_console.ontology_execution.published_content",
        lambda *a, **kw: NS(actions=actions),
    )
    reader = NS(policy=policy, _reads=lambda *a, **kw: None)
    context = NS(
        scope=NS(tenant_id=scope.namespace, security_domain=scope.security_domain),
        principal_id=policy.subjectId,
    )
    if damage is None:
        projected, observed = read_assembly(
            reader, None, context, original, new_employee, selecting=True
        )
        assert (
            projected.source == original.source
            and projected.documentRules == original.documentRules
        )
        assert projected.runtimes == original.runtimes
        assert projected.employees == (new_employee,) and len(observed) == 4
    else:
        with pytest.raises(
            (AuthorityError, PlanningError),
            match={
                "source": "SOURCE_CHANGED",
                "runtime": "RUNTIME_CHANGED",
                "member_kind": "MEMBER_KIND",
                "executor": "EXECUTOR_CONTRACT_CHANGED",
                "io": "EXECUTOR_CONTRACT_CHANGED",
                "agent_model": "AGENT_AUTHORITY_CHANGED",
                "unpublished": "VERSION_UNAVAILABLE",
                # This standing scope leaves successor adoption disabled. The
                # explicit A2 guard rejects the changed Skill before any
                # successor publication/permission lookup can be attempted.
                "skill_without_ontology_successor": "OWNED_ONTOLOGY_SUCCESSOR_DISABLED",
            }[damage],
        ):
            read_assembly(reader, None, context, original, new_employee, selecting=True)


def test_legacy_wait_binding_never_queries_receipts_or_changes_original_contract():
    from agent_console.owned_resource_assembly import prepared_binding

    sentinel = NS(scope=NS(source="original"))
    calls = []
    owner = NS(work=lambda *args, **kwargs: calls.append((args, kwargs)) or sentinel)

    class NoQuery:
        def execute(self, *args, **kwargs):
            raise AssertionError("default OFF must retain the original owner path")

    prep = NS(semantics=NS(target=NS(problem="problem")))
    assert prepared_binding(owner, NoQuery(), "context", "command", prep) is sentinel
    assert len(calls) == 1 and calls[0][1] == {}


@pytest.mark.parametrize(
    "bad",
    [None, {}, {"digest": "a" * 64}, {"body": None, "digest": canonical_digest(None)}],
)
def test_malformed_receipt_is_bounded_deny_never_legacy_fallback(bad):
    from agent_console.owned_resource_assembly import project
    from agent_console.plan_suggestion_domain import ExactReference

    plan = ExactReference(resource_id="plan:explicit", revision_id="2", digest="a" * 64)

    class Rows:
        def execute(self, query, args=None):
            if "to_regclass" in query:
                return NS(fetchone=lambda: {"name": "present"})
            return NS(
                fetchall=lambda: [
                    {"request_key": "original-key", "record": {"assemblyAdoption": bad}}
                ]
            )

    binding = NS(
        scope=NS(trustedAssemblyAdoption=MODE),
        tenant_id="tenant",
        security_domain="domain",
        subject_id="human:one",
    )
    with pytest.raises(AuthorityError, match="OWNED_ASSEMBLY_PROOF_INVALID"):
        project(NS(), Rows(), NS(), binding, plan)
