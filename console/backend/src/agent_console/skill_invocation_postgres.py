# ruff: noqa: E501
"""PostgreSQL authority and atomic Resource Use UoW for Skill invocations."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .execution_domain import ScopeIdentity
from .resource_use_domain import (
    MeasurementAvailability,
    ResourceMeasurement,
    ResourceUseFact,
    ResourceUseFactKind,
    canonical_digest,
    canonical_record,
    reduce_resource_use,
    stable_id,
)
from .resource_use_postgres import PostgresResourceUseRepository
from .skill_invocation_domain import (
    TERMINAL_STATES,
    InvocationFactKind,
    InvocationState,
    SkillInvocationConflict,
    SkillInvocationError,
    SkillInvocationFact,
    SkillInvocationRequest,
    SkillInvocationSnapshot,
)

ADAPTER = "skill-invocation-postgresql-v1"
SCHEMA_VERSION = 16


class PostgresSkillInvocationRepository:
    def __init__(
        self,
        database_url: str,
        *,
        migration_path: Path,
        resource_use_repository: PostgresResourceUseRepository,
        timeout: float = 5.0,
        terminal_hook: Callable[[Any], None] | None = None,
    ) -> None:
        if not database_url:
            raise SkillInvocationError("SKILL_INVOCATION_STORAGE_UNAVAILABLE")
        self.migration_path = migration_path
        self.migration_checksum = hashlib.sha256(
            migration_path.read_bytes()
        ).hexdigest()
        self.resource_use = resource_use_repository
        self.terminal_hook = terminal_hook
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
            prior = connection.execute(
                "SELECT 1 FROM resource_use.schema_migrations WHERE version=15"
            ).fetchone()
            if prior is None:
                raise SkillInvocationError("MIGRATION_0015_REQUIRED")
            connection.execute(self.migration_path.read_text())
            row = connection.execute(
                "SELECT checksum,adapter FROM skill_invocation.schema_migrations WHERE version=16"
            ).fetchone()
            expected = {"checksum": self.migration_checksum, "adapter": ADAPTER}
            if row is None:
                connection.execute(
                    "INSERT INTO skill_invocation.schema_migrations(version,checksum,adapter) VALUES(16,%s,%s)",
                    (self.migration_checksum, ADAPTER),
                )
            elif row != expected:
                raise SkillInvocationError("SKILL_INVOCATION_SCHEMA_INCOMPATIBLE")

    @staticmethod
    def _scope(scope: ScopeIdentity) -> tuple[str, str]:
        return scope.namespace, scope.security_domain

    def prepare_dispatch(
        self,
        request: SkillInvocationRequest,
        inputs: dict[str, Any],
        *,
        payload_digest: str,
        now: datetime,
    ) -> tuple[SkillInvocationSnapshot, bool]:
        if payload_digest != request.payload_digest(inputs):
            raise SkillInvocationError("SKILL_INVOCATION_PAYLOAD_DIGEST_MISMATCH")
        with self.pool.connection() as connection, connection.transaction():
            self._lock(connection, request.scope, request.idempotency_key)
            replay = connection.execute(
                "SELECT payload_digest,skill_invocation_id FROM skill_invocation.invocations WHERE namespace=%s AND security_domain=%s AND idempotency_key=%s",
                (*self._scope(request.scope), request.idempotency_key),
            ).fetchone()
            if replay is not None:
                if replay["payload_digest"] != payload_digest:
                    raise SkillInvocationConflict("SKILL_IDEMPOTENCY_PAYLOAD_MISMATCH")
                return self._snapshot(
                    connection, request.scope, replay["skill_invocation_id"]
                ), False
            self.resource_use._validate_lineage(connection, request.resource_use)
            self._validate_authorities(connection, request, inputs)
            requested = self._fact(
                request,
                InvocationFactKind.INVOCATION_REQUESTED,
                "application",
                request.idempotency_key,
                payload_digest,
                now,
            )
            dispatched = self._fact(
                request,
                InvocationFactKind.DISPATCH_RECORDED,
                "executor-adapter",
                request.invocation_id,
                request.executor.configuration_digest,
                now,
            )
            resource_facts = (
                self._resource_fact(
                    request,
                    ResourceUseFactKind.REQUESTED,
                    "application",
                    request.idempotency_key,
                    payload_digest,
                    now,
                ),
                self._resource_fact(
                    request,
                    ResourceUseFactKind.DISPATCH_RECORDED,
                    "executor-adapter",
                    request.invocation_id,
                    request.executor.configuration_digest,
                    now,
                ),
            )
            self._insert_resource_use(
                connection, request, resource_facts, payload_digest
            )
            self._insert_invocation(connection, request, inputs, payload_digest, now)
            self._insert_invocation_facts(
                connection, request, (requested, dispatched), 0
            )
            snapshot = self._make_snapshot(
                request,
                InvocationState.DISPATCH_RECORDED,
                2,
                payload_digest,
                canonical_digest(inputs),
                None,
                None,
                (requested.kind, dispatched.kind),
                None,
                (),
            )
            self._upsert_projection(connection, request.scope, snapshot, now)
            return snapshot, True

    def _validate_authorities(self, connection, request, inputs) -> None:
        lineage = connection.execute(
            """SELECT wr.assignment_id,eb.approval_id
            FROM execution_authority.attempts a
            JOIN execution_authority.task_runs tr USING(namespace,security_domain,task_run_id)
            JOIN execution_authority.workflow_runs wr USING(namespace,security_domain,workflow_run_id)
            JOIN digital_employee_definition.execution_bindings eb
              ON eb.namespace=a.namespace AND eb.security_domain=a.security_domain
             AND eb.attempt_id=a.attempt_id
            WHERE a.namespace=%s AND a.security_domain=%s AND a.attempt_id=%s""",
            (*self._scope(request.scope), request.attempt_id),
        ).fetchone()
        if (
            lineage is None
            or lineage["assignment_id"] != request.assignment_id
            or lineage["approval_id"] != request.approval_id
        ):
            raise SkillInvocationError("SKILL_EXECUTION_LINEAGE_MISMATCH")
        row = connection.execute(
            """SELECT r.record FROM skill_mcp_resource.resources r
            WHERE r.namespace=%s AND r.security_domain=%s AND r.kind='skill'
              AND r.resource_id=%s""",
            (*self._scope(request.scope), request.skill_id),
        ).fetchone()
        if row is None:
            raise SkillInvocationError("SKILL_INVOCATION_NOT_ELIGIBLE")
        record = row["record"]
        revision = next(
            (
                item
                for item in record.get("revisions", ())
                if item.get("revisionId") == request.skill_revision_id
            ),
            None,
        )
        if (
            revision is None
            or record.get("publishedRevisionId") != request.skill_revision_id
            or revision.get("state") != "PUBLISHED"
            or revision.get("digest") != request.skill_digest
            or not record.get("enabled")
        ):
            raise SkillInvocationError("SKILL_REVISION_NOT_ELIGIBLE")
        operation = next(
            (
                item
                for item in revision.get("content", {}).get("operations", ())
                if item.get("name") == request.operation
            ),
            None,
        )
        if operation is None:
            raise SkillInvocationError("SKILL_OPERATION_NOT_ELIGIBLE")
        input_schema = operation.get("inputSchema")
        output_schema = operation.get("outputSchema")
        if (
            canonical_digest(input_schema) != request.input_schema_digest
            or canonical_digest(output_schema) != request.output_schema_digest
        ):
            raise SkillInvocationError("SKILL_SCHEMA_DIGEST_MISMATCH")
        expected_operation = {
            "sideEffectClass": request.side_effect_class.value,
            "executorId": request.executor.executor_id,
            "executorRevision": request.executor.executor_revision,
            "executorConfigurationDigest": request.executor.configuration_digest,
            "sideEffectPolicy": {
                "policyId": request.policy.policy_id,
                "policyRevision": request.policy.policy_revision,
                "policyDigest": request.policy.policy_digest,
            },
            "ioLimits": {
                "policyId": request.io_limits.policy_id,
                "policyRevision": request.io_limits.policy_revision,
                "maxInputBytes": request.io_limits.max_input_bytes,
                "maxOutputBytes": request.io_limits.max_output_bytes,
                "maxObjectDepth": request.io_limits.max_object_depth,
                "maxProperties": request.io_limits.max_properties,
                "timeoutMs": request.io_limits.timeout_ms,
            },
        }
        if any(
            operation.get(key) != value for key, value in expected_operation.items()
        ):
            raise SkillInvocationError("SKILL_EXECUTION_POLICY_MISMATCH")
        _validate_json_schema(inputs, input_schema, "SKILL_INPUT_SCHEMA_MISMATCH")
        employee = connection.execute(
            """SELECT record,digest FROM digital_employee_definition.revisions
            WHERE namespace=%s AND security_domain=%s AND definition_id=%s AND revision_id=%s""",
            (
                *self._scope(request.scope),
                request.digital_employee_definition_id,
                request.digital_employee_definition_revision_id,
            ),
        ).fetchone()
        if (
            employee is None
            or employee["digest"] != request.digital_employee_definition_digest
        ):
            raise SkillInvocationError("SKILL_EMPLOYEE_REVISION_MISMATCH")
        members = employee["record"].get("members", ())
        exact_member = any(
            item.get("kind") == "SKILL"
            and item.get("resource_id") == request.skill_id
            and item.get("revision_id") == request.skill_revision_id
            and item.get("digest") == request.skill_digest
            for item in members
        )
        expected_binding = stable_id(
            "skill-binding",
            request.digital_employee_definition_id,
            request.digital_employee_definition_revision_id,
            request.skill_id,
            request.skill_revision_id,
        )
        binding_semantic = {
            "bindingId": expected_binding,
            "employeeDefinitionId": request.digital_employee_definition_id,
            "employeeRevisionId": request.digital_employee_definition_revision_id,
            "skillId": request.skill_id,
            "skillRevisionId": request.skill_revision_id,
            "skillDigest": request.skill_digest,
            "operation": request.operation,
        }
        if (
            not exact_member
            or request.binding_id != expected_binding
            or request.binding_digest != canonical_digest(binding_semantic)
        ):
            raise SkillInvocationError("SKILL_BINDING_MISMATCH")

    def _insert_resource_use(self, connection, request, facts, payload_digest) -> None:
        b = request.resource_use
        connection.execute(
            """INSERT INTO resource_use.uses(namespace,security_domain,resource_use_id,
            attempt_id,resource_kind,slot_key,occurrence_ordinal,resource_id,resource_revision_id,
            resource_digest,binding_id,binding_digest,plan_id,plan_version,plan_digest,
            workflow_run_id,task_run_id,digital_employee_definition_id,
            digital_employee_definition_revision_id,digital_employee_definition_digest,
            digital_employee_instance_id,agent_instance_id,runtime_instance_id,executor_id,
            executor_revision,provider_id,provider_revision,authorization_decision_id,
            predecessor_attempt_id,predecessor_workflow_run_id,payload_digest,record)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
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
                json.dumps(canonical_record(b)),
            ),
        )
        self.resource_use._insert_facts(connection, b.scope, facts, 0)
        snapshot = reduce_resource_use(
            b.resource_use_id, facts, (), high_water=len(facts)
        )
        self.resource_use._insert_snapshot(connection, b.scope, snapshot)
        connection.execute(
            "INSERT INTO resource_use.high_waters(namespace,security_domain,resource_use_id,high_water,version) VALUES(%s,%s,%s,%s,1)",
            (*self._scope(b.scope), b.resource_use_id, len(facts)),
        )
        dispatch_key = f"skill-dispatch:{request.idempotency_key}"
        dispatch_digest = canonical_digest(
            {
                "request": asdict(request),
                "facts": [canonical_record(item) for item in facts],
            }
        )
        self.resource_use._insert_idempotency(
            connection, b.scope, dispatch_key, dispatch_digest, snapshot
        )
        claim = {
            "claimId": stable_id("skill-dispatch-claim", request.invocation_id),
            "claimDigest": canonical_digest(
                {"invocationId": request.invocation_id, "payloadDigest": payload_digest}
            ),
            "kind": "SKILL_DISPATCH",
            "invocationId": request.invocation_id,
        }
        connection.execute(
            "INSERT INTO resource_use.claims(namespace,security_domain,resource_use_id,claim_id,claim_digest,record) VALUES(%s,%s,%s,%s,%s,%s::jsonb)",
            (
                *self._scope(b.scope),
                b.resource_use_id,
                claim["claimId"],
                claim["claimDigest"],
                json.dumps(claim),
            ),
        )

    def _insert_invocation(
        self, connection, request, inputs, payload_digest, now
    ) -> None:
        exact = {
            "schemaVersion": "skill-invocation-execution-snapshot.v1",
            "request": canonical_record(request),
            "inputDigest": canonical_digest(inputs),
            "payloadDigest": payload_digest,
        }
        connection.execute(
            """INSERT INTO skill_invocation.invocations(namespace,security_domain,
            skill_invocation_id,idempotency_key,payload_digest,input_digest,attempt_id,
            workflow_run_id,task_run_id,plan_id,plan_version,plan_digest,approval_id,assignment_id,
            digital_employee_definition_id,digital_employee_definition_revision_id,
            digital_employee_definition_digest,digital_employee_instance_id,agent_instance_id,
            runtime_instance_id,skill_id,skill_revision_id,skill_digest,operation,
            input_schema_digest,output_schema_digest,binding_id,binding_digest,executor_id,
            executor_revision,executor_configuration_digest,authorization_decision_id,
            side_effect_class,policy_id,policy_revision,policy_digest,io_policy_id,
            io_policy_revision,io_policy_digest,resource_use_id,exact_snapshot,created_at)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
            (
                *self._scope(request.scope),
                request.invocation_id,
                request.idempotency_key,
                payload_digest,
                canonical_digest(inputs),
                request.attempt_id,
                request.workflow_run_id,
                request.task_run_id,
                request.plan_id,
                request.plan_version,
                request.plan_digest,
                request.approval_id,
                request.assignment_id,
                request.digital_employee_definition_id,
                request.digital_employee_definition_revision_id,
                request.digital_employee_definition_digest,
                request.digital_employee_instance_id,
                request.agent_instance_id,
                request.runtime_instance_id,
                request.skill_id,
                request.skill_revision_id,
                request.skill_digest,
                request.operation,
                request.input_schema_digest,
                request.output_schema_digest,
                request.binding_id,
                request.binding_digest,
                request.executor.executor_id,
                request.executor.executor_revision,
                request.executor.configuration_digest,
                request.authorization_decision_id,
                request.side_effect_class.value,
                request.policy.policy_id,
                request.policy.policy_revision,
                request.policy.policy_digest,
                request.io_limits.policy_id,
                request.io_limits.policy_revision,
                request.io_limits.digest,
                request.resource_use.resource_use_id,
                json.dumps(exact),
                now,
            ),
        )

    @staticmethod
    def _fact(request, kind, source, observation_id, source_digest, now):
        return SkillInvocationFact(
            stable_id("skill-invocation-fact", request.invocation_id, kind.value),
            kind,
            source,
            observation_id,
            source_digest,
            now,
        )

    @staticmethod
    def _resource_fact(
        request,
        kind,
        source,
        observation_id,
        source_digest,
        now,
        *,
        evidence=(),
        limitations=(),
    ):
        return ResourceUseFact(
            stable_id(
                "resource-use-fact", request.resource_use.resource_use_id, kind.value
            ),
            request.resource_use.resource_use_id,
            kind,
            source,
            observation_id,
            source_digest,
            now,
            now,
            tuple(evidence),
            tuple(limitations),
        )

    def _insert_invocation_facts(self, connection, request, facts, offset) -> None:
        for ordinal, fact in enumerate(facts, offset + 1):
            connection.execute(
                """INSERT INTO skill_invocation.facts(namespace,security_domain,
                skill_invocation_id,ordinal,fact_id,kind,source,source_observation_id,
                source_digest,observed_at,record) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                (
                    *self._scope(request.scope),
                    request.invocation_id,
                    ordinal,
                    fact.fact_id,
                    fact.kind.value,
                    fact.source,
                    fact.source_observation_id,
                    fact.source_digest,
                    fact.observed_at,
                    json.dumps(canonical_record(fact)),
                ),
            )

    def commit_terminal(
        self,
        request: SkillInvocationRequest,
        *,
        state: InvocationState,
        output: dict[str, Any] | None,
        provider_observation_id: str,
        error_code: str | None,
        started_at: datetime,
        observed_at: datetime,
    ) -> SkillInvocationSnapshot:
        if state not in TERMINAL_STATES:
            raise SkillInvocationError("SKILL_TERMINAL_STATE_REQUIRED")
        with self.pool.connection() as connection, connection.transaction():
            row = connection.execute(
                """SELECT i.payload_digest,i.input_digest,i.exact_snapshot,p.state,p.high_water
                FROM skill_invocation.invocations i JOIN skill_invocation.projections p
                USING(namespace,security_domain,skill_invocation_id)
                WHERE i.namespace=%s AND i.security_domain=%s AND i.skill_invocation_id=%s
                FOR UPDATE OF p""",
                (*self._scope(request.scope), request.invocation_id),
            ).fetchone()
            if row is None:
                raise SkillInvocationError("SKILL_INVOCATION_NOT_FOUND")
            if row["exact_snapshot"].get("request") != canonical_record(request):
                raise SkillInvocationConflict("SKILL_TERMINAL_SNAPSHOT_MISMATCH")
            current = InvocationState(row["state"])
            if current in TERMINAL_STATES:
                return self._snapshot(connection, request.scope, request.invocation_id)
            output_digest = None if output is None else canonical_digest(output)
            if state is InvocationState.SUCCEEDED:
                operation_schema = self._operation_schema(connection, request)
                try:
                    _validate_json_schema(
                        output, operation_schema, "SKILL_OUTPUT_SCHEMA_MISMATCH"
                    )
                except SkillInvocationError:
                    state = InvocationState.FAILED
                    error_code = "SKILL_OUTPUT_SCHEMA_MISMATCH"
                    output = None
                    output_digest = None
            evidence = self._evidence(
                request,
                state,
                row["input_digest"],
                output_digest,
                error_code,
                observed_at,
            )
            facts = self._terminal_facts(
                request,
                state,
                provider_observation_id,
                evidence["evidenceDigest"],
                observed_at,
            )
            self._insert_invocation_facts(connection, request, facts, row["high_water"])
            connection.execute(
                """INSERT INTO skill_invocation.evidence(namespace,security_domain,evidence_id,
                skill_invocation_id,evidence_digest,redaction_profile,record,created_at)
                VALUES(%s,%s,%s,%s,%s,'skill-invocation-redaction.v1',%s::jsonb,%s)""",
                (
                    *self._scope(request.scope),
                    evidence["evidenceId"],
                    request.invocation_id,
                    evidence["evidenceDigest"],
                    json.dumps(evidence),
                    observed_at,
                ),
            )
            resource_facts = self._terminal_resource_facts(
                request, state, provider_observation_id, evidence, observed_at
            )
            resource_snapshot = self._commit_resource_terminal(
                connection, request, resource_facts, evidence, started_at, observed_at
            )
            prior_kinds = tuple(
                InvocationFactKind(item["kind"])
                for item in connection.execute(
                    "SELECT kind FROM skill_invocation.facts WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s ORDER BY ordinal",
                    (*self._scope(request.scope), request.invocation_id),
                ).fetchall()
            )
            limitations = ("TECHNICAL_SUCCESS_NOT_BUSINESS_SUCCESS",)
            if state is InvocationState.OUTCOME_UNKNOWN:
                limitations += ("PROVIDER_OUTCOME_UNCONFIRMED",)
            snapshot = self._make_snapshot(
                request,
                state,
                row["high_water"] + len(facts),
                row["payload_digest"],
                row["input_digest"],
                output_digest,
                evidence["evidenceId"],
                prior_kinds,
                error_code,
                limitations,
            )
            self._upsert_projection(connection, request.scope, snapshot, observed_at)
            if resource_snapshot.evidence_references != (evidence["evidenceId"],):
                raise SkillInvocationError("SKILL_RESOURCE_USE_EVIDENCE_MISMATCH")
            if self.terminal_hook is not None:
                self.terminal_hook(connection)
            return snapshot

    def _terminal_facts(self, request, state, observation_id, digest, now):
        kinds = []
        if state is InvocationState.SUCCEEDED:
            kinds.extend(
                (
                    InvocationFactKind.INVOCATION_ACCEPTED,
                    InvocationFactKind.INVOCATION_RUNNING,
                )
            )
        kinds.append(
            {
                InvocationState.SUCCEEDED: InvocationFactKind.INVOCATION_SUCCEEDED,
                InvocationState.FAILED: InvocationFactKind.INVOCATION_FAILED,
                InvocationState.CANCELLED: InvocationFactKind.INVOCATION_CANCELLED,
                InvocationState.OUTCOME_UNKNOWN: InvocationFactKind.OUTCOME_UNKNOWN,
            }[state]
        )
        return tuple(
            self._fact(
                request,
                kind,
                "skill-provider",
                f"{observation_id}:{kind.value}",
                digest,
                now,
            )
            for kind in kinds
        )

    def _terminal_resource_facts(self, request, state, observation_id, evidence, now):
        kinds = []
        if state is InvocationState.SUCCEEDED:
            kinds.extend((ResourceUseFactKind.ACCEPTED, ResourceUseFactKind.RUNNING))
        kinds.append(
            {
                InvocationState.SUCCEEDED: ResourceUseFactKind.SUCCEEDED,
                InvocationState.FAILED: ResourceUseFactKind.FAILED,
                InvocationState.CANCELLED: ResourceUseFactKind.CANCELLATION_CONFIRMED,
                InvocationState.OUTCOME_UNKNOWN: ResourceUseFactKind.OUTCOME_UNKNOWN,
            }[state]
        )
        limitations = ("TECHNICAL_SUCCESS_NOT_BUSINESS_SUCCESS",)
        if state is InvocationState.OUTCOME_UNKNOWN:
            limitations += ("PROVIDER_OUTCOME_UNCONFIRMED",)
        return tuple(
            self._resource_fact(
                request,
                kind,
                "SKILL_INVOCATION",
                f"{observation_id}:{kind.value}",
                evidence["evidenceDigest"],
                now,
                evidence=(evidence["evidenceId"],),
                limitations=limitations,
            )
            for kind in kinds
        )

    def _commit_resource_terminal(
        self, connection, request, facts, evidence, started_at, observed_at
    ):
        scope = request.scope
        use_id = request.resource_use.resource_use_id
        row = connection.execute(
            "SELECT high_water,version FROM resource_use.high_waters WHERE namespace=%s AND security_domain=%s AND resource_use_id=%s FOR UPDATE",
            (*self._scope(scope), use_id),
        ).fetchone()
        if row is None:
            raise SkillInvocationError("SKILL_RESOURCE_USE_NOT_FOUND")
        self.resource_use._insert_facts(connection, scope, facts, row["high_water"])
        duration_ms = max(0.0, (observed_at - started_at).total_seconds() * 1000)
        measurements = tuple(
            ResourceMeasurement(
                stable_id("resource-measurement", use_id, metric),
                use_id,
                metric,
                value,
                unit,
                MeasurementAvailability.MEASURED,
                request.executor.executor_id,
                evidence["evidenceDigest"],
                started_at,
                observed_at,
                observed_at,
                "PROVIDER_OBSERVATION"
                if metric == "duration"
                else "PLATFORM_DISPATCH_AUTHORITY",
                "AUTHORITATIVE",
                ("TECHNICAL_SUCCESS_NOT_BUSINESS_SUCCESS",),
                "MILLISECOND" if metric == "duration" else "EXACT_INTEGER",
                True,
                "skill-invocation-redaction.v1",
                (evidence["evidenceId"],),
            )
            for metric, value, unit in (
                ("duration", duration_ms, "ms"),
                ("request_count", 1, "request"),
                ("invocation_count", 1, "invocation"),
            )
        )
        for item in measurements:
            connection.execute(
                """INSERT INTO resource_use.measurements(namespace,security_domain,resource_use_id,
                measurement_id,metric,value,unit,availability,source_identity,source_digest,
                window_started_at,window_ended_at,observed_at,record)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                (
                    *self._scope(scope),
                    use_id,
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
                    json.dumps(canonical_record(item)),
                ),
            )
        evidence_ref = {
            "evidenceId": evidence["evidenceId"],
            "evidenceDigest": evidence["evidenceDigest"],
            "evidenceKind": "SKILL_INVOCATION",
            "invocationId": request.invocation_id,
        }
        connection.execute(
            """INSERT INTO resource_use.evidence_references(namespace,security_domain,
            resource_use_id,evidence_id,evidence_digest,evidence_kind,record)
            VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb)""",
            (
                *self._scope(scope),
                use_id,
                evidence_ref["evidenceId"],
                evidence_ref["evidenceDigest"],
                evidence_ref["evidenceKind"],
                json.dumps(evidence_ref),
            ),
        )
        claim = {
            "claimId": stable_id("skill-terminal-claim", request.invocation_id),
            "claimDigest": canonical_digest(
                {
                    "invocationId": request.invocation_id,
                    "evidenceDigest": evidence["evidenceDigest"],
                }
            ),
            "kind": "SKILL_TERMINAL_OBSERVATION",
            "invocationId": request.invocation_id,
        }
        connection.execute(
            "INSERT INTO resource_use.claims(namespace,security_domain,resource_use_id,claim_id,claim_digest,record) VALUES(%s,%s,%s,%s,%s,%s::jsonb)",
            (
                *self._scope(scope),
                use_id,
                claim["claimId"],
                claim["claimDigest"],
                json.dumps(claim),
            ),
        )
        all_facts = self.resource_use._facts(connection, scope, use_id)
        all_measurements = self.resource_use._measurements(connection, scope, use_id)
        high_water = row["high_water"] + len(facts)
        snapshot = reduce_resource_use(
            use_id, all_facts, all_measurements, high_water=high_water
        )
        changed = connection.execute(
            "UPDATE resource_use.high_waters SET high_water=%s,version=version+1 WHERE namespace=%s AND security_domain=%s AND resource_use_id=%s AND version=%s",
            (high_water, *self._scope(scope), use_id, row["version"]),
        )
        if changed.rowcount != 1:
            raise SkillInvocationConflict("SKILL_RESOURCE_USE_CAS_MISMATCH")
        self.resource_use._insert_snapshot(connection, scope, snapshot)
        terminal_key = f"skill-terminal:{request.invocation_id}"
        terminal_digest = canonical_digest(
            {
                "facts": [canonical_record(item) for item in facts],
                "measurements": [canonical_record(item) for item in measurements],
                "evidence": evidence_ref,
                "claim": claim,
            }
        )
        self.resource_use._insert_idempotency(
            connection, scope, terminal_key, terminal_digest, snapshot
        )
        return snapshot

    def _operation_schema(self, connection, request):
        row = connection.execute(
            "SELECT record FROM skill_mcp_resource.resources WHERE namespace=%s AND security_domain=%s AND kind='skill' AND resource_id=%s",
            (*self._scope(request.scope), request.skill_id),
        ).fetchone()
        if row is None:
            raise SkillInvocationError("SKILL_REVISION_NOT_ELIGIBLE")
        revision = next(
            (
                item
                for item in row["record"].get("revisions", ())
                if item.get("revisionId") == request.skill_revision_id
            ),
            None,
        )
        operation = (
            None
            if revision is None
            else next(
                (
                    item
                    for item in revision.get("content", {}).get("operations", ())
                    if item.get("name") == request.operation
                ),
                None,
            )
        )
        if (
            operation is None
            or canonical_digest(operation.get("outputSchema"))
            != request.output_schema_digest
        ):
            raise SkillInvocationError("SKILL_OUTPUT_SCHEMA_DIGEST_MISMATCH")
        return operation["outputSchema"]

    @staticmethod
    def _evidence(request, state, input_digest, output_digest, error_code, now):
        semantic = {
            "schemaVersion": "skill-invocation-evidence.v1",
            "invocationId": request.invocation_id,
            "attemptId": request.attempt_id,
            "skillId": request.skill_id,
            "skillRevisionId": request.skill_revision_id,
            "skillDigest": request.skill_digest,
            "operation": request.operation,
            "bindingId": request.binding_id,
            "bindingDigest": request.binding_digest,
            "executorId": request.executor.executor_id,
            "executorRevision": request.executor.executor_revision,
            "authorizationDecisionId": request.authorization_decision_id,
            "sideEffectClass": request.side_effect_class.value,
            "policyId": request.policy.policy_id,
            "policyRevision": request.policy.policy_revision,
            "policyDigest": request.policy.policy_digest,
            "inputDigest": input_digest,
            "outputDigest": output_digest,
            "state": state.value,
            "errorCode": error_code,
            "redactionProfile": "skill-invocation-redaction.v1",
            "rawInputStored": False,
            "rawOutputStored": False,
            "technicalSuccessNotBusinessSuccess": True,
            "limitations": [
                "TECHNICAL_SUCCESS_NOT_BUSINESS_SUCCESS",
                *(
                    ["PROVIDER_OUTCOME_UNCONFIRMED"]
                    if state is InvocationState.OUTCOME_UNKNOWN
                    else []
                ),
            ],
            "observedAt": now.isoformat(),
        }
        evidence_id = stable_id("skill-invocation-evidence", request.invocation_id)
        return {
            "evidenceId": evidence_id,
            **semantic,
            "evidenceDigest": canonical_digest(semantic),
        }

    @staticmethod
    def _make_snapshot(
        request,
        state,
        high_water,
        payload_digest,
        input_digest,
        output_digest,
        evidence_id,
        fact_kinds,
        error_code,
        limitations,
    ):
        return SkillInvocationSnapshot(
            request.invocation_id,
            state,
            high_water,
            payload_digest,
            input_digest,
            output_digest,
            evidence_id,
            request.resource_use.resource_use_id,
            tuple(fact_kinds),
            error_code,
            tuple(limitations),
            True,
        )

    def _upsert_projection(self, connection, scope, snapshot, now):
        record = canonical_record(snapshot)
        connection.execute(
            """INSERT INTO skill_invocation.projections(namespace,security_domain,
            skill_invocation_id,state,high_water,snapshot_digest,record,updated_at)
            VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
            ON CONFLICT(namespace,security_domain,skill_invocation_id) DO UPDATE SET
              state=EXCLUDED.state,high_water=EXCLUDED.high_water,
              snapshot_digest=EXCLUDED.snapshot_digest,record=EXCLUDED.record,
              updated_at=EXCLUDED.updated_at""",
            (
                *self._scope(scope),
                snapshot.invocation_id,
                snapshot.state.value,
                snapshot.high_water,
                canonical_digest(record),
                json.dumps(record),
                now,
            ),
        )

    @staticmethod
    def _decode_snapshot(record):
        return SkillInvocationSnapshot(
            **{
                **record,
                "state": InvocationState(record["state"]),
                "fact_kinds": tuple(
                    InvocationFactKind(item) for item in record["fact_kinds"]
                ),
                "limitation_codes": tuple(record["limitation_codes"]),
            }
        )

    def _snapshot(self, connection, scope, invocation_id):
        row = connection.execute(
            "SELECT record FROM skill_invocation.projections WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s",
            (*self._scope(scope), invocation_id),
        ).fetchone()
        if row is None:
            raise SkillInvocationError("SKILL_INVOCATION_NOT_FOUND")
        return self._decode_snapshot(row["record"])

    def get_snapshot(self, scope, invocation_id):
        with self.pool.connection() as connection:
            row = connection.execute(
                "SELECT record FROM skill_invocation.projections WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s",
                (*self._scope(scope), invocation_id),
            ).fetchone()
        return None if row is None else self._decode_snapshot(row["record"])

    @staticmethod
    def _lock(connection, scope, key):
        identity = canonical_digest([scope.namespace, scope.security_domain, key])
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (identity,)
        )


def _validate_json_schema(value: Any, schema: Any, code: str) -> None:
    """Validate the bounded JSON Schema subset accepted by the Skill executor."""

    def validate(item: Any, rule: Any) -> None:
        if not isinstance(rule, dict):
            raise SkillInvocationError(code)
        expected = rule.get("type")
        valid = {
            "string": isinstance(item, str),
            "integer": isinstance(item, int) and not isinstance(item, bool),
            "number": isinstance(item, (int, float)) and not isinstance(item, bool),
            "boolean": isinstance(item, bool),
            "object": isinstance(item, dict),
            "array": isinstance(item, list),
        }.get(expected, False)
        if not valid or ("enum" in rule and item not in rule["enum"]):
            raise SkillInvocationError(code)
        if expected == "string" and (
            len(item) < rule.get("minLength", 0)
            or len(item) > rule.get("maxLength", len(item))
        ):
            raise SkillInvocationError(code)
        if expected == "object":
            properties = rule.get("properties", {})
            required = rule.get("required", [])
            if not isinstance(properties, dict) or not isinstance(required, list):
                raise SkillInvocationError(code)
            if any(name not in item for name in required):
                raise SkillInvocationError(code)
            if rule.get("additionalProperties") is False and any(
                name not in properties for name in item
            ):
                raise SkillInvocationError(code)
            for name, child in item.items():
                if name in properties:
                    validate(child, properties[name])
        if expected == "array":
            child_rule = rule.get("items")
            if child_rule is None:
                raise SkillInvocationError(code)
            for child in item:
                validate(child, child_rule)

    validate(value, schema)
