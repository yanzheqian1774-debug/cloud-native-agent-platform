"""No terminal snapshot data is consumed before the batch has synchronized."""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from agent_console.prepared_snapshot_reads import basis_rows, output_rows
from psycopg import OperationalError


@pytest.mark.parametrize("basis", [False, True])
@pytest.mark.parametrize("fail", [False, True])
def test_snapshot_batch_sync_failure_never_exposes_partial_data(basis, fail):
    events = []

    class Connection:
        synchronized = False

        @contextmanager
        def pipeline(self):
            yield
            if fail:
                raise OperationalError("database synchronization failed")
            self.synchronized = True
            events.append("sync")

        def execute(self, query, args):
            events.append("read")
            connection = self

            class Cursor:
                def fetchall(self):
                    assert connection.synchronized
                    events.append("fetch")
                    return []

                def fetchone(self):
                    assert connection.synchronized
                    events.append("fetch")
                    return {"high_water": 7}

            return Cursor()

    connection = Connection()

    def read():
        if basis:
            return basis_rows(
                connection,
                ("tenant", "domain"),
                SimpleNamespace(
                    criteria=SimpleNamespace(revision_id="criteria"),
                    problem=SimpleNamespace(resource_id="problem", revision_id="r1"),
                ),
            )
        return output_rows(connection, ("tenant", "domain"), "run")

    if fail:
        with pytest.raises(OperationalError):
            read()
        assert "fetch" not in events
    else:
        read()
        assert events.index("sync") < events.index("fetch")
        assert events.count("read") == events.count("fetch") == (2 if basis else 3)
