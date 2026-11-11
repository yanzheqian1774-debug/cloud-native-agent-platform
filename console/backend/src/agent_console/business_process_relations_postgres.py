"""Immutable capability relations on the caller's authorized transaction."""

import hashlib

from psycopg.types.json import Jsonb

from .business_capability_postgres import PostgresBusinessCapabilityRepository
from .business_process_definition import (
    BusinessCapabilityRelation,
    BusinessProcessContent,
    FixedBusinessReference,
    relation_issues,
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

SCOPE = ("namespace", "security_domain")
STRUCTURE = (
    Table(
        "business_process.capability_relations",
        columns(
            *(
                (key, "text")
                for key in (
                    *SCOPE,
                    "relation_id",
                    "relation_revision_id",
                    "relation_type",
                    "process_kind",
                    "process_id",
                    "process_revision_id",
                    "capability_id",
                    "capability_revision_id",
                    "digest",
                    "command_id",
                    "payload_digest",
                    "actor_id",
                    "decision_id",
                )
            ),
            ("relation_version", "bigint"),
            ("record", "jsonb"),
            ("result", "jsonb"),
            ("recorded_at", "timestamp with time zone"),
        ),
        (
            primary(*SCOPE, "command_id"),
            unique(*SCOPE, "relation_id", "relation_version"),
            unique(*SCOPE, "relation_id", "relation_revision_id"),
            foreign(
                (*SCOPE, "process_kind", "process_id", "process_revision_id"),
                "business_process.revisions",
                (*SCOPE, "kind", "object_id", "revision_id"),
            ),
        ),
        ("immutable_capability_relations",),
    ),
)


class BusinessProcessRelationRepository:
    def __init__(self, pool):
        self.pool = pool

    def migrate(self, path):
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.pool.connection() as conn, conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(2760058)")
            conn.execute(path.read_text())
            conn.execute(
                "INSERT INTO business_process.schema_migrations VALUES (58,%s,%s) "
                "ON CONFLICT DO NOTHING",
                (checksum, "business-capability-relations-v1"),
            )
            self._compatible(conn, checksum)

    @staticmethod
    def _compatible(conn, checksum):
        row = conn.execute(
            "SELECT checksum,adapter FROM business_process.schema_migrations "
            "WHERE version=58"
        ).fetchone()
        if (
            not row
            or row["checksum"] != checksum
            or row["adapter"] != "business-capability-relations-v1"
            or not schema_is_compatible(conn, STRUCTURE)
        ):
            raise BusinessProcessStorageError("BUSINESS_RELATION_SCHEMA_INCOMPATIBLE")

    def compatibility(self, path):
        with self.pool.connection() as conn:
            self._compatible(conn, hashlib.sha256(path.read_bytes()).hexdigest())

    @staticmethod
    def save(
        conn, scope, relation, *, expected_version, command_id, actor_id, decision_id
    ):
        """Caller checks current maintenance and both exact read permissions first."""
        for value in (command_id, actor_id, decision_id):
            identifier(value)
        if type(expected_version) is not int or expected_version < 0:
            raise BusinessProcessStorageError("BUSINESS_RELATION_VERSION_INVALID")
        relation = BusinessCapabilityRelation.model_validate(relation)
        identifier(relation.relation_id)
        identifier(relation.relation_revision_id)
        record = relation.model_dump(mode="json")
        key = (scope.namespace, scope.security_domain)
        payload = record_digest(
            dict(
                record=record,
                expectedVersion=expected_version,
                actorId=actor_id,
                commandId=command_id,
            )
        )
        # Serialize same-scope commands, including conflicting reuses on different IDs.
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,58))",
            (record_digest(key),),
        )
        if conn.execute(
            "SELECT 1 FROM business_process.relation_withdrawals WHERE "
            "namespace=%s AND security_domain=%s AND command_id=%s",
            (*key, command_id),
        ).fetchone():
            raise BusinessProcessStorageError("BUSINESS_RELATION_COMMAND_CONFLICT")
        prior = conn.execute(
            "SELECT payload_digest,result FROM business_process.capability_relations "
            "WHERE namespace=%s AND security_domain=%s AND command_id=%s",
            (*key, command_id),
        ).fetchone()
        if prior:
            if prior["payload_digest"] != payload:
                raise BusinessProcessStorageError("BUSINESS_RELATION_COMMAND_CONFLICT")
            return {**prior["result"], "replayed": True}
        if conn.execute(
            "SELECT 1 FROM business_process.relation_withdrawals WHERE "
            "namespace=%s AND security_domain=%s AND relation_id=%s",
            (*key, relation.relation_id),
        ).fetchone():
            raise BusinessProcessStorageError("BUSINESS_RELATION_WITHDRAWN_CONFLICT")
        previous = conn.execute(
            "SELECT * FROM business_process.capability_relations "
            "WHERE namespace=%s AND security_domain=%s AND relation_id=%s "
            "ORDER BY relation_version DESC LIMIT 1",
            (*key, relation.relation_id),
        ).fetchone()
        if (previous["relation_version"] if previous else 0) != expected_version:
            raise BusinessProcessStorageError("BUSINESS_RELATION_VERSION_CONFLICT")
        if previous and (
            previous["process_id"],
            previous["capability_id"],
            previous["relation_type"],
        ) != (
            relation.process.resource_id,
            relation.capability.resource_id,
            relation.relation_type,
        ):
            raise BusinessProcessStorageError("BUSINESS_RELATION_IDENTITY_CONFLICT")
        if conn.execute(
            "SELECT 1 FROM business_process.capability_relations "
            "WHERE namespace=%s AND security_domain=%s AND relation_id=%s "
            "AND relation_revision_id=%s",
            (*key, relation.relation_id, relation.relation_revision_id),
        ).fetchone():
            raise BusinessProcessStorageError("BUSINESS_RELATION_REVISION_CONFLICT")
        process = PostgresBusinessProcessRepository.read(
            conn,
            scope,
            "PROCESS",
            relation.process.resource_id,
            relation.process.revision_id,
        )
        if relation_issues(
            relation,
            FixedBusinessReference(
                resource_id=process["objectId"],
                revision_id=process["revisionId"],
                digest=process["digest"],
            ),
            BusinessProcessContent.model_validate(process["record"]["content"]),
        ):
            raise BusinessProcessStorageError("BUSINESS_RELATION_PROCESS_INVALID")
        capability = PostgresBusinessCapabilityRepository.read(
            conn,
            scope,
            relation.capability.resource_id,
            relation.capability.revision_id,
        )
        if capability.content_digest != relation.capability.digest:
            raise BusinessProcessStorageError("BUSINESS_RELATION_CAPABILITY_INVALID")
        digest = record_digest(record)
        result = dict(
            relationId=relation.relation_id,
            relationRevisionId=relation.relation_revision_id,
            digest=digest,
            relationVersion=expected_version + 1,
            executionAuthorized=False,
        )
        conn.execute(
            "INSERT INTO business_process.capability_relations "
            "(namespace,security_domain,relation_id,relation_revision_id,relation_version,"
            "relation_type,process_id,process_revision_id,capability_id,capability_revision_id,"
            "digest,record,command_id,payload_digest,actor_id,decision_id,result) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *key,
                relation.relation_id,
                relation.relation_revision_id,
                expected_version + 1,
                relation.relation_type,
                relation.process.resource_id,
                relation.process.revision_id,
                relation.capability.resource_id,
                relation.capability.revision_id,
                digest,
                Jsonb(record),
                command_id,
                payload,
                actor_id,
                decision_id,
                Jsonb(result),
            ),
        )
        return result

    @staticmethod
    def decode(row):
        try:
            relation = BusinessCapabilityRelation.model_validate(row["record"])
        except ValueError as error:
            raise BusinessProcessStorageError(
                "BUSINESS_RELATION_RECORD_CORRUPT"
            ) from error
        digest = record_digest(row["record"])
        expected = dict(
            relationId=relation.relation_id,
            relationRevisionId=relation.relation_revision_id,
            digest=digest,
            relationVersion=row["relation_version"],
            executionAuthorized=False,
        )
        if (
            digest != row["digest"]
            or row["result"] != expected
            or (
                relation.relation_id,
                relation.relation_revision_id,
                relation.relation_type,
                relation.process.resource_id,
                relation.process.revision_id,
                relation.capability.resource_id,
                relation.capability.revision_id,
            )
            != (
                row["relation_id"],
                row["relation_revision_id"],
                row["relation_type"],
                row["process_id"],
                row["process_revision_id"],
                row["capability_id"],
                row["capability_revision_id"],
            )
        ):
            raise BusinessProcessStorageError("BUSINESS_RELATION_RECORD_CORRUPT")
        return {
            **expected,
            "record": relation.model_dump(mode="json"),
            "actorId": row["actor_id"],
            "recordedAt": row["recorded_at"].isoformat(),
        }
