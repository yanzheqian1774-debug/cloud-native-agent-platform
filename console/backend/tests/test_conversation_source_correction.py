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
        actual = c.execute(
            "SELECT message_id,content FROM private_conversation.messages WHERE conversation_id=%s AND author_id=%s ORDER BY sequence",
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
    first = correct(f.reader, f.records, e.context, e.conv, f.body)
    assert first["state"]["phase"] == "UNDERSTAND"
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
