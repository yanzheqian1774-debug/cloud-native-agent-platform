from copy import deepcopy

import pytest
from agent_console.native_definition_query_tools import NativeDefinitionQueryTools
from agent_console.native_document_resource_bundle import resource_content
from agent_console.native_document_rule_tools import NativeDocumentRuleTools
from agent_console.native_document_skill import (
    NativeDefinitionQuerySkillExecutor,
    NativeRuleDocumentSkillExecutor,
    document_executor_revision,
)
from test_document_rule_owner import SOURCE, rules


def library(kind=NativeDefinitionQueryTools):
    content = rules().model_dump(mode="json")
    binding = {
        "schema_version": "document-semantics-binding.v1",
        "ontology": {
            "resource_id": "document-rules",
            "revision_id": "published-r1",
            "digest": "b" * 64,
        },
        "mapping_code": "interview",
        "source": content["mappings"][0]["source"],
        "scope": "interview",
    }
    return kind(deepcopy(SOURCE), binding["source"], content, binding)


def test_query_exact_definitions_is_distinct_from_evaluating_rules():
    tool = library()
    before = tool.reviewed
    result = tool.invoke("query_rule_definition", {"ruleCode": "reviewer"})
    assert result["state"] == "FOUND"
    assert result["ruleBinding"]["ontology"]["revision_id"] == "published-r1"
    assert result["rules"][0]["field"] == "Reviewer"
    assert result["sources"][0]["source"] == tool.binding.source.model_dump(mode="json")
    assert result["rulesEvaluated"] is False and result["authorizationGranted"] is False
    assert tool.reviewed is before is None
    assert (
        tool.invoke("query_rule_definition", {"ruleCode": "missing"})["state"]
        == "UNKNOWN"
    )
    assert len(tool.invoke("query_rule_definition", {"ruleCode": ""})["rules"]) == 4
    assert all(set(r) == {"code", "name"} for r in tool.inventory()["rules"])


def test_query_is_optional_and_legacy_inventory_unchanged():
    old = library(NativeDocumentRuleTools)
    assert "kind" in old.inventory()["rules"][0]
    assert "query_rule_definition" not in {t.name for t in old.tools}
    new = library()
    new.confirmed_scope = "interview"
    outcome = new.invoke(
        "review_document", {"documentId": "interview", "policyId": "policy"}
    )
    assert outcome["ruleResult"]["findings"]
    assert new.reviewed is not None


@pytest.mark.parametrize(
    "args",
    [
        {},
        {"ruleCode": 1},
        {"ruleCode": "x" * 65},
        {"ruleCode": "owner", "revision": "other"},
    ],
)
def test_query_cannot_select_another_version_or_inject_arguments(args):
    with pytest.raises(ValueError):
        library().invoke("query_rule_definition", args)


def test_successor_bundle_is_explicit_and_preserves_revision_four():
    old = resource_content(SOURCE, rule_bound=True)["skill"]
    new = resource_content(SOURCE, rule_bound=True, definition_query=True)["skill"]
    assert old["operations"][0]["executorRevision"] == "4"
    assert new["operations"][0]["executorRevision"] == "5"
    assert (
        document_executor_revision(old["operations"])
        == NativeRuleDocumentSkillExecutor.revision
    )
    assert (
        document_executor_revision(new["operations"])
        == NativeDefinitionQuerySkillExecutor.revision
    )
    with pytest.raises(ValueError, match="BINDING_REQUIRED"):
        resource_content(SOURCE, definition_query=True)
