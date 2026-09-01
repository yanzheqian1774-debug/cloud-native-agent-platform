import agent_console.app as app_module
from agent_console.agent_definition_repository import DefinitionScope
from agent_console.app import _WorkbenchBindingResolver, app
from agent_console.attention_service import AttentionService
from agent_console.digital_employee_service import DigitalEmployeeService
from agent_console.product_dashboard_service import ProductDashboardService
from agent_console.resource_catalog_api import get_catalog
from agent_console.resource_catalog_service import ProductScope, ResourceCatalogService
from agent_console.resource_relationship_service import ResourceRelationshipService
from fastapi.testclient import TestClient

SCOPE = ProductScope("tenant-a", "supplier-quality")


class _Repository:
    def __init__(self, records):
        self.records = records

    def get(self, scope, *identity):
        key = (scope.namespace, scope.security_domain, *identity)
        if key not in self.records:
            raise LookupError("RESOURCE_NOT_FOUND")
        return self.records[key]


class _Service:
    def __init__(self, records):
        self.repository = _Repository(records)

    @staticmethod
    def scope(namespace, security_domain):
        return ProductScope(namespace, security_domain)


def _bound_record(kind, identity, *, state="PUBLISHED", **overrides):
    revision_id = f"{kind}-revision:1"
    identity_key = "knowledgeId" if kind == "knowledge" else "resourceId"
    return {
        identity_key: identity,
        "publishedRevisionId": revision_id if state == "PUBLISHED" else None,
        "lifecycleState": state,
        "enabled": True,
        "archived": False,
        "compatible": True,
        "revisions": [
            {"revisionId": revision_id, "digest": f"{kind}-digest", "state": state}
        ],
        **overrides,
    }


def test_workbench_resolver_composes_exact_scope_authorities_and_fails_closed(
    monkeypatch,
):
    scope = DefinitionScope("tenant-a", "supplier-quality")
    skill = _bound_record("skill", "skill:quality")
    mcp = _bound_record(
        "mcp",
        "mcp:quality",
        discoverySnapshots=[{"snapshotId": "mcp-snapshot:1"}],
        toolSelections=[
            {"snapshotId": "mcp-snapshot:1", "toolNames": ["quality.lookup"]}
        ],
    )
    knowledge = _bound_record(
        "knowledge",
        "knowledge:quality",
        activeIndexSnapshotId="knowledge-snapshot:1",
    )
    resource_service = _Service(
        {
            ("tenant-a", "supplier-quality", "skill", "skill:quality"): skill,
            ("tenant-a", "supplier-quality", "mcp", "mcp:quality"): mcp,
        }
    )
    knowledge_service = _Service(
        {("tenant-a", "supplier-quality", "knowledge:quality"): knowledge}
    )
    monkeypatch.setattr(app_module, "get_skill_mcp_service", lambda: resource_service)
    monkeypatch.setattr(app_module, "get_knowledge_service", lambda: knowledge_service)

    resolver = _WorkbenchBindingResolver()
    resolved_skill = resolver.resolve(scope, "skill", "skill:quality")
    resolved_mcp = resolver.resolve(scope, "mcp", "mcp:quality")
    resolved_knowledge = resolver.resolve(scope, "knowledge", "knowledge:quality")
    assert resolved_skill and resolved_skill.digest == "skill-digest"
    assert resolved_mcp and resolved_mcp.tools == ("quality.lookup",)
    assert resolved_mcp.snapshots == ("mcp-snapshot:1",)
    assert resolved_knowledge and resolved_knowledge.snapshots == (
        "knowledge-snapshot:1",
    )
    assert resolver.resolve(scope, "skill", "skill:absent") is None
    assert (
        resolver.resolve(
            DefinitionScope("tenant-b", "supplier-quality"),
            "skill",
            "skill:quality",
        )
        is None
    )


def test_workbench_resolver_preserves_fail_closed_resource_states(monkeypatch):
    scope = DefinitionScope("tenant-a", "supplier-quality")
    records = {}
    for name, changes in (
        ("unpublished", {"publishedRevisionId": None}),
        ("disabled", {"enabled": False}),
        ("deprecated", {"lifecycleState": "DEPRECATED"}),
        ("incompatible", {"compatible": False}),
    ):
        identity = f"skill:{name}"
        records[("tenant-a", "supplier-quality", "skill", identity)] = _bound_record(
            "skill", identity, **changes
        )
    monkeypatch.setattr(app_module, "get_skill_mcp_service", lambda: _Service(records))
    resolver = _WorkbenchBindingResolver()
    assert resolver.resolve(scope, "skill", "skill:unpublished") is None
    assert resolver.resolve(scope, "skill", "skill:disabled").enabled is False
    assert resolver.resolve(scope, "skill", "skill:deprecated").deprecated is True
    assert resolver.resolve(scope, "skill", "skill:incompatible").compatible is False


