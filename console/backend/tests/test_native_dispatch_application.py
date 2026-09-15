import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event

import psycopg
import pytest
from agent_console.authority_configuration import (
    CredentialConfiguration,
    StaticAuthorityGeneration,
)
from agent_console.authority_contracts import (
    AuthenticationSource,
    AuthorityScope,
    CredentialId,
    ExactGrant,
    GrantId,
    GrantSource,
    TrustedRequestContext,
)
from agent_console.authority_postgres import PostgresAuthorityRepository
from agent_console.execution_application import (
    ExecutionCompletionService,
    ExecutionEvidenceRecord,
    PostgresExecutionCompletionWriter,
    RecordNativeCompletionCommand,
)
from agent_console.execution_domain import ExecutionConflict, VersionedAggregate
from agent_console.execution_postgres import (
    AgentInstanceId,
    Generation,
    NativeTerminalKind,
    NativeTerminalObservation,
    PlacementDecision,
    PlacementDecisionKind,
    PlacementId,
    PlacementRequest,
    PlacementRequestId,
    PostgresExecutionAuthorityRepository,
    RuntimeInstanceId,
)
from agent_console.grant_administration_application import GenerationAuthorizationReader
from agent_console.native_dispatch_application import (
    NativeDispatchApplication,
    QueueNativeDispatch,
)
from test_execution_application_postgres import approved_plan

DATABASE_URL = os.environ.get("EXECUTION_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL 15 required")
MIGRATIONS = Path(__file__).parents[1] / "migrations"


def clean_database() -> None:
    with psycopg.connect(DATABASE_URL or "", autocommit=True) as connection:
        rows = connection.execute(
            "SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' "
            "AND nspname <> 'information_schema'"
        ).fetchall()
        for (schema,) in rows:
            connection.execute(
                psycopg.sql.SQL("DROP SCHEMA {} CASCADE").format(
                    psycopg.sql.Identifier(schema)
                )
            )
        connection.execute("CREATE SCHEMA public")


def repository():
    clean_database()
    with psycopg.connect(DATABASE_URL or "") as connection:
        for version in range(1, 8):
            connection.execute(
                next(MIGRATIONS.glob(f"{version:04d}_*.sql")).read_text()
            )
    value = PostgresExecutionAuthorityRepository(
        DATABASE_URL or "",
        migration_path=MIGRATIONS / "0008_execution_runtime_authority.sql",
        max_pool_size=8,
    )
    value.migrate()
    value.migrate_native_dispatch(MIGRATIONS / "0022_native_execution_dispatch.sql")
    with value.pool.connection() as connection, connection.transaction():
        connection.execute(
            "UPDATE execution_authority.evidence_cutover SET "
            "state='POSTGRES_ACTIVE',authoritative_writer='POSTGRES'"
        )
    return value


def seeded(value, suffix=None):
    from employee_identity_support import start_chain

    suffix = suffix or uuid.uuid4().hex
    revision, _, _, start_command, started = start_chain(
        value, DATABASE_URL, approved_plan(suffix)
    )
    identity = started.identity
    member = revision.members[0]
    runtime_id = RuntimeInstanceId(f"runtime-{suffix}")
    agent_id = AgentInstanceId(f"agent-{suffix}")
    value.create_aggregate(
        "runtime_instance",
        VersionedAggregate(
            identity.scope, str(runtime_id), 1, {"current_generation": 1}
        ),
    )
    value.create_aggregate(
        "agent_instance",
        VersionedAggregate(
            identity.scope,
            str(agent_id),
            1,
            {
                "agent_revision_id": member.revision_id,
                "agent_definition_id": member.resource_id,
                "agent_digest": member.digest,
                "runtime_instance_id": str(runtime_id),
            },
        ),
    )
    now = datetime.now(UTC)
    placement_request = PlacementRequest(
        PlacementRequestId(f"request-{suffix}"),
        identity.scope,
        identity.workflow_run.workflow_run_id,
        identity.task_run.task_run_id,
        identity.attempt.attempt_id,
        agent_id,
        member.revision_id,
        "runtime-profile",
        (),
        (),
        (),
        (),
        now,
    )
    decision = PlacementDecision.create(
        placement_id=PlacementId(f"placement-{suffix}"),
        request_id=placement_request.request_id,
        decision=PlacementDecisionKind.PLACED,
        runtime_instance_id=runtime_id,
        policy_version="policy-v1",
        compatibility_facts=(),
        limitation_codes=(),
        decided_at=now,
    )
    value.decide(identity.scope, placement_request, decision)
    context = TrustedRequestContext(
        "human:owner",
        AuthorityScope(identity.scope.namespace, identity.scope.security_domain),
        "credential-1",
        AuthenticationSource.SERVICE_CREDENTIAL,
        "policy-v1",
    )
    grant = ExactGrant(
        "EXECUTION", "START", f"governed-execution:{identity.attempt.attempt_id}"
    )
    request = QueueNativeDispatch(
        identity.scope,
        identity.attempt.attempt_id,
        decision.placement_id,
        start_command.approved_plan.plan_digest,
        Generation(1),
        agent_id,
        context,
        grant,
        Generation(1),
        Generation(1),
        "researcher-agent",
        "analyze quality",
        30,
        f"queue-{suffix}",
        now,
    )
    queued = NativeDispatchApplication(value).queue(request)
    return request, queued.command, identity


