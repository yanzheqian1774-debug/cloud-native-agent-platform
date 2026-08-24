"""Canonical internal fixture serialization for prototype v0.2."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .domain import (
    AgentDefinitionRef,
    AgentInstance,
    AgentInstanceId,
    AgentInstanceLifecycle,
    DesiredRuntimeBinding,
    EffectiveRuntimeBinding,
    ExecutionIdentityRecord,
    NativeCorrelationId,
    NativeRealizationEvidence,
    PlatformExecutionIdentity,
    RuntimeBinding,
)
from .errors import InvalidDomainValueError

SCHEMA_VERSION = "core.agentos.io/prototype-v0.2"


def _binding_to_dict(binding: RuntimeBinding) -> dict[str, Any]:
    return {
        "bindingId": binding.binding_id,
        "providerRef": binding.provider_ref,
        "mode": binding.mode,
        "packageRef": binding.package_ref,
        "configuration": dict(binding.configuration),
    }


def _binding_from_dict(value: object) -> RuntimeBinding:
    if not isinstance(value, dict) or set(value) != {
        "bindingId",
        "providerRef",
        "mode",
        "packageRef",
        "configuration",
    }:
        raise InvalidDomainValueError("invalid Runtime Binding fixture shape")
    return RuntimeBinding(
        binding_id=value["bindingId"],
        provider_ref=value["providerRef"],
        mode=value["mode"],
        package_ref=value["packageRef"],
        configuration=value["configuration"],
    )


def agent_instance_to_dict(instance: AgentInstance) -> dict[str, Any]:
    effective = instance.effective_runtime_binding
    return {
        "schemaVersion": SCHEMA_VERSION,
        "instance": {
            "instanceId": instance.instance_id.value,
            "definitionRef": {
                "kind": "AgentDefinition",
                "namespace": instance.definition_ref.namespace,
                "name": instance.definition_ref.name,
            },
            "lifecycle": instance.lifecycle.value,
            "desiredRuntimeBinding": _binding_to_dict(
                instance.desired_runtime_binding.value
            ),
            "effectiveRuntimeBinding": None
            if effective is None
            else {
                "binding": _binding_to_dict(effective.value),
                "resolvedAt": effective.resolved_at.isoformat(),
            },
            "realizations": [
                {
                    "system": item.system,
                    "kind": item.kind,
                    "id": item.correlation_id.value,
                    "observedAt": item.observed_at.isoformat(),
                    "active": item.active,
                }
                for item in instance.realizations
            ],
            "createdAt": instance.created_at.isoformat(),
            "updatedAt": instance.updated_at.isoformat(),
        },
    }


def agent_instance_from_dict(payload: object) -> AgentInstance:
    if not isinstance(payload, dict) or set(payload) != {"schemaVersion", "instance"}:
        raise InvalidDomainValueError("invalid Agent Instance fixture envelope")
    if payload["schemaVersion"] != SCHEMA_VERSION:
        raise InvalidDomainValueError("unsupported internal fixture schema version")
    value = payload["instance"]
    required = {
        "instanceId",
        "definitionRef",
        "lifecycle",
        "desiredRuntimeBinding",
        "effectiveRuntimeBinding",
        "realizations",
        "createdAt",
        "updatedAt",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise InvalidDomainValueError("invalid Agent Instance fixture shape")
    ref = value["definitionRef"]
    if not isinstance(ref, dict) or set(ref) != {"kind", "namespace", "name"}:
        raise InvalidDomainValueError("invalid Definition reference fixture shape")
    if ref["kind"] != "AgentDefinition":
        raise InvalidDomainValueError(
            "Definition reference kind must be AgentDefinition"
        )
    effective_value = value["effectiveRuntimeBinding"]
    effective = None
    if effective_value is not None:
        if not isinstance(effective_value, dict) or set(effective_value) != {
            "binding",
            "resolvedAt",
        }:
            raise InvalidDomainValueError("invalid effective Runtime Binding fixture")
        effective = EffectiveRuntimeBinding(
            _binding_from_dict(effective_value["binding"]),
            datetime.fromisoformat(effective_value["resolvedAt"]),
        )
    realizations = value["realizations"]
    if not isinstance(realizations, list):
        raise InvalidDomainValueError("realizations must be a list")
    return AgentInstance(
        instance_id=AgentInstanceId(value["instanceId"]),
        definition_ref=AgentDefinitionRef(ref["namespace"], ref["name"]),
        lifecycle=AgentInstanceLifecycle(value["lifecycle"]),
        desired_runtime_binding=DesiredRuntimeBinding(
            _binding_from_dict(value["desiredRuntimeBinding"])
        ),
        effective_runtime_binding=effective,
        realizations=tuple(
            NativeRealizationEvidence(
                system=item["system"],
                kind=item["kind"],
                correlation_id=NativeCorrelationId(item["id"]),
                observed_at=datetime.fromisoformat(item["observedAt"]),
                active=item["active"],
            )
            for item in realizations
        ),
        created_at=datetime.fromisoformat(value["createdAt"]),
        updated_at=datetime.fromisoformat(value["updatedAt"]),
    )


def execution_identity_to_dict(record: ExecutionIdentityRecord) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "executionIdentity": {
            "executionId": record.execution_id.value,
            "rootExecutionId": record.root_execution_id.value,
            "parentExecutionId": None
            if record.parent_execution_id is None
            else record.parent_execution_id.value,
            "attempt": record.attempt,
            "nativeCorrelations": [item.value for item in record.native_correlations],
            "createdAt": record.created_at.isoformat(),
        },
    }


def execution_identity_from_dict(payload: object) -> ExecutionIdentityRecord:
    if not isinstance(payload, dict) or set(payload) != {
        "schemaVersion",
        "executionIdentity",
    }:
        raise InvalidDomainValueError("invalid execution identity fixture envelope")
    if payload["schemaVersion"] != SCHEMA_VERSION:
        raise InvalidDomainValueError("unsupported internal fixture schema version")
    value = payload["executionIdentity"]
    required = {
        "executionId",
        "rootExecutionId",
        "parentExecutionId",
        "attempt",
        "nativeCorrelations",
        "createdAt",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise InvalidDomainValueError("invalid execution identity fixture shape")
    correlations = value["nativeCorrelations"]
    if not isinstance(correlations, list):
        raise InvalidDomainValueError("native correlations must be a list")
    parent = value["parentExecutionId"]
    return ExecutionIdentityRecord(
        execution_id=PlatformExecutionIdentity(value["executionId"]),
        root_execution_id=PlatformExecutionIdentity(value["rootExecutionId"]),
        parent_execution_id=None
        if parent is None
        else PlatformExecutionIdentity(parent),
        attempt=value["attempt"],
        native_correlations=tuple(NativeCorrelationId(item) for item in correlations),
        created_at=datetime.fromisoformat(value["createdAt"]),
    )
