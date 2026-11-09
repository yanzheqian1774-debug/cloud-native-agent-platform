# ruff: noqa: F401, F811, E501, RUF001 -- Existing SQL fixtures and Chinese product inputs.
from contextlib import nullcontext
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest
from agent_console.authority_configuration import RequestabilityRule
from agent_console.authority_contracts import AuthorityError
from agent_console.resource_definition_management import (
    DefinitionManagement,
    DefinitionPolicy,
    DefinitionScope,
    DefinitionTargets,
    install_definitions,
)
from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
    WorkbenchOwnerError,
)
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation

AGENT = {
    "title": "来源核对职责",
    "duties": ["核对准确版本"],
    "capabilities": ["READ_DATA"],
    "businessPurpose": "维护隔离验证",
}
SOURCE = {
    "sourceId": "maintenance-source",
    "documentId": "maintenance-document",
    "kind": "TEXT",
    "provenance": "synthetic-maintenance-only",
    "content": "隔离合成知识正文，不代表企业资料。",
}


def test_definition_policy_cannot_reinterpret_existing_skill_management_configuration():
    from datetime import UTC, datetime

    from agent_console.resource_management import ManagementPolicy, ManagementScope
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ManagementScope(
            namespace="fixture",
            securityDomain="isolated",
            subject="human:fixture",
            kinds=("knowledge",),
            expiresAt=datetime.now(UTC),
        )
    with pytest.raises(ValidationError):
        DefinitionPolicy.model_validate(
            ManagementPolicy(
                enabled=False,
                policyId="old",
                policyVersion="1",
                issuer="service:fixture",
                credentialPath="/not-read",
                workScopes=(),
            ).model_dump()
        )


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"content": " "}, "EMPTY_SOURCE_CONTENT"),
        ({"content": "字" * 1400}, "CHUNK_LIMIT_EXCEEDED"),
        ({"provenance": "不支持的出处"}, "INVALID_PROVENANCE"),
    ],
)
def test_knowledge_invalid_input_is_rejected_without_resource_or_receipt(
    definitions, change, reason
):
    a, _ = definitions
    with a.repository.pool.connection() as c:
        before = c.execute(
            "SELECT count(*) n FROM knowledge_operation.knowledge"
        ).fetchone()["n"]
        grant_count = c.execute(
            "SELECT count(*) n FROM authorization_admin.grants"
        ).fetchone()["n"]
    with pytest.raises(WorkbenchOwnerError, match=reason) as error:
        command(
            definitions,
            "knowledge",
            "create",
            key="invalid-content-not-unknown",
            name="需修正输入",
            source={**SOURCE, **change},
        )
    assert error.value.status_code == 422
    with a.repository.pool.connection() as c:
        assert (
            c.execute("SELECT count(*) n FROM authorization_admin.grants").fetchone()[
                "n"
            ]
            == grant_count
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM knowledge_operation.knowledge"
            ).fetchone()["n"]
            == before
        )
        assert not c.execute(
            "SELECT 1 FROM execution_authority.prepared_resource_commands WHERE command_key='definition-management:invalid-content-not-unknown'"
        ).fetchone()


@pytest.fixture
def definitions(automation):
    a = automation
    g = a.automation.grants
    extra = tuple(
        RequestabilityRule(owner, action, prefix, "RESOURCE_MANAGEMENT")
        for owner, prefix in [("AGENT", "agent:"), ("KNOWLEDGE", "knowledge:")]
        for action in [
            "CREATE_RESOURCE",
            "MANAGE_RESOURCE",
            "READ_RESOURCE",
            "REVIEW_PUBLISH_RESOURCE",
        ]
    )
    gen = replace(a.gen, requestability=a.gen.requestability + extra)
    g._generation_provider = lambda: gen
    g.authorization._generation_provider = lambda: gen
    g.target_validator.additional += (DefinitionTargets(),)
    a.adapter.controller.protected_request = lambda: nullcontext(
        SimpleNamespace(generation=1)
    )
    policy = DefinitionPolicy(
        enabled=True,
        policyId="isolated-definitions",
        policyVersion="1",
        issuer=a.policy.issuer,
        credentialPath=a.policy.credentialPath,
        workScopes=(
            DefinitionScope(
                namespace=a.subject.scope.tenant_id,
                securityDomain=a.subject.scope.security_domain,
                subject=a.subject.principal_id,
                kinds=("agent", "knowledge"),
                expiresAt=g.clock() + timedelta(hours=1),
            ),
        ),
    )
    return a, DefinitionManagement(
        {**a.services, "mcp": a.services["skill"]}, policy, g
    )


