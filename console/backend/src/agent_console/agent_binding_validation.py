"""Fail-closed validation ports for Agent Definition governed bindings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from agent_console.agent_definition_repository import DefinitionScope


@dataclass(frozen=True, slots=True)
class BindingResolution:
    resource_id: str
    revision_id: str
    digest: str
    published: bool
    enabled: bool
    deprecated: bool = False
    compatible: bool = True
    tools: tuple[str, ...] = ()
    snapshots: tuple[str, ...] = ()


class BindingResolver(Protocol):
    def resolve(
        self, scope: DefinitionScope, kind: str, resource_id: str
    ) -> BindingResolution | None: ...


class BindingValidationFailure(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _exact(reference: dict[str, Any], resolved: BindingResolution) -> None:
    if reference["revisionId"] != resolved.revision_id:
        raise BindingValidationFailure("BOUND_REVISION_NOT_CURRENT_PUBLISHED")
    if reference["digest"] != resolved.digest:
        raise BindingValidationFailure("BOUND_RESOURCE_DIGEST_MISMATCH")
    if not resolved.published:
        raise BindingValidationFailure("BOUND_RESOURCE_UNPUBLISHED")
    if not resolved.enabled:
        raise BindingValidationFailure("BOUND_RESOURCE_DISABLED")
    if resolved.deprecated:
        raise BindingValidationFailure("BOUND_RESOURCE_DEPRECATED")
    if not resolved.compatible:
        raise BindingValidationFailure("BOUND_RESOURCE_INCOMPATIBLE")


def validate_bindings(
    scope: DefinitionScope,
    bindings: dict[str, Any],
    resolver: BindingResolver | None,
) -> list[dict[str, str]]:
    """Validate every supplied exact reference; never infer latest or global scope."""
    verified: list[dict[str, str]] = []
    exact_groups = (
        ("skill", "skills"),
        ("mcp", "mcpTools"),
        ("knowledge", "knowledge"),
    )
    for kind, field in exact_groups:
        for reference in bindings.get(field, []):
            if resolver is None:
                raise BindingValidationFailure(f"{kind.upper()}_RESOLVER_UNAVAILABLE")
            resolved = resolver.resolve(scope, kind, reference["resourceId"])
            if resolved is None:
                raise BindingValidationFailure("BOUND_RESOURCE_NOT_FOUND")
            _exact(reference, resolved)
            if kind == "mcp" and reference["toolName"] not in resolved.tools:
                raise BindingValidationFailure("MCP_TOOL_NOT_GOVERNED")
            snapshot = reference.get("snapshotId")
            if snapshot and snapshot not in resolved.snapshots:
                raise BindingValidationFailure("BOUND_SNAPSHOT_NOT_FOUND")
            verified.append(
                {
                    "kind": kind,
                    "resourceId": resolved.resource_id,
                    "revisionId": resolved.revision_id,
                    "digest": resolved.digest,
                }
            )

    for kind, field in (
        ("workflow", "workflow"),
        ("runtime-profile", "runtimeProfile"),
    ):
        reference = bindings.get(field)
        if reference is None:
            continue
        if resolver is None:
            raise BindingValidationFailure(
                f"{kind.upper().replace('-', '_')}_RESOLVER_UNAVAILABLE"
            )
        resolved = resolver.resolve(scope, kind, reference["resourceId"])
        if (
            resolved is None
            or not reference.get("revisionId")
            or not reference.get("digest")
        ):
            raise BindingValidationFailure("SUPPLIED_REFERENCE_UNRESOLVED")
        _exact(reference, resolved)
        verified.append(
            {
                "kind": kind,
                "resourceId": resolved.resource_id,
                "revisionId": resolved.revision_id,
                "digest": resolved.digest,
            }
        )

    model = bindings.get("model")
    if model is not None:
        verified.append(
            {
                "kind": "model",
                "resourceId": model["resourceId"],
                "status": "UNVERIFIED_OPAQUE_REFERENCE",
            }
        )
    return verified
