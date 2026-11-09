"""Non-table computation checks, separate from live provider acceptance."""

from copy import deepcopy

import pytest
from agent_console.native_document_resource_bundle import resource_content
from agent_console.native_document_skill import NativeDocumentSkillExecutor
from agent_console.native_document_tools import (
    NativeDocumentTools,
    review,
    validate_source,
)
from agent_console.native_loop_provider import action_schema
from agent_console.skill_executor import SkillExecutorFailure

REFERENCE = {"resource_id": "knowledge:docs", "revision_id": "1", "digest": "a" * 64}
SOURCE = {
    "schemaVersion": "document-review-source.v1",
    "synthetic": True,
    "title": "Handover",
    "documents": [
        {
            "id": "submission",
            "title": "Handover",
            "role": "SUBMISSION",
            "text": "# Handover\n## Owner\nAlice\n## Rollback\nTODO\n",
        },
        {
            "id": "staging",
            "title": "Staging policy",
            "role": "POLICY",
            "scope": "staging",
            "text": "# Policy\n## Owner\nName the owner.\n",
        },
        {
            "id": "production",
            "title": "Production policy",
            "role": "POLICY",
            "scope": "production",
            "text": (
                "# Policy\n## Owner\nName the owner.\n## Rollback\n"
                "State rollback steps.\n## Verification\nDescribe verification.\n"
            ),
        },
    ],
}


def test_policy_requires_actual_answer_and_changes_document_findings():
    lib = NativeDocumentTools(SOURCE, REFERENCE)
    args = {"documentId": "submission", "policyId": "production"}
    assert lib.invoke("review_document", args)["state"] == "NEEDS_CLARIFICATION"
    lib.record_answer("production")
    result = lib.invoke("review_document", args)
    assert result["missingSections"] == ["Verification"]
    assert result["incompleteSections"] == ["Rollback"]
    evidence = result["findings"][1]["evidence"]
    assert evidence["line"] == 4 and evidence["body"][0] == {"line": 5, "text": "TODO"}
    lib.record_answer("staging")
    assert lib.invoke("review_document", args)["state"] == "NEEDS_CLARIFICATION"
    result = lib.invoke(
        "review_document", {"documentId": "submission", "policyId": "staging"}
    )
    assert result["missingSections"] == result["incompleteSections"] == []


def test_independent_completion_requires_selected_original_documents_and_exact_answer():
    lib = NativeDocumentTools(SOURCE, REFERENCE)
    lib.record_answer("production")
    lib.invoke(
        "review_document", {"documentId": "submission", "policyId": "production"}
    )
    report = lib.invoke("build_report", {})
    observations = [{"kind": "TOOL_RESULT", "tool": "build_report", "output": report}]
    assert not lib.verify({"observations": observations}, report["completionAnswer"])[
        "passed"
    ]
    observations.extend(
        {
            "kind": "TOOL_RESULT",
            "tool": "read_document",
            "arguments": {"id": i},
            "output": lib.invoke("read_document", {"id": i}),
        }
        for i in ["submission", "production"]
    )
    assert lib.verify({"observations": observations}, report["completionAnswer"])[
        "passed"
    ]
    fabricated = {**report["completionAnswer"], "missingSections": []}
    assert not lib.verify({"observations": observations}, fabricated)["passed"]
    altered = deepcopy(report)
    altered["findings"][1]["evidence"]["body"][0]["text"] = "Invented"
    observations[0]["output"] = altered
    assert not lib.verify({"observations": observations}, report["completionAnswer"])[
        "passed"
    ]


def test_document_bundle_has_typed_path_and_no_live_model_fallback():
    from agent_console.planning_contracts import INPUTS, OUTPUTS

    operations = resource_content(SOURCE)["skill"]["operations"]
    previous = "CONTEXT"
    for op in operations:
        assert previous in INPUTS[op["name"]]
        previous = OUTPUTS[op["name"]]
    inputs = {
        "synthetic": True,
        "sourceSnapshot": REFERENCE,
        "source": SOURCE,
        "dependencies": {},
    }
    executor = NativeDocumentSkillExecutor()
    read = executor.invoke("r", "READ_DATA", inputs, 1000).output
    with pytest.raises(SkillExecutorFailure, match="MODEL_NOT_CONFIGURED"):
        executor.invoke(
            "a", "ANALYZE_DATA", {**inputs, "dependencies": {"read": read}}, 1000
        )
    lib = NativeDocumentTools(SOURCE, REFERENCE)
    schema = action_schema([t.descriptor() for t in lib.tools], lib.answer_schema)
    assert (
        schema["properties"]["decision"]["anyOf"][-2]["properties"]["answer"]
        == lib.answer_schema
    )


