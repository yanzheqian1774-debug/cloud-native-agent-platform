"""Real isolated source/plan/grant/ontology/preparation owners; controlled model only."""

# ruff: noqa: F401,F811,E501 -- Shared isolated fixtures and exact SQL/owner calls.
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace as NS

import owned_business_consumer_support as support
import pytest
from agent_console.authority_contracts import AuthorityError, ExactGrant
from agent_console.execution_domain import ScopeIdentity
from agent_console.execution_postgres import PostgresExecutionAuthorityRepository
from agent_console.native_document_resource_bundle import resource_content
from agent_console.native_typed_document_skill import (
    NativeTypedQuestionDocumentSkillExecutor,
)
from agent_console.ontology_action_correction import ENV, OntologyActionCorrection
from agent_console.ontology_action_correction_policy import CorrectionPolicy
from agent_console.ontology_action_correction_postgres import migrate
from agent_console.ontology_execution import published_content
from agent_console.ontology_service import OntologyService, resource
from agent_console.owned_business_resource_adapter import derive_work
from agent_console.plan_suggestion_domain import (
    ConfirmedPlanRevision,
    ExactReference,
    ProposalRevision,
)
from agent_console.policy_plan_confirmation import PolicyPlanConfirmation
from agent_console.prepared_native_coordinator import PreparedNativeCoordinator
from agent_console.readonly_continuation import ReadonlyContinuation
from agent_console.readonly_continuation_policy import ReadonlyContinuationPolicy
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
)
from owned_business_consumer_support import (
    configure_scope,
    prepare_current_resource_reads,
    resource_automation,
)
from owned_business_planning_support import generate_proposal
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark as pgmark
from test_conversation_relation_bff import routed
from test_ontology_lifecycle import ExactOntologyTestAuthority
from test_owned_business_admission import owned_created, owned_ready
from test_owned_business_consumer_chain import cleanup_consumer_resources
from test_owned_conversation_bff import ordinary
from test_recovery_bound_understanding import setup
from test_understanding_adoption_bff import adopted


def configure_mismatch(e, result, policy):
    configure_scope(e, result, policy)
    from agent_console.digital_employee_definition import (
        CompositionMember,
        EmployeeRevision,
        MemberKind,
    )
    from agent_console.digital_employee_definition_postgres import (
        PostgresEmployeeDefinitionRepository,
    )
    from agent_console.workbench_prepared_resources import PreparedResourceOwner
    from test_native_document_tools import SOURCE

    svc = e.consumer_services["skill"]
    scope = e.context.scope
    rs = svc.scope(scope.tenant_id, scope.security_domain)
    value = svc.create(
        rs,
        "skill",
        "human:fixture-author",
        "Published v7",
        resource_content(
            SOURCE, rule_bound=True, durable_wait=True, typed_questions=True
        )["skill"],
    )
    revision = value["revisions"][-1]
    with e.repo.connection_scope() as c:
        PreparedResourceOwner(e.consumer_services)(
            NS(
                operation="REVIEW_PREPARED_RESOURCE",
                context=NS(principal_id="human:fixture-reviewer", scope=scope),
                connection=c,
                authority=NS(require=lambda *a: NS(decision_id="isolated-setup")),
                path=dict(
                    kind="skill",
                    identity=value["resourceId"],
                    revision=revision["revisionId"],
                ),
                payload=dict(
                    expectedVersion=value["aggregateVersion"],
                    digest=revision["digest"],
                    reason="Isolated setup",
                    idempotencyKey="v7-publish",
                ),
            )
        )
    skill = ExactReference(
        resource_id=value["resourceId"],
        revision_id=revision["revisionId"],
        digest=revision["digest"].removeprefix("sha256:"),
    )
    e.consumer_refs["skill"] = skill
    employee = EmployeeRevision(
        ScopeIdentity(scope.tenant_id, scope.security_domain),
        "employee:joint-v7",
        "employee-revision:joint-v7",
        "V7 employee",
        ("Isolated test",),
        tuple(
            CompositionMember(
                MemberKind("RUNTIME_PROFILE" if k == "runtime" else k.upper()),
                v.resource_id,
                v.revision_id,
                v.digest,
            )
            for k, v in e.consumer_refs.items()
        ),
    )
    owner = PostgresEmployeeDefinitionRepository(e.repo)
    with e.repo.connection_scope() as c:
        v = owner.create_for_workbench(
            c,
            employee,
            expected_version=0,
            decision_id="isolated",
            command_id="v7-create",
            authorized=True,
        )
        for action in ("VALIDATE", "APPROVE", "PUBLISH"):
            v = owner.decide_for_workbench(
                c,
                employee.scope,
                employee.definition_id,
                employee.revision_id,
                employee.digest,
                action,
                expected_version=v["aggregateVersion"],
                decision_id="isolated",
                command_id="v7-" + action,
                authorized=True,
            )
    e.consumer_employee = ExactReference(
        resource_id=employee.definition_id,
        revision_id=employee.revision_id,
        digest=employee.digest,
    )
    policy["scopes"][0].update(
        skills=[skill.model_dump()], employees=[e.consumer_employee.model_dump()]
    )


