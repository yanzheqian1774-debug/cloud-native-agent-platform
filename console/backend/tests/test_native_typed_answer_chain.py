"""Same actual prepared Native question and saved C1 answer; provider is controlled."""

# ruff: noqa: F401,F811,RUF001 -- Actual isolated owner fixtures.
from types import SimpleNamespace as NS
from unittest.mock import patch

import pytest
from agent_console.native_document_resource_bundle import resource_content
from agent_console.native_typed_document_skill import (
    NativeTypedQuestionDocumentSkillExecutor as Executor,
)
from agent_console.workbench_bff import PREFIX
from owned_business_consumer_support import configure_scope, prepare_source
from test_conversation_experience_admission import pytestmark as pgmark
from test_owned_business_consumer_chain import (
    adopted,
    cleanup_consumer_resources,
    env,
    ordinary,
    owned_created,
    owned_ready,
    routed,
    setup,
)
from test_owned_business_consumer_chain import (
    test_same_owned_problem_confirms_prepares_and_worker_reads as exercise,
)


@pytest.fixture(autouse=True)
def actual_root_budget(monkeypatch):
    """Replace only the upstream empty fixture before any allowance/reservation."""
    from pathlib import Path

    import test_owned_conversation_bff as fixture
    from agent_console.conversation_experience_admission import LEDGER
    from agent_console.draft_provider_budget_postgres import PostgresProviderCallBudget

    def configure(e, path, **kwargs):
        import json

        from agent_console.conversation_experience_admission import (
            ConversationExperienceAdmission,
        )

        assert not kwargs
        invocation = e.draft.begin(
            e.reviewer, key="experience", content="synthetic review"
        ).invocation
        e.admission.configuration = {
            **e.limits,
            "ledger_id": LEDGER,
            "calls": 20,
            "cost_microusd": 1_000_000,
            "profile_revision_id": invocation.profile_revision_id,
        }
        document = {
            "schemaVersion": "f3-conversation-experience.v1",
            "tenantId": "s5-323-demo",
            "securityDomain": "isolated-real-demo",
            "subjectId": e.reviewer.principal_id,
            "accountId": "local-account:reviewer324",
            "authorizationDigest": "a" * 64,
            "configuration": e.admission.configuration,
            "conversations": {"approved-conversation": "SYNTHETIC_DOCUMENT_REVIEW"},
            "externalWrites": False,
        }
        path = path / "experience.json"
        path.write_text(json.dumps(document))
        path.chmod(0o600)
        e.admission.experience = ConversationExperienceAdmission(
            path, e.admission.configuration
        )
        budget = PostgresProviderCallBudget(
            e.repo.pool.conninfo,
            migration_path=Path(__file__).parents[1]
            / "migrations/0024_draft_provider_budget.sql",
            profile=e.draft.profile,
            ledger_id=LEDGER,
            call_cap=20,
            total_cost_cap_microusd=1_000_000,
            input_price_microusd_per_million_tokens=0,
            output_price_microusd_per_million_tokens=0,
        )
        try:
            budget.migrate_and_configure()
        finally:
            budget.close()
        return invocation, None, path, document

    monkeypatch.setattr(fixture, "configure", configure)


def typed_source(e):
    def content(source, **kwargs):
        return resource_content(
            source, **kwargs, durable_wait=True, typed_questions=True
        )

    with (
        patch("owned_business_consumer_support.resource_content", content),
        patch(
            "owned_business_consumer_support.NativeRuleDocumentSkillExecutor", Executor
        ),
    ):
        return prepare_source(e)


def typed_scope(e, result, policy):
    with patch(
        "owned_business_consumer_support.NativeRuleDocumentSkillExecutor", Executor
    ):
        return configure_scope(e, result, policy)


pytestmark = [
    pgmark,
    pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True),
    pytest.mark.parametrize(
        "owned_ready",
        [
            dict(
                mode="SOURCE_SUCCESSOR",
                prepare_source=typed_source,
                configure_scope=typed_scope,
            )
        ],
        indirect=True,
    ),
]


