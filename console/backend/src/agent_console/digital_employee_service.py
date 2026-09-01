"""Digital Employee template projection without execution authority."""

from typing import Any

from agent_console.resource_catalog_service import ProductScope, ResourceCatalogService


class DigitalEmployeeService:
    def __init__(self, catalog: ResourceCatalogService) -> None:
        self.catalog = catalog

    def list(self, scope: ProductScope) -> list[dict[str, Any]]:
        agents = self.catalog.list(scope, kind="AGENT")
        return [
            {
                "templateId": f"digital-employee-template:{item['identity']}",
                "name": item["name"],
                "purpose": (
                    "Reusable composition input over the exact Agent Definition "
                    "bindings"
                ),
                "agentDefinition": {
                    "identity": item["identity"],
                    "revisionId": item["revisionId"],
                    "digest": item["digest"],
                },
                "composition": item["relationships"],
                "readiness": "MATCHABLE"
                if item["lifecycleStatus"] == "PUBLISHED"
                and item["compatibility"] == "COMPATIBLE"
                else "NOT_MATCHABLE",
                "limitations": list(
                    dict.fromkeys(
                        [
                            *item["limitations"],
                            "TEMPLATE_ONLY",
                            "NO_EXECUTION_AUTHORITY",
                            "UNVERIFIED_MODEL_REFERENCE",
                        ]
                    )
                ),
                "executionAuthority": "NONE",
                "deepLink": item["deepLink"],
            }
            for item in agents
        ]
