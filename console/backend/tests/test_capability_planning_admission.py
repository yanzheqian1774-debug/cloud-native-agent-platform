"""Fixed source provenance rejects absent, ambiguous, changed and revoked inputs."""

from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.capability_planning_admission import source_reader
from agent_console.capability_work_input import work_input
from agent_console.private_conversation import ConversationError
from test_capability_execution_constraints import fixture


@pytest.mark.parametrize(
    "mode", ["exact", "missing", "ambiguous", "revoked", "criteria", "target"]
)
def test_current_fixed_source_is_revalidated_on_same_connection(mode):
    resolved, _, current, _ = fixture()
    resolved["contract"].update(conversationId="conversation", sourceMessageId="source")
    current["criteria"][0]["applicability"] = work_input(resolved)["criterion"][
        "applicability"
    ]
    target = current["target"]
    request = SimpleNamespace(
        target=SimpleNamespace(
            problem=SimpleNamespace(model_dump=lambda **kw: target["problem"]),
            model_dump=lambda **kw: target,
        )
    )

    class Connection:
        def execute(self, sql, params):
            if "SELECT conversation_id,message_id" in sql:
                assert params[:3] == ("tenant", "domain", "actor")
                assert "confirmed_by=%s" in sql and "claimed_at IS NOT NULL" in sql
                rows = (
                    []
                    if mode == "missing"
                    else [{"conversation_id": "conversation", "message_id": "source"}]
                )
                if mode == "ambiguous":
                    rows *= 2
            else:
                assert "SELECT intent_id" in sql
                rows = [{"intent_id": "intent"}]
            return SimpleNamespace(fetchall=lambda: rows)

    connection = Connection()
    context = SimpleNamespace(
        principal_id="actor",
        scope=SimpleNamespace(tenant_id="tenant", security_domain="domain"),
    )
    authorizer = SimpleNamespace(
        controller=SimpleNamespace(
            protected_request=lambda: nullcontext(SimpleNamespace(generation=18)),
            readiness=SimpleNamespace(recovery_epoch=1),
        )
    )
    calls = []

    def read(call, conversation, message):
        assert call.connection is connection and call.context is context
        assert (conversation, message) == ("conversation", "source")
        calls.append(call)
        if mode == "revoked":
            raise ConversationError("CAPABILITY_NOT_FOUND", 404)
        return resolved

    def current_input(*args):
        if mode == "criteria":
            current["criteria"][0]["measurement"] = {"rubric": "changed"}
        if mode == "target":
            return {**current, "target": {**target, "expected_problem_version": 999}}
        return current

    automation = SimpleNamespace(
        bound_app=lambda call: SimpleNamespace(current_input=current_input)
    )
    read_source = source_reader(automation, read, authorizer)
    if mode in {"ambiguous", "revoked", "criteria", "target"}:
        with pytest.raises(AuthorityError, match="DEVELOPMENT_CAPABILITY_"):
            read_source(context, connection, request)
    elif mode == "missing":
        assert read_source(context, connection, request) is None
        assert not calls
    else:
        proof = read_source(context, connection, request)
        assert proof["contractDigest"] == resolved["contractDigest"]
        assert proof["problem"] == target["problem"]
        assert len(calls) == 1
