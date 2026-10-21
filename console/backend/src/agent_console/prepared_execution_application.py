# ruff: noqa: E501 -- SQL statements retain explicit owner/column names.
"""Caller-transaction admission for one prepared Run and exact Task identities.

This owner never invokes a Skill or Runtime. Native remains the effect owner.
"""

import json
from datetime import UTC, datetime

from agent_core.execution_contract import (
    AssignmentId,
    AssignmentIdentity,
    AttemptId,
    AttemptIdentity,
    DigitalEmployeeInstanceId,
    ExecutionIdentityAggregate,
    ScopeIdentity,
    TaskRunId,
    TaskRunIdentity,
    WorkflowRunId,
    WorkflowRunIdentity,
    canonical_bytes,
    canonical_digest,
)
from psycopg.types.json import Jsonb

from .execution_preparation import ExecutionPreparationError, ProgressEvent
from .execution_preparation_postgres import PreparedExecutionStore
from .prepared_execution_lineage import (
    require_evidence_writer,
    validate_approved_preparation,
    validate_participant,
)
from .prepared_execution_resources import resource_read_grants, validate_resources
from .resource_use_domain import stable_id


def start_resource(p):
    return "governed-execution:prepared:" + p.digest


def task_run_id(p, task_id):
    return stable_id("prepared-task", p.run_id, task_id)


