# ruff: noqa: F401,F811,E501 -- Explicit disposable SQL fixtures, not actual IAM acceptance.
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityScope, ExactGrant
from agent_console.digital_employee_definition import (
    CompositionMember,
    EmployeeRevision,
    MemberKind,
)
from agent_console.digital_employee_definition_postgres import (
    PostgresEmployeeDefinitionRepository,
)
from agent_console.prepared_skill_handoff import read_handoff
from agent_console.resource_dependency_impact import project
from agent_console.resource_management import target
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
    WorkbenchOwnerError,
)
from agent_console.workbench_prepared_resources import reference
from psycopg.types.json import Jsonb
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation
from test_resource_management import command, manager
from test_sales_supplement_owners import owner_call, skill_request


def prepare(pair):
    a, management = pair
    request = skill_request(a)
    management.prepared_handoff_enabled = True
    with a.authority.connection_scope() as connection:
        call = AuthorizedOwnerCall(
            "RESOURCE_MANAGEMENT",
            a.subject,
            connection,
            {},
            {"kind": "skill"},
            {},
            (),
            AuthorizedOwnerAuthority(a.adapter, a.subject, connection, 1, ()),
            1,
            1,
        )
        issuer, work = management.scope(a.subject, "skill")
        management.authorize(
            call,
            [
                ExactGrant(
                    "SKILL",
                    "MANAGE_RESOURCE",
                    target("skill", request.path["identity"]),
                ),
                ExactGrant(
                    "SKILL",
                    "READ_RESOURCE",
                    reference(
                        "skill", request.path["identity"], request.path["revision"]
                    ),
                ),
            ],
            "explicit-original-prepared-authority",
            work,
            issuer,
        )
    receipt = owner_call(
        a,
        request.handler,
        "PREPARE_PREPARED_SKILL_SUCCESSOR",
        request.body,
        request.path,
        request.acl,
    )
    return request, receipt


def has_owner(a, identity, context=None, key="isolated-successor-key"):
    with a.repository.pool.connection() as connection:
        return read_handoff(connection, context or a.subject, identity, key) is not None


