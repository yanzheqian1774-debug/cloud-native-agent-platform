"""Capability draft storage; caller owns the authorized transaction."""

from __future__ import annotations

import hashlib
from pathlib import Path

from psycopg.types.json import Jsonb

from .business_capability import BusinessCapabilityError, BusinessCapabilityRevision
from .digital_employee_definition import digest, identifier
from .postgres_schema_compatibility import (
    LEDGER_COLUMNS,
    Table,
    columns,
    foreign,
    primary,
    schema_is_compatible,
    unique,
)

_KEY = ("namespace", "security_domain", "capability_id")
_REVISION = (*_KEY, "revision_id")
_ADAPTER = "business-capability-v1"
CAPABILITY_STRUCTURE = (
    Table(
        "business_capability.schema_migrations", LEDGER_COLUMNS, (primary("version"),)
    ),
    Table(
        "business_capability.definitions",
        columns(
            *((k, "text") for k in _KEY),
            ("head_revision_id", "text"),
            ("aggregate_version", "bigint"),
        ),
        (primary(*_KEY),),
    ),
    Table(
        "business_capability.revisions",
        columns(
            *((k, "text") for k in _REVISION), ("digest", "text"), ("record", "jsonb")
        ),
        (
            primary(*_REVISION),
            unique(*_KEY, "predecessor_revision_id"),
            foreign(_KEY, "business_capability.definitions", _KEY),
            foreign(
                (*_KEY, "predecessor_revision_id"),
                "business_capability.revisions",
                _REVISION,
            ),
        ),
        ("immutable_revisions",),
    ),
    Table(
        "business_capability.receipts",
        columns(
            *(
                (k, "text")
                for k in (
                    *_REVISION,
                    "command_id",
                    "payload_digest",
                    "actor_id",
                    "decision_id",
                )
            ),
            ("aggregate_version", "bigint"),
            ("recorded_at", "timestamp with time zone"),
        ),
        (
            primary("namespace", "security_domain", "command_id"),
            unique(*_KEY, "aggregate_version"),
            foreign(_REVISION, "business_capability.revisions", _REVISION),
        ),
        ("immutable_receipts",),
    ),
)


