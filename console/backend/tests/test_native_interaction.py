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
    repository, tmp_path
):
    seed_pipeline(repository, tmp_path, "cost")
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
        digest="a" * 64,
        participants=[],
        semantics=NS(target=NS(problem=NS(resource_id="problem"))),
    )
    principal = NS(
        principal_id="actor",
        tenant_id=scope.namespace,
        security_domain=scope.security_domain,
    )
    app = NS(principal=principal, validate=lambda prepared: None)
    authority = NS(
        require=lambda *args: None
    )  # Controlled grants, no admin read bypass.
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
                call = NS(
                    connection=c, authority=authority, context=NS(principal_id="actor")
                )
                view = interaction.progress(call, app, p)
            if view["questions"]:
                break
            time.sleep(0.02)
        q = view["questions"][0]
        payload = {k: q[k] for k in ["invocationId", "questionKey", "questionDigest"]}
        payload.update(conversationId="conversation", answer="production")

        def revoked(*args):
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")

        authority.require = revoked
        with repository.pool.connection() as c, c.transaction():
            denied = NS(
                connection=c,
                authority=authority,
                context=NS(principal_id="actor"),
                payload=payload,
            )
            with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
                interaction.progress(denied, app, p)
            with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
                interaction.answer(denied, app, p)
            assert (
                c.execute(
                    "SELECT count(*) AS n FROM skill_invocation.native_loop_records WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s AND record_key='input:answer'",
                    (*identity, row["skill_invocation_id"]),
                ).fetchone()["n"]
                == 0
            )
        authority.require = lambda *args: None
        for changed, reason in [
            ({"conversationId": "wrong"}, "CONVERSATION_MISMATCH"),
            ({"questionDigest": "b" * 64}, "QUESTION_NOT_FOUND"),
            ({"invocationId": "another-invocation"}, "QUESTION_NOT_FOUND"),
            ({"questionKey": "another-question"}, "QUESTION_NOT_FOUND"),
        ]:
            with repository.pool.connection() as c, c.transaction():
                call = NS(
                    connection=c,
                    authority=authority,
                    context=NS(principal_id="actor"),
                    payload={**payload, **changed},
                )
                with pytest.raises(AuthorityError, match=reason):
                    interaction.answer(call, app, p)
        with repository.pool.connection() as c, c.transaction():
            call = NS(
                connection=c,
                authority=authority,
                context=NS(principal_id="other"),
                payload=payload,
            )
            with pytest.raises(AuthorityError, match="PRINCIPAL_MISMATCH"):
                interaction.answer(call, app, p)
            call.context.principal_id = "actor"
            assert interaction.answer(call, app, p) == {
                "accepted": True,
                "replayed": False,
            }
        assert waiting.result(timeout=3)["answer"] == "production"
    with repository.pool.connection() as c, c.transaction():
        call = NS(
            connection=c,
            authority=authority,
            context=NS(principal_id="actor"),
            payload=payload,
        )
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


@pytest.mark.parametrize("terminal", [None, "SUCCEEDED", "STOPPED", "OUTCOME_UNKNOWN"])
def test_first_model_progress_and_terminal_unknown_are_not_conflated(
    monkeypatch, terminal
):
    rows = [
        {
            "skill_invocation_id": "inv",
            "record_key": "inv",
            "result": {"status": terminal} if terminal else None,
        },
        {"skill_invocation_id": "inv", "record_key": "inv:0:MODEL", "result": None},
    ]
    monkeypatch.setattr(interaction, "records", lambda *args: rows)

    class Connection:
        def execute(self, sql):
            assert "to_regclass('skill_invocation.native_wait_heads')" in sql
            return NS(fetchone=lambda: {"present": None})

    view = interaction.progress(NS(connection=Connection()), None, NS(run_id="run"))
    assert view["steps"] == view["questions"] == []
    assert view["modelInFlight"] is (terminal is None)
    assert (
        rows[1]["result"] is None
    )  # Unknown reservation/claim is not resolved or replayed.


