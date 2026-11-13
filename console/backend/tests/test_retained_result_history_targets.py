"""Bounded read targets never infer future outputs or execution authority."""

from types import SimpleNamespace as NS

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.conversation_work_history import result_read_targets
from agent_console.prepared_skill_invocation import planned_outputs
from test_execution_preparation import preparation


@pytest.mark.parametrize("case", ["missing", "changed", "zero", "one"])
def test_saved_preparation_and_actual_attempt_bounds(monkeypatch, case):
    p = preparation()
    calls = []

    class Connection:
        def execute(self, sql, params):
            assert sql.startswith("SELECT ")
            assert params == (p.namespace, p.security_domain, p.run_id)
            return NS(fetchone=lambda: None if case == "missing" else {"present": 1})

    def read(*args):
        calls.append(args)
        assert args == (p.namespace, p.security_domain, p.run_id)
        return (object() if case == "changed" else p), NS(
            tasks=[
                NS(task_id=t.task_id, attempt_ordinal=0 if case == "zero" else 1)
                for t in p.participants
            ]
        )

    monkeypatch.setattr(
        "agent_console.execution_preparation_postgres.PreparedExecutionStore",
        lambda c: NS(read=read),
    )
    if case == "changed":
        with pytest.raises(AuthorityError, match="WORK_SOURCE_MISMATCH"):
            result_read_targets(Connection(), p)
        return
    result = result_read_targets(Connection(), p)
    if case == "missing":
        assert result == set() and calls == []
        return
    assert all(g.action in {"READ", "READ_REFERENCE"} for g in result)
    output = {
        g.exact_resource for g in result if g.owner in {"EVIDENCE", "RESOURCE_USE"}
    }
    if case == "zero":
        assert output == set()
    else:
        progress = NS(
            tasks=[NS(task_id=t.task_id, attempt_ordinal=1) for t in p.participants]
        )
        assert output == {
            v[k]
            for v in planned_outputs(p, progress)
            for k in ("evidenceGrant", "resourceGrant")
        }
