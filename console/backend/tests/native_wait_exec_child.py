"""Independent exec child with fresh owner pools and controlled decision ports.

This is not the production exec CLI or a real provider/Kubernetes acceptance.
"""

import json
import os
import traceback
from pathlib import Path
from threading import Event
from types import SimpleNamespace as NS

from agent_console.execution_domain import ScopeIdentity
from agent_console.execution_postgres import PostgresExecutionAuthorityRepository
from agent_console.readonly_continuation_policy import ReadonlyContinuationPolicy
from agent_console.readonly_continuation_worker import ContinuationWork
from agent_console.workbench_prepared_execution import candidate
from agent_operator.native_host_service_child import ready_and_watch
from agent_operator.native_host_service_state import (
    birth,
    read,
    write,
)
from agent_runtime.native_loop import digest
from native_wait_document_support import compose
from native_wait_exec_configuration import reconstruct
from native_wait_process_support import FileKubernetes


def main():
    import sys

    config = read(sys.argv[1])
    cfg = read(os.environ["NATIVE_HOST_STARTUP_CONFIGURATION"])
    directory = Path(config["directory"])
    output = Path(os.environ["NATIVE_WAIT_TEST_OUTPUT"])
    e, authority, authority_repo = reconstruct(config)
    repository = live = None
    invoke_errors = []
    code = 1
    try:
        repository = PostgresExecutionAuthorityRepository(
            config["database"], migration_path=Path(config["executionMigration"])
        )
        with repository.pool.connection() as c:
            p = candidate(
                c,
                ScopeIdentity(cfg["namespace"], cfg["securityDomain"]),
                cfg["authorizationResources"][0].removeprefix(
                    "governed-execution:prepared:"
                ),
            )
        work = ContinuationWork(
            repository,
            ReadonlyContinuationPolicy.model_validate(config["continuationPolicy"]),
            authority,
            owned_business=e.business_owner,
        )
        live = compose(e, work, repository, p, worker_id=cfg["workerId"])
        original_invoke = live.caller.invoke

        def observed_invoke(command):
            try:
                return original_invoke(command)
            except Exception:
                invoke_errors.append(traceback.format_exc())
                raise

        live.caller.invoke = observed_invoke
        live.worker.kubernetes = FileKubernetes(directory / (p.digest + "-tasks.json"))
        predecessors = []
        if cfg.get("predecessorDigest"):
            old = read(cfg["predecessorRecordPath"])
            predecessors = [
                old["digest"],
                *old["observation"]["predecessorDigests"],
            ]
        startup = live.startup(len(predecessors) + 1, predecessors)
        startup["observation"].update(pid=os.getpid(), processBirth=birth(os.getpid()))
        startup["digest"] = digest(startup["observation"])
        write(cfg["recordPath"], startup, exclusive=True)
        observation = NS(current=lambda: startup, observe_only_receipt=lambda _: None)
        live.worker.startup_observation = observation
        stop = Event()
        ready_and_watch(observation, stop)
        states = []
        while not stop.is_set():
            state = live.worker.run_once().state
            states.append(state)
            if state in {"DRAIN_FOR_INPUT", "IDLE"}:
                break
            assert state == "SUCCEEDED", state
        output.write_text(
            json.dumps(
                dict(
                    states=states,
                    calls=live.calls,
                    stopRequested=stop.is_set(),
                    pid=os.getpid(),
                )
            )
        )
        code = 0
    except BaseException:
        failure = traceback.format_exc()
        snapshots, roots = [], []
        if repository and live:
            with repository.pool.connection() as c:
                snapshots = c.execute(
                    "SELECT i.operation,p.state,p.record "
                    "FROM skill_invocation.projections p "
                    "JOIN skill_invocation.invocations i "
                    "USING(namespace,security_domain,skill_invocation_id) "
                    "WHERE i.workflow_run_id=%s",
                    (p.run_id,),
                ).fetchall()
                roots = c.execute(
                    "SELECT r.record_key,r.result "
                    "FROM skill_invocation.native_loop_records r "
                    "JOIN skill_invocation.invocations i "
                    "USING(namespace,security_domain,skill_invocation_id) "
                    "WHERE i.workflow_run_id=%s "
                    "AND r.record_key=r.skill_invocation_id",
                    (p.run_id,),
                ).fetchall()
        output.write_text(
            json.dumps(
                dict(
                    error=failure,
                    runnerErrors=live.runner_errors if live else [],
                    snapshots=snapshots,
                    roots=roots,
                    invokeErrors=invoke_errors if live else [],
                    calls=live.calls if live else [],
                    states=locals().get("states", []),
                ),
                default=str,
            )
        )
    finally:
        if live:
            live.skills.invocation_repository.pool.close()
        if repository:
            repository.pool.close()
        authority_repo.pool.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
