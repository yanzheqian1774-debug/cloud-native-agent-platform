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
    successor_request = SimpleNamespace(
        idempotency_key="new-planning-successor",
        target=request.target,
        model_dump=lambda **kw: {"idempotency_key": "new-planning-successor"},
    )
    successor = service.prepare_record(
        context,
        successor_request,
        {
            "target": {
                **record["target"],
                "invocation_id": "successor-invocation",
                "input_commitment": "successor",
            }
        },
    )
    assert successor["admission"]["ready"] is True
    assert successor["admission"]["context_id"] != first["admission"]["context_id"]
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


def test_understanding_testing_cap_preserves_ledger_and_revocation(env, setup):
    from agent_console.context_call_admission import development_call_cap

    repo, _generation, sessions, _ = setup
    _, context = sessions.authenticate_session(login(sessions, "devadmin").value)
    draft = env.draft.begin(
        context, key="bounded-tests", content="sales question"
    ).invocation
    env.admission.prepare(context, draft)
    budget = SimpleNamespace(
        ledger_id=env.limits["ledger_id"], delegation_configuration=env.limits
    )
    with repo.connection_scope() as c:
        row = request_row(c, draft.context_id)
        assert row["record"]["development_call_cap"] == 100
        assert row["record"]["configuration"]["cost_microusd"] == 10000000
        assert development_call_cap(c, budget, draft, 12) == 100
        assert (
            development_call_cap(c, budget, SimpleNamespace(context_id=None), 12) == 12
        )
        decision = c.execute(
            "SELECT admission_id FROM authorization_admin.context_call_decisions "
            "WHERE context_id=%s",
            (draft.context_id,),
        ).fetchone()
        c.execute(
            "INSERT INTO authorization_admin.context_call_revocations"
            "(admission_id,actor_id) VALUES(%s,%s)",
            (decision["admission_id"], context.principal_id),
        )
    with (
        repo.connection_scope() as c,
        pytest.raises(AuthorityError, match="CONTEXT_ADMISSION_REQUIRED"),
    ):
        development_call_cap(c, budget, draft, 12)


def test_capability_provenance_reuses_shared_limits_without_fabricated_draft(
    env, setup
):
    repo, _generation, sessions, _ = setup
    _, context = sessions.authenticate_session(login(sessions, "devadmin").value)
    service = PlanningCallAdmission(
        env.admission.delegation,
        {**env.limits, "ledger_id": "planning-original", "calls": 8},
    )
    service.migrate()
    request = SimpleNamespace(
        idempotency_key="capability-planning",
        target=SimpleNamespace(
            problem=SimpleNamespace(resource_id="capability-problem")
        ),
        model_dump=lambda **kw: {"idempotency_key": "capability-planning"},
    )
    record = {
        "target": {
            "invocation_id": "capability-invocation",
            "suggestion_context_id": "capability-context",
            "input_commitment": "capability-commitment",
            "problem": {"problem": {"resource_id": "capability-problem"}},
        }
    }
    with pytest.raises(AuthorityError, match="OWN_DRAFT_REQUIRED"):
        service.prepare_record(context, request, record)
    proof = {
        "conversationId": "conversation",
        "sourceMessageId": "source",
        "contractDigest": "a" * 64,
    }
    seen = []

    def read_source(ctx, connection, body):
        assert ctx is context and body is request
        seen.append(True)
        return proof

    service.capability_source_reader = read_source
    first = service.prepare_record(context, request, record)
    assert first["admission"]["ready"] is True
    assert first["admission"]["maximum_new_calls"] == 1
    assert service.prepare_record(context, request, record) == first
    assert len(seen) == 2
    with repo.connection_scope() as connection:
        row = request_row(connection, first["admission"]["context_id"])
        assert row["record"]["source_context_id"] is None
        assert row["record"]["capability_source"] == proof
        assert row["record"]["cumulative_call_cap"] == 100
        assert row["record"]["total_cost_cap_microusd"] == 50_000_000
    service.capability_source_reader = lambda *args: {
        **proof,
        "contractDigest": "b" * 64,
    }
    with pytest.raises(AuthorityError, match="SOURCE_CHANGED"):
        service.prepare_record(context, request, record)
    service.capability_source_reader = lambda *args: None
    with pytest.raises(AuthorityError, match="OWN_DRAFT_REQUIRED"):
        service.prepare_record(context, request, record)
