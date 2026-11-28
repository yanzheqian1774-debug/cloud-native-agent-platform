"""Tool-owned committed claim, conservative UNKNOWN and append-only result."""

import hashlib
from pathlib import Path

from psycopg.types.json import Jsonb

from .execution_domain import record_digest
from .postgres_schema_compatibility import (
    Table,
    columns,
    foreign,
    primary,
    schema_is_compatible,
    unique,
)

MIGRATION = (
    Path(__file__).resolve().parents[2] / "migrations/0081_tool_source_tests.sql"
)
ADAPTER = "tool-source-tests-v1"
KEY = ("namespace", "security_domain", "subject_id", "command_key")
STRUCTURE = (
    Table(
        "tool_definition.source_test_requests",
        columns(
            *((k, "text") for k in (*KEY, "binding_digest", "request_digest")),
            ("request", "jsonb"),
            ("created_at", "timestamp with time zone"),
        ),
        (primary(*KEY), unique("namespace", "security_domain", "command_key")),
        ("source_test_requests_immutable",),
    ),
    Table(
        "tool_definition.source_test_facts",
        columns(
            *((k, "text") for k in (*KEY, "kind", "fact_digest")),
            ("fact", "jsonb"),
            ("recorded_at", "timestamp with time zone"),
        ),
        (
            primary(*KEY, "kind"),
            foreign(KEY, "tool_definition.source_test_requests", KEY),
        ),
        ("source_test_facts_immutable",),
    ),
)


def check_schema(c):
    row = c.execute(
        "SELECT checksum,adapter FROM tool_definition.schema_migrations "
        "WHERE version=81"
    ).fetchone()
    if (
        not row
        or row["checksum"] != hashlib.sha256(MIGRATION.read_bytes()).hexdigest()
        or row["adapter"] != ADAPTER
        or not schema_is_compatible(c, STRUCTURE)
    ):
        raise ValueError("TOOL_SOURCE_SCHEMA_INCOMPATIBLE")


def migrate(c):
    """Explicit caller transaction only; never invoked by startup or dispatch."""
    if c.autocommit:
        raise ValueError("TOOL_SOURCE_MIGRATION_TRANSACTION_REQUIRED")
    c.execute("SELECT pg_advisory_xact_lock(2760081)")
    row = c.execute(
        "SELECT checksum,adapter FROM tool_definition.schema_migrations "
        "WHERE version=81"
    ).fetchone()
    if row is None:
        c.execute(MIGRATION.read_text())
        c.execute(
            "INSERT INTO tool_definition.schema_migrations VALUES (81,%s,%s)",
            (hashlib.sha256(MIGRATION.read_bytes()).hexdigest(), ADAPTER),
        )
    check_schema(c)


class SourceJournal:
    def __init__(self, pool):
        self.pool = pool

    @staticmethod
    def key(context, command_key):
        return (
            context.scope.tenant_id,
            context.scope.security_domain,
            context.principal_id,
            command_key,
        )

    @staticmethod
    def snapshot(c, key):
        row = c.execute(
            "SELECT request_digest,request FROM tool_definition.source_test_requests "
            "WHERE namespace=%s AND security_domain=%s "
            "AND subject_id=%s AND command_key=%s",
            key,
        ).fetchone()
        if not row:
            return None
        if record_digest(row["request"]) != row["request_digest"]:
            raise ValueError("TOOL_SOURCE_JOURNAL_CORRUPT")
        facts = c.execute(
            "SELECT kind,fact,fact_digest FROM tool_definition.source_test_facts "
            "WHERE namespace=%s AND security_domain=%s "
            "AND subject_id=%s AND command_key=%s",
            key,
        ).fetchall()
        if any(f["fact_digest"] != record_digest(f["fact"]) for f in facts):
            raise ValueError("TOOL_SOURCE_JOURNAL_CORRUPT")
        by_kind = {f["kind"]: f["fact"] for f in facts}
        if by_kind.get("DISPATCH_CLAIM") != {"requestDigest": row["request_digest"]}:
            raise ValueError("TOOL_SOURCE_JOURNAL_CORRUPT")
        return {
            **row,
            "result": by_kind.get("RESULT"),
            "claimed": "DISPATCH_CLAIM" in by_kind,
        }

    def claim(self, context, command_key, binding_digest, request, maximum_calls):
        key = self.key(context, command_key)
        digest = record_digest(request)
        with self.pool.connection() as c, c.transaction():
            check_schema(c)
            # Serialize same-key conflicts across bindings, then shared binding cap.
            for lock in (list(key), [*key[:3], binding_digest]):
                c.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s,81))",
                    (record_digest(lock),),
                )
            old = self.snapshot(c, key)
            if old:
                if old["request_digest"] != digest:
                    raise ValueError("TOOL_SOURCE_COMMAND_CONFLICT")
                return False, old
            used = c.execute(
                "SELECT count(*) n FROM tool_definition.source_test_requests WHERE "
                "namespace=%s AND security_domain=%s "
                "AND subject_id=%s AND binding_digest=%s",
                (*key[:3], binding_digest),
            ).fetchone()["n"]
            if used >= maximum_calls:
                raise ValueError("TOOL_SOURCE_CALL_CAP_EXHAUSTED")
            c.execute(
                "INSERT INTO tool_definition.source_test_requests "
                "(namespace,security_domain,subject_id,command_key,"
                "binding_digest,request_digest,request) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (*key, binding_digest, digest, Jsonb(request)),
            )
            self._append(c, key, "DISPATCH_CLAIM", {"requestDigest": digest})
        return True, None

    @staticmethod
    def _append(c, key, kind, fact):
        c.execute(
            "INSERT INTO tool_definition.source_test_facts "
            "(namespace,security_domain,subject_id,command_key,kind,fact,fact_digest) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (*key, kind, Jsonb(fact), record_digest(fact)),
        )

    def finish(self, context, command_key, result):
        key = self.key(context, command_key)
        with self.pool.connection() as c, c.transaction():
            check_schema(c)
            c.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,81))",
                (record_digest(list(key)),),
            )
            old = self.snapshot(c, key)
            if not old or not old["claimed"]:
                raise ValueError("TOOL_SOURCE_CLAIM_REQUIRED")
            if old["result"] is not None:
                if old["result"] != result:
                    raise ValueError("TOOL_SOURCE_RESULT_CONFLICT")
                return
            self._append(c, key, "RESULT", result)

    def read(self, context, command_key):
        with self.pool.connection() as c:
            check_schema(c)
            return self.snapshot(c, self.key(context, command_key))