def command(pair, kind, action, *, key=None, **payload):
    a, m = pair
    with a.authority.connection_scope() as c:
        return m.handle(
            AuthorizedOwnerCall(
                "DEFINITION_MANAGEMENT",
                a.subject,
                c,
                {
                    "action": action,
                    "commandKey": key or kind + "-" + action + "-once",
                    **payload,
                },
                {"kind": kind},
                {},
                (),
                AuthorizedOwnerAuthority(a.adapter, a.subject, c, 1, ()),
                1,
                1,
            )
        )


@pytest.mark.parametrize("kind", ["agent", "knowledge"])
def test_publication_successor_replay_preserves_records_without_execution(
    definitions, kind
):
    a, m = definitions
    content = {"content": AGENT} if kind == "agent" else {"source": SOURCE}
    created = command(definitions, kind, "create", name="维护副本", **content)
    assert created == command(definitions, kind, "create", name="维护副本", **content)
    with pytest.raises(WorkbenchOwnerError, match="CONFLICT"):
        command(definitions, kind, "create", name="参数变化", **content)
    r, identity = created["resource"], created["identity"]
    published = command(
        definitions,
        kind,
        "publish",
        identity=identity,
        expectedVersion=r["aggregateVersion"],
    )["resource"]
    old = next(
        r
        for r in published["revisions"]
        if r["revisionId"] == published["publishedRevisionId"]
    )
    assert old["state"] == "PUBLISHED"
    if kind == "knowledge":
        assert not published["indexSnapshots"] and not published["retrievals"]
        assert published["activeIndexSnapshotId"] is None
    else:
        assert published["reviews"][-1]["actor"] == m.policy.issuer
    successor = command(
        definitions,
        kind,
        "successor",
        identity=identity,
        expectedVersion=published["aggregateVersion"],
        **({"successorContent": "后继合成资料"} if kind == "knowledge" else {}),
    )["resource"]
    assert successor["publishedRevisionId"] == old["revisionId"]
    assert old == next(
        r for r in successor["revisions"] if r["revisionId"] == old["revisionId"]
    )
    assert successor["currentDraftRevisionId"] != old["revisionId"]
    with a.authority.connection_scope() as c:
        call = AuthorizedOwnerCall(
            "DEFINITION_MANAGEMENT",
            a.subject,
            c,
            {},
            {"kind": kind},
            {},
            (),
            AuthorizedOwnerAuthority(a.adapter, a.subject, c, 1, ()),
            1,
            1,
        )
        assert m.receipt(call, kind, created["commandKey"]) == created
        assert len(m.directory(call)["items"]) == 1
        assert (
            c.execute(
                "SELECT count(*) n FROM execution_authority.workflow_runs"
            ).fetchone()["n"]
            == 0
        )
        assert (
            c.execute(
                "SELECT to_regclass('workflow_planning.invocations') t"
            ).fetchone()["t"]
            is None
        )


