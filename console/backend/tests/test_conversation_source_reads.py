import hashlib
import json
from types import SimpleNamespace as NS

import pytest
from agent_console import conversation_sources as module
from agent_console import planning_candidates
from agent_console.authority_contracts import AuthorityError
from agent_console.plan_suggestion_domain import ExactReference
from test_native_document_tools import SOURCE


@pytest.fixture
def readable_source(monkeypatch):
    raw = json.dumps(SOURCE)
    content = {
        "documents": [
            {
                "contentDigest": hashlib.sha256(raw.encode()).hexdigest(),
                "chunks": [{"content": raw}],
            }
        ]
    }
    calls, loaded = [], []
    allowed = set()
    principal = NS(
        principal_id="human:ordinary",
        scope=NS(tenant_id="tenant", security_domain="domain"),
    )

    def require(p, owner, action, target):
        calls.append((p.principal_id, owner, action, target))
        if p.principal_id not in allowed:
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    call = NS(context=principal, connection=object(), authority=NS(require=require))

    def identities(connection, scope, kind):
        assert connection is call.connection
        assert (scope.namespace, scope.security_domain, kind) == (
            "tenant",
            "domain",
            "KNOWLEDGE",
        )
        return [{"identity": "knowledge:docs", "revision": "1", "digest": "a" * 64}]

    def read(connection, scope, kind, ref):
        assert connection is call.connection
        assert (scope.namespace, scope.security_domain, kind) == (
            "tenant",
            "domain",
            "KNOWLEDGE",
        )
        assert ref.resource_id == "knowledge:docs"
        loaded.append(ref)
        return content, "Readable document"

    def no_execution_policy(*args, **kwargs):
        assert kwargs["connection"] is call.connection
        raise AuthorityError("RESOURCE_WORK_SCOPE_UNAVAILABLE")

    app = NS(
        scope=lambda p: NS(namespace=p.tenant_id, security_domain=p.security_domain)
    )
    automation = NS(
        bound_app=lambda c: app,
        work=no_execution_policy,
        grants=NS(clock=lambda: None),
        services=None,
    )
    monkeypatch.setattr(module, "identities", identities)
    monkeypatch.setattr(planning_candidates, "read_published", read)
    return NS(
        automation=automation,
        call=call,
        allowed=allowed,
        loaded=loaded,
        calls=calls,
        content=content,
        read=read,
    )


def test_ordinary_reader_discovers_without_execution_scope_and_revocation_hides_content(
    readable_source,
):
    f = readable_source
    assert module.sources(f.automation, f.call) == []
    assert f.loaded == []
    f.allowed.add("human:ordinary")
    result = module.ConversationSources(f.automation)(f.call)
    assert result["executionStarted"] is False
    assert [s["name"] for s in result["items"]] == ["Readable document"]
    assert result["items"][0]["assessment"]["executionReady"] is False
    assert f.calls[-1][1:3] == ("KNOWLEDGE", "READ_RESOURCE")
    before = len(f.loaded)
    f.allowed.clear()
    assert module.sources(f.automation, f.call) == []
    assert len(f.loaded) == before


def test_named_task_still_requires_existing_work_scope(readable_source):
    f = readable_source
    f.allowed.add("human:ordinary")
    with pytest.raises(AuthorityError, match="RESOURCE_WORK_SCOPE_UNAVAILABLE"):
        module.sources(
            f.automation,
            f.call,
            ExactReference(resource_id="problem", revision_id="1", digest="a" * 64),
        )
    assert not f.loaded


def test_corrupt_authorized_content_is_not_offered(readable_source):
    f = readable_source
    f.allowed.add("human:ordinary")
    f.content["documents"][0]["contentDigest"] = "0" * 64
    assert module.sources(f.automation, f.call) == []


def test_understanding_reads_same_document_payload_and_current_exact_permission(
    readable_source, monkeypatch
):
    from agent_console import conversation_source_input
    from agent_console.resource_automation_policy import source_digest
    from test_native_document_tools import SOURCE

    f = readable_source
    monkeypatch.setattr(conversation_source_input, "read_published", f.read)
    selected = {
        "source": {
            "resource_id": "knowledge:docs",
            "revision_id": "1",
            "digest": "a" * 64,
        },
        "sourceContentDigest": source_digest(f.content),
    }
    with pytest.raises(AuthorityError):
        conversation_source_input.read_selected(f.automation, f.call, selected)
    assert f.loaded == []
    f.allowed.add("human:ordinary")
    data = json.loads(
        conversation_source_input.read_selected(f.automation, f.call, selected)
    )
    assert data["originalContent"] == SOURCE
    assert data["source"] == selected["source"]
    assert data["sourceContentDigest"] == selected["sourceContentDigest"]
    assert f.calls[-1][1:3] == ("KNOWLEDGE", "READ_RESOURCE")
    f.allowed.clear()
    with pytest.raises(AuthorityError):
        conversation_source_input.read_selected(f.automation, f.call, selected)
    assert len(f.loaded) == 1


def test_owned_catalogue_separates_current_source_scope_from_read_and_execution(
    readable_source,
):
    f = readable_source
    f.allowed.add("human:ordinary")
    f.call.operation = "READ_OWNED_CONVERSATION_SOURCES"
    checked = []

    def policy(c, ctx):
        assert c is f.call.connection and ctx is f.call.context

    def selected(metadata, content):
        checked.append(metadata)
        assert content is f.content

    f.automation.owned_business = NS(
        _policy=policy, policy=NS(validate_source=selected)
    )
    item = module.sources(f.automation, f.call)[0]
    assert item["name"] == "Readable document"
    assert item["businessEligibility"] == {
        "state": "SOURCE_SCOPE_MATCHED",
        "executionReady": False,
    }
    assert checked[0]["source"] == item["source"]

    def denied(*args):
        raise AuthorityError("OWNED_BUSINESS_SOURCE_NOT_AUTHORIZED")

    f.automation.owned_business.policy.validate_source = denied
    assert (
        module.sources(f.automation, f.call)[0]["businessEligibility"]["state"]
        == "READ_ONLY"
    )

    def expired(*args):
        raise AuthorityError("OWNED_BUSINESS_EXPIRED")

    f.automation.owned_business._policy = expired
    assert (
        module.sources(f.automation, f.call)[0]["businessEligibility"]["state"]
        == "UNVERIFIED"
    )
    f.allowed.clear()
    assert module.sources(f.automation, f.call) == []
