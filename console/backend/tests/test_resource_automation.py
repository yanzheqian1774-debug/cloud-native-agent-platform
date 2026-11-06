# ruff: noqa: E501, F811, RUF001 -- Scoped PostgreSQL fixtures and explicit owner SQL.
"""D11 real owner/authorization transactions, disposable PG only; no live effects."""

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from agent_console.authority_configuration import (
    CredentialConfiguration,
    RequestabilityRule,
    StaticAuthorityGeneration,
    StaticGrant,
)
from agent_console.authority_contracts import (
    AuthenticationSource,
    AuthorityScope,
    CredentialId,
    ExactGrant,
    GrantSource,
    TrustedRequestContext,
)
from agent_console.authority_postgres import PostgresAuthorityRepository
from agent_console.digital_employee_definition_postgres import (
    PostgresEmployeeDefinitionRepository,
)
from agent_console.grant_administration_application import (
    GenerationAuthorizationReader,
    GrantAdministrationService,
)
from agent_console.resource_automation import ResourceAutomation, migrate
from agent_console.resource_automation_policy import AutomationPolicy, WorkScope
from agent_console.workbench_grant_targets import WorkbenchGrantTargetValidator
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
    WorkbenchOwnerAuthorization,
)
from agent_console.workbench_plan_suggestion import PlanningGrantTargetValidator
from agent_console.workbench_prepared_resources import PreparedResourceTargets
from psycopg.rows import dict_row
from test_plan_suggestion_v2 import repository  # noqa: F401
from test_planning_candidates_source_change import case  # noqa: F401
from test_prepared_resource_owners import services  # noqa: F401

MIGRATIONS = Path(__file__).parents[1] / "migrations"


def continuation_targets():
    from agent_console.workbench_prepared_execution import PreparedExecutionGrantTargets

    return (PreparedExecutionGrantTargets(),)