def _revision(revision_id="revision:1", state="DRAFT", bindings=None):
    return {
        "revisionId": revision_id,
        "state": state,
        "digest": "sha256:exact",
        "content": {
            "title": "Quality Analyst",
            "capabilities": ["supplier-quality"],
            "bindings": bindings or {},
        },
    }


def _catalog():
    agent = {
        "definitionId": "agent:quality",
        "name": "Quality Analyst",
        "lifecycleState": "PUBLISHED",
        "enabled": True,
        "archived": False,
        "publishedRevisionId": "revision:1",
        "currentDraftRevisionId": None,
        "revisions": [
            _revision(
                state="PUBLISHED",
                bindings={
                    "skills": [
                        {
                            "resourceId": "skill:quality",
                            "revisionId": "skill-revision:1",
                            "digest": "sha256:skill",
                        }
                    ],
                    "model": {"resourceId": "model:declared"},
                },
            )
        ],
        "reviews": [{"digest": "sha256:exact", "decision": "APPROVE"}],
        "limitations": [],
    }
    skill = {
        "resourceId": "skill:quality",
        "name": "Quality Skill",
        "lifecycleState": "DRAFT",
        "enabled": True,
        "archived": False,
        "publishedRevisionId": None,
        "currentDraftRevisionId": "skill-revision:1",
        "revisions": [
            {
                "revisionId": "skill-revision:1",
                "state": "DRAFT",
                "digest": "sha256:skill",
                "content": {},
            }
        ],
        "reviews": [],
        "limitations": [],
    }

    def empty(_scope):
        return []

    return ResourceCatalogService(
        {
            "AGENT": lambda _scope: [agent],
            "SKILL": lambda _scope: [skill],
            "MCP": empty,
            "KNOWLEDGE": empty,
            "WORKFLOW": empty,
            "RUNTIME_PROFILE": empty,
        }
    )


def test_catalog_dashboard_relationship_attention_and_template_are_derived():
    catalog = _catalog()
    resources = catalog.list(SCOPE)
    assert [item["kind"] for item in resources] == ["AGENT", "SKILL"]
    assert (
        catalog.list(SCOPE, query="supplier-quality")[0]["identity"] == "agent:quality"
    )
    assert ProductDashboardService(catalog).get(SCOPE)["resourceCount"] == 2
    assert ProductDashboardService(catalog).get(SCOPE)["attentionCount"] == 1
    assert (
        ResourceRelationshipService(catalog).list(SCOPE)[0]["targetIdentity"]
        == "skill:quality"
    )
    assert AttentionService(catalog).list(SCOPE)[0]["identity"] == "skill:quality"
    template = DigitalEmployeeService(catalog).list(SCOPE)[0]
    assert template["readiness"] == "MATCHABLE"
    assert template["executionAuthority"] == "NONE"
    assert "UNVERIFIED_MODEL_REFERENCE" in template["limitations"]


def test_scope_is_resolved_before_any_resource_disclosure():
    client = TestClient(app)
    response = client.get(
        "/api/internal/v0.2.2/product/catalog",
        headers={"X-Product-Read-Authorized": "false"},
    )
    assert response.status_code == 403
    assert response.json() == {
        "detail": {"reasonCode": "PRODUCT_ASSEMBLY_ACCESS_DENIED"}
    }


def test_product_api_uses_one_catalog_for_identical_product_and_technical_identity():
    app.dependency_overrides[get_catalog] = _catalog
    try:
        client = TestClient(app)
        catalog = client.get("/api/internal/v0.2.2/product/catalog").json()
        templates = client.get(
            "/api/internal/v0.2.2/product/digital-employee-templates"
        ).json()
        assert templates[0]["agentDefinition"] == {
            "identity": catalog[0]["identity"],
            "revisionId": catalog[0]["revisionId"],
            "digest": catalog[0]["digest"],
        }
    finally:
        app.dependency_overrides.clear()
