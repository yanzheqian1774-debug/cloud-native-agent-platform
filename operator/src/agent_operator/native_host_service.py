"""Opt-in single-machine lifecycle service for unchanged exact Native hosts.

This process never calls run_once, creates dispatch commands, or grants authority.
"""

import json
import logging
import os
import select
import signal
import subprocess
import sys
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Event

from .native_host_service_config import Configuration
from .native_host_service_discovery import Discovery
from .native_host_service_state import (
    birth,
    lock,
    machine_lock_directory,
    read,
    worker_id,
    write,
)
from .native_host_startup import digest


@dataclass
class Child:
    process: object
    lock_fd: int
    control_fd: int
    status_path: Path
    status: dict
    candidate: dict


class HostService:
    def __init__(
        self,
        config,
        discovery,
        *,
        popen=subprocess.Popen,
        clock=time.time,
        service_lock_fd=None,
    ):
        self.config, self.discovery = config, discovery
        self.popen, self.clock = popen, clock
        self.children = {}
        self.last_error = None
        self.service_lock_fd = service_lock_fd
        if hasattr(discovery, "observe_stopped"):
            discovery.observe_stopped = self.recover_wait_exit

    def identity(self, item):
        return worker_id(
            self.discovery.fingerprint,
            item["namespace"],
            item["securityDomain"],
            item["principalId"],
            item["preparationDigest"],
        )

    def _status(self, path, record, **changes):
        value = {**record, **changes, "observedAt": self.clock()}
        write(path, value)
        return value

    def view(self, item, state, reason=None):
        identity = [
            item["namespace"],
            item["securityDomain"],
            item["principalId"],
            item["preparationDigest"],
        ]
        write(
            self.config.directory / ("view-" + digest(identity) + ".json"),
            {
                "schema": "native-exact-host-view.v1",
                "identity": identity,
                "runId": item["runId"],
                "observedAt": self.clock(),
                "validForSeconds": max(30, 3 * self.config.value["pollSeconds"]),
                "state": state,
                "reasonCode": reason,
            },
        )

    def _predecessor(self, previous, identity):
        if not previous:
            return {}
        if previous.get("workerId") != identity:
            raise ValueError("HOST_SERVICE_STORED_IDENTITY_MISMATCH")
        pid = previous.get("pid")
        if pid and birth(pid) is not None:
            # Even a reused PID must not be signalled/replaced based on stale state.
            raise ValueError("HOST_SERVICE_EXIT_UNCONFIRMED")
        path = previous.get("recordPath")
        if path and Path(path).exists():
            record = read(path)
            observation = record["observation"]
            if (
                record["digest"] != digest(observation)
                or observation["workerId"] != identity
            ):
                raise ValueError("HOST_SERVICE_PREDECESSOR_INVALID")
            if len(observation.get("predecessorDigests", [])) >= 32:
                raise ValueError("HOST_SERVICE_PREDECESSOR_LIMIT")
            return {
                "predecessorRecordPath": path,
                "predecessorDigest": record["digest"],
            }
        if previous.get("released"):
            raise ValueError("HOST_SERVICE_STARTUP_RECORD_MISSING")
        return {}

    def launch(self, candidate):
        identity = self.identity(candidate)
        if (
            identity in self.children
            or len(self.children) >= self.config.value["maxHosts"]
        ):
            return False
        if any(w != identity for w in candidate["existingWorkers"]):
            raise ValueError("HOST_SERVICE_FOREIGN_WORKER_BOUND")
        directory = self.config.directory
        state_path = directory / (identity + ".json")
        fd = lock(directory / (identity + ".lock"))
        ready_r = ready_w = control_r = control_w = -1
        child = None
        state = None
        try:
            previous = read(state_path) if state_path.exists() else None
            if previous and self.clock() < previous.get("retryAfter", 0):
                return False
            if candidate["existingWorkers"] and previous is None:
                raise ValueError("HOST_SERVICE_BOUND_WORKER_RECORD_MISSING")
            boot = previous["boot"] + 1 if previous else 1
            if boot > self.config.value["maxRestarts"] + 1:
                raise ValueError("HOST_SERVICE_RESTART_LIMIT")
            predecessor = self._predecessor(previous, identity)
            self.config.verify()
            # Revalidate immediately before spawning. Exact child owner checks again.
            current = self.discovery.current(candidate)
            if current is None or current != candidate:
                raise ValueError("HOST_SERVICE_CANDIDATE_CHANGED")
            startup_path = directory / f"{identity}-boot-{boot}.json"
            record_path = directory / f"{identity}-startup-{boot}.json"
            cfg = self.config.value
            startup = {
                "workerId": identity,
                "namespace": candidate["namespace"],
                "securityDomain": candidate["securityDomain"],
                "principalId": candidate["principalId"],
                "manifestPath": cfg["manifestPath"],
                "manifestDigest": cfg["manifestDigest"],
                "recordPath": str(record_path),
                "policyFiles": cfg["policyFiles"],
                "authorizationResources": [candidate["resource"]],
                **predecessor,
            }
            write(startup_path, startup, exclusive=True)
            state = {
                "schema": "native-exact-host-process.v1",
                "workerId": identity,
                "namespace": candidate["namespace"],
                "securityDomain": candidate["securityDomain"],
                "principalId": candidate["principalId"],
                "preparationDigest": candidate["preparationDigest"],
                "runId": candidate["runId"],
                "boot": boot,
                "state": "STARTING",
                "configurationPath": str(startup_path),
                "configurationDigest": digest(startup),
                "recordPath": str(record_path),
                "released": False,
                "pid": None,
            }
            state = self._status(state_path, state)
            self.view(candidate, "STARTING")
            ready_r, ready_w = os.pipe()
            control_r, control_w = os.pipe()
            environment = {
                **self.config.environment,
                "NATIVE_DISPATCH_WORKER_ID": identity,
                "NATIVE_HOST_STARTUP_CONFIGURATION": str(startup_path),
                "NATIVE_HOST_SERVICE_LOCK_FD": str(fd),
                "NATIVE_HOST_SERVICE_CONTROL_FD": str(control_r),
                "NATIVE_HOST_SERVICE_READY_FD": str(ready_w),
            }
            child = self.popen(
                [sys.executable, "-m", "agent_operator.native_dispatch_host"],
                env=environment,
                pass_fds=(
                    fd,
                    control_r,
                    ready_w,
                    *(
                        (self.service_lock_fd,)
                        if self.service_lock_fd is not None
                        else ()
                    ),
                ),
                close_fds=True,
            )
            os.close(ready_w)
            ready_w = -1
            os.close(control_r)
            control_r = -1
            process_birth = birth(child.pid)
            if process_birth is None:
                raise ValueError("HOST_SERVICE_CHILD_EXITED")
            state = self._status(
                state_path, state, pid=child.pid, processBirth=process_birth
            )
            if not select.select(
                [ready_r], [], [], self.config.value["readinessSeconds"]
            )[0]:
                raise ValueError("HOST_SERVICE_READINESS_TIMEOUT")
            ready = json.loads(os.read(ready_r, 4096))
            registered = read(record_path)
            observation = registered["observation"]
            if (
                ready.get("pid") != child.pid
                or ready.get("startupDigest") != registered["digest"]
                or registered["digest"] != digest(observation)
                or observation.get("pid") != child.pid
                or observation.get("processBirth") != process_birth
                or observation.get("workerId") != identity
                or any(
                    observation.get(k) != startup[k]
                    for k in (
                        "namespace",
                        "securityDomain",
                        "principalId",
                        "authorizationResources",
                    )
                )
            ):
                raise ValueError("HOST_SERVICE_READINESS_MISMATCH")
            self.config.verify()
            if self.discovery.current(candidate) != candidate:
                raise ValueError("HOST_SERVICE_CANDIDATE_CHANGED")
            # Persist possible release before G; never forget a possibly live boot.
            state = self._status(
                state_path,
                state,
                state="RUNNING",
                released=True,
                startupDigest=registered["digest"],
            )
            os.write(control_w, b"G")
            self.view(candidate, "READY")
            self.children[identity] = Child(
                child, fd, control_w, state_path, state, candidate
            )
            fd = control_w = -1
            return True
        except BaseException:
            if child is not None:
                # Take ownership BEFORE any fallible close/signal/wait/status I/O.
                # Even failed cleanup cannot forget a potentially live process.
                retained = Child(child, fd, control_w, state_path, state, candidate)
                self.children[identity] = retained
                fd = control_w = -1
                if retained.control_fd >= 0:
                    os.close(retained.control_fd)
                    retained.control_fd = -1
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=self.config.value["shutdownSeconds"])
                    except subprocess.TimeoutExpired:
                        if not state.get("released"):
                            child.kill()
                            child.wait(timeout=self.config.value["shutdownSeconds"])
                retained.status = self._status(
                    state_path,
                    state,
                    state="EXIT_CONFIRMED"
                    if child.poll() is not None
                    else "EXIT_UNCONFIRMED",
                    retryAfter=self.clock() + min(300, 2 ** min(state["boot"], 8)),
                )
            raise
        finally:
            for descriptor in (fd, ready_r, ready_w, control_r, control_w):
                if descriptor >= 0:
                    os.close(descriptor)

    def _confirm_wait_exit(self, child):
        if getattr(self.discovery, "wait_access", None) is None:
            return
        if child.process.poll() is None:
            raise ValueError("HOST_SERVICE_WAIT_EXIT_NOT_OBSERVED")
        if "exitProof" not in child.status:
            state = dict(child.status)
            identity = {
                k: state.get(k)
                for k in ("pid", "processBirth", "boot", "startupDigest", "workerId")
            }
            receipt = {
                "state": "EXIT_CONFIRMED",
                "returnCode": child.process.returncode,
                "stoppedAt": datetime.fromtimestamp(self.clock(), UTC).isoformat(),
                "processIdentityDigest": digest(identity),
                "startupRecordDigest": state.get("startupDigest"),
            }
            proof = {"processRecord": state, "exitReceipt": receipt}
            # Written only after this actual Popen instance yielded a terminal code.
            child.status = self._status(
                child.status_path,
                state,
                exitProof={"record": proof, "digest": digest(proof)},
            )
        self._submit_wait_exit(child.candidate, child.status, child.process)

    def _submit_wait_exit(self, candidate, status, process=None):
        envelope = status.get("exitProof") or {}
        proof = envelope.get("record") or {}
        if envelope.get("digest") != digest(proof):
            raise ValueError("HOST_SERVICE_WAIT_EXIT_PROOF_INVALID")
        state, receipt = proof["processRecord"], proof["exitReceipt"]
        keys = (
            "namespace",
            "securityDomain",
            "principalId",
            "preparationDigest",
            "runId",
        )
        if (
            state.get("state") != "EXIT_CONFIRMED"
            or status.get("state") != "EXIT_CONFIRMED"
            or any(
                state.get(k) != candidate[k] or status.get(k) != candidate[k]
                for k in keys
            )
            or any(
                state.get(k) != status.get(k)
                for k in (
                    "workerId",
                    "pid",
                    "processBirth",
                    "boot",
                    "startupDigest",
                    "recordPath",
                )
            )
            or state.get("workerId") != self.identity(candidate)
            or state.get("released") is not True
            or type(receipt.get("returnCode")) is not int
            or receipt["returnCode"] != state.get("returnCode")
        ):
            raise ValueError("HOST_SERVICE_WAIT_EXIT_BINDING_INVALID")
        expected_path = (
            self.config.directory / f"{state['workerId']}-startup-{state['boot']}.json"
        )
        if Path(state["recordPath"]) != expected_path:
            raise ValueError("HOST_SERVICE_WAIT_EXIT_PATH_INVALID")
        startup = read(expected_path)
        record = startup.get("observation")
        if (
            not isinstance(record, dict)
            or startup.get("digest") != digest(record)
            or startup["digest"] != state.get("startupDigest")
            or any(
                record.get(k) != state.get(k)
                for k in (
                    "workerId",
                    "pid",
                    "processBirth",
                    "namespace",
                    "securityDomain",
                    "principalId",
                )
            )
            or record.get("authorizationResources") != [candidate["resource"]]
        ):
            raise ValueError("HOST_SERVICE_WAIT_EXIT_STARTUP_INVALID")
        identity = {
            k: state.get(k)
            for k in ("pid", "processBirth", "boot", "startupDigest", "workerId")
        }
        if (
            receipt.get("state") != "EXIT_CONFIRMED"
            or receipt.get("processIdentityDigest") != digest(identity)
            or receipt.get("startupRecordDigest") != startup["digest"]
        ):
            raise ValueError("HOST_SERVICE_WAIT_EXIT_RECEIPT_CHANGED")

        def verify_exit(_connection, cp, observation):
            if (
                (
                    process is not None
                    and (
                        process.poll() is None
                        or process.pid != state["pid"]
                        or process.returncode != receipt["returnCode"]
                    )
                )
                or read(expected_path) != startup
                or cp.worker_id != state["workerId"]
                or cp.startup_record_digest != startup["digest"]
                or observation.process_identity_digest != digest(identity)
                or observation.exit_receipt_digest != digest(receipt)
                or observation.stopped_at
                != datetime.fromisoformat(receipt["stoppedAt"])
            ):
                raise ValueError("HOST_SERVICE_WAIT_EXIT_NOT_VERIFIED")

        self.discovery.stopped(candidate, state, startup, receipt, verify_exit)

    def recover_wait_exit(self, candidate):
        """Redeliver a prior trusted exit fact, never infer exit from a missing PID."""
        identity = self.identity(candidate)
        if (
            identity in self.children
            or getattr(self.discovery, "wait_access", None) is None
        ):
            return
        path = self.config.directory / (identity + ".json")
        if not path.exists():
            return
        fd = lock(self.config.directory / (identity + ".lock"))
        try:
            state = read(path)
            if state.get("state") != "EXIT_CONFIRMED" or "exitProof" not in state:
                return
            self._submit_wait_exit(candidate, state)
            return True
        except Exception:
            self.last_error = "WAIT_STOP_UNCONFIRMED"
            self.view(candidate, "UNKNOWN", "OBSERVATION_UNAVAILABLE")
            return False
        finally:
            os.close(fd)

    def poll_children(self):
        for identity, child in list(self.children.items()):
            if child.process.poll() is not None:
                child.status = self._status(
                    child.status_path,
                    child.status,
                    state="EXIT_CONFIRMED",
                    returnCode=child.process.returncode,
                    retryAfter=self.clock()
                    + min(300, 2 ** min(child.status["boot"], 8)),
                )
                try:
                    self._confirm_wait_exit(child)
                except Exception:
                    # Physical exit is distinct from owner confirmation. A durable
                    # proof permits releasing OS capacity, never starting this wait.
                    self.last_error = "WAIT_STOP_UNCONFIRMED"
                    self.view(child.candidate, "UNKNOWN", "OBSERVATION_UNAVAILABLE")
                    proof = child.status.get("exitProof")
                    if proof and read(child.status_path).get("exitProof") == proof:
                        os.close(child.lock_fd)
                        if child.control_fd >= 0:
                            os.close(child.control_fd)
                        del self.children[identity]
                    continue
                os.close(child.lock_fd)
                if child.control_fd >= 0:
                    os.close(child.control_fd)
                self.view(child.candidate, "BLOCKED", "START_BLOCKED")
                del self.children[identity]
                continue
            read_failed = False
            try:
                maintain = getattr(self.discovery, "maintain", None)
                eligible = (
                    maintain(child.candidate, child.status)
                    if maintain is not None
                    else self.discovery.current(child.candidate)
                )
            except Exception:
                eligible = None
                read_failed = True
                self.last_error = "READ_FAILED"
            if eligible is None and child.control_fd >= 0:
                os.close(child.control_fd)
                child.control_fd = -1
                child.status = self._status(
                    child.status_path, child.status, state="STOPPING"
                )
            if eligible is None:
                self.view(
                    child.candidate,
                    "UNKNOWN" if read_failed else "STOPPING",
                    "OBSERVATION_UNAVAILABLE"
                    if read_failed
                    else "CURRENT_CONDITIONS_BLOCKED",
                )
            elif child.control_fd < 0:
                self.view(child.candidate, "STOPPING", "CURRENT_CONDITIONS_BLOCKED")
            else:
                self.view(child.candidate, "READY")

    def tick(self):
        self.last_error = None
        self.config.verify()
        self.poll_children()
        for candidate in self.discovery.page():
            if self.identity(candidate) in self.children:
                continue
            if len(self.children) >= self.config.value["maxHosts"]:
                self.view(candidate, "QUEUED", "WAITING_CAPACITY")
                continue
            try:
                self.launch(candidate)
            except (OSError, ValueError):
                self.last_error = "START_BLOCKED"
                self.view(candidate, "BLOCKED", "START_BLOCKED")
        write(
            self.config.directory / "service-status.json",
            {
                "schema": "native-exact-host-service.v1",
                "pid": os.getpid(),
                "processBirth": birth(os.getpid()),
                "observedAt": self.clock(),
                "state": self.last_error or "RUNNING",
                "children": list(self.children),
            },
        )

    def close(self):
        unresolved = []
        pending_wait = []
        for child in self.children.values():
            if child.control_fd >= 0:
                os.close(child.control_fd)
                child.control_fd = -1
        deadline = time.monotonic() + self.config.value["shutdownSeconds"]
        for child in self.children.values():
            # Child retains its lock until actual exit, even after this timeout.
            with suppress(subprocess.TimeoutExpired):
                child.process.wait(timeout=max(0, deadline - time.monotonic()))
            child.status = self._status(
                child.status_path,
                child.status,
                state="EXIT_CONFIRMED"
                if child.process.poll() is not None
                else "EXIT_UNCONFIRMED",
                returnCode=child.process.returncode,
            )
            if child.process.poll() is None:
                unresolved.append(child.status["workerId"])
            else:
                try:
                    self._confirm_wait_exit(child)
                except Exception:
                    pending_wait.append(child.status["workerId"])
            os.close(child.lock_fd)
        self.children.clear()
        write(
            self.config.directory / "service-status.json",
            {
                "schema": "native-exact-host-service.v1",
                "pid": os.getpid(),
                "processBirth": birth(os.getpid()),
                "observedAt": self.clock(),
                "state": "EXIT_UNCONFIRMED" if unresolved else "DRAINED",
                "children": unresolved,
                "pendingWaitObservations": pending_wait,
            },
        )


