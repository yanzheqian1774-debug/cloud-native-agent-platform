"""Real local process/lock tests, with controlled startup records and no provider."""

import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from agent_operator.native_host_service import HostService
from agent_operator.native_host_service_state import (
    birth,
    lock,
    private_directory,
    read,
    worker_id,
    write,
)
from agent_operator.native_host_startup import digest

CHILD = """
import json,os,time
from pathlib import Path
from threading import Event
from agent_operator.native_host_service_child import ready_and_watch
from agent_operator.native_host_service_state import birth,write
from agent_operator.native_host_startup import digest
cfg=json.loads(Path(os.environ['NATIVE_HOST_STARTUP_CONFIGURATION']).read_text())
keys=('workerId','namespace','securityDomain','principalId','authorizationResources')
record={k:cfg[k] for k in keys}
record.update(pid=os.getpid(),processBirth=birth(os.getpid()),predecessorDigests=[])
if cfg.get('predecessorDigest'): record['predecessorDigests']=[cfg['predecessorDigest']]
value={'observation':record,'digest':digest(record)}
write(cfg['recordPath'],value,exclusive=True)
class Observation:
    def current(self): return value
stop=Event()
ready_and_watch(Observation(),stop)
stop.wait(10)
"""


def item(n="a"):
    return {
        "namespace": "ns",
        "securityDomain": "domain",
        "principalId": "human:a",
        "preparationDigest": n * 64,
        "runId": "run:" + n,
        "commandKey": n,
        "resource": "governed-execution:prepared:" + n * 64,
        "existingWorkers": [],
    }


@pytest.fixture
def service(tmp_path):
    directory = private_directory(tmp_path / "service")
    config = SimpleNamespace(
        directory=directory,
        environment={
            **os.environ,
            "PYTHONPATH": os.pathsep.join(
                (
                    str(Path(__file__).resolve().parents[1] / "src"),
                    os.environ.get("PYTHONPATH", ""),
                )
            ),
        },
        value={
            "maxHosts": 2,
            "maxRestarts": 3,
            "pollSeconds": 1,
            "readinessSeconds": 2,
            "shutdownSeconds": 2,
            "manifestPath": "/controlled/manifest",
            "manifestDigest": "a" * 64,
            "policyFiles": {},
        },
        verify=lambda: None,
    )
    candidates = []
    discovery = SimpleNamespace(
        fingerprint="db-a",
        current=lambda candidate: candidate if candidate in candidates else None,
        page=lambda: candidates[:],
    )
    spawned = []

    def spawn(_command, **kwargs):
        child = subprocess.Popen([sys.executable, "-c", CHILD], **kwargs)
        spawned.append(child)
        return child

    service = HostService(config, discovery, popen=spawn)
    service.candidates, service.spawned = candidates, spawned
    yield service
    service.close()
    for child in spawned:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=5)


def test_new_preparations_after_start_spawn_exact_hosts_once(service):
    service.tick()
    assert not service.children
    first, second = item(), item("b")
    service.candidates.append(first)
    service.tick()
    service.candidates.append(second)
    service.tick()
    service.tick()
    assert len(service.spawned) == len(service.children) == 2
    for candidate in (first, second):
        child = service.children[service.identity(candidate)]
        startup = read(child.status["configurationPath"])
        assert startup["authorizationResources"] == [candidate["resource"]]
        assert child.status["released"] is True
        assert read(child.status_path)["state"] == "RUNNING"
        with pytest.raises(BlockingIOError):
            lock(service.config.directory / (service.identity(candidate) + ".lock"))


def test_capacity_is_observed_queue_not_unbounded_spawn(service):
    service.candidates.extend([item(), item("b"), item("c")])
    service.tick()
    assert len(service.spawned) == 2
    projection = read(
        service.config.directory
        / ("view-" + digest(["ns", "domain", "human:a", "c" * 64]) + ".json")
    )
    assert projection["state"] == "QUEUED"
    assert projection["reasonCode"] == "WAITING_CAPACITY"


def test_revoked_candidate_stops_polling_and_confirmed_exit_frees_capacity(service):
    candidate = item()
    service.candidates.append(candidate)
    service.tick()
    child = next(iter(service.children.values()))
    service.candidates.clear()
    service.poll_children()
    child.process.wait(timeout=5)
    service.poll_children()
    assert not service.children
    assert read(child.status_path)["state"] == "EXIT_CONFIRMED"


def test_parent_pipe_eof_leaves_child_lock_until_exit(service):
    candidate = item()
    service.candidates.append(candidate)
    service.tick()
    child = next(iter(service.children.values()))
    # Simulate loss of parent's worker FD first: child still owns the same flock.
    os.close(child.lock_fd)
    child.lock_fd = os.open(os.devnull, os.O_RDONLY)
    with pytest.raises(BlockingIOError):
        lock(service.config.directory / (service.identity(candidate) + ".lock"))
    os.close(child.control_fd)
    child.control_fd = -1
    child.process.wait(timeout=5)
    service.poll_children()
    fd = lock(service.config.directory / (service.identity(candidate) + ".lock"))
    os.close(fd)