def test_duplicate_sections_and_wrong_role_are_rejected_and_source_is_not_mutated():
    source = deepcopy(SOURCE)
    source["documents"][0]["text"] += "## Owner\nOther\n"
    with pytest.raises(ValueError, match="DUPLICATE_SECTION"):
        review(source, "submission", "production")
    with pytest.raises(ValueError, match="ROLE_MISMATCH"):
        review(SOURCE, "production", "staging")
    before = deepcopy(SOURCE)
    lib = NativeDocumentTools(SOURCE, REFERENCE)
    assert lib.invoke("search_documents", {"query": "TODO"})["matches"] == [
        {"documentId": "submission", "line": 5, "text": "TODO"}
    ]
    assert before == SOURCE
    validate_source(SOURCE)


def test_every_document_operation_satisfies_published_platform_output_contract():
    from agent_console.native_document_skill import DocumentComputationExecutor
    from agent_console.skill_invocation_postgres import _validate_json_schema

    bundle = resource_content(SOURCE)
    executor = DocumentComputationExecutor()
    inputs = {
        "schemaVersion": "document-review-input.v1",
        "synthetic": True,
        "sourceSnapshot": REFERENCE,
        "source": SOURCE,
        "dependencies": {},
    }
    previous = None
    for operation in bundle["skill"]["operations"]:
        args = {**inputs, "dependencies": {"previous": previous} if previous else {}}
        _validate_json_schema(args, operation["inputSchema"], "INVALID_INPUT")
        previous = executor.invoke("contract", operation["name"], args, 1000).output
        _validate_json_schema(previous, operation["outputSchema"], "INVALID_OUTPUT")
        assert "NO_DEPLOYMENT_AUTHORITY" in previous["limitations"]


def test_resource_test_records_inventory_executor_without_claiming_model_execution():
    from agent_console.resource_automation_validation import executor_registry
    from agent_console.skill_mcp_repository import (
        InMemorySkillMcpRepository,
        ResourceScope,
    )
    from agent_console.skill_mcp_service import SkillMcpService
    from agent_console.skill_resource_testing import run

    service = SkillMcpService(InMemorySkillMcpRepository())
    scope = ResourceScope("test", "isolated")
    row = service.create(
        scope, "skill", "actor", "Document review", resource_content(SOURCE)["skill"]
    )
    result = run(
        service,
        scope,
        row["resourceId"],
        "actor",
        row["aggregateVersion"],
        operation="READ_DATA",
        name="Inventory",
        inputs={
            "schemaVersion": "document-review-input.v1",
            "synthetic": True,
            "sourceSnapshot": REFERENCE,
            "source": SOURCE,
            "dependencies": {},
        },
        expected_output={"source": SOURCE},
        comparison="subset",
        executor_registry=executor_registry(sales_v2_candidate=True),
    )["testResult"]
    assert result["status"] == "PASSED"
    assert result["executor"]["id"] == "document-inventory-readonly"
    assert (
        result["verificationContext"]["nativeDecisionValidation"]
        == "NOT_RUN_REQUIRES_NATIVE_ATTEMPT"
    )


def test_initial_inventory_is_only_metadata_and_does_not_satisfy_completion():
    library = NativeDocumentTools(SOURCE, REFERENCE)
    inventory = library.inventory()
    assert inventory == library.invoke("list_documents", {})
    assert inventory["sourceSnapshot"] == REFERENCE
    assert inventory["confirmedScope"] is None
    assert all(
        set(d) == {"id", "title", "role", "scope"} for d in inventory["documents"]
    )
    assert not library.verify({"observations": []}, {})["passed"]
