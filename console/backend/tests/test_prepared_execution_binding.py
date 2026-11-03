# ruff: noqa: E501, F811 -- Shared pytest fixture import.
"""Isolated PostgreSQL source-owner migration; no real admission is asserted."""

import hashlib
import json
from pathlib import Path

import pytest
from agent_console.execution_domain import ScopeIdentity
from agent_console.execution_preparation import ExecutionPreparationError
from agent_console.prepared_execution_schema import migrate
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from test_plan_suggestion_v2 import confirm, proposal, repository  # noqa: F401

MIGRATIONS = Path(__file__).parents[1] / "migrations"


def upgrade(repo):
    with repo.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        c.execute((MIGRATIONS / "0014_digital_employee_identity.sql").read_text())
        c.execute((MIGRATIONS / "0015_resource_use_measurement.sql").read_text())
        migrate(c)


def test_reference_backfill_append_and_restart(repository):
    repo = repository
    scope = ScopeIdentity("migration324", "isolated")
    p = proposal()
    with repo.transaction(scope, p.proposal_id, authorized=True) as c:
        repo.add_proposal(c, scope, p)
    before = confirm(repo, scope, p, "first")
    upgrade(repo)
    with repo.pool.connection() as c:
        c.row_factory = dict_row
        row = c.execute("SELECT * FROM execution_authority.plan_references").fetchone()
        assert row["source_owner"] == "PLANNING"
        assert row["plan_id"] == p.proposal_id
        assert row["legacy_id"] is None
        fks = c.execute(
            "SELECT confrelid::regclass::text AS target FROM pg_constraint "
            "WHERE conname='workflow_runs_plan_fk'"
        ).fetchall()
        assert fks == [{"target": "execution_authority.plan_references"}]
    upgrade(repo)  # Restart checks digest; it must not duplicate or rewrite.
    with repo.transaction(scope, p.proposal_id, authorized=True) as c:
        assert repo.read_plan(c, scope, p.proposal_id, 1) == before
    successor = p.model_copy(update={"revision": 2, "predecessor_digest": p.digest})
    with repo.transaction(scope, p.proposal_id, authorized=True) as c:
        repo.add_proposal(c, scope, successor)
    confirm(repo, scope, successor, "second", expected=1)
    with repo.pool.connection() as c:
        c.row_factory = dict_row
        assert (
            c.execute(
                "SELECT count(*) AS n FROM execution_authority.plan_references"
            ).fetchone()["n"]
            == 2
        )
        assert (
            c.execute("SELECT count(*) AS n FROM execution_authority.plans").fetchone()[
                "n"
            ]
            == 0
        )  # No projection of planning-owned Plan/Approval.


def test_migration_mismatch_rolls_back(repository):
    upgrade(repository)
    with repository.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        c.execute(
            "UPDATE execution_authority.schema_migrations SET checksum=%s WHERE version=34",
            (hashlib.sha256(b"foreign-writer").hexdigest(),),
        )
    with pytest.raises(ExecutionPreparationError, match="SCHEMA_INCOMPATIBLE"):
        upgrade(repository)


def test_single_run_exact_participants_and_replay(repository):
    from types import SimpleNamespace

    from agent_console.prepared_execution_application import (
        PreparedExecutionApplication,
    )
    from prepared_execution_support import ExactTestAuthority, seed

    p = seed(repository)
    principal = SimpleNamespace(
        tenant_id=p.namespace,
        security_domain=p.security_domain,
        principal_id="test-requester",
    )
    authority = ExactTestAuthority(p)
    with repository.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        app = PreparedExecutionApplication(c, principal, authority)
        state = app.start(p, "start")
        assert app.start(p, "start") == state
        assert app.start(p, "another-key") == state
        first = app.queue_attempt(p, "t1-read")
        # Root invariant is unchanged; the participant lives in its scoped binding.
        assert str(first.assignment.assignment_id) == p.root_assignment_id
        row = c.execute(
            "SELECT * FROM execution_authority.prepared_task_bindings WHERE task_id='t1-read'"
        ).fetchone()
        assert row["assignment_id"] == p.participants[0].assignment_id
        assert row["assignment_id"] != p.root_assignment_id
        assert (
            c.execute(
                "SELECT count(*) AS n FROM execution_authority.workflow_runs"
            ).fetchone()["n"]
            == 1
        )
        assert (
            c.execute(
                "SELECT count(*) AS n FROM execution_authority.task_runs"
            ).fetchone()["n"]
            == 6
        )
    with repository.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        app = PreparedExecutionApplication(c, principal, authority)
        with pytest.raises(ExecutionPreparationError, match="DISPATCH_NOT_READY"):
            app.queue_attempt(p, "t2-validate")


