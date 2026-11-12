"""Source attachment boundaries; actual owner integration is tested separately."""

import json
from types import SimpleNamespace

import pytest
from agent_console import conversation_source_input as source
from agent_console.authority_contracts import AuthorityError
from agent_console.private_conversation import ConversationError


def setup(monkeypatch):
    ref = {
        "resource_id": "knowledge:test",
        "revision_id": "revision:test",
        "digest": "a" * 64,
    }
    original = {"synthetic": True, "text": "# 上线交接\n回退步骤待补充"}
    content = {"documents": [{"chunks": [{"content": json.dumps(original)}]}]}
    calls = []
    monkeypatch.setattr(
        source, "require_read", lambda *args: calls.append("authorized")
    )
    monkeypatch.setattr(
        source, "read_published", lambda *args: (content, "actual name")
    )
    monkeypatch.setattr(source, "source_digest", lambda content: "b" * 64)
    monkeypatch.setattr(
        source,
        "validate",
        lambda *args: {
            "sourceSchema": "document-review-source.v1",
            "sourceContentDigest": "b" * 64,
        },
    )
    ctx = SimpleNamespace(
        principal_id="human:test",
        scope=SimpleNamespace(tenant_id="t", security_domain="s"),
    )
    call = SimpleNamespace(context=ctx, authority=object(), connection=object())
    automation = SimpleNamespace(
        bound_app=lambda call: SimpleNamespace(scope=lambda p: "scope")
    )
    selected = {
        "source": ref,
        "sourceContentDigest": "b" * 64,
        "name": "forged",
        "originalContent": "forged",
    }
    return automation, call, selected, original, calls


def test_selected_reference_uses_server_read_content_not_journal_claims(monkeypatch):
    automation, call, selected, original, calls = setup(monkeypatch)
    result = json.loads(source.read_selected(automation, call, selected))
    assert result["originalContent"] == original
    assert result["name"] == "actual name"
    assert result["executionStatus"] == "NOT_EXECUTED"
    assert calls == ["authorized"]


def test_revoked_read_never_fetches_content(monkeypatch):
    automation, call, selected, _, _ = setup(monkeypatch)

    def denied(*args):
        raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    monkeypatch.setattr(source, "require_read", denied)
    monkeypatch.setattr(
        source, "read_published", lambda *args: pytest.fail("read after denial")
    )
    with pytest.raises(AuthorityError):
        source.read_selected(automation, call, selected)


def test_changed_source_commitment_is_rejected(monkeypatch):
    automation, call, selected, _, _ = setup(monkeypatch)
    selected["sourceContentDigest"] = "c" * 64
    with pytest.raises(ConversationError, match="STALE_OR_UNREADABLE"):
        source.read_selected(automation, call, selected)


def test_attachment_scope_resets_on_exception_and_nested_calls():
    assert source.current_attachment() is None
    with source.bind_attachment("first"):
        with pytest.raises(RuntimeError), source.bind_attachment("second"):
            assert source.current_attachment() == "second"
            raise RuntimeError
        assert source.current_attachment() == "first"
    assert source.current_attachment() is None
