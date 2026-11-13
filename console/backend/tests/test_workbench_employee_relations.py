# ruff: noqa: F401,F811 -- Existing explicit disposable PostgreSQL fixtures.
"""Real owner SQL/BFF reads; exact fixture grants are not real IAM acceptance."""

import base64
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from agent_console.digital_employee_application import (
    AssignmentLifecycle,
    AssignmentRecord,
    DefinitionReference,
    InstanceLifecycle,
    InstanceRecord,
)
from agent_console.digital_employee_definition import (
    CompositionMember,
    EmployeeRevision,
    MemberKind,
)
from agent_console.digital_employee_definition_postgres import (
    PostgresEmployeeDefinitionRepository,
)
from agent_console.digital_employee_postgres import PostgresDigitalEmployeeRepository
from agent_console.execution_postgres import (
    AssignmentId,
    DigitalEmployeeInstanceId,
    PostgresExecutionAuthorityRepository,
)
from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
from agent_console.workbench_employee_relations import operations
from agent_console.workbench_owner_authorization import AuthorizedOwnerCall
from agent_console.workbench_pagination import WorkbenchCursorCodec
from fastapi.testclient import TestClient
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation
from test_sales_supplement_owners import (
    ExactFixtureAuthority,
    snapshot,
)
from test_workbench_bff import SessionStub


@pytest.fixture
def relations(automation):
    a = automation
    ref = next(r.selected for r in a.e.p.semantics.requirements if r.kind == "EMPLOYEE")
    definitions = PostgresEmployeeDefinitionRepository(a.repository)
    with a.repository.pool.connection() as c:
        old = definitions.read_revision_for_workbench(
            c, a.e.scope, ref.resource_id, ref.revision_id, authorized=True
        )
    revision = old["revision"]
    agent = next(m for m in revision["members"] if m["kind"] == "AGENT")
    reference = DefinitionReference(
        ref.resource_id,
        ref.revision_id,
        ref.digest,
        True,
        True,
        "DIGITAL_EMPLOYEE_DEFINITION_V1",
        agent["resource_id"],
        agent["revision_id"],
        agent["digest"],
    )
    authority = PostgresExecutionAuthorityRepository(
        a.repository.pool.conninfo,
        migration_path=Path(__file__).parents[1]
        / "migrations/0008_execution_runtime_authority.sql",
    )
    instances = PostgresDigitalEmployeeRepository(authority)
    now = datetime.now(UTC)
    try:
        for identity in ["instance:relations-1", "instance:relations-2"]:
            instances.create_instance(
                InstanceRecord(
                    a.e.scope,
                    DigitalEmployeeInstanceId(identity),
                    1,
                    reference,
                    "human:isolated-owner",
                    "isolated-unit",
                    InstanceLifecycle.ENABLED,
                    None,
                    None,
                    (),
                    now,
                    now,
                ),
                "fixture-create-" + identity,
            )
        for ordinal, parent in [
            (1, "instance:relations-1"),
            (2, "instance:relations-2"),
        ]:
            instances.create_assignment(
                AssignmentRecord(
                    a.e.scope,
                    AssignmentId("assignment:relations-" + str(ordinal)),
                    DigitalEmployeeInstanceId(parent),
                    "human:isolated-owner",
                    "隔离关联只读验证",
                    AssignmentLifecycle.ACTIVE,
                    now,
                    None,
                    1,
                    "fixture-assignment-" + str(ordinal),
                )
            )
        successor = EmployeeRevision(
            a.e.scope,
            ref.resource_id,
            "revision:relations-successor",
            revision["role"],
            tuple(revision["responsibilities"]),
            tuple(
                CompositionMember(
                    MemberKind(m["kind"]),
                    m["resource_id"],
                    m["revision_id"],
                    m["digest"],
                )
                for m in revision["members"]
            ),
            ref.revision_id,
        )
        with a.repository.pool.connection() as c, c.transaction():
            definitions.create_for_workbench(
                c,
                successor,
                expected_version=old["aggregateVersion"],
                decision_id="explicit-isolated-fixture-setup",
                command_id="fixture-history-successor",
                authorized=True,
            )
        allowed = {
            ("EMPLOYEE", "READ", f"employee:{ref.resource_id}:{r}")
            for r in [ref.revision_id, successor.revision_id]
        }
        allowed |= {
            ("INSTANCE", "READ", "instance:instance:relations-" + str(i))
            for i in [1, 2]
        }
        allowed |= {
            ("ASSIGNMENT", "READ", "assignment:assignment:relations-" + str(i))
            for i in [1, 2]
        }
        acl = ExactFixtureAuthority(a.subject.principal_id, allowed)
        yield SimpleNamespace(
            a=a,
            definitions=definitions,
            instances=instances,
            acl=acl,
            ref=ref,
            successor=successor,
            root=f"/api/workbench/v1/employees/{ref.resource_id}/revisions/{ref.revision_id}",
        )
    finally:
        authority.pool.close()


