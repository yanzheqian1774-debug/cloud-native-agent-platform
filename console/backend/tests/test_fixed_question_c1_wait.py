"""Real C1/budget/retention + original WAIT owners; provenance ports controlled.

This is a composition slice, not the service-host/BOUND publication acceptance.
The separate grant-owner suite proves issuer issuance; this slice keeps its
presentation/source port explicit and never changes the service command actor.
"""

# ruff: noqa: F401,F811,E501,RUF001 -- Explicit original isolated fixtures.
from datetime import UTC, datetime
from types import SimpleNamespace as NS

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.execution_preparation_postgres import PreparedExecutionStore
from agent_console.fixed_question_answer import AnswerQuestion, FixedQuestionAnswers
from agent_console.fixed_question_context import from_presentation
from agent_console.fixed_question_reader import FixedQuestionReader
from agent_console.fixed_question_store import FixedQuestionStore
from agent_console.native_wait_owner import NativeWaitOwner
from agent_console.private_conversation import digest
from agent_console.workbench_bff import PREFIX
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
)
from native_typed_answer_support import typed_client
from psycopg.types.json import Jsonb
from test_conversation_experience_admission import pytestmark as pgmark
from test_native_typed_answer_chain import actual_root_budget
from test_native_wait_delegated_answer import presentation
from test_native_wait_owner import stop, waiting
from test_owned_business_consumer_chain import adopted, env, ordinary, routed, setup

pytestmark = [pgmark, pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True)]


