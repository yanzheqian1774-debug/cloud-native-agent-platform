"""Exact discovery provenance and read-only operation projection boundaries."""

import copy
import json

import pytest
from agent_console.definition_authority import canonical_digest
from agent_console.workbench_mcp_tools import project_tools
from agent_console.workbench_owner_authorization import WorkbenchOwnerError
from agent_console.workbench_resource_directory import operations, target


def record():
    catalog = {
        "tools": [{"name": "find_orders", "inputSchema": {"type": "object"}}],
        "resources": [],
        "prompts": [],
    }
    snapshot = {
        "snapshotId": "snapshot:old",
        "revisionId": "revision:old",
        "revisionDigest": "a" * 64,
        "catalog": catalog,
        "digest": canonical_digest(catalog, domain="mcp-discovery-snapshot-v1"),
    }
    return {
        "resourceId": "mcp:orders",
        "name": "Orders",
        "revisions": [
            {"revisionId": "revision:old", "digest": "a" * 64, "state": "PUBLISHED"},
            {"revisionId": "revision:new", "digest": "b" * 64, "state": "DRAFT"},
        ],
        "discoverySnapshots": [snapshot],
        "toolSelections": [
            {
                "snapshotId": "snapshot:old",
                "revisionId": "revision:old",
                "revisionDigest": "a" * 64,
                "toolNames": ["find_orders"],
            }
        ],
        "invocations": [{"input": "private-input", "result": "private-result"}],
        "secretReference": "private-credential-reference",
    }


def test_exact_historical_tools_do_not_substitute_new_revision_or_infer_execution():
    value = record()
    original = copy.deepcopy(value)
    result = project_tools(value, "revision:old")
    assert result["snapshots"][0]["tools"][0]["selectedInSavedSnapshot"] is True
    assert result["revisionDigest"] == "a" * 64
    assert result["executionAuthority"] == "NONE"
    assert result["invocationEvidence"] == "EXACT_RUNTIME_REVISION_NOT_ESTABLISHED"
    assert "private-" not in json.dumps(result)
    assert project_tools(value, "revision:new")["snapshots"] == []
    assert project_tools(value, "revision:new")["availability"] == "NO_EXACT_SNAPSHOT"
    assert value == original


def test_operation_hints_remain_declarations_not_execution_authority():
    value = record()
    snapshot = value["discoverySnapshots"][0]
    snapshot["catalog"]["tools"][0]["annotations"] = {"readOnlyHint": True}
    snapshot["digest"] = canonical_digest(
        snapshot["catalog"], domain="mcp-discovery-snapshot-v1"
    )
    result = project_tools(value, "revision:old")
    assert result["snapshots"][0]["tools"][0]["annotations"] == {"readOnlyHint": True}
    assert result["executionAuthority"] == "NONE"


def test_missing_or_mismatched_provenance_never_becomes_exact_snapshot():
    value = record()
    value["discoverySnapshots"][0].pop("revisionId")
    assert project_tools(value, "revision:old")["snapshots"] == []
    value = record()
    value["discoverySnapshots"][0]["revisionDigest"] = "b" * 64
    assert project_tools(value, "revision:old")["snapshots"] == []
    value = record()
    value["toolSelections"][0]["revisionDigest"] = "b" * 64
    result = project_tools(value, "revision:old")
    assert not result["snapshots"][0]["tools"][0]["selectedInSavedSnapshot"]


@pytest.mark.parametrize("damage", ["digest", "duplicate", "invalid"])
def test_corrupt_or_ambiguous_discovery_is_not_a_successful_empty_catalog(damage):
    value = record()
    snapshot = value["discoverySnapshots"][0]
    if damage == "digest":
        snapshot["digest"] = "bad"
    else:
        snapshot["catalog"]["tools"] += (
            [copy.deepcopy(snapshot["catalog"]["tools"][0])]
            if damage == "duplicate"
            else [{"name": None}]
        )
        snapshot["digest"] = canonical_digest(
            snapshot["catalog"], domain="mcp-discovery-snapshot-v1"
        )
    with pytest.raises(WorkbenchOwnerError):
        project_tools(value, "revision:old")


