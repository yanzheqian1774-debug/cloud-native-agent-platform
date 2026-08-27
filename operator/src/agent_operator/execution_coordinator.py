"""Bounded, controller-independent Task execution coordination for v0.2 MVS."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from typing import Any, Protocol

from agent_core.execution_evidence import (
    AuthorizationDecision as EvidenceAuthorizationDecision,
)
from agent_core.execution_evidence import (
    EvidenceEventType,
    EvidenceRepositoryError,
    ExecutionEvidenceRecord,
    ExecutionEvidenceRepository,
    OutcomeClassification,
    SQLiteExecutionEvidenceRepository,
)
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


class EvidenceAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class CapabilityPlan:
    capability: CapabilityIdentity
    operation: str
    arguments: Mapping[str, Any]
    authorization: AuthorizationContext

    def __post_init__(self) -> None:
        if not isinstance(self.arguments, Mapping):
            raise ValueError("Capability arguments must be a mapping")
        object.__setattr__(
            self,
            "arguments",
            MappingProxyType(deepcopy(dict(self.arguments))),
        )


@dataclass(frozen=True, slots=True)
class TaskExecutionContext:
    """Explicit immutable inputs required by one logical Task execution."""

    envelope: InternalExecutionEnvelope
    runtime_configuration: Mapping[str, str]
    capability_plan: CapabilityPlan | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.runtime_configuration, Mapping):
            raise ValueError("Runtime configuration must be a mapping")
        copied = deepcopy(dict(self.runtime_configuration))
        if not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in copied.items()
        ):
            raise ValueError("Runtime configuration must contain string pairs")
        object.__setattr__(
            self,
            "runtime_configuration",
            MappingProxyType(copied),
        )


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
    evidence_availability: EvidenceAvailability = EvidenceAvailability.UNAVAILABLE
    evidence_reason_code: str = "EVIDENCE_REPOSITORY_NOT_CONFIGURED"


class TaskExecutionCoordinator:
    """Sequence Native and optional Capability effects outside Kopf handlers."""

    def __init__(
        self,
        *,
        native_provider: NativeExecutionPort,
        capability_gateway: CapabilityExecutionPort | None = None,
        evidence_repository: ExecutionEvidenceRepository | None = None,
        security_domain: str = "default",
        clock: Callable[[], str] = lambda: (
            datetime.now(UTC).isoformat().replace("+00:00", "Z")
        ),
    ) -> None:
        self._native_provider = native_provider
        self._capability_gateway = capability_gateway
        self._evidence_repository = evidence_repository
        self._security_domain = security_domain
        self._clock = clock

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
            return self._with_evidence(
                context,
                InternalExecutionOutcome(
                    classification=classification,
                    platform_execution_identity=identity,
                    requested_runtime=requested_runtime,
                    effective_runtime=effective_runtime,
                    runtime=runtime,
                    capability=None,
                    result=None,
                    diagnostic=runtime.reason.value,
                    retry_safe=False,
                ),
            )

        capability = self._execute_capability(context)
        if capability is None:
            return self._with_evidence(
                context,
                InternalExecutionOutcome(
                    classification=ExecutionClassification.SUCCEEDED,
                    platform_execution_identity=identity,
                    requested_runtime=requested_runtime,
                    effective_runtime=effective_runtime,
                    runtime=runtime,
                    capability=None,
                    result=runtime.output,
                    diagnostic="TASK_RUNTIME_SUCCEEDED",
                    retry_safe=False,
                ),
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
        return self._with_evidence(
            context,
            InternalExecutionOutcome(
                classification=classification,
                platform_execution_identity=identity,
                requested_runtime=requested_runtime,
                effective_runtime=effective_runtime,
                runtime=runtime,
                capability=capability,
                result=result,
                diagnostic=capability.diagnostic,
                retry_safe=capability.retry_safe,
            ),
        )

    def _with_evidence(
        self,
        context: TaskExecutionContext,
        outcome: InternalExecutionOutcome,
    ) -> InternalExecutionOutcome:
        """Append normalized evidence without falsifying completed execution."""
        if self._evidence_repository is None:
            return outcome
        capability = outcome.capability
        if capability is None:
            authorization = EvidenceAuthorizationDecision.NOT_APPLICABLE
            capability_identity = None
            provider_calls = 0
            provider_correlation = outcome.runtime.correlation.native_invocation_id
        else:
            authorization = EvidenceAuthorizationDecision(
                capability.authorization.value
            )
            capability_identity = capability.capability.value
            provider_calls = capability.invocation.attempts
            provider_correlation = (
                capability.native_request_id.value
                if capability.native_request_id is not None
                else outcome.runtime.correlation.native_invocation_id
            )
        source_task = context.envelope.source_task_ref
        task_identity = source_task.name if source_task is not None else "task.unbound"
        record = ExecutionEvidenceRecord(
            evidence_record_id=(
                f"evidence.native.{outcome.platform_execution_identity}.1.1"
            ),
            namespace=context.envelope.definition_ref.namespace,
            security_domain=self._security_domain,
            platform_execution_identity=outcome.platform_execution_identity,
            workflow_identity="workflow.unbound",
            task_identity=task_identity,
            attempt_ordinal=1,
            event_ordinal=1,
            event_type=EvidenceEventType.EXECUTION_OUTCOME,
            occurred_at=self._clock(),
            runtime_classification="NATIVE",
            selected_instance_identity=context.envelope.selected_instance_id.value,
            capability_identity=capability_identity,
            authorization_decision=authorization,
            reason_code=outcome.diagnostic,
            provider_correlation_id=provider_correlation,
            provider_call_count=provider_calls,
            outcome_classification=OutcomeClassification(outcome.classification.value),
            limitation_code=(
                "WORKFLOW_IDENTITY_UNBOUND"
                if source_task is not None
                else "TASK_AND_WORKFLOW_IDENTITY_UNBOUND"
            ),
        )
        try:
            self._evidence_repository.append(record)
        except EvidenceRepositoryError as exc:
            return InternalExecutionOutcome(
                **{
                    field: getattr(outcome, field)
                    for field in (
                        "classification",
                        "platform_execution_identity",
                        "requested_runtime",
                        "effective_runtime",
                        "runtime",
                        "capability",
                        "result",
                        "diagnostic",
                        "retry_safe",
                    )
                },
                evidence_availability=EvidenceAvailability.UNAVAILABLE,
                evidence_reason_code=exc.reason_code,
            )
        return InternalExecutionOutcome(
            **{
                field: getattr(outcome, field)
                for field in (
                    "classification",
                    "platform_execution_identity",
                    "requested_runtime",
                    "effective_runtime",
                    "runtime",
                    "capability",
                    "result",
                    "diagnostic",
                    "retry_safe",
                )
            },
            evidence_availability=EvidenceAvailability.AVAILABLE,
            evidence_reason_code="EVIDENCE_RECORDED",
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
    if len(capabilities) != 1:
        raise ValueError("Agent capability evidence is ambiguous")
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
    database_location = os.environ.get("AGENT_EXECUTION_EVIDENCE_DB")
    evidence_repository = (
        SQLiteExecutionEvidenceRepository(Path(database_location))
        if database_location
        else None
    )
    security_domain = os.environ.get("AGENT_EXECUTION_SECURITY_DOMAIN", "default")
    return TaskExecutionCoordinator(
        native_provider=NativeRuntimeProvider(),
        capability_gateway=gateway,
        evidence_repository=evidence_repository,
        security_domain=security_domain,
    )
