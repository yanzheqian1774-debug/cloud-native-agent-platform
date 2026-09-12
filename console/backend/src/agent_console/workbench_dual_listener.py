"""One-process, one-worker Uvicorn child for public and private route sets."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import socket
import sys
from contextlib import suppress

import uvicorn

CONFIGURATION_EXIT = 78


def _bind(host: str, port: int) -> socket.socket:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    value = socket.socket(family, socket.SOCK_STREAM)
    value.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    value.bind((host, port))
    value.listen(2048)
    value.setblocking(False)
    return value


def _paths(application) -> frozenset[str]:
    paths: set[str] = set()

    def collect(routes) -> None:
        for route in routes:
            path = getattr(route, "path", None)
            if isinstance(path, str):
                paths.add(path)
            included = getattr(route, "original_router", None)
            if included is not None:
                collect(included.routes)

    collect(application.routes)
    return frozenset(paths)


async def _serve(public_socket: socket.socket, private_socket: socket.socket) -> int:
    from agent_console import app as composition

    try:
        public = composition.get_workbench_app()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return CONFIGURATION_EXIT
    private = composition.app
    public_paths = _paths(public)
    private_paths = _paths(private)
    if (
        any(path.startswith("/api/internal/") for path in public_paths)
        or any(path.startswith("/api/workbench/") for path in private_paths)
        or not any(path.startswith("/api/workbench/v1/") for path in public_paths)
    ):
        print("WORKBENCH_ROUTE_INVENTORY_INVALID", file=sys.stderr)
        return CONFIGURATION_EXIT

    public_server = uvicorn.Server(
        uvicorn.Config(public, workers=1, lifespan="off", access_log=False)
    )
    private_server = uvicorn.Server(
        uvicorn.Config(private, workers=1, lifespan="off", access_log=False)
    )
    public_server.install_signal_handlers = lambda: None
    private_server.install_signal_handlers = lambda: None
    loop = asyncio.get_running_loop()
    shutdown_reason: list[str | None] = [None]

    def stop(reason: str = "SIGNAL") -> None:
        if shutdown_reason[0] is None:
            shutdown_reason[0] = reason
        public_server.should_exit = True
        private_server.should_exit = True

    for name in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(name, stop)

    async def watch_supervisor() -> None:
        database_url = os.environ.get("EXECUTION_DATABASE_URL", "")
        while composition._governed_execution_supervision.allows(database_url):
            await asyncio.sleep(0.1)
        stop("SUPERVISOR_LOST")

    server_tasks = {
        asyncio.create_task(public_server.serve(sockets=[public_socket])),
        asyncio.create_task(private_server.serve(sockets=[private_socket])),
    }
    supervisor_task = asyncio.create_task(watch_supervisor())
    tasks = {*server_tasks, supervisor_task}

    async def fail_start(reason: str) -> int:
        stop(reason)
        supervisor_task.cancel()
        await asyncio.gather(*server_tasks, supervisor_task, return_exceptions=True)
        return CONFIGURATION_EXIT

    for _ in range(2000):
        if public_server.started and private_server.started:
            break
        if any(task.done() for task in tasks):
            return await fail_start("START_FAILED")
        await asyncio.sleep(0.01)
    else:
        return await fail_start("START_TIMEOUT")

    ready_fd = int(os.environ.get("WORKBENCH_READINESS_FD", "-1"))
    if ready_fd < 0:
        return await fail_start("READINESS_FD_MISSING")
    message = {
        "schemaVersion": "workbench-dual-listener-ready.v1",
        "pid": os.getpid(),
        "publicRoutes": sorted(public_paths),
        "privateRoutes": sorted(private_paths),
    }
    os.write(
        ready_fd,
        json.dumps(message, sort_keys=True, separators=(",", ":")).encode() + b"\n",
    )
    os.close(ready_fd)

    done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    if shutdown_reason[0] is None:
        stop("SERVER_EXITED")
    supervisor_task.cancel()
    await asyncio.gather(*server_tasks, supervisor_task, return_exceptions=True)
    failures = [task.exception() for task in done if not task.cancelled()]
    return (
        0
        if shutdown_reason[0] == "SIGNAL" and all(result is None for result in failures)
        else CONFIGURATION_EXIT
    )


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-host", default="127.0.0.1")
    parser.add_argument("--public-port", type=int, required=True)
    parser.add_argument("--private-host", default="127.0.0.1")
    parser.add_argument("--private-port", type=int, required=True)
    arguments = parser.parse_args(argv)
    sockets: list[socket.socket] = []
    try:
        sockets = [
            _bind(arguments.public_host, arguments.public_port),
            _bind(arguments.private_host, arguments.private_port),
        ]
        return asyncio.run(_serve(sockets[0], sockets[1]))
    except (OSError, TypeError, ValueError) as exc:
        print(f"WORKBENCH_LISTENER_START_FAILED {exc}", file=sys.stderr)
        return CONFIGURATION_EXIT
    finally:
        for value in sockets:
            value.close()


if __name__ == "__main__":
    raise SystemExit(run())