def terminal(command, kind=NativeTerminalKind.SUCCEEDED):
    return NativeTerminalObservation(
        command.command_id,
        kind,
        "s5-v023-impl-315-task",
        "task-uid-1",
        "done" if kind is NativeTerminalKind.SUCCEEDED else None,
        None if kind is NativeTerminalKind.SUCCEEDED else "RUNTIME_FAILED",
        datetime.now(UTC),
    )


def evidence(identity, suffix="one"):
    return ExecutionEvidenceRecord.from_allowlisted(
        {
            "evidence_record_id": f"native-evidence-{suffix}",
            "namespace": identity.scope.namespace,
            "security_domain": identity.scope.security_domain,
            "platform_execution_identity": str(identity.attempt.attempt_id),
            "workflow_identity": str(identity.workflow_run.workflow_run_id),
            "task_identity": str(identity.task_run.task_run_id),
            "attempt_ordinal": 1,
            "event_ordinal": 1,
            "event_type": "EXECUTION_OUTCOME",
            "occurred_at": datetime.now(UTC).isoformat(),
            "runtime_classification": "NATIVE",
            "selected_instance_identity": "native-runtime",
            "capability_identity": None,
            "authorization_decision": "ALLOW",
            "reason_code": "NATIVE_EXECUTION_TERMINAL",
            "provider_correlation_id": "task-uid-1",
            "provider_call_count": 1,
            "outcome_classification": "SUCCEEDED",
            "outcome_reference": f"native-outcome-{suffix}",
            "references": [],
            "limitation_code": "MODEL_INVOCATION_NOT_PROVEN",
            "supersedes_record_id": None,
            "schema_version": 1,
        }
    )


def outcome(identity, suffix="one"):
    return {
        "outcome_id": f"native-outcome-{suffix}",
        "workflow_run_id": str(identity.workflow_run.workflow_run_id),
        "task_run_id": str(identity.task_run.task_run_id),
        "attempt_id": str(identity.attempt.attempt_id),
        "approved_plan_revision_id": identity.workflow_run.approved_plan_revision_id,
        "evidence_ids": [f"native-evidence-{suffix}"],
        "classification": "SUCCEEDED",
        "technical": True,
        "business_problem_resolved": False,
    }


def test_queue_claim_exact_readback_and_old_worker_fencing() -> None:
    value = repository()
    request, _command, _ = seeded(value)
    replay = NativeDispatchApplication(value).queue(request)
    assert replay.disposition.value == "REPLAYED"
    now = datetime.now(UTC)
    first = value.claim_next("worker-a", now=now, lease_seconds=1)
    assert first is not None
    second = value.claim_next("worker-b", now=now)
    assert second is None
    successor = value.claim_next(
        "worker-b", now=now + timedelta(seconds=2), lease_seconds=30
    )
    assert successor.claim_generation.value == first.claim_generation.value + 1
    with pytest.raises(ExecutionConflict, match="CLAIM_STALE"):
        value.permit_effect(first, "s5-v023-impl-315-task", lambda *_: True, now=now)
    assert (
        value.permit_effect(
            successor,
            "s5-v023-impl-315-task",
            lambda *_: True,
            now=now + timedelta(seconds=2),
        ).value
        == "APPENDED"
    )
    resumed = value.resume_effect_started("worker-b")
    assert resumed is not None
    assert resumed.command == successor.command
    assert resumed.claim_generation == successor.claim_generation
    assert resumed.fencing_token == successor.fencing_token
    assert value.resume_effect_started("worker-a") is None
    value.pool.close()


@pytest.mark.parametrize(
    ("field", "changed"),
    (
        ("approved_plan_digest", "f" * 64),
        ("runtime_generation", Generation(2)),
        ("agent_instance_id", AgentInstanceId("other-agent")),
    ),
)
def test_queue_rejects_persisted_binding_mismatch(field, changed) -> None:
    value = repository()
    request, _command, _ = seeded(value)
    mismatched = replace(
        request,
        **{field: changed, "idempotency_key": f"mismatch-{field}"},
    )
    with pytest.raises(ExecutionConflict, match="BINDING_MISMATCH"):
        NativeDispatchApplication(value).queue(mismatched)
    value.pool.close()


