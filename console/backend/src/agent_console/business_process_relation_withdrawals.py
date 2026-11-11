"""Append-only relation withdrawal; original fixed association records survive."""

import hashlib

from psycopg.types.json import Jsonb

from .business_process_postgres import BusinessProcessStorageError
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
        "business_process.relation_withdrawals",
        columns(
            *(
                (name, "text")
                for name in (
                    *SCOPE,
                    "relation_id",
                    "relation_revision_id",
                    "command_id",
                    "payload_digest",
                    "actor_id",
                    "decision_id",
                    "reason",
                )
            ),
            ("result", "jsonb"),
            ("recorded_at", "timestamp with time zone"),
        ),
        (
            primary(*SCOPE, "command_id"),
            unique(*SCOPE, "relation_id"),
            foreign(
                (*SCOPE, "relation_id", "relation_revision_id"),
                "business_process.capability_relations",
                (*SCOPE, "relation_id", "relation_revision_id"),
            ),
        ),
        ("immutable_relation_withdrawals",),
    ),
)


class BusinessRelationWithdrawalRepository:
    def __init__(self, pool):
        self.pool = pool

    def migrate(self, path):
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.pool.connection() as conn, conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(2760059)")
            conn.execute(path.read_text())
            conn.execute(
                "INSERT INTO business_process.schema_migrations VALUES "
                "(59,%s,%s) ON CONFLICT DO NOTHING",
                (checksum, "business-relation-withdrawals-v1"),
            )
            self._compatible(conn, checksum)

    @staticmethod
    def _compatible(conn, checksum):
        row = conn.execute(
            "SELECT checksum,adapter FROM "
            "business_process.schema_migrations WHERE version=59"
        ).fetchone()
        if (
            not row
            or row["checksum"] != checksum
            or row["adapter"] != "business-relation-withdrawals-v1"
            or not schema_is_compatible(conn, STRUCTURE)
        ):
            raise BusinessProcessStorageError(
                "BUSINESS_RELATION_WITHDRAWAL_SCHEMA_INCOMPATIBLE"
            )

    def compatibility(self, path):
        with self.pool.connection() as conn:
            self._compatible(conn, hashlib.sha256(path.read_bytes()).hexdigest())

    @staticmethod
    def withdraw(conn, scope, command, *, actor_id, decision_id):
        for value in (
            command["commandId"],
            command["relationId"],
            command["relationRevisionId"],
            actor_id,
            decision_id,
        ):
            identifier(value)
        reason = command["reason"].strip()
        if not reason or len(reason) > 2000:
            raise BusinessProcessStorageError(
                "BUSINESS_RELATION_WITHDRAWAL_REASON_INVALID"
            )
        key = (scope.namespace, scope.security_domain)
        payload = record_digest(dict(command=command, actorId=actor_id))
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,58))",
            (record_digest(key),),
        )
        if conn.execute(
            "SELECT 1 FROM business_process.capability_relations WHERE "
            "namespace=%s AND security_domain=%s AND command_id=%s",
            (*key, command["commandId"]),
        ).fetchone():
            raise BusinessProcessStorageError("BUSINESS_RELATION_COMMAND_CONFLICT")
        prior = conn.execute(
            "SELECT * FROM business_process.relation_withdrawals WHERE "
            "namespace=%s AND security_domain=%s AND command_id=%s",
            (*key, command["commandId"]),
        ).fetchone()
        if prior:
            if prior["payload_digest"] != payload:
                raise BusinessProcessStorageError("BUSINESS_RELATION_COMMAND_CONFLICT")
            return {**prior["result"], "replayed": True}
        latest = conn.execute(
            "SELECT * FROM business_process.capability_relations WHERE "
            "namespace=%s AND security_domain=%s AND relation_id=%s ORDER "
            "BY relation_version DESC LIMIT 1",
            (*key, command["relationId"]),
        ).fetchone()
        if not latest:
            raise BusinessProcessStorageError("BUSINESS_RELATION_NOT_FOUND")
        if (
            latest["relation_revision_id"],
            latest["relation_version"],
            latest["digest"],
        ) != (
            command["relationRevisionId"],
            command["expectedVersion"],
            command["digest"],
        ):
            raise BusinessProcessStorageError("BUSINESS_RELATION_VERSION_CONFLICT")
        if BusinessRelationWithdrawalRepository.state(
            conn, scope, command["relationId"]
        ):
            raise BusinessProcessStorageError("BUSINESS_RELATION_WITHDRAWN_CONFLICT")
        result = dict(
            relationId=command["relationId"],
            relationRevisionId=command["relationRevisionId"],
            relationVersion=command["expectedVersion"],
            digest=command["digest"],
            state="WITHDRAWN",
            reason=reason,
            executionAuthorized=False,
        )
        conn.execute(
            "INSERT INTO business_process.relation_withdrawals "
            "(namespace,security_domain,relation_id,relation_revision_id,"
            "command_id,payload_digest,actor_id,decision_id,reason,result) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *key,
                command["relationId"],
                command["relationRevisionId"],
                command["commandId"],
                payload,
                actor_id,
                decision_id,
                reason,
                Jsonb(result),
            ),
        )
        return result

    @staticmethod
    def state(conn, scope, relation_id):
        row = conn.execute(
            "SELECT result,recorded_at FROM "
            "business_process.relation_withdrawals WHERE namespace=%s AND "
            "security_domain=%s AND relation_id=%s",
            (scope.namespace, scope.security_domain, relation_id),
        ).fetchone()
        return (
            {**row["result"], "recordedAt": row["recorded_at"].isoformat()}
            if row
            else None
        )
