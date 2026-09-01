"""Read-only attention items derived from existing exact revision facts."""

from typing import Any

from agent_console.resource_catalog_service import ProductScope, ResourceCatalogService


class AttentionService:
    def __init__(self, catalog: ResourceCatalogService) -> None:
        self.catalog = catalog

    def list(self, scope: ProductScope) -> list[dict[str, Any]]:
        return [
            {
                "kind": item["kind"],
                "identity": item["identity"],
                "revisionId": item["revisionId"],
                "digest": item["digest"],
                "status": "REVIEW_REQUIRED"
                if item["reviewStatus"] == "REVIEW_REQUIRED"
                else "APPROVED",
                "reason": "Exact active revision digest requires Human review"
                if item["reviewStatus"] == "REVIEW_REQUIRED"
                else "Exact active revision digest has an existing approval",
                "deepLink": item["deepLink"],
            }
            for item in self.catalog.list(scope)
            if item["reviewStatus"] == "REVIEW_REQUIRED"
        ]