def client(r, context=None):
    subject = context or r.a.subject
    # Explicit read-only projection fixture; never grants mutation by default.
    r.acl.current_action_grants = lambda grants: tuple(
        (grant.owner, grant.action, grant.exact_resource) in r.acl.allowed
        for grant in grants
    )
    r.acl.generation = 1
    observed_at = datetime.now(UTC)
    r.acl.adapter = SimpleNamespace(
        clock=lambda: observed_at,
        controller=SimpleNamespace(readiness=SimpleNamespace(recovery_epoch=1)),
    )
    sessions = SessionStub(subject.principal_id)
    sessions.context = subject

    class Authorizer:
        def execute(self, context, grants, **values):
            for grant in grants:
                r.acl.require(context, grant.owner, grant.action, grant.exact_resource)
            with (
                r.a.repository.pool.connection() as connection,
                connection.transaction(),
            ):
                return values["handler"](
                    AuthorizedOwnerCall(
                        operation=values["operation"],
                        context=context,
                        connection=connection,
                        payload=values["payload"],
                        path=values["path"],
                        query=values["query"],
                        decisions=(),
                        authority=r.acl,
                    )
                )

    app = create_workbench_bff(
        sessions,
        Authorizer(),
        WorkbenchBffPolicy("review.test", "https://review.test"),
        operations=operations(
            r.definitions, r.instances, WorkbenchCursorCodec(b"r" * 32)
        ),
    )
    result = TestClient(app, base_url="https://review.test")
    result.cookies.set("__Host-workbench_session", sessions.secret)
    return result


def read(c, path, **params):
    response = c.get(path, params=params)
    assert response.status_code == 200, response.text
    return response.json()["result"]


def test_history_pagination_uses_exact_parent_current_acl_and_no_effects(relations):
    r = relations
    before = snapshot(r.a)
    with client(r) as c:
        first = read(c, r.root + "/history", pageSize=1)
        assert first["items"][0]["employeeDefinitionRevisionId"] == r.ref.revision_id
        assert first["nextCursor"] and first["visibility"] == "AUTHORIZED_ONLY"
        second = read(c, r.root + "/history", pageSize=1, cursor=first["nextCursor"])
        assert (
            second["items"][0]["employeeDefinitionRevisionId"]
            == r.successor.revision_id
        )
        assert not second["nextCursor"] and not second["scanLimited"]
        r.acl.allowed.remove(
            (
                "EMPLOYEE",
                "READ",
                f"employee:{r.ref.resource_id}:{r.successor.revision_id}",
            )
        )
        revoked = read(c, r.root + "/history", pageSize=1, cursor=first["nextCursor"])
        assert revoked["items"] == []
        r.acl.allowed.remove(
            ("EMPLOYEE", "READ", f"employee:{r.ref.resource_id}:{r.ref.revision_id}")
        )
        assert c.get(r.root + "/history").status_code == 404
    assert snapshot(r.a) == before


def test_instances_and_assignments_are_parent_exact_and_not_execution_claims(relations):
    r = relations
    before = snapshot(r.a)
    with client(r) as c:
        values = read(c, r.root + "/instances")
        assert [v["instanceId"] for v in values["items"]] == [
            "instance:relations-1",
            "instance:relations-2",
        ]
        assert all(v["health"]["state"] == "UNAVAILABLE" for v in values["items"])
        assert all(v["execution"]["state"] == "UNAVAILABLE" for v in values["items"])
        result = read(c, "/api/workbench/v1/instances/instance:relations-1/assignments")
        assert [v["assignmentId"] for v in result["items"]] == [
            "assignment:relations-1"
        ]
        assert result["items"][0]["binding"]["state"] == "UNAVAILABLE"
        r.acl.allowed.remove(
            ("ASSIGNMENT", "READ", "assignment:assignment:relations-1")
        )
        assert (
            read(c, "/api/workbench/v1/instances/instance:relations-1/assignments")[
                "items"
            ]
            == []
        )
        r.acl.allowed.remove(("INSTANCE", "READ", "instance:instance:relations-1"))
        assert (
            c.get(
                "/api/workbench/v1/instances/instance:relations-1/assignments"
            ).status_code
            == 404
        )
    assert snapshot(r.a) == before


