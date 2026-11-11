from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from agent_console.authority_contracts import (
    AuthorityError,
    DynamicAuthorizationState,
    ExactGrant,
)
from agent_console.authority_postgres import PostgresAuthorityRepository
from psycopg import OperationalError
from test_workbench_pagination import context


@pytest.mark.parametrize("fail", [False, True])
def test_bundle_states_wait_for_sync_and_fail_before_fallback(monkeypatch, fail):
    from agent_console import task_delegation, task_identity_continuity

    repository = object.__new__(PostgresAuthorityRepository)
    events = []
    now = datetime.now(UTC)
    rows = [
        {
            "generation": 1,
            "recovery_epoch": 1,
            "latest_grant": now,
            "latest_revocation": None,
        },
        {
            "generation": 1,
            "recovery_epoch": 1,
            "latest_grant": now,
            "latest_revocation": now + timedelta(seconds=1),
        },
        {
            "generation": 1,
            "recovery_epoch": 1,
            "latest_grant": None,
            "latest_revocation": None,
        },
        {
            "generation": 2,
            "recovery_epoch": 1,
            "latest_grant": now,
            "latest_revocation": None,
        },
    ]

    class Connection:
        synced = False

        @contextmanager
        def pipeline(self):
            events.append("pipeline")
            yield
            if fail:
                raise OperationalError("transport unavailable")
            self.synced = True
            events.append("sync")

    connection = Connection()
    monkeypatch.setattr(
        task_identity_continuity,
        "lock_owner_generation",
        lambda c: events.append("generation-lock"),
    )
    monkeypatch.setattr(task_delegation, "grant_condition", lambda *a: "")
    monkeypatch.setattr(
        repository, "_current_credential_id", lambda *a, **kw: "credential"
    )
    monkeypatch.setattr(
        repository, "_lock_dynamic_grants", lambda *a: events.append("grant-locks")
    )
    monkeypatch.setattr(
        repository,
        "_authorization_grants_locked_checkpoint",
        lambda: events.append("locked"),
    )

    def cursor(c, ctx, grant, **kwargs):
        events.append(grant.exact_resource)

        class Cursor:
            def fetchone(self):
                assert c.synced
                return rows[int(grant.exact_resource)]

        return Cursor()

    monkeypatch.setattr(repository, "_dynamic_authorization_cursor", cursor)
    monkeypatch.setattr(
        repository, "_bounded_task_decision", lambda *a, **kw: events.append("fallback")
    )
    grants = tuple(ExactGrant("EXECUTION", "READ", str(i)) for i in range(4))

    def read():
        return repository.read_linearized_authorization_states(
            context(),
            grants,
            now=now,
            generation=1,
            recovery_epoch=1,
            connection=connection,
            configure_transaction=False,
        )

    if fail:
        with pytest.raises(AuthorityError, match="AUTHORITY_STORAGE_UNAVAILABLE"):
            read()
        assert "fallback" not in events
    else:
        credential, states = read()
        assert credential == "credential"
        assert states == (
            DynamicAuthorizationState.ALLOWED,
            DynamicAuthorizationState.REVOKED,
            DynamicAuthorizationState.NONE,
            DynamicAuthorizationState.UNAVAILABLE,
        )
        assert events == [
            "generation-lock",
            "grant-locks",
            "locked",
            "pipeline",
            "0",
            "1",
            "2",
            "3",
            "sync",
            *(["fallback"] * 4),
        ]
