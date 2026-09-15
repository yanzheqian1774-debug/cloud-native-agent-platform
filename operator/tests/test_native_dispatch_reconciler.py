from datetime import UTC, datetime, timedelta

import pytest
from agent_operator.errors import TaskExecutionError
from agent_operator.native_dispatch_reconciler import (
    KubernetesNativeTaskPort,
    NativeDispatchWorker,
)
from agent_operator.runtime_identity_translation import (
    AgentInstanceId,
    AppendDisposition,
    AssignmentId,
    AttemptId,
    CommandId,
    Generation,
    NativeDispatchClaim,
    NativeDispatchCommand,
    PlacementId,
    RuntimeInstanceId,
    ScopeIdentity,
)

NOW = datetime(2026, 9, 15, tzinfo=UTC)


def command() -> NativeDispatchCommand:
    return NativeDispatchCommand(
        CommandId("dispatch-1"),
        ScopeIdentity("tenant-a", "quality"),
        AttemptId("attempt-1"),
        AssignmentId("assignment-1"),
        "plan-revision-1",
        "a" * 64,
        PlacementId("placement-1"),
        "b" * 64,
        RuntimeInstanceId("runtime-1"),
        Generation(1),
        AgentInstanceId("agent-1"),
        "human:owner",
        "credential-1",
        "SERVICE_CREDENTIAL",
        Generation(1),
        Generation(1),
        "EXECUTION",
        "START",
        "governed-execution:attempt-1",
        "researcher-agent",
        "analyze",
        30,
        NOW,
    )


class Repository:
    def __init__(self, *, allowed=True):
        self.claim = NativeDispatchClaim(
            command(), Generation(1), "token", "worker", NOW + timedelta(minutes=1)
        )
        self.original_claim = self.claim
        self.allowed = allowed
        self.effect_started = False
        self.terminal = False
        self.uncertain = []

    def claim_next(self, worker_id, **kwargs):
        del worker_id, kwargs
        value, self.claim = self.claim, None
        return value

    def resume_effect_started(self, worker_id):
        del worker_id
        if self.effect_started and not self.terminal:
            return self.original_claim
        return None

    def permit_effect(self, claim, task_name, authorization_check, **kwargs):
        del task_name, kwargs
        if not self.allowed or not authorization_check(None, claim.command):
            raise ValueError("NATIVE_DISPATCH_EFFECT_NOT_AUTHORIZED")
        replayed = self.effect_started
        self.effect_started = True
        return AppendDisposition.REPLAYED if replayed else AppendDisposition.APPENDED

    def record_kubernetes_correlation(self, claim, task_name, task_uid):
        del claim, task_name, task_uid
        return AppendDisposition.APPENDED

    def record_uncertain(self, claim, observation):
        self.terminal = True
        self.uncertain.append((claim, observation))
        return AppendDisposition.APPENDED


class Kubernetes:
    def __init__(self):
        self.created = 0
        self.body = None

    def create(self, claim, task_name):
        del claim
        self.created += 1
        self.body = {
            "metadata": {"name": task_name, "uid": "task-uid-1"},
            "status": {},
        }
        return self.body

    def read(self, claim, task_name):
        del claim, task_name
        return self.body

    def patch_status(self, command, task_name, status):
        del command, task_name
        self.body["status"] = status


class Transport:
    def __init__(self, result="done", error=None):
        self.result = result
        self.error = error
        self.calls = 0

    def invoke(self, command):
        del command
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


def worker(
    repository, kubernetes, transport, completions, *, checkpoint=lambda _: None
):
    return NativeDispatchWorker(
        repository,
        kubernetes,
        transport,
        lambda _connection, _command: True,
        lambda claim, observation: completions.append((claim, observation)),
        worker_id="worker",
        checkpoint=checkpoint,
    )


def test_positive_transport_and_terminal_observation() -> None:
    repository = Repository()
    kubernetes = Kubernetes()
    transport = Transport()
    completions = []
    result = worker(repository, kubernetes, transport, completions).run_once()
    assert result.state == "SUCCEEDED"
    assert kubernetes.created == transport.calls == 1
    assert len(completions) == 1
    assert completions[0][1].kubernetes_task_uid == "task-uid-1"


def test_denial_has_zero_kubernetes_and_runtime_effect() -> None:
    repository = Repository(allowed=False)
    kubernetes = Kubernetes()
    transport = Transport()
    with pytest.raises(ValueError, match="NOT_AUTHORIZED"):
        worker(repository, kubernetes, transport, []).run_once()
    assert kubernetes.created == transport.calls == 0


def test_ambiguous_transport_is_unknown_and_not_redispatched() -> None:
    repository = Repository()
    kubernetes = Kubernetes()
    transport = Transport(
        error=TaskExecutionError(
            reason="ExecutionOutcomeUnknown", message="ambiguous", retryable=False
        )
    )
    value = worker(repository, kubernetes, transport, [])
    assert value.run_once().state == "UNKNOWN"
    assert value.run_once().state == "IDLE"
    assert transport.calls == 1
    assert len(repository.uncertain) == 1


def test_effect_started_replay_is_observe_first() -> None:
    repository = Repository()
    claim = repository.claim
    kubernetes = Kubernetes()
    transport = Transport()
    completions = []
    value = worker(repository, kubernetes, transport, completions)
    value.run_claim(claim)
    assert value.run_claim(claim).state == "SUCCEEDED"
    assert transport.calls == 1
    assert kubernetes.created == 1


def test_crash_after_effect_started_never_creates_on_recovery() -> None:
    repository = Repository()
    claim = repository.claim
    kubernetes = Kubernetes()
    transport = Transport()

    def crash(name):
        if name == "effect_started":
            raise RuntimeError("crash")

    with pytest.raises(RuntimeError, match="crash"):
        worker(repository, kubernetes, transport, [], checkpoint=crash).run_claim(claim)
    assert worker(repository, kubernetes, transport, []).run_claim(claim).state == (
        "RECOVERY_REQUIRED"
    )
    assert kubernetes.created == transport.calls == 0


def test_task_correlation_covers_identity_generation_and_fencing() -> None:
    claim = Repository().original_claim
    body = {
        "metadata": {
            "labels": KubernetesNativeTaskPort._labels(claim.command),
            "annotations": {
                **KubernetesNativeTaskPort._annotations(claim),
                "injected.example/annotation": "allowed",
            },
        }
    }
    assert KubernetesNativeTaskPort._matches(claim, body)
    body["metadata"]["annotations"]["agentos.io/claim-generation"] = "2"
    assert not KubernetesNativeTaskPort._matches(claim, body)