@pytest.mark.parametrize("mode", ["parent", "relation", "page-size", "tamper", "actor"])
def test_relation_cursor_is_bound_and_cannot_disclose_a_different_parent(
    relations, mode
):
    r = relations
    with client(r) as c:
        first = read(c, r.root + "/history", pageSize=1)
        path, cursor, size = r.root + "/history", first["nextCursor"], 1
        if mode == "parent":
            path = path.replace(r.ref.revision_id, r.successor.revision_id)
        if mode == "relation":
            path = r.root + "/instances"
        if mode == "page-size":
            size = 2
        if mode == "tamper":
            cursor += "0"
        if mode == "actor":
            other = replace(r.a.subject, principal_id="human:other-fixture")
            r.acl = ExactFixtureAuthority(other.principal_id, r.acl.allowed)
            with client(r, other) as changed:
                assert (
                    changed.get(
                        path, params={"cursor": cursor, "pageSize": size}
                    ).status_code
                    == 422
                )
            return
        assert (
            c.get(path, params={"cursor": cursor, "pageSize": size}).status_code == 422
        )


def test_foreign_tenant_cannot_read_identical_parent_or_instances(relations):
    r = relations
    other = replace(r.a.subject, scope=replace(r.a.subject.scope, tenant_id="foreign"))
    with client(r, other) as c:
        assert c.get(r.root + "/history").status_code == 404
        assert c.get(r.root + "/instances").status_code == 404


def test_hidden_identity_never_appears_in_items_or_cursor(relations):
    r = relations
    r.acl.allowed.remove(("INSTANCE", "READ", "instance:instance:relations-1"))
    with client(r) as c:
        value = read(c, r.root + "/instances", pageSize=1)
        assert [x["instanceId"] for x in value["items"]] == ["instance:relations-2"]
        assert not value["nextCursor"]
        assert "instance:relations-1" not in json.dumps(value)
        first = read(c, r.root + "/history", pageSize=1)
        encoded = first["nextCursor"].split(".")[0]
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        )
        assert payload["lastKey"] == [r.ref.revision_id]


def test_bound_instance_with_corrupt_definition_never_becomes_a_related_item(relations):
    r = relations
    with r.a.repository.pool.connection() as c, c.transaction():
        c.execute(
            "UPDATE execution_authority.digital_employee_instances "
            "SET record=jsonb_set(record,'{definition_digest}',%s::jsonb) "
            "WHERE namespace=%s AND security_domain=%s "
            "AND digital_employee_instance_id=%s",
            (
                json.dumps("0" * 64),
                r.a.e.scope.namespace,
                r.a.e.scope.security_domain,
                "instance:relations-1",
            ),
        )
    with client(r) as c:
        assert c.get(r.root + "/instances").status_code == 409


def test_scan_limit_is_explicit_and_never_leaks_hidden_cursor(relations):
    r = relations
    with r.a.repository.pool.connection() as c, c.transaction():
        c.execute(
            "INSERT INTO execution_authority.digital_employee_instances "
            "SELECT namespace,security_domain,'a:hidden-'||lpad(n::text,3,'0'),"
            "definition_revision_id,aggregate_version,record FROM "
            "execution_authority.digital_employee_instances "
            "CROSS JOIN generate_series(1,201) n "
            "WHERE namespace=%s AND security_domain=%s "
            "AND digital_employee_instance_id=%s",
            (
                r.a.e.scope.namespace,
                r.a.e.scope.security_domain,
                "instance:relations-1",
            ),
        )
        c.execute(
            "INSERT INTO digital_employee_definition.instance_bindings "
            "SELECT namespace,security_domain,'a:hidden-'||lpad(n::text,3,'0'),"
            "definition_id,revision_id,digest FROM "
            "digital_employee_definition.instance_bindings "
            "CROSS JOIN generate_series(1,201) n "
            "WHERE namespace=%s AND security_domain=%s "
            "AND digital_employee_instance_id=%s",
            (
                r.a.e.scope.namespace,
                r.a.e.scope.security_domain,
                "instance:relations-1",
            ),
        )
    with client(r) as c:
        value = read(c, r.root + "/instances", pageSize=1)
        assert value["items"] == [] and value["scanLimited"]
        assert value["nextCursor"] is None and "hidden-" not in json.dumps(value)