def test_bounded_projection_reports_partial_and_keeps_snapshot_identity():
    value = record()
    template = value["discoverySnapshots"][0]
    value["discoverySnapshots"] = [
        {**template, "snapshotId": f"snapshot:{i}"} for i in range(201)
    ]
    result = project_tools(value, "revision:old")
    assert len(result["snapshots"]) == 200
    assert result["snapshotsTruncated"]
    assert result["snapshots"][0]["snapshotId"] == "snapshot:1"
    with pytest.raises(WorkbenchOwnerError):
        project_tools(value, "revision:missing")


def test_endpoint_uses_existing_exact_mcp_read_grant_without_new_authority():
    operation = next(
        op for op in operations({}, None) if op.name == "READ_MCP_TOOL_DECLARATIONS"
    )
    assert operation.method == "GET"
    assert operation.grant_builder(
        None, {"identity": "mcp:orders", "revision": "revision:old"}, {}, {}
    ) == (target("mcp", "mcp:orders", "revision:old"),)


def exact_receipt(value, **changes):
    snapshot = value["discoverySnapshots"][0]
    value["toolSelections"][0]["selectionId"] = "selection:exact"
    return {
        "invocationId": "call:1",
        "selectionId": "selection:exact",
        "revisionId": "revision:old",
        "revisionDigest": "a" * 64,
        "snapshotId": snapshot["snapshotId"],
        "snapshotDigest": snapshot["digest"],
        "toolName": "find_orders",
        "dispatchState": "RESPONSE_RECEIVED",
        "status": "SUCCEEDED",
        "input": "private-input",
        "result": "private-output",
        **changes,
    }


@pytest.mark.parametrize(
    "dispatch,status,reason,outcome",
    [
        (
            "RESPONSE_RECEIVED",
            "SUCCEEDED",
            "MCP_TOOL_COMPLETED",
            "TOOL_RESPONSE_RECEIVED",
        ),
        ("RESPONSE_RECEIVED", "FAILED", "MCP_TOOL_REPORTED_ERROR", "TOOL_ERROR"),
        ("CALL_ATTEMPTED", "FAILED", "MCP_TIMEOUT", "RESULT_UNKNOWN"),
        ("NOT_DISPATCHED", "FAILED", "MCP_CONNECTION_FAILED", "NOT_DISPATCHED"),
        (
            "NOT_DISPATCHED",
            "CANCELLED",
            "CANCELLED_BEFORE_DISPATCH",
            "CANCELLED_BEFORE_DISPATCH",
        ),
    ],
)
def test_receipt_outcome_is_explicit_and_sensitive_payload_never_exposed(
    dispatch, status, reason, outcome
):
    value = record()
    value["invocations"].append(
        exact_receipt(value, dispatchState=dispatch, status=status, reasonCode=reason)
    )
    result = project_tools(value, "revision:old")
    receipts = result["snapshots"][0]["tools"][0]["invocations"]
    assert receipts == [
        {"invocationId": "call:1", "invokedAt": None, "outcome": outcome}
    ]
    assert result["unattributedSourceInvocationCount"] == 1
    assert "private-" not in json.dumps(result)
    assert project_tools(value, "revision:new")["snapshots"] == []


@pytest.mark.parametrize(
    "key",
    [
        "revisionId",
        "revisionDigest",
        "snapshotId",
        "snapshotDigest",
        "selectionId",
        "toolName",
    ],
)
def test_receipts_never_follow_same_name_or_selection_ancestry(key):
    value = record()
    value["invocations"] = [exact_receipt(value, **{key: "mismatch"})]
    result = project_tools(value, "revision:old")
    assert result["snapshots"][0]["tools"][0]["invocations"] == []


def test_receipt_window_and_per_tool_limits_are_explicit():
    value = record()
    template = exact_receipt(value)
    value["invocations"] = [
        {**template, "invocationId": f"call:{i}"} for i in range(1001)
    ]
    result = project_tools(value, "revision:old")
    tool = result["snapshots"][0]["tools"][0]
    assert result["invocationWindowTruncated"] and tool["invocationsTruncated"]
    assert (
        len(tool["invocations"]) == 20
        and tool["invocations"][0]["invocationId"] == "call:981"
    )
