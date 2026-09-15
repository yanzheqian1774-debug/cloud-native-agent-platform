from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
from typing import ClassVar

import pytest
from agent_console import app as composition
from agent_console import workbench_dual_listener as dual
from agent_console.governed_execution_supervisor import (
    CONFIGURATION_EXIT,
    _read_ready,
    run,
)
from fastapi import FastAPI


def test_supervisor_requires_a_complete_dual_listener_pair() -> None:
    assert run(["--public-port", "18080"]) == CONFIGURATION_EXIT


def test_readiness_handshake_is_bounded_and_typed() -> None:
    read_fd, write_fd = os.pipe()
    value = {"schemaVersion": "workbench-dual-listener-ready.v1", "pid": 7}
    os.write(write_fd, json.dumps(value).encode() + b"\n")
    os.close(write_fd)
    try:
        assert _read_ready(read_fd, 0.1) == value
    finally:
        os.close(read_fd)


def test_supervisor_kills_dual_child_that_ignores_termination(
    monkeypatch, tmp_path
) -> None:
    from agent_console import governed_execution_supervisor as supervisor

    class Child:
        pid = 7021
        terminated = False
        killed = False
        waits = 0

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True

        def wait(self, timeout=None):
            self.waits += 1
            if self.waits == 1:
                raise subprocess.TimeoutExpired("dual-listener", timeout)
            return -9

    child = Child()
    monkeypatch.setenv("EXECUTION_DATABASE_URL", "postgresql://test/readiness")
    monkeypatch.setattr(supervisor, "_state_dir", lambda: tmp_path)
    monkeypatch.setattr(supervisor.subprocess, "Popen", lambda *args, **kwargs: child)
    monkeypatch.setattr(
        supervisor,
        "_read_ready",
        lambda descriptor, timeout: (_ for _ in ()).throw(
            ValueError("WORKBENCH_READINESS_INCOMPLETE")
        ),
    )

    assert (
        run(
            [
                "--public-port",
                "18080",
                "--private-port",
                "18081",
                "--shutdown-timeout",
                "0.01",
            ]
        )
        == CONFIGURATION_EXIT
    )
    assert child.terminated is True
    assert child.killed is True


def test_private_default_app_never_registers_workbench_routes() -> None:
    assert not any(
        path.startswith("/api/workbench/") for path in dual._paths(composition.app)
    )


def test_dual_child_starts_both_in_one_loop_and_closes_on_supervisor_loss(
    monkeypatch,
) -> None:
    public = FastAPI()
    private = FastAPI()

    @public.get("/api/workbench/v1/session")
    def session():
        return {}

    @private.get("/api/internal/example")
    def internal():
        return {}

    class Guard:
        remaining = 3

        def allows(self, database_url):
            self.remaining -= 1
            return self.remaining > 0

    class Server:
        instances: ClassVar[list] = []

        def __init__(self, configuration):
            self.configuration = configuration
            self.started = False
            self.should_exit = False
            self.instances.append(self)

        def install_signal_handlers(self):
            raise AssertionError("dual child owns signals")

        async def serve(self, *, sockets):
            assert len(sockets) == 1
            self.started = True
            while not self.should_exit:
                await asyncio.sleep(0.01)

    monkeypatch.setattr(composition, "get_workbench_app", lambda: public)
    monkeypatch.setattr(composition, "app", private)
    monkeypatch.setattr(composition, "_governed_execution_supervision", Guard())
    monkeypatch.setattr(dual.uvicorn, "Server", Server)
    monkeypatch.setenv("EXECUTION_DATABASE_URL", "postgresql://test/example")
    read_fd, write_fd = os.pipe()
    monkeypatch.setenv("WORKBENCH_READINESS_FD", str(write_fd))
    try:
        assert (
            asyncio.run(dual._serve(object(), object()))  # type: ignore[arg-type]
            == CONFIGURATION_EXIT
        )
        ready = json.loads(os.read(read_fd, 256_000))
    finally:
        os.close(read_fd)
    assert ready["publicRoutes"] == [
        "/api/workbench/v1/session",
        "/docs",
        "/docs/oauth2-redirect",
        "/openapi.json",
        "/redoc",
    ]
    assert "/api/internal/example" in ready["privateRoutes"]
    assert len(Server.instances) == 2
    assert all(server.should_exit for server in Server.instances)