def main():
    from agent_console.governed_execution_ownership import (
        execution_database_fingerprint,
    )

    from .native_dispatch_reconciler import build_native_dispatch_from_environment

    path = os.environ.get("NATIVE_EXACT_HOST_SERVICE_CONFIGURATION")
    if not path:
        raise ValueError("HOST_SERVICE_CONFIGURATION_REQUIRED")
    config = Configuration(path)
    fingerprint = execution_database_fingerprint(
        os.environ["NATIVE_DISPATCH_DATABASE_URL"]
    )
    lock_directory = machine_lock_directory()
    fd = lock(lock_directory / (fingerprint + ".lock"))
    assembly = None
    service = None
    stop = Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda _sig, _frame: stop.set())
    try:
        write(
            config.directory / "service-status.json",
            {
                "schema": "native-exact-host-service.v1",
                "pid": os.getpid(),
                "processBirth": birth(os.getpid()),
                "observedAt": time.time(),
                "state": "STARTING",
                "children": [],
            },
        )
        assembly = build_native_dispatch_from_environment()
        if assembly is None:
            raise ValueError("HOST_SERVICE_ASSEMBLY_REQUIRED")
        discovery = Discovery(
            assembly,
            tuple(
                config.value[k] for k in ("namespace", "securityDomain", "principalId")
            ),
            fingerprint,
        )
        service = HostService(config, discovery, service_lock_fd=fd)
        while not stop.is_set():
            try:
                service.tick()
            except Exception:
                # No busy automatic respawn on observation/configuration failure.
                logging.getLogger(__name__).error(
                    "Native host service observation blocked"
                )
                break
            stop.wait(config.value["pollSeconds"])
    finally:
        if service is not None:
            service.close()
        if assembly is not None:
            assembly.close()
        os.close(fd)


if __name__ == "__main__":
    main()