def test_independent_participant_authority_before_any_identity(repository):
    from types import SimpleNamespace

    from agent_console.prepared_execution_application import (
        PreparedExecutionApplication,
    )
    from prepared_execution_support import ExactTestAuthority, seed

    p = seed(repository)
    principal = SimpleNamespace(
        tenant_id=p.namespace,
        security_domain=p.security_domain,
        principal_id="test-requester",
    )
    authority = ExactTestAuthority(p)
    authority.allowed.remove(f"governed-execution:participant:{p.digest}:t1-read")
    with repository.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        with pytest.raises(PermissionError, match="DENIED"):
            PreparedExecutionApplication(c, principal, authority).start(p, "denied")
        assert (
            c.execute(
                "SELECT count(*) AS n FROM execution_authority.workflow_runs"
            ).fetchone()["n"]
            == 0
        )


def test_native_binding_uses_task_assignment_and_projects_start(repository):
    from datetime import UTC, datetime
    from types import SimpleNamespace

    from agent_console.authority_contracts import (
        AuthenticationSource,
        AuthorityScope,
        ExactGrant,
        TrustedRequestContext,
    )
    from agent_console.execution_domain import VersionedAggregate
    from agent_console.execution_postgres import (
        AgentInstanceId,
        Generation,
        PlacementDecision,
        PlacementDecisionKind,
        PlacementId,
        PlacementRequest,
        PlacementRequestId,
        PostgresExecutionAuthorityRepository,
        RuntimeInstanceId,
    )
    from agent_console.native_dispatch_application import (
        NativeDispatchApplication,
        QueueNativeDispatch,
    )
    from agent_console.prepared_execution_application import (
        PreparedExecutionApplication,
        start_resource,
    )
    from agent_console.prepared_execution_lineage import dispatch_grants
    from prepared_execution_support import ExactTestAuthority, seed

    p = seed(repository)
    scope = ScopeIdentity(p.namespace, p.security_domain)
    principal = SimpleNamespace(
        tenant_id=p.namespace,
        security_domain=p.security_domain,
        principal_id="test-requester",
    )
    with repository.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        app = PreparedExecutionApplication(c, principal, ExactTestAuthority(p))
        app.start(p, "start")
        identity = app.queue_attempt(p, "t1-read")
    native = PostgresExecutionAuthorityRepository(
        repository.pool.conninfo,
        migration_path=MIGRATIONS / "0008_execution_runtime_authority.sql",
    )
    try:
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
                },
            ),
        )
        now = datetime.now(UTC)
        placement_request = PlacementRequest(
            PlacementRequestId("prepared-placement"),
            scope,
            identity.workflow_run.workflow_run_id,
            identity.task_run.task_run_id,
            identity.attempt.attempt_id,
            AgentInstanceId("agent"),
            "1",
            "controlled",
            (),
            (),
            (),
            (),
            now,
        )
        placement = PlacementDecision.create(
            placement_id=PlacementId("prepared-placement"),
            request_id=placement_request.request_id,
            decision=PlacementDecisionKind.PLACED,
            runtime_instance_id=RuntimeInstanceId("native"),
            policy_version="test-policy",
            compatibility_facts=(),
            limitation_codes=(),
            decided_at=now,
        )
        native.decide(
            scope, placement_request, placement, require_employee_lineage=True
        )
        context = TrustedRequestContext(
            principal.principal_id,
            AuthorityScope(*(p.namespace, p.security_domain)),
            "test-credential",
            AuthenticationSource.SERVICE_CREDENTIAL,
            "test-policy",
        )
        queued = NativeDispatchApplication(native).queue(
            QueueNativeDispatch(
                scope,
                identity.attempt.attempt_id,
                placement.placement_id,
                p.plan_digest,
                Generation(1),
                AgentInstanceId("agent"),
                context,
                ExactGrant("EXECUTION", "START", start_resource(p)),
                Generation(1),
                Generation(1),
                "synthetic-cost-agent",
                "prepared synthetic task",
                30,
                "queue",
                now,
            )
        )
        assert str(queued.command.assignment_id) == p.participants[0].assignment_id
        with native.pool.connection() as c:
            assert {
                (g.owner, g.action) for g in dispatch_grants(c, queued.command)
            } == {
                ("EXECUTION", "START"),
                ("KNOWLEDGE", "READ_RESOURCE"),
                ("RUNTIME_PROFILE", "READ_RESOURCE"),
            }
            assert len(dispatch_grants(c, queued.command)) == 4
        claim = native.claim_next("test-worker")
        native.permit_effect(claim, "task-test", lambda *_: True)
        with native.pool.connection() as c:
            state = c.execute(
                "SELECT record FROM execution_authority.prepared_run_progress"
            ).fetchone()["record"]
            assert state["tasks"][0]["state"] == "RUNNING"
            assert state["state"] == "RUNNING"

        # Synthetic owner integration: no real Kubernetes or Human evidence claimed.
        native.record_kubernetes_correlation(
            claim, "task-test", "fixture-kubernetes-uid"
        )
        from agent_console.execution_postgres import (
            NativeTerminalKind,
            NativeTerminalObservation,
        )
        from agent_console.prepared_execution_observations import apply_native
        from agent_console.prepared_skill_invocation import build_request
        from agent_console.resource_use_postgres import PostgresResourceUseRepository
        from agent_console.skill_executor import (
            SkillExecutorRegistry,
            SkillExecutorResult,
        )
        from agent_console.skill_invocation_application import (
            FixedReadOnlyPolicyAuthority,
            GovernedAttemptSkillInvocationService,
            ScopedSkillInvocationAuthorization,
        )
        from agent_console.skill_invocation_postgres import (
            PostgresSkillInvocationRepository,
        )

        with native.pool.connection() as c:
            request = build_request(
                c, scope, identity.attempt.attempt_id, "test-skill-decision"
            )

        class TestExecutor:
            revision = request.executor
            calls = 0

            def invoke(self, *_):
                self.calls += 1
                return SkillExecutorResult(
                    True, {"synthetic": True, "rows": 2}, "fixture-observation"
                )

        executor = TestExecutor()
        resources = PostgresResourceUseRepository(
            repository.pool.conninfo,
            migration_path=MIGRATIONS / "0015_resource_use_measurement.sql",
        )
        skills = PostgresSkillInvocationRepository(
            repository.pool.conninfo,
            migration_path=MIGRATIONS / "0016_skill_invocation.sql",
            resource_use_repository=resources,
        )
        try:
            resources.migrate()
            skills.migrate()
            service = GovernedAttemptSkillInvocationService(
                skills,
                ScopedSkillInvocationAuthorization(
                    scope,
                    "test-requester",
                    frozenset({"INVOKE_SKILL"}),
                    "test-skill-decision",
                ),
                FixedReadOnlyPolicyAuthority(request.policy),
                SkillExecutorRegistry((executor,)),
            )
            result = service.invoke(request, {"synthetic": True})
            assert result.state == "SUCCEEDED"
            assert service.invoke(request, {"synthetic": True}) == result
            assert executor.calls == 1
            with native.pool.connection() as c:
                artifact = c.execute(
                    "SELECT content,artifact_id,digest FROM execution_authority.run_artifacts"
                ).fetchone()
                assert artifact["content"] == '{"rows":2,"synthetic":true}'
                observation = NativeTerminalObservation(
                    queued.command.command_id,
                    NativeTerminalKind.SUCCEEDED,
                    "task-test",
                    "fixture-kubernetes-uid",
                    json.dumps(
                        {
                            "schemaVersion": "prepared-output-reference.v1",
                            "artifactId": artifact["artifact_id"],
                            "digest": artifact["digest"],
                        }
                    ),
                    None,
                    datetime.now(UTC),
                )
                apply_native(c, queued.command, observation)
                state = c.execute(
                    "SELECT record FROM execution_authority.prepared_run_progress"
                ).fetchone()["record"]
                assert state["tasks"][0]["state"] == "SUCCEEDED"
                assert state["tasks"][1]["state"] == "READY"
                assert state["state"] == "RUNNING"
        finally:
            skills.close()
            resources.close()
    finally:
        native.pool.close()