pytestmark = [
    pgmark,
    pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True),
    pytest.mark.parametrize(
        "owned_ready",
        [
            dict(
                mode="SOURCE_SUCCESSOR",
                prepare_source=support.prepare_source,
                configure_scope=configure_mismatch,
            )
        ],
        indirect=True,
    ),
]


@pytest.fixture
def correction(owned_created, tmp_path, request, monkeypatch):
    e = owned_created
    consumers = {}

    def before(e, current):
        a, adapter = resource_automation(e, e.consumer_planning_app, tmp_path)
        prepare_current_resource_reads(e, a)
        consumers.update(a=a, adapter=adapter)

    generate_proposal(e, before_planning=before)
    a, adapter = consumers["a"], consumers["adapter"]
    proposal = ProposalRevision.model_validate(e.consumer_proposal)
    identity = proposal.proposal_id
    generation = a.grants.generation.generation

    def invoke(handler, operation, payload, query=None, context=None):
        context = context or e.context
        with e.repo.connection_scope() as c:
            return handler(
                AuthorizedOwnerCall(
                    operation,
                    context,
                    c,
                    payload,
                    dict(proposal_id=identity, plan_id=identity),
                    query or {},
                    (),
                    AuthorizedOwnerAuthority(adapter, context, c, generation, ()),
                    generation,
                    1,
                )
            )

    confirmed = invoke(
        PolicyPlanConfirmation(a),
        "CONFIRM_POLICY_PLAN",
        dict(
            problem=proposal.semantics.target.problem.model_dump(),
            revision=proposal.revision,
            digest=proposal.digest,
            expectedPlanVersion=0,
            idempotencyKey="correction-confirm",
        ),
    )
    plan = ConfirmedPlanRevision.model_validate(confirmed["confirmation"]["plan"])
    native = PostgresExecutionAuthorityRepository(
        e.repo.pool.conninfo,
        migration_path=Path(__file__).parents[1]
        / "migrations/0008_execution_runtime_authority.sql",
    )
    request.addfinalizer(native.pool.close)
    native.migrate_native_dispatch(
        Path(__file__).parents[1] / "migrations/0022_native_execution_dispatch.sql"
    )
    continuation = ReadonlyContinuation(
        a,
        ReadonlyContinuationPolicy(
            policyId="correction-readonly", policyVersion="1", enabled=True, works=()
        ),
        PreparedNativeCoordinator(native),
    )
    a.continuation = continuation
    ready = invoke(
        a,
        "PREPARE_RESOURCE_AUTOMATION",
        dict(version=plan.version, idempotencyKey="correction-resources"),
    )
    assert ready["state"] == "READY", ready
    with pytest.raises(Exception, match="ONTOLOGY_EXECUTOR_BINDING_MISMATCH"):
        invoke(continuation, "CONTINUE_READONLY_WORK", dict(version=plan.version))
    scope = ScopeIdentity(e.context.scope.tenant_id, e.context.scope.security_domain)
    with e.repo.connection_scope() as c:
        binding = e.business_owner.work(c, e.context, plan.semantics.target.problem)
        content = published_content(c, scope, binding.scope.documentRules)
    revision = NativeTypedQuestionDocumentSkillExecutor.revision
    new = content.model_copy(
        update={
            "actions": tuple(
                action.model_copy(
                    update=dict(
                        skill=binding.scope.skills[0],
                        executor_id=revision.executor_id,
                        executor_revision=revision.executor_revision,
                        executor_digest=revision.configuration_digest,
                    )
                )
                for action in content.actions
            )
        }
    )
    digest = None
    for version, action in enumerate(
        ("CREATE", "VALIDATE", "TEST", "REVIEW", "PUBLISH")
    ):
        with e.repo.connection_scope() as c:
            owner = OntologyService(
                NS(
                    connection=c,
                    context=NS(
                        scope=e.context.scope,
                        principal_id="human:fixture-reviewer"
                        if version >= 3
                        else "human:fixture-author",
                    ),
                    authority=ExactOntologyTestAuthority(),
                )
            )
            value = owner.handle(
                action,
                "joint-new-v7-rules",
                dict(
                    request_key="correction-" + action,
                    expected_version=version,
                    revision_id="r1",
                    digest=digest,
                    content=new.model_dump(mode="json") if version == 0 else None,
                    reason="Isolated owner setup",
                ),
            )
            if version == 0:
                digest = value["digest"]
    newbinding = binding.scope.documentRules.model_copy(
        update=dict(
            ontology=ExactReference(
                resource_id="joint-new-v7-rules", revision_id="r1", digest=digest
            )
        )
    )
    p = CorrectionPolicy(
        schemaVersion="ontology-action-correction.v1",
        enabled=True,
        tenantId=scope.namespace,
        securityDomain=scope.security_domain,
        subjectId=e.context.principal_id,
        admissionId=binding.admission_id,
        admissionRecordDigest=binding.record_digest,
        originalPolicyDigest=binding.policy_digest,
        problem=binding.problem,
        plan=ExactReference(
            resource_id=plan.plan_id, revision_id=str(plan.version), digest=plan.digest
        ),
        oldBinding=binding.scope.documentRules,
        newBinding=newbinding,
        expiresAt=datetime.now(UTC) + timedelta(minutes=10),
    )
    path = tmp_path / "correction.json"
    path.write_text(p.model_dump_json())
    path.chmod(0o600)
    migrate(e.repo)

    def authorize(call):
        work = derive_work(
            e.business_owner, call.connection, call.context, binding.problem
        )
        return a.decide(
            call,
            [
                ExactGrant(
                    "BUSINESS_ONTOLOGY",
                    action,
                    resource(ref.resource_id, ref.revision_id),
                )
                for ref in (binding.scope.documentRules.ontology, newbinding.ontology)
                for action in ("READ", "USE")
            ],
            "correction-new-rules",
            work,
            a.authenticate(call.context),
            purpose="READONLY_WORK_EXECUTION",
        )

    invoke(authorize, "CORRECTION_SETUP", {})
    monkeypatch.setenv(ENV, str(path))
    e.correction_adapter = adapter
    e.correction_generation = generation
    e.native_repository = native
    e.correct = OntologyActionCorrection(e.business_owner, path)
    e.correction_policy = p
    e.correct_path = path
    e.invoke = invoke
    e.plan = plan
    e.ready = ready
    e.continue_owner = continuation
    e.binding = binding
    return e


