# ruff: noqa: F401,F811 -- Reuse original disposable owner fixtures.
"""Successor publication cannot retarget a still-authorized frozen Employee."""

from dataclasses import replace
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.digital_employee_definition import (
    EmployeeDefinitionError,
    EmployeeRevision,
)
from agent_console.digital_employee_definition_postgres import (
    PostgresEmployeeDefinitionRepository as Employee,
)
from agent_console.plan_suggestion_domain import ExactReference, PlanningError
from agent_console.planning_candidates import (
    ExactPlanningOwnerReader,
    read_employee_member,
    read_published,
)
from agent_console.prepared_execution_resources import published
from agent_console.question_member_capabilities import observe
from agent_console.workbench_owner_authorization import AuthorizedOwnerAuthority
from psycopg.types.json import Jsonb
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_readonly_instance_assembly import invoke, ready_inputs
from test_resource_automation import automation


def successor(a):
    skill = a.services["skill"]
    scope = skill.scope(a.e.scope.namespace, a.e.scope.security_domain)
    old = a.refs["skill"]
    record = skill.repository.get(scope, "skill", old.resource_id)
    draft = skill.successor(
        scope,
        "skill",
        old.resource_id,
        "human:isolated-fixture",
        record["aggregateVersion"],
    )["resource"]
    draft = skill.validate(
        scope,
        "skill",
        old.resource_id,
        "human:isolated-fixture",
        draft["aggregateVersion"],
    )["resource"]
    revision = next(
        r
        for r in draft["revisions"]
        if r["revisionId"] == draft["currentDraftRevisionId"]
    )
    reviewed = skill.review(
        scope,
        "skill",
        old.resource_id,
        "human:isolated-fixture",
        draft["aggregateVersion"],
        revision["digest"],
        "APPROVE",
        "Explicit isolated synthetic fixture review; no production authority",
    )["resource"]
    current = skill.publish(
        scope,
        "skill",
        old.resource_id,
        "human:isolated-fixture",
        reviewed["aggregateVersion"],
        revision["digest"],
        reviewed["reviews"][-1]["reviewId"],
    )["resource"]
    return ExactReference(
        resource_id=old.resource_id,
        revision_id=current["publishedRevisionId"],
        digest=revision["digest"],
    )


def definition(c, a, ref):
    return EmployeeRevision.from_record(
        Employee._read(c, a.e.scope, ref.resource_id, ref.revision_id)["revision"]
    )


def test_successor_keeps_exact_bound_read_assessment_and_planning(automation):
    a = automation
    ready = a.run()
    employee = ExactReference.model_validate(ready["assembly"]["definition"])
    old = a.refs["skill"]
    new = successor(a)
    assert old != new
    with a.repository.pool.connection() as c:
        with pytest.raises(PlanningError, match="VERSION_UNAVAILABLE"):
            read_published(c, a.e.scope, "SKILL", old)
        assert read_published(c, a.e.scope, "SKILL", new)
        revision = definition(c, a, employee)
        with pytest.raises(EmployeeDefinitionError, match="INELIGIBLE"):
            Employee.validate_members(c, revision)  # New assembly stays current-only.
        Employee.validate_members(c, revision, published_binding=True)
        old_content, _ = read_employee_member(c, a.e.scope, employee, "SKILL", old)
        assert published(c, a.e.scope, "SKILL", old, employee=employee) == old_content
        assert (
            Employee._read(c, a.e.scope, employee.resource_id, employee.revision_id)[
                "digest"
            ]
            == employee.digest
        )
        authority = AuthorizedOwnerAuthority(a.adapter, a.subject, c, 1, ())
        call = SimpleNamespace(connection=c, context=a.subject, authority=authority)
        facts = observe(
            a.automation,
            call,
            a.refs["knowledge"],
            "sales-diagnostic-source.v1",
            a.policy.workScopes[0],
        )
        assert facts["state"] == "AUTHORIZED_MEMBER_DECLARATIONS_OBSERVED", facts
        assert {"READ_DATA", "ANALYZE_DATA"} <= {
            x["operation"] for x in facts["operations"]
        }
        requirement = SimpleNamespace(selected=old, requirement_id="old-skill")
        principal = a.e.principal
        assert (
            ExactPlanningOwnerReader(c, a.e.scope, authority, "SKILL")
            .observe(principal, requirement)
            .status
            == "UNAVAILABLE"
        )
        assert (
            ExactPlanningOwnerReader(c, a.e.scope, authority, "SKILL", (employee,))
            .observe(principal, requirement)
            .status
            == "MATCHED"
        )

        class Deny:
            def require(self, *args):
                raise AuthorityError("ISOLATED_REVOKED_READ")

        assert (
            ExactPlanningOwnerReader(c, a.e.scope, Deny(), "SKILL", (employee,))
            .observe(principal, requirement)
            .status
            == "UNREADABLE"
        )
    # Revalidation of original idempotent response uses exact Employee binding.
    assert a.run()["state"] == "READY"


