"""PostgreSQL adapters for Draft Assistance and its owner-separated facts."""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from psycopg import Error as PsycopgError
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from agent_console.draft_assistance import (
    AuthorizationState,
    DraftAssistanceError,
    DraftAuthorization,
    DraftBindingSnapshot,
    DraftInvocation,
    DraftInvocationState,
    DraftResultKind,
    DraftScope,
    ObservationState,
)
from agent_console.draft_assistance_support import (
    ContextualResourceUseRecord,
    ModelDraftEvidence,
)
from agent_console.model_binding_resolution import ExactModelBinding

ADAPTER = "draft-assistance-postgresql-v23"
MIGRATION_VERSION = 23


def _json_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _record(value: DraftInvocation) -> dict[str, Any]:
    authorization = value.authorization
    snapshot = value.snapshot
    return {
        "contextId": value.context_id,
        "turnId": value.turn_id,
        "turnOrdinal": value.turn_ordinal,
        "turnVersion": value.turn_version,
        "invocationId": value.invocation_id,
        "snapshotCandidateId": value.snapshot_candidate_id,
        "scope": [value.scope.namespace, value.scope.security_domain],
        "initiatingPrincipalId": value.initiating_principal_id,
        "scopedIdempotencyKey": value.scoped_idempotency_key,
        "commitment": value.commitment,
        "commitmentAlgorithm": value.commitment_algorithm,
        "canonicalizationVersion": value.canonicalization_version,
        "pepperReference": value.pepper_reference,
        "pepperVersion": value.pepper_version,
        "createdAt": value.created_at.isoformat(),
        "replayNotAfter": value.replay_not_after.isoformat(),
        "profileRevisionId": value.profile_revision_id,
        "requestTarget": value.request_target,
        "modelTarget": value.model_target,
        "parentTurnId": value.parent_turn_id,
        "predecessorInvocationId": value.predecessor_invocation_id,
        "state": value.state.value,
        "aggregateVersion": value.aggregate_version,
        "authorization": (
            None
            if authorization is None
            else {
                "state": authorization.state.value,
                "requestAuthorizationRequestId": (
                    authorization.request_authorization_request_id
                ),
                "modelAuthorizationRequestId": (
                    authorization.model_authorization_request_id
                ),
                "requestDecisionId": authorization.request_decision_id,
                "modelDecisionId": authorization.model_decision_id,
                "requestVersion": authorization.request_version,
                "modelVersion": authorization.model_version,
            }
        ),
        "snapshot": (
            None
            if snapshot is None
            else {
                "snapshotId": snapshot.snapshot_id,
                "snapshotDigest": snapshot.snapshot_digest,
                "profileRevisionId": snapshot.profile_revision_id,
                "profileDigest": snapshot.profile_digest,
                "modelBinding": {
                    "resourceId": snapshot.model_binding.resource_id,
                    "revisionId": snapshot.model_binding.revision_id,
                    "digest": snapshot.model_binding.digest,
                },
                "provider": {
                    "id": snapshot.provider_id,
                    "revisionId": snapshot.provider_revision_id,
                    "digest": snapshot.provider_digest,
                },
                "endpoint": {
                    "id": snapshot.endpoint_id,
                    "revisionId": snapshot.endpoint_revision_id,
                    "digest": snapshot.endpoint_digest,
                },
                "connectionProfile": {
                    "id": snapshot.connection_profile_id,
                    "revisionId": snapshot.connection_profile_revision_id,
                    "digest": snapshot.connection_profile_digest,
                },
                "adapter": {
                    "id": snapshot.adapter_id,
                    "revision": snapshot.adapter_revision,
                },
                "eligibilityHighWater": snapshot.eligibility_high_water,
            }
        ),
        "admissionId": value.admission_id,
        "dispatchFence": value.dispatch_fence,
        "budgetReservationId": value.budget_reservation_id,
        "providerCorrelation": value.provider_correlation,
        "measurement": value.measurement,
        "pricing": value.pricing,
        "settlementStatus": value.settlement_status,
        "localCleanup": value.local_cleanup,
        "terminalObservationId": value.terminal_observation_id,
        "lastObservationId": value.last_observation_id,
        "resultKind": value.result_kind.value if value.result_kind else None,
        "reasonCode": value.reason_code,
        "ownerWriteReasonCode": value.owner_write_reason_code,
        "lastObservationState": (
            value.last_observation_state.value if value.last_observation_state else None
        ),
        "lastObservationLatencyMs": value.last_observation_latency_ms,
        "lastObservationInputTokens": value.last_observation_input_tokens,
        "lastObservationOutputTokens": value.last_observation_output_tokens,
        "contentDisposition": value.content_disposition,
        "resourceUseId": value.resource_use_id,
        "evidenceId": value.evidence_id,
        "problemId": value.problem_id,
        "problemRevisionId": value.problem_revision_id,
        "problemDigest": value.problem_digest,
    }