def test_queue_same_idempotency_with_different_payload_conflicts() -> None:
    value = repository()
    request, _command, _ = seeded(value)
    with pytest.raises(ExecutionConflict, match="COMMAND_CONFLICT"):
        NativeDispatchApplication(value).queue(
            replace(request, input_text="different payload")
        )
    value.pool.close()


def test_denied_effect_and_generation_mismatch_have_zero_effect_started() -> None:
    value = repository()
    _, command, _ = seeded(value)
    claim = value.claim_next("worker")
    with pytest.raises(ExecutionConflict, match="NOT_AUTHORIZED"):
        value.permit_effect(claim, "s5-v023-impl-315-task", lambda *_: False)
    with value.pool.connection() as connection:
        state = connection.execute(
            "SELECT state,kubernetes_task_name FROM "
            "execution_authority.native_dispatch_commands WHERE command_id=%s",
            (str(command.command_id),),
        ).fetchone()
    assert state == {"state": "CLAIMED", "kubernetes_task_name": None}
    value.pool.close()


def test_unknown_is_terminal_for_dispatch_and_never_reclaimed() -> None:
    value = repository()
    _, command, _ = seeded(value)
    claim = value.claim_next("worker")
    value.permit_effect(claim, "s5-v023-impl-315-task", lambda *_: True)
    unknown = NativeTerminalObservation(
        command.command_id,
        NativeTerminalKind.UNKNOWN,
        "s5-v023-impl-315-task",
        None,
        None,
        "TRANSPORT_AMBIGUOUS",
        datetime.now(UTC),
    )
    assert value.record_uncertain(claim, unknown).value == "APPENDED"
    assert value.record_uncertain(claim, unknown).value == "REPLAYED"
    assert value.claim_next("worker-new") is None
    value.pool.close()


@pytest.mark.parametrize(
    "checkpoint", ["command_terminal", "attempt_terminal", "evidence", "outcome"]
)
def test_terminal_bundle_rolls_back_then_replays_atomically(checkpoint) -> None:
    value = repository()
    _, command, identity = seeded(value)
    claim = value.claim_next("worker")
    value.permit_effect(claim, "s5-v023-impl-315-task", lambda *_: True)
    value.record_kubernetes_correlation(claim, "s5-v023-impl-315-task", "task-uid-1")
    observation = terminal(command)
    record = evidence(identity, checkpoint)
    result = outcome(identity, checkpoint)

    def fail(name):
        if name == checkpoint:
            raise RuntimeError("injected-crash")

    service = ExecutionCompletionService(
        value, PostgresExecutionCompletionWriter(value, checkpoint=fail)
    )
    command_record = RecordNativeCompletionCommand(
        claim,
        observation,
        (record,),
        result["outcome_id"],
        result,
    )
    with pytest.raises(RuntimeError, match="injected-crash"):
        service.record_native(command_record)
    with value.pool.connection() as connection:
        row = connection.execute(
            "SELECT state,terminal_record FROM "
            "execution_authority.native_dispatch_commands WHERE command_id=%s",
            (str(command.command_id),),
        ).fetchone()
        counts = connection.execute(
            "SELECT (SELECT count(*) FROM execution_authority.execution_evidence "
            "WHERE evidence_record_id=%s) AS evidence,(SELECT count(*) FROM "
            "execution_authority.outcomes WHERE outcome_id=%s) AS outcome",
            (record.evidence_record_id, result["outcome_id"]),
        ).fetchone()
    assert row == {"state": "EFFECT_STARTED", "terminal_record": None}
    assert counts == {"evidence": 0, "outcome": 0}
    healthy = ExecutionCompletionService(
        value, PostgresExecutionCompletionWriter(value)
    )
    assert healthy.record_native(command_record).disposition.value == "APPENDED"
    assert healthy.record_native(command_record).disposition.value == "REPLAYED"
    conflict = NativeTerminalObservation(
        command.command_id,
        NativeTerminalKind.FAILED,
        "s5-v023-impl-315-task",
        "task-uid-1",
        None,
        "DIFFERENT_TERMINAL",
        datetime.now(UTC),
    )
    with pytest.raises(Exception, match="TERMINAL_CONFLICT"):
        healthy.record_native(
            RecordNativeCompletionCommand(
                claim,
                conflict,
                (record,),
                result["outcome_id"],
                {**result, "classification": "FAILED"},
            )
        )
    value.pool.close()


def test_concurrent_claim_has_one_winner() -> None:
    value = repository()
    seeded(value)
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(value.claim_next, ("worker-a", "worker-b")))
    assert sum(claim is not None for claim in claims) == 1
    value.pool.close()


