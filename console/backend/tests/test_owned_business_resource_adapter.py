"""Bounded admission consumer tests; no real admission, grant, model or dispatch."""

from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.owned_business_resource_adapter import (
    OwnedResourceWork,
    derive_work,
    digest_basis,
    evidence,
    readonly_work,
    require_capability,
    require_employee,
    require_plan,
    require_preparation,
    require_ready,
    require_reference,
)
from agent_console.plan_suggestion_domain import ExactReference
from agent_console.resource_automation import ResourceAutomation
from pydantic import BaseModel


def ref(kind):
    return ExactReference(resource_id=kind, revision_id="v1", digest="a" * 64)


class Scope(BaseModel):
    scopeId: str = "scope-document"
    authorizationBasisDigest: str = "b" * 64
    source: ExactReference = ref("source")
    sourceContentDigest: str = "c" * 64
    capability: ExactReference | None = None
    employees: tuple = (ref("employee"),)
    skills: tuple = (ref("skill"),)
    agents: tuple = (ref("agent"),)
    runtimes: tuple = (ref("runtime"),)
    operations: tuple = ("READ_DATA",)
    effectPolicy: str = "READ_ONLY"
    externalWrites: bool = False
    case: str = "document"
    nativeAgentName: str = "document-native"
    documentRules: object = None


@pytest.fixture
def case():
    context = NS(
        principal_id="human:one", scope=NS(tenant_id="tenant", security_domain="domain")
    )
    binding = NS(
        problem=ref("problem"),
        subject_id=context.principal_id,
        tenant_id="tenant",
        security_domain="domain",
        scope=Scope(),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        admission_id="admission-one",
        record_digest="d" * 64,
        policy_digest="e" * 64,
    )
    seen = []

    def read(connection, subject, problem, **kwargs):
        seen.append((connection, subject, problem, kwargs))
        return binding

    owner = NS(work=read)
    work = derive_work(owner, "connection", context, binding.problem)
    refs = [(kind, ref(kind)) for kind in ("agent", "skill", "runtime")]
    refs.append(("knowledge", ref("source")))
    employee = (
        ref("employee"),
        {
            "published": True,
            "revision": {
                "members": [
                    {
                        "kind": "RUNTIME_PROFILE"
                        if kind == "runtime"
                        else kind.upper(),
                        "resource_id": reference.resource_id,
                        "revision_id": reference.revision_id,
                        "digest": reference.digest,
                    }
                    for kind, reference in refs
                ]
            },
        },
    )
    return NS(
        context=context,
        binding=binding,
        owner=owner,
        seen=seen,
        work=work,
        refs=refs,
        employee=employee,
    )


def test_exact_read_only_binding_and_private_scope_digest(case):
    assert case.seen == [
        ("connection", case.context, ref("problem"), {"source_digest": None})
    ]
    assert isinstance(case.work, OwnedResourceWork)
    assert readonly_work(case.work).nativeAgentName == "document-native"
    assert digest_basis(["old"], case.work)[-1] == evidence(case.work)
    assert case.work.model_dump(mode="json")["businessScope"]["operations"] == [
        "READ_DATA"
    ]


@pytest.mark.parametrize(
    "field,value",
    [
        ("subject_id", "human:other"),
        ("tenant_id", "other"),
        ("security_domain", "other"),
        ("problem", ref("other")),
    ],
)
def test_wrong_binding_identity_rejected(case, field, value):
    setattr(case.binding, field, value)
    with pytest.raises(AuthorityError, match="RESOURCE_SCOPE_DENIED"):
        derive_work(case.owner, "connection", case.context, ref("problem"))


@pytest.mark.parametrize(
    "change", [{"effectPolicy": "WRITE"}, {"externalWrites": True}, {"operations": ()}]
)
def test_unbounded_effect_or_operations_rejected(case, change):
    case.binding.scope = case.binding.scope.model_copy(update=change)
    with pytest.raises(AuthorityError, match="RESOURCE_SCOPE_DENIED"):
        derive_work(case.owner, "connection", case.context, ref("problem"))


