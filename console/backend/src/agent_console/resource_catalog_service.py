"""Authorization-scoped unified projections over existing v0.2.2 resources."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class ProductAssemblyFailure(RuntimeError):
    def __init__(self, reason: str, status: int = 503) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status


@dataclass(frozen=True)
class ProductScope:
    namespace: str
    security_domain: str


ListResources = Callable[[ProductScope], list[dict[str, Any]]]


WORKBENCH_PATHS = {
    "AGENT": "/agents",
    "SKILL": "/skills",
    "MCP": "/mcp",
    "KNOWLEDGE": "/knowledge",
    "WORKFLOW": "/workflow-definitions",
    "RUNTIME_PROFILE": "/runtime-profiles",
}


class ResourceCatalogService:
    """Compose domain-owned reads without owning resource facts."""

    def __init__(self, readers: dict[str, ListResources]) -> None:
        self._readers = readers

    def list(
        self, scope: ProductScope, *, query: str = "", kind: str = "", status: str = ""
    ) -> list[dict[str, Any]]:
        resources: list[dict[str, Any]] = []
        for resource_kind, reader in self._readers.items():
            for raw in reader(scope):
                resources.append(self._project(resource_kind, raw))
        needle = query.casefold().strip()
        return [
            item
            for item in resources
            if (not kind or item["kind"] == kind.upper())
            and (not status or item["lifecycleStatus"] == status.upper())
            and (
                not needle
                or needle
                in " ".join(
                    (
                        item["identity"],
                        item["name"],
                        item["kind"],
                        *item["capabilities"],
                    )
                ).casefold()
            )
        ]

    def get(self, scope: ProductScope, kind: str, identity: str) -> dict[str, Any]:
        match = next(
            (
                item
                for item in self.list(scope, kind=kind)
                if item["identity"] == identity
            ),
            None,
        )
        if match is None:
            raise ProductAssemblyFailure("RESOURCE_NOT_FOUND", 404)
        return match

    @staticmethod
    def _project(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
        record = raw.get("definition") or raw.get("profile") or raw
        identity_key = {
            "AGENT": "definitionId",
            "SKILL": "resourceId",
            "MCP": "resourceId",
            "KNOWLEDGE": "knowledgeId",
            "WORKFLOW": "workflowDefinitionId",
            "RUNTIME_PROFILE": "runtimeProfileId",
        }[kind]
        published_id = record.get("publishedRevisionId")
        draft_id = record.get("currentDraftRevisionId")
        active_id = published_id or draft_id
        revisions = record.get("revisions", [])
        active = next(
            (item for item in revisions if item.get("revisionId") == active_id), None
        )
        lifecycle = str(
            record.get("lifecycleState") or (active or {}).get("state") or "DRAFT"
        )
        reviews = record.get("reviews", [])
        limitations = list(record.get("limitations", []))
        defaults = ["PREVIEW", "NOT_CERTIFIED", "NON_PRODUCTION_READY"]
        if kind == "MCP":
            defaults.extend(["EXPERIMENTAL", "LOCALHOST_ONLY_ACCEPTANCE_BOUNDARY"])
        if kind == "RUNTIME_PROFILE":
            defaults.extend(["DECLARATION_ONLY", "NO_EXECUTION_AUTHORITY"])
        relationships = ResourceCatalogService._relationships(kind, record, active)
        return {
            "kind": kind,
            "identity": record[identity_key],
            "name": record.get("name")
            or (active or {}).get("content", {}).get("title")
            or record[identity_key],
            "revisionId": (active or {}).get("revisionId"),
            "digest": (active or {}).get("digest"),
            "lifecycleStatus": lifecycle,
            "capabilityStatus": ResourceCatalogService._capability_status(
                record, lifecycle
            ),
            "owner": record.get("owner"),
            "compatibility": "COMPATIBLE"
            if record.get("compatible", True)
            else "INCOMPATIBLE",
            "limitations": list(dict.fromkeys([*limitations, *defaults])),
            "capabilities": ResourceCatalogService._capabilities(active),
            "relationships": relationships,
            "consumers": record.get("consumers", []),
            "reviewStatus": "APPROVED"
            if active
            and any(
                r.get("digest") == active.get("digest")
                and r.get("decision", "APPROVE") == "APPROVE"
                for r in reviews
            )
            else "REVIEW_REQUIRED",
            "deepLink": f"{WORKBENCH_PATHS[kind]}?resource={record[identity_key]}",
        }

    @staticmethod
    def _capability_status(record: dict[str, Any], lifecycle: str) -> str:
        if record.get("archived"):
            return "ARCHIVED"
        if lifecycle == "DEPRECATED":
            return "DEPRECATED"
        if record.get("enabled", True) is False:
            return "DISABLED"
        return "ENABLED" if lifecycle == "PUBLISHED" else "VALIDATION_REQUIRED"

    @staticmethod
    def _capabilities(active: dict[str, Any] | None) -> list[str]:
        content = (active or {}).get("content", {})
        values = [
            *content.get("capabilities", []),
            *content.get("capabilityRequirements", []),
        ]
        for task in content.get("tasks", []):
            values.extend(task.get("capabilityRequirements", []))
        return sorted(set(str(value) for value in values))

    @staticmethod
    def _relationships(
        kind: str, record: dict[str, Any], active: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        edges = list(record.get("relationships", []))
        content = (active or {}).get("content", {})
        bindings = content.get("bindings", {})
        for target_kind, values in (
            ("SKILL", bindings.get("skills", [])),
            ("MCP", bindings.get("mcpTools", [])),
            ("KNOWLEDGE", bindings.get("knowledge", [])),
        ):
            for ref in values:
                edges.append(
                    {
                        "relation": "BINDS",
                        "sourceKind": kind,
                        "targetKind": target_kind,
                        "targetIdentity": ref.get("resourceId"),
                        "targetRevisionId": ref.get("revisionId"),
                        "targetDigest": ref.get("digest"),
                    }
                )
        for key, target_kind in (
            ("workflow", "WORKFLOW"),
            ("runtimeProfile", "RUNTIME_PROFILE"),
            ("model", "MODEL"),
        ):
            ref = bindings.get(key)
            if ref:
                edges.append(
                    {
                        "relation": "BINDS",
                        "sourceKind": kind,
                        "targetKind": target_kind,
                        "targetIdentity": ref.get("resourceId"),
                        "targetRevisionId": ref.get("revisionId"),
                        "targetDigest": ref.get("digest"),
                    }
                )
        if kind == "WORKFLOW":
            for task in content.get("tasks", []):
                for ref in task.get("references", []):
                    edges.append(
                        {
                            "relation": "USES",
                            "sourceKind": kind,
                            "targetKind": ref.get("kind"),
                            "targetIdentity": ref.get("resourceId"),
                            "targetRevisionId": ref.get("revisionId"),
                            "targetDigest": ref.get("digest"),
                        }
                    )
            ref = content.get("runtimeProfile")
            if ref:
                edges.append(
                    {
                        "relation": "USES",
                        "sourceKind": kind,
                        "targetKind": "RUNTIME_PROFILE",
                        "targetIdentity": ref.get("resourceId"),
                        "targetRevisionId": ref.get("revisionId"),
                        "targetDigest": ref.get("digest"),
                    }
                )
        return edges
