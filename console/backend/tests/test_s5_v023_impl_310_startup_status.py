from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("s5_v023_impl_310_startup_status.py")
SPEC = importlib.util.spec_from_file_location("s5_310_startup_status", MODULE_PATH)
assert SPEC and SPEC.loader
STATUS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = STATUS
SPEC.loader.exec_module(STATUS)


def test_status_records_only_bounded_stage_and_failure_classification(tmp_path) -> None:
    path = tmp_path / "startup.json"
    status = STATUS.BoundedStartupStatus(path)
    status.begin("DATABASE_CONNECTION")
    initial = json.loads(path.read_text())
    assert initial == {
        "schemaVersion": "s5-v023-impl-310-fixture-startup.v1",
        "state": "STARTING",
        "lastStartedStage": "DATABASE_CONNECTION",
        "lastCompletedStage": "NONE",
        "exceptionCategory": "NONE",
        "reasonCode": "NONE",
    }

    secret = "postgresql://operator:secret@database/session-token"
    try:
        raise RuntimeError(secret)
    except RuntimeError as error:
        status.fail(error)
    failed = json.loads(path.read_text())
    assert failed["state"] == "FAILED"
    assert failed["exceptionCategory"] == "UNKNOWN"
    assert failed["reasonCode"] == "DATABASE_CONNECTION_FAILED"
    assert secret not in path.read_text()


def test_status_reaches_ready_only_after_every_ordered_stage(tmp_path) -> None:
    path = tmp_path / "startup.json"
    status = STATUS.BoundedStartupStatus(path)
    for stage in STATUS.STARTUP_STAGES:
        status.begin(stage)
        status.complete(stage)
    ready = json.loads(path.read_text())
    assert ready["state"] == "READY"
    assert ready["lastStartedStage"] == "LISTENER_READINESS"
    assert ready["lastCompletedStage"] == "LISTENER_READINESS"
    assert ready["exceptionCategory"] == "NONE"
    assert ready["reasonCode"] == "NONE"