def test_correction_real_owner_same_plan_and_exact_preparation(correction):
    e = correction
    p = e.correction_policy
    with e.repo.connection_scope() as c:
        original = c.execute(
            "SELECT record FROM authorization_admin.owned_business_admissions WHERE admission_id=%s",
            (p.admissionId,),
        ).fetchone()
        budget = c.execute(
            "SELECT count(*) n FROM draft_provider_budget.reservations"
        ).fetchone()
    payload = dict(idempotencyKey="correct-original", policyDigest=p.digest)
    with pytest.raises(AuthorityError):
        e.invoke(
            e.correct,
            "CORRECT_ORIGINAL_ONTOLOGY_ACTION_BINDING",
            payload,
            context=replace(e.context, principal_id="human:unrelated"),
        )
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                e.invoke, e.correct, "CORRECT_ORIGINAL_ONTOLOGY_ACTION_BINDING", payload
            )
            for _ in range(2)
        ]
        first = futures[0].result(timeout=10)
        assert futures[1].result(timeout=10) == first

    assert (
        e.invoke(e.correct, "CORRECT_ORIGINAL_ONTOLOGY_ACTION_BINDING", payload)
        == first
    )
    with pytest.raises(AuthorityError, match="CONFLICT"):
        e.invoke(
            e.correct,
            "CORRECT_ORIGINAL_ONTOLOGY_ACTION_BINDING",
            {**payload, "idempotencyKey": "another-key"},
        )
    with e.repo.connection_scope() as c:
        corrected = e.business_owner.work(c, e.context, e.binding.problem)
        assert corrected.scope.documentRules == p.newBinding
        from agent_console.owned_business_resource_adapter import (
            derive_work,
            require_plan,
        )
        from agent_console.owned_business_work_reader import OwnedBusinessWorkReader

        independent = OwnedBusinessWorkReader(
            e.business_owner.path,
            e.business_owner.work_reader.authorization,
            e.business_owner.work_reader.generation,
            e.business_owner.work_reader.recovery_epoch,
        )
        same = independent.work(c, e.context, e.binding.problem)
        assert same.ontology_correction == corrected.ontology_correction
        work = derive_work(independent, c, e.context, e.binding.problem)
        with pytest.raises(AuthorityError, match="CORRECTION_PLAN_MISMATCH"):
            require_plan(
                work, e.plan.model_copy(update={"version": e.plan.version + 1})
            )

        assert (
            c.execute(
                "SELECT record FROM authorization_admin.owned_business_admissions WHERE admission_id=%s",
                (p.admissionId,),
            ).fetchone()
            == original
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.reservations"
            ).fetchone()
            == budget
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM execution_authority.native_dispatch_commands"
            ).fetchone()["n"]
            == 0
        )
    result = e.invoke(
        e.continue_owner, "CONTINUE_READONLY_WORK", dict(version=e.plan.version)
    )
    assert result["receipt"]["executionStarted"] is True
    assert (
        result["receipt"]["ontologyActionCorrection"]["receiptDigest"]
        == first["digest"]
    )
    from agent_console.owned_business_resource_adapter import authorize_dispatch

    with e.repo.connection_scope() as c:
        rows = c.execute(
            "SELECT payload FROM execution_authority.native_dispatch_commands"
        ).fetchall()
        assert rows
        for row in rows:
            command = e.native_repository._dispatch_command(row["payload"])
            assert authorize_dispatch(independent, c, command, e.context)

    assert (
        e.invoke(
            e.continue_owner,
            "READ_READONLY_CONTINUATION",
            {},
            dict(version=e.plan.version),
        )["receipt"]
        == result["receipt"]
    )

    from agent_console.grant_administration_application import GrantRevocationCommand

    with e.repo.connection_scope() as c:
        grant = c.execute(
            "SELECT grant_id FROM authorization_admin.grants WHERE subject_principal_id=%s AND owner='BUSINESS_ONTOLOGY' AND action='USE' AND exact_resource=%s",
            (
                p.subjectId,
                resource(
                    p.newBinding.ontology.resource_id, p.newBinding.ontology.revision_id
                ),
            ),
        ).fetchone()
    e.admission.delegation.grants.revoke_grant(
        e.context,
        GrantRevocationCommand(
            grant["grant_id"],
            "TEST_WITHDRAWAL",
            "worker-correction-revoke",
            surrender=True,
        ),
    )
    with e.repo.connection_scope() as c:
        assert not authorize_dispatch(independent, c, command, e.context)
    # Historical same-key GET is not execution: no new USE or dispatch after revoke.
    assert (
        e.invoke(
            e.continue_owner,
            "READ_READONLY_CONTINUATION",
            {},
            dict(version=e.plan.version),
        )["receipt"]
        == result["receipt"]
    )