def _invocation(value: dict[str, Any]) -> DraftInvocation:
    authorization = value["authorization"]
    snapshot = value["snapshot"]
    return DraftInvocation(
        context_id=value["contextId"],
        turn_id=value["turnId"],
        turn_ordinal=value["turnOrdinal"],
        turn_version=value["turnVersion"],
        invocation_id=value["invocationId"],
        snapshot_candidate_id=value["snapshotCandidateId"],
        scope=DraftScope(*value["scope"]),
        initiating_principal_id=value["initiatingPrincipalId"],
        scoped_idempotency_key=value["scopedIdempotencyKey"],
        commitment=value["commitment"],
        commitment_algorithm=value["commitmentAlgorithm"],
        canonicalization_version=value["canonicalizationVersion"],
        pepper_reference=value["pepperReference"],
        pepper_version=value["pepperVersion"],
        created_at=datetime.fromisoformat(value["createdAt"]),
        replay_not_after=datetime.fromisoformat(value["replayNotAfter"]),
        profile_revision_id=value["profileRevisionId"],
        request_target=value["requestTarget"],
        model_target=value["modelTarget"],
        parent_turn_id=value["parentTurnId"],
        predecessor_invocation_id=value["predecessorInvocationId"],
        state=DraftInvocationState(value["state"]),
        aggregate_version=value["aggregateVersion"],
        authorization=(
            None
            if authorization is None
            else DraftAuthorization(
                AuthorizationState(authorization["state"]),
                authorization["requestAuthorizationRequestId"],
                authorization["modelAuthorizationRequestId"],
                authorization["requestDecisionId"],
                authorization["modelDecisionId"],
                authorization["requestVersion"],
                authorization["modelVersion"],
            )
        ),
        snapshot=(
            None
            if snapshot is None
            else DraftBindingSnapshot(
                snapshot["snapshotId"],
                snapshot["snapshotDigest"],
                snapshot["profileRevisionId"],
                snapshot["profileDigest"],
                ExactModelBinding(
                    snapshot["modelBinding"]["resourceId"],
                    snapshot["modelBinding"]["revisionId"],
                    snapshot["modelBinding"]["digest"],
                ),
                snapshot["provider"]["id"],
                snapshot["provider"]["revisionId"],
                snapshot["provider"]["digest"],
                snapshot["endpoint"]["id"],
                snapshot["endpoint"]["revisionId"],
                snapshot["endpoint"]["digest"],
                snapshot["connectionProfile"]["id"],
                snapshot["connectionProfile"]["revisionId"],
                snapshot["connectionProfile"]["digest"],
                snapshot["adapter"]["id"],
                snapshot["adapter"]["revision"],
                snapshot["eligibilityHighWater"],
            )
        ),
        admission_id=value["admissionId"],
        dispatch_fence=value["dispatchFence"],
        budget_reservation_id=value.get("budgetReservationId"),
        provider_correlation=value["providerCorrelation"],
        measurement=value.get("measurement"),
        pricing=value.get("pricing"),
        settlement_status=value.get("settlementStatus", "NOT_MEASURED"),
        local_cleanup=value.get("localCleanup"),
        terminal_observation_id=value["terminalObservationId"],
        last_observation_id=value.get("lastObservationId"),
        result_kind=(
            DraftResultKind(value["resultKind"]) if value["resultKind"] else None
        ),
        reason_code=value["reasonCode"],
        owner_write_reason_code=value.get("ownerWriteReasonCode"),
        last_observation_state=(
            ObservationState(value["lastObservationState"])
            if value.get("lastObservationState")
            else None
        ),
        last_observation_latency_ms=value.get("lastObservationLatencyMs"),
        last_observation_input_tokens=value.get("lastObservationInputTokens"),
        last_observation_output_tokens=value.get("lastObservationOutputTokens"),
        content_disposition=value["contentDisposition"],
        resource_use_id=value["resourceUseId"],
        evidence_id=value["evidenceId"],
        problem_id=value["problemId"],
        problem_revision_id=value["problemRevisionId"],
        problem_digest=value["problemDigest"],
    )


