from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
MODULE = ROOT / "scripts/acceptance/continuity_monitor.py"
SPEC = importlib.util.spec_from_file_location("continuity_monitor_test", MODULE)
assert SPEC and SPEC.loader
monitor = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = monitor
SPEC.loader.exec_module(monitor)


def contract() -> dict:
    return {
        "contractVersion": "SERVER_LOCAL_CONTINUITY_V1",
        "intervalSeconds": 1,
        "maximumRuntimeSeconds": 30,
        "sentinels": [
            {
                "sentinelClass": "PUBLIC",
                "serviceUnit": "public.service",
                "healthPort": 8000,
                "listenerPort": 8000,
                "listenerRequired": True,
            },
            {
                "sentinelClass": "ORIGINAL_STAGING",
                "serviceUnit": "staging.service",
                "healthPort": 18000,
                "listenerPort": 18000,
                "listenerRequired": True,
            },
        ],
    }


def healthy(_sentinel: dict) -> tuple[str, str, str, str, str]:
    return ("HEALTHY", "opaque-pid", "opaque-start", "0", "MATCH")


def evidence(tmp_path: Path, probe=healthy) -> tuple[bytes, str]:
    stop = tmp_path / "stop"
    ticks = iter((0.0, 0.0, 1.0, 2.0, 3.0))

    def sleep(_seconds: float) -> None:
        stop.touch()

    monitor.run_monitor(
        workspace=ROOT,
        token="unpredictable-owned-token",
        contract=contract(),
        evidence_path=tmp_path / "evidence.jsonl",
        stop_path=stop,
        probe=probe,
        monotonic=lambda: next(ticks),
        sleeper=sleep,
    )
    data = (tmp_path / "evidence.jsonl").read_bytes()
    ownership = monitor.ownership_digest(ROOT, "unpredictable-owned-token")
    return data, ownership


def test_uninterrupted_and_management_independent_continuation_validates(
    tmp_path: Path,
) -> None:
    data, ownership = evidence(tmp_path)
    records = monitor.validate_evidence(data, expected_ownership_digest=ownership)
    assert {record["sentinelClass"] for record in records} >= {
        "PUBLIC",
        "ORIGINAL_STAGING",
    }
    assert any(record["phase"] == "INDEPENDENT_CONTINUATION" for record in records)
    assert records[-1]["completionState"] == "COMPLETE"
    prohibited = {"pid", "startTime", "endpoint", "url", "responseBody", "traceback"}
    assert not prohibited.intersection({key for record in records for key in record})


@pytest.mark.parametrize(
    "field,index,value",
    [
        ("sequence", 1, 9),
        ("recordDigest", 1, "sha256:" + "0" * 64),
        ("sentinelClass", 1, "FOREIGN"),
        ("workspaceOwnershipDigest", 1, "sha256:" + "0" * 64),
    ],
)
def test_gap_tamper_identity_and_ownership_fail_closed(
    tmp_path: Path, field: str, index: int, value: object
) -> None:
    data, ownership = evidence(tmp_path)
    records = [json.loads(line) for line in data.splitlines()]
    records[index][field] = value
    altered = (
        b"\n".join(json.dumps(row, separators=(",", ":")).encode() for row in records)
        + b"\n"
    )
    with pytest.raises(monitor.MonitorError):
        monitor.validate_evidence(altered, expected_ownership_digest=ownership)


def test_duplicate_missing_reordered_extra_and_incomplete_records_fail_closed(
    tmp_path: Path,
) -> None:
    data, ownership = evidence(tmp_path)
    records = [json.loads(line) for line in data.splitlines()]
    variants = [
        [*records, records[1]],
        records[:1] + records[2:],
        list(reversed(records)),
        [{**records[0], "rawPid": 42}, *records[1:]],
        records[:-1],
    ]
    for rows in variants:
        encoded = b"\n".join(json.dumps(row).encode() for row in rows) + b"\n"
        with pytest.raises(monitor.MonitorError):
            monitor.validate_evidence(encoded, expected_ownership_digest=ownership)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(sentinels=[]),
        lambda value: value["sentinels"][0].update(sentinelClass="UNAPPROVED"),
        lambda value: value["sentinels"][0].update(endpoint="http://example.invalid"),
        lambda value: value.update(intervalSeconds=0),
        lambda value: value.update(maximumRuntimeSeconds=21601),
    ],
)
def test_contract_missing_unapproved_disclosing_malformed_or_unbounded_fails(
    mutation,
) -> None:
    value = copy.deepcopy(contract())
    mutation(value)
    with pytest.raises(monitor.MonitorError):
        monitor.validate_contract(value)


def test_runtime_rejects_nonempty_symlink_and_wrong_mode(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    monitor._secure_runtime(runtime)
    (runtime / "foreign").touch()
    with pytest.raises(monitor.MonitorError):
        monitor._secure_runtime(runtime)
    runtime_link = tmp_path / "runtime-link"
    runtime_link.symlink_to(runtime)
    with pytest.raises(monitor.MonitorError):
        monitor._secure_runtime(runtime_link)
    (runtime / "foreign").unlink()
    runtime.chmod(0o755)
    with pytest.raises(monitor.MonitorError):
        monitor._secure_runtime(runtime)


@pytest.mark.parametrize("position", [0, 1, 2, 3, 4])
def test_each_service_continuity_failure_fails_validation(
    tmp_path: Path, position: int
) -> None:
    values = ["HEALTHY", "opaque-pid", "opaque-start", "0", "MATCH"]
    calls = 0

    def changed(_sentinel: dict) -> tuple[str, str, str, str, str]:
        nonlocal calls
        calls += 1
        result = values.copy()
        if calls > 2:
            result[position] = (
                "UNHEALTHY"
                if position == 0
                else ("MISMATCH" if position == 4 else "changed")
            )
        return tuple(result)  # type: ignore[return-value]

    data, ownership = evidence(tmp_path, changed)
    with pytest.raises(monitor.MonitorError, match="service inconsistency"):
        monitor.validate_evidence(data, expected_ownership_digest=ownership)
