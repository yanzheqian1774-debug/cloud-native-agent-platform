"""Private authorization-first unified product assembly API."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException

from agent_console import (
    knowledge_api,
    runtime_profile_api,
    skill_mcp_api,
    workflow_definition_api,
)
from agent_console.attention_service import AttentionService
from agent_console.digital_employee_service import DigitalEmployeeService
from agent_console.product_dashboard_service import ProductDashboardService
from agent_console.resource_catalog_service import (
    ProductAssemblyFailure,
    ProductScope,
    ResourceCatalogService,
)
from agent_console.resource_relationship_service import ResourceRelationshipService

router = APIRouter(prefix="/api/internal/v0.2.2/product")


def trusted_scope(
    tenant: Annotated[str, Header(alias="X-Tenant-ID")] = "tenant-a",
    domain: Annotated[str, Header(alias="X-Security-Domain")] = "supplier-quality",
    authorized: Annotated[str, Header(alias="X-Product-Read-Authorized")] = "true",
) -> ProductScope:
    if authorized.lower() != "true":
        raise HTTPException(
            403, detail={"reasonCode": "PRODUCT_ASSEMBLY_ACCESS_DENIED"}
        )
    return ProductScope(tenant, domain)


def get_catalog() -> ResourceCatalogService:
    from agent_console.app import get_agent_definition_service

    def agents(scope):
        service = get_agent_definition_service()
        return service.list(service.scope(scope.namespace, scope.security_domain))

    def skills(kind):
        return lambda scope: skill_mcp_api.get_skill_mcp_service().list(
            skill_mcp_api.get_skill_mcp_service().scope(
                scope.namespace, scope.security_domain
            ),
            kind,
        )

    def knowledge(scope):
        service = knowledge_api.get_knowledge_service()
        return service.list(service.scope(scope.namespace, scope.security_domain))

    def workflows(scope):
        service = workflow_definition_api.get_service()
        return service.list(service.scope(scope.namespace, scope.security_domain))

    def runtimes(scope):
        service = runtime_profile_api.get_service()
        return service.list(service.scope(scope.namespace, scope.security_domain))

    return ResourceCatalogService(
        {
            "AGENT": agents,
            "SKILL": skills("skill"),
            "MCP": skills("mcp"),
            "KNOWLEDGE": knowledge,
            "WORKFLOW": workflows,
            "RUNTIME_PROFILE": runtimes,
        }
    )


Catalog = Annotated[ResourceCatalogService, Depends(get_catalog)]
Scope = Annotated[ProductScope, Depends(trusted_scope)]


def call(operation):
    try:
        return operation()
    except HTTPException:
        raise
    except ProductAssemblyFailure as exc:
        raise HTTPException(exc.status, detail={"reasonCode": exc.reason}) from exc
    except Exception as exc:
        raise HTTPException(
            503, detail={"reasonCode": "PRODUCT_ASSEMBLY_SOURCE_UNAVAILABLE"}
        ) from exc


@router.get("/catalog")
def catalog(
    scope: Scope, service: Catalog, query: str = "", kind: str = "", status: str = ""
):
    return call(lambda: service.list(scope, query=query, kind=kind, status=status))


@router.get("/catalog/{kind}/{identity}")
def resource(kind: str, identity: str, scope: Scope, service: Catalog):
    return call(lambda: service.get(scope, kind, identity))


@router.get("/dashboard")
def dashboard(scope: Scope, service: Catalog):
    return call(lambda: ProductDashboardService(service).get(scope))


@router.get("/relationships")
def relationships(scope: Scope, service: Catalog):
    return call(lambda: ResourceRelationshipService(service).list(scope))


@router.get("/attention")
def attention(scope: Scope, service: Catalog):
    return call(lambda: AttentionService(service).list(scope))


@router.get("/digital-employee-templates")
def digital_employee_templates(scope: Scope, service: Catalog):
    return call(lambda: DigitalEmployeeService(service).list(scope))