def test_restart_retains_exact_worker_and_predecessor(service):
    candidate = item()
    service.candidates.append(candidate)
    service.tick()
    old = next(iter(service.children.values()))
    os.close(old.control_fd)
    old.control_fd = -1
    old.process.wait(timeout=5)
    service.poll_children()
    service.clock = lambda: time.time() + 20
    candidate["existingWorkers"] = [service.identity(candidate)]
    service.tick()
    new = next(iter(service.children.values()))
    assert new.status["workerId"] == old.status["workerId"]
    cfg = read(new.status["configurationPath"])
    assert cfg["predecessorRecordPath"] == old.status["recordPath"]
    assert cfg["predecessorDigest"] == old.status["startupDigest"]
    assert cfg["authorizationResources"] == [candidate["resource"]]


def test_unconfirmed_live_pid_and_missing_bound_record_never_spawn(service):
    candidate = item()
    candidate["existingWorkers"] = [service.identity(candidate)]
    service.candidates.append(candidate)
    with pytest.raises(ValueError, match="BOUND_WORKER_RECORD_MISSING"):
        service.launch(candidate)
    path = service.config.directory / (service.identity(candidate) + ".json")
    write(
        path,
        {
            "workerId": service.identity(candidate),
            "boot": 1,
            "pid": os.getpid(),
            "processBirth": "wrong birth",
            "released": True,
        },
    )
    with pytest.raises(ValueError, match="EXIT_UNCONFIRMED"):
        service.launch(candidate)
    assert not service.spawned


def test_foreign_worker_is_not_taken_over(service):
    candidate = item()
    candidate["existingWorkers"] = ["manual-old-worker"]
    service.candidates.append(candidate)
    with pytest.raises(ValueError, match="FOREIGN_WORKER"):
        service.launch(candidate)
    assert not service.spawned


def test_readiness_timeout_has_no_release_and_reaps_child(service):
    service.config.value["readinessSeconds"] = 1
    children = []

    def stalled(_cmd, **kwargs):
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(20)"], **kwargs
        )
        children.append(child)
        return child

    service.popen = stalled
    candidate = item()
    service.candidates.append(candidate)
    with pytest.raises(ValueError, match="READINESS_TIMEOUT"):
        service.launch(candidate)
    state = read(service.config.directory / (service.identity(candidate) + ".json"))
    assert state["released"] is False
    assert state["state"] == "EXIT_CONFIRMED"
    assert children[0].poll() is not None
    service.poll_children()
    assert not service.children


def test_private_storage_identity_and_exclusive_records(tmp_path):
    root = private_directory(tmp_path / "p")
    path = root / "immutable.json"
    write(path, {"x": 1}, exclusive=True)
    with pytest.raises(FileExistsError):
        write(path, {"x": 2}, exclusive=True)
    assert read(path) == {"x": 1}
    assert worker_id("db", "a", "b", "c", "d") != worker_id("other", "a", "b", "c", "d")
    link = root / "link"
    link.symlink_to(path)
    with pytest.raises(OSError):
        lock(link)
    assert birth(os.getpid())
    root.chmod(0o755)
    with pytest.raises(ValueError, match="UNSAFE"):
        private_directory(root)


def test_global_service_lock_survives_parent_fd_loss_until_child_exit(service):
    service_fd = lock(service.config.directory / "global.lock")
    service.service_lock_fd = service_fd
    service.candidates.append(item())
    service.tick()
    child = next(iter(service.children.values()))
    os.close(service_fd)
    service.service_lock_fd = None
    with pytest.raises(BlockingIOError):
        lock(service.config.directory / "global.lock")
    os.close(child.control_fd)
    child.control_fd = -1
    child.process.wait(timeout=5)
    service.poll_children()
    fd = lock(service.config.directory / "global.lock")
    os.close(fd)


def test_read_failure_stops_child_without_marking_execution_failed(service):
    service.candidates.append(item())
    service.tick()
    child = next(iter(service.children.values()))

    def unavailable(_):
        raise ValueError("controlled storage unavailable")

    service.discovery.current = unavailable
    service.poll_children()
    projection = read(
        service.config.directory
        / ("view-" + digest(["ns", "domain", "human:a", "a" * 64]) + ".json")
    )
    assert projection["state"] == "UNKNOWN"
    assert projection["reasonCode"] == "OBSERVATION_UNAVAILABLE"
    child.process.wait(timeout=5)


def test_predecessor_missing_or_chain_limit_is_not_fresh_start(service):
    previous = {"workerId": "exact", "pid": None, "released": True}
    with pytest.raises(ValueError, match="STARTUP_RECORD_MISSING"):
        service._predecessor(previous, "exact")
    record = {"workerId": "exact", "predecessorDigests": [str(n) for n in range(32)]}
    path = service.config.directory / "prior.json"
    write(path, {"observation": record, "digest": digest(record)})
    previous["recordPath"] = str(path)
    with pytest.raises(ValueError, match="PREDECESSOR_LIMIT"):
        service._predecessor(previous, "exact")


