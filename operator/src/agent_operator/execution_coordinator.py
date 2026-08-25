"""Bounded, controller-independent Task execution coordination for v0.2 MVS."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Any, Protocol

from agent_core.interface_spine.v0_2 import InternalExecutionEnvelope
from agent_gateway.capability import (
    AuthorizationContext,
    AuthorizationDecision,
    AuthorizationResult,
    CapabilityGateway,
    CapabilityIdentity,
    CapabilityOutcome,
    CapabilityRequest,
    CapabilityStatus,
    DecisionReason,
    ProviderIdentity,
    ProviderNativeRequestId,
    ProviderRequest,
    ProviderResponse,
    RestProvider,
    RestProviderConfiguration,
)
from agent_runtime.providers.native import NativeRuntimeProvider
from agent_runtime.providers.native.compatibility import (
    PROVIDER_PACKAGE,
    RUNTIME_TARGET,
)
from agent_runtime.providers.native.models import (
    CompatibilityRequest,
    DesiredRuntimeBinding,
    ExecutionEvidence,
    ExecutionState,
    ProviderExecutionRequest,
    RuntimeTargetIdentity,
)


class NativeExecutionPort(Protocol):
    """Existing Native Provider invocation boundary consumed by the coordinator."""

    def invoke(self, request: ProviderExecutionRequest) -> ExecutionEvidence: ...


class CapabilityExecutionPort(Protocol):
    """Existing authorization-first Capability Gateway boundary."""

    def execute(
        self,
        request: CapabilityRequest,
        context: AuthorizationContext,
    ) -> CapabilityOutcome: ...


class ExecutionClassification(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    DENIED = "DENIED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class CapabilityPlan:
    capability: CapabilityIdentity
    operation: str
    arguments: Mapping[str, Any]
    authorization: AuthorizationContext


@dataclass(frozen=True, slots=True)
class TaskExecutionContext:
    """Explicit immutable inputs required by one logical Task execution."""

    envelope: InternalExecutionEnvelope
    runtime_configuration: Mapping[str, str]
    capability_plan: CapabilityPlan | None = None


@dataclass(frozen=True, slots=True)
class InternalExecutionOutcome:
    """Unfrozen, non-public evidence normalized for the current Task adapter."""

    classification: ExecutionClassification
    platform_execution_identity: str
    requested_runtime: str
    effective_runtime: str | None
    runtime: ExecutionEvidence
    capability: CapabilityOutcome | None
    result: str | None
    diagnostic: str
    retry_safe: bool


class TaskExecutionCoordinator:
    """Sequence Native and optional Capability effects outside Kopf handlers."""

    def __init__(
        self,
        *,
        native_provider: NativeExecutionPort,
        capability_gateway: CapabilityExecutionPort | None = None,
    ) -> None:
        self._native_provider = native_provider
        self._capability_gateway = capability_gateway

    def execute(
        self,
        *,
        context: TaskExecutionContext,
        input_text: str,
    ) -> InternalExecutionOutcome:
        identity = context.envelope.execution_identity.value
        desired_mode = context.envelope.desired_runtime_binding.value.mode
        effective_mode = context.envelope.effective_runtime_binding.value.mode
        requested_target = (
            RUNTIME_TARGET
            if desired_mode == effective_mode == RUNTIME_TARGET.name
            else RuntimeTargetIdentity(
                name=desired_mode,
                exact_version=None,
                profile="unsupported",
            )
        )
        native_request = ProviderExecutionRequest(
            platform_execution_identity=identity,
            input=input_text,
            compatibility=CompatibilityRequest(
                provider_package=PROVIDER_PACKAGE,
                runtime_target=requested_target,
                core_version="0.1.0",
                platform_execution_identity=identity,
            ),
            desired_binding=DesiredRuntimeBinding(
                runtime_target=requested_target,
                configuration=context.runtime_configuration,
            ),
        )
        runtime = self._native_provider.invoke(native_request)
        requested_runtime = runtime.compatibility.requested_runtime.target
        effective = runtime.compatibility.effective_runtime
        effective_runtime = effective.target if effective is not None else None

        if runtime.state is not ExecutionState.SUCCEEDED:
            classification = (
                ExecutionClassification.UNKNOWN
                if runtime.state is ExecutionState.UNKNOWN
                else ExecutionClassification.FAILED
            )
            return InternalExecutionOutcome(
                classification=classification,
                platform_execution_identity=identity,
                requested_runtime=requested_runtime,
                effective_runtime=effective_runtime,
                runtime=runtime,
                capability=None,
                result=None,
                diagnostic=runtime.reason.value,
                retry_safe=False,
            )

        capability = self._execute_capability(context)
        if capability is None:
            return InternalExecutionOutcome(
                classification=ExecutionClassification.SUCCEEDED,
                platform_execution_identity=identity,
                requested_runtime=requested_runtime,
                effective_runtime=effective_runtime,
                runtime=runtime,
                capability=None,
                result=runtime.output,
                diagnostic="TASK_RUNTIME_SUCCEEDED",
                retry_safe=False,
            )

        if capability.status is CapabilityStatus.SUCCEEDED:
            classification = ExecutionClassification.SUCCEEDED
            result = runtime.output
        elif capability.status is CapabilityStatus.DENIED:
            classification = ExecutionClassification.DENIED
            result = None
        elif capability.status is CapabilityStatus.INDETERMINATE:
            classification = ExecutionClassification.UNKNOWN
            result = None
        else:
            classification = ExecutionClassification.FAILED
            result = None
        return InternalExecutionOutcome(
            classification=classification,
            platform_execution_identity=identity,
            requested_runtime=requested_runtime,
            effective_runtime=effective_runtime,
            runtime=runtime,
            capability=capability,
            result=result,
            diagnostic=capability.diagnostic,
            retry_safe=capability.retry_safe,
        )

    def _execute_capability(
        self, context: TaskExecutionContext
    ) -> CapabilityOutcome | None:
        plan = context.capability_plan
        if plan is None:
            return None
        if self._capability_gateway is None:
            raise ValueError("Capability requested without a configured gateway")
        identity = context.envelope.execution_identity
        if plan.authorization.execution_identity != identity:
            raise ValueError("Capability authorization identity mismatch")
        return self._capability_gateway.execute(
            CapabilityRequest(
                capability=plan.capability,
                operation=plan.operation,
                execution_identity=identity,
                arguments=plan.arguments,
            ),
            plan.authorization,
        )


class DeclaredCapabilityAuthorization:
    """Bounded MVS authorizer: only the selected declared capability may run."""

    def __init__(self, allowed: CapabilityIdentity) -> None:
        self._allowed = allowed

    def decide(
        self,
        request: CapabilityRequest,
        context: AuthorizationContext,
    ) -> AuthorizationResult:
        decision = (
            AuthorizationDecision.ALLOW
            if request.capability == self._allowed
            and request.execution_identity == context.execution_identity
            else AuthorizationDecision.DENY
        )
        return AuthorizationResult(
            decisions=(decision,),
            reason=DecisionReason("DECLARED_CAPABILITY"),
        )


class DeterministicSyntheticTransport:
    """Injected, network-free REST fixture used by the v0.2 MVS path."""

    def send(self, request: ProviderRequest) -> ProviderResponse:
        correlation = sha256(
            f"{request.execution_identity.value}\0{request.method}\0{request.target}".encode()
        ).hexdigest()[:24]
        return ProviderResponse(
            status_code=200,
            body={"accepted": True},
            native_request_id=ProviderNativeRequestId(
                f"synthetic-capability-{correlation}"
            ),
        )


def build_runtime_configuration(
    *, definition_evidence: Mapping[str, Any], namespace: str, agent_name: str
) -> dict[str, str]:
    """Translate existing Agent fields into the exact deterministic Native profile."""
    spec = definition_evidence.get("spec", {})
    model = spec.get("model", {}) if isinstance(spec, Mapping) else {}
    identity = spec.get("identity", {}) if isinstance(spec, Mapping) else {}
    configuration = {
        "AGENT_NAME": agent_name,
        "AGENT_NAMESPACE": namespace,
        "MODEL_PROVIDER": str(model.get("provider", "mock")),
        "MODEL_NAME": str(model.get("name", "mock-model")),
    }
    if isinstance(identity, Mapping):
        if isinstance(identity.get("displayName"), str):
            configuration["AGENT_DISPLAY_NAME"] = identity["displayName"]
        if isinstance(identity.get("role"), str):
            configuration["AGENT_ROLE"] = identity["role"]
    return configuration


def build_capability_plan(
    *,
    definition_evidence: Mapping[str, Any],
    envelope: InternalExecutionEnvelope,
    input_text: str,
) -> CapabilityPlan | None:
    """Select one declared capability without changing the public wire shape."""
    spec = definition_evidence.get("spec", {})
    capabilities = spec.get("capabilities", ()) if isinstance(spec, Mapping) else ()
    if not isinstance(capabilities, Sequence) or isinstance(capabilities, str):
        raise ValueError("Agent capability evidence must be a sequence")
    if not capabilities:
        return None
    selected = capabilities[0]
    if not isinstance(selected, str) or not selected.strip():
        raise ValueError("Agent capability evidence must contain non-empty names")
    identity = envelope.execution_identity
    return CapabilityPlan(
        capability=CapabilityIdentity(selected),
        operation="invoke",
        arguments={"input": input_text},
        authorization=AuthorizationContext(
            subject=envelope.definition_ref.name,
            tenant=envelope.definition_ref.namespace,
            execution_identity=identity,
        ),
    )


def build_default_coordinator(
    capability: CapabilityIdentity | None,
) -> TaskExecutionCoordinator:
    """Construct per-execution collaborators; no repository or service globals."""
    gateway = None
    if capability is not None:
        provider = RestProvider(
            RestProviderConfiguration(
                provider=ProviderIdentity("agentos.synthetic-rest"),
                target="https://synthetic.invalid/capabilities/invoke",
                allowed_hosts=("synthetic.invalid",),
                allowed_operations=("invoke",),
            ),
            DeterministicSyntheticTransport(),
        )
        gateway = CapabilityGateway(
            DeclaredCapabilityAuthorization(capability), provider
        )
    return TaskExecutionCoordinator(
        native_provider=NativeRuntimeProvider(), capability_gateway=gateway
    )
