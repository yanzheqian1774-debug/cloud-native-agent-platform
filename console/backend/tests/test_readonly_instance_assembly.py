# ruff: noqa: F401, F811 -- Reuse explicitly isolated PostgreSQL owner fixtures.
"""Production binding atomicity/replay; no live Native effect is asserted here."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.execution_postgres import PostgresExecutionAuthorityRepository
from agent_console.readonly_instance_assembly import assemble
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation


@pytest.fixture
def ready_inputs(automation):
    a = automation
    value = a.run()
    assert value["state"] == "READY"
    ref = value["assembly"]["definition"]
    bundle = {
        "case": "sales",
        "namespace": a.e.scope.namespace,
        "securityDomain": a.e.scope.security_domain,
        "resources": [
            {
                "kind": x["kind"],
                "identity": x["reference"]["resource_id"],
                "revisionId": x["reference"]["revision_id"],
                "digest": x["reference"]["digest"],
            }
            for x in value["resources"]
        ],
    }
    employee = {
        "employeeDefinitionId": ref["resource_id"],
        "employeeDefinitionRevisionId": ref["revision_id"],
        "employeeDefinitionDigest": ref["digest"],
    }
    owner = PostgresExecutionAuthorityRepository(
        a.repository.pool.conninfo,
        migration_path=Path(__file__).parents[1]
        / "migrations/0008_execution_runtime_authority.sql",
    )
    try:
        yield SimpleNamespace(a=a, bundle=bundle, employee=employee, owner=owner)
    finally:
        owner.pool.close()


def counts(c):
    return {
        t: c.execute("SELECT count(*) n FROM execution_authority." + t).fetchone()["n"]
        for t in (
            "digital_employee_instances",
            "assignments",
            "runtime_instances",
            "agent_instances",
            "workflow_runs",
            "task_runs",
        )
    }


def invoke(f, c, *, denied=None, plan_digest=None, scope=None, bundle=None):
    a = f.a
    # Isolated authority deliberately records and can reject every exact check.
    # Production passes the existing current-generation owner authority instead.
    checks = []

    def authorize(owner, action, resource):
        checks.append((owner, action, resource))
        if owner == denied:
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")
        if owner == "ASSIGNMENT":
            assert action == "CREATE" and resource.startswith("assignment:instance:")
            assert c.execute(
                "SELECT 1 FROM execution_authority.digital_employee_instances "
                "WHERE namespace=%s AND security_domain=%s "
                "AND digital_employee_instance_id=%s",
                (
                    a.e.scope.namespace,
                    a.e.scope.security_domain,
                    resource[len("assignment:instance:") :],
                ),
            ).fetchone()

    principal = SimpleNamespace(
        principal_id=a.subject.principal_id,
        tenant_id=scope or a.e.scope.namespace,
        security_domain=a.e.scope.security_domain,
    )
    value = assemble(
        f.owner,
        c,
        bundle or f.bundle,
        f.employee,
        a.e.p.semantics.model_dump(mode="json"),
        principal=principal,
        authorize=authorize,
        plan_digest=plan_digest or a.e.p.plan_digest,
        agent_name="isolated-test-native-sales",
    )
    return value, checks


def test_same_plan_replay_has_exact_bindings_and_no_run(ready_inputs):
    f = ready_inputs
    with f.a.repository.pool.connection() as c, c.transaction():
        before = counts(c)
        first, checks = invoke(f, c)
        second, _ = invoke(f, c)
        assert first == second
        after = counts(c)
        assert (
            after["digital_employee_instances"]
            == before["digital_employee_instances"] + 2
        )
        assert (
            after["assignments"]
            == before["assignments"] + len(first["mapping"]["participants"]) + 1
        )
        assert after["runtime_instances"] == before["runtime_instances"] + 1
        assert after["agent_instances"] == before["agent_instances"] + 1
        assert after["workflow_runs"] == before["workflow_runs"]
        assert after["task_runs"] == before["task_runs"]
        assert first["executionStarted"] is False
        assert ("INSTANCE", "CREATE", "instance:collection") in checks
        other, _ = invoke(f, c, plan_digest="f" * 64)
        assert (
            first["mapping"]["root_instance_id"] != other["mapping"]["root_instance_id"]
        )


@pytest.mark.parametrize("denied", ["INSTANCE", "ASSIGNMENT", "SKILL"])
def test_permission_failure_rolls_back_all_instance_and_runtime_writes(
    ready_inputs, denied
):
    f = ready_inputs
    with f.a.repository.pool.connection() as c, c.transaction():
        before = counts(c)
        with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
            invoke(f, c, denied=denied)
        assert counts(c) == before


def test_cross_scope_and_mixed_exact_members_never_create_instances(ready_inputs):
    f = ready_inputs
    with f.a.repository.pool.connection() as c, c.transaction():
        before = counts(c)
        with pytest.raises(ValueError, match="READONLY_ASSEMBLY_SCOPE_MISMATCH"):
            invoke(f, c, scope="different-tenant")
        from copy import deepcopy

        bad = deepcopy(f.bundle)
        bad["resources"][0]["digest"] = "0" * 64
        with pytest.raises(ValueError, match="EXACT_EMPLOYEE_MEMBER_MAPPING_REQUIRED"):
            invoke(f, c, bundle=bad)
        assert counts(c) == before


def test_task_local_binding_splits_operations_without_changing_employee(ready_inputs):
    import copy

    from agent_console.plan_suggestion_domain import (
        ExactReference,
        FlexiblePlanSemantics,
    )
    from agent_console.sales_resource_bundle import resource_content
    from agent_console.task_member_binding import bind_steps, resource_groups

    a = ready_inputs.a
    content = resource_content(a.e.source)["skill"]
    read = {
        **content,
        "operations": [x for x in content["operations"] if x["name"] == "READ_DATA"],
    }
    rest = {
        **content,
        "operations": [x for x in content["operations"] if x["name"] != "READ_DATA"],
    }
    first = ExactReference(
        resource_id="skill:read", revision_id="read:1", digest="a" * 64
    )
    second = ExactReference(
        resource_id="skill:rest", revision_id="rest:1", digest="b" * 64
    )
    result = bind_steps(
        a.e.p.semantics,
        [(first, read), (second, rest)],
        source_schema="sales-diagnostic-source.v1",
        case="sales",
    )
    for task in a.e.p.semantics.tasks:
        assert result[task.task_id]["reference"] == (
            first if task.operation == "READ_DATA" else second
        )
    body = a.e.p.semantics.model_dump(mode="json")
    body["requirements"].append(
        {
            "requirement_id": "foreign",
            "kind": "SKILL",
            "name": "Outside member",
            "purpose": "must not substitute",
            "required": True,
            "selected": {
                "resource_id": "skill:foreign",
                "revision_id": "foreign:1",
                "digest": "c" * 64,
            },
            "preparation": "Existing member required",
        }
    )
    body["tasks"][0]["requirement_ids"].append("foreign")
    with pytest.raises(ValueError, match="TASK_MEMBER_OPERATION_UNAVAILABLE"):
        bind_steps(
            FlexiblePlanSemantics.model_validate(body),
            [(first, read), (second, rest)],
            source_schema="sales-diagnostic-source.v1",
            case="sales",
        )
    with pytest.raises(ValueError, match="TASK_MEMBER_DUPLICATE_RESOURCE"):
        resource_groups(
            [*ready_inputs.bundle["resources"], ready_inputs.bundle["resources"][0]]
        )