@pytest.mark.parametrize(
    "owner,prefix,identity",
    [
        ("INSTANCE", "instance:", "instance:relations-1"),
        ("ASSIGNMENT", "assignment:", "assignment:relations-1"),
    ],
)
def test_existing_management_read_target_is_exact_scope_and_never_grants(
    relations, owner, prefix, identity
):
    from agent_console.authority_contracts import AuthorityError, ExactGrant
    from agent_console.workbench_grant_targets import WorkbenchGrantTargetValidator

    r = relations
    validator = WorkbenchGrantTargetValidator(None)
    ctx = r.a.subject
    before = snapshot(r.a)
    with r.a.repository.pool.connection() as c, c.transaction():
        c.execute("SET TRANSACTION READ ONLY")
        exact = ExactGrant(owner, "READ", prefix + identity)
        assert validator.is_known_exact_target(ctx, exact, connection=c)
        for bad in [
            ExactGrant(owner, "READ", prefix + "missing"),
            ExactGrant(owner, "READ", "wrong-prefix:" + identity),
            ExactGrant(owner, "CREATE", prefix + identity),
        ]:
            assert not validator.is_known_exact_target(ctx, bad, connection=c)
        for scope in [
            replace(ctx.scope, tenant_id="foreign-tenant"),
            replace(ctx.scope, security_domain="foreign-domain"),
        ]:
            assert not validator.is_known_exact_target(
                replace(ctx, scope=scope), exact, connection=c
            )
        with pytest.raises(AuthorityError, match="AUTHORITY_STORAGE_UNAVAILABLE"):
            validator.is_known_exact_target(ctx, exact)
    assert snapshot(r.a) == before


def test_authoring_uses_owner_fact_order_and_exact_authority_without_writes(relations):
    r = relations
    before = snapshot(r.a)
    with client(r) as c:
        value = read(c, r.root + "/authoring")
        assert value["basis"] == "OWNER_FACT_ORDER"
        assert value["parent"]["employeeDefinitionRevisionId"] == r.ref.revision_id
        assert value["head"]["status"] == "AVAILABLE"
        assert (
            value["head"]["definition"]["employeeDefinitionRevisionId"]
            == r.successor.revision_id
        )
        assert value["draft"] == value["head"]
        assert (
            value["publication"]["definition"]["employeeDefinitionRevisionId"]
            == r.ref.revision_id
        )
        assert (
            value["aggregateVersion"] == value["head"]["definition"]["aggregateVersion"]
        )
        assert value["executionStarted"] is False
        r.acl.allowed.remove(
            (
                "EMPLOYEE",
                "READ",
                f"employee:{r.ref.resource_id}:{r.successor.revision_id}",
            )
        )
        hidden = read(c, r.root + "/authoring")
        assert hidden["head"] == {"status": "NOT_AVAILABLE"}
        assert hidden["draft"] == {"status": "NOT_AVAILABLE"}
        assert r.successor.revision_id not in json.dumps(hidden)
        assert hidden["publication"] == value["publication"]
        r.acl.allowed.remove(
            ("EMPLOYEE", "READ", f"employee:{r.ref.resource_id}:{r.ref.revision_id}")
        )
        assert c.get(r.root + "/authoring").status_code == 404
    assert snapshot(r.a) == before


