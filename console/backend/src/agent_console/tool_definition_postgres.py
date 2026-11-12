"""Imported tool draft owner inside a freshly authorized caller transaction."""

from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

from psycopg.types.json import Jsonb

from .digital_employee_definition import identifier
from .execution_domain import ScopeIdentity, record_digest
from .postgres_schema_compatibility import (
    LEDGER_COLUMNS,
    Table,
    columns,
    foreign,
    primary,
    schema_is_compatible,
    unique,
)
from .tool_import import preview_import, preview_plugin_zip

KEY = ("namespace", "security_domain", "tool_id")
REVISION = (*KEY, "revision_id")
SOURCE = ("namespace", "security_domain", "source_digest")
STRUCTURE = (
    Table("tool_definition.schema_migrations", LEDGER_COLUMNS, (primary("version"),)),
    Table(
        "tool_definition.sources",
        columns(*((k, "text") for k in (*SOURCE, "source_kind")), ("payload", "bytea")),
        (primary(*SOURCE),),
        ("immutable_sources",),
    ),
    Table(
        "tool_definition.definitions",
        columns(
            *(
                (k, "text")
                for k in (
                    *KEY,
                    "logical_digest",
                )
            ),
            ("aggregate_version", "bigint"),
        ),
        (primary(*KEY), unique("namespace", "security_domain", "logical_digest")),
    ),
    Table(
        "tool_definition.revisions",
        columns(
            *(
                (k, "text")
                for k in (
                    *REVISION,
                    "source_digest",
                    "digest",
                )
            ),
            ("record", "jsonb"),
        ),
        (
            primary(*REVISION),
            foreign(KEY, "tool_definition.definitions", KEY),
            foreign(SOURCE, "tool_definition.sources", SOURCE),
            foreign(
                (*KEY, "predecessor_revision_id"), "tool_definition.revisions", REVISION
            ),
        ),
        ("immutable_revisions",),
    ),
    Table(
        "tool_definition.receipts",
        columns(
            *(
                (k, "text")
                for k in (
                    "namespace",
                    "security_domain",
                    "command_id",
                    "actor_id",
                    "decision_id",
                    "payload_digest",
                )
            ),
            ("result", "jsonb"),
            ("recorded_at", "timestamp with time zone"),
        ),
        (primary("namespace", "security_domain", "command_id"),),
        ("immutable_receipts",),
    ),
)


class ToolStorageError(ValueError):
    pass


def import_preview(kind, payload):
    return (
        preview_plugin_zip(payload)
        if kind == "PLUGIN_ZIP"
        else preview_import(kind, payload)
    )


def logical_identity(operation):
    source = operation["source"]
    identity = (
        {k: source[k] for k in ("kind", "server", "path", "method")}
        if source["kind"] == "API"
        else {"kind": "PLUGIN", "id": source["id"], "tool": operation["name"]}
    )
    digest = record_digest(identity)
    return "tool:" + digest, digest


