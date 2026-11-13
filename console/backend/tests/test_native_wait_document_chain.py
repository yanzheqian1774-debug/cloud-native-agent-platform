"""Disposable real document owners; controlled model and Kubernetes are explicit."""

# ruff: noqa: F401,F811 -- Shared isolated owner fixture registration.
from unittest.mock import patch

import pytest
from agent_console.native_document_resource_bundle import resource_content
from agent_console.native_document_skill import NativeDurableDocumentSkillExecutor
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


def durable_source(e):
    def content(source, **kwargs):
        return resource_content(source, **kwargs, durable_wait=True)

    with (
        patch("owned_business_consumer_support.resource_content", content),
        patch(
            "owned_business_consumer_support.NativeRuleDocumentSkillExecutor",
            NativeDurableDocumentSkillExecutor,
        ),
    ):
        return prepare_source(e)


def durable_scope(e, result, policy):
    with patch(
        "owned_business_consumer_support.NativeRuleDocumentSkillExecutor",
        NativeDurableDocumentSkillExecutor,
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
                prepare_source=durable_source,
                configure_scope=durable_scope,
            )
        ],
        indirect=True,
    ),
]


def test_exact_durable_document_resources_reach_original_native_command(
    owned_created, tmp_path, request
):
    e = owned_created
    observed = []

    def inspect(work, native, receipt, ready):
        from agent_console.execution_domain import ScopeIdentity
        from agent_console.workbench_prepared_execution import candidate

        with native.pool.connection() as c:
            p = candidate(
                c,
                ScopeIdentity(
                    e.context.scope.tenant_id, e.context.scope.security_domain
                ),
                receipt["preparationDigest"],
            )
            expected = NativeDurableDocumentSkillExecutor.revision
            assert all(
                (v.executor_id, v.executor_revision, v.executor_digest)
                == (
                    expected.executor_id,
                    expected.executor_revision,
                    expected.configuration_digest,
                )
                for v in p.participants
            )
            observed.append(p.digest)
        from native_wait_document_support import compose

        live = compose(e, work, native, p)
        request.addfinalizer(live.skills.invocation_repository.pool.close)
        startup = live.startup(1)
        from types import SimpleNamespace

        live.worker.startup_observation = SimpleNamespace(
            current=lambda startup=startup: startup, observe_only_receipt=lambda _: None
        )
        for _ in range(4):
            result = live.worker.run_once()
            if result.state == "DRAIN_FOR_INPUT":
                break
            assert result.state == "SUCCEEDED", result
        assert result.state == "DRAIN_FOR_INPUT", (result, live.calls)
        assert len(live.calls) == 1

        from datetime import UTC, datetime

        from agent_console.native_wait_command_access import NativeWaitCommandAccess
        from agent_console.native_wait_store import NativeWaitStore

        for number in (1, 2):
            session = live.sessions[-1]
            receipt = session.waiting
            with native.pool.connection() as c, c.transaction():
                cp = NativeWaitStore(c, receipt.identity).checkpoint(
                    receipt.checkpoint_digest
                )
                access = NativeWaitCommandAccess(live.runtime, native, work)
                candidate = dict(
                    namespace=p.namespace,
                    securityDomain=p.security_domain,
                    principalId=e.context.principal_id,
                    preparationDigest=p.digest,
                    runId=p.run_id,
                )
                assert access.inspect(c, candidate)["state"] == "QUIESCING"
                process = dict(
                    **candidate,
                    workerId=cp.worker_id,
                    startupDigest=startup["digest"],
                    released=True,
                    pid=startup["observation"]["pid"],
                    processBirth=startup["observation"]["processBirth"],
                )
                exit_receipt = dict(
                    state="EXIT_CONFIRMED", stoppedAt=datetime.now(UTC).isoformat()
                )
                assert access.stopped(
                    c, candidate, process, startup, exit_receipt, lambda *_: None
                )["stopRecorded"]
                assert access.inspect(c, candidate)["state"] == "WAITING_FOR_USER"
                answer = dict(
                    kind="NATIVE_ANSWER",
                    answer=session.binding(c).scope.documentRules.scope,
                    conversationId=cp.identity.conversation_id,
                    principal=cp.identity.principal_id,
                    questionDigest=cp.question_digest,
                )
            from native_wait_answer_support import browser, link_created_problem

            body = {
                "invocationId": cp.identity.skill_invocation_id,
                "questionKey": cp.question_key,
                "questionDigest": cp.question_digest,
                "conversationId": cp.identity.conversation_id,
                "answer": answer["answer"],
            }
            with browser(e, work, native, p, live.runtime, tmp_path) as (client, path):
                link_created_problem(client, e, cp.identity.conversation_id)
                progress = client.get(path + "/native-progress")
                assert progress.status_code == 200, progress.text
                assert (
                    progress.json()["result"]["durableWaits"][0]["state"]
                    == "WAITING_FOR_USER"
                )
                for wrong in (
                    {"conversationId": "not-original"},
                    {"questionDigest": "b" * 64},
                ):
                    rejected = client.post(
                        path + "/native-answers",
                        headers=e.adoption_headers,
                        json={**body, **wrong},
                    )
                    assert rejected.status_code in {403, 404}, rejected.text
                before = len(live.calls)
                response = client.post(
                    path + "/native-answers", headers=e.adoption_headers, json=body
                )
                assert response.status_code == 200, response.text
                assert response.json()["result"] == {
                    "accepted": True,
                    "replayed": False,
                }
                response = client.post(
                    path + "/native-answers", headers=e.adoption_headers, json=body
                )
                assert response.status_code == 200, response.text
                assert response.json()["result"]["replayed"]
                assert len(live.calls) == before
            startup = live.startup(
                number + 1,
                (startup["digest"], *startup["observation"]["predecessorDigests"]),
            )
            live.worker.startup_observation = SimpleNamespace(
                current=lambda startup=startup: startup,
                observe_only_receipt=lambda _: None,
            )
            if number == 2:

                class ProcessExitBeforeSkillTerminal(BaseException):
                    pass

                # The root/head completion is already durable; interrupt only
                # the later Skill terminal write, as a process exit would do.
                with (
                    patch.object(
                        live.skills.invocation_repository,
                        "commit_terminal",
                        side_effect=ProcessExitBeforeSkillTerminal,
                    ),
                    pytest.raises(ProcessExitBeforeSkillTerminal),
                ):
                    live.worker.run_once()
                with native.pool.connection() as c:
                    assert (
                        c.execute(
                            "SELECT state FROM skill_invocation.native_wait_heads"
                        ).fetchone()["state"]
                        == "COMPLETED"
                    )
                completed_calls = list(live.calls)
                result = live.worker.run_once()
                assert live.calls == completed_calls
            else:
                result = live.worker.run_once()
            with native.pool.connection() as c:
                records = c.execute(
                    "SELECT record_key,result "
                    "FROM skill_invocation.native_loop_records "
                    "WHERE result IS NOT NULL ORDER BY record_key"
                ).fetchall()
            if result.state not in {"DRAIN_FOR_INPUT", "SUCCEEDED"}:
                import json

                print(json.dumps(records, ensure_ascii=False))
            assert result.state == (
                "DRAIN_FOR_INPUT" if number == 1 else "SUCCEEDED"
            ), (result, live.calls, records)
        assert len(live.calls) == 7
        assert len(set(live.calls)) == 7
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
                    "SELECT count(*) n FROM skill_invocation.native_wait_checkpoints"
                ).fetchone()["n"]
                == 2
            )
            assert (
                c.execute(
                    "SELECT count(*) n FROM skill_invocation.native_wait_continuations"
                ).fetchone()["n"]
                == 2
            )
            assert (
                c.execute(
                    "SELECT state FROM skill_invocation.native_wait_heads"
                ).fetchone()["state"]
                == "COMPLETED"
            )

    e.consumer_execution_observer = inspect
    exercise(e, tmp_path, request)
    assert len(observed) == 1


