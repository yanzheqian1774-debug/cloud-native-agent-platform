import os
import subprocess
import sys
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from agent_console.execution_domain import ExecutionConflict
from agent_console.execution_postgres import (
    CommandId,
    CommandResult,
    Generation,
    PlacementDecision,
    PlacementDecisionKind,
    PlacementId,
    PlacementRequest,
    PlacementRequestId,
    PostgresExecutionAuthorityRepository,
    RuntimeDesiredState,
    RuntimeDesiredStateKind,
)
from agent_core.execution_contract import canonical_digest
from agent_core.openclaw_binding import (
    AssociationStatus,
    OpenClawBindingObservation,
    OpenClawGenerationBinding,
    OpenClawRuntimeBinding,
)
from employee_identity_support import start_chain
from test_execution_application_postgres import approved_plan
from test_execution_postgres import seed_runtime_agent

DATABASE_URL = os.environ.get("EXECUTION_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL 15 required")
MIGRATIONS = Path(__file__).parents[1] / "migrations"
BASE_MIGRATION = MIGRATIONS / "0008_execution_runtime_authority.sql"
BINDING_MIGRATION = MIGRATIONS / "0021_openclaw_runtime_binding.sql"


def repository():
    value = PostgresExecutionAuthorityRepository(
        DATABASE_URL or "", migration_path=BASE_MIGRATION
    )
    value.migrate()
    value.migrate_openclaw_bindings(BINDING_MIGRATION)
    return value


def seed(value, suffix):
    revision, _, _, _, started = start_chain(value, DATABASE_URL, approved_plan(suffix))
    scope = started.identity.scope
    runtime_id, agent_instance_id = seed_runtime_agent(
        value, scope, suffix, revision.members[0]
    )
    now = datetime.now(UTC)
    request = PlacementRequest(
        PlacementRequestId(f"request-{suffix}"),
        scope,
        started.identity.workflow_run.workflow_run_id,
        started.identity.task_run.task_run_id,
        started.identity.attempt.attempt_id,
        agent_instance_id,
        revision.members[0].revision_id,
        f"runtime-profile-{suffix}",
        (),
        (),
        (),
        (),
        now,
    )
    placement = PlacementDecision.create(
        placement_id=PlacementId(f"placement-{suffix}"),
        request_id=request.request_id,
        decision=PlacementDecisionKind.PLACED,
        runtime_instance_id=runtime_id,
        policy_version="v1",
        compatibility_facts=(),
        limitation_codes=(),
        decided_at=now,
    )
    value.decide(scope, request, placement)
    command = RuntimeDesiredState(
        runtime_id,
        Generation(1),
        RuntimeDesiredStateKind.OBSERVE,
        CommandId(f"command-{suffix}-g1"),
        "operator",
        now,
        now + timedelta(seconds=30),
        "READ_ONLY_RECOVERY",
    )
    value.append_command(scope, command)
    binding = OpenClawRuntimeBinding(
        scope,
        runtime_id,
        placement.placement_id,
        "a" * 64,
        f"openclaw-agent-{suffix}",
        f"/srv/openclaw/{suffix}",
        "gateway-host-1",
        "persistent-volume-1",
        "2026.7.1-2",
        f"authorization-{suffix}",
        now,
    )
    generation = OpenClawGenerationBinding(
        scope,
        runtime_id,
        Generation(1),
        f"agent:{binding.agent_id}:{runtime_id}-g1",
        f"session-{suffix}-g1",
        command.command_id,
        f"idempotency-{suffix}-g1",
        canonical_digest(command),
        AssociationStatus.UNVERIFIED,
        0,
        now,
    )
    return binding, generation, command


def observation(binding, generation, high_water, *, status=AssociationStatus.MATCHED):
    now = datetime.now(UTC)
    matched = status is AssociationStatus.MATCHED
    return OpenClawBindingObservation(
        binding.scope,
        binding.runtime_instance_id,
        generation.generation,
        high_water,
        status,
        now,
        now + timedelta(seconds=30),
        binding.source_version,
        "OPENCLAW_COMPOSITE_ASSOCIATION_MATCHED"
        if matched
        else "OPENCLAW_SESSION_MISSING_OR_AMBIGUOUS",
        True,
        True,
        True,
        matched,
    )


