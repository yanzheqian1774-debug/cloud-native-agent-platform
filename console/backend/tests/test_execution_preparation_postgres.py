"""Real PG tests; all records are isolated synthetic fixtures, not admission proof."""

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from agent_console.execution_preparation import (
    ArtifactDocument,
    ExecutionPreparationError,
    ProgressEvent,
)
from agent_console.execution_preparation_postgres import PreparedExecutionStore
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from test_execution_preparation import preparation

URL = os.environ.get("PREPARED_EXECUTION_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="isolated real PostgreSQL required")
MIGRATIONS = Path(__file__).parents[1] / "migrations"


@pytest.fixture
def isolated_database(monkeypatch):
    database = "prepared324_" + uuid4().hex
    with psycopg.connect(URL, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        monkeypatch.setattr(
            __import__(__name__), "URL", URL.rsplit("/", 1)[0] + "/" + database
        )
        try:
            yield
        finally:
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))


@pytest.fixture
def prepared(isolated_database):
    p = preparation().model_copy(update={"namespace": "test-" + uuid4().hex})
    key = (p.namespace, p.security_domain)
    with psycopg.connect(URL, row_factory=dict_row) as conn:
        # Baseline canonical schema; no fixture grants/approvals are installed.
        conn.execute((MIGRATIONS / "0008_execution_runtime_authority.sql").read_text())
        PreparedExecutionStore(conn).migrate()
        conn.execute(
            "INSERT INTO execution_authority.digital_employee_instances "
            "(namespace,security_domain,digital_employee_instance_id,"
            "definition_revision_id,aggregate_version,record) "
            "VALUES (%s,%s,%s,%s,1,%s)",
            (*key, p.root_instance_id, "fixture", Jsonb({})),
        )
        conn.execute(
            "INSERT INTO execution_authority.assignments VALUES (%s,%s,%s,%s,%s,%s)",
            (*key, p.root_assignment_id, p.root_instance_id, "a" * 64, Jsonb({})),
        )
        conn.execute(
            "INSERT INTO execution_authority.workflow_runs "
            "(namespace,security_domain,workflow_run_id,assignment_id,"
            "approved_plan_revision_id,record) VALUES (%s,%s,%s,%s,%s,%s)",
            (*key, p.run_id, p.root_assignment_id, "fixture-plan", Jsonb({})),
        )
        for task in p.semantics.tasks:
            conn.execute(
                "INSERT INTO execution_authority.task_runs VALUES (%s,%s,%s,%s,%s)",
                (*key, task.task_id, p.run_id, Jsonb({})),
            )
            for ordinal in (1, 2):
                conn.execute(
                    "INSERT INTO execution_authority.attempts "
                    "(namespace,security_domain,attempt_id,task_run_id,"
                    "aggregate_digest,record) VALUES (%s,%s,%s,%s,%s,%s)",
                    (
                        *key,
                        f"{task.task_id}:{ordinal}",
                        task.task_id,
                        "a" * 64,
                        Jsonb({}),
                    ),
                )
        store = PreparedExecutionStore(conn)
        store.attach(p)
        emit(store, p, "QUEUE")
        emit(store, p, "STARTED")
    return p


def emit(store, p, action, attempt="t1-read:1", artifacts=(), event_id=None):
    key = (p.namespace, p.security_domain, p.run_id)
    state = store.read(*key)[1]
    return store.apply(
        *key,
        ProgressEvent(
            action=action,
            task_id="t1-read",
            attempt_id=attempt,
            artifact_ids=artifacts,
            evidence_id=event_id or uuid4().hex,
        ),
        expected_version=state.version,
    )


def artifact(number, attempt="t1-read:1", size=1, task="t1-read"):
    content = "x" * size
    return ArtifactDocument(
        artifact_id=f"artifact:{number}",
        task_id=task,
        attempt_id=attempt,
        kind="SOURCE_SNAPSHOT",
        schema_version="synthetic.v1",
        content=content,
        digest=hashlib.sha256(content.encode()).hexdigest(),
    )


def append(p, a):
    with psycopg.connect(URL) as conn:
        PreparedExecutionStore(conn).append_artifact(
            p.namespace,
            p.security_domain,
            p.run_id,
            a,
        )


