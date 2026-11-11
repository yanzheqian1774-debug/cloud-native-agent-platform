"""Draft persistence inside the caller's freshly authorized transaction.

No route registration, grant creation, publication or execution occurs here.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

from psycopg.types.json import Jsonb

from .business_process_definition import (
    BusinessArchitecture,
    BusinessProcessContent,
    definition_issues,
)
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

KEY = ("namespace", "security_domain", "kind", "object_id")
REVISION = (*KEY, "revision_id")
STRUCTURE = (
    Table("business_process.schema_migrations", LEDGER_COLUMNS, (primary("version"),)),
    Table(
        "business_process.definitions",
        columns(
            *((key, "text") for key in (*KEY, "head_revision_id")),
            ("aggregate_version", "bigint"),
        ),
        (primary(*KEY),),
    ),
    Table(
        "business_process.revisions",
        columns(*((key, "text") for key in (*REVISION, "digest")), ("record", "jsonb")),
        (
            primary(*REVISION),
            unique(*KEY, "predecessor_revision_id"),
            foreign(KEY, "business_process.definitions", KEY),
            foreign(
                (*KEY, "predecessor_revision_id"),
                "business_process.revisions",
                REVISION,
            ),
        ),
        ("immutable_revisions",),
    ),
    Table(
        "business_process.receipts",
        columns(
            *(
                (key, "text")
                for key in (
                    *REVISION,
                    "command_id",
                    "actor_id",
                    "decision_id",
                    "payload_digest",
                )
            ),
            ("aggregate_version", "bigint"),
            ("result", "jsonb"),
            ("recorded_at", "timestamp with time zone"),
        ),
        (
            primary("namespace", "security_domain", "command_id"),
            unique(*KEY, "aggregate_version"),
            foreign(REVISION, "business_process.revisions", REVISION),
        ),
        ("immutable_receipts",),
    ),
)


class BusinessProcessStorageError(ValueError):
    pass


class PostgresBusinessProcessRepository:
    def __init__(self, pool):
        self.pool = pool

    def migrate(self, path: Path):
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.pool.connection() as conn, conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(2760056)")
            conn.execute(path.read_text())
            conn.execute(
                "INSERT INTO business_process.schema_migrations VALUES (56,%s,%s) "
                "ON CONFLICT DO NOTHING",
                (checksum, "business-process-drafts-v1"),
            )
            self._compatible(conn, checksum)

    def compatibility(self, path: Path):
        with self.pool.connection() as conn:
            self._compatible(conn, hashlib.sha256(path.read_bytes()).hexdigest())

    @staticmethod
    def _compatible(conn, checksum):
        row = conn.execute(
            "SELECT checksum,adapter FROM "
            "business_process.schema_migrations WHERE version=56"
        ).fetchone()
        if (
            not row
            or row["checksum"] != checksum
            or row["adapter"] != "business-process-drafts-v1"
            or not schema_is_compatible(conn, STRUCTURE)
        ):
            raise BusinessProcessStorageError("BUSINESS_PROCESS_SCHEMA_INCOMPATIBLE")

    @staticmethod
    def _key(scope, kind, object_id):
        if not isinstance(scope, ScopeIdentity) or kind not in {
            "ARCHITECTURE",
            "PROCESS",
        }:
            raise BusinessProcessStorageError("BUSINESS_PROCESS_SCOPE_INVALID")
        return (scope.namespace, scope.security_domain, kind, identifier(object_id))

    @classmethod
    def read(cls, conn, scope, kind, object_id, revision_id=None):
        key = cls._key(scope, kind, object_id)
        head = conn.execute(
            "SELECT head_revision_id,aggregate_version FROM "
            "business_process.definitions "
            "WHERE namespace=%s AND security_domain=%s AND kind=%s AND object_id=%s",
            key,
        ).fetchone()
        if not head:
            raise BusinessProcessStorageError("BUSINESS_PROCESS_NOT_FOUND")
        revision_id = identifier(revision_id or head["head_revision_id"])
        row = conn.execute(
            "SELECT digest,record FROM business_process.revisions "
            "WHERE namespace=%s AND security_domain=%s AND kind=%s AND object_id=%s "
            "AND revision_id=%s",
            (*key, revision_id),
        ).fetchone()
        if not row:
            raise BusinessProcessStorageError("BUSINESS_PROCESS_NOT_FOUND")
        if record_digest(row["record"]) != row["digest"]:
            raise BusinessProcessStorageError("BUSINESS_PROCESS_RECORD_CORRUPT")
        return {
            "objectId": object_id,
            "revisionId": revision_id,
            "digest": row["digest"],
            "aggregateVersion": head["aggregate_version"],
            "record": row["record"],
        }

    @classmethod
    def save_architecture(cls, conn, scope, content: BusinessArchitecture, **command):
        return cls._save(
            conn, scope, "ARCHITECTURE", "architecture", content, **command
        )

    @classmethod
    def save_process(
        cls, conn, scope, object_id, content: BusinessProcessContent, **command
    ):
        return cls._save(conn, scope, "PROCESS", object_id, content, **command)

    @classmethod
    def _save(
        cls,
        conn,
        scope,
        kind,
        object_id,
        content,
        *,
        expected_version,
        command_id,
        actor_id,
        decision_id,
    ):
        """Caller must reauthorize even replays; this layer cannot grant access."""
        key = cls._key(scope, kind, object_id)
        if type(expected_version) is not int or expected_version < 0:
            raise BusinessProcessStorageError("BUSINESS_PROCESS_VERSION_INVALID")
        for identity in (command_id, actor_id, decision_id):
            identifier(identity)
        model = (
            BusinessArchitecture if kind == "ARCHITECTURE" else BusinessProcessContent
        )
        content = model.model_validate(content)
        request = {
            "kind": kind,
            "objectId": object_id,
            "content": content.model_dump(mode="json"),
            "expectedVersion": expected_version,
            "actorId": actor_id,
        }
        payload = record_digest(request)
        # Scope serialization also prevents architecture/process creation races.
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,56))",
            (record_digest({"namespace": key[0], "domain": key[1]}),),
        )
        prior = conn.execute(
            "SELECT payload_digest,result FROM business_process.receipts "
            "WHERE namespace=%s AND security_domain=%s AND command_id=%s",
            (*key[:2], command_id),
        ).fetchone()
        if prior:
            if prior["payload_digest"] != payload:
                raise BusinessProcessStorageError("BUSINESS_PROCESS_COMMAND_CONFLICT")
            return {**prior["result"], "replayed": True}
        head = conn.execute(
            "SELECT aggregate_version,head_revision_id FROM "
            "business_process.definitions "
            "WHERE namespace=%s AND security_domain=%s AND kind=%s AND "
            "object_id=%s FOR UPDATE",
            key,
        ).fetchone()
        if expected_version != (head["aggregate_version"] if head else 0):
            raise BusinessProcessStorageError("BUSINESS_PROCESS_VERSION_CONFLICT")
        record = {"content": content.model_dump(mode="json")}
        if kind == "PROCESS":
            architecture = cls.read(conn, scope, "ARCHITECTURE", "architecture")
            structure = BusinessArchitecture.model_validate(
                architecture["record"]["content"]
            )
            if any(
                issue.code in {"DOMAIN_NOT_FOUND", "GROUP_DOMAIN_MISMATCH"}
                for issue in definition_issues(content, structure)
            ):
                raise BusinessProcessStorageError(
                    "BUSINESS_PROCESS_ARCHITECTURE_MISMATCH"
                )
            record["architectureReference"] = {
                "revisionId": architecture["revisionId"],
                "digest": architecture["digest"],
            }
        version, revision_id = expected_version + 1, "business-revision:" + str(uuid4())
        digest = record_digest(record)
        if head:
            conn.execute(
                "UPDATE business_process.definitions SET "
                "head_revision_id=%s,aggregate_version=%s "
                "WHERE namespace=%s AND security_domain=%s AND kind=%s AND "
                "object_id=%s",
                (revision_id, version, *key),
            )
        else:
            conn.execute(
                "INSERT INTO business_process.definitions VALUES (%s,%s,%s,%s,%s,%s)",
                (*key, revision_id, version),
            )
        conn.execute(
            "INSERT INTO business_process.revisions VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *key,
                revision_id,
                head["head_revision_id"] if head else None,
                digest,
                Jsonb(record),
            ),
        )
        result = {
            "objectId": object_id,
            "revisionId": revision_id,
            "digest": digest,
            "aggregateVersion": version,
            "decisionId": decision_id,
            "replayed": False,
            "state": "DRAFT",
            "executionAuthorized": False,
        }
        conn.execute(
            "INSERT INTO business_process.receipts "
            "(namespace,security_domain,command_id,kind,object_id,revision_id,actor_id,"
            "decision_id,payload_digest,aggregate_version,result) VALUES "
            "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *key[:2],
                command_id,
                kind,
                object_id,
                revision_id,
                actor_id,
                decision_id,
                payload,
                version,
                Jsonb(result),
            ),
        )
        return result
