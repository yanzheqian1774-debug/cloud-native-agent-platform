"""Read exact criterion owner receipts through the actual ordinary BFF."""

# ruff: noqa: F401,F811
import pytest
from agent_console.context_call_admission import bind_criterion
from agent_console.owned_business_criterion_read import (
    OwnedBusinessCriterionRead,
    criterion_command,
)
from agent_console.workbench_bff import PREFIX, SESSION_COOKIE
from agent_console.workbench_business_problem import business_problem_operations
from fastapi.encoders import jsonable_encoder
from psycopg.types.json import Jsonb
from test_local_accounts_postgres import login
from test_owned_business_creation_read import (
    adopted,
    counters,
    env,
    ordinary,
    owned_created,
    owned_ready,
    pgmark,
    routed,
    setup,
)

pytestmark = [pgmark, pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True)]


@pytest.mark.parametrize(
    "variant",
    [
        "absent",
        "written",
        "linked",
        "partial",
        "wrong_payload",
        "wrong_target",
        "other_key",
        "other_user",
        "different_problem",
        "revoked",
        "problem_read_revoked",
        "wrong_journal_version",
    ],
)
def test_criterion_exact_status_is_read_only(owned_created, variant):
    e = owned_created
    with e.repo.connection_scope() as c:
        state = c.execute(
            "SELECT state FROM private_conversation.journeys WHERE conversation_id=%s",
            (e.conv,),
        ).fetchone()["state"]
        state.update(
            phase="CRITERION",
            pending="criterion",
            problem=jsonable_encoder(e.created["revision"]),
            source=e.business_result["inputSource"],
        )
        c.execute(
            "UPDATE private_conversation.journeys SET state=%s WHERE "
            "conversation_id=%s",
            (Jsonb(state), e.conv),
        )
    if variant == "linked":
        revision = e.created["revision"]
        linked = e.draft.link_problem(
            e.context,
            e.business_result["invocationId"],
            problem_id=revision["business_problem_id"],
            problem_revision_id=revision["revision_id"],
            problem_digest=revision["digest"],
        ).invocation
        assert linked.aggregate_version == state["draft"]["aggregateVersion"] + 1
    reader = OwnedBusinessCriterionRead(
        e.business_owner,
        e.draft.authorization.owner_authorization,
        e.business_repository,
    )
    e.adoption_client.app.state.owned_business_criterion_read = reader
    if variant in ("written", "linked", "partial", "wrong_payload", "revoked"):

        def binding(c, context, owner, result, **kw):
            if variant != "partial":
                assert bind_criterion(c, context, result, kw["problem_id"])
            return result

        operation = next(
            op
            for op in business_problem_operations(e.business_app, task_binding=binding)
            if op.name == "WRITE_CRITERION"
        )
        payload = criterion_command(state).model_dump()
        payload["problemId"] = e.created["revision"]["business_problem_id"]
        if variant == "wrong_payload":
            payload["measurement"] = {"rubric": "不同的完成标准"}
        grants = operation.grant_builder(e.context, {}, payload, {})
        e.business_members.update(grants)
        e.business_work.before(e.context, "WRITE_CRITERION", payload, {}, grants)
        result = e.draft.authorization.owner_authorization.execute(
            e.context,
            grants,
            operation="WRITE_CRITERION",
            payload=payload,
            path={},
            query={},
            handler=operation.handler,
        )
        e.business_work.after(e.context, "WRITE_CRITERION", payload, result)
    if variant == "wrong_journal_version":
        state["draft"]["aggregateVersion"] = 999
        with e.repo.connection_scope() as c:
            c.execute(
                "UPDATE private_conversation.journeys SET state=%s "
                "WHERE conversation_id=%s",
                (Jsonb(state), e.conv),
            )
    if variant == "different_problem":
        state["problem"]["business_problem_id"] = "other-problem"
        with e.repo.connection_scope() as c:
            c.execute(
                "UPDATE private_conversation.journeys SET state=%s "
                "WHERE conversation_id=%s",
                (Jsonb(state), e.conv),
            )
    if variant in ("revoked", "problem_read_revoked"):
        from agent_console.grant_administration_application import (
            GrantRevocationCommand,
        )

        with e.repo.connection_scope() as c:
            grant = c.execute(
                "SELECT grant_id FROM authorization_admin.grants WHERE "
                "subject_principal_id=%s AND owner=%s AND action='READ' "
                "AND exact_resource=%s",
                (
                    e.context.principal_id,
                    "SUCCESS_CRITERION" if variant == "revoked" else "BUSINESS_PROBLEM",
                    "success-criterion:collection"
                    if variant == "revoked"
                    else "business-problem:"
                    + e.created["revision"]["business_problem_id"],
                ),
            ).fetchone()
        e.business_owner.grants.revoke_grant(
            e.context,
            GrantRevocationCommand(
                grant["grant_id"], "TEST_WITHDRAWAL", "criterion-revoke", surrender=True
            ),
        )
    if variant == "other_user":
        secret = login(e.routing_sessions)
        e.adoption_client.cookies.set(SESSION_COOKIE, secret.value)
    before, calls = counters(e), len(e.calls)
    response = e.adoption_client.get(
        PREFIX + f"/conversations/{e.conv}/criterion-status",
        params={
            "draftInvocationId": e.business_result["invocationId"],
            "requestKey": "wrong"
            if variant in ("wrong_target", "other_key")
            else state["key"] + ":criterion",
        },
    )
    if variant in ("wrong_target", "other_key", "wrong_journal_version"):
        assert response.status_code == 409, response.text
    elif variant in (
        "revoked",
        "problem_read_revoked",
        "different_problem",
        "other_user",
    ):
        assert response.status_code == 403, response.text
    else:
        assert response.status_code == 200, response.text
        assert (
            response.json()["result"]["state"]
            == {
                "absent": "NOT_WRITTEN",
                "written": "WRITTEN",
                "linked": "WRITTEN",
                "partial": "UNKNOWN",
                "wrong_payload": "UNKNOWN",
            }[variant]
        )
    assert counters(e) == before and len(e.calls) == calls