def test_every_actual_member_exact_and_no_synthesis(case):
    require_employee(case.work, case.employee, case.refs)
    for kind in ("skill", "runtime", "agent", "knowledge", "employee", "mcp"):
        with pytest.raises(AuthorityError, match="NOT_AUTHORIZED"):
            require_reference(case.work, kind, ref("foreign"))
    with pytest.raises(AuthorityError, match="PUBLISHED_EMPLOYEE_REQUIRED"):
        require_employee(case.work, None, case.refs)
    with pytest.raises(AuthorityError, match="EXACT_EMPLOYEE_MEMBERS_REQUIRED"):
        require_employee(case.work, case.employee, case.refs[:-1])
    case.employee[1]["published"] = False
    with pytest.raises(AuthorityError, match="PUBLISHED_EMPLOYEE_REQUIRED"):
        require_employee(case.work, case.employee, case.refs)


def test_direct_tuple_does_not_invent_capability(case):
    require_capability(None, None, case.work)
    with pytest.raises(AuthorityError, match="CAPABILITY_MISMATCH"):
        require_capability(
            None,
            None,
            case.work,
            {"contract": {"capability": ref("invented").model_dump()}},
        )


def test_plan_source_operation_and_target_rechecked(case, monkeypatch):
    import agent_console.planning_source_change as sources

    monkeypatch.setattr(sources, "approved_source", lambda _: ref("source"))
    semantics = NS(
        target=NS(problem=ref("problem")),
        tasks=[NS(operation="READ_DATA")],
        requirements=[],
    )
    plan = NS(semantics=semantics)
    require_plan(case.work, plan)
    semantics.tasks[0].operation = "WRITE_DATA"
    with pytest.raises(AuthorityError, match="PLAN_NOT_AUTHORIZED"):
        require_plan(case.work, plan)
    semantics.tasks[0].operation = "READ_DATA"
    monkeypatch.setattr(sources, "approved_source", lambda _: ref("other"))
    with pytest.raises(AuthorityError, match="PLAN_NOT_AUTHORIZED"):
        require_plan(case.work, plan)


def test_ready_receipt_changed_policy_and_resource_rejected(case):
    ready = {
        "ownedBusiness": evidence(case.work),
        "assembly": {"definition": ref("employee").model_dump()},
        "resources": [{"kind": k, "reference": r.model_dump()} for k, r in case.refs],
    }
    require_ready(case.work, ready)
    ready["ownedBusiness"] = {**ready["ownedBusiness"], "policyDigest": "f" * 64}
    with pytest.raises(AuthorityError, match="PREPARATION_CHANGED"):
        require_ready(case.work, ready)
    ready["ownedBusiness"] = evidence(case.work)
    ready["resources"][0]["reference"] = ref("foreign").model_dump()
    with pytest.raises(AuthorityError, match="NOT_AUTHORIZED"):
        require_ready(case.work, ready)


def test_preparation_actual_participants_not_only_ready(case):
    participant = NS(
        definition=ref("employee"),
        profile=ref("runtime"),
        skill=NS(kind="SKILL", reference=ref("skill"), operation="READ_DATA"),
        resources=[],
    )
    p = NS(
        semantics=NS(target=NS(problem=ref("problem"))),
        source_snapshot=ref("source"),
        participants=[participant],
    )
    require_preparation(case.work, p)
    participant.skill.operation = "DELETE"
    with pytest.raises(AuthorityError, match="OPERATION_NOT_AUTHORIZED"):
        require_preparation(case.work, p)


def test_resource_automation_uses_current_connection_only_when_legacy_denies(
    case, monkeypatch
):
    import agent_console.development_administrator as admin

    monkeypatch.setattr(admin, "for_service", lambda *_: False)
    a = ResourceAutomation.__new__(ResourceAutomation)
    a.owned_business = case.owner
    a.grants = NS(
        repository=NS(connection_scope=lambda connection: nullcontext(connection))
    )
    legacy = NS()
    a.policy = NS(enabled=True, work=lambda *_: legacy)
    assert (
        a.work(case.context, ref("problem"), datetime.now(UTC), connection="existing")
        is legacy
    )
    assert len(case.seen) == 1

    def denied(*_):
        raise AuthorityError("RESOURCE_POLICY_WORK_SCOPE_DENIED")

    a.policy.work = denied
    assert (
        a.work(
            case.context, ref("problem"), datetime.now(UTC), connection="existing"
        ).admissionId
        == "admission-one"
    )
    assert case.seen[-1][0] == "existing"
    a.owned_business = None
    with pytest.raises(AuthorityError, match="WORK_SCOPE_DENIED"):
        a.work(case.context, ref("problem"), datetime.now(UTC), connection="existing")


