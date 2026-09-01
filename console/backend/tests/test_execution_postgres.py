import os
from pathlib import Path

import psycopg
import pytest
from agent_console.execution_domain import ExecutionSchemaIncompatible
from agent_console.execution_postgres import (
    ADAPTER,
    PostgresExecutionAuthorityRepository,
)

DATABASE_URL = os.environ.get("EXECUTION_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL 15 required")
MIGRATIONS = Path(__file__).parents[1] / "migrations"
MIGRATION = MIGRATIONS / "0008_execution_runtime_authority.sql"


def apply_chain() -> None:
    with psycopg.connect(DATABASE_URL or "") as connection:
        for version in range(1, 8):
            connection.execute(
                next(MIGRATIONS.glob(f"{version:04d}_*.sql")).read_text()
            )


def test_clean_migration_0001_through_0008_and_checksum() -> None:
    apply_chain()
    repository = PostgresExecutionAuthorityRepository(
        DATABASE_URL or "", migration_path=MIGRATION
    )
    repository.migrate()
    repository.compatibility()
    assert len(repository.migration_checksum) == 64
    with repository.pool.connection() as connection:
        row = connection.execute(
            "SELECT checksum,adapter FROM execution_authority.schema_migrations "
            "WHERE version=8"
        ).fetchone()
    assert row == {"checksum": repository.migration_checksum, "adapter": ADAPTER}
    repository.pool.close()


def test_newer_and_partial_schema_fail_closed() -> None:
    repository = PostgresExecutionAuthorityRepository(
        DATABASE_URL or "", migration_path=MIGRATION
    )
    repository.migrate()
    with repository.pool.connection() as connection, connection.transaction():
        connection.execute(
            "INSERT INTO execution_authority.schema_migrations"
            "(version,checksum,adapter) VALUES (9,%s,%s) "
            "ON CONFLICT DO NOTHING",
            ("f" * 64, ADAPTER),
        )
    with pytest.raises(ExecutionSchemaIncompatible):
        repository.compatibility()
    with repository.pool.connection() as connection, connection.transaction():
        connection.execute(
            "DELETE FROM execution_authority.schema_migrations WHERE version=9"
        )
        connection.execute(
            "DELETE FROM execution_authority.schema_migrations WHERE version=8"
        )
    with pytest.raises(ExecutionSchemaIncompatible):
        repository.compatibility()
    repository.migrate()
    with repository.pool.connection() as connection, connection.transaction():
        connection.execute(
            "UPDATE execution_authority.schema_migrations SET checksum=%s "
            "WHERE version=8",
            ("0" * 64,),
        )
    with pytest.raises(ExecutionSchemaIncompatible):
        repository.compatibility()
    with repository.pool.connection() as connection, connection.transaction():
        connection.execute(
            "UPDATE execution_authority.schema_migrations SET checksum=%s "
            "WHERE version=8",
            (repository.migration_checksum,),
        )
    repository.pool.close()