def test_bound_successor_still_prepares_exact_instance_without_execution(ready_inputs):
    f = ready_inputs
    original = f.employee.copy()
    old = f.a.refs["skill"]
    successor(f.a)
    with f.a.repository.pool.connection() as c, c.transaction():
        result, checks = invoke(f, c)
        assert result
        assert f.employee == original
        row = c.execute(
            "SELECT revision_id,digest FROM "
            "digital_employee_definition.instance_bindings "
            "WHERE definition_id=%s",
            (original["employeeDefinitionId"],),
        ).fetchone()
        assert row["revision_id"] == original["employeeDefinitionRevisionId"]
        assert (
            "SKILL",
            "READ_RESOURCE",
            "skill-invocation:prepared-resource:"
            + old.resource_id
            + ":"
            + old.revision_id,
        ) in checks
        assert (
            c.execute("SELECT count(*) n FROM execution_authority.attempts").fetchone()[
                "n"
            ]
            == 0
        )


@pytest.mark.parametrize(
    "damage",
    [
        "disabled",
        "archived",
        "deprecated",
        "revoked",
        "no-publication-head",
        "missing-publication",
        "wrong-publication-digest",
        "wrong-reference-digest",
    ],
)
def test_fixed_binding_never_uses_history_bypass(automation, damage):
    a = automation
    ready = a.run()
    employee = ExactReference.model_validate(ready["assembly"]["definition"])
    old = a.refs["skill"]
    successor(a)
    with a.repository.pool.connection() as c, c.transaction():
        record = c.execute(
            "SELECT record FROM skill_mcp_resource.resources WHERE resource_id=%s",
            (old.resource_id,),
        ).fetchone()["record"]
        if damage == "disabled":
            record["enabled"] = False
        if damage == "archived":
            record["archived"] = True
        if damage == "no-publication-head":
            record["publishedRevisionId"] = None
        if damage == "revoked":
            record["lifecycleState"] = "REVOKED"
        if damage == "deprecated":
            next(r for r in record["revisions"] if r["revisionId"] == old.revision_id)[
                "state"
            ] = "DEPRECATED"
        if damage in {"missing-publication", "wrong-publication-digest"}:
            for fact in record["facts"]:
                if (
                    fact.get("event") == "REVISION_PUBLISHED"
                    and fact.get("subject", {}).get("revisionId") == old.revision_id
                ):
                    if damage == "missing-publication":
                        fact["event"] = "NOT_PUBLICATION"
                    else:
                        fact["subject"]["digest"] = "0" * 64
        c.execute(
            "UPDATE skill_mcp_resource.resources SET record=%s WHERE resource_id=%s",
            (Jsonb(record), old.resource_id),
        )
        if damage == "wrong-reference-digest":
            old = old.model_copy(update={"digest": "0" * 64})
        with pytest.raises((EmployeeDefinitionError, PlanningError)):
            read_employee_member(c, a.e.scope, employee, "SKILL", old)
        # The historical inspection port remains inspection-only.
        if damage in {"disabled", "archived", "deprecated"}:
            assert read_published(c, a.e.scope, "SKILL", old, historical=True)