@pytest.mark.parametrize(
    "mutation",
    [
        None,
        "no_owner",
        "revoked",
        "proof",
        "agent",
        "run",
        "expired",
        "participant",
        "duplicate_receipts",
    ],
)
def test_effect_time_guard_rechecks_exact_saved_admission(case, monkeypatch, mutation):
    import agent_console.ontology_execution as ontology
    import agent_console.prepared_execution_lineage as lineage
    from agent_console.owned_business_resource_adapter import authorize_dispatch

    participant = NS(
        definition=ref("employee"),
        profile=ref("runtime"),
        skill=NS(kind="SKILL", reference=ref("skill"), operation="READ_DATA"),
        resources=[],
    )
    p = NS(
        digest="f" * 64,
        semantics=NS(target=NS(problem=ref("problem"))),
        source_snapshot=ref("source"),
        participants=[participant],
    )
    monkeypatch.setattr(
        lineage,
        "prepared_attempt",
        lambda *_: {"preparation": {}, "workflow_run_id": "run-one"},
    )
    monkeypatch.setattr(ontology, "parse_preparation", lambda _: p)
    receipt = {
        "ownedBusiness": evidence(case.work),
        "subject": case.context.principal_id,
        "sourceContentDigest": case.work.businessScope.sourceContentDigest,
        "runId": "run-one",
        "case": "document",
        "nativeAgentName": "document-native",
        "authorizationExpiresAt": case.work.expiresAt.isoformat(),
    }

    class Connection:
        def execute(self, query, _params=None):
            if "to_regclass" in query:
                return NS(
                    fetchone=lambda: {
                        "name": "execution_authority.prepared_resource_commands"
                    }
                )
            return NS(
                fetchall=lambda: (
                    [{"result": receipt}]
                    * (2 if mutation == "duplicate_receipts" else 1)
                )
            )

    command = NS(
        authorization_resource="governed-execution:prepared:" + p.digest,
        scope=NS(namespace="tenant", security_domain="domain"),
        attempt_id="attempt-one",
        principal_id=case.context.principal_id,
        agent_name="document-native",
    )
    owner = case.owner
    if mutation == "no_owner":
        owner = None
    elif mutation == "revoked":

        def revoked(*_, **__):
            raise AuthorityError("OWNED_BUSINESS_REVOKED")

        owner = NS(work=revoked)
    elif mutation == "proof":
        receipt["ownedBusiness"] = {
            **receipt["ownedBusiness"],
            "recordDigest": "0" * 64,
        }
    elif mutation == "agent":
        command.agent_name = "other-agent"
    elif mutation == "run":
        receipt["runId"] = "other-run"
    elif mutation == "expired":
        receipt["authorizationExpiresAt"] = (
            datetime.now(UTC) - timedelta(seconds=1)
        ).isoformat()
    elif mutation == "participant":
        participant.skill.reference = ref("other-skill")
    assert authorize_dispatch(owner, Connection(), command, case.context) is (
        mutation is None
    )


def test_retained_history_cannot_issue_grants_or_prepare_execution(case):
    work = derive_work(
        case.owner, "existing", case.context, ref("problem"), history=True
    )
    assert case.seen[-1][-1] == {"source_digest": None, "history": True}
    assert work.historyRead is True
    automation = ResourceAutomation.__new__(ResourceAutomation)
    with pytest.raises(AuthorityError, match="HISTORY_NOT_EXECUTABLE"):
        automation.decide(None, (), "no-grant", work, None)
    with pytest.raises(AuthorityError, match="HISTORY_NOT_EXECUTABLE"):
        require_preparation(work, None)


def test_historical_binding_cannot_be_promoted_by_normal_consumer(case):
    case.binding.history_only = True
    with pytest.raises(AuthorityError, match="RESOURCE_SCOPE_DENIED"):
        derive_work(case.owner, "connection", case.context, ref("problem"))
    retained = derive_work(
        case.owner, "connection", case.context, ref("problem"), history=True
    )
    assert retained.historyRead is True