class _Pool:
    def __init__(self, database_url: str, *, timeout: float = 5.0) -> None:
        if not database_url:
            raise DraftAssistanceError("DRAFT_STORAGE_UNAVAILABLE")
        self.pool = ConnectionPool(
            database_url,
            min_size=1,
            max_size=4,
            timeout=timeout,
            kwargs={"row_factory": dict_row, "autocommit": False},
            open=True,
        )
        self.pool.wait(timeout=timeout)

    @contextmanager
    def connection_scope(self):
        with self.pool.connection() as connection, connection.transaction():
            yield connection

    def close(self) -> None:
        self.pool.close()


class PostgresDraftAssistanceRepository(_Pool):
    def __init__(
        self, database_url: str, *, migration_path: Path, timeout: float = 5.0
    ) -> None:
        self.migration_path = migration_path
        super().__init__(database_url, timeout=timeout)

    @property
    def migration_checksum(self) -> str:
        return hashlib.sha256(self.migration_path.read_bytes()).hexdigest()

    def migrate(self) -> None:
        if not self.migration_path.name.startswith("0023_"):
            raise DraftAssistanceError("DRAFT_SCHEMA_INCOMPATIBLE")
        try:
            with self.connection_scope() as connection:
                connection.execute("SET LOCAL statement_timeout='30s'")
                connection.execute("SET LOCAL lock_timeout='3s'")
                connection.execute(self.migration_path.read_text())
                newer = connection.execute(
                    "SELECT version FROM draft_assistance.schema_migrations "
                    "WHERE version>%s ORDER BY version LIMIT 1",
                    (MIGRATION_VERSION,),
                ).fetchone()
                if newer is not None:
                    raise DraftAssistanceError("DRAFT_SCHEMA_INCOMPATIBLE")
                row = connection.execute(
                    "SELECT checksum,adapter FROM draft_assistance.schema_migrations "
                    "WHERE version=%s",
                    (MIGRATION_VERSION,),
                ).fetchone()
                expected = {"checksum": self.migration_checksum, "adapter": ADAPTER}
                if row is None:
                    connection.execute(
                        "INSERT INTO draft_assistance.schema_migrations"
                        "(version,checksum,adapter) VALUES(%s,%s,%s)",
                        (MIGRATION_VERSION, self.migration_checksum, ADAPTER),
                    )
                elif row != expected:
                    raise DraftAssistanceError("DRAFT_SCHEMA_INCOMPATIBLE")
        except DraftAssistanceError:
            raise
        except (OSError, PsycopgError) as exc:
            raise DraftAssistanceError("DRAFT_STORAGE_UNAVAILABLE") from exc

    @staticmethod
    def _latest(connection, scope: DraftScope, invocation_id: str):
        row = connection.execute(
            "SELECT record FROM draft_assistance.invocation_versions "
            "WHERE namespace=%s AND security_domain=%s AND invocation_id=%s "
            "ORDER BY aggregate_version DESC LIMIT 1",
            (scope.namespace, scope.security_domain, invocation_id),
        ).fetchone()
        return None if row is None else _invocation(row["record"])

    def claim(self, candidate: DraftInvocation) -> tuple[DraftInvocation, bool]:
        values = (
            candidate.scope.namespace,
            candidate.scope.security_domain,
            candidate.initiating_principal_id,
            "REQUEST_DRAFT_ASSISTANCE",
            candidate.scoped_idempotency_key,
            candidate.invocation_id,
            candidate.commitment,
            candidate.commitment_algorithm,
            candidate.canonicalization_version,
            candidate.pepper_reference,
            candidate.pepper_version,
            candidate.created_at,
            candidate.replay_not_after,
        )
        try:
            with self.connection_scope() as connection:
                inserted = connection.execute(
                    "INSERT INTO draft_assistance.idempotency_claims"
                    "(namespace,security_domain,initiating_principal_id,action,"
                    "scoped_idempotency_key,invocation_id,commitment,"
                    "commitment_algorithm,canonicalization_version,pepper_reference,"
                    "pepper_version,created_at,replay_not_after) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT DO NOTHING RETURNING invocation_id",
                    values,
                ).fetchone()
                if inserted is None:
                    existing = connection.execute(
                        "SELECT invocation_id FROM draft_assistance.idempotency_claims "
                        "WHERE namespace=%s AND security_domain=%s "
                        "AND initiating_principal_id=%s "
                        "AND action='REQUEST_DRAFT_ASSISTANCE' "
                        "AND scoped_idempotency_key=%s",
                        (
                            candidate.scope.namespace,
                            candidate.scope.security_domain,
                            candidate.initiating_principal_id,
                            candidate.scoped_idempotency_key,
                        ),
                    ).fetchone()
                    current = self._latest(
                        connection, candidate.scope, existing["invocation_id"]
                    )
                    if current is None:
                        raise DraftAssistanceError("DRAFT_STORAGE_UNAVAILABLE")
                    return current, False
                connection.execute(
                    "INSERT INTO draft_assistance.contexts"
                    "(namespace,security_domain,context_id,"
                    "initiating_principal_id,created_at) "
                    "VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    (
                        candidate.scope.namespace,
                        candidate.scope.security_domain,
                        candidate.context_id,
                        candidate.initiating_principal_id,
                        candidate.created_at,
                    ),
                )
                connection.execute(
                    "INSERT INTO draft_assistance.turns"
                    "(namespace,security_domain,context_id,turn_id,ordinal,version,"
                    "parent_turn_id,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        candidate.scope.namespace,
                        candidate.scope.security_domain,
                        candidate.context_id,
                        candidate.turn_id,
                        candidate.turn_ordinal,
                        candidate.turn_version,
                        candidate.parent_turn_id,
                        candidate.created_at,
                    ),
                )
                connection.execute(
                    "INSERT INTO draft_assistance.invocations"
                    "(namespace,security_domain,invocation_id,context_id,turn_id,"
                    "initiating_principal_id,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                    (
                        candidate.scope.namespace,
                        candidate.scope.security_domain,
                        candidate.invocation_id,
                        candidate.context_id,
                        candidate.turn_id,
                        candidate.initiating_principal_id,
                        candidate.created_at,
                    ),
                )
                connection.execute(
                    "INSERT INTO draft_assistance.invocation_versions"
                    "(namespace,security_domain,invocation_id,"
                    "aggregate_version,state,record) "
                    "VALUES(%s,%s,%s,%s,%s,%s)",
                    (
                        candidate.scope.namespace,
                        candidate.scope.security_domain,
                        candidate.invocation_id,
                        candidate.aggregate_version,
                        candidate.state.value,
                        Jsonb(_record(candidate)),
                    ),
                )
                return candidate, True
        except DraftAssistanceError:
            raise
        except PsycopgError as exc:
            raise DraftAssistanceError("DRAFT_STORAGE_UNAVAILABLE") from exc

    def get(self, scope: DraftScope, invocation_id: str) -> DraftInvocation | None:
        try:
            with self.connection_scope() as connection:
                return self._latest(connection, scope, invocation_id)
        except PsycopgError as exc:
            raise DraftAssistanceError("DRAFT_STORAGE_UNAVAILABLE") from exc

    def get_by_key(
        self, scope: DraftScope, principal_id: str, key: str
    ) -> DraftInvocation | None:
        try:
            with self.connection_scope() as connection:
                row = connection.execute(
                    "SELECT invocation_id FROM draft_assistance.idempotency_claims "
                    "WHERE namespace=%s AND security_domain=%s "
                    "AND initiating_principal_id=%s "
                    "AND action='REQUEST_DRAFT_ASSISTANCE' "
                    "AND scoped_idempotency_key=%s",
                    (scope.namespace, scope.security_domain, principal_id, key),
                ).fetchone()
                return (
                    None
                    if row is None
                    else self._latest(connection, scope, row["invocation_id"])
                )
        except PsycopgError as exc:
            raise DraftAssistanceError("DRAFT_STORAGE_UNAVAILABLE") from exc

    def find_by_target(
        self, scope: DraftScope, principal_id: str, target: str
    ) -> DraftInvocation | None:
        try:
            with self.connection_scope() as connection:
                rows = connection.execute(
                    "SELECT DISTINCT ON (v.invocation_id) v.record "
                    "FROM draft_assistance.invocation_versions v "
                    "JOIN draft_assistance.invocations i USING "
                    "(namespace,security_domain,invocation_id) "
                    "WHERE v.namespace=%s AND v.security_domain=%s "
                    "AND i.initiating_principal_id=%s "
                    "ORDER BY v.invocation_id,v.aggregate_version DESC",
                    (scope.namespace, scope.security_domain, principal_id),
                ).fetchall()
                return next(
                    (
                        value
                        for value in (_invocation(row["record"]) for row in rows)
                        if target
                        in {
                            value.request_target,
                            value.model_target,
                            f"draft-assistance:invocation:{value.invocation_id}",
                        }
                    ),
                    None,
                )
        except PsycopgError as exc:
            raise DraftAssistanceError("DRAFT_STORAGE_UNAVAILABLE") from exc

    def get_context_head(
        self, scope: DraftScope, context_id: str
    ) -> DraftInvocation | None:
        try:
            with self.connection_scope() as connection:
                row = connection.execute(
                    "SELECT i.invocation_id FROM draft_assistance.invocations i "
                    "JOIN draft_assistance.turns t USING "
                    "(namespace,security_domain,context_id,turn_id) "
                    "WHERE i.namespace=%s AND i.security_domain=%s "
                    "AND i.context_id=%s ORDER BY t.ordinal DESC LIMIT 1",
                    (scope.namespace, scope.security_domain, context_id),
                ).fetchone()
                return (
                    None
                    if row is None
                    else self._latest(connection, scope, row["invocation_id"])
                )
        except PsycopgError as exc:
            raise DraftAssistanceError("DRAFT_STORAGE_UNAVAILABLE") from exc

    def compare_and_set(
        self, expected_version: int, replacement: DraftInvocation
    ) -> DraftInvocation | None:
        try:
            with self.connection_scope() as connection:
                row = connection.execute(
                    "SELECT invocation_id FROM draft_assistance.invocations "
                    "WHERE namespace=%s AND security_domain=%s AND invocation_id=%s "
                    "FOR UPDATE",
                    (
                        replacement.scope.namespace,
                        replacement.scope.security_domain,
                        replacement.invocation_id,
                    ),
                ).fetchone()
                if row is None:
                    return None
                current = self._latest(
                    connection, replacement.scope, replacement.invocation_id
                )
                if current is None or current.aggregate_version != expected_version:
                    return None
                connection.execute(
                    "INSERT INTO draft_assistance.invocation_versions"
                    "(namespace,security_domain,invocation_id,"
                    "aggregate_version,state,record) "
                    "VALUES(%s,%s,%s,%s,%s,%s)",
                    (
                        replacement.scope.namespace,
                        replacement.scope.security_domain,
                        replacement.invocation_id,
                        replacement.aggregate_version,
                        replacement.state.value,
                        Jsonb(_record(replacement)),
                    ),
                )
                return replacement
        except PsycopgError as exc:
            raise DraftAssistanceError("DRAFT_STORAGE_UNAVAILABLE") from exc


