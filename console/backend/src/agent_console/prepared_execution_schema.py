"""Additive D324 writer gate; old execution binaries reject version 34."""

import hashlib
from pathlib import Path

from .execution_preparation import ExecutionPreparationError
from .execution_preparation_postgres import PreparedExecutionStore

ADAPTER = "prepared-execution-binding-postgresql-v34"
PATH = Path(__file__).parents[2] / "migrations/0034_prepared_execution_binding.sql"


def expected_version():
    return {
        "version": 34,
        "checksum": hashlib.sha256(PATH.read_bytes()).hexdigest(),
        "adapter": ADAPTER,
    }


def migrate(connection):
    PreparedExecutionStore(connection).migrate()
    connection.execute("SELECT pg_advisory_xact_lock(3240034)")
    newer = connection.execute(
        "SELECT version,checksum,adapter FROM execution_authority.schema_migrations "
        "WHERE version>11 ORDER BY version"
    ).fetchall()
    expected = expected_version()
    if newer:
        if newer != [expected]:
            raise ExecutionPreparationError("PREPARATION_BINDING_SCHEMA_INCOMPATIBLE")
        return
    connection.execute(PATH.read_text())
    connection.execute(
        "INSERT INTO execution_authority.schema_migrations(version,checksum,adapter) "
        "VALUES (%s,%s,%s)",
        (expected["version"], expected["checksum"], expected["adapter"]),
    )


def compatible_versions(rows):
    """The v34 writer accepts only exact known prerequisite revisions."""
    if not rows or rows[-1] != expected_version():
        return False
    from .workflow_control_postgres import ADAPTER as workflow_adapter

    expected = [
        {
            "version": version,
            "checksum": hashlib.sha256(
                next(PATH.parent.glob(f"{version:04d}_*.sql")).read_bytes()
            ).hexdigest(),
            "adapter": workflow_adapter,
        }
        for version in (9, 10, 11)
    ]
    known = {item["version"]: item for item in [*expected, expected_version()]}
    return all(item == known.get(item["version"]) for item in rows)
