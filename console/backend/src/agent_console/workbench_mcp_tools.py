"""Read saved MCP operation declarations, never infer execution authority."""

from .definition_authority import canonical_digest
from .skill_mcp_transport import redact
from .workbench_owner_authorization import WorkbenchOwnerError
from .workbench_prepared_resources import bind_service


def project_tools(record, revision_id):
    revision = next(
        (r for r in record["revisions"] if r["revisionId"] == revision_id), None
    )
    if revision is None:
        raise WorkbenchOwnerError("RESOURCE_DIRECTORY_NOT_FOUND", 404)
    exact = [
        s
        for s in record.get("discoverySnapshots", [])
        if s.get("revisionId") == revision_id
        and s.get("revisionDigest") == revision["digest"]
    ]
    snapshots = []
    for snapshot in exact[-200:]:
        catalog = snapshot.get("catalog")
        if not isinstance(catalog, dict) or snapshot.get("digest") != canonical_digest(
            catalog, domain="mcp-discovery-snapshot-v1"
        ):
            raise WorkbenchOwnerError("MCP_DISCOVERY_DIGEST_MISMATCH", 409)
        tools = catalog.get("tools")
        if not isinstance(tools, list) or any(
            not isinstance(tool, dict)
            or not isinstance(tool.get("name"), str)
            or not tool["name"].strip()
            for tool in tools
        ):
            raise WorkbenchOwnerError("MCP_DISCOVERY_TOOLS_INVALID", 409)
        if len({tool["name"] for tool in tools}) != len(tools):
            raise WorkbenchOwnerError("MCP_DISCOVERY_TOOLS_AMBIGUOUS", 409)
        selections = [
            s
            for s in record.get("toolSelections", [])
            if s.get("snapshotId") == snapshot["snapshotId"]
            and s.get("revisionId") == revision_id
            and s.get("revisionDigest") == revision["digest"]
        ]
        selected = {name for s in selections for name in s.get("toolNames", [])}
        snapshots.append(
            {
                "snapshotId": snapshot["snapshotId"],
                "digest": snapshot["digest"],
                "capturedAt": snapshot.get("capturedAt"),
                "protocolRevision": snapshot.get("protocolRevision"),
                "tools": [
                    {
                        **redact(
                            {
                                k: tool[k]
                                for k in (
                                    "name",
                                    "description",
                                    "inputSchema",
                                    "outputSchema",
                                    "annotations",
                                    "sideEffect",
                                )
                                if k in tool
                            }
                        ),
                        "selectedInSavedSnapshot": tool["name"] in selected,
                    }
                    for tool in tools[:500]
                ],
                "toolsTruncated": len(tools) > 500,
            }
        )
    return {
        "identity": record["resourceId"],
        "name": record["name"],
        "revisionId": revision_id,
        "revisionDigest": revision["digest"],
        "sourceRevisionState": revision["state"],
        "sourceEnabled": record.get("enabled", True),
        "sourceArchived": record.get("archived", False),
        "snapshots": snapshots,
        "snapshotsTruncated": len(exact) > 200,
        "basis": "SAVED_EXACT_MCP_DISCOVERY",
        "availability": "EXACT_SNAPSHOT_SAVED" if snapshots else "NO_EXACT_SNAPSHOT",
        "executionAuthority": "NONE",
        "invocationEvidence": "EXACT_RUNTIME_REVISION_NOT_ESTABLISHED",
    }


def read_tools(services, call):
    service = services.get("mcp")
    if service is None:
        raise WorkbenchOwnerError("PREPARED_RESOURCE_OWNER_UNAVAILABLE", 503)
    service = bind_service(service, call.connection)
    scope = service.scope(
        call.context.scope.tenant_id, call.context.scope.security_domain
    )
    record = service.repository.get(scope, "mcp", call.path["identity"])
    return {
        **project_tools(record, call.path["revision"]),
        "subject": call.context.principal_id,
        "scope": {
            "tenantId": scope.namespace,
            "securityDomain": scope.security_domain,
        },
    }
