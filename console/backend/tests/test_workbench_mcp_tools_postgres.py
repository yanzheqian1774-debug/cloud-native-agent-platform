# ruff: noqa: F811 -- Explicit isolated PostgreSQL fixture import.
"""Trusted route reads only exact authorized stored discovery; no MCP transport."""

import copy
import json
from dataclasses import replace
from pathlib import Path

from agent_console.authority_contracts import AuthorityScope
from agent_console.skill_mcp_postgres import PostgresSkillMcpRepository
from agent_console.skill_mcp_service import SkillMcpService
from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
from agent_console.workbench_resource_directory import operations, target
from fastapi.testclient import TestClient
from test_workbench_authorization_postgres import (
    context,
    repository,  # noqa: F401
    seed,
    seed_workflow_grant,
)
from test_workbench_bff import SessionStub
from test_workbench_mcp_tools import record


def test_real_route_exact_grant_history_scope_and_revocation(repository):
    now, _, adapter = seed(repository)
    owner = PostgresSkillMcpRepository(
        repository.pool.conninfo,
        migration_path=Path(__file__).parents[1]
        / "migrations/0002_skill_mcp_lifecycle.sql",
    )
    try:
        owner.migrate()
        value = record()
        value.update(namespace="tenant-a", securityDomain="quality", kind="mcp")
        original = copy.deepcopy(value)
        with repository.connection_scope() as connection:
            connection.execute(
                "INSERT INTO skill_mcp_resource.resources "
                "(namespace,security_domain,kind,resource_id,aggregate_version,record) "
                "VALUES ('tenant-a','quality','mcp','mcp:orders',1,%s::jsonb)",
                (json.dumps(value),),
            )
        sessions = SessionStub()
        sessions.context = context()
        app = create_workbench_bff(
            sessions,
            adapter,
            WorkbenchBffPolicy("workbench.example", "https://workbench.example"),
            operations=operations({"mcp": SkillMcpService(owner)}, None),
        )
        path = "/api/workbench/v1/resource-directory/mcp/mcp:orders/revision:old/tools"
        with TestClient(app, base_url="https://workbench.example") as client:
            assert client.get(path).status_code == 401
            client.cookies.set("__Host-workbench_session", sessions.secret)
            denied = client.get(path)
            assert denied.status_code == 404
            assert "result" not in denied.json()
            seed_workflow_grant(
                repository, now, target("mcp", "mcp:orders", "revision:old")
            )
            response = client.get(path)
            assert response.status_code == 200
            result = response.json()["result"]
            assert result["revisionDigest"] == "a" * 64
            assert result["subject"] == "human:alice"
            assert result["snapshots"][0]["tools"][0]["name"] == "find_orders"
            assert result["executionAuthority"] == "NONE"
            assert "private-" not in response.text
            assert (
                client.get(path.replace("revision:old", "revision:new")).status_code
                == 404
            )
            sessions.context = replace(
                context(), scope=AuthorityScope("other", "quality")
            )
            assert client.get(path).status_code == 404
            sessions.context = context()
            with repository.connection_scope() as connection:
                connection.execute(
                    "DELETE FROM authorization_admin.effective_grants "
                    "WHERE grant_id='grant-workflow'"
                )
            denied = client.get(path)
            assert denied.status_code == 404
            assert "result" not in denied.json()
        assert (
            owner.get(
                owner_scope := SkillMcpService.scope("tenant-a", "quality"),
                "mcp",
                "mcp:orders",
            )
            == original
        )
        assert owner_scope.namespace == "tenant-a"
        with repository.connection_scope() as connection:
            assert (
                connection.execute(
                    "SELECT count(*) n FROM skill_mcp_resource.lifecycle_facts"
                ).fetchone()["n"]
                == 0
            )
    finally:
        owner.pool.close()
