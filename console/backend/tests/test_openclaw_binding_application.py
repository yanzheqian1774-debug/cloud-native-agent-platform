import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from agent_console.governed_execution_authorization import (
    GovernedAuthorizationError,
    GovernedExecutionAuthority,
)
from agent_console.openclaw_binding_application import (
    OpenClawBindingApplicationError,
    OpenClawBindingApplicationService,
    RecordOpenClawBinding,
    observation_resource,
)
from agent_core.execution_contract import (
    CommandId,
    Generation,
    PlacementDecision,
    PlacementDecisionKind,
    PlacementId,
    PlacementRequestId,
    RuntimeDesiredState,
    RuntimeDesiredStateKind,
    RuntimeInstanceId,
    ScopeIdentity,
)
from agent_core.openclaw_binding import (
    AssociationStatus,
    OpenClawBindingObservation,
)


def command():
    now = datetime(2026, 9, 12, tzinfo=UTC)
    scope = ScopeIdentity("tenant-a", "restricted")
    runtime_id = RuntimeInstanceId("runtime-1")
    placement_id = PlacementId("placement-1")
    desired = RuntimeDesiredState(
        runtime_id,
        Generation(1),
        RuntimeDesiredStateKind.OBSERVE,
        CommandId("command-1"),
        "operator",
        now,
        now + timedelta(seconds=30),
        "READ_ONLY_RECOVERY",
    )
    return RecordOpenClawBinding(
        scope,
        runtime_id,
        Generation(1),
        placement_id,
        desired,
        "idempotency-1",
        "a" * 64,
        "agent-1",
        "/srv/openclaw/runtime-1",
        "gateway-host-1",
        "persistent-volume-1",
        "agent:agent-1:runtime-1-g1",
        "session-1",
    )


def authority(value, *, grant=True):
    resource = observation_resource(
        value.scope, value.runtime_instance_id, value.generation, value.placement_id
    )
    configuration = {
        "schemaVersion": "governed-execution-auth.v1",
        "policyVersion": "policy.v1",
        "auditSource": "test",
        "credentials": [
            {
                "credentialId": "credential-1",
                "principalId": "operator-1",
                "tenantId": value.scope.namespace,
                "securityDomain": value.scope.security_domain,
                "credentialSha256": hashlib.sha256(b"secret").hexdigest(),
                "expiresAt": "2100-01-01T00:00:00Z",
                "grants": [
                    {
                        "owner": "EXECUTION",
                        "action": "OBSERVE",
                        "resource": resource,
                    }
                ]
                if grant
                else [],
            }
        ],
    }
    result = GovernedExecutionAuthority(configuration)
    return result, result.authenticate("Bearer secret")


class Repository:
    def __init__(self, value):
        self.command = value.desired_command
        self.placement = PlacementDecision.create(
            placement_id=value.placement_id,
            request_id=PlacementRequestId("request-1"),
            decision=PlacementDecisionKind.PLACED,
            runtime_instance_id=value.runtime_instance_id,
            policy_version="v1",
            compatibility_facts=(),
            limitation_codes=(),
            decided_at=datetime(2026, 9, 12, tzinfo=UTC),
        )
        self.binding = None
        self.observations = []

    def get(self, scope, placement_id):
        return self.placement

    def get_command(self, scope, command_id):
        return self.command

    def save_openclaw_binding(self, binding, generation):
        self.binding = (binding, generation)

    def get_openclaw_binding(self, scope, runtime_instance_id, generation):
        return self.binding

    def append_openclaw_observation(self, observation):
        self.observations.append(observation)

    def read_openclaw_observations(self, scope, runtime_instance_id, generation):
        return tuple(self.observations)


class Observer:
    def __init__(self):
        self.calls = 0

    def observe(self, binding, generation, *, high_water, at=None):
        self.calls += 1
        now = at or datetime.now(UTC)
        return OpenClawBindingObservation(
            binding.scope,
            binding.runtime_instance_id,
            generation.generation,
            high_water,
            AssociationStatus.MATCHED,
            now,
            now + timedelta(seconds=30),
            binding.source_version,
            "OPENCLAW_COMPOSITE_ASSOCIATION_MATCHED",
            True,
            True,
            True,
            True,
        )


def test_record_and_replay_require_current_exact_authorization_and_placement():
    value = command()
    auth, principal = authority(value)
    repository = Repository(value)
    observer = Observer()
    service = OpenClawBindingApplicationService(repository, auth, observer)

    first = service.record(value, principal=principal)
    replay = service.record(value, principal=principal)

    assert replay == first
    assert first[1].association_status is AssociationStatus.UNVERIFIED
    assert first[0].authorization_decision_id.startswith("governed-authorization:")

    observation = service.observe(
        value.scope,
        value.runtime_instance_id,
        value.generation,
        principal=principal,
        at=datetime(2026, 9, 12, tzinfo=UTC),
    )
    assert observation.association_status is AssociationStatus.MATCHED
    assert observer.calls == 1


def test_reference_presence_without_grant_or_command_never_observes():
    value = command()
    denied, principal = authority(value, grant=False)
    repository = Repository(value)
    observer = Observer()
    service = OpenClawBindingApplicationService(repository, denied, observer)

    with pytest.raises(GovernedAuthorizationError):
        service.record(value, principal=principal)
    assert repository.binding is None

    allowed, principal = authority(value)
    repository.command = None
    service = OpenClawBindingApplicationService(repository, allowed, observer)
    with pytest.raises(
        OpenClawBindingApplicationError, match="OPENCLAW_COMMAND_NOT_VALID"
    ):
        service.record(value, principal=principal)
    assert observer.calls == 0


def test_wrong_scope_placement_and_operation_fail_before_observer():
    value = command()
    auth, principal = authority(value)
    repository = Repository(value)
    observer = Observer()
    service = OpenClawBindingApplicationService(repository, auth, observer)

    with pytest.raises(
        OpenClawBindingApplicationError, match="OPENCLAW_COMMAND_NOT_VALID"
    ):
        service.record(
            replace(
                value,
                desired_command=replace(
                    value.desired_command,
                    desired_state=RuntimeDesiredStateKind.RUNNING,
                ),
            ),
            principal=principal,
        )

    repository.placement = replace(
        repository.placement, runtime_instance_id=RuntimeInstanceId("other")
    )
    with pytest.raises(
        OpenClawBindingApplicationError, match="OPENCLAW_PLACEMENT_NOT_VALID"
    ):
        service.record(value, principal=principal)
    assert observer.calls == 0
