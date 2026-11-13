"""Real owner transactions; published-source fixtures, no external model calls."""

# ruff: noqa: F401,F811,E501 -- Shared PG fixtures and exact SQL.
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from agent_console.authority_configuration import RequestabilityRule
from agent_console.authority_contracts import AuthorityError, ExactGrant
from agent_console.business_problem_postgres import PostgresBusinessProblemRepository
from agent_console.conversation_source_correction import correct
from agent_console.grant_administration_application import (
    GrantDecisionCommand,
    GrantRequestCommand,
    GrantRevocationCommand,
)
from agent_console.owned_business_admission import OwnedBusinessAdmission
from agent_console.owned_business_creation_read import OwnedBusinessCreationRead
from agent_console.private_conversation import ConversationError
from agent_console.workbench_prepared_resources import reference
from psycopg.types.json import Jsonb
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark as pgmark
from test_conversation_relation_bff import routed
from test_local_accounts_postgres import login
from test_owned_business_admission import owned_created, owned_ready
from test_owned_business_creation_read import counters
from test_owned_conversation_bff import ordinary
from test_recovery_bound_understanding import setup
from test_understanding_adoption_bff import adopted

pytestmark = [pgmark, pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True)]


@pytest.fixture
def correction(owned_ready, request):
    e = (
        request.getfixturevalue("owned_created")
        if getattr(request, "param", None) == "created"
        else owned_ready
    )
    old = e.business_result["inputSource"]
    new = copy.deepcopy(old)
    new["source"]["resource_id"] = "knowledge:correction"
    grant = ExactGrant(
        "KNOWLEDGE",
        "READ_RESOURCE",
        reference(
            "knowledge", new["source"]["resource_id"], new["source"]["revision_id"]
        ),
    )
    grants = e.business_owner.grants
    generation = grants.generation
    grants._generation_provider = lambda: replace(
        generation,
        requestability=(
            *generation.requestability,
            RequestabilityRule(
                grant.owner, grant.action, grant.exact_resource, "RESOURCE_PREPARATION"
            ),
        ),
    )
    prior = grants.target_validator
    grants.target_validator = NS(
        is_known_exact_target=lambda ctx, g, **kw: (
            g == grant or prior.is_known_exact_target(ctx, g, **kw)
        )
    )
    with e.repo.connection_scope() as c:
        original = c.execute(
            "SELECT record FROM knowledge_operation.knowledge WHERE knowledge_id=%s",
            (old["source"]["resource_id"],),
        ).fetchone()["record"]
        original["knowledgeId"] = new["source"]["resource_id"]
        original["name"] = "Production handover authorized source"
        c.execute(
            "INSERT INTO knowledge_operation.knowledge(namespace,security_domain,knowledge_id,aggregate_version,record) VALUES(%s,%s,%s,1,%s)",
            (
                e.context.scope.tenant_id,
                e.context.scope.security_domain,
                new["source"]["resource_id"],
                Jsonb(original),
            ),
        )
        # The journal carries user messages, never assistant SOURCE facts whose
        # author_id may name the invoking human. Preserve earlier user goals.
        actual = c.execute(
            "SELECT m.message_id,m.content FROM private_conversation.messages m WHERE "
            "m.conversation_id=%s AND m.author_id=%s AND NOT EXISTS "
            "(SELECT 1 FROM private_conversation.message_facts f WHERE "
            "f.conversation_id=m.conversation_id AND f.message_id=m.message_id) ORDER BY m.sequence",
            (e.conv, e.context.principal_id),
        ).fetchall()
        j = c.execute(
            "SELECT state FROM private_conversation.journeys WHERE conversation_id=%s",
            (e.conv,),
        ).fetchone()["state"]
        j.update(
            pending="create-problem",
            error="Error: OWNED_BUSINESS_SOURCE_NOT_AUTHORIZED",
            source=old,
            question=actual[0]["content"],
            messages=[
                {"id": "user:" + m["message_id"], "text": m["content"]} for m in actual
            ],
            log=[],
        )
        c.execute(
            "UPDATE private_conversation.journeys SET state=%s WHERE conversation_id=%s",
            (Jsonb(j), e.conv),
        )
    requested = grants.submit_request(
        e.context,
        GrantRequestCommand("RESOURCE_PREPARATION", (grant,), "correction-source"),
    )
    _, admin = e.routing_sessions.authenticate_session(
        login(e.routing_sessions, "devadmin").value
    )
    grants.decide_request(
        admin,
        GrantDecisionCommand(
            requested.request_id,
            True,
            "ISOLATED_READ",
            "TICKET",
            "source-correction",
            None,
            datetime.now(UTC) + timedelta(hours=1),
            "correction-decision",
        ),
    )
    policy = e.business_owner.policy.model_dump(mode="json")
    policy["scopes"][0]["source"] = new["source"]
    policy["scopes"][0]["documentRules"]["source"] = new["source"]
    path = e.business_owner.path
    path.write_text(json.dumps(policy))
    e.business_owner = OwnedBusinessAdmission(e.admission, path)
    migrations = Path(__file__).parents[1] / "migrations"
    repo = PostgresBusinessProblemRepository(
        e.repo.pool.conninfo,
        migration_path=migrations / "0013_business_problem_authority.sql",
        creator_receipt_migration_path=migrations
        / "0020_business_problem_creator_receipt.sql",
    )
    reader = OwnedBusinessCreationRead(
        e.business_owner, e.draft.authorization.owner_authorization, repo
    )
    records = e.adoption_client.app.state.conversation_actions.records
    with e.repo.connection_scope() as c:
        version = c.execute(
            "SELECT version FROM private_conversation.journeys WHERE conversation_id=%s",
            (e.conv,),
        ).fetchone()["version"]
    body = dict(
        idempotencyKey="correct-source",
        expectedVersion=version,
        draftInvocationId=e.business_result["invocationId"],
        requestKey="initial-work:problem",
        source=new,
    )
    e.adoption_client.app.state.owned_business_creation_read = reader
    yield NS(e=e, reader=reader, records=records, body=body)
    repo.pool.close()


