import inspect
import json
from dataclasses import fields
from datetime import UTC, datetime, timedelta
from pathlib import Path

from agent_core.execution_contract import (
    AMBIGUOUS_COMMAND_RESULTS,
    CommandId,
    CommandResult,
    ExternalCorrelation,
    Generation,
    ObservationId,
    RuntimeDesiredState,
    RuntimeDesiredStateKind,
    RuntimeHealth,
    RuntimeInstanceId,
    RuntimeObservation,
    RuntimeObservedStateKind,
    RuntimeReadiness,
    may_reissue_command,
)
from agent_core.runtime_control import (
    ScopedRuntimeCommand,
    classify_reconciliation,
)
from agent_runtime.providers.openclaw import EXACT_TARGET
from agent_runtime.providers.openclaw.production_transport import (
    OpenClawProductionTransport,
)

CONFORMANCE = (
    Path(__file__).parents[3]
    / "manifests/acceptance/openclaw/openclaw-lifecycle-conformance-v1.json"
)


def _contract() -> dict[str, object]:
    return json.loads(CONFORMANCE.read_text())


def _desired(now: datetime) -> RuntimeDesiredState:
    return RuntimeDesiredState(
        RuntimeInstanceId("runtime-c1"),
        Generation(1),
        RuntimeDesiredStateKind.RUNNING,
        CommandId("command-c1-g1-start"),
        "principal-1",
        now,
        now + timedelta(seconds=30),
        "HUMAN_APPROVED_START",
    )


def _observation(now: datetime) -> RuntimeObservation:
    return RuntimeObservation(
        ObservationId("observation-c1-g1-1"),
        RuntimeInstanceId("runtime-c1"),
        Generation(1),
        RuntimeObservedStateKind.RUNNING,
        RuntimeHealth.HEALTHY,
        RuntimeReadiness.READY,
        now,
        now + timedelta(seconds=30),
        ExternalCorrelation("openclaw", "session", "opaque-correlation"),
        None,
        ("OPENCLAW_NATIVE_OWNERSHIP_UNSUPPORTED",),
    )


def test_schema_reuses_accepted_execution_contract_without_new_authority() -> None:
    contract = _contract()
    reuse = contract["platformSchemaReuse"]

    desired_fields = {item.name for item in fields(RuntimeDesiredState)}
    scoped_fields = {item.name for item in fields(ScopedRuntimeCommand)}
    observation_fields = {item.name for item in fields(RuntimeObservation)}

    assert contract["status"] == "INTERNAL_CONFORMANCE_PROPOSED_NOT_FROZEN"
    assert reuse["desiredCommandOwner"] == "PostgresExecutionAuthorityRepository"
    assert reuse["observationOwner"] == "PostgresExecutionAuthorityRepository"
    assert {
        "runtime_instance_id",
        "desired_generation",
        "desired_state",
        "command_id",
        "requested_by",
        "requested_at",
        "deadline",
        "reason_classification",
    } <= desired_fields
    assert {
        "scope",
        "authorization_reference",
        "placement_reference",
    } <= scoped_fields
    assert set(reuse["observationFields"]) == observation_fields
    assert (
        "DURABLE_EXPLICIT_IDEMPOTENCY_KEY_SEPARATE_FROM_COMMAND_ID"
        in reuse["missingForOpenClawMapping"]
    )


def test_human_accepted_identity_and_inheritance_directions_are_explicit() -> None:
    contract = _contract()
    directions = set(contract["authority"]["humanAcceptedDirections"])
    correlation = contract["identityCorrelationSchema"]["nativeCorrelation"]
    inheritance = contract["stateInheritance"]

    assert "ONE_RUNTIME_INSTANCE_ONE_EXCLUSIVE_AGENT_WORKSPACE" in directions
    assert "PLATFORM_GENERATION_DISTINCT_FROM_OPENCLAW_SESSION" in directions
    assert correlation["ownershipProofStatus"] == (
        "UNSUPPORTED_BY_FIXED_VERSION_NATIVE_METADATA"
    )
    assert "SESSIONS_RESOLVE_ALONE_IS_INSUFFICIENT" in correlation["associationRules"]
    assert inheritance["generationReplacement"] == {
        "retains": "SAME_EXCLUSIVE_AGENT_AND_WORKSPACE_FILES",
        "doesNotRetain": "SESSION_ID_SESSION_ENTRY_ACTIVE_RUN_OR_TRANSCRIPT",
        "forbids": (
            "FORK_PARENT_TRANSCRIPT_OR_CROSS_INSTANCE_WORKSPACE_SESSION_BINDING"
        ),
    }
    assert "MEMORY.md_WHEN_PRESENT" in inheritance["workspaceRetained"]


def test_internal_mapping_schemas_are_closed_and_fully_typed() -> None:
    contract = _contract()
    identity = contract["identityCorrelationSchema"]
    lifecycle = contract["lifecycleSchema"]

    platform = identity["platformIdentity"]
    native = identity["nativeCorrelation"]
    request = lifecycle["request"]
    observation = lifecycle["observation"]

    assert set(platform["required"]) == set(platform["properties"])
    assert set(native["required"]) | set(native["optional"]) == set(
        native["properties"]
    )
    assert set(request["required"]) == set(request["properties"])
    assert set(observation["required"]) == set(observation["properties"])
    assert all(
        item["additionalProperties"] is False
        for item in (platform, native, request, observation)
    )
    assert native["properties"]["gatewayDigest"]["pattern"] == "^[0-9a-f]{64}$"
    assert native["properties"]["workspaceAttestationDigest"]["pattern"] == (
        "^[0-9a-f]{64}$"
    )


