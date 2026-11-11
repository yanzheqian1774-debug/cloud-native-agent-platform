"""Candidate reuse must not cache an authorization decision."""

from types import SimpleNamespace

import pytest
from agent_console import bounded_task_authorization as module
from agent_console.authority_contracts import AuthorityError, ExactGrant
from test_workbench_pagination import context


def test_batch_rechecks_revocation_and_records_each_success(monkeypatch):
    grant = ExactGrant("EXECUTION", "READ", "run:one")
    spec = SimpleNamespace(permissions=[grant], derived_permissions=[])
    rows, checks, statements = [], [], []

    class Connection:
        def execute(self, sql, params=None):
            statements.append(sql)
            return self

        def fetchone(self):
            return {"name": "bounded_task_requests"}

        def fetchall(self):
            return list(rows)

    def current(c, candidate):
        checks.append(candidate)
        if len(checks) == 2:
            raise AuthorityError("TASK_AUTHORIZATION_REVOKED")
        return {"decision_id": "decision:one"}

    monkeypatch.setattr(
        module.TaskAuthorizationRequest, "model_validate", lambda v: spec
    )
    monkeypatch.setattr(module, "current", current)
    c = Connection()
    empty = module.ExactDecisionBatch(c, context())
    assert empty(grant) is None
    rows.append({"record": {}, "request_id": "request:one"})
    assert empty(grant) is None
    batch = module.ExactDecisionBatch(c, context())
    assert batch(grant)["decision_id"] == "decision:one"
    assert batch(grant) is None
    assert len(checks) == 2
    assert sum("to_regclass" in s for s in statements) == 2
    assert sum("SELECT *" in s for s in statements) == 2
    assert sum("bounded_task_effects" in s for s in statements) == 1
    assert batch(grant)["decision_id"] == "decision:one"
    assert sum("bounded_task_effects" in s for s in statements) == 2


def test_failed_candidate_read_propagates_without_allowing():
    class Connection:
        def execute(self, *a):
            raise RuntimeError("storage unavailable")

    batch = module.ExactDecisionBatch(Connection(), context())
    with pytest.raises(RuntimeError, match="storage unavailable"):
        batch(ExactGrant("EXECUTION", "READ", "run:one"))
    assert batch.rows is None
