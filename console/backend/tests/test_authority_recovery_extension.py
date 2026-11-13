"""Restart with exact recovery extension and historical bootstrap, isolated PG."""

import shutil

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.authority_postgres import PostgresAuthorityRepository
from agent_console.conversation_planning_recovery import migrate
from test_conversation_planning_admission import (  # noqa: F401
    env,
    ordinary,
    pytestmark,
    setup,
)


def historical_bootstrap(e, tmp_path):
    original = e.repo.migration_path
    folder = tmp_path / "old-bootstrap" / "migrations"
    folder.mkdir(parents=True)
    for path in original.parent.glob("*.sql"):
        if not path.name.startswith("0063_"):
            shutil.copyfile(path, folder / path.name)
    e.repo.migration_path = folder / original.name
    assert not (folder / "0063_conversation_planning_recovery.sql").exists()
    return e.repo.migration_path


def test_existing_recovery_migration_allows_verified_restart(ordinary, tmp_path):  # noqa: F811
    e = ordinary
    path = historical_bootstrap(e, tmp_path)
    migrate(e.planning)
    with e.repo.connection_scope() as c:
        before = c.execute(
            "SELECT * FROM authorization_admin.schema_migrations ORDER BY version"
        ).fetchall()
    e.repo.migrate()
    e.repo.verify_existing_schema()
    restarted = PostgresAuthorityRepository(e.repo.pool.conninfo, migration_path=path)
    try:
        restarted.migrate()
        restarted.verify_existing_schema()
        with restarted.connection_scope() as c:
            assert (
                c.execute(
                    "SELECT * FROM authorization_admin.schema_migrations "
                    "ORDER BY version"
                ).fetchall()
                == before
            )
    finally:
        restarted.close()
    assert path == e.repo.migration_path
    assert any(row["version"] == 63 for row in before)


@pytest.mark.parametrize(
    "corruption", ["checksum", "adapter", "unknown-version", "legacy-checksum"]
)
def test_recovery_extension_still_rejects_wrong_or_unknown_schema(
    ordinary,  # noqa: F811
    tmp_path,
    corruption,
):
    e = ordinary
    historical_bootstrap(e, tmp_path)
    migrate(e.planning)
    with e.repo.connection_scope() as c:
        if corruption == "unknown-version":
            c.execute(
                "INSERT INTO authorization_admin.schema_migrations "
                "(version,checksum,adapter) VALUES(64,%s,'unknown')",
                ("f" * 64,),
            )
        elif corruption == "legacy-checksum":
            c.execute(
                "UPDATE authorization_admin.schema_migrations "
                "SET checksum=%s WHERE version=28",
                ("f" * 64,),
            )
        elif corruption == "checksum":
            c.execute(
                "UPDATE authorization_admin.schema_migrations "
                "SET checksum=%s WHERE version=63",
                ("f" * 64,),
            )
        else:
            c.execute(
                "UPDATE authorization_admin.schema_migrations "
                "SET adapter='unrecognized' WHERE version=63"
            )
    for check in (e.repo.migrate, e.repo.verify_existing_schema):
        with pytest.raises(AuthorityError, match="AUTHORITY_SCHEMA_INCOMPATIBLE"):
            check()