def test_coordinator_atomic_rollback_and_refresh_zero_queue(repository):
    from types import SimpleNamespace

    from agent_console.authority_contracts import (
        AuthenticationSource,
        AuthorityScope,
        TrustedRequestContext,
    )
    from agent_console.execution_domain import VersionedAggregate
    from agent_console.execution_postgres import PostgresExecutionAuthorityRepository
    from agent_console.prepared_execution_application import (
        PreparedExecutionApplication,
    )
    from agent_console.prepared_native_coordinator import PreparedNativeCoordinator
    from prepared_execution_support import ExactTestAuthority, seed

    p = seed(repository)
    scope = ScopeIdentity(p.namespace, p.security_domain)
    principal = SimpleNamespace(
        tenant_id=p.namespace,
        security_domain=p.security_domain,
        principal_id="test-requester",
    )
    authority = ExactTestAuthority(p)
    context = TrustedRequestContext(
        principal.principal_id,
        AuthorityScope(p.namespace, p.security_domain),
        "test-credential",
        AuthenticationSource.SERVICE_CREDENTIAL,
        "test-policy",
    )
    with repository.pool.connection() as c:
        c.row_factory = dict_row
        PreparedExecutionApplication(c, principal, authority).start(p, "start")
    native = PostgresExecutionAuthorityRepository(
        repository.pool.conninfo,
        migration_path=MIGRATIONS / "0008_execution_runtime_authority.sql",
    )
    try:
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
                },
            ),
        )
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

        with pytest.raises(PermissionError):
            queue()
        authority.allowed.add(f"skill-invocation:prepared:{p.digest}:t1-read:1")
        with pytest.raises(ExecutionPreparationError, match="AGENT_NAME_REQUIRED"):
            queue()
        with native.pool.connection() as c:
            assert (
                c.execute(
                    "SELECT count(*) AS n FROM execution_authority.attempts"
                ).fetchone()["n"]
                == 0
            )
            c.execute(
                "UPDATE execution_authority.agent_instances SET record=record || %s WHERE agent_instance_id='agent'",
                (Jsonb({"kubernetes_agent_name": "fixture-synthetic-agent"}),),
            )
        queue()
        queue()
        with native.pool.connection() as c:
            assert (
                c.execute(
                    "SELECT count(*) AS n FROM execution_authority.attempts"
                ).fetchone()["n"]
                == 1
            )
            assert (
                c.execute(
                    "SELECT count(*) AS n FROM execution_authority.native_dispatch_commands"
                ).fetchone()["n"]
                == 1
            )
        from datetime import UTC, datetime, timedelta

        from agent_console.execution_preparation_postgres import PreparedExecutionStore
        from agent_console.prepared_execution_cancellation import request_cancel

        class CancelAuthority:
            def require(self, *args):
                assert args[1:3] == ("EXECUTION", "CANCEL")
                return SimpleNamespace(decision_id="test-cancel-authority")

        with native.pool.connection() as c, c.transaction():
            state = request_cancel(c, principal, CancelAuthority(), p, "cancel-test")
            assert state.state == "CANCEL_REQUESTED"
            assert state.tasks[0].state == "QUEUED"
        claim = native.claim_next("cancel-worker")
        assert native.stop_prepared_before_effect(claim)
        assert native.stop_prepared_before_effect(claim)
        assert (
            native.claim_next(
                "restart-worker", now=datetime.now(UTC) + timedelta(minutes=10)
            )
            is None
        )
        with native.pool.connection() as c:
            state = PreparedExecutionStore(c).read(
                p.namespace, p.security_domain, p.run_id
            )[1]
            assert state.state == "CANCELLED"
            assert state.cancellation_request_id
            assert state.tasks[0].stop_evidence
            assert (
                c.execute(
                    "SELECT count(*) AS n FROM execution_authority.prepared_stop_receipts"
                ).fetchone()["n"]
                == 1
            )
            row = c.execute(
                "SELECT effect_started_at,terminal_record FROM execution_authority.native_dispatch_commands"
            ).fetchone()
            assert row == {"effect_started_at": None, "terminal_record": None}
    finally:
        native.pool.close()


def test_no_start_before_authoritative_evidence_writer(repository):
    from types import SimpleNamespace

    from agent_console.prepared_execution_application import (
        PreparedExecutionApplication,
    )
    from prepared_execution_support import ExactTestAuthority, seed

    p = seed(repository, evidence_ready=False)
    principal = SimpleNamespace(
        principal_id="fixture-requester",
        tenant_id=p.namespace,
        security_domain=p.security_domain,
    )
    with repository.pool.connection() as c, c.transaction():
        app = PreparedExecutionApplication(c, principal, ExactTestAuthority(p))
        with pytest.raises(
            ExecutionPreparationError, match="EVIDENCE_WRITER_NOT_READY"
        ):
            app.start(p, "fixture-inactive-evidence")
        assert (
            c.execute(
                "SELECT count(*) AS n FROM execution_authority.workflow_runs"
            ).fetchone()["n"]
            == 0
        )
