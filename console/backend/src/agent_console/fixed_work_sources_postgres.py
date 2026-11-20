"""Internal source facts, caller transaction; no service authority or model writes."""

import hashlib
from pathlib import Path

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from .business_problem_domain import canonical_digest as digest
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

MIGRATION = Path(__file__).parents[2] / "migrations/0073_fixed_work_sources.sql"

KEY = ("namespace", "security_domain", "work_id", "revision_id")
STRUCTURE = (
    Table(
        "fixed_work_sources.schema_migrations", LEDGER_COLUMNS, (primary("version"),)
    ),
    *(
        Table(
            "fixed_work_sources." + table,
            columns(
                *(
                    (name, "text")
                    for name in (
                        *KEY,
                        "subject_id",
                        "conversation_id",
                        "command_id",
                        "digest",
                    )
                ),
                ("record", "jsonb"),
            ),
            (
                primary(*KEY),
                unique("namespace", "security_domain", "subject_id", "command_id"),
                foreign(
                    KEY,
                    "fixed_work_authoring.revisions"
                    if table == "handoffs"
                    else "fixed_work_sources.handoffs",
                    KEY,
                ),
            )
            + (
                (unique("namespace", "security_domain", "conversation_id"),)
                if table == "handoffs"
                else ()
            ),
            ("immutable_fixed_work_" + table,),
        )
        for table in ("handoffs", "bindings")
    ),
)


def require(ok, reason):
    if not ok:
        raise WorkbenchOwnerError("FIXED_WORK_SOURCE_" + reason, 409)


def compatible(c):
    row = c.execute(
        "SELECT version,checksum,adapter FROM fixed_work_sources.schema_migrations"
    ).fetchall()
    require(
        row
        == [
            dict(
                version=73,
                checksum=hashlib.sha256(MIGRATION.read_bytes()).hexdigest(),
                adapter="fixed-work-source-v1",
            )
        ]
        and schema_is_compatible(c, STRUCTURE),
        "SCHEMA_INCOMPATIBLE",
    )


def migrate(c):
    c.execute("SELECT pg_advisory_xact_lock(2760073)")
    if (
        c.execute(
            "SELECT to_regclass('fixed_work_sources.schema_migrations') name"
        ).fetchone()["name"]
        is None
    ):
        c.execute(MIGRATION.read_text())
        c.execute(
            "INSERT INTO fixed_work_sources.schema_migrations VALUES(73,%s,%s)",
            (
                hashlib.sha256(MIGRATION.read_bytes()).hexdigest(),
                "fixed-work-source-v1",
            ),
        )
    compatible(c)


def read(c, scope, table, work_id, revision_id):
    require(table in {"handoffs", "bindings"}, "TABLE_INVALID")
    row = c.execute(
        "SELECT record,digest FROM fixed_work_sources."
        + table
        + " WHERE namespace=%s AND security_domain=%s AND work_id=%s AND "
        "revision_id=%s",
        (*scope, work_id, revision_id),
    ).fetchone()
    if row:
        require(digest(row["record"]) == row["digest"], "RECORD_INVALID")
    return row


def append(c, scope, table, value):
    old = read(
        c, scope, table, value["work"]["resource_id"], value["work"]["revision_id"]
    )
    if old:
        require(old["record"] == value, "CONFLICT")
        return old
    hashed = digest(value)
    try:
        c.execute(
            "INSERT INTO fixed_work_sources."
            + table
            + " VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *scope,
                value["work"]["resource_id"],
                value["work"]["revision_id"],
                value["subjectId"],
                value["conversationId"],
                value["commandId"],
                hashed,
                Jsonb(value),
            ),
        )
    except UniqueViolation as exc:
        raise WorkbenchOwnerError("FIXED_WORK_SOURCE_CONFLICT", 409) from exc
    return {"record": value, "digest": hashed}


def conversation_mode(c, context, identity):
    """Read retained handoff after the original conversation owner check.

    This UI pause survives turning off new authoring. It grants no domain action.
    A damaged retained fact fails the journal read rather than silently starting work.
    """
    if (
        c.execute("SELECT to_regclass('fixed_work_sources.handoffs') name").fetchone()[
            "name"
        ]
        is None
    ):
        return None
    rows = c.execute(
        "SELECT record,digest FROM fixed_work_sources.handoffs WHERE namespace=%s "
        "AND security_domain=%s AND conversation_id=%s",
        (context.scope.tenant_id, context.scope.security_domain, identity),
    ).fetchall()
    if not rows:
        return None
    require(len(rows) == 1, "HANDOFF_CHANGED")
    row = rows[0]
    require(digest(row["record"]) == row["digest"], "RECORD_INVALID")
    require(
        row["record"].get("conversationId") == identity
        and row["record"].get("mode") == "TARGET_REVIEW_ONLY"
        and row["record"].get("executionEnabled") is False,
        "HANDOFF_CHANGED",
    )
    return {
        "mode": "TARGET_REVIEW_ONLY",
        "handoffDigest": row["digest"],
        "work": row["record"]["work"],
        "team": row["record"]["team"],
    }