def test_agent_binding_uses_current_exact_knowledge_read_and_never_upgrades_it(
    definitions,
):
    a, _ = definitions
    k = command(definitions, "knowledge", "create", name="绑定知识", source=SOURCE)
    k = command(
        definitions, "knowledge", "publish", identity=k["identity"], expectedVersion=1
    )
    kr = next(
        r
        for r in k["resource"]["revisions"]
        if r["revisionId"] == k["resource"]["publishedRevisionId"]
    )
    content = {
        **AGENT,
        "bindings": {
            "knowledge": [
                {
                    "resourceId": k["identity"],
                    "revisionId": kr["revisionId"],
                    "digest": kr["digest"],
                }
            ]
        },
    }
    agent = command(
        definitions, "agent", "create", name="准确绑定Agent", content=content
    )
    published = command(
        definitions, "agent", "publish", identity=agent["identity"], expectedVersion=1
    )
    assert (
        published["resource"]["revisions"][-1]["bindingValidation"][
            "verifiedReferences"
        ][0]["revisionId"]
        == kr["revisionId"]
    )
    successor = command(
        definitions,
        "knowledge",
        "successor",
        identity=k["identity"],
        expectedVersion=k["aggregateVersion"],
        successorContent="知识后继正文",
    )
    command(
        definitions,
        "knowledge",
        "publish",
        key="knowledge-next-publish",
        identity=k["identity"],
        expectedVersion=successor["aggregateVersion"],
    )
    draft = command(
        definitions,
        "agent",
        "successor",
        identity=agent["identity"],
        expectedVersion=published["aggregateVersion"],
    )
    with pytest.raises(
        WorkbenchOwnerError, match="BOUND_REVISION_NOT_CURRENT_PUBLISHED"
    ):
        command(
            definitions,
            "agent",
            "publish",
            key="agent-not-auto-upgraded",
            identity=agent["identity"],
            expectedVersion=draft["aggregateVersion"],
        )
    scope = a.services["agent"].scope(
        a.subject.scope.tenant_id, a.subject.scope.security_domain
    )
    current = a.services["agent"].repository.get(scope, agent["identity"])
    assert (
        current["publishedRevisionId"] == published["resource"]["publishedRevisionId"]
    )
    assert (
        current["revisions"][-1]["content"]["bindings"]["knowledge"][0]["revisionId"]
        == kr["revisionId"]
    )


def test_strict_kind_payload_policy_scope_and_foreign_ownership(definitions):
    a, m = definitions
    for kind, payload in [
        ("knowledge", {"content": AGENT}),
        ("agent", {"source": SOURCE}),
        ("agent", {"content": {**AGENT, "token": "not-a-credential"}}),
    ]:
        with pytest.raises(WorkbenchOwnerError, match="INVALID"):
            command(definitions, kind, "create", name="不应创建", **payload)
    r = command(definitions, "agent", "create", name="原创建者", content=AGENT)
    with pytest.raises(WorkbenchOwnerError, match="NOT_FOUND"):
        command(
            definitions,
            "knowledge",
            "validate",
            identity=r["identity"],
            expectedVersion=1,
        )
    with pytest.raises(AuthorityError):
        m.scope(replace(a.subject, principal_id="human:another"), "agent")
    m.policy = m.policy.model_copy(update={"enabled": False})
    with pytest.raises(AuthorityError):
        command(definitions, "agent", "access", identity=r["identity"])


def test_http_session_csrf_original_receipt_and_no_legacy_identity(definitions):
    from fastapi.testclient import TestClient
    from test_workbench_bff import SessionStub

    a, m = definitions
    s = SessionStub()
    s.context = a.subject
    app = create_workbench_bff(
        s,
        a.adapter,
        WorkbenchBffPolicy("workbench.example", "https://workbench.example"),
        route_installers=(install_definitions(m, a.adapter),),
    )
    with TestClient(app, base_url="https://workbench.example") as client:
        root = "/api/workbench/v1/definition-management/knowledge"
        assert client.get(root).status_code == 401
        client.cookies.set("__Host-workbench_session", s.secret)
        body = {
            "action": "create",
            "commandKey": "http-original-key",
            "name": "当前账号知识",
            "source": SOURCE,
        }
        assert client.post(root + "/commands", json=body).status_code == 403
        headers = {"Origin": "https://workbench.example", "X-CSRF-Token": "csrf-token"}
        bad = {
            **body,
            "commandKey": "http-invalid-source",
            "source": {**SOURCE, "content": " "},
        }
        rejected = client.post(root + "/commands", json=bad, headers=headers)
        assert (
            rejected.status_code == 422
            and rejected.json()["reasonCode"] == "EMPTY_SOURCE_CONTENT"
        )
        assert client.get(root + "/commands/http-invalid-source").status_code == 404
        response = client.post(root + "/commands", json=body, headers=headers)
        assert response.status_code == 200, response.text
        assert (
            client.get(root + "/commands/http-original-key").json() == response.json()
        )
        assert len(client.get(root).json()["result"]["items"]) == 1
        assert client.get(root, headers={"X-Tenant-ID": "foreign"}).status_code == 400
        assert client.get(root + "/commands/unrelated-key").status_code == 404


