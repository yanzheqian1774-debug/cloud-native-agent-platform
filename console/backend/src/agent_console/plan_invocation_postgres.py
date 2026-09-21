"""Planning invocation claims and atomic bounded result/proposal persistence."""

import hashlib
from pathlib import Path

from psycopg.types.json import Jsonb

from .plan_suggestion_domain import PlanningConflict, PlanningError
from .plan_suggestion_postgres import PostgresPlanningRepository


class PostgresPlanningInvocations:
    def __init__(self, planning: PostgresPlanningRepository):
        self.planning = planning

    def has_usage_target(self, connection, scope, identity, *, measurement):
        """Validate persisted invocation, kind and receipt without dispatch."""
        row = connection.execute(
            "SELECT r.record FROM workflow_planning.invocations i "
            "JOIN contextual_resource_use.uses u ON u.namespace=i.namespace "
            "AND u.security_domain=i.security_domain AND u.context_id=i.invocation_id "
            "AND u.context_kind='PLAN_SUGGESTION_INVOCATION' "
            "AND u.resource_use_id=%s "
            "LEFT JOIN workflow_planning.provider_receipts r "
            "ON r.namespace=i.namespace AND r.security_domain=i.security_domain "
            "AND r.invocation_id=i.invocation_id "
            "WHERE i.namespace=%s AND i.security_domain=%s AND i.invocation_id=%s",
            (
                "contextual-resource-use:" + identity,
                scope.tenant_id,
                scope.security_domain,
                identity,
            ),
        ).fetchone()
        return row is not None and (not measurement or isinstance(row["record"], dict))

    def migrate(self):
        self._migrate(26, "0026_plan_suggestion_invocation.sql")
        self._migrate(27, "0027_planning_provider_receipt.sql")

    def _migrate(self, version, filename):
        path = Path(__file__).parents[2] / "migrations" / filename
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.planning.pool.connection() as conn, conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(3230026)")
            row = conn.execute(
                "SELECT checksum FROM workflow_planning.schema_migrations "
                "WHERE version=%s",
                (version,),
            ).fetchone()
            if row:
                existing = row["checksum"] if isinstance(row, dict) else row[0]
                if existing != checksum:
                    raise PlanningConflict("PLANNING_MIGRATION_CHECKSUM")
                return
            conn.execute(path.read_text())
            conn.execute(
                "INSERT INTO workflow_planning.schema_migrations VALUES (%s,%s)",
                (version, checksum),
            )

    def claim(self, scope, actor, key, digest, record):
        with self.planning.transaction(
            scope, "invocation:" + actor + key, authorized=True
        ) as cursor:
            existing = cursor.execute(
                "SELECT * FROM workflow_planning.invocations WHERE namespace=%s "
                "AND security_domain=%s AND actor_id=%s AND request_key=%s",
                (scope.namespace, scope.security_domain, actor, key),
            ).fetchone()
            if existing:
                if existing["payload_digest"] != digest:
                    raise PlanningConflict("PLANNING_IDEMPOTENCY_CONFLICT")
                return existing["record"], False
            cursor.execute(
                "INSERT INTO workflow_planning.invocations "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (
                    scope.namespace,
                    scope.security_domain,
                    record["target"]["invocation_id"],
                    actor,
                    key,
                    digest,
                    Jsonb(record),
                ),
            )
            return record, True

    def read(self, scope, invocation_id, actor):
        with self.planning.transaction(scope, invocation_id, authorized=True) as cursor:
            row = cursor.execute(
                "SELECT i.record,r.record AS result "
                "FROM workflow_planning.invocations i "
                "LEFT JOIN workflow_planning.invocation_results r "
                "USING(namespace,security_domain,invocation_id) "
                "WHERE namespace=%s AND security_domain=%s AND invocation_id=%s "
                "AND actor_id=%s",
                (scope.namespace, scope.security_domain, invocation_id, actor),
            ).fetchone()
            if row is None:
                raise PlanningError("PLANNING_NOT_FOUND")
            return {
                "invocation": row["record"],
                "result": row["result"]
                or {
                    "technical_status": "OUTCOME_UNKNOWN",
                    "kind": None,
                    "reason": "NO_DURABLE_TERMINAL_RESULT_DO_NOT_REDISPATCH",
                },
            }

    def finish(self, scope, invocation_id, result, proposal=None, validate=None):
        identity = proposal.proposal_id if proposal else invocation_id
        with self.planning.transaction(scope, identity, authorized=True) as cursor:
            if validate:
                validate(cursor.connection)
            if proposal:
                self.planning.add_proposal(cursor, scope, proposal)
            inserted = cursor.execute(
                "INSERT INTO workflow_planning.invocation_results VALUES (%s,%s,%s,%s) "
                "ON CONFLICT DO NOTHING RETURNING invocation_id",
                (scope.namespace, scope.security_domain, invocation_id, Jsonb(result)),
            ).fetchone()
            if inserted is None:
                existing = cursor.execute(
                    "SELECT record FROM workflow_planning.invocation_results "
                    "WHERE namespace=%s AND security_domain=%s AND invocation_id=%s",
                    (scope.namespace, scope.security_domain, invocation_id),
                ).fetchone()
                if existing["record"] != result:
                    raise PlanningConflict("PLANNING_RESULT_IMMUTABLE")

    def save_receipt(self, scope, invocation_id, receipt):
        with self.planning.transaction(scope, invocation_id, authorized=True) as cursor:
            inserted = cursor.execute(
                "INSERT INTO workflow_planning.provider_receipts VALUES (%s,%s,%s,%s) "
                "ON CONFLICT DO NOTHING RETURNING invocation_id",
                (scope.namespace, scope.security_domain, invocation_id, Jsonb(receipt)),
            ).fetchone()
            if inserted is None:
                existing = cursor.execute(
                    "SELECT record FROM workflow_planning.provider_receipts "
                    "WHERE namespace=%s AND security_domain=%s AND invocation_id=%s",
                    (scope.namespace, scope.security_domain, invocation_id),
                ).fetchone()
                if existing["record"] != receipt:
                    raise PlanningConflict("PLANNING_RECEIPT_IMMUTABLE")

    def receipt(self, scope, invocation_id):
        with self.planning.transaction(scope, invocation_id, authorized=True) as cursor:
            row = cursor.execute(
                "SELECT record FROM workflow_planning.provider_receipts "
                "WHERE namespace=%s AND security_domain=%s AND invocation_id=%s",
                (scope.namespace, scope.security_domain, invocation_id),
            ).fetchone()
            return row["record"] if row else None

    def find_request(self, scope, actor, key, digest=None):
        with self.planning.transaction(
            scope, "invocation:" + actor + key, authorized=True
        ) as cursor:
            row = cursor.execute(
                "SELECT invocation_id,payload_digest "
                "FROM workflow_planning.invocations "
                "WHERE namespace=%s AND security_domain=%s "
                "AND actor_id=%s AND request_key=%s",
                (scope.namespace, scope.security_domain, actor, key),
            ).fetchone()
            if row and digest is not None and row["payload_digest"] != digest:
                raise PlanningConflict("PLANNING_IDEMPOTENCY_CONFLICT")
            return row["invocation_id"] if row else None