@pytest.fixture
def automation(repository, case, services, tmp_path, request):
    e = case
    mode = getattr(request, "param", "existing")
    continuation = isinstance(mode, dict) and mode.get("continuation", False)
    delivery_v2 = isinstance(mode, dict) and mode.get("deliveryV2", False)
    if isinstance(mode, dict):
        mode = mode["resources"]
    from agent_console.plan_suggestion_domain import ExactReference, ProposalRevision
    from agent_console.sales_resource_bundle import resource_content
    from agent_console.workbench_prepared_resources import PreparedResourceOwner
    from test_plan_suggestion_v2 import confirm

    if delivery_v2:
        import json

        from agent_console.synthetic_delivery_skill_v2 import (
            resource_content as delivery_content,
        )
        from delivery_v2_support import six_roles

        contents = delivery_content()
        e.source = json.loads(contents["knowledge"]["content"])
        e.p = e.p.model_copy(update={"semantics": six_roles(e.p.semantics)})
    else:
        contents = resource_content(e.source)
    refs = {}
    pub = PreparedResourceOwner(services)
    setup_context = SimpleNamespace(
        principal_id="human:isolated-setup-reviewer",
        scope=AuthorityScope(e.scope.namespace, e.scope.security_domain),
    )
    setup_authority = SimpleNamespace(
        require=lambda *args: SimpleNamespace(decision_id="isolated-setup-only")
    )
    for kind, service in services.items():
        rs = service.scope(e.scope.namespace, e.scope.security_domain)
        args = (
            (rs, "skill", "human:isolated-setup")
            if kind == "skill"
            else (rs, "human:isolated-setup")
        )
        content = contents[kind]
        if kind == "skill" and mode in {"partial", "bad-schema"}:
            import copy

            content = copy.deepcopy(content)
            if mode == "partial":
                content["operations"][0]["executorId"] = "unregistered-executor"
            else:
                content["operations"][0]["inputSchema"]["properties"]["schemaVersion"][
                    "enum"
                ] = ["wrong-input.v1"]
        if mode == "expanded" and kind == "skill":
            content = {**content, "operations": content["operations"][:1]}
        value = service.create(*args, "明确标记的隔离D11测试资源", content)
        if kind == "knowledge":
            value = value["knowledge"]
        identity = value[
            {
                "skill": "resourceId",
                "runtime": "runtimeProfileId",
                "agent": "definitionId",
                "knowledge": "knowledgeId",
            }[kind]
        ]
        rev = value["revisions"][-1]
        if mode not in {"batch", "partial"} and not (
            kind == "skill" and mode in {"new", "bad-schema"}
        ):
            with repository.pool.connection() as c, c.transaction():
                pub(
                    SimpleNamespace(
                        operation="REVIEW_PREPARED_RESOURCE",
                        context=setup_context,
                        connection=c,
                        authority=setup_authority,
                        path={
                            "kind": kind,
                            "identity": identity,
                            "revision": rev["revisionId"],
                        },
                        payload={
                            "expectedVersion": value["aggregateVersion"],
                            "digest": rev["digest"],
                            "reason": "Isolated setup only; not D11 automation evidence",
                            "idempotencyKey": "fixture-setup-" + kind,
                        },
                    )
                )
        if mode == "expanded" and kind == "skill":
            value = service.repository.get(rs, "skill", identity)
            service.successor(
                rs, "skill", identity, "human:isolated-setup", value["aggregateVersion"]
            )
            value = service.repository.get(rs, "skill", identity)
            service.edit(
                rs,
                "skill",
                identity,
                "human:isolated-setup",
                value["aggregateVersion"],
                contents[kind],
            )
            value = service.repository.get(rs, "skill", identity)
            rev = value["revisions"][-1]
        refs[kind] = ExactReference(
            resource_id=identity,
            revision_id=rev["revisionId"],
            digest=rev["digest"].removeprefix("sha256:"),
        )
    from agent_console.digital_employee_definition import (
        CompositionMember,
        EmployeeRevision,
        MemberKind,
    )

    employees_setup = PostgresEmployeeDefinitionRepository(repository)
    employee_revision = EmployeeRevision(
        e.scope,
        "employee-definition:d11-setup",
        "employee-revision:d11-setup",
        "隔离自动准备验证",
        ("仅用于隔离验证，不代表真实业务结果",),
        tuple(
            CompositionMember(
                MemberKind("RUNTIME_PROFILE" if k == "runtime" else k.upper()),
                r.resource_id,
                r.revision_id,
                "sha256:" + r.digest if k == "runtime" else r.digest,
            )
            for k, r in refs.items()
        ),
    )
    with repository.pool.connection() as c, c.transaction():
        value = employees_setup.create_for_workbench(
            c,
            employee_revision,
            expected_version=0,
            decision_id="explicit-isolated-fixture-setup",
            command_id="fixture-employee-create",
            authorized=True,
        )
        if mode == "existing":
            for action in ("VALIDATE", "APPROVE", "PUBLISH"):
                value = employees_setup.decide_for_workbench(
                    c,
                    e.scope,
                    employee_revision.definition_id,
                    employee_revision.revision_id,
                    employee_revision.digest,
                    action,
                    expected_version=value["aggregateVersion"],
                    decision_id="explicit-isolated-fixture-setup",
                    command_id="fixture-employee-" + action,
                    authorized=True,
                )
    employee_ref = ExactReference(
        resource_id=employee_revision.definition_id,
        revision_id=employee_revision.revision_id,
        digest=employee_revision.digest,
    )
    semantics = e.p.semantics.model_dump(mode="json")
    semantics["requirements"] = [
        {
            **r,
            "selected": (
                employee_ref if r["kind"] == "EMPLOYEE" else refs["knowledge"]
            ).model_dump(mode="json"),
        }
        for r in semantics["requirements"]
    ]
    semantics["boundaries"] = [
        b for b in semantics["boundaries"] if not b.startswith("隔离合成来源：")
    ]
    source = refs["knowledge"]
    semantics["boundaries"].append(
        f"隔离合成来源：{source.resource_id}；修订：{source.revision_id}；SHA256：{source.digest}"
    )
    previous = e.app.repository
    with previous.transaction(e.scope, e.p.plan_id, authorized=True) as cur:
        head = previous.proposal(cur, e.scope, e.p.plan_id, e.p.plan_version)
        proposal = ProposalRevision(
            proposal_id=e.p.plan_id,
            revision=head.revision + 1,
            predecessor_digest=head.digest,
            invocation_id="explicit-isolated-policy-test-setup",
            semantics=type(e.p.semantics).model_validate(semantics),
        )
        previous.add_proposal(cur, e.scope, proposal)
    confirmed = confirm(
        previous,
        e.scope,
        proposal,
        "isolated-resource-policy-setup",
        expected=e.p.plan_version,
    )
    e.p = e.p.model_copy(
        update={
            "plan_version": confirmed["plan"]["version"],
            "plan_digest": confirmed["digest"],
            "semantics": proposal.semantics,
            "source_snapshot": source,
        }
    )
    authority = PostgresAuthorityRepository(
        repository.pool.conninfo,
        migration_path=MIGRATIONS / "0018_browser_session_grant_authority.sql",
    )
    authority.migrate()
    now = datetime.now(UTC)
    scope = AuthorityScope(e.scope.namespace, e.scope.security_domain)
    raw = "isolated-policy-secret-not-an-actual-credential"
    credential = tmp_path / "policy.secret"
    credential.write_text(raw)
    member_read = ExactGrant(
        "GRANT_ADMIN",
        "DECIDE",
        f"grant-scope:{scope.tenant_id}:{scope.security_domain}",
    )
    initial = (
        ExactGrant("PLAN", "READ", "plan:v2:" + e.p.plan_id),
        ExactGrant("PLAN", "APPROVE", "plan:v2:" + e.p.plan_id),
    )
    gen = StaticAuthorityGeneration(
        1,
        "a" * 64,
        "test-policy-generation",
        "isolated-d11-test",
        (
            CredentialConfiguration(
                CredentialId("user-test"),
                hashlib.sha256(b"unit-subject-secret").hexdigest(),
                e.principal.principal_id,
                scope,
                now + timedelta(hours=4),
                GrantSource.SERVICE_ONLY,
                tuple(StaticGrant(g, GrantSource.SERVICE_ONLY) for g in initial),
            ),
            CredentialConfiguration(
                CredentialId("policy-test"),
                hashlib.sha256(raw.encode()).hexdigest(),
                "service:resource-preparation-policy",
                scope,
                now + timedelta(hours=4),
                GrantSource.SERVICE_ONLY,
                (StaticGrant(member_read, GrantSource.STATIC_META),),
            ),
        ),
        tuple(
            RequestabilityRule(owner, action, prefix, "RESOURCE_PREPARATION")
            for owner, action, prefix in [
                ("BUSINESS_PROBLEM", "READ", "business-problem:"),
                ("SUCCESS_CRITERIA_SET", "READ", "success-criteria-set:"),
                ("SUCCESS_CRITERION", "READ", "success-criterion:"),
                ("PLAN", "PREPARE", "plan:"),
                ("PLAN", "READ", "plan:"),
                ("PLAN", "APPROVE", "plan:"),
                ("AGENT", "READ", "agent:"),
                *[
                    (owner, a, prefix)
                    for owner, prefix in [
                        ("AGENT", "agent:"),
                        ("SKILL", "skill-invocation:"),
                        ("RUNTIME_PROFILE", "runtime-profile:"),
                        ("KNOWLEDGE", "knowledge:"),
                    ]
                    for a in ("READ_RESOURCE", "REVIEW_PUBLISH_RESOURCE")
                ],
                *[
                    ("EMPLOYEE", a, "employee:")
                    for a in ("CREATE", "READ", "VALIDATE", "APPROVE", "PUBLISH")
                ],
            ]
        ),
        frozenset(),
    )
    if continuation:
        from dataclasses import replace

        from agent_console.authority_configuration import OWNER_RESOURCE_PREFIXES

        extra = [(r.owner, r.action) for r in gen.requestability]
        extra += [
            ("INSTANCE", "CREATE"),
            ("ASSIGNMENT", "CREATE"),
            ("EXECUTION", "START"),
            ("EXECUTION", "READ"),
            ("SKILL", "INVOKE_SKILL"),
            ("EVALUATION", "EVALUATE"),
            ("EVALUATION", "READ"),
            ("HUMAN_CONFIRMATION", "READ"),
            ("EVIDENCE", "READ_REFERENCE"),
            ("RESOURCE_USE", "READ"),
        ]
        gen = replace(
            gen,
            requestability=gen.requestability
            + tuple(
                RequestabilityRule(
                    owner,
                    action,
                    OWNER_RESOURCE_PREFIXES[owner],
                    "READONLY_WORK_EXECUTION",
                )
                for owner, action in sorted(set(extra))
            ),
        )
    authority.activate_generation(
        1,
        gen.digest,
        1,
        operator_id="operator:isolated-test",
        revoked_credentials=(),
        now=now,
    )
    reader = GenerationAuthorizationReader(gen, authority, authority, recovery_epoch=1)
    employees = PostgresEmployeeDefinitionRepository(repository)
    targets = WorkbenchGrantTargetValidator(
        e.app.problems,
        services["agent"].repository,
        employees,
        additional=(
            PreparedResourceTargets(),
            PlanningGrantTargetValidator(),
            *continuation_targets(),
        ),
    )
    grants = GrantAdministrationService(
        authority,
        reader,
        gen,
        continuation_owner=None,
        target_validator=targets,
        recovery_epoch=1,
    )
    controller = SimpleNamespace(readiness=SimpleNamespace(recovery_epoch=1))
    adapter = WorkbenchOwnerAuthorization(
        controller, authority, reader, clock=lambda: grants.clock()
    )
    subject = TrustedRequestContext(
        e.principal.principal_id,
        scope,
        "user-test",
        AuthenticationSource.SERVICE_CREDENTIAL,
        gen.policy_version,
    )
    with repository.pool.connection() as c:
        content = c.execute(
            "SELECT record FROM knowledge_operation.knowledge WHERE namespace=%s AND security_domain=%s AND knowledge_id=%s",
            (
                e.scope.namespace,
                e.scope.security_domain,
                e.p.source_snapshot.resource_id,
            ),
        ).fetchone()["record"]["revisions"][0]["content"]
        content_digest = content["documents"][0]["contentDigest"]
        migrate(c)
    policy = AutomationPolicy(
        policyId="resource-preparation",
        policyVersion="d11-test-1",
        issuer="service:resource-preparation-policy",
        credentialPath=credential,
        kubeconfigPath=tmp_path / "kubeconfig",
        kubeContext="isolated",
        enabled=True,
        workScopes=(
            WorkScope(
                namespace=e.scope.namespace,
                securityDomain=e.scope.security_domain,
                subject=subject.principal_id,
                problem=e.p.semantics.target.problem,
                sourceContentDigests=(content_digest,),
                expiresAt=now + timedelta(hours=2),
            ),
        ),
    )
    automation = ResourceAutomation(
        policy,
        grants,
        e.app,
        {**services, "mcp": services["skill"]},
        employees,
        runtime_probe=lambda namespace: {
            "check": "ISOLATED_RUNTIME_PROBE",
            "status": "PASSED",
            "namespace": namespace,
        },
    )

    def run(key="first", read=False, version=None):
        with repository.pool.connection() as c, c.transaction():
            c.row_factory = dict_row
            owner_authority = AuthorizedOwnerAuthority(adapter, subject, c, 1, ())
            return automation(
                AuthorizedOwnerCall(
                    "READ_RESOURCE_AUTOMATION"
                    if read
                    else "PREPARE_RESOURCE_AUTOMATION",
                    subject,
                    c,
                    {"version": version or e.p.plan_version, "idempotencyKey": key},
                    {"proposal_id": e.p.plan_id},
                    {"version": version or e.p.plan_version, "key": key},
                    (),
                    owner_authority,
                    1,
                    1,
                )
            )

    errors = []
    original = automation.prepare_one

    def instrumented(*args, **kwargs):
        try:
            return original(*args, **kwargs)
        except Exception as exc:
            errors.append(repr(exc))
            raise

    automation.prepare_one = instrumented
    try:
        yield SimpleNamespace(
            errors=errors,
            refs=refs,
            mode=mode,
            e=e,
            run=run,
            automation=automation,
            authority=authority,
            gen=gen,
            subject=subject,
            adapter=adapter,
            repository=repository,
            services=services,
            policy=policy,
        )
    finally:
        authority.close()


