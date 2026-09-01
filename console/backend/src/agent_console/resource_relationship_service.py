"""Read-only relationship projection; no graph authority is persisted here."""

from typing import Any

from agent_console.resource_catalog_service import ProductScope, ResourceCatalogService


class ResourceRelationshipService:
    def __init__(self, catalog: ResourceCatalogService) -> None:
        self.catalog = catalog

    def list(self, scope: ProductScope) -> list[dict[str, Any]]:
        resources = self.catalog.list(scope)
        edges = []
        for item in resources:
            for relation in item["relationships"]:
                edges.append(
                    {
                        "sourceKind": item["kind"],
                        "sourceIdentity": item["identity"],
                        "sourceRevisionId": item["revisionId"],
                        "sourceDigest": item["digest"],
                        "relationshipId": self._relationship_id(item, relation),
                        **relation,
                    }
                )
        return edges

    @staticmethod
    def _relationship_id(source: dict[str, Any], relation: dict[str, Any]) -> str:
        return "|".join(
            str(value or "")
            for value in (
                source["kind"],
                source["identity"],
                source["revisionId"],
                relation.get("relation"),
                relation.get("targetKind"),
                relation.get("targetIdentity"),
                relation.get("targetRevisionId"),
            )
        )