@pytest.mark.parametrize("action", ["MANAGE_RESOURCE", "READ_RESOURCE"])
def test_revocation_is_not_regranted_by_access_or_result_recovery(definitions, action):
    from agent_console.authority_contracts import GrantId
    from agent_console.grant_administration_application import GrantRevocationCommand
    from agent_console.resource_definition_management import target
    from agent_console.workbench_prepared_resources import reference

    a, m = definitions
    r = command(
        definitions, "knowledge", "create", name="撤权保持原记录", source=SOURCE
    )
    exact = (
        target("knowledge", r["identity"])
        if action == "MANAGE_RESOURCE"
        else reference(
            "knowledge", r["identity"], r["resource"]["revisions"][0]["revisionId"]
        )
    )
    with a.repository.pool.connection() as c:
        grant = c.execute(
            "SELECT grant_id FROM authorization_admin.grants WHERE owner='KNOWLEDGE' AND action=%s AND exact_resource=%s",
            (action, exact),
        ).fetchone()["grant_id"]
    m.grants.revoke_grant(
        a.subject,
        GrantRevocationCommand(
            GrantId(grant), "USER_REQUESTED", "exact-knowledge-revoked", True
        ),
    )
    with pytest.raises(AuthorityError, match="RESOURCE_PERMISSION_REVOKED"):
        command(definitions, "knowledge", "access", identity=r["identity"])


def test_result_grant_failure_rolls_back_definition_and_original_command(
    definitions, monkeypatch
):
    a, m = definitions
    with a.repository.pool.connection() as c:
        before = c.execute(
            "SELECT count(*) n FROM knowledge_operation.knowledge"
        ).fetchone()["n"]
    original = m.authorize

    def authorize(call, members, key, work, issuer):
        if key.endswith(":result-access"):
            raise AuthorityError("RESOURCE_PERMISSION_REVOKED")
        return original(call, members, key, work, issuer)

    monkeypatch.setattr(m, "authorize", authorize)
    with pytest.raises(AuthorityError):
        command(
            definitions,
            "knowledge",
            "create",
            key="atomic-create-denied",
            name="不应留部分资源",
            source=SOURCE,
        )
    with a.repository.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM knowledge_operation.knowledge"
            ).fetchone()["n"]
            == before
        )
        assert not c.execute(
            "SELECT 1 FROM execution_authority.prepared_resource_commands WHERE command_key='definition-management:atomic-create-denied'"
        ).fetchone()


