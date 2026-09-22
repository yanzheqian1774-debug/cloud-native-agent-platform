# ruff: noqa: F811 -- Isolated PostgreSQL fixture import.
"""Six-task owner pipeline with explicit fake Kubernetes; not actual acceptance."""

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
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
from agent_console.execution_domain import ScopeIdentity, VersionedAggregate
from agent_console.execution_postgres import PostgresExecutionAuthorityRepository
from agent_console.execution_preparation_postgres import PreparedExecutionStore
from agent_console.prepared_execution_application import PreparedExecutionApplication
from agent_console.prepared_native_composition import POLICY
from agent_console.prepared_native_coordinator import PreparedNativeCoordinator
from agent_console.prepared_native_skill import PreparedNativeSkillCaller
from agent_console.prepared_result_review import PreparedResultReview
from agent_console.skill_executor import SkillExecutorRegistry
from agent_console.skill_invocation_application import FixedReadOnlyPolicyAuthority
from agent_console.skill_invocation_composition import compose_governed_skill_invocation
from agent_console.synthetic_cost_skill import SyntheticCostSkillExecutor
from agent_operator.native_dispatch_reconciler import (
    ManagedSkillNativeTransport,
    NativeDispatchWorker,
)
from prepared_execution_support import ExactTestAuthority, seed
from test_execution_preparation import preparation
from test_plan_suggestion_v2 import repository  # noqa: F401
from test_prepared_result_review import ReviewAuthority, seed_criteria

MIGRATIONS = Path(__file__).parents[1] / "migrations"


class FixtureKubernetes:
    def __init__(self):
        self.tasks = {}

    def create(self, claim, name):
        assert name not in self.tasks
        self.tasks[name] = {
            "metadata": {"uid": "fixture-kubernetes-" + name},
            "status": {},
        }
        return self.tasks[name]

    def read(self, claim, name):
        return self.tasks.get(name)

    def patch_status(self, command, name, status):
        self.tasks[name]["status"] = status


