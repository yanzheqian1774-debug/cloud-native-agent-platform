# ruff: noqa: E501
"""PostgreSQL 15 adapter for durable Business Problem authority."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from agent_console.business_problem_domain import (
    TRANSITIONS,
    BusinessProblemConflict,
    BusinessProblemError,
    BusinessProblemLifecycleEvent,
    BusinessProblemNotAuthorized,
    BusinessProblemRevision,
    BusinessProblemState,
    CriterionType,
    PlanProblemBinding,
    SuccessCriteriaSetRevision,
    SuccessCriterionRevision,
    canonical_bytes,
    canonical_digest,
)
from agent_console.execution_domain import ScopeIdentity

ADAPTER = "business-problem-postgresql-v1"


class PostgresBusinessProblemRepository:
    def __init__(
        self, database_url: str, *, migration_path: Path, timeout: float = 5.0
    ):
        if not database_url:
            raise BusinessProblemError("RECOVERY_REQUIRED")
        self.migration_path = migration_path
        try:
            self.pool = ConnectionPool(
                database_url,
                min_size=1,
                max_size=4,
                timeout=timeout,
                kwargs={"row_factory": dict_row, "autocommit": False},
                open=True,
            )
            self.pool.wait(timeout=timeout)
        except Exception as exc:
            raise BusinessProblemError("RECOVERY_REQUIRED") from exc

    @property
    def migration_checksum(self) -> str:
        return hashlib.sha256(self.migration_path.read_bytes()).hexdigest()

    def migrate(self) -> None:
        if self.migration_path.name[:4] != "0013":
            raise BusinessProblemError("RECOVERY_REQUIRED")
        with self.pool.connection() as connection, connection.transaction():
            exists = connection.execute(
                "SELECT to_regclass('business_problem_authority.schema_migrations') AS name"
            ).fetchone()["name"]
            if exists is None:
                connection.execute(self.migration_path.read_text())
                connection.execute(
                    "INSERT INTO business_problem_authority.schema_migrations(version,checksum,adapter) VALUES (13,%s,%s)",
                    (self.migration_checksum, ADAPTER),
                )
            else:
                row = connection.execute(
                    "SELECT checksum,adapter FROM business_problem_authority.schema_migrations WHERE version=13"
                ).fetchone()
                if (
                    row is None
                    or row["checksum"] != self.migration_checksum
                    or row["adapter"] != ADAPTER
                ):
                    raise BusinessProblemError("RECOVERY_REQUIRED")

    @staticmethod
    def _authorize(authorized: bool) -> None:
        if not authorized:
            raise BusinessProblemNotAuthorized("BUSINESS_PROBLEM_NOT_FOUND")

    @staticmethod
    def _scope(scope: ScopeIdentity) -> tuple[str, str]:
        return scope.namespace, scope.security_domain

    def _claim(
        self,
        connection: Any,
        scope: ScopeIdentity,
        actor: str,
        command: str,
        key: str,
        digest: str,
    ) -> dict[str, Any] | None:
        row = connection.execute(
            "SELECT payload_digest,result_record FROM business_problem_authority.idempotency_claims WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND command_type=%s AND idempotency_key=%s FOR UPDATE",
            (*self._scope(scope), actor, command, key),
        ).fetchone()
        if row and row["payload_digest"] != digest:
            raise BusinessProblemConflict("IDEMPOTENCY_PAYLOAD_MISMATCH")
        return row["result_record"] if row else None

    def _complete(
        self,
        connection: Any,
        scope: ScopeIdentity,
        actor: str,
        command: str,
        key: str,
        digest: str,
        kind: str,
        identity: str,
        result: dict[str, Any],
    ) -> None:
        connection.execute(
            "INSERT INTO business_problem_authority.idempotency_claims(namespace,security_domain,actor_id,command_type,idempotency_key,payload_digest,result_kind,result_id,result_record) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
            (
                *self._scope(scope),
                actor,
                command,
                key,
                digest,
                kind,
                identity,
                json.dumps(result),
            ),
        )

    @staticmethod
    def _revision(row: dict[str, Any]) -> BusinessProblemRevision:
        return BusinessProblemRevision(
            ScopeIdentity(row["namespace"], row["security_domain"]),
            row["business_problem_id"],
            row["revision_id"],
            row["revision"],
            row["predecessor_revision_id"],
            row["title"],
            row["description"],
            row["owner_id"],
            row["created_by"],
            row["created_at"],
            row["digest"],
        )

    def create_problem(
        self,
        revision: BusinessProblemRevision,
        *,
        idempotency_key: str,
        payload_digest: str,
        authorized: bool,
    ) -> BusinessProblemRevision:
        self._authorize(authorized)
        if revision.revision != 1 or revision.predecessor_revision_id is not None:
            raise BusinessProblemError("BUSINESS_PROBLEM_REVISION_STALE")
        with self.pool.connection() as connection, connection.transaction():
            replay = self._claim(
                connection,
                revision.scope,
                revision.created_by,
                "CREATE_BUSINESS_PROBLEM",
                idempotency_key,
                payload_digest,
            )
            if replay:
                return self._read_revision(
                    connection, revision.scope, replay["revision_id"]
                )
            connection.execute(
                "INSERT INTO business_problem_authority.problems VALUES (%s,%s,%s,%s,'DRAFT',1,%s,%s,%s,%s)",
                (
                    *self._scope(revision.scope),
                    revision.business_problem_id,
                    revision.owner_id,
                    revision.revision_id,
                    revision.created_by,
                    revision.created_at,
                    revision.created_at,
                ),
            )
            self._insert_problem_revision(connection, revision)
            connection.execute(
                "INSERT INTO business_problem_authority.lifecycle_events(namespace,security_domain,event_id,business_problem_id,ordinal,event_type,from_state,to_state,actor_id,event_digest,occurred_at) VALUES (%s,%s,%s,%s,1,'INITIAL',NULL,'DRAFT',%s,%s,%s)",
                (
                    *self._scope(revision.scope),
                    f"created:{revision.revision_id}",
                    revision.business_problem_id,
                    revision.created_by,
                    canonical_digest(
                        {"revision_id": revision.revision_id, "state": "DRAFT"}
                    ),
                    revision.created_at,
                ),
            )
            self._complete(
                connection,
                revision.scope,
                revision.created_by,
                "CREATE_BUSINESS_PROBLEM",
                idempotency_key,
                payload_digest,
                "PROBLEM_REVISION",
                revision.revision_id,
                {"revision_id": revision.revision_id},
            )
        return revision

    def _insert_problem_revision(
        self, connection: Any, revision: BusinessProblemRevision
    ) -> None:
        connection.execute(
            "INSERT INTO business_problem_authority.problem_revisions VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *self._scope(revision.scope),
                revision.business_problem_id,
                revision.revision_id,
                revision.revision,
                revision.predecessor_revision_id,
                revision.digest,
                canonical_bytes(revision.digest_contract()),
                revision.title.strip(),
                revision.description.strip(),
                revision.owner_id,
                revision.created_by,
                revision.created_at,
            ),
        )

    def _read_revision(
        self, connection: Any, scope: ScopeIdentity, revision_id: str
    ) -> BusinessProblemRevision:
        row = connection.execute(
            "SELECT * FROM business_problem_authority.problem_revisions WHERE namespace=%s AND security_domain=%s AND revision_id=%s",
            (*self._scope(scope), revision_id),
        ).fetchone()
        if row is None:
            raise BusinessProblemError("BUSINESS_PROBLEM_NOT_FOUND")
        return self._revision(row)

    def get_problem(
        self, scope: ScopeIdentity, business_problem_id: str, *, authorized: bool
    ) -> tuple[BusinessProblemRevision, ...]:
        self._authorize(authorized)
        with self.pool.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM business_problem_authority.problem_revisions WHERE namespace=%s AND security_domain=%s AND business_problem_id=%s ORDER BY revision",
                (*self._scope(scope), business_problem_id),
            ).fetchall()
        if not rows:
            raise BusinessProblemError("BUSINESS_PROBLEM_NOT_FOUND")
        return tuple(self._revision(row) for row in rows)

    def list_problems(
        self, scope: ScopeIdentity, *, authorized: bool
    ) -> tuple[BusinessProblemRevision, ...]:
        self._authorize(authorized)
        with self.pool.connection() as connection:
            rows = connection.execute(
                "SELECT r.* FROM business_problem_authority.problems p JOIN business_problem_authority.problem_revisions r ON r.namespace=p.namespace AND r.security_domain=p.security_domain AND r.revision_id=p.current_revision_id WHERE p.namespace=%s AND p.security_domain=%s ORDER BY p.updated_at,p.business_problem_id",
                self._scope(scope),
            ).fetchall()
        return tuple(self._revision(row) for row in rows)

    def add_problem_revision(
        self,
        revision: BusinessProblemRevision,
        *,
        expected_version: int,
        idempotency_key: str,
        payload_digest: str,
        authorized: bool,
    ) -> BusinessProblemRevision:
        self._authorize(authorized)
        with self.pool.connection() as connection, connection.transaction():
            replay = self._claim(
                connection,
                revision.scope,
                revision.created_by,
                "CREATE_PROBLEM_REVISION",
                idempotency_key,
                payload_digest,
            )
            if replay:
                return self._read_revision(
                    connection, revision.scope, replay["revision_id"]
                )
            current = connection.execute(
                "SELECT p.aggregate_version,p.current_revision_id,r.revision AS current_revision FROM business_problem_authority.problems p JOIN business_problem_authority.problem_revisions r ON r.namespace=p.namespace AND r.security_domain=p.security_domain AND r.revision_id=p.current_revision_id WHERE p.namespace=%s AND p.security_domain=%s AND p.business_problem_id=%s FOR UPDATE OF p",
                (*self._scope(revision.scope), revision.business_problem_id),
            ).fetchone()
            if current is None:
                raise BusinessProblemError("BUSINESS_PROBLEM_NOT_FOUND")
            if (
                current["aggregate_version"] != expected_version
                or current["current_revision_id"] != revision.predecessor_revision_id
                or revision.revision != current["current_revision"] + 1
            ):
                raise BusinessProblemConflict("BUSINESS_PROBLEM_REVISION_STALE")
            self._insert_problem_revision(connection, revision)
            changed = connection.execute(
                "UPDATE business_problem_authority.problems SET current_revision_id=%s,owner_id=%s,aggregate_version=aggregate_version+1,updated_at=%s WHERE namespace=%s AND security_domain=%s AND business_problem_id=%s AND aggregate_version=%s RETURNING aggregate_version",
                (
                    revision.revision_id,
                    revision.owner_id,
                    revision.created_at,
                    *self._scope(revision.scope),
                    revision.business_problem_id,
                    expected_version,
                ),
            ).fetchone()
            if changed is None:
                raise BusinessProblemConflict("STALE_AGGREGATE_VERSION")
            self._complete(
                connection,
                revision.scope,
                revision.created_by,
                "CREATE_PROBLEM_REVISION",
                idempotency_key,
                payload_digest,
                "PROBLEM_REVISION",
                revision.revision_id,
                {"revision_id": revision.revision_id},
            )
        return revision

    def add_criterion_revision(
        self,
        revision: SuccessCriterionRevision,
        *,
        expected_version: int | None,
        idempotency_key: str,
        payload_digest: str,
        authorized: bool,
    ) -> SuccessCriterionRevision:
        self._authorize(authorized)
        with self.pool.connection() as connection, connection.transaction():
            replay = self._claim(
                connection,
                revision.scope,
                revision.created_by,
                "CREATE_CRITERION_REVISION",
                idempotency_key,
                payload_digest,
            )
            if replay:
                return self._read_criterion(
                    connection, revision.scope, replay["revision_id"]
                )
            if expected_version is None:
                if (
                    revision.revision != 1
                    or revision.predecessor_revision_id is not None
                ):
                    raise BusinessProblemConflict("STALE_AGGREGATE_VERSION")
                connection.execute(
                    "INSERT INTO business_problem_authority.criteria VALUES (%s,%s,%s,1,%s)",
                    (
                        *self._scope(revision.scope),
                        revision.success_criterion_id,
                        revision.revision_id,
                    ),
                )
            else:
                current = connection.execute(
                    "SELECT aggregate_version,current_revision_id FROM business_problem_authority.criteria WHERE namespace=%s AND security_domain=%s AND success_criterion_id=%s FOR UPDATE",
                    (*self._scope(revision.scope), revision.success_criterion_id),
                ).fetchone()
                if (
                    current is None
                    or current["aggregate_version"] != expected_version
                    or current["current_revision_id"]
                    != revision.predecessor_revision_id
                    or revision.revision != expected_version + 1
                ):
                    raise BusinessProblemConflict("STALE_AGGREGATE_VERSION")
            connection.execute(
                "INSERT INTO business_problem_authority.criterion_revisions VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s::jsonb,%s,%s,%s,%s)",
                (
                    *self._scope(revision.scope),
                    revision.success_criterion_id,
                    revision.revision_id,
                    revision.revision,
                    revision.predecessor_revision_id,
                    revision.criterion_type.value,
                    json.dumps(revision.measurement),
                    json.dumps(revision.required_evidence_kinds),
                    revision.evaluator_type,
                    revision.evaluator_version,
                    json.dumps(revision.applicability),
                    revision.digest,
                    canonical_bytes(revision.digest_contract()),
                    revision.created_by,
                    revision.created_at,
                ),
            )
            if expected_version is not None:
                connection.execute(
                    "UPDATE business_problem_authority.criteria SET current_revision_id=%s,aggregate_version=aggregate_version+1 WHERE namespace=%s AND security_domain=%s AND success_criterion_id=%s AND aggregate_version=%s",
                    (
                        revision.revision_id,
                        *self._scope(revision.scope),
                        revision.success_criterion_id,
                        expected_version,
                    ),
                )
            self._complete(
                connection,
                revision.scope,
                revision.created_by,
                "CREATE_CRITERION_REVISION",
                idempotency_key,
                payload_digest,
                "CRITERION_REVISION",
                revision.revision_id,
                {"revision_id": revision.revision_id},
            )
        return revision

    def _read_criterion(
        self, connection: Any, scope: ScopeIdentity, revision_id: str
    ) -> SuccessCriterionRevision:
        row = connection.execute(
            "SELECT * FROM business_problem_authority.criterion_revisions WHERE namespace=%s AND security_domain=%s AND revision_id=%s",
            (*self._scope(scope), revision_id),
        ).fetchone()
        if row is None:
            raise BusinessProblemError("BUSINESS_PROBLEM_NOT_FOUND")
        return SuccessCriterionRevision(
            scope,
            row["success_criterion_id"],
            row["revision_id"],
            row["revision"],
            row["predecessor_revision_id"],
            CriterionType(row["criterion_type"]),
            row["measurement"],
            tuple(row["required_evidence_kinds"]),
            row["evaluator_type"],
            row["evaluator_version"],
            row["applicability"],
            row["created_by"],
            row["created_at"],
            row["digest"],
        )

    def get_criterion_revision(
        self, scope: ScopeIdentity, revision_id: str, *, authorized: bool
    ) -> SuccessCriterionRevision:
        self._authorize(authorized)
        with self.pool.connection() as connection:
            return self._read_criterion(connection, scope, revision_id)

    def add_criteria_set_revision(
        self,
        revision: SuccessCriteriaSetRevision,
        *,
        expected_version: int,
        idempotency_key: str,
        payload_digest: str,
        authorized: bool,
    ) -> SuccessCriteriaSetRevision:
        self._authorize(authorized)
        with self.pool.connection() as connection, connection.transaction():
            replay = self._claim(
                connection,
                revision.scope,
                revision.created_by,
                "CREATE_CRITERIA_SET",
                idempotency_key,
                payload_digest,
            )
            if replay:
                return self._read_set(
                    connection, revision.scope, replay["set_revision_id"]
                )
            problem = connection.execute(
                "SELECT aggregate_version FROM business_problem_authority.problems WHERE namespace=%s AND security_domain=%s AND business_problem_id=%s FOR UPDATE",
                (*self._scope(revision.scope), revision.business_problem_id),
            ).fetchone()
            if problem is None:
                raise BusinessProblemError("BUSINESS_PROBLEM_NOT_FOUND")
            if problem["aggregate_version"] != expected_version:
                raise BusinessProblemConflict("STALE_AGGREGATE_VERSION")
            connection.execute(
                "INSERT INTO business_problem_authority.criteria_sets VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    *self._scope(revision.scope),
                    revision.set_revision_id,
                    revision.business_problem_id,
                    revision.problem_revision_id,
                    revision.revision,
                    revision.predecessor_set_revision_id,
                    revision.digest,
                    canonical_bytes(revision.digest_contract()),
                    revision.created_by,
                    revision.created_at,
                ),
            )
            for ordinal, criterion_id in enumerate(
                revision.ordered_criterion_revision_ids, 1
            ):
                connection.execute(
                    "INSERT INTO business_problem_authority.criteria_set_members VALUES (%s,%s,%s,%s,%s)",
                    (
                        *self._scope(revision.scope),
                        revision.set_revision_id,
                        ordinal,
                        criterion_id,
                    ),
                )
            changed = connection.execute(
                "UPDATE business_problem_authority.problems SET aggregate_version=aggregate_version+1,updated_at=now() WHERE namespace=%s AND security_domain=%s AND business_problem_id=%s AND aggregate_version=%s RETURNING aggregate_version",
                (
                    *self._scope(revision.scope),
                    revision.business_problem_id,
                    expected_version,
                ),
            ).fetchone()
            if changed is None:
                raise BusinessProblemConflict("STALE_AGGREGATE_VERSION")
            self._complete(
                connection,
                revision.scope,
                revision.created_by,
                "CREATE_CRITERIA_SET",
                idempotency_key,
                payload_digest,
                "CRITERIA_SET_REVISION",
                revision.set_revision_id,
                {"set_revision_id": revision.set_revision_id},
            )
        return revision

    def _read_set(
        self, connection: Any, scope: ScopeIdentity, set_id: str
    ) -> SuccessCriteriaSetRevision:
        row = connection.execute(
            "SELECT * FROM business_problem_authority.criteria_sets WHERE namespace=%s AND security_domain=%s AND set_revision_id=%s",
            (*self._scope(scope), set_id),
        ).fetchone()
        if row is None:
            raise BusinessProblemError("BUSINESS_PROBLEM_NOT_FOUND")
        members = connection.execute(
            "SELECT criterion_revision_id FROM business_problem_authority.criteria_set_members WHERE namespace=%s AND security_domain=%s AND set_revision_id=%s ORDER BY ordinal",
            (*self._scope(scope), set_id),
        ).fetchall()
        return SuccessCriteriaSetRevision(
            scope,
            row["set_revision_id"],
            row["business_problem_id"],
            row["problem_revision_id"],
            row["revision"],
            row["predecessor_set_revision_id"],
            tuple(item["criterion_revision_id"] for item in members),
            row["created_by"],
            row["created_at"],
            row["digest"],
        )

    def get_criteria_set_revision(
        self, scope: ScopeIdentity, set_revision_id: str, *, authorized: bool
    ) -> SuccessCriteriaSetRevision:
        self._authorize(authorized)
        with self.pool.connection() as connection:
            return self._read_set(connection, scope, set_revision_id)

    def transition(
        self,
        scope: ScopeIdentity,
        business_problem_id: str,
        to_state: BusinessProblemState,
        *,
        actor_id: str,
        expected_version: int,
        event_id: str,
        idempotency_key: str,
        payload_digest: str,
        authorized: bool,
    ) -> int:
        self._authorize(authorized)
        with self.pool.connection() as connection, connection.transaction():
            replay = self._claim(
                connection,
                scope,
                actor_id,
                "TRANSITION_BUSINESS_PROBLEM",
                idempotency_key,
                payload_digest,
            )
            if replay:
                return int(replay["aggregate_version"])
            row = connection.execute(
                "SELECT current_state,aggregate_version FROM business_problem_authority.problems WHERE namespace=%s AND security_domain=%s AND business_problem_id=%s FOR UPDATE",
                (*self._scope(scope), business_problem_id),
            ).fetchone()
            if row is None:
                raise BusinessProblemError("BUSINESS_PROBLEM_NOT_FOUND")
            current = BusinessProblemState(row["current_state"])
            if to_state not in TRANSITIONS.get(current, set()):
                raise BusinessProblemConflict("BUSINESS_PROBLEM_TRANSITION_INVALID")
            if row["aggregate_version"] != expected_version:
                raise BusinessProblemConflict("STALE_AGGREGATE_VERSION")
            version = expected_version + 1
            event_digest = canonical_digest(
                {
                    "event_id": event_id,
                    "business_problem_id": business_problem_id,
                    "ordinal": version,
                    "from_state": current,
                    "to_state": to_state,
                    "actor_id": actor_id,
                }
            )
            event_type = (
                "REOPENED"
                if current
                in {BusinessProblemState.RESOLVED, BusinessProblemState.CLOSED}
                and to_state is BusinessProblemState.IN_PROGRESS
                else "TRANSITION"
            )
            connection.execute(
                "INSERT INTO business_problem_authority.lifecycle_events(namespace,security_domain,event_id,business_problem_id,ordinal,event_type,from_state,to_state,actor_id,event_digest) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    *self._scope(scope),
                    event_id,
                    business_problem_id,
                    version,
                    event_type,
                    current.value,
                    to_state.value,
                    actor_id,
                    event_digest,
                ),
            )
            connection.execute(
                "UPDATE business_problem_authority.problems SET current_state=%s,aggregate_version=%s,updated_at=now() WHERE namespace=%s AND security_domain=%s AND business_problem_id=%s AND aggregate_version=%s",
                (
                    to_state.value,
                    version,
                    *self._scope(scope),
                    business_problem_id,
                    expected_version,
                ),
            )
            self._complete(
                connection,
                scope,
                actor_id,
                "TRANSITION_BUSINESS_PROBLEM",
                idempotency_key,
                payload_digest,
                "LIFECYCLE_EVENT",
                event_id,
                {"aggregate_version": version},
            )
        return version

    def get_lifecycle(
        self, scope: ScopeIdentity, business_problem_id: str, *, authorized: bool
    ) -> tuple[BusinessProblemLifecycleEvent, ...]:
        self._authorize(authorized)
        with self.pool.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM business_problem_authority.lifecycle_events WHERE namespace=%s AND security_domain=%s AND business_problem_id=%s ORDER BY ordinal",
                (*self._scope(scope), business_problem_id),
            ).fetchall()
        if not rows:
            raise BusinessProblemError("BUSINESS_PROBLEM_NOT_FOUND")
        return tuple(
            BusinessProblemLifecycleEvent(
                row["event_id"],
                row["business_problem_id"],
                row["ordinal"],
                row["event_type"],
                BusinessProblemState(row["from_state"]) if row["from_state"] else None,
                BusinessProblemState(row["to_state"]),
                row["actor_id"],
                row["event_digest"],
                row["occurred_at"],
            )
            for row in rows
        )

    def bind_plan(
        self,
        binding: PlanProblemBinding,
        *,
        expected_problem_version: int,
        idempotency_key: str,
        payload_digest: str,
        authorized: bool,
    ) -> PlanProblemBinding:
        self._authorize(authorized)
        with self.pool.connection() as connection, connection.transaction():
            replay = self._claim(
                connection,
                binding.scope,
                binding.actor_id,
                "BIND_PLAN_TO_PROBLEM",
                idempotency_key,
                payload_digest,
            )
            if replay:
                return self._read_binding(
                    connection, binding.scope, replay["binding_id"]
                )
            problem = connection.execute(
                "SELECT aggregate_version FROM business_problem_authority.problems WHERE namespace=%s AND security_domain=%s AND business_problem_id=%s FOR UPDATE",
                (*self._scope(binding.scope), binding.business_problem_id),
            ).fetchone()
            if problem is None:
                raise BusinessProblemError("BUSINESS_PROBLEM_NOT_FOUND")
            if problem["aggregate_version"] != expected_problem_version:
                raise BusinessProblemConflict("STALE_AGGREGATE_VERSION")
            plan = connection.execute(
                "SELECT status,plan_digest FROM execution_authority.plans WHERE namespace=%s AND security_domain=%s AND plan_id=%s AND plan_version=%s",
                (*self._scope(binding.scope), binding.plan_id, binding.plan_version),
            ).fetchone()
            if (
                plan is None
                or plan["status"] != "APPROVED"
                or plan["plan_digest"] != binding.plan_digest
            ):
                raise BusinessProblemConflict("PLAN_NOT_EXACTLY_APPROVED")
            exact = connection.execute(
                "SELECT r.digest AS problem_digest,s.digest AS set_digest,s.problem_revision_id FROM business_problem_authority.problem_revisions r JOIN business_problem_authority.criteria_sets s ON s.namespace=r.namespace AND s.security_domain=r.security_domain AND s.business_problem_id=r.business_problem_id WHERE r.namespace=%s AND r.security_domain=%s AND r.business_problem_id=%s AND r.revision_id=%s AND s.set_revision_id=%s",
                (
                    *self._scope(binding.scope),
                    binding.business_problem_id,
                    binding.problem_revision_id,
                    binding.criteria_set_revision_id,
                ),
            ).fetchone()
            if (
                exact is None
                or exact["problem_revision_id"] != binding.problem_revision_id
                or exact["problem_digest"] != binding.problem_revision_digest
                or exact["set_digest"] != binding.criteria_set_digest
            ):
                raise BusinessProblemConflict("PLAN_PROBLEM_BINDING_MISMATCH")
            connection.execute(
                "INSERT INTO business_problem_authority.plan_bindings VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    *self._scope(binding.scope),
                    binding.binding_id,
                    binding.plan_id,
                    binding.plan_version,
                    binding.plan_digest,
                    binding.business_problem_id,
                    binding.problem_revision_id,
                    binding.problem_revision_digest,
                    binding.criteria_set_revision_id,
                    binding.criteria_set_digest,
                    binding.actor_id,
                    binding.digest,
                    canonical_bytes(binding.digest_contract()),
                    binding.created_at,
                ),
            )
            self._complete(
                connection,
                binding.scope,
                binding.actor_id,
                "BIND_PLAN_TO_PROBLEM",
                idempotency_key,
                payload_digest,
                "PLAN_BINDING",
                binding.binding_id,
                {"binding_id": binding.binding_id},
            )
        return binding

    def _read_binding(
        self, connection: Any, scope: ScopeIdentity, binding_id: str
    ) -> PlanProblemBinding:
        row = connection.execute(
            "SELECT * FROM business_problem_authority.plan_bindings WHERE namespace=%s AND security_domain=%s AND binding_id=%s",
            (*self._scope(scope), binding_id),
        ).fetchone()
        if row is None:
            raise BusinessProblemError("BUSINESS_PROBLEM_NOT_FOUND")
        return PlanProblemBinding(
            scope,
            row["binding_id"],
            row["plan_id"],
            row["plan_version"],
            row["plan_digest"],
            row["business_problem_id"],
            row["problem_revision_id"],
            row["problem_revision_digest"],
            row["criteria_set_revision_id"],
            row["criteria_set_digest"],
            row["actor_id"],
            row["created_at"],
            row["digest"],
        )

    def get_plan_binding(
        self, scope: ScopeIdentity, binding_id: str, *, authorized: bool
    ) -> PlanProblemBinding:
        self._authorize(authorized)
        with self.pool.connection() as connection:
            return self._read_binding(connection, scope, binding_id)