@pytest.mark.parametrize("exiting_app", ["public", "private"])
def test_either_listener_unexpected_exit_closes_the_pair_and_fails(
    monkeypatch, exiting_app
) -> None:
    public = FastAPI()
    private = FastAPI()

    @public.get("/api/workbench/v1/session")
    def session():
        return {}

    @private.get("/api/internal/example")
    def internal():
        return {}

    class Guard:
        def allows(self, database_url):
            return True

    class Server:
        instances: ClassVar[list] = []

        def __init__(self, configuration):
            self.configuration = configuration
            self.started = False
            self.should_exit = False
            self.instances.append(self)

        async def serve(self, *, sockets):
            self.started = True
            if self.configuration.app is (
                public if exiting_app == "public" else private
            ):
                while not all(server.started for server in self.instances):
                    await asyncio.sleep(0)
                return
            while not self.should_exit:
                await asyncio.sleep(0.01)

    monkeypatch.setattr(composition, "get_workbench_app", lambda: public)
    monkeypatch.setattr(composition, "app", private)
    monkeypatch.setattr(composition, "_governed_execution_supervision", Guard())
    monkeypatch.setattr(dual.uvicorn, "Server", Server)
    read_fd, write_fd = os.pipe()
    monkeypatch.setenv("WORKBENCH_READINESS_FD", str(write_fd))
    try:
        assert (
            asyncio.run(dual._serve(object(), object()))  # type: ignore[arg-type]
            == CONFIGURATION_EXIT
        )
        assert json.loads(os.read(read_fd, 256_000))["pid"] == os.getpid()
    finally:
        os.close(read_fd)
    assert len(Server.instances) == 2
    assert all(server.should_exit for server in Server.instances)


@pytest.mark.parametrize("failing_app", ["public", "private"])
def test_partial_listener_start_failure_closes_the_other_and_fails(
    monkeypatch, failing_app
) -> None:
    public = FastAPI()
    private = FastAPI()

    @public.get("/api/workbench/v1/session")
    def session():
        return {}

    @private.get("/api/internal/example")
    def internal():
        return {}

    class Guard:
        def allows(self, database_url):
            return True

    class Server:
        instances: ClassVar[list] = []

        def __init__(self, configuration):
            self.configuration = configuration
            self.started = False
            self.should_exit = False
            self.instances.append(self)

        async def serve(self, *, sockets):
            if self.configuration.app is (
                public if failing_app == "public" else private
            ):
                raise RuntimeError(f"{failing_app} listener failed")
            self.started = True
            while not self.should_exit:
                await asyncio.sleep(0.01)

    monkeypatch.setattr(composition, "get_workbench_app", lambda: public)
    monkeypatch.setattr(composition, "app", private)
    monkeypatch.setattr(composition, "_governed_execution_supervision", Guard())
    monkeypatch.setattr(dual.uvicorn, "Server", Server)
    read_fd, write_fd = os.pipe()
    monkeypatch.setenv("WORKBENCH_READINESS_FD", str(write_fd))
    try:
        assert (
            asyncio.run(dual._serve(object(), object()))  # type: ignore[arg-type]
            == CONFIGURATION_EXIT
        )
        os.close(write_fd)
        write_fd = -1
        assert os.read(read_fd, 1) == b""
    finally:
        if write_fd >= 0:
            os.close(write_fd)
        os.close(read_fd)
    assert len(Server.instances) == 2
    assert all(server.should_exit for server in Server.instances)


def test_authorized_signal_shutdown_closes_both_and_succeeds(monkeypatch) -> None:
    public = FastAPI()
    private = FastAPI()

    @public.get("/api/workbench/v1/session")
    def session():
        return {}

    @private.get("/api/internal/example")
    def internal():
        return {}

    callbacks = {}
    running_loop = asyncio.get_running_loop

    class LoopProxy:
        def add_signal_handler(self, name, callback):
            callbacks[name] = callback

    class Guard:
        def allows(self, database_url):
            return True

    class Server:
        instances: ClassVar[list] = []

        def __init__(self, configuration):
            self.configuration = configuration
            self.started = False
            self.should_exit = False
            self.instances.append(self)

        async def serve(self, *, sockets):
            self.started = True
            if self.configuration.app is public:
                while not all(server.started for server in self.instances):
                    await asyncio.sleep(0)
                callbacks[signal.SIGTERM]()
            while not self.should_exit:
                await asyncio.sleep(0.01)

    monkeypatch.setattr(composition, "get_workbench_app", lambda: public)
    monkeypatch.setattr(composition, "app", private)
    monkeypatch.setattr(composition, "_governed_execution_supervision", Guard())
    monkeypatch.setattr(dual.uvicorn, "Server", Server)
    monkeypatch.setattr(
        dual.asyncio,
        "get_running_loop",
        lambda: LoopProxy() if callbacks == {} else running_loop(),
    )
    read_fd, write_fd = os.pipe()
    monkeypatch.setenv("WORKBENCH_READINESS_FD", str(write_fd))
    try:
        assert asyncio.run(dual._serve(object(), object())) == 0  # type: ignore[arg-type]
        assert json.loads(os.read(read_fd, 256_000))["pid"] == os.getpid()
    finally:
        os.close(read_fd)
    assert len(Server.instances) == 2
    assert all(server.should_exit for server in Server.instances)
