"""Actual BFF GET of owner CREATE facts; no provider or business writes on reads."""

# ruff: noqa: F401,F811 -- Shared isolated fixtures.
from pathlib import Path

import pytest
from agent_console.business_problem_postgres import PostgresBusinessProblemRepository
from agent_console.grant_administration_application import GrantRevocationCommand
from agent_console.owned_business_creation_read import OwnedBusinessCreationRead
from agent_console.workbench_bff import PREFIX, SESSION_COOKIE
from psycopg.types.json import Jsonb
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark as pgmark
from test_conversation_relation_bff import routed
from test_local_accounts_postgres import login
from test_owned_business_admission import owned_created, owned_ready
from test_owned_conversation_bff import ordinary
from test_recovery_bound_understanding import setup
from test_understanding_adoption_bff import adopted

pytestmark = [pgmark, pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True)]


def observe(e):
    return e.adoption_client.get(
        PREFIX + f"/conversations/{e.conv}/create-status",
        params={
            "draftInvocationId": e.business_result["invocationId"],
            "requestKey": "initial-work:problem",
        },
    )


def attach(e, repository):
    e.adoption_client.app.state.owned_business_creation_read = (
        OwnedBusinessCreationRead(
            e.business_owner,
            e.draft.authorization.owner_authorization,
            repository,
        )
    )


def counters(e):
    with e.repo.connection_scope() as c:
        tables = [
            "business_problem_authority.problems",
            "business_problem_authority.creator_receipts",
            "business_problem_authority.idempotency_claims",
            "authorization_admin.owned_business_admissions",
            "authorization_admin.grant_decisions",
            "draft_provider_budget.reservations",
        ]
        from psycopg import sql

        return {
            table: c.execute(
                sql.SQL("SELECT count(*) n FROM {}").format(
                    sql.Identifier(*table.split("."))
                )
            ).fetchone()["n"]
            for table in tables
        }


def test_not_created_requires_all_owner_facts_absent_and_get_has_no_effect(owned_ready):
    e = owned_ready
    migrations = Path(__file__).parents[1] / "migrations"
    repository = PostgresBusinessProblemRepository(
        e.repo.pool.conninfo,
        migration_path=migrations / "0013_business_problem_authority.sql",
        creator_receipt_migration_path=migrations
        / "0020_business_problem_creator_receipt.sql",
    )
    try:
        attach(e, repository)
        before, calls = counters(e), len(e.calls)
        for _ in range(2):
            response = observe(e)
            assert response.status_code == 200, response.text
            assert response.json()["result"]["state"] == "NOT_CREATED"
        assert counters(e) == before and len(e.calls) == calls
    finally:
        repository.pool.close()


@pytest.mark.parametrize(
    "variant",
    [
        "exact",
        "expired_receipt",
        "missing_receipt",
        "changed_goal",
        "revoked_problem_read",
        "other_user",
        "archived",
    ],
)
def test_existing_creation_requires_exact_complete_authorized_facts(
    owned_created, variant
):
    e = owned_created
    attach(e, e.business_repository)
    with e.repo.connection_scope() as c:
        if variant == "expired_receipt":
            c.execute(
                "UPDATE business_problem_authority.creator_receipts SET "
                "receipt_started_at=receipt_started_at-interval '1 hour',"
                "expires_at=expires_at-interval '1 hour'"
            )
        elif variant == "missing_receipt":
            c.execute("DELETE FROM business_problem_authority.creator_receipts")
        elif variant == "changed_goal":
            c.execute(
                "UPDATE private_conversation.journeys SET state=state||%s "
                "WHERE conversation_id=%s",
                (Jsonb({"key": "different-goal"}), e.conv),
            )
    if variant == "revoked_problem_read":
        with e.repo.connection_scope() as c:
            grant = c.execute(
                "SELECT grant_id FROM authorization_admin.grants WHERE "
                "subject_principal_id=%s AND owner='BUSINESS_PROBLEM' "
                "AND action='READ' AND exact_resource=%s",
                (
                    e.context.principal_id,
                    "business-problem:" + e.created["revision"]["business_problem_id"],
                ),
            ).fetchone()
        e.business_owner.grants.revoke_grant(
            e.context,
            GrantRevocationCommand(
                grant["grant_id"],
                "TEST_WITHDRAWAL",
                "creation-read-revoke",
                surrender=True,
            ),
        )
    elif variant == "other_user":
        secret = login(e.routing_sessions)
        e.adoption_client.cookies.set(SESSION_COOKIE, secret.value)
    elif variant == "archived":
        with e.repo.connection_scope() as c:
            c.execute(
                "UPDATE private_conversation.conversations SET archived_at=now() "
                "WHERE conversation_id=%s",
                (e.conv,),
            )
    before, calls = counters(e), len(e.calls)
    response = observe(e)
    if variant in {"revoked_problem_read", "other_user", "archived"}:
        assert response.status_code == 403, response.text
    elif variant == "changed_goal":
        assert response.status_code == 409, response.text
    else:
        assert response.status_code == 200, response.text
        value = response.json()["result"]
        assert value["state"] == (
            "UNKNOWN" if variant == "missing_receipt" else "CREATED"
        )
        if value["state"] == "CREATED":
            assert value["revision"]["digest"] == e.created["revision"]["digest"]
            assert (
                value["revision"]["business_problem_id"]
                == e.created["revision"]["business_problem_id"]
            )
    assert counters(e) == before and len(e.calls) == calls