@pytest.mark.parametrize(
    "automation", ["existing", "new", "expanded", "batch"], indirect=True
)
def test_existing_resource_policy_is_real_exact_idempotent_and_has_no_dispatch(
    automation,
):
    a = automation
    result = a.run()
    assert result["state"] == "READY", str(result["resources"]) + str(
        result["assembly"]
    )
    assert result["assembly"]["state"] == "ASSEMBLED"
    if a.mode == "existing":
        assert all(r["case"] == "EXISTING" for r in result["resources"])
    else:
        publications = [r for r in result["resources"] if r["publication"]]
        assert len(publications) == (4 if a.mode == "batch" else 1)
        assert all(
            r["publication"]["policyBasis"]["issuer"]
            == "service:resource-preparation-policy"
            for r in publications
        )
        assert any(
            r["case"] == ("EXPANDED" if a.mode == "expanded" else "NEW")
            for r in publications
        )
    assert (
        result["humanApprovalClicks"] == 0
        and result["modelCalls"] == 0
        and result["newRuns"] == 0
    )
    assert a.run() == result and a.run(read=True) == result
    with a.repository.pool.connection() as c:
        decisions = c.execute(
            "SELECT issuer_principal_id,basis_type FROM authorization_admin.grant_decisions"
        ).fetchall()
        assert decisions and all(
            d
            == {
                "issuer_principal_id": "service:resource-preparation-policy",
                "basis_type": "POLICY",
            }
            for d in decisions
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM execution_authority.workflow_runs"
            ).fetchone()["n"]
            == 0
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM execution_authority.resource_automation"
            ).fetchone()["n"]
            == 1
        )


