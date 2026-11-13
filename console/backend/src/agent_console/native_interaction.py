# ruff: noqa: E501 -- Exact owner SQL.
"""Bounded interaction within a RUNNING Skill; no lifecycle or retry semantics."""

import time
from datetime import UTC, datetime, timedelta

from agent_runtime.native_loop import LoopBoundaryError, digest
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import AuthorityError
from .prepared_execution_resources import resource_read_grants


class NativeAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invocationId: str = Field(min_length=1, max_length=250)
    questionKey: str = Field(min_length=1, max_length=350)
    questionDigest: str = Field(pattern="^[0-9a-f]{64}$")
    conversationId: str = Field(min_length=1, max_length=200)
    answer: str = Field(min_length=1, max_length=1800)


def await_answer(
    journal,
    question,
    *,
    key,
    remaining_seconds,
    current,
    principal,
    run_id,
    policy_expiry,
):
    expiry = min(
        datetime.now(UTC) + timedelta(seconds=min(180, remaining_seconds - 65)),
        policy_expiry,
    )
    if expiry <= datetime.now(UTC):
        raise LoopBoundaryError("NATIVE_INPUT_DEADLINE")
    record = {
        "kind": "NATIVE_QUESTION",
        "question": question,
        "questionKey": key,
        "principal": principal,
        "workflowRunId": run_id,
        "expiresAt": expiry.isoformat(),
    }
    commitment = digest(record)
    question_key = key + ":question"
    if journal.claim(question_key, commitment) is not None:
        raise ValueError("NATIVE_QUESTION_ALREADY_CLAIMED")
    journal.finish(question_key, commitment, record)
    while datetime.now(UTC) < expiry:
        if not current():
            raise LoopBoundaryError("NATIVE_INPUT_AUTHORIZATION_ENDED")
        with journal.pool.connection() as c:
            row = c.execute(
                "SELECT request_digest,result FROM skill_invocation.native_loop_records WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s AND record_key=%s",
                (*journal.identity, key + ":answer"),
            ).fetchone()
        if row:
            if row["request_digest"] != commitment or not row["result"]:
                raise ValueError("NATIVE_ANSWER_IDENTITY_CONFLICT")
            return {
                "question": question,
                "answer": row["result"]["answer"],
                "questionDigest": commitment,
            }
        time.sleep(0.25)
    raise LoopBoundaryError("NATIVE_INPUT_EXPIRED")


def records(call, app, p):
    if (p.namespace, p.security_domain) != (
        app.principal.tenant_id,
        app.principal.security_domain,
    ):
        raise AuthorityError("NATIVE_PROGRESS_NOT_AUTHORIZED")
    call.authority.require(
        app.principal, "EXECUTION", "READ", "governed-execution:prepared:" + p.digest
    )
    for participant in p.participants:
        for grant in resource_read_grants(p, participant):
            call.authority.require(
                app.principal, grant.owner, grant.action, grant.exact_resource
            )
    c = call.connection
    if not c.execute(
        "SELECT to_regclass('skill_invocation.native_loop_records') present"
    ).fetchone()["present"]:
        return []
    return c.execute(
        "SELECT j.skill_invocation_id,j.record_key,j.request_digest,j.result,j.created_at,j.completed_at,i.attempt_id,i.operation FROM skill_invocation.native_loop_records j JOIN skill_invocation.invocations i USING(namespace,security_domain,skill_invocation_id) WHERE i.namespace=%s AND i.security_domain=%s AND i.workflow_run_id=%s ORDER BY j.created_at,j.record_key LIMIT 300",
        (p.namespace, p.security_domain, p.run_id),
    ).fetchall()


def progress(call, app, p):
    rows = records(call, app, p)
    steps, questions = [], []
    terminal_invocations = {
        r["skill_invocation_id"]
        for r in rows
        if r["record_key"] == r["skill_invocation_id"]
        and (r["result"] or {}).get("status")
        in {"SUCCEEDED", "STOPPED", "OUTCOME_UNKNOWN"}
    }
    by_key = {(r["skill_invocation_id"], r["record_key"]): r for r in rows}
    for r in rows:
        value = r["result"] or {}
        if value.get("action") in {"TOOL", "CLARIFY", "FINISH"}:
            base = r["record_key"].removesuffix(":MODEL")
            tool = by_key.get((r["skill_invocation_id"], base + ":TOOL"))
            steps.append(
                {
                    "id": r["record_key"],
                    "decision": value,
                    "at": r["completed_at"].isoformat(),
                    "output": tool["result"] if tool else None,
                    "toolState": "COMPLETED"
                    if tool and tool["completed_at"]
                    else "RUNNING"
                    if tool
                    else "NOT_STARTED",
                }
            )
        if value.get("kind") == "NATIVE_QUESTION":
            answer = by_key.get(
                (r["skill_invocation_id"], value["questionKey"] + ":answer")
            )
            questions.append(
                {
                    "invocationId": r["skill_invocation_id"],
                    "questionKey": value["questionKey"],
                    "questionDigest": r["request_digest"],
                    "question": value["question"],
                    "expiresAt": value["expiresAt"],
                    "answer": answer["result"]["answer"]
                    if answer and answer["result"]
                    else None,
                    "expired": datetime.fromisoformat(value["expiresAt"])
                    <= datetime.now(UTC),
                }
            )
    return {
        "runId": p.run_id,
        "steps": steps,
        "questions": questions,
        "modelInFlight": any(
            r["record_key"].endswith(":MODEL")
            and r["result"] is None
            and r["skill_invocation_id"] not in terminal_invocations
            for r in rows
        ),
    }