def test_one_saved_c1_answer_and_controller_receipt_reach_original_service_wait(
    adopted, tmp_path, monkeypatch
):
    e = adopted
    import prepared_execution_support as support
    import test_prepared_native_pipeline as pipeline_support
    from agent_console.plan_suggestion_postgres import PostgresPlanningRepository
    from test_prepared_result_review import seed_criteria

    monkeypatch.setattr(
        pipeline_support,
        "seed_criteria",
        lambda repo, p: seed_criteria(repo, p, schema_prepared=True),
    )
    original = support.preparation
    monkeypatch.setattr(
        support,
        "preparation",
        lambda: original().model_copy(
            update={
                "namespace": e.context.scope.tenant_id,
                "security_domain": e.context.scope.security_domain,
            }
        ),
    )
    repo = PostgresPlanningRepository(e.repo.pool)
    try:
        repo.migrate()

        w = waiting.__wrapped__(
            repo, tmp_path, monkeypatch, NS(param="service", conversation_id=e.conv)
        )
        with repo.pool.connection() as c:
            prepared, _ = PreparedExecutionStore(c).read(
                w.cp.identity.namespace,
                w.cp.identity.security_domain,
                w.cp.identity.workflow_run_id,
            )
        p = presentation(w).model_copy(update={"actorId": e.context.principal_id})
        e.typed_meaning = None
        from agent_console.fixed_chat_api import install_fixed_chat

        composition = NS(
            policy=NS(enabled=True, expiresAt=p.expiresAt, scopes=()),
            clock=lambda: datetime.now(UTC),
        )
        holder = {}
        composition.owners = lambda _: (holder["presentations"], holder["owner"])
        installer = install_fixed_chat(
            composition.policy,
            e.draft.authorization.owner_authorization,
            NS(grants=NS(clock=composition.clock)),
            None,
            question_composition=composition,
        )
        with typed_client(
            e, prepared, w.question, tmp_path, additional_installers=(installer,)
        ) as (
            client,
            headers,
            context,
            service,
            calls,
            authorizer,
        ):
            actions = client.app.state.conversation_actions
            records = actions.records
            target = FixedQuestionReader.target(p)
            with records.connect() as c:
                FixedQuestionStore.migrate(c)
                store = FixedQuestionStore(c, records.scope(context))
                store.anchor(p.identity)
                store.append_presentation(p)
                c.execute(
                    "INSERT INTO private_conversation.links(tenant_id,security_domain,conversation_id,link_id,target,created_by,request_key,request_digest) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        *records.scope(context),
                        e.conv,
                        p.focusLinkId,
                        Jsonb(target),
                        context.principal_id,
                        "controlled-question-link",
                        digest(target),
                    ),
                )

            # Controlled source/presentation boundary; real saved-message lookup,
            # C1 owner, budget settlement and retention below are not replaced.
            def read_question(
                ctx, chat, *, message_id=None, target=None, current=False
            ):
                assert ctx.principal_id == p.actorId and chat == e.conv
                if message_id is not None:
                    with records.connect() as c:
                        row = c.execute(
                            "SELECT focus_link_id FROM private_conversation.messages WHERE conversation_id=%s AND message_id=%s",
                            (chat, message_id),
                        ).fetchone()
                    assert row and row["focus_link_id"] == p.focusLinkId
                else:
                    assert target == FixedQuestionReader.target(p)
                return p, from_presentation(p, message_id or "")

            client.app.state.fixed_question_reader = NS(read=read_question)
            actions.fixed_question_read = lambda ctx, chat, target: read_question(
                ctx, chat, target=target
            )
            actions.fixed_question_for_message = lambda ctx, chat, message: (
                read_question(ctx, chat, message_id=message)
            )
            client.app.state.conversation_relation_reader = (
                lambda ctx, chat, message, *_: read_question(
                    ctx, chat, message_id=message, current=True
                )[1]
            )
            head = client.get(PREFIX + f"/conversations/{e.conv}/head").json()[
                "result"
            ]["conversation"]
            text = "只检查这份材料，不执行上线或回退。"
            saved = client.post(
                PREFIX + f"/conversations/{e.conv}/messages",
                headers=headers,
                json={
                    "content": text,
                    "expectedVersion": head["version"],
                    "idempotencyKey": "delegated-user-answer",
                    "focusLinkId": p.focusLinkId,
                },
            )
            assert saved.status_code == 200, saved.text
            message = saved.json()["result"]["identity"]
            response = client.post(
                PREFIX + "/draft-assistance/invocations",
                headers=headers,
                json={
                    "content": text,
                    "idempotencyKey": "delegated-c1-once",
                    "conversationId": e.conv,
                    "conversationMessageId": message,
                    "conversationRouting": True,
                },
            )
            assert response.status_code in (200, 201), (
                response.text,
                getattr(e, "typed_budget_error", None),
            )
            value = response.json()["result"]
            assert value["state"] == "SUCCEEDED", value
            assert value["conversationDelivery"]["state"] == "SAVED", value
            assert len(calls) == 1
            allowed = True

            def require_current(call, supplied):
                assert supplied == p
                if not allowed:
                    raise AuthorityError("CONTROLLED_QUESTION_ANSWER_REVOKED")

            presentations = NS(
                delivery=NS(records=records),
                clock=lambda: datetime.now(UTC),
                require_current=require_current,
                require_read=require_current,
                read=lambda *args: (w.cp, w.question, prepared, None),
                validate_execution=lambda c, cp: w.owner.authorize(
                    c, cp, "DELEGATED_ANSWER"
                ),
            )
            owner = FixedQuestionAnswers(
                presentations,
                settlement_reader=service.budget.read_invocation_settlement,
                skill_repository=w.owner.skill_repository,
            )
            body = AnswerQuestion(
                presentationId=p.presentationId,
                presentationDigest=p.digest,
                messageId=message,
                requestKey="delegated-c1-once",
                commandId="delegated-answer-once",
            )

            def make_call(c):
                return AuthorizedOwnerCall(
                    "ANSWER_FIXED_QUESTION",
                    context,
                    c,
                    {},
                    {},
                    {},
                    (),
                    AuthorizedOwnerAuthority(authorizer, context, c, 1, ()),
                    1,
                    1,
                )

            with records.connect() as c:
                call = make_call(c)
                denied_owner = FixedQuestionAnswers(
                    presentations,
                    settlement_reader=lambda *_: {
                        "status": "PENDING",
                        "reservation_retained": True,
                    },
                    skill_repository=w.owner.skill_repository,
                )
                with pytest.raises(AuthorityError, match="INTERPRETATION_INVALID"):
                    denied_owner.accept(call, e.conv, body)
                assert (
                    FixedQuestionStore(c, records.scope(context)).answer(
                        p.presentationId
                    )
                    is None
                )
            holder.update(presentations=presentations, owner=owner)
            path = (
                PREFIX
                + f"/conversations/{e.conv}/fixed-work-activity/questions/answers"
            )
            invalid = client.post(path, json=body.model_dump(mode="json"))
            assert invalid.status_code == 403, invalid.text
            accepted = client.post(
                path, headers=headers, json=body.model_dump(mode="json")
            )
            assert accepted.status_code == 200, accepted.text
            receipt = accepted.json()["result"]
            assert receipt["replayed"] is False
            assert receipt["modelDispatched"] is False
            assert receipt["continuationDispatched"] is False
            assert receipt["receipt"]["actorId"] == context.principal_id
            assert receipt["receipt"]["executionSubject"] == w.cp.identity.principal_id
            repeated = client.post(
                path, headers=headers, json=body.model_dump(mode="json")
            )
            assert repeated.status_code == 200, repeated.text
            assert (
                repeated.json()["result"]["receiptDigest"] == receipt["receiptDigest"]
            )
            assert repeated.json()["result"]["replayed"] is True
            recovered = client.get(
                path,
                params={
                    "presentationId": p.presentationId,
                    "commandId": body.commandId,
                },
            )
            assert recovered.status_code == 200, recovered.text
            assert (
                recovered.json()["result"]["receiptDigest"] == receipt["receiptDigest"]
            )
            with records.connect() as c:
                w.owner.confirm_stopped(c, w.cp, stop(w), lambda *_: None)
                frame = w.owner.read_continuation(c, w.cp, w.original_root)
                assert frame is not None
                stored_answer = c.execute(
                    "SELECT result FROM skill_invocation.native_loop_records WHERE record_key=%s",
                    (w.cp.question_key + ":answer",),
                ).fetchone()["result"]
                assert "verifiedInterpretation" not in stored_answer
                claim = w.owner.claim_continuation(
                    c,
                    w.cp,
                    worker_id="controlled-next-worker",
                    startup_record_digest="9" * 64,
                    verify_worker=lambda *_: None,
                )
                duplicate = w.owner.claim_continuation(
                    c,
                    w.cp,
                    worker_id="controlled-next-worker",
                    startup_record_digest="9" * 64,
                    verify_worker=lambda *_: None,
                )
                assert claim.newly_claimed is True and duplicate.newly_claimed is False
                assert (
                    c.execute(
                        "SELECT count(*) n FROM fixed_question.answers"
                    ).fetchone()["n"]
                    == 1
                )
                assert (
                    c.execute(
                        "SELECT count(*) n FROM skill_invocation.native_loop_records WHERE record_key=%s",
                        (w.cp.question_key + ":answer",),
                    ).fetchone()["n"]
                    == 1
                )
            allowed = False
            with (
                records.connect() as c,
                pytest.raises(AuthorityError, match="QUESTION_ANSWER_REVOKED"),
            ):
                owner.accept(make_call(c), e.conv, body)
            assert len(calls) == 1
    finally:
        if "w" in locals():
            w.skills.pool.close()
