"""Real adopted source/criteria owners; controlled model output, no second call.

The companion BFF test covers the handoff transaction. This test covers the
confirmed-source reader against the actual retained understanding lineage.
"""
# ruff: noqa: F401,F811 -- Register the existing disposable owner fixture chain.

import pytest
from agent_console.authority_contracts import ExactGrant
from agent_console.context_call_admission import request_row
from agent_console.workbench_fixed_work_source import FixedWorkSourceOwner
from agent_console.workbench_owner_authorization import WorkbenchOwnerError
from owned_business_consumer_support import configure_scope, prepare_source
from owned_business_planning_support import activate_created
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark as pgmark
from test_conversation_relation_bff import routed
from test_owned_business_admission import owned_created, owned_ready
from test_owned_business_consumer_chain import cleanup_consumer_resources
from test_owned_business_result_link import link
from test_owned_conversation_bff import ordinary
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


def test_exact_real_adopted_target_and_literal_message_no_new_model(
    owned_created, tmp_path
):
    e = owned_created
    link(e)
    activate_created(e)
    revision = e.created["revision"]
    owner = FixedWorkSourceOwner(None, e.business_owner, e.business_repository)
    with e.repo.connection_scope() as c:
        *_, actual, ancestry = e.business_owner._source_evidence(
            c, e.context, e.business_result["invocationId"]
        )
        origin_id = (
            ancestry[-1]["target"]["original_context_id"]
            if ancestry
            else actual.context_id
        )
        message_id = request_row(c, origin_id)["record"]["first_user_message_id"]
        original = c.execute(
            "SELECT message_id,content FROM private_conversation.messages WHERE "
            "tenant_id=%s AND security_domain=%s AND conversation_id=%s "
            "AND author_id=%s AND message_id=%s",
            (
                e.context.scope.tenant_id,
                e.context.scope.security_domain,
                e.conv,
                e.context.principal_id,
                message_id,
            ),
        ).fetchone()
    assert original
    state = {
        "problem": revision,
        "userMessageId": original["message_id"],
        "question": original["content"],
    }
    saved = {"draft": {"instruction": original["content"]}}
    members = (
        ExactGrant(
            "BUSINESS_PROBLEM",
            "READ",
            "business-problem:" + revision["business_problem_id"],
        ),
    )
    calls = len(e.calls)

    def read(instruction):
        return e.draft.authorization.owner_authorization.execute(
            e.context,
            members,
            operation="READ_FIXED_WORK_SOURCE",
            payload={},
            path={},
            query={},
            handler=lambda call: owner.confirmed(call, instruction, state, e.conv),
        )

    value = read(saved)
    assert value["understanding"]["invocationId"] == e.business_result["invocationId"]
    assert value["target"]["problem"]["resource_id"] == revision["business_problem_id"]
    assert value["target"]["criterion_revision_ids"] == [
        e.business_criterion["revision"]["revision_id"]
    ]
    assert value["originalMessageId"] == original["message_id"]
    assert value["inputSource"] == e.business_result["inputSource"]
    assert read(saved) == value
    with pytest.raises(WorkbenchOwnerError, match="INSTRUCTION_CHANGED"):
        read({"draft": {"instruction": "unrelated replacement goal"}})
    from agent_console.workbench_bff import PREFIX

    head = e.adoption_client.get(PREFIX + f"/conversations/{e.conv}/head").json()[
        "result"
    ]["conversation"]
    duplicate = e.adoption_client.post(
        PREFIX + f"/conversations/{e.conv}/messages",
        headers=e.adoption_headers,
        json={
            "expectedVersion": head["version"],
            "content": original["content"],
            "focusLinkId": None,
            "idempotencyKey": "same-text-other-goal",
        },
    )
    assert duplicate.status_code == 200, duplicate.text
    other_id = duplicate.json()["result"]["identity"]
    assert other_id != original["message_id"]
    state["userMessageId"] = other_id
    with pytest.raises(WorkbenchOwnerError, match="ORIGINAL_MESSAGE_CHANGED"):
        read(saved)
    assert len(e.calls) == calls

    # Full BIND command uses the real authoring, current grants, adopted-source
    # reader and immutable source store in one authorized transaction.
    from agent_console.authority_contracts import AuthorityError
    from agent_console.grant_administration_application import GrantRevocationCommand
    from fixed_work_binding_support import setup as binding_setup

    state["userMessageId"] = original["message_id"]
    invoke, draft, grants, decision = binding_setup(
        e, tmp_path, state, original["content"]
    )
    preview = invoke("READ_FIXED_WORK_SOURCE")
    assert preview["state"] == "READY_TO_CONFIRM"
    command = dict(
        conversationId=e.conv,
        workDigest=draft["digest"],
        commandId="bind-original",
        previewDigest=preview["previewDigest"],
    )
    with e.repo.connection_scope() as c:
        grants_before = c.execute(
            "SELECT count(*) n FROM authorization_admin.grants"
        ).fetchone()["n"]
        budget_before = c.execute(
            "SELECT * FROM draft_provider_budget.reservations ORDER BY reservation_id"
        ).fetchall()
    with pytest.raises(RuntimeError, match="after-binding-rollback"):
        invoke("BIND_FIXED_WORK_SOURCE", command, fail=True)
    assert invoke("READ_FIXED_WORK_SOURCE")["state"] == "READY_TO_CONFIRM"
    with pytest.raises(WorkbenchOwnerError, match="PREVIEW_CHANGED"):
        invoke("BIND_FIXED_WORK_SOURCE", {**command, "previewDigest": "f" * 64})
    assert e.business.principal_id != e.context.principal_id
    with pytest.raises((AuthorityError, WorkbenchOwnerError)):
        invoke("BIND_FIXED_WORK_SOURCE", command, context=e.business)
    bound = invoke("BIND_FIXED_WORK_SOURCE", command)
    assert bound["state"] == "BOUND" and bound["executionEnabled"] is False
    assert invoke("BIND_FIXED_WORK_SOURCE", command) == bound
    assert invoke("READ_FIXED_WORK_SOURCE") == bound
    with pytest.raises(WorkbenchOwnerError, match="CONFLICT"):
        invoke("BIND_FIXED_WORK_SOURCE", {**command, "commandId": "other-key"})
    with e.repo.connection_scope() as c:
        assert (
            c.execute("SELECT count(*) n FROM fixed_work_sources.bindings").fetchone()[
                "n"
            ]
            == 1
        )
        assert (
            c.execute("SELECT count(*) n FROM authorization_admin.grants").fetchone()[
                "n"
            ]
            == grants_before
        )
        assert (
            c.execute(
                "SELECT * FROM draft_provider_budget.reservations "
                "ORDER BY reservation_id"
            ).fetchall()
            == budget_before
        )
    # Formal grant surrender, not deletion of a projection, blocks replay too.
    for grant_id in decision.grants:
        grants.revoke_grant(
            e.context,
            GrantRevocationCommand(
                grant_id, "TEST_SURRENDER", "source-surrender-" + str(grant_id), True
            ),
        )
    with pytest.raises((AuthorityError, WorkbenchOwnerError)):
        invoke("BIND_FIXED_WORK_SOURCE", command)
    assert len(e.calls) == calls