def test_partial_unknown_revoke_and_atomic_rollback(correction, monkeypatch):
    e = correction
    p = e.correction_policy
    from agent_console import ontology_action_correction_postgres as store
    from agent_console.grant_administration_application import GrantRevocationCommand
    from psycopg.types.json import Jsonb

    payload = dict(idempotencyKey="bounded-correction", policyDigest=p.digest)

    def call(c):
        return AuthorizedOwnerCall(
            "CORRECT_ORIGINAL_ONTOLOGY_ACTION_BINDING",
            e.context,
            c,
            payload,
            dict(plan_id=e.plan.plan_id),
            {},
            (),
            AuthorizedOwnerAuthority(
                e.correction_adapter, e.context, c, e.correction_generation, ()
            ),
            e.correction_generation,
            1,
        )

    class Rollback(Exception):
        pass

    for state in ("PARTIAL", "UNKNOWN"):
        with pytest.raises(Rollback), e.repo.connection_scope() as c:
            c.execute(
                "INSERT INTO execution_authority.prepared_resource_commands VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    p.tenantId,
                    p.securityDomain,
                    p.subjectId,
                    "partial:" + state,
                    "a" * 64,
                    Jsonb(dict(sourcePlanId=e.plan.plan_id, state=state)),
                ),
            )
            with pytest.raises(AuthorityError, match="EXISTING_EXECUTION_OR_PARTIAL"):
                e.correct(call(c))
            assert store.read(c, p.admissionId) is None
            raise Rollback()
    # A caller transaction failure after the real append must not leave the receipt.
    with pytest.raises(Rollback), e.repo.connection_scope() as c:
        e.correct(call(c))
        assert store.read(c, p.admissionId) is not None
        raise Rollback()
    with e.repo.connection_scope() as c:
        assert store.read(c, p.admissionId) is None
    # Formal surrender, not DELETE effective_grants: current USE remains authoritative.
    with e.repo.connection_scope() as c:
        grant = c.execute(
            "SELECT grant_id FROM authorization_admin.grants WHERE subject_principal_id=%s AND owner='BUSINESS_ONTOLOGY' AND action='USE' AND exact_resource=%s",
            (
                p.subjectId,
                resource(
                    p.newBinding.ontology.resource_id, p.newBinding.ontology.revision_id
                ),
            ),
        ).fetchone()
    assert grant
    e.admission.delegation.grants.revoke_grant(
        e.context,
        GrantRevocationCommand(
            grant["grant_id"], "TEST_WITHDRAWAL", "correction-revoke", surrender=True
        ),
    )
    with pytest.raises(AuthorityError, match="READ_DENIED"):
        e.invoke(e.correct, "CORRECT_ORIGINAL_ONTOLOGY_ACTION_BINDING", payload)
    with e.repo.connection_scope() as c:
        assert store.read(c, p.admissionId) is None