@pytest.mark.parametrize("automation", ["partial", "bad-schema"], indirect=True)
def test_failed_technical_check_is_not_published_or_assembled_and_partial_success_remains(
    automation,
):
    a = automation
    result = a.run()
    assert result["state"] == "PARTIALLY_READY", str(result) + str(a.errors)
    blocked = [r for r in result["resources"] if r["state"] == "BLOCKED"]
    assert [r["kind"] for r in blocked] == ["skill"]
    ref = a.refs["skill"]
    s = a.services["skill"]
    record = s.repository.get(
        s.scope(a.e.scope.namespace, a.e.scope.security_domain),
        "skill",
        ref.resource_id,
    )
    assert record["publishedRevisionId"] is None
    assert record["revisions"][-1]["state"] == "DRAFT"
    assert not any(f["event"] == "POLICY_REVIEWED" for f in record["facts"])
    assert result["assembly"]["state"] == "BLOCKED"
    before = [r for r in result["resources"] if r["state"] == "READY"]
    assert len(before) == 3
    assert a.run(read=True) == result


@pytest.mark.parametrize(
    "failure",
    [
        "expired-work",
        "foreign-root",
        "foreign-subject",
        "revoked-issuer",
        "bad-credential",
    ],
)
def test_policy_scope_and_real_credential_fail_closed_before_any_decision(
    automation, failure
):
    from dataclasses import replace

    from agent_console.authority_contracts import AuthorityError

    a = automation
    p = a.policy
    if failure == "bad-credential":
        p.credentialPath.write_text("wrong-secret")
    elif failure == "revoked-issuer":
        gen = replace(
            a.gen,
            credential_revocation_tombstones=frozenset({CredentialId("policy-test")}),
        )
        a.automation.grants._generation_provider = lambda: gen
        a.automation.grants.authorization._generation_provider = lambda: gen
    else:
        work = p.workScopes[0]
        if failure == "expired-work":
            work = work.model_copy(
                update={"expiresAt": datetime.now(UTC) - timedelta(seconds=1)}
            )
        elif failure == "foreign-root":
            work = work.model_copy(
                update={"problem": work.problem.model_copy(update={"digest": "b" * 64})}
            )
        else:
            work = work.model_copy(update={"subject": "human:another-user"})
        a.automation.policy = p.model_copy(update={"workScopes": (work,)})
    with pytest.raises(AuthorityError):
        a.run()
    with a.repository.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.grant_decisions"
            ).fetchone()["n"]
            == 0
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM execution_authority.resource_automation"
            ).fetchone()["n"]
            == 0
        )