class PostgresContextualResourceUseOwner(_Pool):
    @staticmethod
    def _scope(invocation: DraftInvocation) -> tuple[str, str]:
        return invocation.scope.namespace, invocation.scope.security_domain

    def _operation(self, connection, scope, operation_id, payload, resource_use_id):
        digest = _json_digest(payload)
        row = connection.execute(
            "INSERT INTO contextual_resource_use.operations"
            "(namespace,security_domain,operation_id,payload_digest,"
            "resource_use_id,record) "
            "VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING "
            "RETURNING operation_id",
            (*scope, operation_id, digest, resource_use_id, Jsonb(payload)),
        ).fetchone()
        if row is None:
            existing = connection.execute(
                "SELECT payload_digest,resource_use_id FROM "
                "contextual_resource_use.operations WHERE namespace=%s "
                "AND security_domain=%s AND operation_id=%s",
                (*scope, operation_id),
            ).fetchone()
            if existing != {
                "payload_digest": digest,
                "resource_use_id": resource_use_id,
            }:
                raise DraftAssistanceError("RESOURCE_USE_OPERATION_CONFLICT")
            return False
        return True

    def record_requested(self, operation_id, invocation, snapshot):
        resource_use_id = f"contextual-resource-use:{invocation.invocation_id}"
        record = {
            "schemaVersion": "contextual-resource-use.v2",
            "resourceUseId": resource_use_id,
            "contextKind": "DRAFT_ASSISTANCE_INVOCATION",
            "contextId": invocation.invocation_id,
            "resourceKind": "MODEL",
            "bindingSnapshotId": snapshot.snapshot_id,
            "bindingSnapshotDigest": snapshot.snapshot_digest,
            "model": {
                "id": snapshot.model_binding.resource_id,
                "revisionId": snapshot.model_binding.revision_id,
                "digest": snapshot.model_binding.digest,
            },
            "provider": {
                "id": snapshot.provider_id,
                "revisionId": snapshot.provider_revision_id,
                "digest": snapshot.provider_digest,
            },
            "endpoint": {
                "id": snapshot.endpoint_id,
                "revisionId": snapshot.endpoint_revision_id,
                "digest": snapshot.endpoint_digest,
            },
            "connectionProfile": {
                "id": snapshot.connection_profile_id,
                "revisionId": snapshot.connection_profile_revision_id,
                "digest": snapshot.connection_profile_digest,
            },
            "draftProfile": {
                "revisionId": snapshot.profile_revision_id,
                "digest": snapshot.profile_digest,
            },
            "adapter": {
                "id": snapshot.adapter_id,
                "revision": snapshot.adapter_revision,
            },
            "authorizationDecisionIds": [
                invocation.authorization.request_decision_id,
                invocation.authorization.model_decision_id,
            ]
            if invocation.authorization
            else [],
            "predecessorInvocationId": invocation.predecessor_invocation_id,
            "status": "REQUESTED",
        }
        try:
            with self.connection_scope() as connection:
                if self._operation(
                    connection,
                    self._scope(invocation),
                    operation_id,
                    record,
                    resource_use_id,
                ):
                    connection.execute(
                        "INSERT INTO contextual_resource_use.uses"
                        "(namespace,security_domain,resource_use_id,context_kind,context_id,"
                        "resource_kind,binding_snapshot_id,record) "
                        "VALUES(%s,%s,%s,'DRAFT_ASSISTANCE_INVOCATION',%s,'MODEL',%s,%s)",
                        (
                            *self._scope(invocation),
                            resource_use_id,
                            invocation.invocation_id,
                            snapshot.snapshot_id,
                            Jsonb(record),
                        ),
                    )
                return resource_use_id
        except DraftAssistanceError:
            raise
        except PsycopgError as exc:
            raise DraftAssistanceError("RESOURCE_USE_STORAGE_UNAVAILABLE") from exc

    def record_observation(self, operation_id, invocation, observation):
        if invocation.resource_use_id is None:
            raise DraftAssistanceError("RESOURCE_USE_NOT_FOUND")
        record = {
            "schemaVersion": "contextual-resource-use-fact.v2",
            "observationId": observation.observation_id,
            "status": observation.state.value,
            "latencyMs": observation.latency_ms,
            "inputTokens": observation.input_tokens,
            "outputTokens": observation.output_tokens,
            "limitationCode": observation.reason_code,
        }
        with self.connection_scope() as connection:
            if self._operation(
                connection,
                self._scope(invocation),
                operation_id,
                record,
                invocation.resource_use_id,
            ):
                connection.execute(
                    "INSERT INTO contextual_resource_use.facts"
                    "(namespace,security_domain,resource_use_id,"
                    "operation_id,fact_kind,record) "
                    "VALUES(%s,%s,%s,%s,'OBSERVATION',%s)",
                    (
                        *self._scope(invocation),
                        invocation.resource_use_id,
                        operation_id,
                        Jsonb(record),
                    ),
                )

    def attach_evidence(self, operation_id, resource_use_id, evidence_id):
        with self.connection_scope() as connection:
            rows = connection.execute(
                "SELECT namespace,security_domain FROM contextual_resource_use.uses "
                "WHERE resource_use_id=%s",
                (resource_use_id,),
            ).fetchall()
            if len(rows) != 1:
                raise DraftAssistanceError("RESOURCE_USE_NOT_FOUND")
            row = rows[0]
            namespace, security_domain = row["namespace"], row["security_domain"]
            record = {
                "schemaVersion": "contextual-resource-use-evidence-ref.v2",
                "evidenceId": evidence_id,
            }
            if self._operation(
                connection,
                (namespace, security_domain),
                operation_id,
                record,
                resource_use_id,
            ):
                connection.execute(
                    "INSERT INTO contextual_resource_use.facts"
                    "(namespace,security_domain,resource_use_id,"
                    "operation_id,fact_kind,record) "
                    "VALUES(%s,%s,%s,%s,'EVIDENCE_REFERENCE',%s)",
                    (
                        namespace,
                        security_domain,
                        resource_use_id,
                        operation_id,
                        Jsonb(record),
                    ),
                )