def test_persistence_uniqueness_replay_high_water_rollback_and_restart():
    value = repository()
    suffix = uuid.uuid4().hex
    binding, generation, _ = seed(value, suffix)

    assert value.save_openclaw_binding(binding, generation).value == "APPENDED"
    assert value.save_openclaw_binding(binding, generation).value == "REPLAYED"
    assert [
        fact.result
        for fact in value.read_command_results(binding.scope, generation.command_id)
    ] == [CommandResult.REQUESTED]
    assert value.get_openclaw_binding(
        binding.scope, binding.runtime_instance_id, generation.generation
    ) == (binding, generation)

    first = observation(binding, generation, 1)
    assert value.append_openclaw_observation(first).value == "APPENDED"
    assert value.append_openclaw_observation(first).value == "REPLAYED"
    with pytest.raises(
        ExecutionConflict, match="OPENCLAW_OBSERVATION_HIGH_WATER_REGRESSION"
    ):
        value.append_openclaw_observation(
            replace(first, association_status=AssociationStatus.RECOVERY_REQUIRED)
        )
    with pytest.raises(ExecutionConflict, match="OPENCLAW_OBSERVATION_HIGH_WATER_GAP"):
        value.append_openclaw_observation(observation(binding, generation, 3))
    second = observation(
        binding, generation, 2, status=AssociationStatus.RECOVERY_REQUIRED
    )
    assert value.append_openclaw_observation(second).value == "APPENDED"
    assert value.read_openclaw_observations(
        binding.scope, binding.runtime_instance_id, generation.generation
    ) == (first, second)
    assert [
        fact.result
        for fact in value.read_command_results(binding.scope, generation.command_id)
    ] == [
        CommandResult.REQUESTED,
        CommandResult.OBSERVED,
        CommandResult.RECOVERY_REQUIRED,
    ]

    recovered_generation = value.get_openclaw_binding(
        binding.scope, binding.runtime_instance_id, generation.generation
    )[1]
    assert recovered_generation.observation_high_water == 2
    assert (
        recovered_generation.association_status is AssociationStatus.RECOVERY_REQUIRED
    )

    other_binding, other_generation, _ = seed(value, f"other-{suffix}")
    assert other_binding.scope != binding.scope
    duplicate_external = replace(
        other_binding,
        gateway_digest=binding.gateway_digest,
        agent_id=binding.agent_id,
        canonical_workspace=binding.canonical_workspace,
        workspace_host=binding.workspace_host,
        workspace_storage_domain=binding.workspace_storage_domain,
    )
    with pytest.raises(ExecutionConflict):
        value.save_openclaw_binding(duplicate_external, other_generation)
    assert (
        value.get_openclaw_binding(
            other_binding.scope,
            other_binding.runtime_instance_id,
            other_generation.generation,
        )
        is None
    )

    value.pool.close()
    recovered = repository()
    loaded = recovered.get_openclaw_binding(
        binding.scope, binding.runtime_instance_id, generation.generation
    )
    assert loaded is not None
    assert loaded[0] == binding
    assert loaded[1].observation_high_water == 2
    assert recovered.read_openclaw_observations(
        binding.scope, binding.runtime_instance_id, generation.generation
    ) == (first, second)
    recovered.pool.close()

    root = Path(__file__).parents[3]
    code = f"""
from pathlib import Path
from agent_console.execution_postgres import PostgresExecutionAuthorityRepository
from agent_core.execution_contract import Generation, RuntimeInstanceId, ScopeIdentity
repo = PostgresExecutionAuthorityRepository(
    {DATABASE_URL!r},
    migration_path=Path({str(BASE_MIGRATION)!r}),
)
value = repo.get_openclaw_binding(
    ScopeIdentity({binding.scope.namespace!r}, {binding.scope.security_domain!r}),
    RuntimeInstanceId({str(binding.runtime_instance_id)!r}),
    Generation(1),
)
assert value is not None and value[1].observation_high_water == 2
repo.pool.close()
"""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = ":".join(
        str(root / path) for path in ("core/src", "console/backend/src", "runtime/src")
    )
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=root,
        env=environment,
        check=True,
        timeout=30,
    )


def test_generation_session_and_idempotency_uniqueness():
    value = repository()
    suffix = uuid.uuid4().hex
    binding, generation, first_command = seed(value, suffix)
    value.save_openclaw_binding(binding, generation)
    now = datetime.now(UTC)
    second_command = RuntimeDesiredState(
        binding.runtime_instance_id,
        Generation(2),
        RuntimeDesiredStateKind.OBSERVE,
        CommandId(f"command-{suffix}-g2"),
        "operator",
        now,
        now + timedelta(seconds=30),
        "READ_ONLY_RECOVERY",
    )
    value.append_command(binding.scope, second_command)
    second = replace(
        generation,
        generation=Generation(2),
        session_key=f"agent:{binding.agent_id}:{binding.runtime_instance_id}-g2",
        session_id=f"session-{suffix}-g2",
        command_id=second_command.command_id,
        idempotency_key=f"idempotency-{suffix}-g2",
        command_payload_digest=canonical_digest(second_command),
        recorded_at=now,
    )
    assert value.save_openclaw_binding(binding, second).value == "APPENDED"

    conflicting_key = replace(
        second,
        idempotency_key=generation.idempotency_key,
    )
    with pytest.raises(ExecutionConflict, match="OPENCLAW_IDEMPOTENCY_KEY_CONFLICT"):
        value.save_openclaw_binding(binding, conflicting_key)

    third_command = replace(
        second_command,
        desired_generation=Generation(3),
        command_id=CommandId(f"command-{suffix}-g3"),
    )
    value.append_command(binding.scope, third_command)
    duplicate_session = replace(
        second,
        generation=Generation(3),
        command_id=third_command.command_id,
        idempotency_key=f"idempotency-{suffix}-g3",
        command_payload_digest=canonical_digest(third_command),
    )
    with pytest.raises(ExecutionConflict):
        value.save_openclaw_binding(binding, duplicate_session)
    assert (
        value.get_openclaw_binding(
            binding.scope, binding.runtime_instance_id, Generation(3)
        )
        is None
    )
    assert first_command != second_command
    value.pool.close()
