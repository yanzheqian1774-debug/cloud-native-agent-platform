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

SERVER_PATH = Path(__file__).with_name("s5_v023_impl_310_real_browser_server.py")
SERVER_SPEC = importlib.util.spec_from_file_location("s5_310_server", SERVER_PATH)
assert SERVER_SPEC and SERVER_SPEC.loader
SERVER = importlib.util.module_from_spec(SERVER_SPEC)
sys.modules[SERVER_SPEC.name] = SERVER
sys.path.insert(0, str(SERVER_PATH.parent))
try:
    SERVER_SPEC.loader.exec_module(SERVER)
finally:
    sys.path.pop(0)


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


def test_prerequisite_migrations_use_exact_order_and_transaction_boundaries(
    monkeypatch,
) -> None:
    statements: list[str] = []
    transactions: list[str] = []

    class Connection:
        def __enter__(self):
            transactions.append("BEGIN")
            return self

        def __exit__(self, error_type, _error, _traceback):
            transactions.append("COMMIT" if error_type is None else "ROLLBACK")

        def execute(self, statement: str) -> None:
            statements.append(statement)

    connections: list[str] = []

    def connect(database_url: str) -> Connection:
        connections.append(database_url)
        return Connection()

    monkeypatch.setattr(SERVER.psycopg, "connect", connect)
    SERVER.apply_prerequisite_migrations(
        "postgresql://fixture", SERVER.AGENT_PREREQUISITE_MIGRATIONS
    )
    SERVER.apply_prerequisite_migrations(
        "postgresql://fixture", SERVER.WORKFLOW_PREREQUISITE_MIGRATIONS
    )

    assert connections == ["postgresql://fixture", "postgresql://fixture"]
    assert transactions == ["BEGIN", "COMMIT", "BEGIN", "COMMIT"]
    assert statements == [
        (
            SERVER.MIGRATIONS
            / next(SERVER.MIGRATIONS.glob(f"{version:04d}_*.sql")).name
        ).read_text()
        for version in (1, 2, 3, 4, 5, 7)
    ]
