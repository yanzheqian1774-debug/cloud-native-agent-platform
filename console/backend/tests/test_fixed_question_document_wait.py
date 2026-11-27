"""Formal service source -> actual document7 NativeLoop WAIT, controlled model."""

# ruff: noqa: F401,F811 -- Original isolated owner fixtures.
from datetime import UTC, datetime
from types import SimpleNamespace as NS

import pytest
import test_fixed_chat_delivery_postgres as delivery_tests
from agent_console.bound_service_execution import BoundServiceExecutionBridge
from agent_console.execution_preparation_postgres import PreparedExecutionStore
from agent_console.fixed_work_service_continuation import ServiceCycleContinuation
from agent_console.native_typed_document_skill import (
    NativeTypedQuestionDocumentSkillExecutor as Executor,
)
from agent_console.native_wait_command_access import NativeWaitCommandAccess
from agent_console.native_wait_store import NativeWaitStore
from agent_console.readonly_continuation_worker import ContinuationWork
from agent_console.workbench_owner_authorization import AuthorizedOwnerAuthority
from fixed_question_document_c1_support import answer
from fixed_question_document_presentation_support import present
from fixed_question_document_support import automation, case, repository, services
from native_wait_document_support import compose


@pytest.mark.parametrize(
    "automation", [{"resources": "existing", "continuation": True}], indirect=True
)
def test_original_service_document7_produces_actual_typed_wait(
    automation, monkeypatch, tmp_path, request
):
    a = automation
    holder = {}
    original = ServiceCycleContinuation.continue_once

    def continued(owner, call, event):
        result = original(owner, call, event)
        holder["bridge"] = BoundServiceExecutionBridge(owner.registry)
        return result

    monkeypatch.setattr(ServiceCycleContinuation, "continue_once", continued)

    def drive(a, native, policy, _path, _count, *, exact_run_id, **_):
        with native.pool.connection() as c:
            p, _ = PreparedExecutionStore(c).read(
                a.e.scope.namespace, a.e.scope.security_domain, exact_run_id
            )

        def authority(c, command):
            assert command.principal_id == a.subject.principal_id
            return a.subject, AuthorizedOwnerAuthority(a.adapter, a.subject, c, 1, ())

        work = ContinuationWork(
            native, policy, authority, bound_service_execution=holder["bridge"]
        )

        def decide(library, ordinal):
            if ordinal > 0:
                assert library.confirmed_scope == library.binding.scope
                submission = next(
                    d["id"]
                    for d in library.documents.values()
                    if d["role"] == "SUBMISSION"
                )
                policy_id = next(
                    d["id"]
                    for d in library.documents.values()
                    if d["role"] == "POLICY" and d["scope"] == library.confirmed_scope
                )
                if ordinal in (1, 2):
                    return dict(
                        action="TOOL",
                        tool="read_document",
                        arguments={"id": submission if ordinal == 1 else policy_id},
                    )
                if ordinal == 3:
                    return dict(
                        action="TOOL",
                        tool="review_document",
                        arguments={"documentId": submission, "policyId": policy_id},
                    )
                if ordinal == 4:
                    return dict(action="TOOL", tool="build_report", arguments={})
                assert ordinal == 5
                return dict(
                    action="FINISH",
                    answer=library.invoke("build_report", {})["completionAnswer"],
                )
            assert ordinal == 0
            contract = library.question_contracts()[0]
            return {
                "action": "CLARIFY",
                "question": "是否按这份规范核对交接材料?",
                "questionContractId": contract["contractDigest"],
            }

        live = compose(
            NS(context=a.subject, business_owner=None),
            work,
            native,
            p,
            executor_type=Executor,
            typed_questions=True,
            decision_factory=decide,
            bound_service_execution=holder["bridge"],
        )
        request.addfinalizer(live.skills.close)
        live.runtime.generation = a.gen
        startup = live.startup(1)
        live.worker.startup_observation = NS(
            current=lambda: startup, observe_only_receipt=lambda _: None
        )
        for _ in range(4):
            outcome = live.worker.run_once()
            if outcome.state == "DRAIN_FOR_INPUT":
                break
            assert outcome.state == "SUCCEEDED", (outcome, live.runner_errors)
        assert outcome.state == "DRAIN_FOR_INPUT", (outcome, live.runner_errors)
        assert len(live.calls) == 1
        cp = live.sessions[-1].waiting
        assert cp.identity.principal_id == a.subject.principal_id
        with native.pool.connection() as c:
            row = c.execute(
                "SELECT result FROM skill_invocation.native_loop_records "
                "WHERE namespace=%s AND security_domain=%s "
                "AND skill_invocation_id=%s AND record_key LIKE %s",
                (
                    p.namespace,
                    p.security_domain,
                    cp.identity.skill_invocation_id,
                    "%:question",
                ),
            ).fetchone()
            assert row["result"]["answerContract"]["proposedCandidateId"]
        presented = present(a, live, native, work)
        holder["read_policy"] = presented.read_policy
        request.addfinalizer(presented.records.close_pool)
        assert presented.presentation.identity.checkpointDigest == cp.checkpoint_digest
        receipt = answer(a, live, native, work, presented)
        assert receipt["modelDispatched"] is False
        with native.pool.connection() as c:
            checkpoint = NativeWaitStore(c, cp.identity).checkpoint(
                cp.checkpoint_digest
            )
            candidate = dict(
                namespace=p.namespace,
                securityDomain=p.security_domain,
                principalId=a.subject.principal_id,
                preparationDigest=p.digest,
                runId=p.run_id,
            )
            assert NativeWaitCommandAccess(live.runtime, native, work).stopped(
                c,
                candidate,
                dict(
                    **candidate,
                    workerId=checkpoint.worker_id,
                    startupDigest=startup["digest"],
                    released=True,
                    pid=startup["observation"]["pid"],
                    processBirth=startup["observation"]["processBirth"],
                ),
                startup,
                dict(state="EXIT_CONFIRMED", stoppedAt=datetime.now(UTC).isoformat()),
                lambda *_: None,
            )["stopRecorded"]
        # Physical stop is an explicitly controlled port in this owner test.
        previous = startup
        startup = live.startup(
            2, (previous["digest"], *previous["observation"]["predecessorDigests"])
        )
        live.worker.startup_observation = NS(
            current=lambda: startup, observe_only_receipt=lambda _: None
        )
        assert live.worker.run_once().state == "SUCCEEDED", live.runner_errors
        for _ in range(4):
            final = live.worker.run_once()
            if final.state == "IDLE":
                break
            assert final.state == "SUCCEEDED", (final, live.runner_errors)
        assert final.state == "IDLE"
        assert len(live.calls) == len(set(live.calls)) == 6
        assert work.evaluate_terminal() == {"evaluated": 1, "blocked": 0}
        with native.pool.connection() as c:
            assert (
                c.execute(
                    "SELECT count(*) n FROM skill_invocation.native_wait_continuations"
                ).fetchone()["n"]
                == 1
            )
            assert (
                c.execute(
                    "SELECT state FROM skill_invocation.native_wait_heads"
                ).fetchone()["state"]
                == "COMPLETED"
            )
            artifacts = c.execute(
                "SELECT count(*) n FROM execution_authority.run_artifacts "
                "WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s",
                (p.namespace, p.security_domain, p.run_id),
            ).fetchone()["n"]
            outcome = c.execute(
                "SELECT record FROM product_outcome.outcomes WHERE namespace=%s "
                "AND security_domain=%s AND workflow_run_id=%s",
                (p.namespace, p.security_domain, p.run_id),
            ).fetchone()["record"]
        assert artifacts == 4
        holder["seen"] = True
        return {"artifacts": artifacts, "outcome": outcome}

    monkeypatch.setattr("pending_pipeline_support.drive", drive)
    delivery_tests.test_bound_committed_event_is_read_in_original_chat_without_human_model_lease(
        a,
        monkeypatch,
        tmp_path,
        delegated_answer=True,
        delegated_read_policy=lambda: holder["read_policy"],
    )
    assert holder.get("seen") is True
