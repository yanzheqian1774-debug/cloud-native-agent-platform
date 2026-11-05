# ruff: noqa: F401,F811 -- Real isolated owner fixtures; exact permission fake only.
from copy import deepcopy
from types import SimpleNamespace

from agent_console.authority_contracts import AuthorityError
from agent_console.resource_dependency_impact import project, references, structural
from agent_console.workbench_business_problem import OwnerPrincipal
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation
from test_resource_management import CONTENT, command, manager


def test_only_typed_exact_references_are_dependencies():
    sample = {"resourceId": "not-a-dependency", "revisionId": "1", "digest": "b" * 64}
    assert structural({"examples": [sample], "inputSchema": sample}, "SKILL") == {}
    assert structural({"examples": [sample]}, "AGENT") == {}
    assert references({"text": "skill:abc v1", "dependencies": ["a name"]}) == []
    assert (
        references(
            {
                "bindings": {
                    "skills": [
                        {"resourceId": "a", "revisionId": "1", "digest": "b" * 64}
                    ]
                }
            }
        )[0]["identity"]
        == "a"
    )


def test_real_agent_binding_is_permission_filtered_and_pinned_to_old_version(manager):
    a, _ = manager
    created = command(manager, "create", name="影响核对目标", content=CONTENT)[
        "resource"
    ]
    published = command(
        manager,
        "publish",
        identity=created["resourceId"],
        expectedVersion=created["aggregateVersion"],
    )["resource"]
    old = published["revisions"][-1]
    successor = command(
        manager,
        "successor",
        identity=published["resourceId"],
        expectedVersion=published["aggregateVersion"],
    )["resource"]
    service = a.services["agent"]
    scope = service.scope(a.e.scope.namespace, a.e.scope.security_domain)
    base = service.repository.get(scope, a.refs["agent"].resource_id)
    content = deepcopy(base["revisions"][-1]["content"])
    content["bindings"] = {
        **content.get("bindings", {}),
        "skills": [
            {
                "resourceId": created["resourceId"],
                "revisionId": old["revisionId"],
                "digest": old["digest"],
            }
        ],
    }
    consumer = service.create(scope, "human:isolated-setup", "引用旧版的职责", content)
    from agent_console.digital_employee_definition import (
        CompositionMember,
        EmployeeRevision,
        MemberKind,
    )
    from agent_console.execution_domain import ScopeIdentity

    employee = EmployeeRevision(
        ScopeIdentity(a.e.scope.namespace, a.e.scope.security_domain),
        "employee-definition:impact-transitive",
        "employee-revision:impact-transitive",
        "经职责引用技能的员工",
        ("只核对真实版本依赖",),
        (
            CompositionMember(
                MemberKind.AGENT,
                consumer["definitionId"],
                consumer["revisions"][-1]["revisionId"],
                consumer["revisions"][-1]["digest"],
            ),
        ),
    )
    with a.repository.pool.connection() as c, c.transaction():
        a.automation.employees.create_for_workbench(
            c,
            employee,
            expected_version=0,
            decision_id="isolated-fixture-creation-only",
            command_id="impact-transitive-employee",
            authorized=True,
        )
    reads = []

    class Authority:
        enabled = True

        def require(self, p, owner, action, target):
            reads.append((owner, action, target))
            if not self.enabled or (
                consumer["definitionId"] not in target
                and employee.definition_id not in target
            ):
                raise AuthorityError("READ_DENIED")

    authority = Authority()
    with a.repository.pool.connection() as c:
        call = SimpleNamespace(connection=c, context=a.subject, authority=authority)
        result = project(call, "skill", successor)
        rows = [
            x for x in result["incoming"] if x["identity"] == consumer["definitionId"]
        ]
        assert len(rows) == 1 and rows[0]["distance"] == 1
        assert (
            rows[0]["versionRelation"] == "OTHER_VERSION"
            and rows[0]["targetRevision"] == old["revisionId"]
        )
        transitive = next(
            x
            for x in result["incoming"]
            if x["kind"] == "EMPLOYEE" and x["identity"] == employee.definition_id
        )
        assert (
            transitive["distance"] == 2
            and transitive["versionRelation"] == "OTHER_VERSION"
        )
        assert rows[0]["automaticUpgrade"] is False and result["complete"] is False
        authority.enabled = False
        hidden = project(call, "skill", successor)
        assert hidden["incoming"] == [] and consumer["definitionId"] not in str(hidden)
    assert reads and any(x[0] == "AGENT" for x in reads)
