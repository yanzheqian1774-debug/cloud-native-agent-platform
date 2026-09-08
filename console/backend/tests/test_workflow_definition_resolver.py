"""Focused fail-closed authoring checks; real protocol proof is separate."""

import copy

import pytest
from agent_console import workflow_definition_resolver as resolver
from agent_console.skill_mcp_repository import InMemorySkillMcpRepository
from agent_console.skill_mcp_service import SkillMcpService
from agent_console.workflow_definition_repository import (
    InMemoryWorkflowDefinitionRepository,
)
from agent_console.workflow_definition_service import (
    WorkflowDefinitionFailure,
    WorkflowDefinitionService,
)


def test_owner_scope_publication_and_exact_operation(monkeypatch):
    service = SkillMcpService(InMemorySkillMcpRepository())
    monkeypatch.setattr(resolver, "get_skill_mcp_service", lambda: service)
    scope = service.scope("293", "authoring")
    operation = {
        "name": "quality.read",
        "inputSchema": {},
        "outputSchema": {},
        "executorId": "readonly",
        "executorRevision": "1",
        "executorConfigurationDigest": "a" * 64,
        "sideEffectClass": "READ_ONLY",
        "sideEffectPolicy": {
            "policyId": "read",
            "policyRevision": "1",
            "policyDigest": "b" * 64,
        },
        "ioLimits": {
            "policyId": "limits",
            "policyRevision": "1",
            "maxInputBytes": 1024,
            "maxOutputBytes": 1024,
            "maxObjectDepth": 8,
            "maxProperties": 64,
            "timeoutMs": 1000,
        },
    }
    row = service.create(
        scope,
        "skill",
        "human",
        "Skill",
        {
            "description": "Read",
            "capabilities": ["read"],
            "instructions": "Read",
            "operations": [operation],
        },
    )
    ref = {
        "kind": "SKILL",
        "resourceId": row["resourceId"],
        "revisionId": row["revisions"][0]["revisionId"],
        "digest": row["revisions"][0]["digest"],
        "operation": "quality.read",
    }
    assert not resolver.resolve_workflow_reference(scope, ref)
    row = service.validate(
        scope, "skill", row["resourceId"], "human", row["aggregateVersion"]
    )["resource"]
    row = service.review(
        scope,
        "skill",
        row["resourceId"],
        "human",
        row["aggregateVersion"],
        ref["digest"],
        "APPROVE",
        "Review",
    )["resource"]
    service.publish(
        scope,
        "skill",
        row["resourceId"],
        "human",
        row["aggregateVersion"],
        ref["digest"],
        row["reviews"][0]["reviewId"],
    )
    assert resolver.resolve_workflow_reference(scope, ref)
    assert not resolver.resolve_workflow_reference(
        service.scope("other", "authoring"), ref
    )
    for key, value in (
        ("kind", "MCP"),
        ("revisionId", "missing"),
        ("digest", "0" * 64),
        ("operation", "missing"),
    ):
        assert not resolver.resolve_workflow_reference(scope, {**ref, key: value})
    # No name/capability fallback, and all duplicate matches must fail closed.
    original = service.repository.get(scope, "skill", row["resourceId"])
    for change in (
        "duplicate",
        "write",
        "missing-schema",
        "invalid-executor",
        "invalid-limits",
    ):
        malformed = copy.deepcopy(original)
        op = malformed["revisions"][0]["content"]["operations"][0]
        if change == "duplicate":
            malformed["revisions"][0]["content"]["operations"].append(copy.deepcopy(op))
        elif change == "write":
            op["sideEffectClass"] = "IDEMPOTENT_WRITE"
        elif change == "missing-schema":
            del op["inputSchema"]
        elif change == "invalid-executor":
            op["executorConfigurationDigest"] = "invalid"
        else:
            op["ioLimits"]["timeoutMs"] = 0
        monkeypatch.setattr(
            service.repository, "get", lambda *_args, record=malformed: record
        )
        assert not resolver.resolve_workflow_reference(scope, ref)


def test_validation_passes_binding_assertions_to_resolver():
    seen = []

    def resolve(_scope, reference):
        seen.append(reference)
        return "operation" not in reference

    service = WorkflowDefinitionService(InMemoryWorkflowDefinitionRepository(), resolve)
    scope = service.scope("293", "authoring")
    content = {
        "runtimeProfile": {
            "kind": "RUNTIME_PROFILE",
            "resourceId": "runtime",
            "revisionId": "1",
        },
        "tasks": [
            {
                "taskId": "read",
                "references": [
                    {"kind": "SKILL", "resourceId": "skill", "revisionId": "1"}
                ],
                "skillOperationBindings": [
                    {
                        "skillId": "skill",
                        "skillRevisionId": "1",
                        "skillDigest": "a" * 64,
                        "operation": "read",
                    }
                ],
            }
        ],
    }
    row = service.create(scope, "human", "Workflow", content)
    with pytest.raises(WorkflowDefinitionFailure, match="EXACT_REFERENCE_NOT_FOUND"):
        service.validate(
            scope, row["workflowDefinitionId"], "human", row["aggregateVersion"]
        )
    assert seen[-1] == {
        "kind": "SKILL",
        "resourceId": "skill",
        "revisionId": "1",
        "digest": "a" * 64,
        "operation": "read",
    }
