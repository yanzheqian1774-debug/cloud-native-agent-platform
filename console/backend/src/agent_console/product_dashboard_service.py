"""Truthful Dashboard projection derived from the unified catalog."""

from collections import Counter
from typing import Any

from agent_console.resource_catalog_service import ProductScope, ResourceCatalogService


class ProductDashboardService:
    def __init__(self, catalog: ResourceCatalogService) -> None:
        self.catalog = catalog

    def get(self, scope: ProductScope) -> dict[str, Any]:
        resources = self.catalog.list(scope)
        by_kind = Counter(item["kind"] for item in resources)
        by_lifecycle = Counter(item["lifecycleStatus"] for item in resources)
        attention = sum(item["reviewStatus"] == "REVIEW_REQUIRED" for item in resources)
        incompatible = sum(
            item["compatibility"] == "INCOMPATIBLE" for item in resources
        )
        return {
            "resourceCount": len(resources),
            "countsByKind": dict(by_kind),
            "countsByLifecycle": dict(by_lifecycle),
            "attentionCount": attention,
            "capabilityGapCount": incompatible,
            "authority": "AUTHORIZED_DURABLE_DOMAIN_FACTS",
            "limitations": [
                "PREVIEW",
                "NOT_CERTIFIED",
                "NON_PRODUCTION_READY",
                "NO_EXECUTION_AUTHORITY",
            ],
        }
