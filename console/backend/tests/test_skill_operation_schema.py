"""Strict API adaptation of the existing READ_ONLY operation record."""

import copy

import pytest
from agent_console.skill_mcp_api import resource_content
from agent_console.skill_mcp_schemas import (
    CreateResource,
    EditResource,
    ResourceContent,
)
from fastapi import HTTPException
from pydantic import ValidationError


def content():
    return {
        "description": "Read quality",
        "capabilities": ["quality.read"],
        "instructions": "Summarize supplied facts",
        "operations": [
            {
                "name": "quality.read",
                "inputSchema": {},
                "outputSchema": {},
                "sideEffectClass": "READ_ONLY",
                "executorId": "readonly",
                "executorRevision": "1",
                "executorConfigurationDigest": "a" * 64,
                "sideEffectPolicy": {
                    "policyId": "readonly",
                    "policyRevision": "1",
                    "policyDigest": "b" * 64,
                },
                "ioLimits": {
                    "policyId": "bounded",
                    "policyRevision": "1",
                    "maxInputBytes": 1024,
                    "maxOutputBytes": 1024,
                    "maxObjectDepth": 8,
                    "maxProperties": 64,
                    "timeoutMs": 1000,
                },
            }
        ],
    }


def test_operation_identity_roundtrip_and_strict_contract():
    original = content()
    parsed = CreateResource(name="Skill", content=original)
    assert (
        resource_content("skill", parsed.content)["operations"]
        == original["operations"]
    )
    variants = []
    for field, value in (
        ("name", ""),
        ("sideEffectClass", "IDEMPOTENT_WRITE"),
        ("executorConfigurationDigest", "invalid"),
        ("inputSchema", []),
        ("extra", "ignored?"),
        ("sideEffectPolicy", {}),
        ("ioLimits", {}),
    ):
        bad = copy.deepcopy(original)
        bad["operations"][0][field] = value
        variants.append(bad)
    for timeout in (0, True, "1000"):
        bad = copy.deepcopy(original)
        bad["operations"][0]["ioLimits"]["timeoutMs"] = timeout
        variants.append(bad)
    bad = copy.deepcopy(original)
    bad["operations"].append(copy.deepcopy(bad["operations"][0]))
    variants.extend((bad, {**original, "unexpected": True}))
    for bad in variants:
        with pytest.raises(ValidationError):
            CreateResource(name="Skill", content=bad)
    with pytest.raises(ValidationError):
        EditResource(expectedVersion=1, content=original, unexpected=True)
    with pytest.raises(HTTPException, match="SKILL_OPERATIONS_ONLY"):
        resource_content("mcp", parsed.content)


def test_absent_null_empty_and_legacy_content_are_distinct():
    legacy = content()
    del legacy["operations"]
    parsed = ResourceContent(**legacy)
    assert "operations" not in resource_content("skill", parsed)
    assert "operations" not in resource_content("mcp", parsed)
    for value in (None, [], {}, "quality.read"):
        with pytest.raises(ValidationError):
            ResourceContent(**legacy, operations=value)