def test_exact_prepared_handoff_current_management_test_publication_and_history(
    manager,
):
    a, management = manager
    identity = a.refs["skill"].resource_id
    assert not has_owner(a, identity)
    with pytest.raises(WorkbenchOwnerError, match="RESOURCE_MANAGEMENT_NOT_FOUND"):
        command(manager, "access", identity=identity)
    request, receipt = prepare(manager)
    assert has_owner(a, identity)
    with a.repository.pool.connection() as connection:
        assert not management.owned(
            SimpleNamespace(connection=connection, context=a.subject), "skill", identity
        )
    management.prepared_handoff_enabled = False
    with pytest.raises(WorkbenchOwnerError, match="PREPARED_SKILL_HANDOFF_DISABLED"):
        command(
            manager,
            "adopt-prepared",
            key="closed-handoff-denied",
            identity=identity,
            expectedVersion=receipt["aggregateVersion"],
            preparedCommandKey=receipt["commandKey"],
        )
    management.prepared_handoff_enabled = True
    resource = command(
        manager,
        "adopt-prepared",
        identity=identity,
        expectedVersion=receipt["aggregateVersion"],
        preparedCommandKey=receipt["commandKey"],
    )["resource"]
    resource = command(manager, "access", identity=identity)["resource"]
    old = deepcopy(
        next(
            r
            for r in resource["revisions"]
            if r["revisionId"] == a.refs["skill"].revision_id
        )
    )
    assert old == next(
        r for r in request.old["revisions"] if r["revisionId"] == old["revisionId"]
    )
    assert resource["currentDraftRevisionId"] == receipt["draft"]["revision_id"]

    def act(action, key, **extra):
        return command(
            manager,
            action,
            key=key,
            identity=identity,
            expectedVersion=resource["aggregateVersion"],
            **extra,
        )

    source_ref = a.refs["knowledge"].model_dump(mode="json")

    def inputs(operation, read=None):
        return {
            "schemaVersion": "sales-diagnostic-input.v2",
            "synthetic": True,
            "sourceSnapshot": source_ref,
            "source": a.e.source,
            "dependencies": {} if operation == "READ_DATA" else {"read": read},
        }

    disabled = act(
        "test",
        "disabled-v2",
        operation="READ_DATA",
        testName="bounded-READ_DATA",
        testInput=inputs("READ_DATA"),
        expectedOutput={"operation": "READ_DATA"},
        comparison="subset",
    )
    resource = disabled["resource"]
    assert resource["testResults"][-1]["actualExecution"] is False
    assert resource["testResults"][-1]["status"] != "PASSED"
    with pytest.raises(WorkbenchOwnerError, match="CURRENT_OPERATION_TESTS_REQUIRED"):
        act("publish-tested", "blocked-disabled-v2")
    management.sales_v2_candidate = True
    read = None
    for operation in [
        "READ_DATA",
        "VALIDATE_DATA",
        "SUMMARIZE",
        "ANALYZE_DATA",
        "RENDER_REPORT",
    ]:
        resource = act(
            "test",
            "enabled-" + operation,
            operation=operation,
            testName="bounded-" + operation,
            testInput=inputs(operation, read),
            expectedOutput={"operation": operation, "sourceSnapshot": source_ref},
            comparison="subset",
        )["resource"]
        observed = resource["testResults"][-1]
        assert observed["status"] == "PASSED", observed
        assert observed["actualExecution"] and not observed["businessRunStarted"]
        if operation == "READ_DATA":
            read = observed["actual"]
        if operation == "RENDER_REPORT":
            assert observed["actual"]["schemaVersion"] == "sales-diagnostic-output.v2"
    published = act("publish-tested", "checked-v2-publication")
    resource = published["resource"]
    assert published["publicationVerification"]["ready"]
    assert resource["publishedRevisionId"] == receipt["draft"]["revision_id"]
    assert (
        next(r for r in resource["revisions"] if r["revisionId"] == old["revisionId"])
        == old
    )
    assert has_owner(a, identity)
    old_employee = next(
        r.selected for r in a.e.p.semantics.requirements if r.kind == "EMPLOYEE"
    )
    employee_repo = PostgresEmployeeDefinitionRepository(a.repository)
    with a.repository.pool.connection() as connection, connection.transaction():
        before_employee = employee_repo._read(
            connection, a.e.scope, old_employee.resource_id, old_employee.revision_id
        )["revision"]
        new_employee = EmployeeRevision(
            a.e.scope,
            old_employee.resource_id,
            "employee-revision:prepared-handoff",
            before_employee["role"],
            tuple(before_employee["responsibilities"]),
            tuple(
                CompositionMember(
                    MemberKind(m["kind"]),
                    identity if m["kind"] == "SKILL" else m["resource_id"],
                    receipt["draft"]["revision_id"]
                    if m["kind"] == "SKILL"
                    else m["revision_id"],
                    receipt["draft"]["digest"] if m["kind"] == "SKILL" else m["digest"],
                )
                for m in before_employee["members"]
            ),
            old_employee.revision_id,
        )
        result = employee_repo.create_for_workbench(
            connection,
            new_employee,
            expected_version=4,
            decision_id="isolated-explicit-fixture-only",
            command_id="isolated-prepared-handoff-employee",
            authorized=True,
        )
        for action in ["VALIDATE", "APPROVE", "PUBLISH"]:
            result = employee_repo.decide_for_workbench(
                connection,
                a.e.scope,
                new_employee.definition_id,
                new_employee.revision_id,
                new_employee.digest,
                action,
                expected_version=result["aggregateVersion"],
                decision_id="isolated-fixture-only",
                command_id="isolated-handoff-employee-" + action,
                authorized=True,
            )
        assert (
            employee_repo._read(
                connection,
                a.e.scope,
                old_employee.resource_id,
                old_employee.revision_id,
            )["revision"]
            == before_employee
        )

    def consumer():
        with a.authority.connection_scope() as connection:
            original = AuthorizedOwnerAuthority(a.adapter, a.subject, connection, 1, ())

            def require(principal, owner, action, exact):
                if (owner, action, exact) == (
                    "EMPLOYEE",
                    "READ",
                    f"employee:{new_employee.definition_id}:{new_employee.revision_id}",
                ):
                    return SimpleNamespace()
                return original.require(principal, owner, action, exact)

            projection = project(
                SimpleNamespace(
                    connection=connection,
                    context=a.subject,
                    authority=SimpleNamespace(require=require),
                ),
                "skill",
                resource,
            )
            return next(
                c
                for c in projection["incoming"]
                if c["identity"] == new_employee.definition_id
                and c["revision"] == new_employee.revision_id
            )

    assert consumer()["targetRevision"] == receipt["draft"]["revision_id"]
    # Further immutable edits remain governed by the same genuine handoff.
    resource = act("successor", "next-maintained-successor")["resource"]
    resource = act(
        "edit",
        "next-maintained-edit",
        content={**request.body["content"], "description": "later maintained draft"},
    )["resource"]
    assert has_owner(a, identity)
    assert resource["publishedRevisionId"] == receipt["draft"]["revision_id"]
    assert consumer()["targetRevision"] == receipt["draft"]["revision_id"]
    assert consumer()["versionRelation"] != "CURRENT_VERSION"
    with a.repository.pool.connection() as connection:
        assert (
            connection.execute(
                "SELECT count(*) n FROM execution_authority.workflow_runs"
            ).fetchone()["n"]
            == 0
        )
        assert (
            connection.execute(
                "SELECT count(*) n FROM execution_authority.prepared_resource_commands WHERE result->>'schemaVersion'='resource-management-receipt.v1' AND result->>'action' IN ('create','import')"
            ).fetchone()["n"]
            == 0
        )


