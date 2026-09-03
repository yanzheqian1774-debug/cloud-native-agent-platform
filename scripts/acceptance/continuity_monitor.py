#!/usr/bin/env python3
"""Owned server-local, minimum-disclosure release continuity monitor."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn

SCHEMA_VERSION = "release-continuity-monitor.v1"
CONTRACT_VERSION = "SERVER_LOCAL_CONTINUITY_V1"
SENTINEL_CLASSES = frozenset({"PUBLIC", "ORIGINAL_STAGING"})
PHASES = frozenset(
    {"START", "OBSERVATION", "INDEPENDENT_CONTINUATION", "STOP", "COMPLETE"}
)
CATEGORIES = frozenset(
    {
        "MATCH",
        "MISMATCH",
        "HEALTHY",
        "UNHEALTHY",
        "NOT_REQUIRED",
        "NOT_OBSERVED_INDEPENDENTLY",
    }
)
COMPLETION = frozenset({"RUNNING", "STOP_REQUESTED", "COMPLETE", "FAILED"})
RECORD_FIELDS = frozenset(
    {
        "schemaVersion",
        "workspaceOwnershipDigest",
        "sentinelClass",
        "sequence",
        "phase",
        "healthClass",
        "pidContinuityClass",
        "startTimeContinuityClass",
        "restartCountClass",
        "listenerProcessContinuityClass",
        "managementChannelObservabilityClass",
        "completionState",
        "previousDigest",
        "recordDigest",
    }
)
SENTINEL_FIELDS = frozenset(
    {"sentinelClass", "serviceUnit", "healthPort", "listenerPort", "listenerRequired"}
)
IDENTIFIER = re.compile(r"[A-Za-z0-9_.@-]{1,128}\Z")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
MAX_OBSERVATIONS = 7200


class MonitorError(ValueError):
    """Disclosure-safe continuity-monitor failure."""


def fail(message: str) -> NoReturn:
    raise MonitorError(message)


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def ownership_digest(workspace: Path, token: str) -> str:
    return _digest(f"{workspace.resolve()}\0{token}\0{CONTRACT_VERSION}".encode())


def validate_contract(value: Any) -> dict[str, Any]:
    fields = frozenset(
        {"contractVersion", "intervalSeconds", "maximumRuntimeSeconds", "sentinels"}
    )
    if not isinstance(value, dict) or set(value) != fields:
        fail("continuity monitor contract has missing or unknown fields")
    if value["contractVersion"] != CONTRACT_VERSION:
        fail("continuity monitor contract version is unsupported")
    interval = value["intervalSeconds"]
    maximum = value["maximumRuntimeSeconds"]
    if type(interval) is not int or not 1 <= interval <= 60:
        fail("continuity monitor interval is outside the accepted bound")
    if type(maximum) is not int or not interval <= maximum <= 21600:
        fail("continuity monitor runtime is outside the accepted bound")
    sentinels = value["sentinels"]
    if not isinstance(sentinels, list) or len(sentinels) != 2:
        fail("continuity sentinels are absent or incomplete")
    seen: set[str] = set()
    for item in sentinels:
        if not isinstance(item, dict) or set(item) != SENTINEL_FIELDS:
            fail("continuity sentinel has missing or unknown fields")
        identity = item["sentinelClass"]
        if identity not in SENTINEL_CLASSES or identity in seen:
            fail("continuity sentinel identity is unapproved or duplicated")
        if not isinstance(item["serviceUnit"], str) or not IDENTIFIER.fullmatch(
            item["serviceUnit"]
        ):
            fail("continuity sentinel service identity is malformed")
        for field in ("healthPort", "listenerPort"):
            if type(item[field]) is not int or not 1 <= item[field] <= 65535:
                fail("continuity sentinel port is malformed")
        if type(item["listenerRequired"]) is not bool:
            fail("continuity sentinel listener policy is malformed")
        seen.add(identity)
    if seen != SENTINEL_CLASSES:
        fail("continuity sentinel set is unapproved")
    return value


def _canonical_record(record: dict[str, Any]) -> bytes:
    return json.dumps(record, sort_keys=True, separators=(",", ":")).encode()


def _record_digest(record: dict[str, Any]) -> str:
    return _digest(
        _canonical_record({k: v for k, v in record.items() if k != "recordDigest"})
    )


def validate_evidence(
    data: bytes, *, expected_ownership_digest: str
) -> list[dict[str, Any]]:
    try:
        text = data.decode("utf-8")
        records = [json.loads(line) for line in text.splitlines()]
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise MonitorError("continuity evidence is malformed") from exc
    if not records or len(records) > MAX_OBSERVATIONS * 2 + 4:
        fail("continuity evidence length is outside the accepted bound")
    previous = "sha256:" + "0" * 64
    for sequence, record in enumerate(records):
        if not isinstance(record, dict) or set(record) != RECORD_FIELDS:
            fail("continuity record has missing or unknown fields")
        if record["schemaVersion"] != SCHEMA_VERSION or record["sequence"] != sequence:
            fail(
                "continuity sequence is missing, duplicated, reordered, or out of range"
            )
        if record["workspaceOwnershipDigest"] != expected_ownership_digest:
            fail("continuity workspace ownership does not match")
        if record["sentinelClass"] not in SENTINEL_CLASSES | {"MONITOR"}:
            fail("continuity sentinel class is unapproved")
        if record["phase"] not in PHASES or record["completionState"] not in COMPLETION:
            fail("continuity lifecycle category is invalid")
        if (
            record["healthClass"] not in CATEGORIES
            or record["pidContinuityClass"] not in CATEGORIES
        ):
            fail("continuity observation category is invalid")
        for field in (
            "startTimeContinuityClass",
            "restartCountClass",
            "listenerProcessContinuityClass",
            "managementChannelObservabilityClass",
        ):
            if record[field] not in CATEGORIES:
                fail("continuity observation category is invalid")
        if (
            record["previousDigest"] != previous
            or not isinstance(record["recordDigest"], str)
            or not DIGEST.fullmatch(record["recordDigest"])
        ):
            fail("continuity hash chain is broken")
        if record["recordDigest"] != _record_digest(record):
            fail("continuity record was altered")
        previous = record["recordDigest"]
    if (
        records[0]["phase"] != "START"
        or records[-1]["phase"] != "COMPLETE"
        or records[-1]["completionState"] != "COMPLETE"
    ):
        fail("continuity lifecycle is incomplete")
    observed = {
        r["sentinelClass"]
        for r in records
        if r["phase"] in {"OBSERVATION", "INDEPENDENT_CONTINUATION"}
    }
    if observed != SENTINEL_CLASSES:
        fail("continuity sentinel coverage is incomplete")
    if any(
        r[field] in {"MISMATCH", "UNHEALTHY"}
        for r in records
        for field in (
            "healthClass",
            "pidContinuityClass",
            "startTimeContinuityClass",
            "restartCountClass",
            "listenerProcessContinuityClass",
        )
    ):
        fail("continuity evidence records a service inconsistency")
    return records


def _system_probe(sentinel: dict[str, Any]) -> tuple[str, str, str, str, str]:
    result = subprocess.run(
        [
            "systemctl",
            "show",
            sentinel["serviceUnit"],
            "--property=ActiveState,MainPID,ExecMainStartTimestampMonotonic,NRestarts",
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=5,
    )
    try:
        values = dict(line.split("=", 1) for line in result.stdout.splitlines())
        active = values["ActiveState"]
        pid = values["MainPID"]
        started = values["ExecMainStartTimestampMonotonic"]
        restarts = values["NRestarts"]
    except (KeyError, ValueError):
        return ("UNHEALTHY", "MISMATCH", "MISMATCH", "MISMATCH", "MISMATCH")
    if result.returncode or active != "active" or pid in {"", "0"} or not started:
        return ("UNHEALTHY", "MISMATCH", "MISMATCH", "MISMATCH", "MISMATCH")
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{sentinel['healthPort']}/healthz", timeout=2
        ) as response:
            health = "HEALTHY" if response.status == 200 else "UNHEALTHY"
    except (OSError, urllib.error.URLError):
        health = "UNHEALTHY"
    listener = "NOT_REQUIRED"
    if sentinel["listenerRequired"]:
        check = subprocess.run(
            ["ss", "-ltnH", f"sport = :{sentinel['listenerPort']}"],
            capture_output=True,
            check=False,
            timeout=5,
        )
        listener = (
            "MATCH" if check.returncode == 0 and check.stdout.strip() else "MISMATCH"
        )
    return health, pid, started, restarts, listener


def run_monitor(
    *,
    workspace: Path,
    token: str,
    contract: dict[str, Any],
    evidence_path: Path,
    stop_path: Path,
    probe: Callable[[dict[str, Any]], tuple[str, str, str, str, str]] = _system_probe,
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> None:
    validate_contract(contract)
    own = ownership_digest(workspace, token)
    baseline: dict[str, tuple[str, str, str]] = {}
    previous = "sha256:" + "0" * 64
    sequence = 0
    fd = os.open(
        evidence_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400
    )

    def append(
        sentinel: str,
        phase: str,
        values: tuple[str, str, str, str, str] | None,
        completion: str,
    ) -> None:
        nonlocal previous, sequence
        health, pid_class, start_class, restart_class, listener = (
            values or ("NOT_REQUIRED",) * 5
        )
        record = {
            "schemaVersion": SCHEMA_VERSION,
            "workspaceOwnershipDigest": own,
            "sentinelClass": sentinel,
            "sequence": sequence,
            "phase": phase,
            "healthClass": health,
            "pidContinuityClass": pid_class,
            "startTimeContinuityClass": start_class,
            "restartCountClass": restart_class,
            "listenerProcessContinuityClass": listener,
            "managementChannelObservabilityClass": "NOT_OBSERVED_INDEPENDENTLY",
            "completionState": completion,
            "previousDigest": previous,
            "recordDigest": "",
        }
        record["recordDigest"] = _record_digest(record)
        payload = _canonical_record(record) + b"\n"
        if os.write(fd, payload) != len(payload):
            fail("continuity record append was incomplete")
        os.fsync(fd)
        previous = record["recordDigest"]
        sequence += 1

    try:
        append("MONITOR", "START", None, "RUNNING")
        started_at = monotonic()
        observation = 0
        while (
            monotonic() - started_at <= contract["maximumRuntimeSeconds"]
            and observation < MAX_OBSERVATIONS
        ):
            for sentinel in contract["sentinels"]:
                health, pid, began, restarts, listener = probe(sentinel)
                identity = sentinel["sentinelClass"]
                if identity not in baseline:
                    baseline[identity] = (pid, began, restarts)
                base_pid, base_began, base_restarts = baseline[identity]
                values = (
                    health,
                    "MATCH" if pid == base_pid else "MISMATCH",
                    "MATCH" if began == base_began else "MISMATCH",
                    "MATCH" if restarts == base_restarts else "MISMATCH",
                    listener,
                )
                append(
                    identity,
                    "OBSERVATION" if observation == 0 else "INDEPENDENT_CONTINUATION",
                    values,
                    "RUNNING",
                )
            observation += 1
            if stop_path.exists():
                append("MONITOR", "STOP", None, "STOP_REQUESTED")
                append("MONITOR", "COMPLETE", None, "COMPLETE")
                return
            sleeper(contract["intervalSeconds"])
        append("MONITOR", "STOP", None, "FAILED")
        fail("continuity monitor bounded runtime expired")
    finally:
        os.close(fd)


def _secure_runtime(runtime: Path) -> None:
    st = runtime.lstat()
    if (
        not stat.S_ISDIR(st.st_mode)
        or stat.S_ISLNK(st.st_mode)
        or st.st_uid != os.getuid()
        or stat.S_IMODE(st.st_mode) != 0o700
    ):
        fail("continuity runtime ownership is unsafe")
    if any(runtime.iterdir()):
        fail("continuity runtime must be empty")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--token-fd", required=True, type=int)
    args = parser.parse_args()
    token = os.read(args.token_fd, 512).decode().strip()
    if not token:
        fail("continuity ownership token is absent")
    _secure_runtime(args.runtime)
    contract = json.loads(args.contract.read_bytes())
    run_monitor(
        workspace=args.workspace,
        token=token,
        contract=contract,
        evidence_path=args.runtime / "evidence.jsonl",
        stop_path=args.runtime / "stop",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
