"""Pure policy boundaries; no protocol call or grant is authorized by these checks."""

from datetime import UTC, datetime, timedelta

import pytest
from agent_console.authority_configuration import validate_registered_grant
from agent_console.authority_contracts import AuthorityError, ExactGrant
from agent_console.mcp_tool_test_policy import ToolBinding, ToolTestPolicy
from agent_console.skill_resource_testing import schema_check


def binding():
    return ToolBinding(
        namespace="n",
        securityDomain="d",
        subject="human:owner",
        mcp={"resource_id": "mcp:m", "revision_id": "mcp:r", "digest": "a" * 64},
        source={
            "resource_id": "knowledge:k",
            "revision_id": "knowledge:r",
            "digest": "b" * 64,
        },
        sourceContentDigest="c" * 64,
        endpoint="http://127.0.0.1:12345/mcp",
        selectionId="selection:one",
        snapshotId="snapshot:one",
        snapshotDigest="d" * 64,
        toolName="read_source",
        inputSchema={
            "type": "object",
            "properties": {"sourceDigest": {"type": "string"}},
            "required": ["sourceDigest"],
            "additionalProperties": False,
        },
        arguments={"sourceDigest": "c" * 64},
        sideEffect="READ",
        expiresAt=datetime.now(UTC) + timedelta(minutes=5),
    )


def test_lease_extension_does_not_make_unknown_tuple_new():
    b = binding()
    assert (
        b.model_copy(update={"expiresAt": b.expiresAt + timedelta(hours=1)}).digest
        == b.digest
    )
    assert (
        b.model_copy(update={"arguments": {"sourceDigest": "e" * 64}}).digest
        != b.digest
    )
    validate_registered_grant(b.grant, allow_meta=False)
    with pytest.raises(AuthorityError):
        validate_registered_grant(
            ExactGrant("SKILL", "INVOKE_MCP_TOOL", "unknown:scope"), allow_meta=False
        )


def test_policy_file_and_schema_fail_closed(tmp_path):
    b = binding()
    p = ToolTestPolicy(
        schemaVersion="mcp-published-tool-test.v1",
        enabled=False,
        policyId="p",
        policyVersion="1",
        issuer="service:issuer",
        credentialPath=tmp_path / "secret",
        bindings=(b,),
    )
    file = tmp_path / "policy.json"
    file.write_text(p.model_dump_json())
    file.chmod(0o644)
    with pytest.raises(AuthorityError):
        ToolTestPolicy.load(file)
    file.chmod(0o600)
    assert not ToolTestPolicy.load(file).enabled
    link = tmp_path / "link"
    link.symlink_to(file)
    with pytest.raises(AuthorityError):
        ToolTestPolicy.load(link)
    schema_check(b.arguments, b.inputSchema, "INPUT_INVALID")
    with pytest.raises(ValueError):
        schema_check(
            {"sourceDigest": "c" * 64, "write": True}, b.inputSchema, "INPUT_INVALID"
        )
    with pytest.raises(ValueError):
        schema_check(b.arguments, {"type": "object", "oneOf": [{}]}, "INPUT_INVALID")