def test_physical_exit_and_late_answer_resume_the_original_document_job(
    owned_created, tmp_path, request
):
    import os
    import time
    from datetime import UTC, datetime, timedelta

    from agent_console.execution_domain import ScopeIdentity
    from agent_console.native_wait_command_access import NativeWaitCommandAccess
    from agent_console.native_wait_owner import NativeWaitOwner
    from agent_console.workbench_prepared_execution import candidate
    from native_wait_document_support import compose
    from native_wait_process_support import child

    e = owned_created
    e.wait_runtime_expiry = datetime.now(UTC) + timedelta(hours=1)
    delay = int(os.getenv("NATIVE_WAIT_TEST_HUMAN_DELAY_SECONDS", "181"))
    assert delay == 0 or delay > 180  # Zero is an explicit short wiring check only.

    def inspect(work, native, receipt, ready):
        with native.pool.connection() as c:
            p = candidate(
                c,
                ScopeIdentity(
                    e.context.scope.tenant_id, e.context.scope.security_domain
                ),
                receipt["preparationDigest"],
            )
        live = compose(e, work, native, p)
        request.addfinalizer(live.skills.invocation_repository.pool.close)
        access = NativeWaitCommandAccess(live.runtime, native, work)
        target = dict(
            namespace=p.namespace,
            securityDomain=p.security_domain,
            principalId=e.context.principal_id,
            preparationDigest=p.digest,
            runId=p.run_id,
        )
        predecessors = []
        all_calls = []
        directory = tmp_path / "actual-processes"
        directory.mkdir()
        for number in (1, 2, 3):
            process, result = child(e, work, native, p, directory, number, predecessors)
            all_calls.extend(result["calls"])
            startup = result["startup"]
            predecessors = [startup["digest"], *predecessors]
            assert process.exitcode == 0 and not process.is_alive()
            if number == 3:
                assert result["states"][-1] == "IDLE"
                break
            assert result["states"][-1] == "DRAIN_FOR_INPUT"
            with native.pool.connection() as c, c.transaction():
                cp, command, state = access._load(c, target)
                assert state == "QUIESCING"
                process_record = dict(
                    **target,
                    workerId=cp.worker_id,
                    startupDigest=startup["digest"],
                    released=True,
                    pid=process.pid,
                    processBirth=startup["observation"]["processBirth"],
                )
                exit_receipt = dict(
                    state="EXIT_CONFIRMED", stoppedAt=datetime.now(UTC).isoformat()
                )

                def verify_exit(*_, process=process, startup=startup):
                    assert process.exitcode == 0 and not process.is_alive()
                    assert process.pid == startup["observation"]["pid"]

                assert access.stopped(
                    c, target, process_record, startup, exit_receipt, verify_exit
                )["stopRecorded"]
                assert not access.inspect(c, target)["resumable"]
            if number == 1:
                started = time.monotonic()
                time.sleep(delay)
                assert time.monotonic() - started >= delay
                assert not process.is_alive()
            with native.pool.connection() as c, c.transaction():
                cp, command, _ = access._load(c, target)
                owner = NativeWaitOwner(
                    lambda c, cp, _, command=command: access._authorize(c, cp, command),
                    None,
                )
                binding = e.business_owner.work(
                    c, e.context, p.semantics.target.problem
                )
                answer = dict(
                    kind="NATIVE_ANSWER",
                    answer=binding.scope.documentRules.scope,
                    conversationId=cp.identity.conversation_id,
                    principal=cp.identity.principal_id,
                    questionDigest=cp.question_digest,
                )
                assert owner.accept_answer(c, cp, answer)["accepted"]
                assert owner.accept_answer(c, cp, answer)["replayed"]
                assert access.inspect(c, target)["resumable"]
        assert len(all_calls) == len(set(all_calls)) == 7
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

    e.consumer_execution_observer = inspect
    exercise(e, tmp_path, request)