@pytest.mark.parametrize("case", ["cost", "delivery"])
def test_six_task_managed_skill_pipeline_restart_readback_and_no_redispatch(
    repository, tmp_path, case
):
    baseline = PostgresExecutionAuthorityRepository(
        repository.pool.conninfo,
        migration_path=MIGRATIONS / "0008_execution_runtime_authority.sql",
    )
    try:
        baseline.migrate()
    finally:
        baseline.pool.close()
    digest = hashlib.sha256(b"fixture").hexdigest()
    target = preparation().semantics.target
    target = target.model_copy(
        update={
            "problem": target.problem.model_copy(update={"digest": digest}),
            "criteria": target.criteria.model_copy(update={"digest": digest}),
        }
    )
    p = seed(repository, synthetic_skill=case, evidence_ready=False, target=target)
    seed_criteria(repository, p)
    scope = ScopeIdentity(p.namespace, p.security_domain)
    principal = SimpleNamespace(
        principal_id="fixture-requester",
        tenant_id=p.namespace,
        security_domain=p.security_domain,
    )
    authority = ExactTestAuthority(p)
    authority.allowed.update(
        f"skill-invocation:prepared:{p.digest}:{t.task_id}:1" for t in p.participants
    )
    context = TrustedRequestContext(
        principal.principal_id,
        AuthorityScope(p.namespace, p.security_domain),
        "fixture-credential",
        AuthenticationSource.SERVICE_CREDENTIAL,
        "fixture-policy",
    )
    native = PostgresExecutionAuthorityRepository(
        repository.pool.conninfo,
        migration_path=MIGRATIONS / "0008_execution_runtime_authority.sql",
    )
    skills = None
    try:
        from agent_console.execution_evidence_cutover import EvidenceCutoverCoordinator
        from agent_console.execution_evidence_import import SQLiteEvidenceImporter
        from agent_core.execution_evidence import SQLiteExecutionEvidenceRepository
        from agent_core.execution_evidence.postgres import (
            PostgresExecutionEvidenceRepository,
        )

        source = tmp_path / "fixture-empty-evidence.sqlite"
        SQLiteExecutionEvidenceRepository(source)
        target = PostgresExecutionEvidenceRepository(repository.pool.conninfo)
        try:
            SQLiteEvidenceImporter(source, native, target).import_all(
                writer_quiesced=True
            )
            EvidenceCutoverCoordinator(native).activate_postgres(
                sqlite_quiesced=True, parity_verified=True
            )
        finally:
            target.pool.close()
        native.migrate_native_dispatch(
            MIGRATIONS / "0022_native_execution_dispatch.sql"
        )
        native.create_aggregate(
            "runtime_instance",
            VersionedAggregate(scope, "native", 1, {"current_generation": 1}),
        )
        native.create_aggregate(
            "agent_instance",
            VersionedAggregate(
                scope,
                "agent",
                1,
                {
                    "agent_revision_id": "1",
                    "agent_definition_id": "agent-definition",
                    "agent_digest": "a" * 64,
                    "runtime_instance_id": "native",
                    "kubernetes_agent_name": "fixture-cost-agent",
                },
            ),
        )
        with native.pool.connection() as c, c.transaction():
            PreparedExecutionApplication(c, principal, authority).start(p, "start")
        coordinator = PreparedNativeCoordinator(native)

        def queue():
            with native.pool.connection() as c, c.transaction():
                coordinator(
                    SimpleNamespace(
                        connection=c,
                        context=context,
                        authority=authority,
                        policy_generation=1,
                        recovery_epoch=1,
                    ),
                    p,
                )

        from agent_console.synthetic_delivery_skill import (
            SyntheticDeliverySkillExecutor,
        )

        executor = (
            SyntheticDeliverySkillExecutor()
            if case == "delivery"
            else SyntheticCostSkillExecutor()
        )
        skills = compose_governed_skill_invocation(
            repository.pool.conninfo,
            MIGRATIONS,
            None,
            FixedReadOnlyPolicyAuthority(POLICY),
            SkillExecutorRegistry((executor,)),
        )
        caller = PreparedNativeSkillCaller(
            native.pool, skills, lambda *_: "fixture-skill-authority"
        )
        caller_errors = []
        original_invoke = caller.invoke

        def traced_invoke(command):
            try:
                return original_invoke(command)
            except Exception as error:
                caller_errors.append((type(error).__name__, str(error)))
                raise

        caller.invoke = traced_invoke
        completion = ExecutionCompletionService(
            native, PostgresExecutionCompletionWriter(native)
        )

        def complete(claim, observation):
            command = claim.command
            identity = native.get_attempt(scope, command.attempt_id)
            evidence_id = "fixture-evidence:" + str(command.attempt_id)
            outcome_id = "fixture-outcome:" + str(command.attempt_id)
            evidence = ExecutionEvidenceRecord.from_allowlisted(
                {
                    "evidence_record_id": evidence_id,
                    "namespace": p.namespace,
                    "security_domain": p.security_domain,
                    "platform_execution_identity": str(command.attempt_id),
                    "workflow_identity": p.run_id,
                    "task_identity": str(identity.task_run.task_run_id),
                    "attempt_ordinal": 1,
                    "event_ordinal": 1,
                    "event_type": "EXECUTION_OUTCOME",
                    "occurred_at": observation.observed_at.isoformat(),
                    "runtime_classification": "NATIVE",
                    "selected_instance_identity": "native",
                    "capability_identity": None,
                    "authorization_decision": "ALLOW",
                    "reason_code": "NATIVE_EXECUTION_SUCCEEDED",
                    "provider_correlation_id": observation.kubernetes_task_uid,
                    "provider_call_count": 1,
                    "outcome_classification": observation.kind.value,
                    "outcome_reference": outcome_id,
                    "references": [],
                    "limitation_code": "FIXTURE_KUBERNETES_NOT_ACCEPTANCE",
                    "supersedes_record_id": None,
                    "schema_version": 1,
                }
            )
            outcome = {
                "outcome_id": outcome_id,
                "workflow_run_id": p.run_id,
                "task_run_id": str(identity.task_run.task_run_id),
                "attempt_id": str(command.attempt_id),
                "approved_plan_revision_id": command.approved_plan_revision_id,
                "evidence_ids": [evidence_id],
                "classification": observation.kind.value,
                "technical": True,
                "business_problem_resolved": False,
            }
            completion.record_native(
                RecordNativeCompletionCommand(
                    claim, observation, (evidence,), outcome_id, outcome
                )
            )

        kubernetes = FixtureKubernetes()

        def worker():
            return NativeDispatchWorker(
                native,
                kubernetes,
                ManagedSkillNativeTransport(caller),
                lambda *_: True,
                complete,
                worker_id="fixture-native-worker",
                prepare_ready=queue,
            )

        for _ in range(6):
            result = worker().run_once()  # fresh worker, same durable owner state
            assert result.state == "SUCCEEDED", caller_errors
        assert worker().run_once().state == "IDLE"
        assert len(kubernetes.tasks) == 6
        with native.pool.connection() as c:
            _, progress = PreparedExecutionStore(c).read(
                p.namespace, p.security_domain, p.run_id
            )
            assert progress.state == "SUCCEEDED"
            artifacts = c.execute(
                "SELECT task_id,content,digest FROM execution_authority.run_artifacts "
                "ORDER BY task_id"
            ).fetchall()
            assert len(artifacts) == 6
            assert "UNDETERMINED" in artifacts[-1]["content"]
            assert (
                c.execute(
                    "SELECT count(*) AS n FROM execution_authority.attempts"
                ).fetchone()["n"]
                == 6
            )
        with native.pool.connection() as c, c.transaction():
            review = PreparedResultReview(c, principal, ReviewAuthority())
            evaluated = review.evaluate(p, "fixture-six-task-evaluation")
            assert evaluated["businessResolution"] == "UNDETERMINED"
            assert len(evaluated["evaluation"]["results"][0]["artifactIds"]) == 6
            snapshot = c.execute(
                "SELECT record FROM success_criteria_evaluation.snapshots"
            ).fetchone()["record"]
            assert len(snapshot["resourceUseSnapshots"]) == 6
            assert (
                snapshot["criteriaSet"]["digest"] == p.semantics.target.criteria.digest
            )
            assert snapshot["runState"] == "SUCCEEDED"
            if case == "delivery":
                from agent_console.delivery_evaluation import CHECKS, evaluate
                from agent_console.resource_use_domain import canonical_digest

                source, report = review.delivery_evidence(p, snapshot)
                for check in CHECKS:
                    criterion = {
                        "criterion_type": "DETERMINISTIC_BOOLEAN",
                        "measurement": {"expected": True},
                        "evaluator_type": "SYNTHETIC_DELIVERY",
                        "evaluator_version": "1",
                        "required_evidence_kinds": [
                            "NATIVE_EXECUTION_ARTIFACT",
                            "PUBLISHED_SYNTHETIC_SOURCE",
                        ],
                        "applicability": {
                            "check": check,
                            "sourceContentDigest": canonical_digest(source),
                        },
                    }
                    assert (
                        evaluate(
                            criterion,
                            source,
                            report,
                            p.source_snapshot.model_dump(mode="json"),
                        )[0]
                        == "SATISFIED"
                    )
        # Reopening the PG adapter also must not queue another effect.
        reopened = PostgresExecutionAuthorityRepository(
            repository.pool.conninfo,
            migration_path=MIGRATIONS / "0008_execution_runtime_authority.sql",
        )
        try:
            reopened.compatibility()
            assert reopened.claim_next("fixture-restarted-worker") is None
        finally:
            reopened.pool.close()
    finally:
        if skills is not None:
            skills.close()
        native.pool.close()
