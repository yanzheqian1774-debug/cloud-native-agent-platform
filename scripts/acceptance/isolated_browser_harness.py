#!/usr/bin/env python3
"""Own an isolated real backend while a serialized browser command runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import socket
import stat
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


def release_manifest(root: Path) -> dict[str, dict[str, str | int]]:
    result: dict[str, dict[str, str | int]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        entry: dict[str, str | int] = {"mode": stat.S_IMODE(path.lstat().st_mode)}
        if path.is_symlink():
            entry.update(type="symlink", target=os.readlink(path))
        elif path.is_dir():
            entry["type"] = "directory"
        elif path.is_file():
            entry.update(
                type="file", sha256=hashlib.sha256(path.read_bytes()).hexdigest()
            )
        else:
            entry["type"] = "other"
        result[relative] = entry
    return result


def assert_immutable(root: Path) -> None:
    writable = [
        str(path)
        for path in (root, *root.rglob("*"))
        if not path.is_symlink() and path.stat().st_mode & 0o222
    ]
    if writable:
        raise RuntimeError(f"release tree is writable by mode: {writable[0]}")


def endpoint(value: str, name: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"http", "https", "postgresql", "postgres"}
        or not parsed.hostname
        or not parsed.port
    ):
        raise ValueError(f"{name} must include an explicit scheme, host and port")
    return value


class Harness:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.release = args.release_root.resolve()
        self.runtime = args.runtime_dir.resolve()
        self.runtime.mkdir(parents=True, exist_ok=False)
        if self.runtime == self.release or self.release in self.runtime.parents:
            raise RuntimeError("runtime directory must be outside the release")
        self.token = secrets.token_urlsafe(32)
        self.child: subprocess.Popen[bytes] | None = None
        self.child_started_ns = 0
        self.socket_path = self.runtime / "control.sock"
        self.metadata_path = self.runtime / "backend.json"
        caches = [
            path
            for path in self.release.rglob("*")
            if path.name == "__pycache__" or path.suffix == ".pyc"
        ]
        if caches:
            raise RuntimeError(f"release already contains Python cache: {caches[0]}")
        self.before = release_manifest(self.release)
        (self.runtime / "release-manifest-before.json").write_text(
            json.dumps(self.before, indent=2, sort_keys=True), encoding="utf-8"
        )
        assert_immutable(self.release)

    @property
    def url(self) -> str:
        return f"http://{self.args.backend_host}:{self.args.backend_port}"

    def assert_port_free(self) -> None:
        with socket.socket() as connection_probe:
            connection_probe.settimeout(0.2)
            if (
                connection_probe.connect_ex(
                    (self.args.backend_host, self.args.backend_port)
                )
                == 0
            ):
                raise RuntimeError(
                    "backend port is occupied by an unowned process: "
                    f"{self.args.backend_host}:{self.args.backend_port}"
                )
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((self.args.backend_host, self.args.backend_port))
            except OSError as exc:
                raise RuntimeError(
                    "backend port is occupied by an unowned process: "
                    f"{self.args.backend_host}:{self.args.backend_port}"
                ) from exc

    def write_metadata(self) -> None:
        assert self.child is not None
        payload = {
            "schemaVersion": 1,
            "ownershipToken": self.token,
            "supervisorPid": os.getpid(),
            "backendPid": self.child.pid,
            "backendStartTimeNs": self.child_started_ns,
            "backendHost": self.args.backend_host,
            "backendPort": self.args.backend_port,
            "backendUrl": self.url,
            "releaseRoot": str(self.release),
            "runtimeDir": str(self.runtime),
            "controlSocket": str(self.socket_path),
        }
        temporary = self.metadata_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload), encoding="utf-8")
        temporary.replace(self.metadata_path)

    def wait_health(self, expected: bool, timeout: float = 20) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            healthy = False
            try:
                with urllib.request.urlopen(
                    f"{self.url}/healthz", timeout=0.5
                ) as response:
                    healthy = response.status == 200
            except Exception:
                pass
            if healthy is expected:
                return
            time.sleep(0.1)
        raise RuntimeError(f"backend health did not become {expected}")

    def start(self, overrides: dict[str, str] | None = None) -> None:
        self.assert_port_free()
        env = os.environ.copy()
        python_paths = [
            str((self.release / entry).resolve())
            for entry in self.args.python_path.split(os.pathsep)
        ]
        env.update(
            {
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPYCACHEPREFIX": str(self.runtime / "pycache"),
                "AGENT_DEFINITION_DATABASE_URL": self.args.postgres_url,
                "SKILL_MCP_DATABASE_URL": self.args.postgres_url,
                "KNOWLEDGE_DATABASE_URL": self.args.postgres_url,
                "WORKFLOW_RUNTIME_DATABASE_URL": self.args.postgres_url,
                "KNOWLEDGE_QDRANT_URL": self.args.qdrant_url,
                "S5_IMPL_041_QDRANT_URL": self.args.qdrant_url,
                "S5_HARNESS_OWNERSHIP_TOKEN": self.token,
                "PYTHONPATH": os.pathsep.join(python_paths),
            }
        )
        allowed = {
            "S5_PLANNING_PROVIDER",
            "S5_PLANNING_BASE_URL",
            "S5_PLANNING_API_KEY",
            "S5_PLANNING_MODEL",
            "S5_EMBEDDING_PROVIDER",
            "S5_EMBEDDING_BASE_URL",
            "S5_EMBEDDING_API_KEY",
            "S5_EMBEDDING_MODEL",
        }
        for key, value in (overrides or {}).items():
            if key not in allowed or not isinstance(value, str):
                raise RuntimeError("unsupported backend environment override")
            if key.endswith("BASE_URL"):
                parsed = urlparse(value)
                if (
                    parsed.scheme != "http"
                    or parsed.hostname
                    not in {
                        "127.0.0.1",
                        "localhost",
                    }
                    or not parsed.port
                ):
                    raise RuntimeError("test provider URL must be explicit localhost")
            env[key] = value
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "agent_console.app:app",
            "--host",
            self.args.backend_host,
            "--port",
            str(self.args.backend_port),
            "--header",
            f"X-Harness-Ownership-Token:{self.token}",
        ]
        self.child = subprocess.Popen(command, cwd=self.release, env=env)
        self.child_started_ns = time.time_ns()
        self.write_metadata()
        self.wait_health(True)

    def verify_owned(self) -> None:
        if self.child is None or self.child.poll() is not None:
            raise RuntimeError("owned backend is not running")
        metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        expected = (
            self.token,
            self.child.pid,
            str(self.release),
            self.args.backend_port,
        )
        actual = (
            metadata.get("ownershipToken"),
            metadata.get("backendPid"),
            metadata.get("releaseRoot"),
            metadata.get("backendPort"),
        )
        if actual != expected:
            raise RuntimeError("backend ownership metadata mismatch")
        if Path(f"/proc/{self.child.pid}").exists():
            cwd = Path(f"/proc/{self.child.pid}/cwd").resolve()
            command = Path(f"/proc/{self.child.pid}/cmdline").read_bytes().split(b"\0")
            joined = b" ".join(command)
            if (
                cwd != self.release
                or b"uvicorn" not in joined
                or str(self.args.backend_port).encode() not in command
                or self.token.encode() not in joined
            ):
                raise RuntimeError("backend process identity mismatch")
        else:
            command = subprocess.run(
                ["ps", "-p", str(self.child.pid), "-o", "command="],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            cwd = subprocess.run(
                ["lsof", "-a", "-p", str(self.child.pid), "-d", "cwd", "-Fn"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            listener = subprocess.run(
                [
                    "lsof",
                    "-nP",
                    "-a",
                    "-p",
                    str(self.child.pid),
                    f"-iTCP:{self.args.backend_port}",
                    "-sTCP:LISTEN",
                ],
                capture_output=True,
                text=True,
                check=False,
            ).stdout
            if (
                "uvicorn" not in command
                or self.token not in command
                or str(self.args.backend_port) not in command
                or f"n{self.release}" not in cwd
                or not listener
            ):
                raise RuntimeError(
                    "backend executable, command, cwd, token, or listener mismatch"
                )

    def stop(self) -> None:
        if self.child is None or self.child.poll() is not None:
            return
        self.verify_owned()
        self.child.terminate()
        try:
            self.child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.verify_owned()
            self.child.kill()
            self.child.wait(timeout=5)
        self.wait_health(False)

    def restart(self, overrides: dict[str, str] | None = None) -> None:
        self.stop()
        self.start(overrides)

    def serve(self, ready: threading.Event) -> None:
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(str(self.socket_path))
            os.chmod(self.socket_path, 0o600)
            server.listen()
            ready.set()
            while True:
                connection, _ = server.accept()
                with connection:
                    request = json.loads(connection.recv(65536))
                    if request.get("ownershipToken") != self.token:
                        response = {"ok": False, "error": "ownership token mismatch"}
                    elif request.get("action") == "restart":
                        try:
                            self.restart(request.get("environment"))
                            response = {
                                "ok": True,
                                "backendPid": self.child.pid,
                                "backendStartTimeNs": self.child_started_ns,
                            }
                        except Exception as exc:
                            response = {"ok": False, "error": str(exc)}
                    elif request.get("action") == "status":
                        try:
                            self.verify_owned()
                            response = {
                                "ok": True,
                                "backendPid": self.child.pid,
                                "backendStartTimeNs": self.child_started_ns,
                            }
                        except Exception as exc:
                            response = {"ok": False, "error": str(exc)}
                    elif request.get("action") == "stop":
                        try:
                            self.stop()
                            response = {"ok": True}
                        except Exception as exc:
                            response = {"ok": False, "error": str(exc)}
                    elif request.get("action") == "start":
                        try:
                            if self.child is not None and self.child.poll() is None:
                                raise RuntimeError("owned backend is already running")
                            self.start(request.get("environment"))
                            response = {
                                "ok": True,
                                "backendPid": self.child.pid,
                                "backendStartTimeNs": self.child_started_ns,
                            }
                        except Exception as exc:
                            response = {"ok": False, "error": str(exc)}
                    else:
                        response = {"ok": False, "error": "unsupported action"}
                    connection.sendall(json.dumps(response).encode())

    def verify_release(self) -> None:
        after = release_manifest(self.release)
        (self.runtime / "release-manifest-after.json").write_text(
            json.dumps(after, indent=2, sort_keys=True), encoding="utf-8"
        )
        if after != self.before:
            raise RuntimeError(
                "immutable release content, file modes, or directory modes changed"
            )
        caches = [
            path
            for path in self.release.rglob("*")
            if path.name == "__pycache__" or path.suffix == ".pyc"
        ]
        if caches:
            raise RuntimeError(f"Python cache appeared inside release: {caches[0]}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-root", required=True, type=Path)
    parser.add_argument("--runtime-dir", required=True, type=Path)
    parser.add_argument("--backend-host", required=True)
    parser.add_argument("--backend-port", required=True, type=int)
    parser.add_argument("--postgres-url", required=True)
    parser.add_argument("--qdrant-url", required=True)
    parser.add_argument("--python-path", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command[:1] == ["--"]:
        args.command = args.command[1:]
    if not args.command:
        parser.error("a browser command is required after --")
    args.postgres_url = endpoint(args.postgres_url, "PostgreSQL endpoint")
    args.qdrant_url = endpoint(args.qdrant_url, "Qdrant endpoint")
    return args


def main() -> int:
    args = parse_args()
    harness = Harness(args)
    command_result = 1
    try:
        harness.start()
        ready = threading.Event()
        threading.Thread(target=harness.serve, args=(ready,), daemon=True).start()
        ready.wait(timeout=5)
        env = os.environ.copy()
        env.update(
            {
                "S5_HARNESS_METADATA": str(harness.metadata_path),
                "S5_HARNESS_OWNERSHIP_TOKEN": harness.token,
                "CONSOLE_BACKEND_URL": harness.url,
                "VITE_BACKEND_URL": harness.url,
                "KNOWLEDGE_QDRANT_DIRECT_URL": args.qdrant_url,
                "S5_IMMUTABLE_ACCEPTANCE": "1",
                "PLAYWRIGHT_OUTPUT_DIR": str(harness.runtime / "playwright-output"),
                "S5_HARNESS_PYTHON": sys.executable,
            }
        )
        command_result = subprocess.run(
            args.command, cwd=harness.release, env=env, check=False
        ).returncode
    finally:
        try:
            harness.stop()
        finally:
            harness.verify_release()
    return command_result


if __name__ == "__main__":
    raise SystemExit(main())