def current_authorization(value, command):
    migration = MIGRATIONS / "0018_browser_session_grant_authority.sql"
    authority = PostgresAuthorityRepository(
        DATABASE_URL or "", migration_path=migration
    )
    authority.migrate()
    now = datetime.now(UTC)
    context = TrustedRequestContext(
        command.principal_id,
        AuthorityScope(command.scope.namespace, command.scope.security_domain),
        command.credential_id,
        AuthenticationSource.SERVICE_CREDENTIAL,
        "policy-v1",
    )
    grant = ExactGrant(
        command.authorization_owner,
        command.authorization_action,
        command.authorization_resource,
    )
    credential = CredentialConfiguration(
        CredentialId(command.credential_id),
        "c" * 64,
        command.principal_id,
        context.scope,
        now + timedelta(hours=1),
        GrantSource.SERVICE_ONLY,
        (),
    )
    generation = StaticAuthorityGeneration(
        1,
        "g" * 64,
        "policy-v1",
        "test",
        (credential,),
        (),
        frozenset(),
    )
    with authority.pool.connection() as connection, connection.transaction():
        connection.execute(
            "INSERT INTO authorization_admin.active_generation VALUES"
            "(true,1,%s,1,%s,%s)",
            ("a" * 64, "operator:test", now),
        )
        connection.execute(
            "INSERT INTO authorization_admin.grant_requests"
            "(request_id,subject_principal_id,tenant_id,security_domain,purpose,"
            "state,created_at,decided_at) VALUES"
            "('request-1',%s,%s,%s,'NATIVE_DISPATCH','APPROVED',%s,%s)",
            (
                command.principal_id,
                command.scope.namespace,
                command.scope.security_domain,
                now,
                now,
            ),
        )
        connection.execute(
            "INSERT INTO authorization_admin.grant_decisions VALUES"
            "('decision-1','request-1','human:admin','meta-1',true,'ASSIGNED_DUTY',"
            "'TICKET',%s,'policy-v1','test',%s)",
            ("b" * 64, now),
        )
        values = (
            "grant-1",
            "decision-1",
            "request-1",
            command.principal_id,
            command.scope.namespace,
            command.scope.security_domain,
            grant.owner,
            grant.action,
            grant.exact_resource,
            "TICKET",
            "b" * 64,
            "human:admin",
            "meta-1",
            "policy-v1",
            "test",
            now,
            now + timedelta(hours=1),
            now,
            1,
        )
        connection.execute(
            "INSERT INTO authorization_admin.grants VALUES("
            + ",".join(["%s"] * 19)
            + ")",
            values,
        )
        connection.execute(
            "INSERT INTO authorization_admin.effective_grants VALUES"
            "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                "grant-1",
                command.principal_id,
                command.scope.namespace,
                command.scope.security_domain,
                grant.owner,
                grant.action,
                grant.exact_resource,
                now,
                now + timedelta(hours=1),
                1,
            ),
        )
    reader = GenerationAuthorizationReader(
        generation, authority, authority, recovery_epoch=1
    )

    def check(connection, checked):
        assert checked == command
        return reader.has_current_grants(
            context,
            (grant,),
            now=datetime.now(UTC),
            generation=1,
            recovery_epoch=1,
            connection=connection,
            configure_transaction=False,
        )[0]

    return authority, check


def test_revocation_first_prevents_effect_and_effect_first_serializes_revocation() -> (
    None
):
    value = repository()
    _, command, _ = seeded(value)
    authority, check = current_authorization(value, command)
    first = value.claim_next("worker-a")
    authority.revoke_grant(
        GrantId("grant-1"),
        actor_id="human:admin",
        reason="DUTY_ENDED",
        idempotency_key="revoke-first",
        payload_digest="d" * 64,
        now=datetime.now(UTC),
    )
    with pytest.raises(ExecutionConflict, match="NOT_AUTHORIZED"):
        value.permit_effect(first, "s5-v023-impl-315-task", check)
    authority.close()
    value.pool.close()

    value = repository()
    _, command, _ = seeded(value)
    authority, check = current_authorization(value, command)
    claim = value.claim_next("worker-b")
    locked = Event()
    release = Event()

    def checkpoint():
        locked.set()
        assert release.wait(timeout=10)

    authority._authorization_grants_locked_checkpoint = checkpoint
    with ThreadPoolExecutor(max_workers=2) as pool:
        effect = pool.submit(
            value.permit_effect,
            claim,
            "s5-v023-impl-315-task",
            check,
        )
        assert locked.wait(timeout=10)
        revoked = pool.submit(
            authority.revoke_grant,
            GrantId("grant-1"),
            actor_id="human:admin",
            reason="DUTY_ENDED",
            idempotency_key="revoke-second",
            payload_digest="e" * 64,
            now=datetime.now(UTC),
        )
        assert not revoked.done()
        release.set()
        assert effect.result(timeout=10).value == "APPENDED"
        assert revoked.result(timeout=10) is True
    authority.close()
    value.pool.close()