@pytest.mark.parametrize(
    "denial", [None, "subject", "scope", "execution", "resource", "revoked"]
)
def test_progress_exact_reader_without_administrator_and_fail_closed(
    monkeypatch, denial
):
    from agent_console.authority_contracts import ExactGrant

    principal = NS(principal_id="human:ordinary", tenant_id="t", security_domain="d")
    p = NS(
        namespace="other" if denial == "scope" else "t",
        security_domain="d",
        run_id="run-exact",
        digest="a" * 64,
        participants=["participant"],
    )
    expected = (
        "human:ordinary",
        "EXECUTION",
        "READ",
        "governed-execution:prepared:" + p.digest,
    )
    granted_resource = ExactGrant(
        "KNOWLEDGE", "READ_RESOURCE", "knowledge:prepared-resource:source:r1"
    )
    monkeypatch.setattr(
        interaction, "resource_read_grants", lambda *args: (granted_resource,)
    )
    reads, checks = [], []

    class Authority:
        def require(self, actor, owner, action, target):
            value = (actor.principal_id, owner, action, target)
            checks.append(value)
            if (
                owner == "EXECUTION"
                and (value != expected or denial in {"execution", "revoked"})
            ) or (owner == "KNOWLEDGE" and denial == "resource"):
                raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    class Connection:
        def execute(self, sql, params=None):
            assert sql.startswith("SELECT")
            reads.append((sql, params))
            return NS(
                fetchone=lambda: {
                    "present": None if "native_wait_heads" in sql else True
                },
                fetchall=lambda: [],
            )

    if denial == "subject":
        principal.principal_id = "human:other"
    call = NS(
        connection=Connection(),
        authority=Authority(),
        context=NS(principal_id=principal.principal_id),
    )
    app = NS(principal=principal)
    if denial:
        with pytest.raises(AuthorityError):
            interaction.progress(call, app, p)
        assert reads == []
    else:
        assert interaction.progress(call, app, p) == {
            "runId": "run-exact",
            "steps": [],
            "questions": [],
            "modelInFlight": False,
        }
        assert reads[-2][1] == ("t", "d", "run-exact")
        assert "native_wait_heads" in reads[-1][0]
        assert checks[0] == expected
        assert interaction.progress(call, app, p)["steps"] == []
        assert len(reads) == 6
    # READ does not substitute for START: answer must validate before any read.
    before = len(reads)

    def denied_start(prepared):
        raise AuthorityError("START_REVOKED")

    app.validate = denied_start
    with pytest.raises(AuthorityError, match="START_REVOKED"):
        interaction.answer(call, app, p)
    assert len(reads) == before


def test_ordinary_answer_requires_real_application_start_admission_before_query():
    from agent_console.prepared_execution_application import (
        PreparedExecutionApplication,
    )
    from agent_console.workbench_business_problem import OwnerPrincipal

    principal = OwnerPrincipal("human:ordinary", "t", "d")
    checks = []

    class Authority:
        def require(self, actor, owner, action, resource):
            checks.append((actor, owner, action, resource))
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    class Connection:
        def execute(self, *args):
            pytest.fail("Denied answer must not query or write journal")

    call = NS(
        connection=Connection(),
        authority=Authority(),
        context=NS(principal_id=principal.principal_id),
    )
    app = PreparedExecutionApplication(call.connection, principal, call.authority)
    p = NS(namespace="t", security_domain="d", digest="a" * 64)
    with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
        interaction.answer(call, app, p)
    assert checks == [
        (principal, "EXECUTION", "START", "governed-execution:prepared:" + p.digest)
    ]


@pytest.mark.parametrize(
    "origin",
    ["exact", "other-subject", "other-conversation", "ambiguous", "partial-tables"],
)
def test_answer_pins_existing_problem_context_origin(monkeypatch, origin):
    p = NS(
        namespace="t",
        security_domain="d",
        run_id="run",
        semantics=NS(target=NS(problem=NS(resource_id="problem"))),
    )
    body = {
        "invocationId": "inv",
        "questionKey": "q",
        "questionDigest": "a" * 64,
        "conversationId": "original",
        "answer": "production",
    }
    question = {
        "skill_invocation_id": "inv",
        "record_key": "q:question",
        "request_digest": body["questionDigest"],
        "result": {
            "principal": "human:ordinary",
            "workflowRunId": "run",
            "expiresAt": (datetime.now(UTC) + timedelta(minutes=1)).isoformat(),
        },
    }
    monkeypatch.setattr(interaction, "records", lambda *args: [question])
    original = {"subject_id": "human:ordinary", "conversation_id": "original"}
    origins = [
        {
            **original,
            **(
                {"subject_id": "human:other"}
                if origin == "other-subject"
                else {"conversation_id": "other"}
                if origin == "other-conversation"
                else {}
            ),
        }
    ]
    if origin == "ambiguous":
        origins.append(original)
    prior = {
        "request_digest": body["questionDigest"],
        "result": {
            "kind": "NATIVE_ANSWER",
            "answer": "production",
            "conversationId": "original",
            "principal": "human:ordinary",
            "questionDigest": body["questionDigest"],
        },
    }

    class Connection:
        def execute(self, sql, params=None):
            assert sql.startswith("SELECT")
            if "private_conversation.links" in sql:
                return NS(
                    fetchall=lambda: [
                        {"conversation_id": "original"},
                        {"conversation_id": "other"},
                    ]
                )
            if "to_regclass('skill_invocation.native_wait_heads')" in sql:
                return NS(fetchone=lambda: {"t": None})
            if "to_regclass" in sql:
                return NS(
                    fetchone=lambda: {
                        "objects": True,
                        "requests": origin != "partial-tables",
                    }
                )
            if "context_call_objects" in sql:
                assert params == ("t", "d", "problem")
                return NS(fetchall=lambda: origins)
            if "native_loop_records" in sql:
                return NS(fetchone=lambda: prior)
            pytest.fail("Unexpected answer query")

    call = NS(
        connection=Connection(), context=NS(principal_id="human:ordinary"), payload=body
    )
    app = NS(validate=lambda p: None)
    if origin == "exact":
        assert interaction.answer(call, app, p) == {"accepted": True, "replayed": True}
    else:
        with pytest.raises(AuthorityError, match="CONVERSATION_MISMATCH"):
            interaction.answer(call, app, p)
