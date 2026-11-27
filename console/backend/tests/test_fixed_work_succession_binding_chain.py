"""Real pre-message succession -> one existing understanding/adoption -> BIND.

Original model transport and resource publications remain the shared fixture's
controlled boundaries, not actual models or a hosted service acceptance.
"""

# ruff: noqa: F401,F811 -- Explicit existing isolated owner fixture dependencies.
from types import SimpleNamespace

import pytest
from agent_console.context_call_admission import request_row
from agent_console.fixed_chat_facts import binding_facts
from agent_console.fixed_work_authoring_postgres import read as read_work
from agent_console.fixed_work_sources_postgres import read
from agent_console.plan_suggestion_domain import ExactReference
from fastapi.encoders import jsonable_encoder
from owned_business_consumer_support import configure_scope, prepare_source
from owned_business_planning_support import activate_created
from psycopg.types.json import Jsonb
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark as pgmark
from test_conversation_relation_bff import routed
from test_owned_business_admission import owned_created, owned_ready
from test_owned_business_consumer_chain import cleanup_consumer_resources
from test_owned_business_result_link import link
from test_owned_conversation_bff import ordinary as original_ordinary
from test_recovery_bound_understanding import setup
from test_understanding_adoption_bff import adopted

pytestmark = [
    pgmark,
    pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True),
    pytest.mark.parametrize(
        "owned_ready",
        [
            dict(
                mode="SOURCE_SUCCESSOR",
                prepare_source=prepare_source,
                configure_scope=configure_scope,
            )
        ],
        indirect=True,
    ),
]


@pytest.fixture
def ordinary(env, setup, tmp_path):
    from fixed_work_succession_chain_support import before_message

    gen = original_ordinary.__wrapped__(env, setup, tmp_path)
    e = next(gen)
    try:
        before_message(e, tmp_path, setup[2])
        yield e
    finally:
        gen.close()


def test_same_original_chat_successor_actual_adoption_bind_and_service_facts(
    owned_created,
):
    e = owned_created
    link(e)
    activate_created(e)
    source = e.succession_source
    source.owned = e.business_owner
    source.problems = e.business_repository
    scope = (e.context.scope.tenant_id, e.context.scope.security_domain)
    with e.repo.connection_scope() as c:
        *_, actual, ancestry = e.business_owner._source_evidence(
            c, e.context, e.business_result["invocationId"]
        )
        origin = (
            ancestry[-1]["target"]["original_context_id"]
            if ancestry
            else actual.context_id
        )
        message = request_row(c, origin)["record"]["first_user_message_id"]
        original = c.execute(
            "SELECT content FROM private_conversation.messages WHERE "
            "tenant_id=%s AND security_domain=%s AND conversation_id=%s AND "
            "message_id=%s",
            (*scope, e.conv, message),
        ).fetchone()
        assert original["content"] == "你好"
        # Same retained journal setup as original BIND fixture, not an approval.
        c.execute(
            "UPDATE private_conversation.journeys SET state=%s WHERE "
            "tenant_id=%s AND security_domain=%s AND conversation_id=%s",
            (
                Jsonb(
                    jsonable_encoder(
                        {
                            "problem": e.created["revision"],
                            "userMessageId": message,
                            "question": original["content"],
                        }
                    )
                ),
                *scope,
                e.conv,
            ),
        )
    invoke = e.succession_invoke
    route = e.succession_route
    preview = invoke("READ_FIXED_WORK_SOURCE", path=route)
    assert preview["state"] == "READY_TO_CONFIRM"
    before = len(e.calls)
    command = {
        "conversationId": e.conv,
        "workDigest": e.succession_receipt["record"]["work"]["digest"],
        "commandId": "bind-after-update",
        "previewDigest": preview["previewDigest"],
    }
    bound = invoke("BIND_FIXED_WORK_SOURCE", command, path=route)
    assert bound["state"] == "BOUND"
    assert (
        bound["binding"]["record"]["schemaVersion"] == "fixed-work-confirmed-source.v2"
    )
    assert invoke("BIND_FIXED_WORK_SOURCE", command, path=route) == bound
    with e.repo.connection_scope() as c:
        work = ExactReference.model_validate(e.succession_receipt["record"]["work"])
        b = read(c, scope, "bindings", work.resource_id, work.revision_id)
        h = read(c, scope, "handoffs", work.resource_id, work.revision_id)
        saved = read_work(c, scope, work.resource_id, work.revision_id)
        permit = SimpleNamespace(
            tenantId=scope[0],
            securityDomain=scope[1],
            subjectId=e.context.principal_id,
            conversationId=e.conv,
            work=work,
            bindingDigest=b["digest"],
        )
        assert binding_facts(b, h, saved, permit) == bound["binding"]["record"]
        assert (
            c.execute("SELECT count(*) n FROM fixed_work_sources.bindings").fetchone()[
                "n"
            ]
            == 0
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM fixed_work_successions.bindings"
            ).fetchone()["n"]
            == 1
        )
    from fixed_work_succession_chain_support import check_service_source

    check_service_source(e, bound)
    assert len(e.calls) == before
