"""Falsification tests for S5-SPIKE-004 Checkpoint C recovery."""

import sys
from pathlib import Path

EXPERIMENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT))

from generic_caller import GenericCaller, LogicalAgentRequest  # noqa: E402
from object_model import AgentInstance, DesiredLifecycle, RuntimeBinding  # noqa: E402
from recovery import (  # noqa: E402
    ConditionValue,
    ExperimentalInstanceReconciler,
    ExperimentalRecoveryProvider,
    RecoveryOutcome,
)
from routing import ExperimentalPlatformRouter  # noqa: E402


def build_recovery_route(
    *, infrastructure_observable: bool = True
) -> tuple[
    GenericCaller,
    ExperimentalPlatformRouter,
    ExperimentalRecoveryProvider,
    RuntimeBinding,
]:
    instance = AgentInstance(
        "researcher-a", "researcher", "v7", DesiredLifecycle.RUNNING, "binding-a"
    )
    binding = RuntimeBinding("binding-a", instance.instance_id, "recoverable")
    provider = ExperimentalRecoveryProvider(
        "recoverable", infrastructure_observable=infrastructure_observable
    )
    provider.realize(
        binding,
        realization_id="session-a-v1",
        native_kind="GatewaySession",
        native_id="gateway/session-a-v1",
    )
    router = ExperimentalPlatformRouter(
        instances=(instance,), bindings=(binding,), providers=(provider,)
    )
    return GenericCaller(router), router, provider, binding


def test_failure_is_observed_as_normalized_semantic_divergence() -> None:
    _, _, provider, binding = build_recovery_route()
    reconciler = ExperimentalInstanceReconciler()

    healthy = provider.observe(binding, evidence="native health ok")
    failed = provider.fail(binding, evidence="native session unavailable")

    assert healthy.instance_id == failed.instance_id == "researcher-a"
    assert healthy.realization_id == failed.realization_id == "session-a-v1"
    assert healthy.runtime_available is ConditionValue.TRUE
    assert failed.runtime_available is ConditionValue.FALSE
    assert failed.infrastructure_available is ConditionValue.TRUE
    assert reconciler.detect(failed)
    assert reconciler.divergences == [failed]


def test_replacement_requires_semantic_verification_to_be_recovered() -> None:
    caller, router, provider, binding = build_recovery_route()
    reconciler = ExperimentalInstanceReconciler()
    request = LogicalAgentRequest(
        "execution-stable", "researcher", "inspect", "researcher-a"
    )
    assert caller.invoke(request).execution_id == "execution-stable"
    failure = provider.fail(binding, evidence="native session unavailable")
    assert reconciler.detect(failure)

    replacement = provider.recover(
        binding,
        realization_id="session-a-v2",
        native_id="gateway/session-a-v2",
        semantically_ready=True,
    )
    result = reconciler.verify(
        caller=caller,
        request=request,
        provider=provider,
        binding=binding,
        old_realization_id="session-a-v1",
        new_realization_id=replacement.realization_id,
    )

    assert provider.native_actions == ["recreate:binding-a"]
    assert result.old_realization_id != result.new_realization_id
    assert result.instance_id == "researcher-a"
    assert result.execution_id == "execution-stable"
    assert result.semantic_route_verified
    assert result.outcome is RecoveryOutcome.RECOVERED
    assert router.dispatch_evidence[-1].execution_id == result.execution_id


def test_native_restart_success_does_not_imply_semantic_recovery() -> None:
    caller, _, provider, binding = build_recovery_route()
    reconciler = ExperimentalInstanceReconciler()
    provider.fail(binding, evidence="native session unavailable")

    replacement = provider.recover(
        binding,
        realization_id="session-a-v2",
        native_id="gateway/session-a-v2",
        semantically_ready=False,
    )
    result = reconciler.verify(
        caller=caller,
        request=LogicalAgentRequest(
            "execution-negative", "researcher", "inspect", "researcher-a"
        ),
        provider=provider,
        binding=binding,
        old_realization_id="session-a-v1",
        new_realization_id=replacement.realization_id,
    )

    assert result.native_restart_succeeded
    assert not result.semantic_route_verified
    assert result.outcome is RecoveryOutcome.NOT_RECOVERED


def test_unverifiable_runtime_truth_yields_recovery_unknown() -> None:
    caller, _, provider, binding = build_recovery_route(infrastructure_observable=False)
    reconciler = ExperimentalInstanceReconciler()
    provider.fail(binding, evidence="external target unavailable")
    replacement = provider.recover(
        binding,
        realization_id="session-a-v2",
        native_id="external/session-a-v2",
        semantically_ready=None,
    )

    observation = provider.observe(binding, evidence="external probe inconclusive")
    result = reconciler.verify(
        caller=caller,
        request=LogicalAgentRequest(
            "execution-unknown", "researcher", "inspect", "researcher-a"
        ),
        provider=provider,
        binding=binding,
        old_realization_id="session-a-v1",
        new_realization_id=replacement.realization_id,
    )

    assert observation.runtime_available is ConditionValue.UNKNOWN
    assert observation.infrastructure_available is ConditionValue.NOT_APPLICABLE
    assert result.outcome is RecoveryOutcome.RECOVERY_UNKNOWN
