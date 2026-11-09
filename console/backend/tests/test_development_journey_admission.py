# ruff: noqa: F401,F811 -- Reuse isolated role and owner fixtures.
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.context_call_admission import request_row
from agent_console.planning_call_admission import PlanningCallAdmission
from test_context_call_admission import env
from test_development_administrator import URL, login, setup

pytestmark = pytest.mark.skipif(not URL, reason="exclusive PostgreSQL required")


def test_new_admin_planning_is_exact_current_and_revocable(env, setup):
    repo, _generation, sessions, _ = setup
    _, context = sessions.authenticate_session(login(sessions, "devadmin").value)
    draft = env.draft.begin(
        context, key="journey-draft", content="new analysis"
    ).invocation
    env.admission.prepare(context, draft)
    service = PlanningCallAdmission(
        env.admission.delegation,
        {**env.limits, "ledger_id": "planning-original", "calls": 8},
    )
    service.migrate()
    with repo.connection_scope() as c:
        c.execute(
            "INSERT INTO authorization_admin.context_call_objects VALUES "
            "('s5-323-demo','isolated-real-demo','BUSINESS_PROBLEM','journey-problem',%s,%s)",
            (draft.context_id, draft.invocation_id),
        )
    request = SimpleNamespace(
        idempotency_key="new-planning",
        target=SimpleNamespace(problem=SimpleNamespace(resource_id="journey-problem")),
        model_dump=lambda **kw: {"idempotency_key": "new-planning"},
    )
    record = {
        "target": {
            "invocation_id": "journey-invocation",
            "suggestion_context_id": "journey-planning-context",
            "input_commitment": "same",
            "problem": {"problem": {"resource_id": "journey-problem"}},
        }
    }
    first = service.prepare_record(context, request, record)
    assert first["admission"]["ready"] is True
    assert service.prepare_record(context, request, record) == first
    with pytest.raises(AuthorityError, match="PAYLOAD_CONFLICT"):
        service.prepare_record(
            context,
            request,
            {"target": {**record["target"], "input_commitment": "changed"}},
        )
    with repo.connection_scope() as c:
        row = request_row(c, first["admission"]["context_id"])
        assert row["subject_id"] == context.principal_id
        assert row["record"]["source_context_id"] == draft.context_id
        assert row["record"]["maximum_new_calls"] == 1
        decision = c.execute(
            "SELECT admission_id FROM authorization_admin.context_call_decisions "
            "WHERE context_id=%s",
            (row["context_id"],),
        ).fetchone()
        c.execute(
            "INSERT INTO authorization_admin.context_call_revocations "
            "(admission_id,actor_id) VALUES(%s,%s)",
            (decision["admission_id"], context.principal_id),
        )
    with pytest.raises(AuthorityError, match="CONTEXT_ADMISSION_REQUIRED"):
        service.prepare_record(context, request, record)
