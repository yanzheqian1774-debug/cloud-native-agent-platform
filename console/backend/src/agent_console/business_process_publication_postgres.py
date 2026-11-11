"""Immutable publication facts; callers provide current authorization transaction."""

import hashlib
from pathlib import Path

from psycopg.types.json import Jsonb

from .business_process_definition import (
    BusinessArchitecture,
    BusinessProcessContent,
    definition_issues,
)
from .business_process_postgres import (
    BusinessProcessStorageError,
    PostgresBusinessProcessRepository,
)
from .digital_employee_definition import identifier
from .execution_domain import record_digest
from .postgres_schema_compatibility import (
    Table,
    columns,
    foreign,
    primary,
    schema_is_compatible,
    unique,
)

KEY = ("namespace", "security_domain", "object_id")
REVISION = ("namespace", "security_domain", "kind", "object_id", "revision_id")
STRUCTURE = (
    Table(
        "business_process.publications",
        columns(
            *(
                (k, "text")
                for k in (
                    *REVISION,
                    "revision_digest",
                    "command_id",
                    "payload_digest",
                    "actor_id",
                    "decision_id",
                )
            ),
            ("publication_version", "bigint"),
            ("content_version", "bigint"),
            ("result", "jsonb"),
            ("recorded_at", "timestamp with time zone"),
        ),
        (
            primary("namespace", "security_domain", "command_id"),
            unique(*KEY, "publication_version"),
            unique(*KEY, "revision_id"),
            foreign(REVISION, "business_process.revisions", REVISION),
        ),
        ("immutable_publications",),
    ),
)


class BusinessProcessPublicationRepository:
    def __init__(self, pool):
        self.pool = pool

    def migrate(self, path: Path):
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.pool.connection() as conn, conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(2760057)")
            conn.execute(path.read_text())
            conn.execute(
                "INSERT INTO business_process.schema_migrations VALUES (57,%s,%s) "
                "ON CONFLICT DO NOTHING",
                (checksum, "business-process-publication-v1"),
            )
            self._compatible(conn, checksum)

    @staticmethod
    def _compatible(conn, checksum):
        row = conn.execute(
            "SELECT checksum,adapter FROM business_process.schema_migrations "
            "WHERE version=57"
        ).fetchone()
        if (
            not row
            or row["checksum"] != checksum
            or row["adapter"] != "business-process-publication-v1"
            or not schema_is_compatible(conn, STRUCTURE)
        ):
            raise BusinessProcessStorageError("BUSINESS_PROCESS_SCHEMA_INCOMPATIBLE")

    def compatibility(self, path: Path):
        with self.pool.connection() as conn:
            self._compatible(conn, hashlib.sha256(path.read_bytes()).hexdigest())

    @staticmethod
    def latest(conn, scope, object_id):
        row = conn.execute(
            "SELECT result FROM business_process.publications WHERE namespace=%s "
            "AND security_domain=%s AND object_id=%s "
            "ORDER BY publication_version DESC LIMIT 1",
            (scope.namespace, scope.security_domain, identifier(object_id)),
        ).fetchone()
        return row["result"] if row else None

    @staticmethod
    def receipt(conn, scope, command_id, actor_id):
        row = conn.execute(
            "SELECT result FROM business_process.publications WHERE namespace=%s "
            "AND security_domain=%s AND command_id=%s AND actor_id=%s",
            (scope.namespace, scope.security_domain, identifier(command_id), actor_id),
        ).fetchone()
        if not row:
            raise BusinessProcessStorageError("BUSINESS_PROCESS_COMMAND_NOT_FOUND")
        return row["result"]

    @classmethod
    def publish(
        cls,
        conn,
        scope,
        object_id,
        *,
        revision_id,
        revision_digest,
        expected_version,
        command_id,
        actor_id,
        decision_id,
        validate_references=None,
    ):
        key = PostgresBusinessProcessRepository._key(scope, "PROCESS", object_id)
        for value in (revision_id, command_id, actor_id, decision_id):
            identifier(value)
        if type(expected_version) is not int or expected_version < 1:
            raise BusinessProcessStorageError("BUSINESS_PROCESS_VERSION_INVALID")
        payload = record_digest(
            dict(
                objectId=object_id,
                revisionId=revision_id,
                digest=revision_digest,
                expectedVersion=expected_version,
                commandId=command_id,
                actorId=actor_id,
            )
        )
        # Same serialization domain as draft saves; publish cannot overtake a save.
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,56))",
            (record_digest({"namespace": key[0], "domain": key[1]}),),
        )
        prior = conn.execute(
            "SELECT payload_digest,result FROM business_process.publications "
            "WHERE namespace=%s AND security_domain=%s AND command_id=%s",
            (*key[:2], command_id),
        ).fetchone()
        if prior:
            if prior["payload_digest"] != payload:
                raise BusinessProcessStorageError("BUSINESS_PROCESS_COMMAND_CONFLICT")
            return {**prior["result"], "replayed": True}
        head = conn.execute(
            "SELECT head_revision_id,aggregate_version "
            "FROM business_process.definitions "
            "WHERE namespace=%s AND security_domain=%s "
            "AND kind=%s AND object_id=%s FOR UPDATE",
            key,
        ).fetchone()
        if (
            not head
            or head["head_revision_id"] != revision_id
            or head["aggregate_version"] != expected_version
        ):
            raise BusinessProcessStorageError("BUSINESS_PROCESS_VERSION_CONFLICT")
        revision = PostgresBusinessProcessRepository.read(
            conn, scope, "PROCESS", object_id, revision_id
        )
        if revision["digest"] != revision_digest:
            raise BusinessProcessStorageError("BUSINESS_PROCESS_DIGEST_CONFLICT")
        reference = revision["record"]["architectureReference"]
        architecture = PostgresBusinessProcessRepository.read(
            conn, scope, "ARCHITECTURE", "architecture", reference["revisionId"]
        )
        if architecture["digest"] != reference["digest"]:
            raise BusinessProcessStorageError("BUSINESS_PROCESS_RECORD_CORRUPT")
        content = BusinessProcessContent.model_validate(revision["record"]["content"])
        if content.source_materials or any(
            item.employee for item in content.activities
        ):
            if validate_references is None:
                raise BusinessProcessStorageError(
                    "BUSINESS_PROCESS_REFERENCE_ADAPTER_UNAVAILABLE"
                )
            validate_references(content)
        if definition_issues(
            content,
            BusinessArchitecture.model_validate(architecture["record"]["content"]),
        ):
            raise BusinessProcessStorageError("BUSINESS_PROCESS_DEFINITION_INCOMPLETE")
        latest = cls.latest(conn, scope, object_id)
        if latest and latest["revisionId"] == revision_id:
            raise BusinessProcessStorageError(
                "BUSINESS_PROCESS_ALREADY_PUBLISHED_CONFLICT"
            )
        version = latest["publicationVersion"] + 1 if latest else 1
        result = {
            "objectId": object_id,
            "revisionId": revision_id,
            "digest": revision_digest,
            "contentVersion": expected_version,
            "publicationVersion": version,
            "state": "PUBLISHED",
            "executionAuthorized": False,
            "decisionId": decision_id,
            "replayed": False,
        }
        conn.execute(
            "INSERT INTO business_process.publications "
            "(namespace,security_domain,kind,object_id,revision_id,revision_digest,"
            "command_id,payload_digest,actor_id,decision_id,"
            "publication_version,content_version,result) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *key,
                revision_id,
                revision_digest,
                command_id,
                payload,
                actor_id,
                decision_id,
                version,
                expected_version,
                Jsonb(result),
            ),
        )
        return result
