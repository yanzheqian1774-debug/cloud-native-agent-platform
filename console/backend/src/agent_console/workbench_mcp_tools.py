"""Read saved MCP operation declarations, never infer execution authority."""

from .definition_authority import canonical_digest
from .skill_mcp_transport import redact
from .workbench_owner_authorization import WorkbenchOwnerError
from .workbench_prepared_resources import bind_service


def receipt_index(record, revision):
    """Only explicit runtime provenance can attribute a receipt to this revision."""
    invocations = record.get("invocations", [])
    required = ("revisionId", "revisionDigest", "snapshotId", "snapshotDigest")
    unknown = sum(not all(item.get(key) for key in required) for item in invocations)
    snapshots = {s["snapshotId"]: s for s in record.get("discoverySnapshots", [])}
    selections = {
        s.get("selectionId"): s
        for s in record.get("toolSelections", [])
        if s.get("selectionId")
    }
    grouped = {}
    for item in invocations[-1000:]:
        if (
            item.get("revisionId") != revision["revisionId"]
            or item.get("revisionDigest") != revision["digest"]
        ):
            continue
        snapshot = snapshots.get(item.get("snapshotId"))
        selection = selections.get(item.get("selectionId"))
        if not snapshot or not selection or not item.get("invocationId"):
            continue
        if (
            snapshot.get("revisionId") != revision["revisionId"]
            or snapshot.get("revisionDigest") != revision["digest"]
            or snapshot.get("digest") != item.get("snapshotDigest")
            or selection.get("snapshotId") != snapshot["snapshotId"]
            or selection.get("revisionId") != revision["revisionId"]
            or selection.get("revisionDigest") != revision["digest"]
            or item.get("toolName") not in selection.get("toolNames", [])
        ):
            continue
        dispatch, status = item.get("dispatchState"), item.get("status")
        outcome = "RESULT_UNKNOWN"
        if dispatch == "NOT_DISPATCHED":
            outcome = (
                "CANCELLED_BEFORE_DISPATCH"
                if status == "CANCELLED"
                else "NOT_DISPATCHED"
            )
        elif dispatch == "RESPONSE_RECEIVED":
            if item.get("reasonCode") == "MCP_TOOL_REPORTED_ERROR":
                outcome = "TOOL_ERROR"
            elif status == "SUCCEEDED":
                outcome = "TOOL_RESPONSE_RECEIVED"
        grouped.setdefault((snapshot["snapshotId"], item.get("toolName")), []).append(
            {
                "invocationId": item["invocationId"],
                "invokedAt": item.get("invokedAt"),
                "outcome": outcome,
            }
        )
    return grouped, unknown, len(invocations) > 1000


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
    receipts, unattributed, receipts_truncated = receipt_index(record, revision)
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
                        "invocations": receipts.get(
                            (snapshot["snapshotId"], tool["name"]), []
                        )[-20:],
                        "invocationsTruncated": len(
                            receipts.get((snapshot["snapshotId"], tool["name"]), [])
                        )
                        > 20,
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
        "invocationEvidence": "EXACT_RUNTIME_RECEIPTS"
        if receipts
        else "EXACT_RUNTIME_REVISION_NOT_ESTABLISHED",
        "unattributedSourceInvocationCount": unattributed,
        "invocationWindowTruncated": receipts_truncated,
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
