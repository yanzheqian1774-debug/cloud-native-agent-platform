# ruff: noqa: E501 -- Exact scoped SQL owner keys.
"""Explicit migration, never implicit app startup or authority ledger mutation."""

from hashlib import sha256
from pathlib import Path

from .postgres_schema_compatibility import (
    LEDGER_COLUMNS,
    Table,
    columns,
    foreign,
    primary,
    schema_is_compatible,
    unique,
)
from .workbench_owner_authorization import WorkbenchOwnerError

MIGRATION = Path(__file__).parents[2] / "migrations/0069_fixed_work_triggers.sql"


STRUCTURE = (
    Table(
        "fixed_work_triggers.schema_migrations", LEDGER_COLUMNS, (primary("version"),)
    ),
    Table(
        "fixed_work_triggers.receipts",
        columns(
            *(
                (key, "text")
                for key in (
                    "namespace",
                    "security_domain",
                    "actor_id",
                    "event_id",
                    "work_id",
                    "revision_id",
                    "work_digest",
                    "preparation_digest",
                    "payload_digest",
                    "policy_digest",
                    "workflow_run_id",
                    "start_command_key",
                )
            ),
            ("recorded_at", "timestamp with time zone"),
        ),
        (
            primary("namespace", "security_domain", "actor_id", "event_id"),
            unique("namespace", "security_domain", "preparation_digest"),
            foreign(
                ("namespace", "security_domain", "work_id", "revision_id"),
                "fixed_work_authoring.revisions",
                ("namespace", "security_domain", "work_id", "revision_id"),
            ),
            foreign(
                ("namespace", "security_domain", "workflow_run_id"),
                "execution_authority.workflow_runs",
                ("namespace", "security_domain", "workflow_run_id"),
            ),
        ),
        ("immutable_receipts",),
    ),
)


def compatible(c):
    if not c.execute(
        "SELECT to_regclass('fixed_work_triggers.schema_migrations') AS name"
    ).fetchone()["name"]:
        raise WorkbenchOwnerError("FIXED_WORK_TRIGGER_SCHEMA_UNAVAILABLE", 503)
    rows = c.execute(
        "SELECT version,checksum,adapter FROM fixed_work_triggers.schema_migrations ORDER BY version"
    ).fetchall()
    if not schema_is_compatible(c, STRUCTURE) or rows != [
        {
            "version": 69,
            "checksum": sha256(MIGRATION.read_bytes()).hexdigest(),
            "adapter": "fixed-work-one-use-v1",
        }
    ]:
        raise WorkbenchOwnerError("FIXED_WORK_TRIGGER_SCHEMA_INCOMPATIBLE", 503)


def migrate(c):
    c.execute("SELECT pg_advisory_xact_lock(3240069)")
    if c.execute(
        "SELECT to_regclass('fixed_work_triggers.schema_migrations') AS name"
    ).fetchone()["name"]:
        compatible(c)
        return
    c.execute(MIGRATION.read_text())
    c.execute(
        "INSERT INTO fixed_work_triggers.schema_migrations VALUES(69,%s,'fixed-work-one-use-v1')",
        (sha256(MIGRATION.read_bytes()).hexdigest(),),
    )