def test_fixed_target_and_live_generation_correlations_are_exact() -> None:
    contract = _contract()
    target = contract["target"]
    sessions = contract["liveEvidence"]["generationSessions"]

    assert target == {
        "package": f"openclaw@{EXACT_TARGET.version}",
        "tagCommit": EXACT_TARGET.tag_commit,
        "profile": "external-single-gateway-isolated-agent-workspace",
    }
    assert [item["generation"] for item in sessions] == [1, 2]
    assert len({item["sessionId"] for item in sessions}) == 2
    assert all(item["runStarted"] is False for item in sessions)
    assert all(item["messageCount"] == 0 for item in sessions)
    assert all(
        item["key"].startswith("agent:s5-v023-impl-314-conformance-a1:")
        for item in sessions
    )


def test_unknown_effects_are_observed_not_blindly_reissued() -> None:
    contract = _contract()
    now = datetime(2026, 9, 12, tzinfo=UTC)
    desired = _desired(now)

    assert set(reuse.value for reuse in AMBIGUOUS_COMMAND_RESULTS) == {
        "UNKNOWN",
        "STALE",
        "RECOVERY_REQUIRED",
    }
    assert all(not may_reissue_command(result) for result in AMBIGUOUS_COMMAND_RESULTS)
    assert may_reissue_command(CommandResult.REQUESTED)
    assert may_reissue_command(CommandResult.REJECTED)
    assert (
        classify_reconciliation(
            desired,
            _observation(now),
            at=now,
            effect_was_ambiguous=True,
        )
        is CommandResult.RECOVERY_REQUIRED
    )
    assert (
        contract["lifecycleSchema"]["recoveryRules"][
            "timeoutOrTransportFailureAfterWrite"
        ]
        == "OBSERVE_ONLY_THEN_RECOVERY_REQUIRED_IF_UNRESOLVED"
    )


def test_stop_requires_positive_termination_facts() -> None:
    contract = _contract()
    rules = contract["lifecycleSchema"]["recoveryRules"]

    assert rules["stop"] == ("REQUIRES_DISPATCH_BARRIER_AND_NONE_PROVEN_ACTIVE_WORK")
    assert rules["archiveOrDelete"] == "NEVER_STOP_EVIDENCE"
    assert "ACTIVE_RUN_CORRELATION" in contract["stateInheritance"]["sessionOnly"]


def test_fixed_version_metadata_is_mutable_correlation_not_attestation() -> None:
    contract = _contract()
    surfaces = contract["fixedVersionMetadataSurfaces"]

    assert surfaces["agent"]["arbitraryMetadata"] == (
        "REJECTED_ADDITIONAL_PROPERTIES_FALSE"
    )
    assert surfaces["session"]["arbitraryMetadata"] == (
        "REJECTED_ADDITIONAL_PROPERTIES_FALSE"
    )
    assert surfaces["agent"]["ownershipClaim"] == ("CORRELATION_ONLY_NOT_ATTESTATION")
    assert surfaces["session"]["ownershipClaim"] == ("CORRELATION_ONLY_NOT_ATTESTATION")
    assert surfaces["workspace"]["attestation"] == (
        "NO_RPC_EXPOSED_UNFORGEABLE_WORKSPACE_ATTESTATION"
    )


def test_production_transport_remains_read_only_and_lifecycle_fail_closed() -> None:
    contract = _contract()
    capabilities = {
        item["method"]: item for item in contract["fixedVersionCapabilities"]
    }
    rpc_source = inspect.getsource(OpenClawProductionTransport._rpc)

    assert capabilities["agents.list"]["productionTransport"] == ("READ_ONLY_SUPPORTED")
    assert capabilities["sessions.create"]["productionTransport"] == "UNSUPPORTED"
    assert capabilities["agents.create"]["requiredScope"] == "operator.admin"
    assert capabilities["sessions.create"]["requiredScope"] == "operator.write"
    assert capabilities["sessions.list"]["requiredScope"] == "operator.read"
    assert capabilities["sessions.abort"]["liveConformance"] == "NOT_RUN"
    assert capabilities["agents.delete"]["liveConformance"] == "NOT_RUN"
    assert capabilities["sessions.delete"]["liveConformance"] == "NOT_RUN"
    assert '"health"' in rpc_source
    assert '"status"' in rpc_source
    assert '"agents.list"' in rpc_source
    assert '"sessions.create"' not in rpc_source
    assert '"sessions.patch"' not in rpc_source


def test_unresolved_parameters_are_not_silently_frozen() -> None:
    proposed = _contract()["proposedParameters"]

    assert proposed["observationFreshnessSeconds"] == {
        "recommended": 30,
        "basis": "EXISTING_RUNTIME_MANAGER_AND_OPENCLAW_BOOTSTRAP_DEFAULT",
        "status": "PROPOSED_NOT_FROZEN",
    }
    assert proposed["rpcTimeoutSeconds"]["status"] == "PROPOSED_NOT_FROZEN"
    assert proposed["commandDeadlineSeconds"]["status"] == "PROPOSED_NOT_FROZEN"
    assert proposed["profileEligibilityLeaseSeconds"]["recommended"] is None
    assert proposed["clockSkewSeconds"]["recommended"] is None
