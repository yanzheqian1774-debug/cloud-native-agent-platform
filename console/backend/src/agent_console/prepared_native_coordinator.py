# ruff: noqa: E501 -- Explicit scoped SQL and grant identities.
"""Static ready-task assembly in the Execution owner; no Runtime effects here."""

from datetime import UTC, datetime

from agent_core.execution_contract import (
    AgentInstanceId,
    Generation,
    PlacementDecision,
    PlacementDecisionKind,
    PlacementId,
    PlacementRequest,
    PlacementRequestId,
    RuntimeInstanceId,
)

from .authority_contracts import ExactGrant
from .execution_preparation import ExecutionPreparationError
from .execution_preparation_postgres import PreparedExecutionStore
from .native_dispatch_application import NativeDispatchApplication, QueueNativeDispatch
from .prepared_execution_application import PreparedExecutionApplication, start_resource
from .resource_use_domain import stable_id
from .workbench_business_problem import OwnerPrincipal


class PreparedNativeCoordinator:
    def __init__(self, repository):
        self.repository = repository

    def __call__(self, call, preparation, *, retry_task=None):
        p = preparation
        principal = OwnerPrincipal(
            call.context.principal_id,
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        app = PreparedExecutionApplication(call.connection, principal, call.authority)
        app.authorize(p)
        repository = self.repository.for_transaction(call.connection)
        _, progress = PreparedExecutionStore(call.connection).read(
            p.namespace, p.security_domain, p.run_id, lock=True
        )
        if (
            progress.state not in {"PENDING", "RUNNING"}
            or progress.cancellation_request_id
        ):
            return
        for task in progress.tasks:
            if retry_task is not None:
                if task.task_id != retry_task:
                    continue
                if task.state != "RETRY_WAIT":
                    raise ExecutionPreparationError("EXECUTION_RETRY_NOT_READY")
            elif task.state != "READY":
                continue
            participant = next(t for t in p.participants if t.task_id == task.task_id)
            # Known before dispatch, independently admitted for this exact ordinal.
            call.authority.require(
                principal,
                "SKILL",
                "INVOKE_SKILL",
                f"skill-invocation:prepared:{p.digest}:{task.task_id}:{task.attempt_ordinal + 1}",
            )
            identity = app.queue_attempt(p, task.task_id, retry=retry_task is not None)
            agent = call.connection.execute(
                "SELECT agent_revision_id,runtime_instance_id,record FROM execution_authority.agent_instances "
                "WHERE namespace=%s AND security_domain=%s AND agent_instance_id=%s FOR SHARE",
                (p.namespace, p.security_domain, participant.agent_instance_id),
            ).fetchone()
            if (
                agent is None
                or agent["runtime_instance_id"] != participant.runtime_instance_id
            ):
                raise ExecutionPreparationError("PREPARED_AGENT_RUNTIME_MISMATCH")
            agent_name = agent["record"].get("kubernetes_agent_name")
            if not agent_name:
                raise ExecutionPreparationError(
                    "PREPARED_KUBERNETES_AGENT_NAME_REQUIRED"
                )
            now = datetime.now(UTC)
            request = PlacementRequest(
                PlacementRequestId(
                    stable_id(
                        "prepared-placement-request", str(identity.attempt.attempt_id)
                    )
                ),
                app.scope,
                identity.workflow_run.workflow_run_id,
                identity.task_run.task_run_id,
                identity.attempt.attempt_id,
                AgentInstanceId(participant.agent_instance_id),
                agent["agent_revision_id"],
                participant.profile.revision_id,
                (),
                (),
                ("NAMESPACE",),
                ("STATELESS",),
                now,
            )
            placement = PlacementDecision.create(
                placement_id=PlacementId(
                    stable_id("prepared-placement", str(identity.attempt.attempt_id))
                ),
                request_id=request.request_id,
                decision=PlacementDecisionKind.PLACED,
                runtime_instance_id=RuntimeInstanceId(participant.runtime_instance_id),
                policy_version="prepared-native-exact.v1",
                compatibility_facts=("EXACT_PREPARED_BINDING",),
                limitation_codes=("ISOLATED_SYNTHETIC_ONLY",),
                decided_at=now,
            )
            repository.decide(
                app.scope, request, placement, require_employee_lineage=True
            )
            NativeDispatchApplication(repository).queue(
                QueueNativeDispatch(
                    app.scope,
                    identity.attempt.attempt_id,
                    placement.placement_id,
                    p.plan_digest,
                    Generation(participant.runtime_generation),
                    AgentInstanceId(participant.agent_instance_id),
                    call.context,
                    ExactGrant("EXECUTION", "START", start_resource(p)),
                    Generation(call.policy_generation),
                    Generation(call.recovery_epoch),
                    agent_name,
                    "prepared-task:" + p.digest + ":" + task.task_id,
                    30,
                    "prepared:" + str(identity.attempt.attempt_id),
                    now,
                )
            )


class PreparedReadyDriver:
    """Restart-safe ready discovery; UNKNOWN/retry-wait never becomes new work."""

    def __init__(self, repository, authority_factory):
        self.repository = repository
        self.authority_factory = authority_factory
        self.coordinator = PreparedNativeCoordinator(repository)

    def tick(self):
        from types import SimpleNamespace

        from .authority_contracts import AuthorityError
        from .execution_preparation import ExecutionPreparation

        with self.repository.pool.connection() as connection:
            rows = connection.execute(
                "SELECT DISTINCT ON (b.namespace,b.security_domain,b.workflow_run_id) "
                "c.payload,p.record FROM execution_authority.prepared_task_bindings b "
                "JOIN execution_authority.attempts a ON a.namespace=b.namespace "
                "AND a.security_domain=b.security_domain AND a.task_run_id=b.task_run_id "
                "JOIN execution_authority.native_dispatch_commands c "
                "ON c.namespace=a.namespace AND c.security_domain=a.security_domain "
                "AND c.attempt_id=a.attempt_id "
                "JOIN execution_authority.run_preparations p "
                "ON p.namespace=b.namespace AND p.security_domain=b.security_domain "
                "AND p.workflow_run_id=b.workflow_run_id "
                "JOIN execution_authority.prepared_run_progress s "
                "ON s.namespace=p.namespace AND s.security_domain=p.security_domain "
                "AND s.workflow_run_id=p.workflow_run_id "
                "WHERE s.record->>'state' IN ('PENDING','RUNNING') "
                "AND s.record->'tasks' @> '[{\"state\":\"READY\"}]'::jsonb "
                "ORDER BY b.namespace,b.security_domain,b.workflow_run_id,c.queued_at LIMIT 32"
            ).fetchall()
        for row in rows:
            command = self.repository._dispatch_command(row["payload"])
            try:
                with (
                    self.repository.pool.connection() as connection,
                    connection.transaction(),
                ):
                    context, authority = self.authority_factory(connection, command)
                    self.coordinator(
                        SimpleNamespace(
                            context=context,
                            authority=authority,
                            connection=connection,
                            policy_generation=command.authority_generation.value,
                            recovery_epoch=command.recovery_epoch.value,
                        ),
                        ExecutionPreparation.model_validate(row["record"]),
                    )
            except (AuthorityError, ExecutionPreparationError):
                # Remains READY with no new Attempt/effect; current readiness is exposed by owner UI.
                continue