@pytest.mark.parametrize("automation", ["batch"], indirect=True)
def test_unavailable_native_credential_does_not_publish_any_draft(automation):
    a = automation

    def fail(_):
        raise RuntimeError("unavailable isolated runtime")

    a.automation.runtime_probe = fail
    result = a.run()
    assert result["state"] == "BLOCKED"
    assert all(
        r["reason"] == "NATIVE_RUNTIME_OR_CREDENTIAL_UNAVAILABLE"
        for r in result["resources"]
    )
    for kind, ref in a.refs.items():
        service = a.services[kind]
        scope = service.scope(a.e.scope.namespace, a.e.scope.security_domain)
        record = (
            service.repository.get(scope, "skill", ref.resource_id)
            if kind == "skill"
            else service.repository.get(scope, ref.resource_id)
        )
        assert record["publishedRevisionId"] is None


def test_concurrent_same_request_and_reconstructed_owner_readback_never_repeat_publication(
    automation,
):
    from concurrent.futures import ThreadPoolExecutor

    a = automation
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: a.run("same"), range(3)))
    assert results[0] == results[1] == results[2]
    replacement = ResourceAutomation(
        a.policy,
        a.automation.grants,
        a.e.app,
        a.automation.services,
        a.automation.employees,
        runtime_probe=lambda _: pytest.fail(
            "Recovery GET must not repeat technical effects"
        ),
    )
    a.automation.__dict__.update(replacement.__dict__)
    assert a.run("same", read=True) == results[0]
    with a.repository.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM execution_authority.resource_automation"
            ).fetchone()["n"]
            == 1
        )


