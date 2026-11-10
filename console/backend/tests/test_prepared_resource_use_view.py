from copy import deepcopy
from types import SimpleNamespace as N

import pytest
from agent_console import prepared_resource_use_view as module
from agent_console.resource_use_domain import canonical_digest, stable_id


def fixture(monkeypatch, task_id="analyze", ordinal=1):
    ref = N(resource_id="skill:same", revision_id="skill:r1", digest="a" * 64)
    employee = N(resource_id="employee", revision_id="employee:r1", digest="b" * 64)
    tasks = [
        N(
            task_id=t,
            skill=N(reference=ref, operation=t.upper()),
            definition=employee,
            instance_id="instance",
        )
        for t in ["read", "analyze"]
    ]
    p = N(
        namespace="tenant",
        security_domain="domain",
        run_id="run",
        plan_id="plan",
        plan_version=2,
        plan_digest="c" * 64,
        participants=tasks,
    )
    aid = stable_id("prepared-attempt", "run", task_id, str(ordinal))
    uid = stable_id(
        "resource-use", "tenant", "domain", aid, "SKILL", "skill:primary", "1"
    )
    attempt = {
        "workflow_run_id": "run",
        "task_id": task_id,
        "task_run_id": "task-run:" + task_id,
        "attempt_ordinal": ordinal,
    }
    binding = {
        "scope": {"namespace": "tenant", "security_domain": "domain"},
        "resource_use_id": uid,
        "attempt_id": aid,
        "workflow_run_id": "run",
        "plan_id": "plan",
        "plan_version": 2,
        "plan_digest": "c" * 64,
        "resource_kind": "SKILL",
        "slot_key": "skill:primary",
        "occurrence_ordinal": 1,
        "task_run_id": attempt["task_run_id"],
        "resource_id": ref.resource_id,
        "resource_revision_id": ref.revision_id,
        "resource_digest": ref.digest,
        "digital_employee_definition_id": employee.resource_id,
        "digital_employee_definition_revision_id": employee.revision_id,
        "digital_employee_definition_digest": employee.digest,
        "digital_employee_instance_id": "instance",
    }

    bid = stable_id(
        "skill-binding",
        employee.resource_id,
        employee.revision_id,
        ref.resource_id,
        ref.revision_id,
    )
    binding.update(
        binding_id=bid,
        binding_digest=canonical_digest(
            {
                "bindingId": bid,
                "employeeDefinitionId": employee.resource_id,
                "employeeRevisionId": employee.revision_id,
                "skillId": ref.resource_id,
                "skillRevisionId": ref.revision_id,
                "skillDigest": ref.digest,
                "operation": task_id.upper(),
            }
        ),
    )

    def read_attempt(connection, scope, identity):
        assert scope.namespace == "tenant" and scope.security_domain == "domain"
        assert identity == aid
        return attempt

    monkeypatch.setattr(module, "prepared_attempt", read_attempt)

    class Connection:
        record = binding

        def execute(self, sql, params):
            assert params == ("tenant", "domain", uid)
            return N(
                fetchone=lambda: (
                    {"record": self.record} if self.record is not None else None
                )
            )

    return Connection(), p, uid, attempt


@pytest.mark.parametrize(
    "task_id,ordinal", [("read", 1), ("analyze", 1), ("analyze", 2)]
)
def test_shared_resource_resolves_exact_task_and_retry(monkeypatch, task_id, ordinal):
    c, p, uid, _ = fixture(monkeypatch, task_id, ordinal)
    result = module.read_saved_use_binding(c, p, uid)
    assert result["taskId"] == task_id
    assert result["attemptOrdinal"] == ordinal
    assert result["operation"] == task_id.upper()
    assert result["resource"] == {
        "resource_id": "skill:same",
        "revision_id": "skill:r1",
        "digest": "a" * 64,
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("binding_digest", "foreign"),
        ("plan_digest", "foreign"),
        ("plan_version", 3),
        ("workflow_run_id", "foreign"),
        ("scope", {"namespace": "other", "security_domain": "domain"}),
        ("resource_revision_id", "other"),
        ("resource_digest", "other"),
        ("digital_employee_instance_id", "other"),
        ("task_run_id", "other"),
        ("resource_use_id", "other"),
        ("resource_kind", "MCP"),
        ("attempt_id", None),
    ],
)
def test_inconsistent_binding_has_no_trusted_link(monkeypatch, field, value):
    c, p, uid, _ = fixture(monkeypatch)
    c.record = deepcopy(c.record)
    c.record[field] = value
    assert module.read_saved_use_binding(c, p, uid) is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("task_id", "read"),
        ("workflow_run_id", "other"),
        ("attempt_ordinal", 2),
        ("task_id", "missing"),
    ],
)
def test_attempt_cannot_be_substituted(monkeypatch, field, value):
    c, p, uid, attempt = fixture(monkeypatch)
    attempt[field] = value
    assert module.read_saved_use_binding(c, p, uid) is None


def test_missing_saved_binding_is_not_inferred_from_plan(monkeypatch):
    c, p, uid, _ = fixture(monkeypatch)
    c.record = None
    assert module.read_saved_use_binding(c, p, uid) is None