def test_concurrent_count_limit_and_retry_history(prepared):
    p = prepared
    for i in range(15):
        append(p, artifact(i))
    with psycopg.connect(URL) as conn:
        store = PreparedExecutionStore(conn)
        emit(store, p, "FAILED")
        emit(store, p, "RETRY", attempt="t1-read:2")
        emit(store, p, "STARTED", attempt="t1-read:2")

    def writer(i):
        try:
            append(p, artifact(i, attempt="t1-read:2"))
            return "inserted"
        except psycopg.errors.RaiseException as exc:
            assert "ARTIFACT_HISTORY_CAPACITY_EXCEEDED" in str(exc)
            return "bounded"

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(writer, range(15, 23)))
    assert results.count("inserted") == 1
    assert results.count("bounded") == 7
    # Exact replay of prior Attempt output succeeds even after its failure.
    append(p, artifact(0))
    with pytest.raises(ExecutionPreparationError, match="REPLAY_CONFLICT"):
        append(p, artifact(0, size=2))


def test_run_bytes_are_atomic_across_different_tasks(prepared):
    p = prepared
    key = (p.namespace, p.security_domain, p.run_id)

    # Exercise the DB invariant directly, including writers outside the adapter.
    def writer(i):
        task = p.semantics.tasks[i % 6].task_id
        a = artifact(i, attempt=task + ":1", task=task, size=256 * 1024)
        try:
            with psycopg.connect(URL) as conn:
                conn.execute(
                    "INSERT INTO execution_authority.run_artifacts "
                    "(namespace,security_domain,workflow_run_id,artifact_id,"
                    "task_id,attempt_id,digest,content,record) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        *key,
                        a.artifact_id,
                        a.task_id,
                        a.attempt_id,
                        a.digest,
                        a.content,
                        Jsonb(a.model_dump(mode="json")),
                    ),
                )
            return "inserted"
        except psycopg.errors.RaiseException as exc:
            assert "ARTIFACT_HISTORY_CAPACITY_EXCEEDED" in str(exc)
            return "bounded"

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(writer, range(24)))
    assert results.count("inserted") == 16
    assert results.count("bounded") == 8
    with psycopg.connect(URL) as conn:
        assert (
            conn.execute(
                "SELECT sum(byte_size) FROM execution_authority.run_artifacts "
                "WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s",
                key,
            ).fetchone()[0]
            == 4 * 1024 * 1024
        )
        with pytest.raises(psycopg.errors.RaiseException, match="HISTORY_IMMUTABLE"):
            conn.execute(
                "DELETE FROM execution_authority.run_artifacts WHERE namespace=%s",
                (p.namespace,),
            )


def test_event_replay_cas_outputs_and_cancel_survive_reconnect(prepared):
    p = prepared
    key = (p.namespace, p.security_domain, p.run_id)
    with psycopg.connect(URL) as conn:
        store = PreparedExecutionStore(conn)
        with pytest.raises(ExecutionPreparationError, match="ARTIFACT_MISSING"):
            emit(store, p, "SUCCEEDED", artifacts=("missing",))
        result = emit(store, p, "REQUEST_CANCEL", event_id="cancel-request")
        event = ProgressEvent(
            action="REQUEST_CANCEL",
            task_id="t1-read",
            attempt_id="t1-read:1",
            evidence_id="cancel-request",
        )
        assert store.apply(*key, event, expected_version=1) == result
        with pytest.raises(ExecutionPreparationError, match="VERSION_CONFLICT"):
            store.apply(
                *key,
                event.model_copy(update={"evidence_id": "different"}),
                expected_version=1,
            )
    with psycopg.connect(URL) as conn:
        store = PreparedExecutionStore(conn)
        assert store.read(*key)[1].state == "CANCEL_REQUESTED"
        state = emit(store, p, "STOP_CONFIRMED", event_id="actual-stop")
        assert state.state == "CANCELLED"
        assert state.cancellation_request_id == "cancel-request"
        assert state.tasks[0].stop_evidence == "actual-stop"
    with psycopg.connect(URL) as conn:
        store = PreparedExecutionStore(conn)
        assert store.read(*key)[1].state == "CANCELLED"
        with pytest.raises(ExecutionPreparationError, match="TERMINAL_IMMUTABLE"):
            emit(store, p, "RETRY")


def test_migration_replay_and_checksum_drift_fail_closed(prepared):
    with psycopg.connect(URL) as conn:
        store = PreparedExecutionStore(conn)
        store.migrate()
        conn.execute(
            "UPDATE execution_authority.preparation_migrations SET checksum=%s",
            ("0" * 64,),
        )
        with pytest.raises(ExecutionPreparationError, match="SCHEMA_INCOMPATIBLE"):
            store.migrate()
        conn.rollback()
