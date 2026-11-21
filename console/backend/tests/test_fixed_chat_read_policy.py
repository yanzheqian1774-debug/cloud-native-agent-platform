"""Private policy boundaries; no grants, database, or model operations."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from types import SimpleNamespace as N

import pytest
from agent_console.authority_contracts import AuthenticationSource
from agent_console.fixed_chat_read_policy import FixedChatReadPolicy
from agent_console.workbench_owner_authorization import WorkbenchOwnerError


def value():
    return dict(
        schemaVersion="fixed-chat-read-policy.v1",
        policyId="test",
        enabled=True,
        expiresAt=datetime.now(UTC) + timedelta(hours=26),
        grantTTLSeconds=3600,
        scopes=[
            dict(
                tenantId="t",
                securityDomain="d",
                subjectId="human:a",
                conversationId="chat",
                bindingDigest="a" * 64,
                work=dict(resource_id="work", revision_id="r", digest="b" * 64),
            )
        ],
    )


def context():
    return N(
        authentication_source=AuthenticationSource.BROWSER_SESSION,
        scope=N(tenant_id="t", security_domain="d"),
        principal_id="human:a",
    )


def test_policy_requires_exact_human_current_window(tmp_path):
    policy = FixedChatReadPolicy.model_validate(value())
    path = tmp_path / "policy.json"
    path.write_text(policy.model_dump_json())
    path.chmod(0o600)
    assert (
        FixedChatReadPolicy.load(path, sha256(path.read_bytes()).hexdigest()) == policy
    )
    assert (
        policy.require(context(), "chat", datetime.now(UTC)).bindingDigest == "a" * 64
    )
    for ctx, chat, now in [
        (context(), "other", datetime.now(UTC)),
        (context(), "chat", policy.expiresAt),
    ]:
        with pytest.raises(WorkbenchOwnerError):
            policy.require(ctx, chat, now)
    ctx = context()
    ctx.principal_id = "human:other"
    with pytest.raises(WorkbenchOwnerError):
        policy.require(ctx, "chat", datetime.now(UTC))
    ctx = context()
    ctx.authentication_source = AuthenticationSource.SERVICE_CREDENTIAL
    with pytest.raises(WorkbenchOwnerError):
        policy.require(ctx, "chat", datetime.now(UTC))


@pytest.mark.parametrize("mode", ["badpin", "symlink", "permissions", "duplicate"])
def test_policy_rejects_unpinned_or_ambiguous_files(tmp_path, mode):
    path = tmp_path / "policy.json"
    raw = FixedChatReadPolicy.model_validate(value()).model_dump_json()
    if mode == "duplicate":
        raw = raw.replace('"enabled":true', '"enabled":true,"enabled":true')
    path.write_text(raw)
    path.chmod(0o600)
    pin = sha256(path.read_bytes()).hexdigest()
    if mode == "badpin":
        pin = "0" * 64
    if mode == "permissions":
        path.chmod(0o644)
    if mode == "symlink":
        link = tmp_path / "link.json"
        link.symlink_to(path)
        path = link
    with pytest.raises(WorkbenchOwnerError, match="FIXED_CHAT_READ_POLICY_UNAVAILABLE"):
        FixedChatReadPolicy.load(path, pin)


def test_default_off_and_ttl_do_not_create_execution_scope():
    data = value()
    data.pop("enabled")
    policy = FixedChatReadPolicy.model_validate(data)
    with pytest.raises(WorkbenchOwnerError):
        policy.require(context(), "chat", datetime.now(UTC))
    data["grantTTLSeconds"] = 3601
    with pytest.raises(ValueError):
        FixedChatReadPolicy.model_validate(data)
