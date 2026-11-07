# ruff: noqa: F401,F811 -- Explicit disposable SQL fixtures; not actual IAM acceptance.
"""One maintenance publication, immutable successor and exact Employee consumer."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from agent_console.digital_employee_definition import (
    CompositionMember,
    EmployeeRevision,
    MemberKind,
)
from agent_console.resource_dependency_impact import project
from agent_console.sales_evaluation import CHECKS, evaluate_sales
from agent_console.skill_mcp_schemas import ResourceContent
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    WorkbenchOwnerError,
)
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation
from test_resource_management import command, manager


def test_maintenance_test_failure_repair_publication_exact_consumer_and_successor(
    manager,
):
    a, _manager = manager
    fixture = Path(__file__).resolve().parents[2] / "frontend/tests"
    content = json.loads(
        (fixture / "resource-management/fixtures/maintenance-skill.json").read_text()
    )
    ResourceContent.model_validate(content)
    original = json.loads((fixture / "e2e/fixtures/sales-report.json").read_text())
    source, reference = original["source"], original["sourceSnapshot"]
    with a.repository.pool.connection() as c:
        prior_runs = c.execute(
            "SELECT count(*) n FROM execution_authority.run_preparations"
        ).fetchone()["n"]
        prior_skill = c.execute(
            "SELECT record FROM skill_mcp_resource.resources WHERE resource_id=%s",
            (a.refs["skill"].resource_id,),
        ).fetchone()["record"]
    resource = command(
        manager, "create", key="journey-create", name="完整维护核验", content=content
    )["resource"]
    identity = resource["resourceId"]

    def act(action, key, **extra):
        return command(
            manager,
            action,
            key=key,
            identity=identity,
            expectedVersion=resource["aggregateVersion"],
            **extra,
        )

    resource = act(
        "edit",
        "journey-edit",
        content={**content, "description": "编辑后保留准确操作契约"},
    )["resource"]

    def inputs(operation):
        return {
            "schemaVersion": "sales-diagnostic-input.v1",
            "synthetic": True,
            "sourceSnapshot": reference,
            "source": source,
            "dependencies": {} if operation == "READ_DATA" else {"read": read_output},
        }

    resource = act(
        "test",
        "journey-negative",
        operation="READ_DATA",
        testName="来源核验·READ_DATA",
        testInput=inputs("READ_DATA"),
        expectedOutput={"operation": "WRONG"},
        comparison="subset",
    )["resource"]
    assert resource["testResults"][-1]["status"] == "FAILED"
    with pytest.raises(WorkbenchOwnerError, match="CURRENT_OPERATION_TESTS_REQUIRED"):
        act("publish-tested", "journey-blocked-before-tests")
    read_output = None
    for op in content["operations"]:
        operation = op["name"]
        resource = act(
            "test",
            "journey-test-" + operation,
            operation=operation,
            testName="来源核验·" + operation,
            testInput=inputs(operation),
            expectedOutput={"operation": operation, "sourceSnapshot": reference},
            comparison="subset",
        )["resource"]
        observed = resource["testResults"][-1]
        assert observed["actualExecution"] and observed["status"] == "PASSED"
        if operation == "READ_DATA":
            read_output = observed["actual"]
        if operation == "RENDER_REPORT":
            assert all(
                evaluate_sales(check, source, observed["actual"], reference)[0]
                == "SATISFIED"
                for check in CHECKS
            )
    published = act("publish-tested", "journey-checked-publication")
    assert published["publicationVerification"]["ready"]
    resource = published["resource"]
    revision = next(
        r
        for r in resource["revisions"]
        if r["revisionId"] == resource["publishedRevisionId"]
    )
    pinned = json.loads(json.dumps(revision))
    employee = EmployeeRevision(
        a.e.scope,
        "employee-definition:maintenance-reference",
        "employee-revision:maintenance-reference",
        "维护后的准确引用",
        ("只保存准确成员且不声称已运行",),
        (
            CompositionMember(
                MemberKind.AGENT,
                a.refs["agent"].resource_id,
                a.refs["agent"].revision_id,
                a.refs["agent"].digest,
            ),
            CompositionMember(
                MemberKind.SKILL, identity, revision["revisionId"], revision["digest"]
            ),
        ),
    )
    with a.repository.pool.connection() as c, c.transaction():
        a.automation.employees.create_for_workbench(
            c,
            employee,
            expected_version=0,
            decision_id="isolated-fixture-create-only",
            command_id="isolated-journey-create",
            authorized=True,
        )

    def impact():
        with a.authority.connection_scope() as c:
            real = AuthorizedOwnerAuthority(a.adapter, a.subject, c, 1, ())

            def require(principal, owner, action, exact):
                if (owner, action, exact) == (
                    "EMPLOYEE",
                    "READ",
                    f"employee:{employee.definition_id}:{employee.revision_id}",
                ):
                    return SimpleNamespace()
                return real.require(principal, owner, action, exact)

            return project(
                SimpleNamespace(
                    connection=c,
                    context=a.subject,
                    authority=SimpleNamespace(require=require),
                ),
                "skill",
                resource,
            )

    incoming = impact()["incoming"]
    consumer = next(x for x in incoming if x["identity"] == employee.definition_id)
    assert (
        consumer["targetRevision"] == pinned["revisionId"]
        and consumer["versionRelation"] == "CURRENT_VERSION"
    )
    resource = act("successor", "journey-successor")["resource"]
    with pytest.raises(WorkbenchOwnerError, match="CURRENT_OPERATION_TESTS_REQUIRED"):
        act("publish-tested", "journey-blocked-new-revision")
    assert (
        next(
            r for r in resource["revisions"] if r["revisionId"] == pinned["revisionId"]
        )
        == pinned
    )
    consumer = next(
        x for x in impact()["incoming"] if x["identity"] == employee.definition_id
    )
    assert (
        consumer["targetRevision"] == pinned["revisionId"]
        and consumer["versionRelation"] != "CURRENT_VERSION"
    )
    with a.repository.pool.connection() as c:
        saved = c.execute(
            "SELECT record FROM digital_employee_definition.revisions "
            "WHERE definition_id=%s",
            (employee.definition_id,),
        ).fetchone()["record"]
        assert (
            next(x for x in saved["members"] if x["kind"] == "SKILL")["revision_id"]
            == pinned["revisionId"]
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM execution_authority.run_preparations"
            ).fetchone()["n"]
            == prior_runs
        )
        assert (
            c.execute(
                "SELECT record FROM skill_mcp_resource.resources WHERE resource_id=%s",
                (a.refs["skill"].resource_id,),
            ).fetchone()["record"]
            == prior_skill
        )
