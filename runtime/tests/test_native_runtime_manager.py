from agent_runtime.providers.native import NativeRuntimeProvider
from agent_runtime.providers.native.models import (
    DiagnosticReason,
    NativeLifecycleObservation,
    NativeLifecycleState,
    SupportState,
)


class Driver:
    def __init__(self):
        self.values = {}
        self.sequence = 0

    def start(self, identity):
        return self._running(identity)

    def stop(self, identity):
        prior = self.values.get(identity)
        value = NativeLifecycleObservation(
            identity,
            NativeLifecycleState.TERMINATED,
            prior.native_correlation if prior else None,
            DiagnosticReason.LIFECYCLE_APPLIED,
        )
        self.values[identity] = value
        return value

    def replace(self, identity):
        return self._running(identity)

    def observe(self, identity):
        return self.values.get(identity)

    def _running(self, identity):
        self.sequence += 1
        value = NativeLifecycleObservation(
            identity,
            NativeLifecycleState.RUNNING,
            f"native-runtime-{self.sequence}",
            DiagnosticReason.LIFECYCLE_APPLIED,
        )
        self.values[identity] = value
        return value


def test_typed_start_stop_and_observe_preserve_platform_identity() -> None:
    provider = NativeRuntimeProvider(lifecycle_driver=Driver())
    started = provider.start_runtime("runtime-product-1")
    assert started.state is SupportState.SUPPORTED
    assert started.native_correlation != "runtime-product-1"
    assert (
        provider.observe_runtime("runtime-product-1").state
        is NativeLifecycleState.RUNNING
    )
    stopped = provider.stop_runtime("runtime-product-1")
    assert stopped.native_correlation == started.native_correlation
    assert (
        provider.observe_runtime("runtime-product-1").state
        is NativeLifecycleState.TERMINATED
    )


def test_replacement_changes_only_native_correlation() -> None:
    provider = NativeRuntimeProvider(lifecycle_driver=Driver())
    first = provider.start_runtime("runtime-product-1")
    replacement = provider.replace("runtime-product-1")
    observed = provider.observe_runtime("runtime-product-1")
    assert replacement.platform_execution_identity == "runtime-product-1"
    assert replacement.native_correlation != first.native_correlation
    assert observed.platform_runtime_identity == "runtime-product-1"
    assert observed.native_correlation == replacement.native_correlation


def test_default_provider_does_not_claim_substrate_effects() -> None:
    provider = NativeRuntimeProvider()
    assert (
        provider.start_runtime("runtime-product-1").state is SupportState.NOT_YET_PROVEN
    )
    assert provider.observe_runtime("runtime-product-1") is None
