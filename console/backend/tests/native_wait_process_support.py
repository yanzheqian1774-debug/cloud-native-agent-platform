"""Real isolated child processes; model decisions and Kubernetes remain controlled."""

import json
import multiprocessing
import os
import traceback
from types import SimpleNamespace as NS

from agent_console.execution_postgres import PostgresExecutionAuthorityRepository
from agent_operator.native_host_service_state import birth
from agent_runtime.native_loop import digest
from native_wait_document_support import compose
from test_prepared_native_pipeline import FixtureKubernetes


class FileKubernetes(FixtureKubernetes):
    def __init__(self, path):
        self.path = path

    @property
    def tasks(self):
        return json.loads(self.path.read_text()) if self.path.exists() else {}

    def create(self, claim, name):
        tasks = self.tasks
        assert name not in tasks
        tasks[name] = {
            "metadata": {"uid": "controlled-kubernetes-" + name},
            "status": {},
        }
        self.path.write_text(json.dumps(tasks))
        return tasks[name]

    def patch_status(self, command, name, status):
        tasks = self.tasks
        tasks[name]["status"] = status
        self.path.write_text(json.dumps(tasks))


def child(e, work, native, p, directory, number, predecessors=()):
    """Fork only test data, then construct fresh repository/pools in the child."""
    output = directory / f"child-{number}.json"
    db = native.pool.conninfo

    def execute():
        repository = None
        live = None
        try:
            repository = PostgresExecutionAuthorityRepository(
                db, migration_path=native.migration_path
            )
            live = compose(e, work, repository, p)
            live.worker.kubernetes = FileKubernetes(directory / "kubernetes.json")
            startup = live.startup(number, predecessors)
            startup["observation"]["pid"] = os.getpid()
            startup["observation"]["processBirth"] = birth(os.getpid())
            startup["digest"] = digest(startup["observation"])
            live.worker.startup_observation = NS(
                current=lambda: startup, observe_only_receipt=lambda _: None
            )
            states = []
            for _ in range(5):
                state = live.worker.run_once().state
                states.append(state)
                if state in {"DRAIN_FOR_INPUT", "IDLE"}:
                    break
                assert state == "SUCCEEDED", state
            output.write_text(
                json.dumps(dict(states=states, startup=startup, calls=live.calls))
            )
        except BaseException:
            output.write_text(json.dumps(dict(error=traceback.format_exc())))
            raise
        finally:
            if live:
                live.skills.invocation_repository.pool.close()
            if repository:
                repository.pool.close()

    process = multiprocessing.get_context("fork").Process(target=execute)
    process.start()
    process.join(60)
    if process.is_alive():
        process.terminate()
        process.join(5)
        raise AssertionError("controlled child did not exit")
    value = json.loads(output.read_text())
    assert process.exitcode == 0 and "error" not in value, value
    return process, value
