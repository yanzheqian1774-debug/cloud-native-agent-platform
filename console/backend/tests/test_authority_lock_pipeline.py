from contextlib import contextmanager

import pytest
from agent_console.authority_contracts import ExactGrant
from agent_console.authority_postgres import PostgresAuthorityRepository
from test_workbench_pagination import context


class Connection:
    def __init__(self, *, available=True, fail=False):
        self.available = available
        self.fail = fail
        self.events = []
        self.sync = False

    @contextmanager
    def pipeline(self):
        self.events.append("begin")
        yield
        if self.fail:
            raise RuntimeError("synchronization failed")
        self.sync = True
        self.events.append("sync")

    def execute(self, sql, params=None):
        if "to_regclass" in sql:
            self.events.append("schema")
            return type(
                "Schema",
                (),
                {"fetchone": lambda _: {"name": "table" if self.available else None}},
            )()
        kind = "delegation" if "task_delegation_control" in sql else "grant"
        self.events.append((kind, params[-1]))
        connection = self

        class Cursor:
            def fetchall(self):
                assert connection.sync, "Read lock results before synchronization"
                connection.events.append("fetch")
                return []

        return Cursor()


@pytest.mark.parametrize("available", [True, False])
def test_lock_pipeline_preserves_order_and_waits_for_all_results(available):
    connection = Connection(available=available)
    grants = [
        ExactGrant("EXECUTION", "READ", "first"),
        ExactGrant("EXECUTION", "READ", "second"),
    ]
    PostgresAuthorityRepository._lock_dynamic_grants(connection, context(), grants)
    locks = (
        [
            ("delegation", "first"),
            ("grant", "first"),
            ("delegation", "second"),
            ("grant", "second"),
        ]
        if available
        else [("grant", "first"), ("grant", "second")]
    )
    assert connection.events == [
        "schema",
        "begin",
        *locks,
        "sync",
        *(["fetch"] * len(locks)),
    ]


def test_lock_pipeline_failure_cannot_return_success():
    connection = Connection(fail=True)
    with pytest.raises(RuntimeError, match="synchronization failed"):
        PostgresAuthorityRepository._lock_dynamic_grants(
            connection, context(), [ExactGrant("EXECUTION", "READ", "one")]
        )
    assert "fetch" not in connection.events
