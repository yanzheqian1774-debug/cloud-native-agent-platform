"""Current member eligibility must not erase authorized saved execution evidence."""

from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.digital_employee_definition import EmployeeDefinitionError
from agent_console.execution_preparation import initial_progress
from agent_console.workbench_prepared_execution import PreparedExecutionOwner
from test_execution_preparation import preparation


class SavedReadConnection:
    def __init__(self):
        self.content_reads = 0

    def execute(self, query, params):
        assert query.startswith("SELECT"), "Historical reading must not mutate state"
        if "SELECT 1 FROM execution_authority.run_preparations" in query:
            return SimpleNamespace(fetchone=lambda: {"present": 1})
        if "octet_length(content)" in query:
            return SimpleNamespace(
                fetchall=lambda: [{"artifact_id": "saved", "digest": "d" * 64}]
            )
        if "SELECT content FROM" in query:
            self.content_reads += 1
            return SimpleNamespace(fetchone=lambda: {"content": "exact saved result"})
        if "FROM execution_authority.prepared_run_events" in query:
            return SimpleNamespace(
                fetchall=lambda: [{"version": 2, "record": {"action": "SUCCEEDED"}}]
            )
        if "FROM execution_authority.prepared_resource_commands" in query:
            return SimpleNamespace(fetchone=lambda: None)
        raise AssertionError(query)


@pytest.mark.parametrize("evidence_allowed", [False, True])
def test_ineligible_current_member_preserves_saved_read_and_evidence_grants(
    monkeypatch, evidence_allowed
):
    from agent_console import execution_preparation_postgres, prepared_skill_invocation

    p = preparation()
    saved = initial_progress(p)
    monkeypatch.setattr(
        execution_preparation_postgres.PreparedExecutionStore,
        "read",
        lambda *_args, **_kwargs: (p, saved),
    )
    monkeypatch.setattr(prepared_skill_invocation, "planned_outputs", lambda *_args: ())
    connection = SavedReadConnection()

    def require(_principal, owner, _action, _resource):
        if owner == "EVALUATION" or (owner == "EVIDENCE" and not evidence_allowed):
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    def validate(_p):
        raise EmployeeDefinitionError("BOUND_RESOURCE_INELIGIBLE")

    app = SimpleNamespace(
        principal=SimpleNamespace(principal_id="reader"), validate=validate
    )
    call = SimpleNamespace(
        connection=connection, authority=SimpleNamespace(require=require)
    )
    value = PreparedExecutionOwner.read(call, app, p)
    assert value["admission"] == {
        "state": "NOT_ADMITTED",
        "reason": "BOUND_RESOURCE_INELIGIBLE",
    }
    assert value["preparation"] == p.model_dump(mode="json")
    assert value["progress"] == saved.model_dump(mode="json")
    assert value["events"] == [{"version": 2, "record": {"action": "SUCCEEDED"}}]
    assert value["executionStarted"] is True
    assert connection.content_reads == int(evidence_allowed)
    if evidence_allowed:
        assert value["artifacts"][0]["content"] == "exact saved result"
    else:
        assert value["artifacts"][0]["contentAccess"] == "RESTRICTED"
        assert "content" not in value["artifacts"][0]


def test_unexpected_read_error_is_not_disguised_as_admission_rejection(monkeypatch):
    from agent_console import execution_preparation_postgres

    p = preparation()
    monkeypatch.setattr(
        execution_preparation_postgres.PreparedExecutionStore,
        "read",
        lambda *_args, **_kwargs: (p, initial_progress(p)),
    )

    def validate(_p):
        raise RuntimeError("storage unavailable")

    app = SimpleNamespace(
        principal=SimpleNamespace(principal_id="reader"), validate=validate
    )
    call = SimpleNamespace(
        connection=SavedReadConnection(),
        authority=SimpleNamespace(require=lambda *_args: None),
    )
    with pytest.raises(RuntimeError, match="storage unavailable"):
        PreparedExecutionOwner.read(call, app, p)