def test_revoked_resource_read_withdraws_old_receipt_and_is_not_silently_regranted(
    automation,
):
    from agent_console.authority_contracts import AuthorityError, GrantId
    from agent_console.grant_administration_application import GrantRevocationCommand

    a = automation
    result = a.run()
    ref = a.refs["knowledge"]
    from agent_console.workbench_prepared_resources import reference

    with a.repository.pool.connection() as c:
        grant = c.execute(
            "SELECT grant_id FROM authorization_admin.grants WHERE owner='KNOWLEDGE' AND action='READ_RESOURCE' AND exact_resource=%s",
            (reference("knowledge", ref.resource_id, ref.revision_id),),
        ).fetchone()["grant_id"]
    a.automation.grants.revoke_grant(
        a.subject,
        GrantRevocationCommand(
            GrantId(grant), "USER_REQUESTED", "surrender-exact-read", True
        ),
    )
    with pytest.raises(AuthorityError):
        a.run(read=True)
    second = a.run("new-attempt")
    knowledge = next(r for r in second["resources"] if r["kind"] == "knowledge")
    assert (
        knowledge["state"] == "BLOCKED"
        and knowledge["reason"] == "RESOURCE_PERMISSION_REVOKED"
    )
    assert second["assembly"]["state"] == "BLOCKED"
    assert result["assembly"]["state"] == "ASSEMBLED"


def test_expired_receipt_does_not_waive_current_exact_access(automation):
    from agent_console.authority_contracts import AuthorityError

    a = automation
    a.run()
    future = datetime.now(UTC) + timedelta(minutes=40)
    a.automation.grants.clock = lambda: future
    with pytest.raises(AuthorityError):
        a.run(read=True)


def test_policy_source_change_has_truthful_provenance_and_policy_confirmation_without_model_or_run(
    automation,
):
    from agent_console.plan_suggestion_domain import (
        PolicySourceChangeOrigin,
        ProposalRevision,
    )
    from agent_console.planning_source_change import SourceChangeRequest, read
    from agent_console.sales_resource_bundle import resource_content

    a = automation
    s = a.services["knowledge"]
    scope = s.scope(a.e.scope.namespace, a.e.scope.security_domain)
    alias = s.create(
        scope,
        "agent:isolated-source-preparer",
        "隔离合成同内容替代来源",
        resource_content(a.e.source)["knowledge"],
    )["knowledge"]
    rev = alias["revisions"][0]
    request = SourceChangeRequest(
        plan_version=a.e.p.plan_version,
        plan_digest=a.e.p.plan_digest,
        expected_proposal_revision=a.e.p.plan_version,
        old_source=a.refs["knowledge"],
        new_source={
            "resource_id": alias["knowledgeId"],
            "revision_id": rev["revisionId"],
            "digest": rev["digest"],
        },
        reason="同内容文件替换，保留口径和历史",
        idempotency_key="source-policy",
    )

    def act():
        with a.repository.pool.connection() as c, c.transaction():
            authority = AuthorizedOwnerAuthority(a.adapter, a.subject, c, 1, ())
            call = AuthorizedOwnerCall(
                "AUTOMATE_SOURCE_CHANGE",
                a.subject,
                c,
                request.model_dump(mode="json"),
                {"proposal_id": a.e.p.plan_id},
                {},
                (),
                authority,
                1,
                1,
            )
            value = a.automation.source_change(call)
            app = a.automation.bound_app(call)
            recovered = read(
                app,
                a.e.principal,
                c,
                a.e.p.plan_id,
                request.idempotency_key,
                by_key=True,
            )
            assert recovered["actor"] == "service:resource-preparation-policy"
            assert recovered["subjectActor"] == a.subject.principal_id
            return value

    value = act()
    assert isinstance(
        ProposalRevision.model_validate(value["proposal"]).origin,
        PolicySourceChangeOrigin,
    )
    assert (
        value["policyConfirmation"]["approval"]["actor_id"]
        == "service:resource-preparation-policy"
    )
    assert (
        value["policyConfirmation"]["approval"]["reason_category"]
        == "RESOURCE_POLICY_APPROVAL"
    )
    assert value["confirmationRequired"] is False and value["executionStarted"] is False
    assert act() == value
    with a.repository.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM execution_authority.workflow_runs"
            ).fetchone()["n"]
            == 0
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM workflow_planning.source_changes"
            ).fetchone()["n"]
            == 1
        )