@pytest.mark.parametrize(
    "damage",
    ["actor", "draft", "predecessor", "key", "digest", "contentDigest", "scope"],
)
def test_handoff_cannot_adopt_foreign_or_corrupt_receipt(manager, damage):
    a, _ = manager
    _, receipt = prepare(manager)
    identity = a.refs["skill"].resource_id
    assert has_owner(a, identity)
    if damage == "scope":
        foreign = SimpleNamespace(
            principal_id=a.subject.principal_id,
            scope=AuthorityScope("foreign-tenant", a.subject.scope.security_domain),
        )
        assert not has_owner(a, identity, foreign)
        return
    if damage == "actor":
        foreign = SimpleNamespace(
            principal_id="human:another-maintainer", scope=a.subject.scope
        )
        assert not has_owner(a, identity, foreign)
        return
    changed = deepcopy(receipt)
    bad_key = "malformed-receipt-" + damage
    changed["commandKey"] = bad_key
    if damage == "draft":
        changed["draft"]["digest"] = "f" * 64
    if damage == "predecessor":
        changed["predecessor"]["revision_id"] = changed["draft"]["revision_id"]
    if damage == "key":
        changed["commandKey"] = "different-bound-command"
    if damage == "contentDigest":
        changed["contentDigest"] = "e" * 64
    with a.repository.pool.connection() as connection, connection.transaction():
        original = connection.execute(
            "SELECT digest FROM execution_authority.prepared_resource_commands WHERE command_key=%s",
            ("prepared-skill-successor:" + receipt["commandKey"],),
        ).fetchone()
        connection.execute(
            "INSERT INTO execution_authority.prepared_resource_commands(namespace,security_domain,actor_id,command_key,digest,result) VALUES(%s,%s,%s,%s,%s,%s)",
            (
                a.subject.scope.tenant_id,
                a.subject.scope.security_domain,
                a.subject.principal_id,
                "prepared-skill-successor:" + bad_key,
                "a" * 64 if damage == "digest" else original["digest"],
                Jsonb(changed),
            ),
        )
    assert not has_owner(a, identity, key=bad_key)
    with pytest.raises(WorkbenchOwnerError, match="PREPARED_SKILL_HANDOFF_NOT_FOUND"):
        command(
            manager,
            "adopt-prepared",
            key="malformed-handoff-adoption",
            identity=identity,
            expectedVersion=receipt["aggregateVersion"],
            preparedCommandKey=bad_key,
        )
    # The original append-only receipt remains valid; malformed new evidence
    # neither overwrites it nor confers generic management ownership.
    assert has_owner(a, identity)


@pytest.mark.parametrize("condition", ["closed", "mcp", "stale", "revoked", "expired"])
def test_explicit_handoff_denials_are_atomic(manager, condition):
    from datetime import timedelta

    from agent_console.authority_contracts import AuthorityError, GrantId
    from agent_console.grant_administration_application import GrantRevocationCommand

    a, management = manager
    _, receipt = prepare(manager)
    identity = a.refs["skill"].resource_id
    if condition == "closed":
        management.prepared_handoff_enabled = False
    if condition == "expired":
        scope = management.policy.workScopes[0].model_copy(
            update={"expiresAt": management.grants.clock() - timedelta(seconds=1)}
        )
        management.policy = management.policy.model_copy(
            update={"workScopes": (scope,)}
        )
    if condition == "revoked":
        with a.repository.pool.connection() as connection:
            grant = connection.execute(
                "SELECT grant_id FROM authorization_admin.grants WHERE owner='SKILL' AND action='MANAGE_RESOURCE' AND exact_resource=%s",
                (target("skill", identity),),
            ).fetchone()["grant_id"]
        management.grants.revoke_grant(
            a.subject,
            GrantRevocationCommand(
                GrantId(grant),
                "USER_REQUESTED",
                "isolated-explicit-handoff-revocation",
                True,
            ),
        )

    def snapshot():
        with a.repository.pool.connection() as connection:
            return {
                table: sorted(
                    r["digest"]
                    for r in connection.execute(
                        "SELECT md5(row_to_json(t)::text) digest FROM " + table + " t"
                    )
                )
                for table in [
                    "skill_mcp_resource.resources",
                    "execution_authority.prepared_resource_commands",
                    "authorization_admin.grant_requests",
                    "authorization_admin.grants",
                ]
            }

    before = snapshot()
    with pytest.raises((WorkbenchOwnerError, AuthorityError)):
        command(
            manager,
            "adopt-prepared",
            kind="mcp" if condition == "mcp" else "skill",
            identity=identity,
            expectedVersion=receipt["aggregateVersion"] - 1
            if condition == "stale"
            else receipt["aggregateVersion"],
            preparedCommandKey=receipt["commandKey"],
        )
    assert snapshot() == before
