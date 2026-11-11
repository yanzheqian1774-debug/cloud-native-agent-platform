"""Append-only publication facts in the capability owner's existing transaction."""

import hashlib
from pathlib import Path

from psycopg.types.json import Jsonb

from .business_capability import BusinessCapabilityError
from .digital_employee_definition import digest
from .postgres_schema_compatibility import (
    Table,
    columns,
    foreign,
    primary,
    schema_is_compatible,
    unique,
)

_KEY = ("namespace", "security_domain", "capability_id")
_REVISION = (*_KEY, "revision_id")
STRUCTURE = (
    Table(
        "business_capability.publications",
        columns(
            *(
                (k, "text")
                for k in (
                    *_REVISION,
                    "revision_digest",
                    "command_id",
                    "payload_digest",
                    "actor_id",
                    "decision_id",
                    "authority_basis",
                    "impact_digest",
                )
            ),
            ("record", "jsonb"),
            ("aggregate_version", "bigint"),
            ("recorded_at", "timestamp with time zone"),
        ),
        (
            primary("namespace", "security_domain", "command_id"),
            unique(*_KEY, "aggregate_version"),
            unique(*_REVISION),
            foreign(_REVISION, "business_capability.revisions", _REVISION),
        ),
        ("immutable_publications",),
    ),
)


class CapabilityPublicationRepository:
    def __init__(self, pool):
        self.pool = pool

    def migrate(self, path: Path):
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.pool.connection() as conn, conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(2760053)")
            conn.execute(path.read_text())
            conn.execute(
                "INSERT INTO business_capability.schema_migrations VALUES (53,%s,%s) "
                "ON CONFLICT DO NOTHING",
                (checksum, "business-capability-publication-v1"),
            )
            self._compatible(conn, checksum)

    @staticmethod
    def _compatible(conn, checksum):
        row = conn.execute(
            "SELECT checksum,adapter FROM business_capability.schema_migrations "
            "WHERE version=53"
        ).fetchone()
        if (
            not row
            or row["checksum"] != checksum
            or row["adapter"] != "business-capability-publication-v1"
            or not schema_is_compatible(conn, STRUCTURE)
        ):
            raise BusinessCapabilityError("CAPABILITY_PUBLICATION_SCHEMA_INCOMPATIBLE")

    def compatibility(self, path: Path):
        with self.pool.connection() as conn:
            self._compatible(conn, hashlib.sha256(path.read_bytes()).hexdigest())

    @staticmethod
    def latest(conn, scope, identity):
        return conn.execute(
            "SELECT revision_id,revision_digest,aggregate_version,recorded_at "
            "FROM business_capability.publications WHERE namespace=%s "
            "AND security_domain=%s "
            "AND capability_id=%s ORDER BY aggregate_version DESC LIMIT 1",
            (scope.namespace, scope.security_domain, identity),
        ).fetchone()

    @staticmethod
    def payload(revision, command, actor):
        return digest(
            {
                "revisionId": revision.revision_id,
                "capabilityId": revision.capability_id,
                "revisionDigest": revision.content_digest,
                "actor": actor,
                "command": command.model_dump(mode="json"),
            }
        )

    @staticmethod
    def begin(conn, revision, command, actor):
        """Fresh authorization and reference verification must precede replay."""
        scope = revision.scope
        key = (scope.namespace, scope.security_domain, revision.capability_id)
        command_key = (scope.namespace, scope.security_domain, command.commandId)
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 55))",
            (digest(command_key),),
        )
        prior = conn.execute(
            "SELECT * FROM business_capability.publications WHERE namespace=%s "
            "AND security_domain=%s AND command_id=%s",
            command_key,
        ).fetchone()
        if prior:
            if prior["payload_digest"] != CapabilityPublicationRepository.payload(
                revision, command, actor
            ):
                raise BusinessCapabilityError("CAPABILITY_COMMAND_CONFLICT")
            return {
                "revisionId": prior["revision_id"],
                "digest": prior["revision_digest"],
                "aggregateVersion": prior["aggregate_version"],
                "replayed": True,
                "decisionId": prior["decision_id"],
                "state": "PUBLISHED",
                "executionAuthorized": False,
            }
        # Same ordering/aggregate lock as draft saves. No duplicated publication.
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 54))", (digest(key),)
        )
        row = conn.execute(
            "SELECT head_revision_id,aggregate_version "
            "FROM business_capability.definitions "
            "WHERE namespace=%s AND security_domain=%s AND capability_id=%s FOR UPDATE",
            key,
        ).fetchone()
        if (
            not row
            or row["head_revision_id"] != revision.revision_id
            or row["aggregate_version"] != command.expectedVersion
        ):
            raise BusinessCapabilityError("CAPABILITY_VERSION_CONFLICT")
        if conn.execute(
            "SELECT 1 FROM business_capability.publications WHERE namespace=%s "
            "AND security_domain=%s AND capability_id=%s AND revision_id=%s",
            (*key, revision.revision_id),
        ).fetchone():
            raise BusinessCapabilityError("CAPABILITY_ALREADY_PUBLISHED")
        return None

    @staticmethod
    def append(conn, revision, command, preview, actor, decision, basis):
        if basis not in {"HUMAN_EXACT_REVIEW", "DEVELOPMENT_ADMINISTRATOR"}:
            raise BusinessCapabilityError("CAPABILITY_REVIEW_BASIS_REQUIRED")
        key = (
            revision.scope.namespace,
            revision.scope.security_domain,
            revision.capability_id,
        )
        version = command.expectedVersion + 1
        changed = conn.execute(
            "UPDATE business_capability.definitions SET aggregate_version=%s "
            "WHERE namespace=%s AND security_domain=%s AND capability_id=%s "
            "AND aggregate_version=%s AND head_revision_id=%s",
            (version, *key, command.expectedVersion, revision.revision_id),
        ).rowcount
        if changed != 1:
            raise BusinessCapabilityError("CAPABILITY_VERSION_CONFLICT")
        record = {
            "schemaVersion": "business-capability-publication.v1",
            "preview": preview,
            "reason": command.reason,
            "validationScope": preview["validationScope"],
            "actorId": actor,
            "decisionId": decision,
            "authorityBasis": basis,
        }
        conn.execute(
            "INSERT INTO business_capability.publications "
            "(namespace,security_domain,capability_id,revision_id,revision_digest,command_id,"
            "payload_digest,actor_id,decision_id,authority_basis,impact_digest,"
            "record,aggregate_version) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *key,
                revision.revision_id,
                revision.content_digest,
                command.commandId,
                CapabilityPublicationRepository.payload(revision, command, actor),
                actor,
                decision,
                basis,
                preview["impactDigest"],
                Jsonb(record),
                version,
            ),
        )
        return {
            "revisionId": revision.revision_id,
            "digest": revision.content_digest,
            "aggregateVersion": version,
            "replayed": False,
            "decisionId": decision,
            "state": "PUBLISHED",
            "executionAuthorized": False,
        }
