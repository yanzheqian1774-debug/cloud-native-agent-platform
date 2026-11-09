# ruff: noqa: E501, F811 -- Isolated owner SQL and fixture imports.
"""Real isolated journal interaction; test grants are not live admission proof."""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from agent_console import native_interaction as interaction
from agent_console.authority_contracts import AuthorityError
from agent_console.native_loop_journal import NativeLoopJournal
from psycopg.types.json import Jsonb
from test_plan_suggestion_v2 import repository  # noqa: F401
from test_prepared_native_pipeline import (
    test_six_task_managed_skill_pipeline_restart_readback_and_no_redispatch as seed_pipeline,
)


def test_persisted_question_original_conversation_and_exact_answer(
    repository, tmp_path, monkeypatch
):
    seed_pipeline(repository, tmp_path, "cost")
    monkeypatch.setattr(interaction, "for_call", lambda call: True)
    with repository.pool.connection() as c, c.transaction():
        for filename in ["0046_private_conversation.sql", "0050_native_loop.sql"]:
            c.execute((Path(__file__).parents[1] / "migrations" / filename).read_text())
        row = c.execute(
            "SELECT namespace,security_domain,skill_invocation_id,workflow_run_id FROM skill_invocation.invocations LIMIT 1"
        ).fetchone()
        scope = NS(namespace=row["namespace"], security_domain=row["security_domain"])
        identity = (scope.namespace, scope.security_domain)
        c.execute(
            "INSERT INTO private_conversation.conversations(tenant_id,security_domain,conversation_id,owner_id,title,request_key,request_digest) VALUES(%s,%s,'conversation','actor','test','request','digest')",
            identity,
        )
        c.execute(
            "INSERT INTO private_conversation.links(tenant_id,security_domain,conversation_id,link_id,target,created_by,request_key,request_digest) VALUES(%s,%s,'conversation','link',%s,'actor','request','digest')",
            (*identity, Jsonb({"problemId": "problem"})),
        )
        c.execute(
            "UPDATE execution_authority.prepared_run_progress SET record=jsonb_set(record,'{state}','\"RUNNING\"') WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s",
            (*identity, row["workflow_run_id"]),
        )
    p = NS(
        **vars(scope),
        run_id=row["workflow_run_id"],
        participants=[],
        semantics=NS(target=NS(problem=NS(resource_id="problem"))),
    )
    app = NS(principal="actor", validate=lambda prepared: None)
    journal = NativeLoopJournal(repository.pool, scope, row["skill_invocation_id"])
    with ThreadPoolExecutor() as pool:
        waiting = pool.submit(
            interaction.await_answer,
            journal,
            "Which policy?",
            key="input",
            remaining_seconds=80,
            current=lambda: True,
            principal="actor",
            run_id=p.run_id,
            policy_expiry=datetime.now(UTC) + timedelta(minutes=1),
        )
        for _ in range(100):
            with repository.pool.connection() as c:
                call = NS(connection=c, context=NS(principal_id="actor"))
                view = interaction.progress(call, app, p)
            if view["questions"]:
                break
            time.sleep(0.02)
        q = view["questions"][0]
        payload = {k: q[k] for k in ["invocationId", "questionKey", "questionDigest"]}
        payload.update(conversationId="conversation", answer="production")
        for changed, reason in [
            ({"conversationId": "wrong"}, "CONVERSATION_MISMATCH"),
            ({"questionDigest": "b" * 64}, "QUESTION_NOT_FOUND"),
        ]:
            with repository.pool.connection() as c, c.transaction():
                call = NS(
                    connection=c,
                    context=NS(principal_id="actor"),
                    payload={**payload, **changed},
                )
                with pytest.raises(AuthorityError, match=reason):
                    interaction.answer(call, app, p)
        with repository.pool.connection() as c, c.transaction():
            call = NS(connection=c, context=NS(principal_id="other"), payload=payload)
            with pytest.raises(AuthorityError, match="PRINCIPAL_MISMATCH"):
                interaction.answer(call, app, p)
            call.context.principal_id = "actor"
            assert interaction.answer(call, app, p) == {
                "accepted": True,
                "replayed": False,
            }
        assert waiting.result(timeout=3)["answer"] == "production"
    with repository.pool.connection() as c, c.transaction():
        call = NS(connection=c, context=NS(principal_id="actor"), payload=payload)
        assert interaction.answer(call, app, p)["replayed"]
        call.payload = {**payload, "answer": "staging"}
        with pytest.raises(AuthorityError, match="ANSWER_CONFLICT"):
            interaction.answer(call, app, p)
        assert (
            interaction.progress(call, app, p)["questions"][0]["answer"] == "production"
        )
        assert not interaction.progress(
            call, app, NS(**{**vars(p), "run_id": "other"})
        )["questions"]