def test_authoring_withdrawal_never_falls_back_and_new_edit_needs_validation(
    relations,
):
    r = relations

    def decide(revision, action):
        with r.a.repository.pool.connection() as c, c.transaction():
            current = r.definitions.read_revision_for_workbench(
                c, r.a.e.scope, r.ref.resource_id, revision.revision_id, authorized=True
            )
            return r.definitions.decide_for_workbench(
                c,
                r.a.e.scope,
                r.ref.resource_id,
                revision.revision_id,
                revision.digest,
                action,
                expected_version=current["aggregateVersion"],
                decision_id="isolated-authoring-test",
                command_id=f"authoring:{action}:{revision.revision_id}",
                authorized=True,
            )

    for action in ("VALIDATE", "APPROVE", "PUBLISH"):
        decide(r.successor, action)
    with client(r) as c:
        published = read(c, r.root + "/authoring")
        assert published["draft"] == {"status": "NONE"}
        assert (
            published["publication"]["definition"]["employeeDefinitionRevisionId"]
            == r.successor.revision_id
        )
        decide(r.successor, "UNPUBLISH")
        withdrawn = read(c, r.root + "/authoring")
        assert withdrawn["publication"] == {"status": "WITHDRAWN"}
        # The older publication remains valid but is never silently substituted.
        with r.a.repository.pool.connection() as connection:
            assert (
                r.definitions.read_revision_for_workbench(
                    connection,
                    r.a.e.scope,
                    r.ref.resource_id,
                    r.ref.revision_id,
                    authorized=True,
                )["publicationState"]
                == "PUBLISHED"
            )
        new_revision = replace(
            r.successor,
            revision_id="revision:aaa-newest",
            predecessor_revision_id=r.successor.revision_id,
        )
        with r.a.repository.pool.connection() as connection, connection.transaction():
            r.definitions.create_for_workbench(
                connection,
                new_revision,
                expected_version=withdrawn["aggregateVersion"],
                decision_id="isolated-authoring-test",
                command_id="authoring:new-draft",
                authorized=True,
            )
        r.acl.allowed.add(
            (
                "EMPLOYEE",
                "READ",
                f"employee:{r.ref.resource_id}:{new_revision.revision_id}",
            )
        )
        before = snapshot(r.a)
        edited = read(c, r.root + "/authoring")
        assert (
            edited["head"]["definition"]["employeeDefinitionRevisionId"]
            == new_revision.revision_id
        )
        assert edited["draft"]["definition"]["lifecycleState"] == "DRAFT"
        assert edited["publication"] == {"status": "WITHDRAWN"}
        assert snapshot(r.a) == before


def test_new_discovery_uses_current_publication_and_preserves_historical_read(
    relations,
):
    from agent_console.plan_suggestion_domain import ExactReference, PlanningError
    from agent_console.planning_candidates import identities, read_published

    r = relations

    def found():
        with r.a.repository.pool.connection() as c:
            return [
                x
                for x in identities(c, r.a.e.scope, "EMPLOYEE")
                if x["identity"] == r.ref.resource_id
            ]

    # A created successor is not an eligible replacement for the publication.
    assert [x["revision"] for x in found()] == [r.ref.revision_id]
    for action in ("VALIDATE", "APPROVE", "PUBLISH"):
        with r.a.repository.pool.connection() as c, c.transaction():
            current = r.definitions.read_revision_for_workbench(
                c,
                r.a.e.scope,
                r.ref.resource_id,
                r.successor.revision_id,
                authorized=True,
            )
            r.definitions.decide_for_workbench(
                c,
                r.a.e.scope,
                r.ref.resource_id,
                r.successor.revision_id,
                r.successor.digest,
                action,
                expected_version=current["aggregateVersion"],
                decision_id="isolated-current-discovery",
                command_id="discovery:" + action,
                authorized=True,
            )
    assert found() == [
        {
            "identity": r.ref.resource_id,
            "revision": r.successor.revision_id,
            "digest": r.successor.digest,
        }
    ]
    with r.a.repository.pool.connection() as c, c.transaction():
        current = r.definitions.read_revision_for_workbench(
            c, r.a.e.scope, r.ref.resource_id, r.successor.revision_id, authorized=True
        )
        r.definitions.decide_for_workbench(
            c,
            r.a.e.scope,
            r.ref.resource_id,
            r.successor.revision_id,
            r.successor.digest,
            "UNPUBLISH",
            expected_version=current["aggregateVersion"],
            decision_id="isolated-current-discovery",
            command_id="discovery:withdraw",
            authorized=True,
        )
    assert [x["revision"] for x in found()] == [r.successor.revision_id]
    # Selection still undergoes exact publication checks; no fallback to old.
    with r.a.repository.pool.connection() as c:
        with pytest.raises(PlanningError, match="CANDIDATE_VERSION_UNAVAILABLE"):
            read_published(
                c,
                r.a.e.scope,
                "EMPLOYEE",
                ExactReference(
                    resource_id=r.ref.resource_id,
                    revision_id=r.successor.revision_id,
                    digest=r.successor.digest,
                ),
            )
        historical, _ = read_published(
            c, r.a.e.scope, "EMPLOYEE", r.ref, historical=True
        )
        assert historical["revisionId"] == r.ref.revision_id