def test_policy_role_selection_keeps_goal_graph_and_standards_and_creates_truthful_successor(
    automation,
):
    from agent_console.digital_employee_definition import EmployeeRevision
    from agent_console.plan_suggestion_domain import (
        PolicyResourcePreparationOrigin,
        ProposalRevision,
    )

    a = automation
    original = next(
        r.selected for r in a.e.p.semantics.requirements if r.kind == "EMPLOYEE"
    )
    repo = a.automation.employees
    with a.repository.pool.connection() as c, c.transaction():
        old = repo._read(c, a.e.scope, original.resource_id, original.revision_id)
        revision = EmployeeRevision.from_record(old["revision"])
        from dataclasses import replace

        revision = replace(
            revision,
            definition_id="employee-definition:second-isolated-role",
            revision_id="employee-revision:second-isolated-role",
        )
        repo.create_for_workbench(
            c,
            revision,
            expected_version=0,
            decision_id="explicit-isolated-setup",
            command_id="isolated-second-role",
            authorized=True,
        )
    body = {
        "version": a.e.p.plan_version,
        "digest": a.e.p.plan_digest,
        "expectedProposalRevision": a.e.p.plan_version,
        "employee": {
            "resource_id": revision.definition_id,
            "revision_id": revision.revision_id,
            "digest": revision.digest,
        },
        "idempotencyKey": "select-resource-role",
    }

    def act():
        with a.repository.pool.connection() as c, c.transaction():
            authority = AuthorizedOwnerAuthority(a.adapter, a.subject, c, 1, ())
            return a.automation.select_employee(
                AuthorizedOwnerCall(
                    "SELECT_POLICY_EMPLOYEE_RESOURCES",
                    a.subject,
                    c,
                    body,
                    {"proposal_id": a.e.p.plan_id},
                    {},
                    (),
                    authority,
                    1,
                    1,
                )
            )

    result = act()
    assert result == act()
    proposal = ProposalRevision.model_validate(result["proposal"])
    assert isinstance(proposal.origin, PolicyResourcePreparationOrigin)
    assert proposal.semantics.target == a.e.p.semantics.target
    assert proposal.semantics.tasks == a.e.p.semantics.tasks
    assert (
        result["confirmation"]["approval"]["actor_id"]
        == "service:resource-preparation-policy"
    )
    assert result["modelCalls"] == 0 and result["newRuns"] == 0
    with a.repository.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM execution_authority.resource_policy_plan_commands"
            ).fetchone()["n"]
            == 1
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM execution_authority.workflow_runs"
            ).fetchone()["n"]
            == 0
        )
    prepared = a.run(
        "selected-resource-preparation",
        version=result["confirmation"]["plan"]["version"],
    )
    assert prepared["state"] == "READY", str(prepared) + str(a.errors)
    assert prepared["assembly"]["definition"] == body["employee"]


def test_out_of_scope_member_is_rejected_before_granting_employee_metadata_access(
    automation,
):
    from agent_console.authority_contracts import AuthorityError

    a = automation
    work = a.policy.workScopes[0].model_copy(
        update={"sourceContentDigests": ("f" * 64,)}
    )
    a.automation.policy = a.policy.model_copy(update={"workScopes": (work,)})
    with pytest.raises(AuthorityError, match="RESOURCE_SOURCE_OUTSIDE_WORK_SCOPE"):
        a.run()
    with a.repository.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.grants WHERE owner='EMPLOYEE'"
            ).fetchone()["n"]
            == 0
        )


