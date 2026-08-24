"""Bounded, replaceable interpretation of current Agent and Task evidence.

The interpreter is deliberately Kubernetes-shape aware but performs no I/O and
writes no public resource fields. Kubernetes UIDs provide immutable evidence
for deterministic internal identities; names retain their current
Definition-facing meaning.
"""

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from agent_core.interface_spine.v0_2 import (
    DefinitionFacingRequest,
    ExecutionEnvelopeBuilder,
    InternalExecutionEnvelope,
    RejectAmbiguousInstanceSelector,
)
from agent_core.repositories import InMemoryAgentInstanceRepository
from agent_core.representation.v0_2 import (
    AgentDefinitionRef,
    AgentInstance,
    AgentInstanceId,
    AgentInstanceLifecycle,
    DesiredRuntimeBinding,
    EffectiveRuntimeBinding,
    PlatformExecutionIdentity,
    RuntimeBinding,
)


class CompatibilityInterpreterError(ValueError):
    """Typed fail-closed compatibility failure with a stable status reason."""

    reason = "CompatibilityInterpretationFailed"


class MissingDefinitionError(CompatibilityInterpreterError):
    reason = "AgentDefinitionNotFound"


class ConflictingIdentityEvidenceError(CompatibilityInterpreterError):
    reason = "ConflictingIdentityEvidence"


class InvalidLegacyEvidenceError(CompatibilityInterpreterError):
    reason = "InvalidLegacyIdentityEvidence"


def _required_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidLegacyEvidenceError(f"{field_name} must be a non-empty string")
    return value


def _mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise InvalidLegacyEvidenceError(f"{field_name} must be an object")
    return value


def _timestamp(value: object, field_name: str) -> datetime:
    raw = _required_string(value, field_name)
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidLegacyEvidenceError(
            f"{field_name} must be an RFC 3339 timestamp"
        ) from exc


def _opaque_id(kind: str, uid: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"agentos.io/v0.2/{kind}/{uid}"))


def _runtime_binding(
    *, namespace: str, agent_name: str, agent_uid: str, spec: Mapping[str, Any]
) -> RuntimeBinding:
    runtime = _mapping(spec.get("runtime"), "Agent.spec.runtime")
    runtime_type = _required_string(runtime.get("type"), "Agent.spec.runtime.type")
    image = runtime.get("image")
    if image is not None:
        image = _required_string(image, "Agent.spec.runtime.image")
    return RuntimeBinding(
        binding_id=f"legacy-agent:{namespace}:{agent_uid}",
        provider_ref="agentos.io/current-agent-service",
        mode=runtime_type,
        package_ref=image,
        configuration={"serviceName": agent_name},
    )


def _legacy_instance(
    *, namespace: str, agent_name: str, body: Mapping[str, Any]
) -> AgentInstance:
    metadata = _mapping(body.get("metadata"), "Agent.metadata")
    actual_namespace = _required_string(
        metadata.get("namespace"), "Agent.metadata.namespace"
    )
    actual_name = _required_string(metadata.get("name"), "Agent.metadata.name")
    if actual_namespace != namespace or actual_name != agent_name:
        raise ConflictingIdentityEvidenceError(
            "Agent evidence does not match the Task's namespaced Definition reference"
        )
    if metadata.get("deletionTimestamp") is not None:
        raise InvalidLegacyEvidenceError("terminating Agent cannot be selected")
    agent_uid = _required_string(metadata.get("uid"), "Agent.metadata.uid")
    created_at = _timestamp(
        metadata.get("creationTimestamp"), "Agent.metadata.creationTimestamp"
    )
    binding = _runtime_binding(
        namespace=namespace,
        agent_name=agent_name,
        agent_uid=agent_uid,
        spec=_mapping(body.get("spec"), "Agent.spec"),
    )
    return AgentInstance(
        instance_id=AgentInstanceId(_opaque_id("legacy-agent-instance", agent_uid)),
        definition_ref=AgentDefinitionRef(namespace, agent_name),
        lifecycle=AgentInstanceLifecycle.ACTIVE,
        desired_runtime_binding=DesiredRuntimeBinding(binding),
        effective_runtime_binding=EffectiveRuntimeBinding(
            binding, resolved_at=created_at
        ),
        created_at=created_at,
        updated_at=created_at,
    )


def interpret_legacy_task(
    *,
    task_spec: Mapping[str, Any],
    task_metadata: Mapping[str, Any],
    namespace: str,
    agent_candidates: Sequence[Mapping[str, Any]],
) -> InternalExecutionEnvelope:
    """Build or recover one deterministic internal context for a current Task.

    A Kubernetes Task UID is the logical-execution boundary. Reinterpreting the
    same UID recovers the same Platform Execution Identity; delete/recreate
    produces a new UID and therefore a new identity.
    """
    task_uid = _required_string(task_metadata.get("uid"), "Task.metadata.uid")
    task_name = _required_string(task_metadata.get("name"), "Task.metadata.name")
    metadata_namespace = _required_string(
        task_metadata.get("namespace"), "Task.metadata.namespace"
    )
    if metadata_namespace != namespace:
        raise ConflictingIdentityEvidenceError(
            "Task namespace conflicts with handler namespace"
        )
    conflicting_fields = {
        "agentInstanceRef",
        "executionId",
        "executionIdentity",
        "instanceRef",
        "nativeId",
        "runtimeId",
    }.intersection(task_spec)
    if conflicting_fields:
        fields = ", ".join(sorted(conflicting_fields))
        raise ConflictingIdentityEvidenceError(
            f"unsupported mixed identity evidence: {fields}"
        )
    agent_ref = _mapping(task_spec.get("agentRef"), "Task.spec.agentRef")
    unexpected_ref_fields = set(agent_ref).difference({"name"})
    if unexpected_ref_fields:
        fields = ", ".join(sorted(unexpected_ref_fields))
        raise ConflictingIdentityEvidenceError(
            f"unsupported Agent reference evidence: {fields}"
        )
    agent_name = _required_string(agent_ref.get("name"), "Task.spec.agentRef.name")
    if not agent_candidates:
        raise MissingDefinitionError(f"Agent {namespace}/{agent_name} does not exist")
    if len(agent_candidates) > 1:
        raise ConflictingIdentityEvidenceError(
            "multiple Agent objects match one namespaced Definition reference"
        )

    repository = InMemoryAgentInstanceRepository()
    for candidate in agent_candidates:
        repository.save(
            _legacy_instance(
                namespace=namespace,
                agent_name=agent_name,
                body=candidate,
            )
        )
    instances = repository.list_by_definition(AgentDefinitionRef(namespace, agent_name))
    if len(instances) != 1:
        raise ConflictingIdentityEvidenceError(
            "legacy Agent evidence must resolve to exactly one internal Instance"
        )
    desired_binding = instances[0].desired_runtime_binding
    request = DefinitionFacingRequest(
        namespace=namespace,
        agent_name=agent_name,
        desired_runtime_binding=desired_binding,
        source_task_name=task_name,
    )
    builder = ExecutionEnvelopeBuilder(
        selector=RejectAmbiguousInstanceSelector(repository),
        identity_minter=lambda: PlatformExecutionIdentity(
            _opaque_id("task-execution", task_uid)
        ),
    )
    return builder.build(request)
