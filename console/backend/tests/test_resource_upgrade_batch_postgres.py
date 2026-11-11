"""Dedicated PostgreSQL receipt/rollback tests with actual capability owner writes.

This is not HTTP authorization or the complete resource/employee publish chain.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from uuid import uuid4

import psycopg
import pytest
from agent_console.business_capability_postgres import (
    PostgresBusinessCapabilityRepository,
)
from agent_console.execution_domain import ScopeIdentity
from agent_console.resource_upgrade_batch_postgres import (
    UpgradeBatchError,
    UpgradeBatchRepository,
)
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from test_business_capability import capability

URL = os.environ.get("UPGRADE_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="Dedicated PostgreSQL required")
MIGRATIONS = Path(__file__).parents[1] / "migrations"


@pytest.fixture
def store():
    with ConnectionPool(URL, kwargs={"row_factory": dict_row}) as pool:
        repo = UpgradeBatchRepository(pool)
        repo.migrate(MIGRATIONS / "0060_resource_upgrade_batch.sql")
        repo.compatibility(MIGRATIONS / "0060_resource_upgrade_batch.sql")
        PostgresBusinessCapabilityRepository(pool).migrate(
            MIGRATIONS / "0052_business_capability.sql"
        )
        yield pool


def fresh():
    return replace(
        capability(), scope=ScopeIdentity("upgrade-" + uuid4().hex, "isolated")
    )


def owner_write(conn, revision):
    return PostgresBusinessCapabilityRepository.save(
        conn,
        revision,
        expected_version=0,
        command_id="cap:command",
        actor_id="human:test",
        decision_id="controlled:decision",
    )


def apply(conn, revision, action, **changes):
    args = dict(
        request={"selected": revision.capability_id},
        reviewed_digest="a" * 64,
        authority_generation=1,
        recovery_epoch=1,
        decision_ids=("controlled:decision",),
        current_preview_digest=lambda: "a" * 64,
        apply_owners=action,
    )
    args.update(changes)
    return UpgradeBatchRepository.apply(
        conn, revision.scope, "human:test", "batch:command", **args
    )


def counts(conn, revision):
    key = (revision.scope.namespace, revision.scope.security_domain)
    return tuple(
        conn.execute(
            "SELECT count(*) n FROM "
            + table
            + " WHERE namespace=%s AND security_domain=%s",
            key,
        ).fetchone()["n"]
        for table in [
            "business_capability.definitions",
            "business_capability.revisions",
            "business_capability.receipts",
            "resource_upgrade.receipts",
        ]
    )


def test_success_replay_restarts_and_isolates_actor_and_scope(store):
    revision = fresh()
    with store.connection() as conn, conn.transaction():
        first = apply(conn, revision, lambda: owner_write(conn, revision))
    with psycopg.connect(URL, row_factory=dict_row) as conn, conn.transaction():
        replay = apply(
            conn,
            revision,
            lambda: pytest.fail("Replay applied owners"),
            current_preview_digest=lambda: pytest.fail("Replay requires old preview"),
        )
        assert replay == {**first, "replayed": True}
        assert counts(conn, revision) == (1, 1, 1, 1)
        assert (
            UpgradeBatchRepository.read(
                conn, revision.scope, "human:test", "batch:command"
            )["state"]
            == "COMMITTED"
        )
        assert UpgradeBatchRepository.read(
            conn, revision.scope, "human:other", "batch:command"
        ) == {"state": "NOT_RECORDED", "safeToReplay": False}
        assert (
            UpgradeBatchRepository.read(
                conn, ScopeIdentity("other", "isolated"), "human:test", "batch:command"
            )["state"]
            == "NOT_RECORDED"
        )


def test_owner_failure_rolls_back_even_if_outer_caller_catches(store):
    revision = fresh()
    with store.connection() as conn, conn.transaction():

        def fail_after_write():
            owner_write(conn, revision)
            raise ValueError("injected next owner rejection")

        with pytest.raises(ValueError, match="injected"):
            apply(conn, revision, fail_after_write)
        assert counts(conn, revision) == (0, 0, 0, 0)
    with store.connection() as conn, conn.transaction():
        assert counts(conn, revision) == (0, 0, 0, 0)


def test_preview_change_prevents_every_owner_write(store):
    revision = fresh()
    with store.connection() as conn, conn.transaction():
        with pytest.raises(UpgradeBatchError, match="PREVIEW_CHANGED"):
            apply(
                conn,
                revision,
                lambda: pytest.fail("Owner called"),
                current_preview_digest=lambda: "b" * 64,
            )
        assert counts(conn, revision) == (0, 0, 0, 0)


def test_changed_command_payload_is_not_replay(store):
    revision = fresh()
    with store.connection() as conn, conn.transaction():
        apply(conn, revision, lambda: owner_write(conn, revision))
    with store.connection() as conn, conn.transaction():
        with pytest.raises(UpgradeBatchError, match="COMMAND_CONFLICT"):
            apply(
                conn,
                revision,
                lambda: pytest.fail("Owner called"),
                request={"selected": "different"},
            )
        assert counts(conn, revision) == (1, 1, 1, 1)


def test_uncommitted_receipt_not_exposed_and_concurrent_duplicate_applies_once(store):
    revision = fresh()
    ready, release, second_started = Event(), Event(), Event()
    calls = []
    second_pid = []

    def write(is_second=False):
        with store.connection() as conn, conn.transaction():
            if is_second:
                second_pid.append(conn.info.backend_pid)
                second_started.set()

            def action():
                calls.append(1)
                result = owner_write(conn, revision)
                ready.set()
                assert release.wait(10)
                return result

            return apply(conn, revision, action)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(write)
        try:
            assert ready.wait(10)
            with store.connection() as conn, conn.transaction():
                assert UpgradeBatchRepository.read(
                    conn, revision.scope, "human:test", "batch:command"
                ) == {"state": "NOT_RECORDED", "safeToReplay": False}
            second = executor.submit(write, True)
            assert second_started.wait(5)
            deadline = monotonic() + 5
            with store.connection() as observer:
                while monotonic() < deadline:
                    waiting = observer.execute(
                        "SELECT 1 FROM pg_locks WHERE pid=%s "
                        "AND locktype='advisory' AND NOT granted",
                        (second_pid[0],),
                    ).fetchone()
                    if waiting:
                        break
                    sleep(0.02)
                else:
                    pytest.fail("Duplicate never overlapped the uncommitted batch")
        finally:
            release.set()
        values = [first.result(10), second.result(10)]
    assert sorted(v["replayed"] for v in values) == [False, True]
    assert calls == [1]


def test_outer_rollback_removes_owner_and_receipt_together(store):
    revision = fresh()
    with store.connection() as conn:
        with pytest.raises(ValueError, match="outer failure"), conn.transaction():
            apply(conn, revision, lambda: owner_write(conn, revision))
            raise ValueError("outer failure")
        with conn.transaction():
            assert counts(conn, revision) == (0, 0, 0, 0)


def test_receipts_are_append_only_and_caller_transaction_is_required(store):
    revision = fresh()
    with store.connection() as conn:
        with pytest.raises(UpgradeBatchError, match="CALLER_TRANSACTION_REQUIRED"):
            apply(conn, revision, lambda: pytest.fail("Owner called"))
        with conn.transaction():
            apply(conn, revision, lambda: owner_write(conn, revision))
        with (
            pytest.raises(psycopg.Error, match="RECEIPT_IMMUTABLE"),
            conn.transaction(),
        ):
            conn.execute(
                "DELETE FROM resource_upgrade.receipts WHERE namespace=%s",
                (revision.scope.namespace,),
            )


@pytest.mark.parametrize("seed", [0, 54])
def test_existing_owner_lock_rejects_batch_before_row_locks(store, seed):
    """An actual competing owner lock must fail fast, not form a lock inversion."""
    import json
    from types import SimpleNamespace

    from agent_console.digital_employee_definition import digest
    from agent_console.resource_upgrade_preview import SelectedUpgradePreview

    scope = fresh().scope
    identity = "employee:locked" if seed == 0 else "capability:locked"
    key = (scope.namespace, scope.security_domain, identity)
    encoded = json.dumps(key) if seed == 0 else digest(key)
    item = SimpleNamespace(original=SimpleNamespace(resource_id=identity))
    selected = SimpleNamespace(
        employees=(item,) if seed == 0 else (),
        capabilities=(item,) if seed == 54 else (),
    )
    with store.connection() as owner, store.connection() as batch:
        with owner.transaction():
            owner.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, %s))",
                (encoded, seed),
            )
            with batch.transaction():
                batch.execute("SET LOCAL statement_timeout = '2s'")
                call = SimpleNamespace(
                    connection=batch,
                    context=SimpleNamespace(
                        scope=SimpleNamespace(
                            tenant_id=scope.namespace,
                            security_domain=scope.security_domain,
                        )
                    ),
                )
                with pytest.raises(
                    UpgradeBatchError, match="UPGRADE_CONCURRENT_CHANGE"
                ):
                    SelectedUpgradePreview._lock(call, selected)
                # No skill row lookup was reached (selected has no new_skill).
                assert batch.execute("SELECT 1 n").fetchone()["n"] == 1
        with batch.transaction():
            assert batch.execute(
                "SELECT pg_try_advisory_xact_lock(hashtextextended(%s, %s)) acquired",
                (encoded, seed),
            ).fetchone()["acquired"]
