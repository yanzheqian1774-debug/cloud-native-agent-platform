# ruff: noqa: F401,F811,RUF001 -- Isolated fixture composition and Chinese instructions.
"""Original user intent, never model output or a fabricated native answer."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from agent_console.execution_preparation import ExactReference
from agent_console.native_confirmed_scope import classify_scope, read_confirmed_scope
from agent_console.native_document_tools import NativeDocumentTools
from test_native_document_tools import SOURCE
from test_private_conversation import ctx, database, service


@pytest.mark.parametrize(
    "text,expected",
    [
        (
            "帮我按生产环境规范检查订单服务上线交接说明，只检查，不执行上线。",
            "生产环境",
        ),
        ("请按测试环境规范检查。", "测试环境"),
        ("帮我按生产环境规范检查一下？", "生产环境"),
        ("请按生产环境规范检查，不要上线。", "生产环境"),
        ("请按生产环境规范检查；不要再使用生产环境规范。", None),
        ("“按生产环境规范检查”是文档中的原话", None),
        ("按生产环境规范检查；按测试环境规范检查", None),
        ("不要按生产环境规范检查", None),
        ("请按生产环境规范还是测试环境规范检查？", None),
        ("文档写着按生产环境规范检查", None),
        ("请按“生产环境规范”检查", "生产环境"),
        ("请按生产环境甲规范检查", None),
        ("可能按生产环境规范检查", None),
        ("帮我看看哪里缺内容", None),
    ],
)
def test_scope_requires_unambiguous_direct_instruction(text, expected):
    value = classify_scope(
        [{"message_id": "m1", "content": text}], ["生产环境", "测试环境"]
    )
    assert (value["scope"] if value else None) == expected


def test_original_confirmation_survives_generic_source_selection_but_not_conflict():
    messages = [
        {"message_id": "original", "content": "帮我按生产环境规范检查。"},
        {"message_id": "source", "content": "使用系统资料；范围不明确时请追问。"},
    ]
    assert classify_scope(messages, ["生产环境", "测试环境"]) == {
        "scope": "生产环境",
        "messageIds": ["original"],
    }
    messages.append({"message_id": "change", "content": "请按测试环境规范检查。"})
    assert classify_scope(messages, ["生产环境", "测试环境"]) is None
    assert (
        classify_scope(
            [{"message_id": "english", "content": "Please use production policy."}],
            ["production", "test"],
        )["scope"]
        == "production"
    )


def linked(service, actor, question):
    identity = service.create(
        actor, {"idempotencyKey": str(uuid4()), "title": "Scope"}
    )["conversation_id"]
    service.mutate(
        actor,
        identity,
        {"idempotencyKey": "question", "expectedVersion": 0, "content": question},
        "message",
    )
    target = {
        "problemId": "allowed",
        "revisionId": "allowed:1",
        "problemDigest": "a" * 64,
    }
    service.mutate(
        actor,
        identity,
        {"idempotencyKey": "link", "expectedVersion": 1, "target": target},
        "link",
    )
    return identity


@pytest.mark.parametrize(
    "variant",
    ["exact", "subject", "tenant", "revision", "digest", "duplicate", "later-message"],
)
def test_original_owner_and_exact_problem_lineage(service, variant):
    actor = ctx("scope-" + uuid4().hex)
    identity = linked(service, actor, "帮我按生产环境规范检查。")
    ref = ExactReference(
        resource_id="allowed", revision_id="allowed:1", digest="a" * 64
    )
    p = SimpleNamespace(
        namespace="tenant",
        security_domain="domain",
        semantics=SimpleNamespace(target=SimpleNamespace(problem=ref)),
    )
    principal = actor.principal_id
    if variant == "subject":
        principal = "other"
    if variant == "tenant":
        p.namespace = "other"
    if variant == "revision":
        p.semantics.target.problem = ref.model_copy(update={"revision_id": "allowed:2"})
    if variant == "digest":
        p.semantics.target.problem = ref.model_copy(update={"digest": "b" * 64})
    if variant == "duplicate":
        linked(service, actor, "请按测试环境规范检查。")
    if variant == "later-message":
        service.mutate(
            actor,
            identity,
            {
                "idempotencyKey": "later",
                "expectedVersion": 2,
                "content": "请按测试环境规范检查。",
            },
            "message",
        )
    with service.connect() as connection:
        value = read_confirmed_scope(connection, p, principal, ["生产环境", "测试环境"])
    if variant not in {"exact", "later-message"}:
        assert value is None
    else:
        assert value["conversationId"] == identity
        assert value["scope"] == "生产环境"
        assert len(value["messages"]) == 1
        assert value["authority"] == "USER_SCOPE_CONTEXT_ONLY_NOT_PERMISSION"


def test_scope_projection_does_not_modify_source_or_invent_answers():
    tools = NativeDocumentTools(SOURCE, {"digest": "a" * 64})
    original = tools.source.copy()
    scope = next(d["scope"] for d in SOURCE["documents"] if d["role"] == "POLICY")
    tools.apply_confirmed_scope({"scope": scope})
    assert tools.inventory()["confirmedScope"] == scope
    assert tools.source == original
    tools.apply_confirmed_scope(None)
    assert tools.inventory()["confirmedScope"] is None
    with pytest.raises(ValueError, match="UNAVAILABLE"):
        tools.apply_confirmed_scope({"scope": "not-present"})


def test_scope_executor_is_explicit_and_preserves_old_bundles():
    from agent_console.native_document_resource_bundle import resource_content
    from agent_console.native_document_skill import (
        NativeDocumentSkillExecutor,
        NativeEmployeeDocumentSkillExecutor,
        NativeUserScopeDocumentSkillExecutor,
        document_executor_revision,
    )
    from agent_console.resource_automation_validation import executor_registry

    for options, expected in [
        ({}, NativeDocumentSkillExecutor),
        ({"bound_employee": True}, NativeEmployeeDocumentSkillExecutor),
        ({"confirmed_user_scope": True}, NativeUserScopeDocumentSkillExecutor),
    ]:
        bundle = resource_content(SOURCE, **options)
        assert (
            document_executor_revision(bundle["skill"]["operations"])
            == expected.revision
        )
        assert (
            executor_registry().resolve(expected.revision).revision == expected.revision
        )


def test_original_message_change_invalidates_captured_scope_evidence(service):
    actor = ctx("scope-change-" + uuid4().hex)
    identity = linked(service, actor, "请按生产环境规范检查。")
    ref = ExactReference(
        resource_id="allowed", revision_id="allowed:1", digest="a" * 64
    )
    p = SimpleNamespace(
        namespace="tenant",
        security_domain="domain",
        semantics=SimpleNamespace(target=SimpleNamespace(problem=ref)),
    )
    with service.connect() as connection:
        before = read_confirmed_scope(
            connection, p, actor.principal_id, ["生产环境", "测试环境"]
        )
        # Isolated corruption fixture: no production message mutation route exists.
        connection.execute(
            "UPDATE private_conversation.messages SET content=%s "
            "WHERE conversation_id=%s",
            ("请按测试环境规范检查。", identity),
        )
        after = read_confirmed_scope(
            connection, p, actor.principal_id, ["生产环境", "测试环境"]
        )
    assert before["scope"] == "生产环境"
    assert after["scope"] == "测试环境"
    assert before["messages"] != after["messages"]
    assert after != before  # Runtime supervisor requires exact captured equality.


def scoped_history(service, actor, current_messages, *, history_count=1):
    identity = service.create(
        actor, {"idempotencyKey": str(uuid4()), "title": "Separate problem scopes"}
    )["conversation_id"]
    version = 0
    first = None
    for text in [
        "先确认是测试环境还是生产环境再检查。"
    ] * history_count + current_messages:
        reply = service.mutate(
            actor,
            identity,
            {
                "idempotencyKey": str(uuid4()),
                "expectedVersion": version,
                "content": text,
            },
            "message",
        )
        if version == history_count:
            first = reply["identity"]
        version += 1
    service.mutate(
        actor,
        identity,
        {
            "idempotencyKey": "link",
            "expectedVersion": version,
            "target": {
                "problemId": "allowed",
                "revisionId": "allowed:1",
                "problemDigest": "a" * 64,
            },
        },
        "link",
    )
    p = SimpleNamespace(
        namespace="tenant",
        security_domain="domain",
        semantics=SimpleNamespace(
            target=SimpleNamespace(
                problem=ExactReference(
                    resource_id="allowed", revision_id="allowed:1", digest="a" * 64
                )
            )
        ),
    )
    return identity, first, p


def lineage_projection(c, identity, first, principal, *, variant):
    """Minimal isolated owner projections; no live admission or permission writes."""
    from psycopg.types.json import Jsonb

    c.execute("CREATE SCHEMA IF NOT EXISTS authorization_admin")
    c.execute("CREATE SCHEMA IF NOT EXISTS draft_assistance")
    c.execute(
        "CREATE TABLE IF NOT EXISTS authorization_admin.context_call_objects "
        "(tenant_id text,security_domain text,owner text,resource_id text,"
        "context_id text,invocation_id text)"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS authorization_admin.context_call_requests "
        "(context_id text,tenant_id text,security_domain "
        "text,subject_id text,record jsonb)"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS draft_assistance.invocation_versions "
        "(namespace text,security_domain text,invocation_id "
        "text,aggregate_version int,record jsonb)"
    )
    context = "context:" + uuid4().hex
    invocation = "invocation:" + uuid4().hex
    record = {
        "context_id": context,
        "subject_id": principal,
        "conversation_id": "other-conversation"
        if variant == "other-conversation"
        else identity,
        "first_user_message_id": "missing" if variant == "missing-first" else first,
    }
    value = {
        "state": "FAILED" if variant == "failed-invocation" else "SUCCEEDED",
        "resultKind": "DRAFT_READY",
        "contextId": "other" if variant == "wrong-context" else context,
        "initiatingPrincipalId": "other" if variant == "other-subject" else principal,
        "problemId": "allowed",
        "problemRevisionId": "allowed:2"
        if variant == "wrong-problem-revision"
        else "allowed:1",
        "problemDigest": "b" * 64 if variant == "wrong-problem-digest" else "a" * 64,
    }
    c.execute(
        "INSERT INTO authorization_admin.context_call_objects VALUES "
        "('tenant','domain','BUSINESS_PROBLEM','allowed',%s,%s)",
        (context, invocation),
    )
    c.execute(
        "INSERT INTO authorization_admin.context_call_requests VALUES "
        "(%s,'tenant','domain',%s,%s)",
        (context, principal, Jsonb(record)),
    )
    c.execute(
        "INSERT INTO draft_assistance.invocation_versions VALUES "
        "('tenant','domain',%s,1,%s)",
        (invocation, Jsonb(value)),
    )
    return context, invocation


@pytest.mark.parametrize(
    "variant",
    [
        "historical-ambiguity",
        "many-historical-messages",
        "current-reversal",
        "current-uncertain",
        "other-conversation",
        "other-subject",
        "wrong-context",
        "missing-first",
        "failed-invocation",
        "wrong-problem-revision",
        "wrong-problem-digest",
        "current-over-limit",
        "current-too-long",
    ],
)
def test_current_problem_scope_uses_immutable_context_boundary(service, variant):
    actor = ctx("current-scope-" + uuid4().hex)
    current = ["请按生产环境规范检查。", "使用系统现有交接资料，保持只读。"]
    if variant == "current-reversal":
        current += ["请按测试环境规范检查。"]
    if variant == "current-uncertain":
        current += ["不确定是否应按生产环境规范。"]
    if variant == "current-over-limit":
        current += ["补充资料说明。"] * 31
    if variant == "current-too-long":
        current += ["合成补充说明。" * 500] * 10
    identity, first, p = scoped_history(
        service,
        actor,
        current,
        history_count=35 if variant == "many-historical-messages" else 1,
    )
    with service.connect() as c:
        context, invocation = lineage_projection(
            c, identity, first, actor.principal_id, variant=variant
        )
        try:
            before = c.execute(
                "SELECT count(*) n FROM private_conversation.messages "
                "WHERE conversation_id=%s",
                (identity,),
            ).fetchone()["n"]
            value = read_confirmed_scope(
                c, p, actor.principal_id, ["生产环境", "测试环境"]
            )
            after = c.execute(
                "SELECT count(*) n FROM private_conversation.messages "
                "WHERE conversation_id=%s",
                (identity,),
            ).fetchone()["n"]
            assert (
                before
                == after
                == len(current) + (35 if variant == "many-historical-messages" else 1)
            )
            if variant not in {"historical-ambiguity", "many-historical-messages"}:
                assert value is None
            else:
                assert value["scope"] == "生产环境"
                assert value["conversationId"] == identity
                assert len(value["messages"]) == 2
                assert value["affirmativeMessageIds"] == [first]
        finally:
            c.execute(
                "DELETE FROM authorization_admin.context_call_objects "
                "WHERE context_id=%s",
                (context,),
            )
            c.execute(
                "DELETE FROM "
                "authorization_admin.context_call_requests WHERE context_id=%s",
                (context,),
            )
            c.execute(
                "DELETE FROM draft_assistance.invocation_versions "
                "WHERE invocation_id=%s",
                (invocation,),
            )


def test_unbound_legacy_multi_message_history_does_not_invent_a_context(service):
    actor = ctx("legacy-multi-" + uuid4().hex)
    _, _, p = scoped_history(service, actor, ["请按生产环境规范检查。"])
    with service.connect() as c:
        assert (
            read_confirmed_scope(c, p, actor.principal_id, ["生产环境", "测试环境"])
            is None
        )