def test_correction_current_owner_preserves_history_and_replays_without_effect(
    correction,
):
    f = correction
    e = f.e
    before = counters(e)
    calls = len(e.calls)
    original = e.business_result.copy()
    with e.repo.connection_scope() as c:
        origin = c.execute(
            "SELECT record FROM authorization_admin.context_call_requests WHERE context_id=%s",
            (e.original["contextId"],),
        ).fetchone()["record"]
        prior = c.execute(
            "SELECT state FROM private_conversation.journeys WHERE conversation_id=%s",
            (e.conv,),
        ).fetchone()["state"]
        assert prior["messages"][0]["id"] != "user:" + origin["first_user_message_id"]
        assert any(
            m["id"] == "user:" + origin["first_user_message_id"]
            for m in prior["messages"]
        )
    first = correct(f.reader, f.records, e.context, e.conv, f.body)
    assert first["state"]["phase"] == "UNDERSTAND"
    assert first["state"]["messages"][:-1] == prior["messages"]
    assert first["state"]["question"] == prior["question"]
    assert "draft" not in first["state"] and "problem" not in first["state"]
    assert first["state"]["source"]["source"] == f.body["source"]["source"]
    assert first["state"]["sourceCorrections"][-1]["source"] == original["inputSource"]
    second = correct(f.reader, f.records, e.context, e.conv, f.body)
    assert second["replayed"] and second["version"] == first["version"]
    assert counters(e) == before and len(e.calls) == calls
    with e.repo.connection_scope() as c, pytest.raises(AuthorityError):
        e.business_owner.admit(c, e.context, e.business_result["invocationId"])


def test_simultaneous_identical_corrections_commit_one_message(correction):
    f = correction

    def run():
        return correct(f.reader, f.records, f.e.context, f.e.conv, f.body)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run) for _ in range(2)]
        results = [future.result(timeout=20) for future in futures]
    assert sorted(r["replayed"] for r in results) == [False, True]
    assert results[0]["version"] == results[1]["version"]
    with f.e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM private_conversation.messages WHERE conversation_id=%s AND request_key=%s",
                (f.e.conv, f.body["idempotencyKey"]),
            ).fetchone()["n"]
            == 1
        )


def test_stale_correction_cannot_replace_current_goal(correction):
    f = correction
    correct(f.reader, f.records, f.e.context, f.e.conv, f.body)
    other = {**f.body, "idempotencyKey": "different-correction"}
    with pytest.raises(ConversationError, match="JOURNEY_VERSION_CONFLICT"):
        correct(f.reader, f.records, f.e.context, f.e.conv, other)


@pytest.mark.parametrize("correction", ["created"], indirect=True)
@pytest.mark.parametrize("partial", [False, True])
def test_created_or_partial_facts_never_allow_correction(correction, partial):
    f = correction
    if partial:
        with f.e.repo.connection_scope() as c:
            c.execute("DELETE FROM business_problem_authority.creator_receipts")
    before = counters(f.e)
    with pytest.raises(
        ConversationError, match="CONVERSATION_SOURCE_CORRECTION_NOT_SAFE"
    ):
        correct(f.reader, f.records, f.e.context, f.e.conv, f.body)
    assert counters(f.e) == before