@pytest.mark.parametrize("kind", ["agent", "knowledge"])
def test_exact_reference_projection_never_substitutes_new_draft(definitions, kind):
    from agent_console.workbench_resource_directory import ResourceDirectory

    a, _ = definitions
    r = command(
        definitions,
        kind,
        "create",
        name="精确引用根",
        **({"content": AGENT} if kind == "agent" else {"source": SOURCE}),
    )
    r = command(
        definitions,
        kind,
        "publish",
        identity=r["identity"],
        expectedVersion=r["aggregateVersion"],
    )
    old = next(
        x
        for x in r["resource"]["revisions"]
        if x["revisionId"] == r["resource"]["publishedRevisionId"]
    )
    command(
        definitions,
        kind,
        "successor",
        identity=r["identity"],
        expectedVersion=r["aggregateVersion"],
        **({"successorContent": "后继正文"} if kind == "knowledge" else {}),
    )
    with a.authority.connection_scope() as c:
        call = AuthorizedOwnerCall(
            "READ_DIRECTORY_REFERENCES",
            a.subject,
            c,
            {},
            {"kind": kind, "identity": r["identity"], "revision": old["revisionId"]},
            {},
            (),
            AuthorizedOwnerAuthority(a.adapter, a.subject, c, 1, ()),
            1,
            1,
        )
        value = ResourceDirectory(a.services, None)(call)
        assert (
            value["revision"] == old["revisionId"] and value["digest"] == old["digest"]
        )
        assert "revisions" not in value
        assert value["subject"] == a.subject.principal_id


def test_agent_edit_retains_prior_draft_and_invalid_exact_binding_cannot_publish(
    definitions,
):
    from agent_console.workbench_prepared_resources import reference

    a, _ = definitions
    k = command(definitions, "knowledge", "create", name="准确知识", source=SOURCE)
    k = command(
        definitions, "knowledge", "publish", identity=k["identity"], expectedVersion=1
    )
    kr = next(
        x
        for x in k["resource"]["revisions"]
        if x["revisionId"] == k["resource"]["publishedRevisionId"]
    )
    r = command(definitions, "agent", "create", name="可修复Agent", content=AGENT)
    old = r["resource"]["revisions"][0]
    bad = {
        **AGENT,
        "bindings": {
            "knowledge": [
                {
                    "resourceId": k["identity"],
                    "revisionId": kr["revisionId"],
                    "digest": "0" * 64,
                }
            ]
        },
    }
    edited = command(
        definitions,
        "agent",
        "edit",
        identity=r["identity"],
        expectedVersion=1,
        content=bad,
    )
    assert old == edited["resource"]["revisions"][0]
    with pytest.raises(WorkbenchOwnerError, match="BOUND_RESOURCE_DIGEST_MISMATCH"):
        command(
            definitions,
            "agent",
            "publish",
            identity=r["identity"],
            expectedVersion=edited["aggregateVersion"],
        )
    with pytest.raises(WorkbenchOwnerError, match="STALE"):
        command(
            definitions,
            "agent",
            "edit",
            key="stale-agent-edit",
            identity=r["identity"],
            expectedVersion=1,
            content=AGENT,
        )
    scope = a.services["agent"].scope(
        a.subject.scope.tenant_id, a.subject.scope.security_domain
    )
    current = a.services["agent"].repository.get(scope, r["identity"])
    assert current["publishedRevisionId"] is None
    assert len(current["revisions"]) == 2