def test_two_formal_preparations_are_discovered_without_preset_host_list(
    owned_created, tmp_path, request
):
    from types import SimpleNamespace as NS

    from agent_console.execution_domain import ScopeIdentity
    from agent_console.native_wait_command_access import NativeWaitCommandAccess
    from agent_console.workbench_prepared_execution import candidate
    from agent_operator.native_host_service_discovery import Discovery
    from native_wait_document_support import compose
    from native_wait_second_preparation import prepare_second

    e = owned_created

    def inspect(work, native, first, ready):
        with native.pool.connection() as c:
            p = candidate(
                c,
                ScopeIdentity(
                    e.context.scope.tenant_id, e.context.scope.security_domain
                ),
                first["preparationDigest"],
            )
        live = compose(e, work, native, p)
        request.addfinalizer(live.skills.invocation_repository.pool.close)
        access = NativeWaitCommandAccess(live.runtime, native, work)
        discovery = Discovery(
            NS(
                worker=NS(
                    repository=NS(work=work),
                    transport=NS(caller=NS(wait_access=access)),
                ),
                execution_repository=native,
            ),
            (p.namespace, p.security_domain, e.context.principal_id),
            "isolated-manager-database",
        )
        assert [v["preparationDigest"] for v in discovery.page()] == [p.digest]
        import json
        import time

        from native_wait_manager_support import managed

        manager = managed(e, work, native, discovery, tmp_path / "actual-manager")
        request.addfinalizer(manager.close)

        def drain_to_wait(count):
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                manager.tick()
                for process, output, _ in manager.spawned:
                    if process.poll() is not None:
                        assert process.returncode == 0, (
                            output.read_text()
                            if output.exists()
                            else "no child receipt"
                        )
                with native.pool.connection() as c:
                    rows = c.execute(
                        "SELECT state FROM skill_invocation.native_wait_heads"
                    ).fetchall()
                if (
                    len(rows) == count
                    and all(row["state"] == "WAITING_FOR_USER" for row in rows)
                    and not manager.children
                ):
                    break
                time.sleep(0.05)
            else:
                raise AssertionError((manager.last_error, rows, manager.children))
            assert len(manager.spawned) == count
            for _, output, _ in manager.spawned:
                assert json.loads(output.read_text())["states"][-1] == "DRAIN_FOR_INPUT"

        drain_to_wait(1)
        assert discovery.page() == []
        second = prepare_second(e)
        assert second["preparationDigest"] != p.digest
        found = discovery.page()
        assert {v["preparationDigest"] for v in found} == {second["preparationDigest"]}
        assert all(discovery.current(value) == value for value in found)
        drain_to_wait(2)
        assert discovery.page() == []
        # Both original questions remain pending, no repeated process/model start.
        manager.tick()
        assert len(manager.spawned) == 2 and not manager.children
        assert {cfg["authorizationResources"][0] for _, _, cfg in manager.spawned} == {
            "governed-execution:prepared:" + p.digest,
            "governed-execution:prepared:" + second["preparationDigest"],
        }

    e.consumer_execution_observer = inspect
    exercise(e, tmp_path, request)