@pytest.mark.parametrize("operation", ["prepare", "source", "selection"])
def test_generic_policy_preserves_ontology_binding_before_any_mutation(
    automation, operation
):
    from agent_console.plan_suggestion_domain import (
        OntologyPlanOrigin,
        ProposalRevision,
    )
    from agent_console.planning_source_change import SourceChangeRequest
    from agent_console.workbench_owner_authorization import WorkbenchOwnerError
    from test_plan_suggestion_v2 import confirm

    a = automation
    with a.repository.transaction(a.e.scope, a.e.p.plan_id, authorized=True) as cur:
        previous = a.repository.proposal(
            cur, a.e.scope, a.e.p.plan_id, a.e.p.plan_version
        )
        proposal = ProposalRevision(
            proposal_id=previous.proposal_id,
            revision=previous.revision + 1,
            predecessor_digest=previous.digest,
            invocation_id=None,
            semantics=previous.semantics,
            origin=OntologyPlanOrigin(
                namespace=a.e.scope.namespace,
                security_domain=a.e.scope.security_domain,
                root=previous.semantics.target.problem,
                source_snapshot=a.refs["knowledge"],
                ontology=a.refs["knowledge"],
                mapping_digest="b" * 64,
                prepared_by=a.subject.principal_id,
                request_key="ontology-binding-boundary-test",
            ),
        )
        a.repository.add_proposal(cur, a.e.scope, proposal)
    confirmed = confirm(
        a.repository,
        a.e.scope,
        proposal,
        "ontology-boundary-confirm",
        expected=a.e.p.plan_version,
    )
    plan = confirmed["plan"]
    with a.authority.pool.connection() as c:
        before = c.execute(
            "SELECT count(*) n FROM authorization_admin.grant_decisions"
        ).fetchone()["n"]
    if operation == "prepare":

        def invoke():
            return a.run(version=plan["version"])
    else:
        if operation == "source":
            payload = SourceChangeRequest(
                plan_version=plan["version"],
                plan_digest=confirmed["digest"],
                expected_proposal_revision=proposal.revision,
                old_source=a.refs["knowledge"],
                new_source=a.refs["knowledge"],
                reason="same content must not strip semantic binding",
                idempotency_key="blocked-ontology-source",
            ).model_dump(mode="json")
        else:
            payload = {
                "version": plan["version"],
                "digest": confirmed["digest"],
                "expectedProposalRevision": proposal.revision,
                "employee": next(
                    r.selected
                    for r in proposal.semantics.requirements
                    if r.kind == "EMPLOYEE"
                ).model_dump(mode="json"),
                "idempotencyKey": "blocked-ontology-selection",
            }

        def invoke():
            with a.repository.pool.connection() as c, c.transaction():
                call = AuthorizedOwnerCall(
                    "ONTOLOGY_BOUNDARY_TEST",
                    a.subject,
                    c,
                    payload,
                    {"proposal_id": a.e.p.plan_id},
                    {},
                    (),
                    AuthorizedOwnerAuthority(a.adapter, a.subject, c, 1, ()),
                    1,
                    1,
                )
                return (
                    a.automation.source_change
                    if operation == "source"
                    else a.automation.select_employee
                )(call)

    with pytest.raises(
        WorkbenchOwnerError, match="RESOURCE_POLICY_ONTOLOGY_BINDING_REQUIRED"
    ):
        invoke()
    with a.authority.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.grant_decisions"
            ).fetchone()["n"]
            == before
        )
    with a.repository.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM execution_authority.resource_automation"
            ).fetchone()["n"]
            == 0
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM execution_authority.workflow_runs"
            ).fetchone()["n"]
            == 0
        )
        assert (
            a.repository.proposal(
                c.cursor(), a.e.scope, proposal.proposal_id, proposal.revision
            ).digest
            == proposal.digest
        )


def test_assembly_cannot_report_ready_for_a_different_selected_definition(automation):
    from agent_console.authority_contracts import AuthorityError
    from agent_console.plan_suggestion_domain import ConfirmedPlanRevision
    from agent_console.workbench_business_problem import OwnerPrincipal

    a = automation
    with a.repository.pool.connection() as c, c.transaction():
        call = AuthorizedOwnerCall(
            "ASSEMBLY_BOUNDARY_TEST",
            a.subject,
            c,
            {},
            {"proposal_id": a.e.p.plan_id},
            {},
            (),
            AuthorizedOwnerAuthority(a.adapter, a.subject, c, 1, ()),
            1,
            1,
        )
        app = a.automation.bound_app(call)
        principal = OwnerPrincipal(
            a.subject.principal_id, a.e.scope.namespace, a.e.scope.security_domain
        )
        scope = app.scope(principal)
        with app.repository.transaction(scope, a.e.p.plan_id, authorized=True) as cur:
            plan = ConfirmedPlanRevision.model_validate(
                app.repository.read_plan(cur, scope, a.e.p.plan_id, a.e.p.plan_version)[
                    "plan"
                ]
            )
            work = a.policy.work(
                a.subject, plan.semantics.target.problem, a.automation.grants.clock()
            )
            issuer = a.automation.authenticate(a.subject)
            refs, employee = a.automation.derive(
                call, plan, "assembly-boundary", work, issuer
            )
            before = c.execute(
                "SELECT count(*) n FROM digital_employee_definition.definitions"
            ).fetchone()["n"]
            with pytest.raises(
                AuthorityError, match="RESOURCE_EMPLOYEE_SUCCESSOR_SELECTION_REQUIRED"
            ):
                a.automation.assemble(
                    call,
                    plan,
                    [(kind, ref) for kind, ref in refs if kind != "knowledge"],
                    employee,
                    "assembly-boundary",
                    work,
                    issuer,
                )
            assert (
                c.execute(
                    "SELECT count(*) n FROM digital_employee_definition.definitions"
                ).fetchone()["n"]
                == before
            )


def test_employee_list_entry_target_matches_registered_read_only_collection_route():
    check = PostgresEmployeeDefinitionRepository.is_known_grant_target_for_workbench
    assert check(None, None, "LIST", "employee:collection")
    assert check(None, None, "CREATE", "employee:collection")
    for action in ("READ", "APPROVE", "PUBLISH", "DELETE"):
        assert not check(None, None, action, "employee:collection")