@pytest.mark.parametrize("meaning", ["CONFIRM", "REJECT", "UNCLEAR"])
def test_saved_typed_c1_answer_reaches_same_native_question_once(
    owned_created, tmp_path, request, meaning
):
    e = owned_created
    observed = []

    def inspect(work, native, receipt, ready):
        from agent_console.execution_domain import ScopeIdentity
        from agent_console.workbench_prepared_execution import candidate
        from native_typed_answer_support import typed_client
        from native_wait_answer_support import browser, link_created_problem
        from native_wait_document_support import compose

        with native.pool.connection() as c:
            p = candidate(
                c,
                ScopeIdentity(
                    e.context.scope.tenant_id, e.context.scope.security_domain
                ),
                receipt["preparationDigest"],
            )

        continued = []

        def decision(library, ordinal):
            if ordinal >= 1:
                expected = library.binding.scope if meaning == "CONFIRM" else None
                assert library.confirmed_scope == expected
                if ordinal == 1:
                    continued.append((ordinal, library.confirmed_scope))
                if meaning != "CONFIRM":
                    return {"action": "CLARIFY", "question": "请补充检查对象的负责人。"}
                submission = next(
                    d["id"]
                    for d in library.documents.values()
                    if d["role"] == "SUBMISSION"
                )
                policy = next(
                    d["id"]
                    for d in library.documents.values()
                    if d["role"] == "POLICY" and d["scope"] == expected
                )
                if ordinal in (1, 2):
                    return {
                        "action": "TOOL",
                        "tool": "read_document",
                        "arguments": {"id": submission if ordinal == 1 else policy},
                    }
                if ordinal == 3:
                    return {
                        "action": "TOOL",
                        "tool": "review_document",
                        "arguments": {"documentId": submission, "policyId": policy},
                    }
                if ordinal == 4:
                    return {"action": "TOOL", "tool": "build_report", "arguments": {}}
                assert ordinal == 5
                return {
                    "action": "FINISH",
                    "answer": library.invoke("build_report", {})["completionAnswer"],
                }
            assert ordinal == 0
            contracts = library.question_contracts()
            contract = next(
                item
                for item in contracts
                if next(
                    c["label"]
                    for c in item["candidates"]
                    if c["id"] == item["proposedCandidateId"]
                )
                == library.binding.scope
            )
            return {
                "action": "CLARIFY",
                "question": "是否仅按所提供的规范核对这份合成材料？",
                "questionContractId": contract["contractDigest"],
            }

        live = compose(
            e,
            work,
            native,
            p,
            executor_type=Executor,
            typed_questions=True,
            decision_factory=decision,
        )
        request.addfinalizer(live.skills.invocation_repository.pool.close)
        startup = live.startup(1)
        live.worker.startup_observation = NS(
            current=lambda: startup, observe_only_receipt=lambda _: None
        )
        for _ in range(4):
            result = live.worker.run_once()
            if result.state == "DRAIN_FOR_INPUT":
                break
            assert result.state == "SUCCEEDED", result
        assert result.state == "DRAIN_FOR_INPUT", result
        assert len(live.calls) == 1
        with browser(
            e,
            work,
            native,
            p,
            live.runtime,
            tmp_path,
            executor_type=Executor,
            typed_questions=True,
        ) as (read_client, path):
            link_created_problem(read_client, e, e.conv)
            progress = read_client.get(path + "/native-progress")
            assert progress.status_code == 200, progress.text
            question = next(
                q for q in progress.json()["result"]["questions"] if q["answer"] is None
            )
        contract = question["answerContract"]
        assert {c["label"] for c in contract["candidates"]} == {
            p.business_semantics.scope
        }
        e.typed_meaning = {
            "decision": meaning,
            "candidateId": contract["proposedCandidateId"]
            if meaning == "CONFIRM"
            else None,
            "questionContractDigest": contract["contractDigest"],
        }
        with typed_client(e, p, question, tmp_path) as (
            client,
            headers,
            _context,
            service,
            calls,
            _authorizer,
        ):
            head = client.get(PREFIX + f"/conversations/{e.conv}/head").json()[
                "result"
            ]["conversation"]
            text = {
                "CONFIRM": "对，只核对这份合成材料，不执行上线或回退。",
                "REJECT": "不，先不要按这个范围检查。",
                "UNCLEAR": "我还不确定应该用哪个范围。",
            }[meaning]
            saved = client.post(
                PREFIX + f"/conversations/{e.conv}/messages",
                headers=headers,
                json={
                    "content": text,
                    "expectedVersion": head["version"],
                    "idempotencyKey": "typed-short-answer",
                },
            )
            assert saved.status_code == 200, saved.text
            message = saved.json()["result"]["identity"]
            response = client.post(
                PREFIX + "/draft-assistance/invocations",
                headers=headers,
                json={
                    "content": text,
                    "idempotencyKey": "typed-model-once",
                    "conversationId": e.conv,
                    "conversationMessageId": message,
                    "conversationRouting": True,
                },
            )
            assert response.status_code in (200, 201), (
                response.text,
                getattr(e, "typed_budget_error", None),
            )
            result = response.json()["result"]
            assert result["state"] == "SUCCEEDED", result
            assert result["conversationDelivery"]["state"] == "SAVED", result
            assert len(calls) == 1
            payload = {
                k: question[k]
                for k in ("invocationId", "questionKey", "questionDigest")
            }
            payload.update(
                conversationId=e.conv,
                answer=text,
                interpretationReference={
                    "messageId": message,
                    "requestKey": "typed-model-once",
                },
            )
            # An invocation's settled snapshot cannot substitute for the
            # authoritative settlement reader. No answer is written on denial.
            with browser(
                e,
                work,
                native,
                p,
                live.runtime,
                tmp_path,
                executor_type=Executor,
                typed_questions=True,
                typed_settlement_reader=lambda *_: {
                    "status": "PENDING",
                    "reservation_retained": True,
                },
            ) as (unsettled_client, path):
                denied = unsettled_client.post(
                    path + "/native-answers", headers=e.adoption_headers, json=payload
                )
                assert denied.status_code in (403, 404, 409), denied.text
                pending = unsettled_client.get(path + "/native-progress")
                assert (
                    next(
                        q
                        for q in pending.json()["result"]["questions"]
                        if q["questionKey"] == question["questionKey"]
                    )["answer"]
                    is None
                )

            with browser(
                e,
                work,
                native,
                p,
                live.runtime,
                tmp_path,
                executor_type=Executor,
                typed_questions=True,
                typed_settlement_reader=service.budget.read_invocation_settlement,
            ) as (answer_client, path):
                for invalid in (
                    {
                        **payload,
                        "interpretationReference": {
                            "messageId": "foreign-message",
                            "requestKey": "typed-model-once",
                        },
                    },
                    {
                        **payload,
                        "interpretationReference": {
                            "messageId": message,
                            "requestKey": "foreign-request",
                        },
                    },
                    {**payload, "questionDigest": "f" * 64},
                    {
                        **payload,
                        "interpretationReference": {
                            "messageId": message,
                            "requestKey": "typed-model-once",
                            "candidateId": "other-readable-scope",
                        },
                    },
                ):
                    denied = answer_client.post(
                        path + "/native-answers",
                        headers=e.adoption_headers,
                        json=invalid,
                    )
                    assert denied.status_code in (400, 403, 404, 409, 422), denied.text
                assert len(calls) == 1
                accepted = answer_client.post(
                    path + "/native-answers", headers=e.adoption_headers, json=payload
                )
                assert accepted.status_code == 200, accepted.text
                assert accepted.json()["result"]["accepted"] is True
                replay = answer_client.post(
                    path + "/native-answers", headers=e.adoption_headers, json=payload
                )
                assert replay.status_code == 200, replay.text
                assert replay.json()["result"]["replayed"] is True
                refreshed = answer_client.get(path + "/native-progress")
                assert refreshed.status_code == 200, refreshed.text
                assert (
                    next(
                        q
                        for q in refreshed.json()["result"]["questions"]
                        if q["questionKey"] == question["questionKey"]
                    )["answer"]
                    == text
                )
                assert len(calls) == 1
            from datetime import UTC, datetime

            from agent_console.native_wait_command_access import NativeWaitCommandAccess
            from agent_console.native_wait_store import NativeWaitStore

            wait = live.sessions[-1].waiting
            with native.pool.connection() as c, c.transaction():
                cp = NativeWaitStore(c, wait.identity).checkpoint(
                    wait.checkpoint_digest
                )
                access = NativeWaitCommandAccess(live.runtime, native, work)
                candidate_scope = dict(
                    namespace=p.namespace,
                    securityDomain=p.security_domain,
                    principalId=e.context.principal_id,
                    preparationDigest=p.digest,
                    runId=p.run_id,
                )
                assert access.stopped(
                    c,
                    candidate_scope,
                    dict(
                        **candidate_scope,
                        workerId=cp.worker_id,
                        startupDigest=startup["digest"],
                        released=True,
                        pid=startup["observation"]["pid"],
                        processBirth=startup["observation"]["processBirth"],
                    ),
                    startup,
                    dict(
                        state="EXIT_CONFIRMED", stoppedAt=datetime.now(UTC).isoformat()
                    ),
                    lambda *_: None,
                )["stopRecorded"]
            previous = startup
            startup = live.startup(
                2, (previous["digest"], *previous["observation"]["predecessorDigests"])
            )
            live.worker.startup_observation = NS(
                current=lambda: startup, observe_only_receipt=lambda _: None
            )
            resume = live.worker.transport.resume_wait
            resume_errors = []

            def observed_resume(command):
                try:
                    return resume(command)
                except Exception as exc:
                    import traceback

                    resume_errors.append(
                        (type(exc).__name__, str(exc), traceback.format_exc())
                    )
                    raise

            live.worker.transport.resume_wait = observed_resume
            continued_result = live.worker.run_once()
            expected_state = "SUCCEEDED" if meaning == "CONFIRM" else "DRAIN_FOR_INPUT"
            assert continued_result.state == expected_state, (
                continued_result,
                resume_errors,
            )
            assert len(continued) == 1
            assert len(calls) == 1
            if meaning == "CONFIRM":
                assert len(live.calls) == len(set(live.calls)) == 6
                for _ in range(4):
                    final = live.worker.run_once()
                    if final.state == "IDLE":
                        break
                    assert final.state == "SUCCEEDED", final
                assert final.state == "IDLE"
                with native.pool.connection() as c:
                    assert (
                        c.execute(
                            "SELECT count(*) n FROM execution_authority.run_artifacts"
                        ).fetchone()["n"]
                        == 4
                    )
                    assert (
                        c.execute(
                            "SELECT count(*) n FROM skill_invocation.invocations"
                        ).fetchone()["n"]
                        == 4
                    )
                    assert (
                        c.execute(
                            "SELECT state FROM skill_invocation.native_wait_heads"
                        ).fetchone()["state"]
                        == "COMPLETED"
                    )
                    assert (
                        c.execute(
                            "SELECT count(*) n FROM "
                            "skill_invocation.native_wait_continuations"
                        ).fetchone()["n"]
                        == 1
                    )
            else:
                assert len(live.calls) == 2
                assert live.sessions[-1].waiting.identity == wait.identity
            observed.append(question["questionDigest"])

    e.consumer_execution_observer = inspect
    exercise(e, tmp_path, request)
    assert len(observed) == 1