def answer(call, app, p):
    app.validate(p)
    rows = records(call, app, p)
    body = call.payload
    question = next(
        (
            r
            for r in rows
            if r["skill_invocation_id"] == body["invocationId"]
            and r["record_key"] == body["questionKey"] + ":question"
        ),
        None,
    )
    if not question or question["request_digest"] != body["questionDigest"]:
        raise AuthorityError("NATIVE_QUESTION_NOT_FOUND")
    q = question["result"]
    if (
        not q
        or q["principal"] != call.context.principal_id
        or q["workflowRunId"] != p.run_id
    ):
        raise AuthorityError("NATIVE_QUESTION_PRINCIPAL_MISMATCH")
    linked = call.connection.execute(
        "SELECT DISTINCT l.conversation_id FROM private_conversation.links l JOIN private_conversation.conversations c USING(tenant_id,security_domain,conversation_id) WHERE l.tenant_id=%s AND l.security_domain=%s AND c.owner_id=%s AND l.target->>'problemId'=%s",
        (
            p.namespace,
            p.security_domain,
            call.context.principal_id,
            p.semantics.target.problem.resource_id,
        ),
    ).fetchall()
    tables = call.connection.execute(
        "SELECT to_regclass('authorization_admin.context_call_objects') AS objects, to_regclass('authorization_admin.context_call_requests') AS requests"
    ).fetchone()
    if bool(tables["objects"]) != bool(tables["requests"]):
        raise AuthorityError("NATIVE_QUESTION_CONVERSATION_MISMATCH")
    origins = (
        call.connection.execute(
            "SELECT r.subject_id,r.record->>'conversation_id' AS conversation_id FROM authorization_admin.context_call_objects o JOIN authorization_admin.context_call_requests r USING(tenant_id,security_domain,context_id) WHERE o.tenant_id=%s AND o.security_domain=%s AND o.owner='BUSINESS_PROBLEM' AND o.resource_id=%s LIMIT 2",
            (p.namespace, p.security_domain, p.semantics.target.problem.resource_id),
        ).fetchall()
        if tables["objects"]
        else []
    )
    if origins:
        allowed = (
            len(origins) == 1
            and origins[0]
            == {
                "subject_id": call.context.principal_id,
                "conversation_id": body["conversationId"],
            }
            and {"conversation_id": body["conversationId"]} in linked
        )
    else:
        # Legacy work without context objects must have one unambiguous origin.
        allowed = linked == [{"conversation_id": body["conversationId"]}]
    if not allowed:
        raise AuthorityError("NATIVE_QUESTION_CONVERSATION_MISMATCH")
    value = {
        "kind": "NATIVE_ANSWER",
        "answer": body["answer"].strip(),
        "conversationId": body["conversationId"],
        "principal": call.context.principal_id,
        "questionDigest": body["questionDigest"],
    }
    if not value["answer"]:
        raise AuthorityError("NATIVE_ANSWER_EMPTY")
    identity = (
        p.namespace,
        p.security_domain,
        body["invocationId"],
        body["questionKey"] + ":answer",
    )
    prior = call.connection.execute(
        "SELECT request_digest,result FROM skill_invocation.native_loop_records WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s AND record_key=%s",
        identity,
    ).fetchone()
    if prior:
        if prior != {"request_digest": body["questionDigest"], "result": value}:
            raise AuthorityError("NATIVE_ANSWER_CONFLICT")
        return {"accepted": True, "replayed": True}
    if datetime.fromisoformat(q["expiresAt"]) <= datetime.now(UTC):
        raise AuthorityError("NATIVE_QUESTION_EXPIRED")
    state = call.connection.execute(
        "SELECT record FROM execution_authority.prepared_run_progress WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s FOR UPDATE",
        (p.namespace, p.security_domain, p.run_id),
    ).fetchone()
    if (
        not state
        or state["record"]["state"] != "RUNNING"
        or state["record"].get("cancellation_request_id")
    ):
        raise AuthorityError("NATIVE_RUN_NOT_ACCEPTING_INPUT")
    inserted = call.connection.execute(
        "INSERT INTO skill_invocation.native_loop_records(namespace,security_domain,skill_invocation_id,record_key,request_digest,result,completed_at) VALUES(%s,%s,%s,%s,%s,%s,now()) ON CONFLICT DO NOTHING RETURNING record_key",
        (*identity, body["questionDigest"], Jsonb(value)),
    ).fetchone()
    if not inserted:
        raise AuthorityError("NATIVE_ANSWER_CONFLICT")
    return {"accepted": True, "replayed": False}
