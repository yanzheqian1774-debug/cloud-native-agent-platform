"""Guard bounded internal reads; SQL correctness is checked against PostgreSQL."""

from types import SimpleNamespace

import pytest
from agent_console.workbench_current_work_snapshot import (
    MAX_SNAPSHOT_RUNS,
    read_current_work_snapshot,
)
from agent_console.workbench_owner_authorization import WorkbenchOwnerError


class SnapshotConnection:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, sql, params=None):
        if "to_regclass" in sql:
            return SimpleNamespace(fetchone=lambda: {"t": None})
        self.calls.append((sql, params))
        return SimpleNamespace(fetchall=lambda: self.rows)


@pytest.mark.parametrize("size", [0, MAX_SNAPSHOT_RUNS])
def test_complete_snapshot_uses_one_parameterized_statement(size):
    rows = [{"workflow_run_id": str(i)} for i in range(size)]
    connection = SnapshotConnection(rows)
    assert (
        read_current_work_snapshot(
            connection, namespace="tenant'", security_domain="private"
        )
        == rows
    )
    assert len(connection.calls) == 1
    sql, params = connection.calls[0]
    assert params == ("tenant'", "private", MAX_SNAPSHOT_RUNS + 1)
    assert "tenant'" not in sql


def test_capacity_overflow_fails_instead_of_exposing_partial_total():
    connection = SnapshotConnection([{}] * (MAX_SNAPSHOT_RUNS + 1))
    with pytest.raises(
        WorkbenchOwnerError, match="CURRENT_WORK_SNAPSHOT_CAPACITY"
    ) as e:
        read_current_work_snapshot(connection, namespace="tenant", security_domain="p")
    assert e.value.status_code == 503


def test_storage_failure_is_not_an_empty_directory():
    class FailedConnection:
        def execute(self, *_):
            raise RuntimeError("storage unavailable")

    with pytest.raises(RuntimeError, match="storage unavailable"):
        read_current_work_snapshot(
            FailedConnection(), namespace="tenant", security_domain="p"
        )