class PreparedExecutionApplication:
    def __init__(self, connection, principal, authority):
        self.connection = connection
        self.principal = principal
        self.authority = authority
        self.scope = ScopeIdentity(principal.tenant_id, principal.security_domain)
        self.store = PreparedExecutionStore(connection)

    def authorize(self, p):
        if (p.namespace, p.security_domain) != (
            self.scope.namespace,
            self.scope.security_domain,
        ):
            raise ExecutionPreparationError("PREPARED_EXECUTION_NOT_FOUND")
        return self.authority.require(
            self.principal, "EXECUTION", "START", start_resource(p)
        )

    def validate(self, p, *, task_id=None):
        decision = self.authorize(p)  # Before all target/resource readbacks.
        require_evidence_writer(self.connection)
        validate_approved_preparation(self.connection, p)
        self.validate_root(p)
        for participant in p.participants:
            if task_id is not None and participant.task_id != task_id:
                continue
            # Independent exact participant grants: root conveys no Task authority.
            self.authority.require(
                self.principal,
                "EXECUTION",
                "START",
                f"governed-execution:participant:{p.digest}:{participant.task_id}",
            )
            validate_participant(self.connection, self.scope, participant)
            for grant in resource_read_grants(p, participant):
                self.authority.require(
                    self.principal, grant.owner, grant.action, grant.exact_resource
                )
            validate_resources(self.connection, self.scope, p, participant)
        return decision

    def validate_root(self, p):
        root = self.connection.execute(
            "SELECT a.digital_employee_instance_id,a.record,i.record AS instance_record "
            "FROM execution_authority.assignments a JOIN execution_authority.digital_employee_instances i "
            "USING(namespace,security_domain,digital_employee_instance_id) "
            "WHERE a.namespace=%s AND a.security_domain=%s AND a.assignment_id=%s FOR SHARE",
            (p.namespace, p.security_domain, p.root_assignment_id),
        ).fetchone()
        if (
            root is None
            or root["digital_employee_instance_id"] != p.root_instance_id
            or root["instance_record"].get("lifecycle") != "ENABLED"
        ):
            raise ExecutionPreparationError("PREPARED_ROOT_ASSIGNMENT_MISMATCH")
        try:
            a = root["record"]
            now = datetime.now(UTC)
            valid = (
                a["lifecycle"] == "ACTIVE"
                and datetime.fromisoformat(a["effective_from"]) <= now
            )
            valid = valid and (
                a["effective_until"] is None
                or now < datetime.fromisoformat(a["effective_until"])
            )
        except (KeyError, ValueError, TypeError):
            valid = False
        if not valid:
            raise ExecutionPreparationError("PREPARED_ROOT_ASSIGNMENT_NOT_ACTIVE")

    def start(self, p, key):
        if not key or len(key) > 200:
            raise ExecutionPreparationError("PREPARED_COMMAND_KEY_INVALID")
        self.authorize(p)
        conn = self.connection
        scope = (p.namespace, p.security_domain)
        # Serialize both same-key/different-content and same-instance/different-key.
        for lock in sorted(
            (
                json.dumps((*scope, self.principal.principal_id, key)),
                json.dumps((*scope, p.run_id)),
            )
        ):
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (lock,)
            )
        prior = conn.execute(
            "SELECT payload_digest,workflow_run_id FROM execution_authority.prepared_start_commands "
            "WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND command_key=%s",
            (*scope, self.principal.principal_id, key),
        ).fetchone()
        if prior:
            if (
                prior["payload_digest"] != p.digest
                or prior["workflow_run_id"] != p.run_id
            ):
                raise ExecutionPreparationError("PREPARED_START_REPLAY_CONFLICT")
            return self.store.read(*scope, p.run_id)[1]
        existing = conn.execute(
            "SELECT digest FROM execution_authority.run_preparations "
            "WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s",
            (*scope, p.run_id),
        ).fetchone()
        if not existing:
            self.validate(p)
            run = WorkflowRunIdentity(
                WorkflowRunId(p.run_id),
                AssignmentId(p.root_assignment_id),
                f"plan:{p.plan_id}:{p.plan_version}:{p.plan_digest}",
            )
            conn.execute(
                "INSERT INTO execution_authority.workflow_runs "
                "(namespace,security_domain,workflow_run_id,assignment_id,approved_plan_revision_id,"
                "record,plan_id,plan_version,approved_plan_digest,control_state) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'PENDING')",
                (
                    *scope,
                    p.run_id,
                    p.root_assignment_id,
                    run.approved_plan_revision_id,
                    Jsonb(json.loads(canonical_bytes(run))["payload"]),
                    p.plan_id,
                    p.plan_version,
                    p.plan_digest,
                ),
            )
            progress = self.store.attach(p)
            for participant in p.participants:
                task = TaskRunIdentity(
                    TaskRunId(task_run_id(p, participant.task_id)), run.workflow_run_id
                )
                state = next(
                    t.state for t in progress.tasks if t.task_id == participant.task_id
                )
                conn.execute(
                    "INSERT INTO execution_authority.task_runs "
                    "(namespace,security_domain,task_run_id,workflow_run_id,record,workflow_node_id,control_state) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (
                        *scope,
                        str(task.task_run_id),
                        p.run_id,
                        Jsonb(json.loads(canonical_bytes(task))["payload"]),
                        participant.task_id,
                        "READY" if state == "READY" else "PENDING",
                    ),
                )
                conn.execute(
                    "INSERT INTO execution_authority.prepared_task_bindings VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (
                        *scope,
                        str(task.task_run_id),
                        p.run_id,
                        participant.task_id,
                        participant.assignment_id,
                        Jsonb(participant.model_dump(mode="json")),
                    ),
                )
        elif existing["digest"] != p.digest:
            raise ExecutionPreparationError("PREPARED_START_REPLAY_CONFLICT")
        conn.execute(
            "INSERT INTO execution_authority.prepared_start_commands "
            "(namespace,security_domain,actor_id,command_key,payload_digest,workflow_run_id) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (*scope, self.principal.principal_id, key, p.digest, p.run_id),
        )
        return self.store.read(*scope, p.run_id)[1]

    def queue_attempt(self, p, task_id, *, retry=False):
        decision = self.validate(p, task_id=task_id)
        scope = (p.namespace, p.security_domain)
        stored, state = self.store.read(*scope, p.run_id, lock=True)
        if stored != p:
            raise ExecutionPreparationError("PREPARED_RUN_MISMATCH")
        participant = next((t for t in p.participants if t.task_id == task_id), None)
        task = next((t for t in state.tasks if t.task_id == task_id), None)
        if participant is None or task is None:
            raise ExecutionPreparationError("PREPARED_TASK_NOT_FOUND")
        if retry:
            stopped = self.connection.execute(
                "SELECT a.control_state,c.state,c.terminal_observation_digest FROM execution_authority.attempts a "
                "JOIN execution_authority.native_dispatch_commands c USING(namespace,security_domain,attempt_id) "
                "WHERE a.namespace=%s AND a.security_domain=%s AND a.attempt_id=%s",
                (*scope, task.attempt_id),
            ).fetchone()
            if (
                stopped is None
                or stopped["control_state"] != "FAILED"
                or stopped["state"] != "FAILED"
                or not stopped["terminal_observation_digest"]
                or not task.stop_evidence
            ):
                raise ExecutionPreparationError("RETRY_AUTHORITATIVE_STOP_REQUIRED")
        attempt_id = stable_id(
            "prepared-attempt", p.run_id, task_id, str(task.attempt_ordinal + 1)
        )
        event = ProgressEvent(
            action="RETRY" if retry else "QUEUE",
            task_id=task_id,
            attempt_id=attempt_id,
            evidence_id="queue:" + attempt_id,
        )
        # Validate transition before inserting identities. Owner transaction rolls back all.
        from .execution_preparation import transition

        transition(p, state, event)
        identity = ExecutionIdentityAggregate(
            self.scope,
            AssignmentIdentity(
                AssignmentId(p.root_assignment_id),
                DigitalEmployeeInstanceId(p.root_instance_id),
            ),
            WorkflowRunIdentity(
                WorkflowRunId(p.run_id),
                AssignmentId(p.root_assignment_id),
                f"plan:{p.plan_id}:{p.plan_version}:{p.plan_digest}",
            ),
            TaskRunIdentity(
                TaskRunId(task_run_id(p, task_id)), WorkflowRunId(p.run_id)
            ),
            AttemptIdentity(
                AttemptId(attempt_id),
                TaskRunId(task_run_id(p, task_id)),
                AttemptId(task.attempt_id) if retry else None,
            ),
        )
        self.connection.execute(
            "INSERT INTO execution_authority.attempts "
            "(namespace,security_domain,attempt_id,task_run_id,predecessor_attempt_id,"
            "aggregate_digest,record,control_state,attempt_ordinal) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,'PENDING',%s)",
            (
                *scope,
                attempt_id,
                task_run_id(p, task_id),
                task.attempt_id if retry else None,
                canonical_digest(identity),
                Jsonb(json.loads(canonical_bytes(identity))["payload"]),
                task.attempt_ordinal + 1,
            ),
        )
        ref = participant.definition
        self.connection.execute(
            "INSERT INTO digital_employee_definition.execution_bindings VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *scope,
                attempt_id,
                participant.instance_id,
                ref.resource_id,
                ref.revision_id,
                ref.digest,
                p.plan_digest,
                p.approval_id,
                decision.decision_id,
            ),
        )
        self.store.apply(*scope, p.run_id, event, expected_version=state.version)
        return identity