def test_typed_employee_pins_published_definitions_without_dispatch(definitions):
    """Disposable owner composition; the explicit fixture grant is not real IAM."""
    from agent_console.digital_employee_definition import (
        CompositionMember,
        EmployeeRevision,
        MemberKind,
    )
    from agent_console.workbench_resource_directory import ResourceDirectory

    a, _ = definitions
    records = {}
    for kind, payload in [
        ("knowledge", {"source": SOURCE}),
        ("agent", {"content": AGENT}),
    ]:
        r = command(definitions, kind, "create", name="装配核对" + kind, **payload)
        r = command(
            definitions, kind, "publish", identity=r["identity"], expectedVersion=1
        )
        records[kind] = (
            r,
            next(
                x
                for x in r["resource"]["revisions"]
                if x["revisionId"] == r["resource"]["publishedRevisionId"]
            ),
        )
    employee = EmployeeRevision(
        a.e.scope,
        "employee-definition:definition-maintenance",
        "employee-revision:definition-maintenance",
        "知识与Agent准确引用",
        ("隔离维护，不执行",),
        tuple(
            CompositionMember(
                MemberKind.AGENT if kind == "agent" else MemberKind.KNOWLEDGE,
                r["identity"],
                rev["revisionId"],
                rev["digest"],
            )
            for kind, (r, rev) in records.items()
        ),
    )
    with a.repository.pool.connection() as c, c.transaction():
        a.automation.employees.create_for_workbench(
            c,
            employee,
            expected_version=0,
            decision_id="isolated-fixture-create-only",
            command_id="isolated-definition-employee-create",
            authorized=True,
        )
    for kind, (r, rev) in records.items():
        command(
            definitions,
            kind,
            "successor",
            identity=r["identity"],
            expectedVersion=r["aggregateVersion"],
            **(
                {"successorContent": "保留旧引用后的新正文"}
                if kind == "knowledge"
                else {}
            ),
        )
        with a.authority.connection_scope() as c:
            real = AuthorizedOwnerAuthority(a.adapter, a.subject, c, 1, ())

            def require(principal, owner, action, exact, real=real):
                if (owner, action, exact) == (
                    "EMPLOYEE",
                    "READ",
                    f"employee:{employee.definition_id}:{employee.revision_id}",
                ):
                    return SimpleNamespace(decision_id="isolated-fixture-read-only")
                return real.require(principal, owner, action, exact)

            call = AuthorizedOwnerCall(
                "READ_DIRECTORY_REFERENCES",
                a.subject,
                c,
                {},
                {
                    "kind": kind,
                    "identity": r["identity"],
                    "revision": rev["revisionId"],
                },
                {},
                (),
                SimpleNamespace(require=require),
                1,
                1,
            )
            data = ResourceDirectory(a.services, None)(call)
            consumer = next(
                x
                for x in data["dependencies"]["incoming"]
                if x["identity"] == employee.definition_id
            )
            assert (
                consumer["targetRevision"] == rev["revisionId"]
                and consumer["versionRelation"] == "CURRENT_VERSION"
            )
            saved = a.automation.employees.read_revision_for_workbench(
                c,
                employee.scope,
                employee.definition_id,
                employee.revision_id,
                authorized=True,
            )
            assert any(
                m["resource_id"] == r["identity"]
                and m["revision_id"] == rev["revisionId"]
                and m["digest"] == rev["digest"]
                for m in saved["revision"]["members"]
            )
            assert (
                c.execute(
                    "SELECT count(*) n FROM execution_authority.workflow_runs"
                ).fetchone()["n"]
                == 0
            )


def test_knowledge_snapshot_binding_requires_same_published_revision(definitions):
    """Explicit fake-index setup; no real indexing or hidden publication effect."""
    a, _ = definitions

    class IndexFixture:
        collection = "isolated-explicit-index-fixture"
        upserts = 0

        def ensure_collection(self):
            pass

        def upsert(self, points):
            assert points
            self.upserts += 1

    index = IndexFixture()
    service = a.services["knowledge"]
    service.qdrant = index
    k = command(definitions, "knowledge", "create", name="索引版本核对", source=SOURCE)
    k = command(
        definitions, "knowledge", "publish", identity=k["identity"], expectedVersion=1
    )
    assert index.upserts == 0
    scope = service.scope(a.subject.scope.tenant_id, a.subject.scope.security_domain)
    indexed = service.ingest(
        scope, k["identity"], a.subject.principal_id, k["aggregateVersion"]
    )["knowledge"]
    snapshot = indexed["indexSnapshots"][-1]
    first = next(
        r
        for r in indexed["revisions"]
        if r["revisionId"] == indexed["publishedRevisionId"]
    )

    def content(revision):
        return {
            **AGENT,
            "bindings": {
                "knowledge": [
                    {
                        "resourceId": k["identity"],
                        "revisionId": revision["revisionId"],
                        "digest": revision["digest"],
                        "snapshotId": snapshot["snapshotId"],
                    }
                ]
            },
        }

    agent = command(
        definitions, "agent", "create", name="当前索引引用", content=content(first)
    )
    command(
        definitions, "agent", "publish", identity=agent["identity"], expectedVersion=1
    )
    successor = command(
        definitions,
        "knowledge",
        "successor",
        identity=k["identity"],
        expectedVersion=indexed["aggregateVersion"],
        successorContent="新发布正文尚未建立新索引",
    )
    second = command(
        definitions,
        "knowledge",
        "publish",
        key="snapshot-second-publication",
        identity=k["identity"],
        expectedVersion=successor["aggregateVersion"],
    )
    revision = next(
        r
        for r in second["resource"]["revisions"]
        if r["revisionId"] == second["resource"]["publishedRevisionId"]
    )
    bad = command(
        definitions,
        "agent",
        "create",
        key="old-index-new-revision-create",
        name="旧索引不可套新版本",
        content=content(revision),
    )
    with pytest.raises(WorkbenchOwnerError, match="BOUND_SNAPSHOT_NOT_FOUND"):
        command(
            definitions,
            "agent",
            "publish",
            key="old-index-new-revision-rejected",
            identity=bad["identity"],
            expectedVersion=1,
        )
    assert index.upserts == 1