@pytest.mark.parametrize(
    "variant",
    [
        "archived",
        "other_actor",
        "outside_scope",
        "stale",
        "forged_messages",
        "expired_policy",
        "revoked_read",
    ],
)
def test_correction_rejects_changed_authority_or_history(correction, variant):
    f = correction
    ctx = f.e.context
    body = copy.deepcopy(f.body)
    if variant == "archived":
        with f.e.repo.connection_scope() as c:
            c.execute(
                "UPDATE private_conversation.conversations SET archived_at=now() WHERE conversation_id=%s",
                (f.e.conv,),
            )
    elif variant == "other_actor":
        ctx = replace(ctx, principal_id="human:someone-else")
    elif variant == "outside_scope":
        body["source"] = f.e.business_result["inputSource"]
    elif variant == "stale":
        body["expectedVersion"] += 1
    elif variant == "expired_policy":
        policy = f.e.business_owner.policy.model_dump(mode="json")
        policy["expiresAt"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        f.e.business_owner.path.write_text(json.dumps(policy))
        f.reader.owner = OwnedBusinessAdmission(f.e.admission, f.e.business_owner.path)
    elif variant == "revoked_read":
        ref = body["source"]["source"]
        with f.e.repo.connection_scope() as c:
            target = c.execute(
                "SELECT grant_id FROM authorization_admin.grants WHERE subject_principal_id=%s AND owner='KNOWLEDGE' AND action='READ_RESOURCE' AND exact_resource=%s",
                (
                    ctx.principal_id,
                    reference("knowledge", ref["resource_id"], ref["revision_id"]),
                ),
            ).fetchone()
        f.e.business_owner.grants.revoke_grant(
            ctx,
            GrantRevocationCommand(
                target["grant_id"],
                "TEST_WITHDRAWAL",
                "correction-read-revoke",
                surrender=True,
            ),
        )
    else:
        with f.e.repo.connection_scope() as c:
            c.execute(
                "UPDATE private_conversation.journeys SET state=jsonb_set(state,'{messages,0,text}','\"forged\"'::jsonb) WHERE conversation_id=%s",
                (f.e.conv,),
            )
    before = counters(f.e)
    with pytest.raises((AuthorityError, ConversationError)):
        correct(f.reader, f.records, ctx, f.e.conv, body)
    assert counters(f.e) == before


def test_bff_correction_uses_real_current_session_and_returns_new_journal(correction):
    from agent_console.workbench_bff import PREFIX

    f = correction
    response = f.e.adoption_client.post(
        PREFIX + f"/conversations/{f.e.conv}/source-correction",
        headers=f.e.adoption_headers,
        json=f.body,
    )
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    assert result["state"]["phase"] == "UNDERSTAND"
    assert result["state"]["source"]["source"] == f.body["source"]["source"]


def test_new_message_reads_exact_corrected_source_via_existing_primary_reader(
    correction,
):
    from agent_console.conversation_source_access import ConversationSourceAccess
    from agent_console.conversation_source_input import source_reader

    f = correction
    result = correct(f.reader, f.records, f.e.context, f.e.conv, f.body)
    automation = NS(
        bound_app=lambda call: NS(
            scope=lambda p: NS(namespace=p.tenant_id, security_domain=p.security_domain)
        )
    )
    access = ConversationSourceAccess(
        automation, f.reader.authorizer, f.records, f.e.draft
    )
    read = source_reader(
        automation, f.reader.authorizer, f.records, owned_access=access
    )
    attachment = json.loads(
        read(f.e.context, f.e.conv, result["state"]["userMessageId"])
    )
    assert attachment["source"] == f.body["source"]["source"]
    assert attachment["name"] == "Production handover authorized source"
    assert attachment["readStatus"] == "EXACT_PUBLISHED_SNAPSHOT_READ"
    assert attachment["executionStatus"] == "NOT_EXECUTED"
    assert len(f.e.calls) == f.e.business_model_call_count


def test_old_create_competing_with_correction_cannot_bind_old_source(correction):
    f = correction
    before = counters(f.e)

    def old():
        try:
            with f.e.repo.connection_scope() as c:
                f.e.business_owner.admit(
                    c, f.e.context, f.e.business_result["invocationId"]
                )
        except AuthorityError as exc:
            return exc.reason_code
        return "UNEXPECTED_ADMISSION"

    with ThreadPoolExecutor(max_workers=2) as pool:
        old_request = pool.submit(old)
        new_request = pool.submit(
            correct, f.reader, f.records, f.e.context, f.e.conv, f.body
        )
        assert old_request.result(timeout=20) == "OWNED_BUSINESS_SOURCE_NOT_AUTHORIZED"
        assert new_request.result(timeout=20)["state"]["phase"] == "UNDERSTAND"
    assert counters(f.e) == before


@pytest.mark.parametrize(
    "variant",
    ["optimistic", "wrong_existing", "later_missing", "changed_body", "invalid_id"],
)
def test_initial_optimistic_identity_uses_exact_root_binding_not_text_search(
    correction, variant
):
    from uuid import uuid4

    f = correction
    with f.e.repo.connection_scope() as c:
        row = c.execute(
            "SELECT state FROM private_conversation.journeys WHERE conversation_id=%s",
            (f.e.conv,),
        ).fetchone()
        state = row["state"]
        origin = c.execute(
            "SELECT record FROM authorization_admin.context_call_requests WHERE context_id=%s",
            (f.e.original["contextId"],),
        ).fetchone()["record"]
        root_id = "user:" + origin["first_user_message_id"]
        root_index = next(
            i for i, m in enumerate(state["messages"]) if m["id"] == root_id
        )
        # This case reproduces r2's single current goal; the shared fixture above
        # deliberately keeps earlier valid goals for regression coverage.
        state["messages"] = state["messages"][root_index:]
        state["question"] = state["messages"][0]["text"]
        old = copy.deepcopy(state["messages"])
        optimistic = "user:" + str(uuid4())
        if variant == "wrong_existing":
            # Existing same-body message is not the root-bound initial question.
            identity = str(uuid4())
            c.execute(
                "INSERT INTO private_conversation.messages(tenant_id,security_domain,conversation_id,message_id,sequence,author_id,content,disposition,request_key,request_digest) VALUES(%s,%s,%s,%s,10000,%s,%s,'GOAL_RECORDED','duplicate-body-test','fixture')",
                (
                    *f.records.scope(f.e.context),
                    f.e.conv,
                    identity,
                    f.e.context.principal_id,
                    old[0]["text"],
                ),
            )
            state["messages"][0]["id"] = "user:" + identity
        elif variant == "later_missing":
            state["messages"][-1]["id"] = optimistic
        else:
            state["messages"][0]["id"] = (
                "user:forged" if variant == "invalid_id" else optimistic
            )
            if variant == "changed_body":
                state["messages"][0]["text"] = "different requested goal"
        c.execute(
            "UPDATE private_conversation.journeys SET state=%s WHERE conversation_id=%s",
            (Jsonb(state), f.e.conv),
        )
    before = counters(f.e)
    if variant != "optimistic":
        with pytest.raises(
            ConversationError, match="CONVERSATION_SOURCE_CORRECTION_HISTORY_CHANGED"
        ):
            correct(f.reader, f.records, f.e.context, f.e.conv, f.body)
    else:
        result = correct(f.reader, f.records, f.e.context, f.e.conv, f.body)
        assert result["state"]["messages"][:-1] == old
        repair = result["state"]["sourceCorrections"][-1]["messageIdentityRepairs"]
        assert len(repair) == 1 and repair[0]["oldId"] == optimistic
        assert repair[0]["newId"] == old[0]["id"]
        assert repair[0]["originContextId"] == f.e.original["contextId"]
        assert repair[0]["originInvocationId"] == f.e.original["invocationId"]
        assert correct(f.reader, f.records, f.e.context, f.e.conv, f.body)["replayed"]
    assert counters(f.e) == before


def test_same_actor_assistant_fact_cannot_become_user_history(correction):
    f = correction
    with f.e.repo.connection_scope() as c:
        message = c.execute(
            "SELECT m.message_id,m.content FROM private_conversation.messages m JOIN private_conversation.message_facts f USING(tenant_id,security_domain,conversation_id,message_id) WHERE m.conversation_id=%s AND m.author_id=%s LIMIT 1",
            (f.e.conv, f.e.context.principal_id),
        ).fetchone()
        assert message is not None
        state = c.execute(
            "SELECT state FROM private_conversation.journeys WHERE conversation_id=%s",
            (f.e.conv,),
        ).fetchone()["state"]
        state["messages"].append(
            {"id": "user:" + message["message_id"], "text": message["content"]}
        )
        c.execute(
            "UPDATE private_conversation.journeys SET state=%s WHERE conversation_id=%s",
            (Jsonb(state), f.e.conv),
        )
    before = counters(f.e)
    with pytest.raises(
        ConversationError, match="CONVERSATION_SOURCE_CORRECTION_HISTORY_CHANGED"
    ):
        correct(f.reader, f.records, f.e.context, f.e.conv, f.body)
    assert counters(f.e) == before
