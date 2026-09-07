# ruff: noqa: E501
"""PostgreSQL authority for immutable Attempt Resource Use history."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_core.execution_contract import ScopeIdentity
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .resource_use_domain import (
    EffectiveUseState,
    MeasurementAvailability,
    ResourceKind,
    ResourceMeasurement,
    ResourceUseBinding,
    ResourceUseConflict,
    ResourceUseError,
    ResourceUseFact,
    ResourceUseFactKind,
    ResourceUseSnapshot,
    canonical_digest,
    canonical_record,
    reduce_resource_use,
)

ADAPTER = "resource-use-postgresql-v1"


class PostgresResourceUseRepository:
    def __init__(self, database_url: str, *, migration_path: Path, timeout: float = 5):
        self.migration_path = migration_path
        self.migration_checksum = hashlib.sha256(
            migration_path.read_bytes()
        ).hexdigest()
        self.pool = ConnectionPool(
            database_url,
            min_size=1,
            max_size=6,
            timeout=timeout,
            kwargs={"row_factory": dict_row, "autocommit": False},
            open=True,
        )
        self.pool.wait(timeout=timeout)

    def close(self) -> None:
        self.pool.close()

    def migrate(self) -> None:
        with self.pool.connection() as connection, connection.transaction():
            connection.execute(self.migration_path.read_text())
            row = connection.execute(
                "SELECT checksum,adapter FROM resource_use.schema_migrations WHERE version=15"
            ).fetchone()
            expected = {"checksum": self.migration_checksum, "adapter": ADAPTER}
            if row is None:
                connection.execute(
                    "INSERT INTO resource_use.schema_migrations(version,checksum,adapter) VALUES(15,%s,%s)",
                    (self.migration_checksum, ADAPTER),
                )
            elif row != expected:
                raise ResourceUseError("RESOURCE_USE_SCHEMA_INCOMPATIBLE")

    @staticmethod
    def _scope(scope: ScopeIdentity) -> tuple[str, str]:
        return scope.namespace, scope.security_domain

    @staticmethod
    def _record(value: Any) -> dict[str, Any]:
        return canonical_record(value)

    def prepare_dispatch(
        self,
        binding: ResourceUseBinding,
        facts: tuple[ResourceUseFact, ...],
        *,
        idempotency_key: str,
        payload_digest: str,
    ) -> ResourceUseSnapshot:
        if not facts or any(
            f.resource_use_id != binding.resource_use_id for f in facts
        ):
            raise ResourceUseError("RESOURCE_USE_FACTS_INVALID")
        if payload_digest != canonical_digest(
            {
                "binding": self._record(binding),
                "facts": [self._record(f) for f in facts],
            }
        ):
            raise ResourceUseError("RESOURCE_USE_PAYLOAD_DIGEST_MISMATCH")
        with self.pool.connection() as connection, connection.transaction():
            replay = self._replay(
                connection, binding.scope, idempotency_key, payload_digest
            )
            if replay is not None:
                return replay
            b = binding
            connection.execute(
                """INSERT INTO resource_use.uses(
                namespace,security_domain,resource_use_id,attempt_id,resource_kind,slot_key,
                occurrence_ordinal,resource_id,resource_revision_id,resource_digest,binding_id,
                binding_digest,plan_id,plan_version,plan_digest,workflow_run_id,task_run_id,
                digital_employee_definition_id,digital_employee_definition_revision_id,
                digital_employee_definition_digest,digital_employee_instance_id,agent_instance_id,
                runtime_instance_id,executor_id,executor_revision,provider_id,provider_revision,
                authorization_decision_id,predecessor_attempt_id,predecessor_workflow_run_id,
                payload_digest,record) VALUES (
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                (
                    *self._scope(b.scope),
                    b.resource_use_id,
                    b.attempt_id,
                    b.resource_kind.value,
                    b.slot_key,
                    b.occurrence_ordinal,
                    b.resource_id,
                    b.resource_revision_id,
                    b.resource_digest,
                    b.binding_id,
                    b.binding_digest,
                    b.plan_id,
                    b.plan_version,
                    b.plan_digest,
                    b.workflow_run_id,
                    b.task_run_id,
                    b.digital_employee_definition_id,
                    b.digital_employee_definition_revision_id,
                    b.digital_employee_definition_digest,
                    b.digital_employee_instance_id,
                    b.agent_instance_id,
                    b.runtime_instance_id,
                    b.executor_id,
                    b.executor_revision,
                    b.provider_id,
                    b.provider_revision,
                    b.authorization_decision_id,
                    b.predecessor_attempt_id,
                    b.predecessor_workflow_run_id,
                    b.payload_digest,
                    json.dumps(self._record(b)),
                ),
            )
            self._insert_facts(connection, b.scope, facts, 0)
            snapshot = reduce_resource_use(
                b.resource_use_id, facts, (), high_water=len(facts)
            )
            self._insert_snapshot(connection, b.scope, snapshot)
            connection.execute(
                "INSERT INTO resource_use.high_waters(namespace,security_domain,resource_use_id,high_water,version) VALUES(%s,%s,%s,%s,1)",
                (*self._scope(b.scope), b.resource_use_id, len(facts)),
            )
            self._insert_idempotency(
                connection, b.scope, idempotency_key, payload_digest, snapshot
            )
            return snapshot

    def commit_observation(
        self,
        scope: ScopeIdentity,
        resource_use_id: str,
        facts: tuple[ResourceUseFact, ...],
        measurements: tuple[ResourceMeasurement, ...],
        *,
        evidence_records: tuple[dict[str, object], ...],
        claim: dict[str, object],
        idempotency_key: str,
        payload_digest: str,
        expected_high_water: int,
    ) -> ResourceUseSnapshot:
        semantic = {
            "resourceUseId": resource_use_id,
            "facts": [self._record(f) for f in facts],
            "measurements": [self._record(m) for m in measurements],
            "evidence": evidence_records,
            "claim": claim,
            "expectedHighWater": expected_high_water,
        }
        if payload_digest != canonical_digest(semantic):
            raise ResourceUseError("RESOURCE_USE_PAYLOAD_DIGEST_MISMATCH")
        with self.pool.connection() as connection, connection.transaction():
            replay = self._replay(connection, scope, idempotency_key, payload_digest)
            if replay is not None:
                return replay
            row = connection.execute(
                "SELECT high_water,version FROM resource_use.high_waters WHERE namespace=%s AND security_domain=%s AND resource_use_id=%s FOR UPDATE",
                (*self._scope(scope), resource_use_id),
            ).fetchone()
            if row is None:
                raise ResourceUseError("RESOURCE_USE_NOT_FOUND")
            if row["high_water"] != expected_high_water:
                raise ResourceUseConflict("RESOURCE_USE_CAS_MISMATCH")
            self._insert_facts(connection, scope, facts, expected_high_water)
            for item in measurements:
                connection.execute(
                    """INSERT INTO resource_use.measurements(namespace,security_domain,resource_use_id,
                    measurement_id,metric,value,unit,availability,source_identity,source_digest,
                    window_started_at,window_ended_at,observed_at,record)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                    (
                        *self._scope(scope),
                        resource_use_id,
                        item.measurement_id,
                        item.metric,
                        item.value,
                        item.unit,
                        item.availability.value,
                        item.source_identity,
                        item.source_digest,
                        item.window_started_at,
                        item.window_ended_at,
                        item.observed_at,
                        json.dumps(self._record(item)),
                    ),
                )
            for item in evidence_records:
                connection.execute(
                    """INSERT INTO resource_use.evidence_references(namespace,security_domain,
                    resource_use_id,evidence_id,evidence_digest,evidence_kind,record)
                    VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                    (
                        *self._scope(scope),
                        resource_use_id,
                        item["evidenceId"],
                        item["evidenceDigest"],
                        item["evidenceKind"],
                        json.dumps(item),
                    ),
                )
            connection.execute(
                """INSERT INTO resource_use.claims(namespace,security_domain,resource_use_id,
                claim_id,claim_digest,record) VALUES(%s,%s,%s,%s,%s,%s::jsonb)""",
                (
                    *self._scope(scope),
                    resource_use_id,
                    claim["claimId"],
                    claim["claimDigest"],
                    json.dumps(claim),
                ),
            )
            all_facts = self._facts(connection, scope, resource_use_id)
            all_measurements = self._measurements(connection, scope, resource_use_id)
            high_water = expected_high_water + len(facts)
            snapshot = reduce_resource_use(
                resource_use_id, all_facts, all_measurements, high_water=high_water
            )
            updated = connection.execute(
                """UPDATE resource_use.high_waters SET high_water=%s,version=version+1
                WHERE namespace=%s AND security_domain=%s AND resource_use_id=%s AND version=%s""",
                (high_water, *self._scope(scope), resource_use_id, row["version"]),
            )
            if updated.rowcount != 1:
                raise ResourceUseConflict("RESOURCE_USE_CAS_MISMATCH")
            self._insert_snapshot(connection, scope, snapshot)
            self._insert_idempotency(
                connection, scope, idempotency_key, payload_digest, snapshot
            )
            return snapshot

    def _replay(self, connection, scope, key, digest):
        row = connection.execute(
            "SELECT payload_digest,snapshot_id FROM resource_use.idempotency WHERE namespace=%s AND security_domain=%s AND idempotency_key=%s",
            (*self._scope(scope), key),
        ).fetchone()
        if row is None:
            return None
        if row["payload_digest"] != digest:
            raise ResourceUseConflict("RESOURCE_USE_IDEMPOTENCY_PAYLOAD_MISMATCH")
        return self._snapshot_by_id(connection, scope, row["snapshot_id"])

    def _insert_facts(self, connection, scope, facts, offset):
        for index, fact in enumerate(facts, offset + 1):
            connection.execute(
                """INSERT INTO resource_use.facts(namespace,security_domain,resource_use_id,
                ordinal,fact_id,kind,source_owner,source_observation_id,source_digest,observed_at,
                recorded_at,supersedes_fact_id,record) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                (
                    *self._scope(scope),
                    fact.resource_use_id,
                    index,
                    fact.fact_id,
                    fact.kind.value,
                    fact.source_owner,
                    fact.source_observation_id,
                    fact.source_digest,
                    fact.observed_at,
                    fact.recorded_at,
                    fact.supersedes_fact_id,
                    json.dumps(self._record(fact)),
                ),
            )

    def _insert_snapshot(self, connection, scope, snapshot):
        connection.execute(
            """INSERT INTO resource_use.snapshots(namespace,security_domain,resource_use_id,
            snapshot_id,digest,high_water,reducer_version,record,created_at)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
            (
                *self._scope(scope),
                snapshot.resource_use_id,
                snapshot.snapshot_id,
                snapshot.digest,
                snapshot.high_water,
                snapshot.reducer_version,
                json.dumps(self._record(snapshot)),
                snapshot.created_at,
            ),
        )

    def _insert_idempotency(self, connection, scope, key, digest, snapshot):
        connection.execute(
            "INSERT INTO resource_use.idempotency(namespace,security_domain,idempotency_key,payload_digest,resource_use_id,snapshot_id) VALUES(%s,%s,%s,%s,%s,%s)",
            (
                *self._scope(scope),
                key,
                digest,
                snapshot.resource_use_id,
                snapshot.snapshot_id,
            ),
        )

    def _facts(self, connection, scope, resource_use_id):
        rows = connection.execute(
            "SELECT record FROM resource_use.facts WHERE namespace=%s AND security_domain=%s AND resource_use_id=%s ORDER BY ordinal",
            (*self._scope(scope), resource_use_id),
        ).fetchall()
        return tuple(self._fact(row["record"]) for row in rows)

    def _measurements(self, connection, scope, resource_use_id):
        rows = connection.execute(
            "SELECT record FROM resource_use.measurements WHERE namespace=%s AND security_domain=%s AND resource_use_id=%s ORDER BY measurement_id",
            (*self._scope(scope), resource_use_id),
        ).fetchall()
        return tuple(self._measurement(row["record"]) for row in rows)

    @staticmethod
    def _fact(record):
        return ResourceUseFact(
            **{
                **record,
                "kind": ResourceUseFactKind(record["kind"]),
                "observed_at": datetime.fromisoformat(record["observed_at"]),
                "recorded_at": datetime.fromisoformat(record["recorded_at"]),
                "evidence_references": tuple(record["evidence_references"]),
                "limitation_codes": tuple(record["limitation_codes"]),
            }
        )

    @staticmethod
    def _measurement(record):
        for key in ("window_started_at", "window_ended_at", "observed_at"):
            record[key] = datetime.fromisoformat(record[key])
        record["availability"] = MeasurementAvailability(record["availability"])
        record["limitations"] = tuple(record["limitations"])
        record["evidence_references"] = tuple(record["evidence_references"])
        return ResourceMeasurement(**record)

    @staticmethod
    def _snapshot(record):
        return ResourceUseSnapshot(
            **{
                **record,
                "effective_state": EffectiveUseState(record["effective_state"]),
                "fact_ids": tuple(record["fact_ids"]),
                "measurement_ids": tuple(record["measurement_ids"]),
                "evidence_references": tuple(record["evidence_references"]),
                "limitation_codes": tuple(record["limitation_codes"]),
                "conflicts": tuple(record["conflicts"]),
                "created_at": datetime.fromisoformat(record["created_at"]),
            }
        )

    def _snapshot_by_id(self, connection, scope, snapshot_id):
        row = connection.execute(
            "SELECT record FROM resource_use.snapshots WHERE namespace=%s AND security_domain=%s AND snapshot_id=%s",
            (*self._scope(scope), snapshot_id),
        ).fetchone()
        if row is None:
            raise ResourceUseError("RESOURCE_USE_NOT_FOUND")
        return self._snapshot(row["record"])

    def get_binding(self, scope, resource_use_id):
        with self.pool.connection() as connection:
            row = connection.execute(
                "SELECT record FROM resource_use.uses WHERE namespace=%s AND security_domain=%s AND resource_use_id=%s",
                (*self._scope(scope), resource_use_id),
            ).fetchone()
        if row is None:
            return None
        record = row["record"]
        record["scope"] = scope
        record["resource_kind"] = ResourceKind(record["resource_kind"])
        return ResourceUseBinding(**record)

    def get_snapshot(self, scope, resource_use_id):
        with self.pool.connection() as connection:
            row = connection.execute(
                "SELECT record FROM resource_use.snapshots WHERE namespace=%s AND security_domain=%s AND resource_use_id=%s ORDER BY high_water DESC LIMIT 1",
                (*self._scope(scope), resource_use_id),
            ).fetchone()
        return None if row is None else self._snapshot(row["record"])

    def list_snapshots(self, scope):
        with self.pool.connection() as connection:
            rows = connection.execute(
                """SELECT DISTINCT ON(resource_use_id) record FROM resource_use.snapshots
                WHERE namespace=%s AND security_domain=%s ORDER BY resource_use_id,high_water DESC""",
                self._scope(scope),
            ).fetchall()
        return tuple(self._snapshot(row["record"]) for row in rows)

    def count(self, scope):
        with self.pool.connection() as connection:
            return connection.execute(
                "SELECT count(*) AS count FROM resource_use.uses WHERE namespace=%s AND security_domain=%s",
                self._scope(scope),
            ).fetchone()["count"]