class PostgresToolDefinitionRepository:
    def __init__(self, pool):
        self.pool = pool

    def migrate(self, path: Path):
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.pool.connection() as conn, conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(2760061)")
            conn.execute(path.read_text())
            conn.execute(
                "INSERT INTO tool_definition.schema_migrations VALUES (61,%s,%s) ON "
                "CONFLICT DO NOTHING",
                (checksum, "tool-definition-drafts-v1"),
            )
            self._compatible(conn, checksum)

    def compatibility(self, path: Path):
        with self.pool.connection() as conn:
            self._compatible(conn, hashlib.sha256(path.read_bytes()).hexdigest())

    @staticmethod
    def _compatible(conn, checksum):
        row = conn.execute(
            "SELECT checksum,adapter FROM tool_definition.schema_migrations WHERE"
            " version=61"
        ).fetchone()
        nullable = conn.execute(
            "SELECT table_name,column_name,data_type,is_nullable FROM "
            "information_schema.columns WHERE table_schema='tool_definition' AND "
            "((table_name='definitions' AND column_name IN "
            "('draft_revision_id','published_revision_id')) OR "
            "(table_name='revisions' AND column_name='predecessor_revision_id'))"
        ).fetchall()
        expected_nullable = {
            ("definitions", "draft_revision_id", "text", "YES"),
            ("definitions", "published_revision_id", "text", "YES"),
            ("revisions", "predecessor_revision_id", "text", "YES"),
        }
        if (
            not row
            or row["checksum"] != checksum
            or row["adapter"] != "tool-definition-drafts-v1"
            or {tuple(r.values()) for r in nullable} != expected_nullable
            or not schema_is_compatible(conn, STRUCTURE)
        ):
            raise ToolStorageError("TOOL_SCHEMA_INCOMPATIBLE")

    @staticmethod
    def _scope(scope):
        if not isinstance(scope, ScopeIdentity):
            raise ToolStorageError("TOOL_SCOPE_INVALID")
        return identifier(scope.namespace), identifier(scope.security_domain)

    @classmethod
    def head(cls, conn, scope, tool_id):
        return conn.execute(
            "SELECT * FROM tool_definition.definitions WHERE namespace=%s AND "
            "security_domain=%s AND tool_id=%s",
            (*cls._scope(scope), identifier(tool_id)),
        ).fetchone()

    @classmethod
    def read(cls, conn, scope, tool_id, revision_id=None):
        head = cls.head(conn, scope, tool_id)
        if not head:
            raise ToolStorageError("TOOL_NOT_FOUND")
        revision_id = identifier(
            revision_id or head["draft_revision_id"] or head["published_revision_id"]
        )
        row = conn.execute(
            "SELECT digest,record,source_digest FROM tool_definition.revisions "
            "WHERE namespace=%s AND security_domain=%s AND tool_id=%s AND "
            "revision_id=%s",
            (*cls._scope(scope), tool_id, revision_id),
        ).fetchone()
        if not row:
            raise ToolStorageError("TOOL_NOT_FOUND")
        if record_digest(row["record"]) != row["digest"]:
            raise ToolStorageError("TOOL_RECORD_CORRUPT")
        return {
            "toolId": tool_id,
            "revisionId": revision_id,
            "digest": row["digest"],
            "sourceDigest": row["source_digest"],
            "aggregateVersion": head["aggregate_version"],
            "draftRevisionId": head["draft_revision_id"],
            "publishedRevisionId": head["published_revision_id"],
            "record": row["record"],
            "executionAuthorized": False,
        }

    @classmethod
    def source(cls, conn, scope, source_digest):
        row = conn.execute(
            "SELECT source_kind,payload FROM tool_definition.sources WHERE "
            "namespace=%s AND security_domain=%s AND source_digest=%s",
            (*cls._scope(scope), source_digest),
        ).fetchone()
        if not row:
            raise ToolStorageError("TOOL_SOURCE_NOT_FOUND")
        payload = bytes(row["payload"])
        if hashlib.sha256(payload).hexdigest() != source_digest:
            raise ToolStorageError("TOOL_SOURCE_CORRUPT")
        return row["source_kind"], payload

    @classmethod
    def import_drafts(
        cls,
        conn,
        scope,
        kind,
        payload,
        selected,
        expected_versions,
        *,
        command_id,
        actor_id,
        decision_id,
        effects=None,
    ):
        """No grants minted here. Caller must reauthorize even idempotent replays."""
        key = cls._scope(scope)
        for value in (command_id, actor_id, decision_id):
            identifier(value)
        preview = import_preview(kind, payload)
        operations = {op["name"]: op for op in preview["operations"]}
        if (
            not isinstance(selected, list)
            or not selected
            or any(
                not isinstance(name, str) or name not in operations for name in selected
            )
            or len(set(selected)) != len(selected)
            or not isinstance(expected_versions, dict)
            or set(expected_versions) - set(selected)
            or any(type(v) is not int or v < 0 for v in expected_versions.values())
        ):
            raise ToolStorageError("TOOL_IMPORT_SELECTION_INVALID")
        effects = {} if effects is None else effects
        if (
            not isinstance(effects, dict)
            or set(effects) - set(selected)
            or any(
                value
                not in {"UNCONFIRMED", "read-only", "creates-file", "external-write"}
                for value in effects.values()
            )
        ):
            raise ToolStorageError("TOOL_IMPORT_EFFECT_INVALID")
        request = {
            "kind": kind,
            "sourceDigest": preview["sourceDigest"],
            "selected": sorted(selected),
            "expectedVersions": expected_versions,
            "actorId": actor_id,
        }
        # Preserve historical receipt digests when callers omit declarations.
        if effects:
            request["effects"] = effects
        digest = record_digest(request)
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,61))",
            (record_digest(list(key)),),
        )
        prior = conn.execute(
            "SELECT payload_digest,result FROM tool_definition.receipts WHERE "
            "namespace=%s AND security_domain=%s AND command_id=%s",
            (*key, command_id),
        ).fetchone()
        if prior:
            if prior["payload_digest"] != digest:
                raise ToolStorageError("TOOL_COMMAND_CONFLICT")
            return {**prior["result"], "replayed": True}
        plans = []
        for name in selected:
            operation = dict(operations[name])
            if name in effects:
                operation["sideEffect"] = effects[name]
            tool_id, logical_digest = logical_identity(operation)
            head = cls.head(conn, scope, tool_id)
            expected = expected_versions.get(name, 0)
            duplicate = bool(head and expected == 0)
            if not duplicate and expected != (head["aggregate_version"] if head else 0):
                raise ToolStorageError("TOOL_VERSION_CONFLICT")
            plans.append((operation, tool_id, logical_digest, head, duplicate))
        # Check the entire selection before writing; BFF transaction is atomic.
        if any(not plan[-1] for plan in plans):
            conn.execute(
                "INSERT INTO tool_definition.sources VALUES (%s,%s,%s,%s,%s) ON "
                "CONFLICT DO NOTHING",
                (*key, preview["sourceDigest"], kind, payload),
            )
            saved_kind, saved_payload = cls.source(conn, scope, preview["sourceDigest"])
            if saved_kind != kind or saved_payload != payload:
                raise ToolStorageError("TOOL_SOURCE_CONFLICT")
        result = []
        for operation, tool_id, logical_digest, head, duplicate in plans:
            if duplicate:
                result.append(
                    {
                        "toolId": tool_id,
                        "revisionId": head["draft_revision_id"]
                        or head["published_revision_id"],
                        "aggregateVersion": head["aggregate_version"],
                        "existing": True,
                        "changed": False,
                    }
                )
                continue
            revision = "tool-revision:" + str(uuid4())
            version = (head["aggregate_version"] if head else 0) + 1
            predecessor = (
                (head["draft_revision_id"] or head["published_revision_id"])
                if head
                else None
            )
            record = {
                "schemaVersion": "tool-definition.v1",
                "name": operation["name"],
                "purpose": operation["description"],
                "operation": operation,
                "sourceDigest": preview["sourceDigest"],
                "state": "DRAFT",
                "validation": None,
            }
            if not head:
                conn.execute(
                    "INSERT INTO tool_definition.definitions VALUES "
                    "(%s,%s,%s,%s,NULL,NULL,%s)",
                    (*key, tool_id, logical_digest, version),
                )
            conn.execute(
                "INSERT INTO tool_definition.revisions VALUES "
                "(%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    *key,
                    tool_id,
                    revision,
                    predecessor,
                    preview["sourceDigest"],
                    record_digest(record),
                    Jsonb(record),
                ),
            )
            conn.execute(
                "UPDATE tool_definition.definitions SET "
                "draft_revision_id=%s,aggregate_version=%s WHERE namespace=%s AND "
                "security_domain=%s AND tool_id=%s",
                (revision, version, *key, tool_id),
            )
            result.append(
                {
                    "toolId": tool_id,
                    "revisionId": revision,
                    "digest": record_digest(record),
                    "aggregateVersion": version,
                    "existing": bool(head),
                    "changed": True,
                    "state": "DRAFT",
                }
            )
        response = {
            "commandKind": "IMPORT",
            "items": result,
            "sourceDigest": preview["sourceDigest"],
            "replayed": False,
            "executionAuthorized": False,
        }
        conn.execute(
            "INSERT INTO "
            "tool_definition.receipts(namespace,security_domain,command_id,actor_id,decision_id,payload_digest,result)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (*key, command_id, actor_id, decision_id, digest, Jsonb(response)),
        )
        return response

    @classmethod
    def revise_draft(
        cls,
        conn,
        scope,
        tool_id,
        content,
        *,
        expected_version,
        command_id,
        actor_id,
        decision_id,
    ):
        from .tool_definition import ToolDraftContent

        key = cls._scope(scope)
        for value in (tool_id, command_id, actor_id, decision_id):
            identifier(value)
        if type(expected_version) is not int or expected_version < 1:
            raise ToolStorageError("TOOL_VERSION_INVALID")
        content = ToolDraftContent.model_validate(content)
        payload = record_digest(
            {
                "toolId": tool_id,
                "content": content.model_dump(mode="json"),
                "expectedVersion": expected_version,
                "actorId": actor_id,
            }
        )
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,61))",
            (record_digest(list(key)),),
        )
        prior = conn.execute(
            "SELECT payload_digest,result FROM tool_definition.receipts WHERE "
            "namespace=%s AND security_domain=%s AND command_id=%s",
            (*key, command_id),
        ).fetchone()
        if prior:
            if prior["payload_digest"] != payload:
                raise ToolStorageError("TOOL_COMMAND_CONFLICT")
            return {**prior["result"], "replayed": True}
        current = cls.read(conn, scope, tool_id)
        if current["aggregateVersion"] != expected_version:
            raise ToolStorageError("TOOL_VERSION_CONFLICT")
        operation = {
            **current["record"]["operation"],
            "inputSchema": content.inputSchema,
            "outputSchema": content.outputSchema,
            "sideEffect": content.sideEffect,
        }
        record = {
            **current["record"],
            "name": content.name,
            "purpose": content.purpose,
            "operation": operation,
            "validation": None,
            "state": "DRAFT",
        }
        revision = "tool-revision:" + str(uuid4())
        digest = record_digest(record)
        version = expected_version + 1
        conn.execute(
            "INSERT INTO tool_definition.revisions VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *key,
                tool_id,
                revision,
                current["revisionId"],
                current["sourceDigest"],
                digest,
                Jsonb(record),
            ),
        )
        conn.execute(
            "UPDATE tool_definition.definitions SET "
            "draft_revision_id=%s,aggregate_version=%s WHERE namespace=%s AND "
            "security_domain=%s AND tool_id=%s",
            (revision, version, *key, tool_id),
        )
        result = {
            "commandKind": "REVISE",
            "items": [
                {
                    "toolId": tool_id,
                    "revisionId": revision,
                    "digest": digest,
                    "aggregateVersion": version,
                    "existing": True,
                    "changed": True,
                    "state": "DRAFT",
                }
            ],
            "replayed": False,
            "executionAuthorized": False,
        }
        conn.execute(
            "INSERT INTO "
            "tool_definition.receipts(namespace,security_domain,command_id,actor_id,decision_id,payload_digest,result)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (*key, command_id, actor_id, decision_id, payload, Jsonb(result)),
        )
        return result
