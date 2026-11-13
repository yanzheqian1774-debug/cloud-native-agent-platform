"""Package-relative recovery migration; no deployed database or runtime changes."""

from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest
from agent_console import conversation_planning_recovery as recovery


@pytest.mark.parametrize("relocated", [False, True])
def test_current_package_migration_ignores_historical_bootstrap(
    tmp_path, monkeypatch, relocated
):
    current_source = Path(recovery.__file__)
    sql = (
        current_source.resolve().parents[2]
        / "migrations"
        / "0063_conversation_planning_recovery.sql"
    ).read_bytes()
    if relocated:
        backend = tmp_path / "installed" / "console" / "backend"
        module = backend / "src" / "agent_console" / current_source.name
        module.parent.mkdir(parents=True)
        module.write_text("# installed module location fixture\n")
        migration = backend / "migrations" / "0063_conversation_planning_recovery.sql"
        migration.parent.mkdir(parents=True)
        migration.write_bytes(sql)
        monkeypatch.setattr(recovery, "__file__", str(module))
    historical = (
        tmp_path / "old-platform-alignment" / "migrations" / "0018_authority.sql"
    )
    historical.parent.mkdir(parents=True)
    historical.write_text("-- historical authority bootstrap, intentionally retained\n")
    # Deliberately no 0063 alongside the historical runtime migrationPath.
    statements = []

    class Connection:
        def execute(self, statement, parameters=None):
            statements.append((statement, parameters))
            return self

        def fetchone(self):
            return None

    @contextmanager
    def connection_scope():
        yield Connection()

    repository = SimpleNamespace(
        migration_path=historical, connection_scope=connection_scope
    )
    recovery.migrate(SimpleNamespace(repository=repository))
    assert repository.migration_path == historical
    assert historical.read_text().startswith("-- historical authority bootstrap")
    assert any(statement == sql.decode() for statement, _ in statements)
    assert statements[-1][1] == (sha256(sql).hexdigest(),)
    assert "VALUES(63," in statements[-1][0]