def test_readiness_binding_mismatch_cannot_release_go(service):
    children = []
    corrupt = CHILD.replace(
        "value={'observation':record",
        "record['principalId']='other'\nvalue={'observation':record",
    )

    def spawn(_cmd, **kwargs):
        child = subprocess.Popen([sys.executable, "-c", corrupt], **kwargs)
        children.append(child)
        return child

    service.popen = spawn
    candidate = item()
    service.candidates.append(candidate)
    with pytest.raises(ValueError, match="READINESS_MISMATCH"):
        service.launch(candidate)
    assert children[0].poll() is not None
    saved = read(service.config.directory / (service.identity(candidate) + ".json"))
    assert saved["released"] is False


def test_stopping_child_never_becomes_ready_again(service):
    candidate = item()
    service.candidates.append(candidate)
    service.tick()
    child = next(iter(service.children.values()))
    service.candidates.clear()
    service.poll_children()
    service.candidates.append(candidate)
    # Inspect the already stopping process before its exit gets reaped.
    original_poll = child.process.poll
    child.process.poll = lambda: None
    try:
        service.poll_children()
        view = read(
            service.config.directory
            / ("view-" + digest(["ns", "domain", "human:a", "a" * 64]) + ".json")
        )
        assert view["state"] == "STOPPING"
    finally:
        child.process.poll = original_poll


def test_unconfirmed_post_release_child_still_occupies_capacity(service, monkeypatch):
    candidate = item()
    service.candidates.append(candidate)
    # Make only the post-release presentation write fail. The child may now be
    # processing; cleanup must not forget it or free its capacity prematurely.
    original_view = service.view
    real_wait = []

    def view(item, state, reason=None):
        if state == "READY":
            raise OSError("controlled local status failure")
        original_view(item, state, reason)

    service.view = view
    original_spawn = service.popen

    def spawn(*args, **kwargs):
        child = original_spawn(*args, **kwargs)
        real_wait.append(child.wait)
        monkeypatch.setattr(child, "poll", lambda: None)
        monkeypatch.setattr(
            child,
            "wait",
            lambda timeout=None: (_ for _ in ()).throw(
                subprocess.TimeoutExpired("controlled", timeout)
            ),
        )
        return child

    service.popen = spawn
    with pytest.raises(OSError):
        service.launch(candidate)
    assert len(service.children) == 1
    child = next(iter(service.children.values()))
    assert child.status["state"] == "EXIT_UNCONFIRMED"
    assert child.control_fd == -1
    monkeypatch.undo()
    real_wait[0](timeout=5)
    service.poll_children()
    assert not service.children


def test_shutdown_registry_requires_real_child_exit(service):
    service.candidates.append(item())
    service.tick()
    service.close()
    registry = read(service.config.directory / "service-status.json")
    assert registry["state"] == "DRAINED"
    assert registry["children"] == []


def test_cleanup_status_failure_cannot_forget_unconfirmed_child(service, monkeypatch):
    service.config.value["maxHosts"] = 1
    service.candidates.extend([item(), item("b")])
    original_view, original_status = service.view, service._status

    def view(candidate, state, reason=None):
        if state == "READY":
            raise OSError("controlled post-G view failure")
        original_view(candidate, state, reason)

    def status(path, record, **changes):
        if changes.get("state") == "EXIT_UNCONFIRMED":
            raise OSError("controlled cleanup status failure")
        return original_status(path, record, **changes)

    service.view, service._status = view, status
    original_spawn = service.popen

    def spawn(*args, **kwargs):
        child = original_spawn(*args, **kwargs)
        monkeypatch.setattr(child, "poll", lambda: None)
        monkeypatch.setattr(
            child,
            "wait",
            lambda timeout=None: (_ for _ in ()).throw(
                subprocess.TimeoutExpired("controlled", timeout)
            ),
        )
        return child

    service.popen = spawn
    service.tick()
    assert len(service.spawned) == len(service.children) == 1
    retained = next(iter(service.children.values()))
    assert retained.lock_fd >= 0
    queue = read(
        service.config.directory
        / ("view-" + digest(["ns", "domain", "human:a", "b" * 64]) + ".json")
    )
    assert queue["state"] == "QUEUED"
    monkeypatch.undo()
    service._status = original_status
    service.view = original_view
    retained.process.wait(timeout=5)
    service.poll_children()


def test_machine_lock_path_is_canonical_and_not_environment_selected(monkeypatch):
    from agent_operator import native_host_service_state as state

    seen = []
    monkeypatch.setattr(state, "private_directory", lambda p: seen.append(p) or p)
    monkeypatch.setenv("TMPDIR", "/unrelated/temp")
    first = state.machine_lock_directory()
    monkeypatch.setenv("TMPDIR", "/another/temp")
    assert state.machine_lock_directory() == first
    assert first.parent == Path("/tmp").resolve()
    assert first.name == "native-exact-host-service-" + str(os.getuid())
    assert all(p.resolve() == p for p in seen)