@pytest.mark.parametrize("kind", ["knowledge", "agent"])
def test_d12_role_publication_uses_actual_admin_and_no_grant_queue(
    definitions, monkeypatch, kind
):
    # Publication-owner integration: authentication/revocation of the role is
    # exercised separately against real local sessions in test_development_administrator.
    import agent_console.development_administrator as role

    a, manager = definitions
    a.subject = replace(a.subject, principal_id="human:development-admin")
    monkeypatch.setattr(
        role,
        "for_service",
        lambda service, ctx, connection=None: (
            ctx.principal_id == "human:development-admin"
        ),
    )
    monkeypatch.setattr(
        role,
        "for_call",
        lambda call: call.context.principal_id == "human:development-admin",
    )
    monkeypatch.setattr(
        a.adapter.authorization,
        "has_current_grants",
        lambda context, grants, **kwargs: tuple(True for _ in grants),
    )
    manager.policy = manager.policy.model_copy(
        update={"enabled": False, "workScopes": ()}
    )

    def requests():
        with a.authority.connection_scope() as c:
            return c.execute(
                "SELECT count(*) n FROM authorization_admin.grant_requests"
            ).fetchone()["n"]

    before = requests()
    payload = {"source": SOURCE} if kind == "knowledge" else {"content": AGENT}
    created = command(
        (a, manager),
        kind,
        "create",
        name="D12 administrator publication",
        key="d12-" + kind + "-create",
        **payload,
    )
    validated = command(
        (a, manager),
        kind,
        "validate",
        identity=created["identity"],
        expectedVersion=created["aggregateVersion"],
        key="d12-" + kind + "-validate",
    )
    published = command(
        (a, manager),
        kind,
        "publish",
        identity=created["identity"],
        expectedVersion=validated["aggregateVersion"],
        key="d12-" + kind + "-publish",
    )
    replayed = command(
        (a, manager),
        kind,
        "publish",
        identity=created["identity"],
        expectedVersion=validated["aggregateVersion"],
        key="d12-" + kind + "-publish",
    )
    assert replayed == published
    assert requests() == before
    assert published["policyIssuer"] == "human:development-admin"
    record = published["resource"]
    assert record["publishedRevisionId"] is not None
    with a.authority.connection_scope() as c:
        receipts = c.execute(
            "SELECT result FROM execution_authority.prepared_resource_commands WHERE actor_id='human:development-admin' AND result ? 'policyBasis'"
        ).fetchall()
        assert any(
            r["result"]["policyBasis"]["type"] == "DEVELOPMENT_ADMINISTRATOR"
            for r in receipts
        )
    if kind == "knowledge":
        with pytest.raises(WorkbenchOwnerError, match="EMPTY_SOURCE_CONTENT"):
            command(
                (a, manager),
                kind,
                "create",
                name="Invalid D12",
                key="d12-invalid",
                source={**SOURCE, "content": " "},
            )
    assert requests() == before
