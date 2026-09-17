"""Workflow Control's scoped, append-only planning v2 PostgreSQL adapter."""

from __future__ import annotations

import hashlib
from contextlib import contextmanager, nullcontext
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .business_problem_domain import canonical_digest
from .plan_suggestion_domain import (
    ConfirmedPlanRevision,
    PlanningConflict,
    PlanningError,
    ProposalRevision,
)
from .workflow_control_domain import ApprovalDecision


class PostgresPlanningRepository:
    """All confirmations use the caller's same-owner transaction and target lock."""

    def __init__(self, pool, connection=None):
        self.pool = pool
        self.connection = connection

    def migrate(self):
        path = Path(__file__).parents[2] / "migrations/0025_plan_suggestion.sql"
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.pool.connection() as conn, conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(3230025)")
            conn.execute(path.read_text())
            row = conn.execute(
                "SELECT checksum FROM workflow_planning.schema_migrations "
                "WHERE version=25"
            ).fetchone()
            if (
                row
                and (row["checksum"] if isinstance(row, dict) else row[0]) != checksum
            ):
                raise PlanningConflict("PLANNING_MIGRATION_CHECKSUM")
            conn.execute(
                "INSERT INTO workflow_planning.schema_migrations VALUES (25,%s) "
                "ON CONFLICT DO NOTHING",
                (checksum,),
            )

    @staticmethod
    def _scope(scope):
        return scope.namespace, scope.security_domain

    @contextmanager
    def transaction(self, scope, proposal_id, *, authorized):
        if not authorized:
            raise PlanningError("PLANNING_NOT_AUTHORIZED")
        with (
            (
                nullcontext(self.connection)
                if self.connection is not None
                else self.pool.connection()
            ) as connection,
            nullcontext() if self.connection is not None else connection.transaction(),
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            connection.row_factory = dict_row
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (canonical_digest([*self._scope(scope), proposal_id]),),
            )
            yield cursor

    def proposal(self, cursor, scope, proposal_id, revision):
        row = cursor.execute(
            "SELECT record FROM workflow_planning.proposals "
            "WHERE namespace=%s AND security_domain=%s AND proposal_id=%s "
            "AND revision=%s",
            (*self._scope(scope), proposal_id, revision),
        ).fetchone()
        if row is None:
            raise PlanningError("PLANNING_NOT_FOUND")
        return ProposalRevision.model_validate(row["record"])

    def add_proposal(self, cursor, scope, proposal):
        row = cursor.execute(
            "SELECT record FROM workflow_planning.proposals "
            "WHERE namespace=%s AND security_domain=%s AND proposal_id=%s "
            "ORDER BY revision DESC LIMIT 1",
            (*self._scope(scope), proposal.proposal_id),
        ).fetchone()
        if row:
            head = ProposalRevision.model_validate(row["record"])
            if proposal.revision <= head.revision:
                existing = self.proposal(
                    cursor, scope, proposal.proposal_id, proposal.revision
                )
                if existing == proposal:
                    return existing
                raise PlanningConflict("PROPOSAL_IMMUTABLE_CONFLICT")
            if (
                proposal.revision != head.revision + 1
                or proposal.predecessor_digest != head.digest
            ):
                raise PlanningConflict("PROPOSAL_HEAD_CONFLICT")
        elif proposal.revision != 1 or proposal.predecessor_digest is not None:
            raise PlanningConflict("PROPOSAL_HEAD_CONFLICT")
        cursor.execute(
            "INSERT INTO workflow_planning.proposals VALUES (%s,%s,%s,%s,%s,%s)",
            (
                *self._scope(scope),
                proposal.proposal_id,
                proposal.revision,
                proposal.digest,
                Jsonb(proposal.model_dump(mode="json")),
            ),
        )
        return proposal

    def _replay(self, cursor, scope, actor, key, digest):
        # A key is scoped to its actor and all confirmation targets.
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,1))",
            (canonical_digest([*self._scope(scope), actor, key]),),
        )
        row = cursor.execute(
            "SELECT * FROM workflow_planning.commands WHERE namespace=%s "
            "AND security_domain=%s AND actor_id=%s AND command_key=%s",
            (*self._scope(scope), actor, key),
        ).fetchone()
        if row and row["payload_digest"] != digest:
            raise PlanningConflict("PLANNING_IDEMPOTENCY_CONFLICT")
        return row["result"] if row else None

    def confirmation(
        self,
        cursor,
        scope,
        proposal,
        *,
        actor,
        key,
        expected_plan_version,
        authority_basis,
        before_commit=None,
        validate_current=None,
    ):
        persisted = self.proposal(
            cursor, scope, proposal.proposal_id, proposal.revision
        )
        if persisted != proposal:
            raise PlanningConflict("PROPOSAL_DIGEST_CONFLICT")
        payload = canonical_digest(
            [
                proposal.proposal_id,
                proposal.revision,
                proposal.digest,
                expected_plan_version,
            ]
        )
        replay = self._replay(cursor, scope, actor, key, payload)
        if replay:
            return replay
        existing = cursor.execute(
            "SELECT record,version FROM workflow_planning.plans "
            "WHERE namespace=%s AND security_domain=%s AND proposal_id=%s "
            "AND proposal_revision=%s",
            (*self._scope(scope), proposal.proposal_id, proposal.revision),
        ).fetchone()
        if existing:
            result = self.read_plan(
                cursor, scope, proposal.proposal_id, existing["version"]
            )
        else:
            if validate_current:
                validate_current()
            head = cursor.execute(
                "SELECT record FROM workflow_planning.plans "
                "WHERE namespace=%s AND security_domain=%s AND plan_id=%s "
                "ORDER BY version DESC LIMIT 1",
                (*self._scope(scope), proposal.proposal_id),
            ).fetchone()
            previous = (
                ConfirmedPlanRevision.model_validate(head["record"]) if head else None
            )
            version = previous.version if previous else 0
            latest = cursor.execute(
                "SELECT max(revision) AS revision FROM workflow_planning.proposals "
                "WHERE namespace=%s AND security_domain=%s AND proposal_id=%s",
                (*self._scope(scope), proposal.proposal_id),
            ).fetchone()["revision"]
            if version != expected_plan_version or latest != proposal.revision:
                raise PlanningConflict("PLAN_HEAD_CONFLICT")
            plan = ConfirmedPlanRevision(
                plan_id=proposal.proposal_id,
                version=version + 1,
                source_proposal_id=proposal.proposal_id,
                source_proposal_revision=proposal.revision,
                source_proposal_digest=proposal.digest,
                predecessor_digest=previous.digest if previous else None,
                semantics=proposal.semantics,
            )
            decision_id = str(uuid4())
            now = datetime.now(UTC)
            decision = ApprovalDecision(
                decision_id,
                plan.plan_id,
                plan.version,
                plan.digest,
                1,
                "APPROVE",
                actor,
                authority_basis,
                "BUSINESS_APPROVAL",
                canonical_digest([decision_id, plan.digest, actor, authority_basis]),
                now,
            )
            record = plan.model_dump(mode="json")
            approval = asdict(decision)
            approval["decided_at"] = now.isoformat()
            cursor.execute(
                "INSERT INTO workflow_planning.plans VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    *self._scope(scope),
                    plan.plan_id,
                    plan.version,
                    proposal.proposal_id,
                    proposal.revision,
                    plan.digest,
                    Jsonb(record),
                ),
            )
            cursor.execute(
                "INSERT INTO workflow_planning.approvals VALUES (%s,%s,%s,%s,%s,%s)",
                (
                    *self._scope(scope),
                    plan.plan_id,
                    plan.version,
                    decision_id,
                    Jsonb(approval),
                ),
            )
            result = {
                "plan": record,
                "digest": plan.digest,
                "approval": approval,
                "execution_status": "NOT_STARTED",
            }
        cursor.execute(
            "INSERT INTO workflow_planning.commands VALUES (%s,%s,%s,%s,%s,%s)",
            (*self._scope(scope), actor, key, payload, Jsonb(result)),
        )
        if before_commit:
            before_commit()
        return result

    def read_plan(self, cursor, scope, plan_id, version):
        row = cursor.execute(
            "SELECT p.record,p.digest,a.record AS approval "
            "FROM workflow_planning.plans p JOIN workflow_planning.approvals a "
            "USING(namespace,security_domain,plan_id,version) "
            "WHERE namespace=%s AND security_domain=%s AND plan_id=%s AND version=%s",
            (*self._scope(scope), plan_id, version),
        ).fetchone()
        if row is None:
            raise PlanningError("PLANNING_NOT_FOUND")
        return {
            "plan": row["record"],
            "digest": row["digest"],
            "approval": row["approval"],
            "execution_status": "NOT_STARTED",
        }

    def history(self, cursor, scope, proposal_id):
        rows = cursor.execute(
            "SELECT revision,record FROM workflow_planning.proposals "
            "WHERE namespace=%s "
            "AND security_domain=%s AND proposal_id=%s ORDER BY revision LIMIT 100",
            (*self._scope(scope), proposal_id),
        ).fetchall()
        plans = cursor.execute(
            "SELECT version FROM workflow_planning.plans WHERE namespace=%s "
            "AND security_domain=%s AND plan_id=%s ORDER BY version LIMIT 100",
            (*self._scope(scope), proposal_id),
        ).fetchall()
        return {
            "proposals": [row["record"] for row in rows],
            "plans": [
                self.read_plan(cursor, scope, proposal_id, row["version"])
                for row in plans
            ],
        }

    def save_resources(self, cursor, scope, proposal, snapshot):
        snapshot.pending_required(proposal)
        cursor.execute(
            "INSERT INTO workflow_planning.resource_snapshots "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (
                *self._scope(scope),
                snapshot.snapshot_id,
                proposal.proposal_id,
                proposal.revision,
                Jsonb(snapshot.model_dump(mode="json")),
            ),
        )
        return snapshot
