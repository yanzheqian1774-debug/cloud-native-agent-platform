"""Atomic receipt boundary, inside the caller's existing authorized transaction.

This repository does not authorize calls or choose resources. The coordinator must
check fresh actor/object permissions even on replay, supply the reviewed request,
and invoke only transaction-bound owners. No external tool or model effects belong
inside this transaction. A missing receipt never proves rollback of an unknown call.
"""

import hashlib
import re
from pathlib import Path

from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb

from .digital_employee_definition import digest, identifier
from .postgres_schema_compatibility import Table, columns, primary, schema_is_compatible


class UpgradeBatchError(ValueError):
    pass


STRUCTURE = (
    Table(
        "resource_upgrade.receipts",
        columns(
            *(
                (name, "text")
                for name in (
                    "namespace",
                    "security_domain",
                    "actor_id",
                    "command_id",
                    "request_digest",
                    "preview_digest",
                    "record_digest",
                )
            ),
            ("record", "jsonb"),
            ("recorded_at", "timestamp with time zone"),
        ),
        (primary("namespace", "security_domain", "actor_id", "command_id"),),
        ("immutable_upgrade_receipts",),
    ),
)


class UpgradeBatchRepository:
    def __init__(self, pool):
        self.pool = pool

    def migrate(self, path: Path):
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.pool.connection() as conn, conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(2760060)")
            conn.execute(path.read_text())
            conn.execute(
                "INSERT INTO resource_upgrade.schema_migrations VALUES (60,%s,%s) "
                "ON CONFLICT DO NOTHING",
                (checksum, "selected-resource-upgrade-v1"),
            )
            self._compatible(conn, checksum)

    @staticmethod
    def _compatible(conn, checksum):
        row = conn.execute(
            "SELECT checksum,adapter FROM resource_upgrade.schema_migrations "
            "WHERE version=60"
        ).fetchone()
        if (
            not row
            or row != {"checksum": checksum, "adapter": "selected-resource-upgrade-v1"}
            or not schema_is_compatible(conn, STRUCTURE)
        ):
            raise UpgradeBatchError("UPGRADE_BATCH_SCHEMA_INCOMPATIBLE")

    def compatibility(self, path: Path):
        with self.pool.connection() as conn:
            self._compatible(conn, hashlib.sha256(path.read_bytes()).hexdigest())

    @staticmethod
    def _key(conn, scope, actor, command):
        if conn.info.transaction_status != TransactionStatus.INTRANS:
            raise UpgradeBatchError("UPGRADE_CALLER_TRANSACTION_REQUIRED")
        return (
            scope.namespace,
            scope.security_domain,
            identifier(actor),
            identifier(command),
        )

    @staticmethod
    def _row(conn, key):
        return conn.execute(
            "SELECT request_digest,preview_digest,record_digest,record "
            "FROM resource_upgrade.receipts WHERE namespace=%s AND security_domain=%s "
            "AND actor_id=%s AND command_id=%s",
            key,
        ).fetchone()

    @staticmethod
    def _record(row, key):
        record = row["record"]
        if (
            digest(record) != row["record_digest"]
            or record.get("batchId") != digest(key)
            or record.get("previewDigest") != row["preview_digest"]
            or record.get("requestDigest") != row["request_digest"]
        ):
            raise UpgradeBatchError("UPGRADE_BATCH_RECEIPT_CORRUPT")
        return record

    @classmethod
    def read(cls, conn, scope, actor, command):
        """Caller authorizes original batch scope first; no retry decision inferred."""
        key = cls._key(conn, scope, actor, command)
        row = cls._row(conn, key)
        return (
            {"state": "COMMITTED", "receipt": cls._record(row, key)}
            if row
            else {"state": "NOT_RECORDED", "safeToReplay": False}
        )

    @classmethod
    def apply(
        cls,
        conn,
        scope,
        actor,
        command,
        *,
        request,
        reviewed_digest,
        authority_generation,
        recovery_epoch,
        decision_ids,
        current_preview_digest,
        apply_owners,
        completed_decision_ids=None,
    ):
        key = cls._key(conn, scope, actor, command)
        if not re.fullmatch(r"[0-9a-f]{64}", reviewed_digest):
            raise UpgradeBatchError("UPGRADE_REVIEW_DIGEST_REQUIRED")
        if (
            type(authority_generation) is not int
            or authority_generation < 1
            or type(recovery_epoch) is not int
            or recovery_epoch < 0
            or not decision_ids
        ):
            raise UpgradeBatchError("UPGRADE_AUTHORIZATION_EVIDENCE_REQUIRED")
        decisions = [identifier(value) for value in decision_ids]
        request_digest = digest({"request": request, "previewDigest": reviewed_digest})
        # A savepoint also rolls back owner writes if the outer caller catches an error.
        with conn.transaction():
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,60))", (digest(key),)
            )
            prior = cls._row(conn, key)
            if prior:
                if prior["request_digest"] != request_digest:
                    raise UpgradeBatchError("UPGRADE_BATCH_COMMAND_CONFLICT")
                return {"receipt": cls._record(prior, key), "replayed": True}
            if current_preview_digest() != reviewed_digest:
                raise UpgradeBatchError("UPGRADE_PREVIEW_CHANGED")
            result = apply_owners()
            if completed_decision_ids is not None:
                # Actual nested owner decisions are only available after the chain.
                decisions = sorted(
                    set(decisions)
                    | {identifier(value) for value in completed_decision_ids()}
                )
            record = {
                "schemaVersion": "selected-resource-upgrade-receipt.v1",
                "batchId": digest(key),
                "requestDigest": request_digest,
                "previewDigest": reviewed_digest,
                "actorId": actor,
                "authorityGeneration": authority_generation,
                "recoveryEpoch": recovery_epoch,
                "decisionIds": decisions,
                "result": result,
            }
            conn.execute(
                "INSERT INTO resource_upgrade.receipts "
                "(namespace,security_domain,actor_id,command_id,request_digest,"
                "preview_digest,record_digest,record) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (*key, request_digest, reviewed_digest, digest(record), Jsonb(record)),
            )
            return {"receipt": record, "replayed": False}