class PostgresDraftEvidenceOwner(_Pool):
    SCHEMA_VERSION = "model-draft-assistance-invocation-evidence.v1"

    def append(self, operation_id, invocation, observation):
        if invocation.snapshot is None:
            raise DraftAssistanceError("EVIDENCE_INPUT_INVALID")
        record = {
            "schemaVersion": self.SCHEMA_VERSION,
            "scope": [invocation.scope.namespace, invocation.scope.security_domain],
            "contextId": invocation.context_id,
            "turnId": invocation.turn_id,
            "invocationId": invocation.invocation_id,
            "bindingSnapshotId": invocation.snapshot.snapshot_id,
            "bindingSnapshotDigest": invocation.snapshot.snapshot_digest,
            "modelId": invocation.snapshot.model_binding.resource_id,
            "modelRevisionId": invocation.snapshot.model_binding.revision_id,
            "modelDigest": invocation.snapshot.model_binding.digest,
            "providerId": invocation.snapshot.provider_id,
            "providerRevisionId": invocation.snapshot.provider_revision_id,
            "providerDigest": invocation.snapshot.provider_digest,
            "endpointId": invocation.snapshot.endpoint_id,
            "endpointRevisionId": invocation.snapshot.endpoint_revision_id,
            "endpointDigest": invocation.snapshot.endpoint_digest,
            "connectionProfileId": invocation.snapshot.connection_profile_id,
            "connectionProfileRevisionId": (
                invocation.snapshot.connection_profile_revision_id
            ),
            "connectionProfileDigest": (invocation.snapshot.connection_profile_digest),
            "draftProfileRevisionId": invocation.snapshot.profile_revision_id,
            "draftProfileDigest": invocation.snapshot.profile_digest,
            "adapterId": invocation.snapshot.adapter_id,
            "adapterRevision": invocation.snapshot.adapter_revision,
            "authorizationDecisionIds": [
                invocation.authorization.request_decision_id,
                invocation.authorization.model_decision_id,
            ]
            if invocation.authorization
            else [],
            "resourceUseId": invocation.resource_use_id,
            "observationId": observation.observation_id,
            "status": observation.state.value,
            "providerCorrelation": observation.correlation,
            "latencyMs": observation.latency_ms,
            "inputTokens": observation.input_tokens,
            "outputTokens": observation.output_tokens,
            "callCount": 1,
            "costMeasurement": "OWNER_LEDGER_ESTIMATE"
            if observation.measurement is not None
            else "NOT_COLLECTED",
            **(
                {
                    "measurement": observation.measurement,
                    "pricing": invocation.pricing,
                    "budgetReservationId": invocation.budget_reservation_id,
                }
                if observation.measurement is not None
                else {}
            ),
            "requestedAt": invocation.created_at.isoformat(),
            "limitationCode": observation.reason_code,
        }
        payload_digest = _json_digest(record)
        evidence_id = f"model-evidence:{payload_digest}"
        record["evidenceId"] = evidence_id
        try:
            with self.connection_scope() as connection:
                inserted = connection.execute(
                    "INSERT INTO model_evidence.records"
                    "(namespace,security_domain,evidence_id,schema_version,operation_id,"
                    "payload_digest,record) VALUES(%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT DO NOTHING RETURNING evidence_id",
                    (
                        invocation.scope.namespace,
                        invocation.scope.security_domain,
                        evidence_id,
                        self.SCHEMA_VERSION,
                        operation_id,
                        payload_digest,
                        Jsonb(record),
                    ),
                ).fetchone()
                if inserted is None:
                    existing = connection.execute(
                        "SELECT evidence_id,payload_digest FROM model_evidence.records "
                        "WHERE namespace=%s AND security_domain=%s AND operation_id=%s",
                        (
                            invocation.scope.namespace,
                            invocation.scope.security_domain,
                            operation_id,
                        ),
                    ).fetchone()
                    if existing != {
                        "evidence_id": evidence_id,
                        "payload_digest": payload_digest,
                    }:
                        raise DraftAssistanceError("EVIDENCE_OPERATION_CONFLICT")
                return evidence_id
        except DraftAssistanceError:
            raise
        except PsycopgError as exc:
            raise DraftAssistanceError("EVIDENCE_STORAGE_UNAVAILABLE") from exc


def contextual_reader(record: dict[str, Any]) -> ContextualResourceUseRecord | None:
    """Reader-first projection; unknown versions are explicit and not inferred."""
    if record.get("schemaVersion") != "contextual-resource-use.v2":
        return None
    return ContextualResourceUseRecord(
        record["resourceUseId"],
        record["contextKind"],
        record["contextId"],
        record["resourceKind"],
        record["bindingSnapshotId"],
        record["status"],
        record.get("evidenceId"),
    )


def evidence_reader(record: dict[str, Any]) -> ModelDraftEvidence | None:
    if record.get("schemaVersion") != PostgresDraftEvidenceOwner.SCHEMA_VERSION:
        return None
    return ModelDraftEvidence(
        record["evidenceId"],
        record["schemaVersion"],
        record["invocationId"],
        record["bindingSnapshotId"],
        record.get("resourceUseId"),
        record["observationId"],
        record["status"],
        record.get("providerCorrelation"),
        record.get("latencyMs"),
        record.get("inputTokens"),
        record.get("outputTokens"),
        record.get("limitationCode"),
    )