class PostgresBusinessCapabilityRepository:
    def __init__(self, pool):
        self.pool = pool

    def migrate(self, path: Path) -> None:
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.pool.connection() as conn, conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(2760052)")
            conn.execute(path.read_text())
            conn.execute(
                "INSERT INTO business_capability.schema_migrations VALUES (52,%s,%s) "
                "ON CONFLICT DO NOTHING",
                (checksum, _ADAPTER),
            )
            self._compatible(conn, checksum)

    @staticmethod
    def _compatible(conn, checksum):
        row = conn.execute(
            "SELECT checksum,adapter FROM business_capability.schema_migrations "
            "WHERE version=52"
        ).fetchone()
        if (
            not row
            or row["checksum"] != checksum
            or row["adapter"] != _ADAPTER
            or not schema_is_compatible(conn, CAPABILITY_STRUCTURE)
        ):
            raise BusinessCapabilityError("CAPABILITY_SCHEMA_INCOMPATIBLE")

    def compatibility(self, path: Path) -> None:
        with self.pool.connection() as conn:
            self._compatible(conn, hashlib.sha256(path.read_bytes()).hexdigest())

    @staticmethod
    def read(conn, scope, capability_id, revision_id):
        key = (
            scope.namespace,
            scope.security_domain,
            identifier(capability_id),
            identifier(revision_id),
        )
        row = conn.execute(
            "SELECT record,digest FROM business_capability.revisions "
            "WHERE namespace=%s AND security_domain=%s AND capability_id=%s AND "
            "revision_id=%s",
            key,
        ).fetchone()
        if row is None:
            raise BusinessCapabilityError("CAPABILITY_NOT_FOUND")
        value = BusinessCapabilityRevision.from_record(row["record"])
        if (
            value.content_digest != row["digest"]
            or value.scope != scope
            or value.capability_id != capability_id
            or value.revision_id != revision_id
        ):
            raise BusinessCapabilityError("CAPABILITY_RECORD_CORRUPT")
        return value

    @staticmethod
    def save(
        conn,
        revision: BusinessCapabilityRevision,
        *,
        expected_version: int,
        command_id: str,
        actor_id: str,
        decision_id: str,
    ):
        """Called only after capability and exact member reads are authorized.

        Fresh authorization is required even for a replay. No grants or policy
        decisions are synthesized here. All locks are held by the caller's UoW.
        """
        if type(expected_version) is not int or expected_version < 0:
            raise BusinessCapabilityError("CAPABILITY_EXPECTED_VERSION_INVALID")
        for value in (command_id, actor_id, decision_id):
            identifier(value)
        scope = revision.scope
        key = (scope.namespace, scope.security_domain, revision.capability_id)
        command_key = (scope.namespace, scope.security_domain, command_id)
        payload = digest(
            {
                "revision": revision.canonical_record(),
                "expectedVersion": expected_version,
                "actor": actor_id,
            }
        )
        # Stable command lock also serializes a reused command on another capability.
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 53))",
            (digest(command_key),),
        )
        prior = conn.execute(
            "SELECT * FROM business_capability.receipts WHERE namespace=%s "
            "AND security_domain=%s AND command_id=%s",
            command_key,
        ).fetchone()
        if prior:
            if prior["payload_digest"] != payload:
                raise BusinessCapabilityError("CAPABILITY_COMMAND_CONFLICT")
            return {
                "revisionId": prior["revision_id"],
                "aggregateVersion": prior["aggregate_version"],
                "replayed": True,
                "decisionId": prior["decision_id"],
            }
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 54))", (digest(key),)
        )
        head = conn.execute(
            "SELECT head_revision_id,aggregate_version FROM "
            "business_capability.definitions "
            "WHERE namespace=%s AND security_domain=%s AND capability_id=%s FOR UPDATE",
            key,
        ).fetchone()
        if (
            head is None
            and (expected_version != 0 or revision.predecessor_revision_id is not None)
        ) or (
            head is not None
            and (
                head["aggregate_version"] != expected_version
                or head["head_revision_id"] != revision.predecessor_revision_id
            )
        ):
            raise BusinessCapabilityError("CAPABILITY_VERSION_CONFLICT")
        version = expected_version + 1
        if head is None:
            conn.execute(
                "INSERT INTO business_capability.definitions VALUES (%s,%s,%s,%s,%s)",
                (*key, revision.revision_id, version),
            )
        else:
            if conn.execute(
                "SELECT 1 FROM business_capability.revisions WHERE namespace=%s "
                "AND security_domain=%s AND capability_id=%s AND revision_id=%s",
                (*key, revision.revision_id),
            ).fetchone():
                raise BusinessCapabilityError("CAPABILITY_REVISION_EXISTS")
            conn.execute(
                "UPDATE business_capability.definitions SET "
                "head_revision_id=%s,aggregate_version=%s "
                "WHERE namespace=%s AND security_domain=%s AND capability_id=%s",
                (revision.revision_id, version, *key),
            )
        conn.execute(
            "INSERT INTO business_capability.revisions VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (
                *key,
                revision.revision_id,
                revision.predecessor_revision_id,
                revision.content_digest,
                Jsonb(revision.canonical_record()),
            ),
        )
        conn.execute(
            "INSERT INTO business_capability.receipts "
            "(namespace,security_domain,command_id,capability_id,revision_id,"
            "payload_digest,actor_id,decision_id,aggregate_version) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *command_key,
                revision.capability_id,
                revision.revision_id,
                payload,
                actor_id,
                decision_id,
                version,
            ),
        )
        return {
            "revisionId": revision.revision_id,
            "aggregateVersion": version,
            "replayed": False,
            "decisionId": decision_id,
        }
