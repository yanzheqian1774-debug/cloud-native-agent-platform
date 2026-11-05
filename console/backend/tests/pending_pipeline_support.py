"""Disposable-DB engineering driver; Kubernetes port is explicitly a fixture."""

from datetime import UTC, datetime
from pathlib import Path

from agent_console.authority_contracts import (
    AuthenticationSource,
    AuthorityScope,
    TrustedRequestContext,
)
from agent_console.execution_application import (
    ExecutionCompletionService,
    ExecutionEvidenceRecord,
    PostgresExecutionCompletionWriter,
    RecordNativeCompletionCommand,
)
from agent_console.prepared_execution_lineage import dispatch_grants
from agent_console.prepared_native_composition import compose, owner_authority_factory
from agent_console.prepared_native_coordinator import PreparedReadyDriver
from agent_console.readonly_continuation_worker import (
    ContinuationDispatchRepository,
    ContinuationWork,
)
from agent_operator.native_dispatch_reconciler import (
    ManagedSkillNativeTransport,
    NativeDispatchWorker,
)
from test_prepared_native_pipeline import FixtureKubernetes


def drive(a, native, policy, tmp_path, task_count, *, expected_definitions):
    assert native.load_checkpoint().state.value == "POSTGRES_ACTIVE"
    reader = a.automation.grants.authorization

    def authorize(c, command):
        context = TrustedRequestContext(
            command.principal_id,
            AuthorityScope(command.scope.namespace, command.scope.security_domain),
            command.credential_id,
            AuthenticationSource(command.authentication_source),
            a.gen.policy_version,
        )
        return all(
            reader.has_current_grants(
                context,
                dispatch_grants(c, command),
                now=datetime.now(UTC),
                generation=command.authority_generation.value,
                recovery_epoch=command.recovery_epoch.value,
                connection=c,
                configure_transaction=False,
            )
        )

    factory = owner_authority_factory(reader, a.gen, authorize)
    work = ContinuationWork(native, policy, factory)
    ready = PreparedReadyDriver(native, factory, eligible_dispatches=work.dispatches)
    caller, composition = compose(
        native.pool,
        a.repository.pool.conninfo,
        Path(__file__).parents[1] / "migrations",
        reader,
        a.gen,
        authorize,
        mode="registered-readonly-v1",
    )
    completion = ExecutionCompletionService(
        native, PostgresExecutionCompletionWriter(native)
    )

    def complete(claim, observation):
        command = claim.command
        identity = native.get_attempt(command.scope, command.attempt_id)
        evidence_id = "explicit-fixture-evidence:" + str(command.attempt_id)
        outcome_id = "explicit-fixture-outcome:" + str(command.attempt_id)
        evidence = ExecutionEvidenceRecord.from_allowlisted(
            dict(
                evidence_record_id=evidence_id,
                namespace=command.scope.namespace,
                security_domain=command.scope.security_domain,
                platform_execution_identity=str(command.attempt_id),
                workflow_identity=str(identity.workflow_run.workflow_run_id),
                task_identity=str(identity.task_run.task_run_id),
                attempt_ordinal=1,
                event_ordinal=1,
                event_type="EXECUTION_OUTCOME",
                occurred_at=observation.observed_at.isoformat(),
                runtime_classification="NATIVE",
                selected_instance_identity=str(command.runtime_instance_id),
                capability_identity=None,
                authorization_decision="ALLOW",
                reason_code="NATIVE_EXECUTION_" + observation.kind.value,
                provider_correlation_id=observation.kubernetes_task_uid,
                provider_call_count=1,
                outcome_classification=observation.kind.value,
                outcome_reference=outcome_id,
                references=[],
                limitation_code="FIXTURE_KUBERNETES_NOT_REAL_QUESTION_ACCEPTANCE",
                supersedes_record_id=None,
                schema_version=1,
            )
        )
        outcome = dict(
            outcome_id=outcome_id,
            workflow_run_id=str(identity.workflow_run.workflow_run_id),
            task_run_id=str(identity.task_run.task_run_id),
            attempt_id=str(command.attempt_id),
            approved_plan_revision_id=command.approved_plan_revision_id,
            evidence_ids=[evidence_id],
            classification=observation.kind.value,
            technical=True,
            business_problem_resolved=False,
        )
        completion.record_native(
            RecordNativeCompletionCommand(
                claim, observation, (evidence,), outcome_id, outcome
            )
        )

    kubernetes = FixtureKubernetes()
    try:
        for _ in range(task_count):
            # Restart the worker each turn while all owner state remains durable.
            worker = NativeDispatchWorker(
                ContinuationDispatchRepository(native, work),
                kubernetes,
                ManagedSkillNativeTransport(caller),
                authorize,
                complete,
                worker_id="explicit-engineering-worker",
                prepare_ready=ready.tick,
            )
            result = worker.run_once()
            assert result.state == "SUCCEEDED", result
        assert worker.run_once().state == "IDLE"
        assert work.evaluate_terminal() == {"evaluated": 1, "blocked": 0}
        assert work.evaluate_terminal() == {"evaluated": 0, "blocked": 0}
        assert len(kubernetes.tasks) == task_count
        with native.pool.connection() as c:
            outcome = c.execute(
                "SELECT record FROM product_outcome.outcomes LIMIT 1"
            ).fetchone()["record"]
            summary = {
                "isolatedEngineeringOnly": True,
                "kubernetesPort": "EXPLICIT_FIXTURE",
                "modelNetworkCalls": 0,
                "realRawQuestionAcceptance": False,
                "registeredSkillTasks": task_count,
                "runs": c.execute(
                    "SELECT count(*) n FROM execution_authority.workflow_runs"
                ).fetchone()["n"],
                "artifacts": c.execute(
                    "SELECT count(*) n FROM execution_authority.run_artifacts"
                ).fetchone()["n"],
                "employeeDefinitions": c.execute(
                    "SELECT count(*) n FROM digital_employee_definition.definitions"
                ).fetchone()["n"],
                "outcome": outcome,
            }
        assert summary["runs"] == 1
        assert summary["artifacts"] == task_count
        assert summary["employeeDefinitions"] == expected_definitions
        summary["longEmployeeDefinitionsUnchangedAfterFixtureSetup"] = True
        return summary
    finally:
        composition.close()