def test_frozen_skill_reaches_existing_native_pipeline_without_rebinding(
    repository, tmp_path, monkeypatch
):
    """Original owner pipeline, fake K8s and registered synthetic compute only."""
    from copy import deepcopy

    import test_prepared_native_pipeline as pipeline

    original = pipeline.seed

    def seed_with_successor(*args, **kwargs):
        p = original(*args, **kwargs)
        old = p.participants[0].skill.reference
        with repository.pool.connection() as c, c.transaction():
            row = c.execute(
                "SELECT record FROM skill_mcp_resource.resources WHERE resource_id=%s",
                (old.resource_id,),
            ).fetchone()
            record = deepcopy(row["record"])
            revision = next(
                r for r in record["revisions"] if r["revisionId"] == old.revision_id
            )
            record.setdefault("facts", []).append(
                {
                    "event": "REVISION_PUBLISHED",
                    "subject": deepcopy(revision),
                    "actor": "explicit-isolated-owner-fixture",
                }
            )
            later = deepcopy(revision)
            later["revisionId"] = "isolated-later-published"
            later["digest"] = "e" * 64
            record["revisions"].append(later)
            record["publishedRevisionId"] = later["revisionId"]
            c.execute(
                "UPDATE skill_mcp_resource.resources SET record=%s "
                "WHERE resource_id=%s",
                (Jsonb(record), old.resource_id),
            )
        return p

    monkeypatch.setattr(pipeline, "seed", seed_with_successor)
    pipeline.test_six_task_managed_skill_pipeline_restart_readback_and_no_redispatch(
        repository, tmp_path, "sales"
    )


@pytest.mark.parametrize("action", ["UNPUBLISH", "REVOKE_PUBLICATION", "DEPRECATE"])
def test_revoked_employee_cannot_supply_old_member_proof(automation, action):
    a = automation
    ready = a.run()
    ref = ExactReference.model_validate(ready["assembly"]["definition"])
    successor(a)
    owner = a.automation.employees
    value = owner.read(a.e.scope, ref.resource_id, ref.revision_id)
    owner.decide(
        a.e.scope,
        ref.resource_id,
        ref.revision_id,
        ref.digest,
        action,
        expected_version=value["aggregateVersion"],
        decision_id="isolated:revoke",
        command_id="isolated:revoke:" + action,
    )
    with a.repository.pool.connection() as c, pytest.raises(PlanningError):
        read_employee_member(c, a.e.scope, ref, "SKILL", a.refs["skill"])


def test_tool_frozen_member_requires_real_outer_publication_and_exact_receipt(
    automation,
):
    from dataclasses import replace
    from pathlib import Path

    from agent_console.digital_employee_definition import CompositionMember, MemberKind
    from agent_console.tool_definition_postgres import PostgresToolDefinitionRepository
    from test_tool_definition_postgres import read, save
    from test_tool_lifecycle import action

    a = automation
    ready = a.run()
    parent = ExactReference.model_validate(ready["assembly"]["definition"])
    owner = PostgresToolDefinitionRepository(a.repository.pool)
    owner.migrate(Path(__file__).parents[1] / "migrations/0061_tool_definitions.sql")
    tool = save(owner, a.e.scope, effects={"orders": "read-only"})["items"][0]["toolId"]
    action(owner, a.e.scope, tool, "validate", "tool:validate")
    action(owner, a.e.scope, tool, "publish", "tool:publish")
    old = read(owner, a.e.scope, tool)
    repo = a.automation.employees
    with a.repository.pool.connection() as c:
        previous = definition(c, a, parent)
    revision = replace(
        previous,
        revision_id="employee-revision:tool-bound",
        predecessor_revision_id=parent.revision_id,
        members=(
            *previous.members,
            CompositionMember(MemberKind.TOOL, tool, old["revisionId"], old["digest"]),
        ),
    )
    current = repo.read(a.e.scope, parent.resource_id, parent.revision_id)
    value = repo.create(
        revision,
        expected_version=current["aggregateVersion"],
        decision_id="isolated:create-tool-binding",
        command_id="isolated:create-tool-binding",
    )
    for decision in ("VALIDATE", "APPROVE", "PUBLISH"):
        value = repo.decide(
            a.e.scope,
            revision.definition_id,
            revision.revision_id,
            revision.digest,
            decision,
            expected_version=value["aggregateVersion"],
            decision_id="isolated:tool:" + decision,
            command_id="isolated:tool:" + decision,
        )
    action(owner, a.e.scope, tool, "successor", "tool:successor")
    action(owner, a.e.scope, tool, "validate", "tool:next-validate")
    action(owner, a.e.scope, tool, "publish", "tool:next-publish")
    with a.repository.pool.connection() as c:
        with pytest.raises(EmployeeDefinitionError, match="INELIGIBLE"):
            Employee.validate_members(c, revision)
        Employee.validate_members(c, revision, published_binding=True)
        assert (
            repo._read(c, a.e.scope, revision.definition_id, revision.revision_id)[
                "digest"
            ]
            == revision.digest
        )
