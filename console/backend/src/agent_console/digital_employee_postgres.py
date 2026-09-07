# ruff: noqa: E501
"""PostgreSQL adapter for Digital Employee application services (migration 0008)."""

from __future__ import annotations

import json
from datetime import datetime

from .digital_employee_application import (
    AssignmentLifecycle,
    AssignmentRecord,
    DefinitionReference,
    DigitalEmployeeError,
    InstanceLifecycle,
    InstanceRecord,
    assignment_command_digest,
)
from .execution_domain import ExecutionConflict, VersionedAggregate
from .execution_postgres import (
    AgentInstanceId,
    AppendDisposition,
    DigitalEmployeeInstanceId,
    PlacementDecision,
    PlacementRequest,
    PlacementResult,
    PostgresExecutionAuthorityRepository,
    RuntimeInstanceId,
    ScopeIdentity,
)


class PostgresDigitalEmployeeRepository:
    def __init__(self, authority: PostgresExecutionAuthorityRepository) -> None:
        self.authority = authority

    @staticmethod
    def _instance_record(value: InstanceRecord, command_id: str) -> dict:
        return {
            "definition_id": value.definition.definition_id,
            "definition_revision_id": value.definition.revision_id,
            "definition_digest": value.definition.digest,
            "definition_published": value.definition.published,
            "definition_eligible": value.definition.eligible,
            "definition_authority": value.definition.authority_kind,
            "primary_agent_id": value.definition.primary_agent_id,
            "primary_agent_revision_id": value.definition.primary_agent_revision_id,
            "primary_agent_digest": value.definition.primary_agent_digest,
            "owner_id": value.owner_id,
            "organization_id": value.organization_id,
            "lifecycle": value.lifecycle.value,
            "workspace_reference": value.workspace_reference,
            "model_reference": value.model_reference,
            "policy_references": list(value.policy_references),
            "created_at": value.created_at.isoformat(),
            "updated_at": value.updated_at.isoformat(),
            "reobservation_id": value.reobservation_id,
            "command_id": command_id,
        }

    def create_instance(
        self, value: InstanceRecord, command_id: str
    ) -> AppendDisposition:
        record = self._instance_record(value, command_id)
        from .digital_employee_definition import EmployeeRevision, MemberKind
        from .digital_employee_definition_postgres import (
            PostgresEmployeeDefinitionRepository,
        )

        if value.definition.authority_kind != "DIGITAL_EMPLOYEE_DEFINITION_V1":
            raise DigitalEmployeeError("EXACT_EMPLOYEE_DEFINITION_REQUIRED")
        key = (
            value.scope.namespace,
            value.scope.security_domain,
            str(value.instance_id),
        )

        def operation(conn):
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (json.dumps(key),),
            )
            definition = PostgresEmployeeDefinitionRepository._read(
                conn,
                value.scope,
                value.definition.definition_id,
                value.definition.revision_id,
            )
            revision = EmployeeRevision.from_record(definition["revision"])
            agent = next(m for m in revision.members if m.kind is MemberKind.AGENT)
            if definition["digest"] != value.definition.digest or (
                agent.resource_id,
                agent.revision_id,
                agent.digest,
            ) != (
                value.definition.primary_agent_id,
                value.definition.primary_agent_revision_id,
                value.definition.primary_agent_digest,
            ):
                raise DigitalEmployeeError("EMPLOYEE_DEFINITION_MISMATCH")
            existing = conn.execute(
                "SELECT record,aggregate_version FROM execution_authority.digital_employee_instances WHERE namespace=%s AND security_domain=%s AND digital_employee_instance_id=%s FOR UPDATE",
                key,
            ).fetchone()
            if existing is not None:
                comparable = dict(record)
                comparable["created_at"] = existing["record"].get("created_at")
                comparable["updated_at"] = existing["record"].get("updated_at")
                if (
                    existing["aggregate_version"] == value.version
                    and existing["record"] == comparable
                ):
                    return AppendDisposition.REPLAYED
                raise DigitalEmployeeError("INSTANCE_IDENTITY_CONFLICT")
            if not definition["published"]:
                raise DigitalEmployeeError("DEFINITION_INELIGIBLE")
            PostgresEmployeeDefinitionRepository.validate_members(conn, revision)
            conn.execute(
                "INSERT INTO execution_authority.digital_employee_instances(namespace,security_domain,digital_employee_instance_id,definition_revision_id,aggregate_version,record) VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
                (*key, value.definition.revision_id, value.version, json.dumps(record)),
            )
            conn.execute(
                "INSERT INTO digital_employee_definition.instance_bindings VALUES (%s,%s,%s,%s,%s,%s)",
                (
                    *key,
                    value.definition.definition_id,
                    value.definition.revision_id,
                    value.definition.digest,
                ),
            )
            return AppendDisposition.APPENDED

        return self.authority._transaction(operation)

    def get_instance(
        self, scope: ScopeIdentity, instance_id: DigitalEmployeeInstanceId
    ) -> InstanceRecord | None:
        value = self.authority.get_aggregate(
            "digital_employee_instance", scope, str(instance_id)
        )
        if value is None:
            return None
        record = value.record
        definition = DefinitionReference(
            record["definition_id"],
            record["definition_revision_id"],
            record["definition_digest"],
            record["definition_published"],
            record["definition_eligible"],
            record.get("definition_authority", "LEGACY_UNVERIFIED"),
            record.get("primary_agent_id"),
            record.get("primary_agent_revision_id"),
            record.get("primary_agent_digest"),
        )
        return InstanceRecord(
            scope,
            instance_id,
            value.aggregate_version,
            definition,
            record["owner_id"],
            record["organization_id"],
            InstanceLifecycle(record["lifecycle"]),
            record.get("workspace_reference"),
            record.get("model_reference"),
            tuple(record.get("policy_references", ())),
            datetime.fromisoformat(record["created_at"]),
            datetime.fromisoformat(record["updated_at"]),
            record.get("reobservation_id"),
        )

    def replace_instance(self, value: InstanceRecord, expected_version: int) -> None:
        current = self.authority.get_aggregate(
            "digital_employee_instance", value.scope, str(value.instance_id)
        )
        command_id = "transition"
        if current is not None:
            command_id = current.record.get("command_id", command_id)
        aggregate = VersionedAggregate(
            value.scope,
            str(value.instance_id),
            value.version,
            self._instance_record(value, command_id),
        )
        try:
            self.authority.replace_aggregate(
                "digital_employee_instance",
                aggregate,
                expected_version=expected_version,
            )
        except ExecutionConflict as exc:
            raise DigitalEmployeeError("STALE_INSTANCE_VERSION") from exc

    @staticmethod
    def _assignment_from_row(scope: ScopeIdentity, row: dict) -> AssignmentRecord:
        record = row["record"]
        from .execution_postgres import AssignmentId

        return AssignmentRecord(
            scope,
            AssignmentId(row["assignment_id"]),
            DigitalEmployeeInstanceId(row["digital_employee_instance_id"]),
            record["assignee_id"],
            record["business_role"],
            AssignmentLifecycle(record["lifecycle"]),
            datetime.fromisoformat(record["effective_from"]),
            None
            if record.get("effective_until") is None
            else datetime.fromisoformat(record["effective_until"]),
            record["version"],
            record["command_id"],
            None
            if record.get("predecessor_assignment_id") is None
            else AssignmentId(record["predecessor_assignment_id"]),
        )

    def create_assignment(self, value: AssignmentRecord) -> AppendDisposition:
        digest = assignment_command_digest(value)
        record = {
            "assignee_id": value.assignee_id,
            "business_role": value.business_role,
            "lifecycle": value.lifecycle.value,
            "effective_from": value.effective_from.isoformat(),
            "effective_until": None
            if value.effective_until is None
            else value.effective_until.isoformat(),
            "version": value.version,
            "command_id": value.command_id,
            "predecessor_assignment_id": None
            if value.predecessor_assignment_id is None
            else str(value.predecessor_assignment_id),
        }

        def operation(connection):
            instance = connection.execute(
                "SELECT record FROM execution_authority.digital_employee_instances WHERE namespace=%s AND security_domain=%s AND digital_employee_instance_id=%s FOR UPDATE",
                (
                    value.scope.namespace,
                    value.scope.security_domain,
                    str(value.instance_id),
                ),
            ).fetchone()
            if instance is None:
                raise DigitalEmployeeError("INSTANCE_NOT_FOUND")
            existing = connection.execute(
                "SELECT approved_input_digest FROM execution_authority.assignments WHERE namespace=%s AND security_domain=%s AND assignment_id=%s FOR UPDATE",
                (
                    value.scope.namespace,
                    value.scope.security_domain,
                    str(value.assignment_id),
                ),
            ).fetchone()
            if existing:
                if existing["approved_input_digest"] != digest:
                    raise DigitalEmployeeError("ASSIGNMENT_REPLAY_CONFLICT")
                return AppendDisposition.REPLAYED
            if value.lifecycle is AssignmentLifecycle.ACTIVE:
                conflict = connection.execute(
                    "SELECT 1 FROM execution_authority.assignments WHERE namespace=%s AND security_domain=%s AND digital_employee_instance_id=%s AND record->>'lifecycle'='ACTIVE' AND record->>'business_role'=%s LIMIT 1 FOR UPDATE",
                    (
                        value.scope.namespace,
                        value.scope.security_domain,
                        str(value.instance_id),
                        value.business_role,
                    ),
                ).fetchone()
                if conflict:
                    raise DigitalEmployeeError("ACTIVE_ASSIGNMENT_CONFLICT")
            if value.predecessor_assignment_id is not None:
                predecessor = connection.execute(
                    "SELECT record,digital_employee_instance_id FROM execution_authority.assignments WHERE namespace=%s AND security_domain=%s AND assignment_id=%s FOR UPDATE",
                    (
                        value.scope.namespace,
                        value.scope.security_domain,
                        str(value.predecessor_assignment_id),
                    ),
                ).fetchone()
                if (
                    predecessor is None
                    or predecessor["digital_employee_instance_id"]
                    != str(value.instance_id)
                    or predecessor["record"].get("version") != value.version - 1
                ):
                    raise DigitalEmployeeError("STALE_ASSIGNMENT_VERSION")
            connection.execute(
                "INSERT INTO execution_authority.assignments(namespace,security_domain,assignment_id,digital_employee_instance_id,approved_input_digest,record) VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
                (
                    value.scope.namespace,
                    value.scope.security_domain,
                    str(value.assignment_id),
                    str(value.instance_id),
                    digest,
                    json.dumps(record),
                ),
            )
            return AppendDisposition.APPENDED

        return self.authority._transaction(operation)

    def assignments_for_instance(
        self, scope: ScopeIdentity, instance_id: DigitalEmployeeInstanceId
    ) -> tuple[AssignmentRecord, ...]:
        with self.authority.pool.connection() as connection:
            rows = connection.execute(
                "SELECT assignment_id,digital_employee_instance_id,record FROM execution_authority.assignments WHERE namespace=%s AND security_domain=%s AND digital_employee_instance_id=%s ORDER BY record->>'effective_from',assignment_id",
                (scope.namespace, scope.security_domain, str(instance_id)),
            ).fetchall()
        return tuple(self._assignment_from_row(scope, row) for row in rows)

    def decide_placement(
        self,
        scope: ScopeIdentity,
        request: PlacementRequest,
        decision: PlacementDecision,
    ) -> PlacementResult:
        return self.authority.decide(
            scope, request, decision, require_employee_lineage=True
        )

    def runtime_exists(
        self, scope: ScopeIdentity, runtime_id: RuntimeInstanceId
    ) -> bool:
        return (
            self.authority.get_aggregate("runtime_instance", scope, str(runtime_id))
            is not None
        )

    def agent_exists(self, scope: ScopeIdentity, agent_id: AgentInstanceId) -> bool:
        return (
            self.authority.get_aggregate("agent_instance", scope, str(agent_id))
            is not None
        )

    def latest_observation(
        self, scope: ScopeIdentity, runtime_id: RuntimeInstanceId
    ) -> tuple[str, datetime] | None:
        observations = self.authority.read_observations(scope, runtime_id)
        if not observations:
            return None
        value = observations[-1]
        return str(value.observation_id), value.observed_at

    def active_attempts(
        self,
        scope: ScopeIdentity,
        runtime_id: RuntimeInstanceId,
        agent_id: AgentInstanceId,
    ):
        return self.authority.attempts_for_runtime_agent(scope, runtime_id, agent_id)
