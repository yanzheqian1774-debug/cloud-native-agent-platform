from types import SimpleNamespace as N

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.conversation_answer_retention import require_fixed_basis
from agent_console.digital_employee_definition import digest
from agent_console.fixed_chat_focus import FocusCommand, read_basis
from agent_console.private_conversation import ConversationError


def test_retained_legacy_is_unchanged_but_missing_fixed_reader_is_not_public():
    require_fixed_basis(N(), None, "chat", {})
    with pytest.raises(ConversationError, match="CONVERSATION_SOURCE_UNAVAILABLE"):
        require_fixed_basis(
            N(), None, "chat", {"fixedCycleFocus": {"focusDigest": "a" * 64}}
        )


def test_retained_denial_is_not_absence():
    def denied(*args):
        raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
        require_fixed_basis(
            N(fixed_focus_read=denied), None, "chat", {"fixedCycleFocus": {}}
        )


def test_focus_input_forbids_client_content_and_unknown_proof():
    from pydantic import ValidationError

    value = dict(
        bindingDigest="a" * 64,
        workDigest="b" * 64,
        eventId="event",
        receiptDigest="c" * 64,
        preparationDigest="d" * 64,
        runId="run",
        expectedConversationVersion=1,
        commandId="key",
    )
    assert FocusCommand.model_validate(value)
    with pytest.raises(ValidationError):
        FocusCommand.model_validate({**value, "proof": {}, "content": "client result"})


def test_read_excerpt_is_explicit_and_checks_permissions_before_body(monkeypatch):
    import agent_console.fixed_chat_focus as module

    p = N(namespace="n", security_domain="s", run_id="run")
    monkeypatch.setattr(module, "checked", lambda *args: (None, None, None, p))
    from hashlib import sha256

    text = "x" * 3000
    artifact_digest = sha256(text.encode()).hexdigest()
    basis = dict(
        schemaVersion="fixed-cycle-focus.v1",
        conversationId="chat",
        identity={},
        grants=[
            dict(owner="EVIDENCE", action="READ_REFERENCE", exactResource="evidence:1")
        ],
        artifacts=[dict(artifactId="a", digest=artifact_digest)],
        observation={},
    )
    basis["focusDigest"] = digest(basis)
    calls = []

    def require(*args):
        calls.append("read")

    def execute(*args):
        assert calls and calls[-1] == "read"
        record = dict(
            artifact_id="a",
            task_id="task",
            attempt_id="attempt",
            kind="report",
            schema_version="v1",
            digest=artifact_digest,
            content=text,
        )
        return N(
            fetchone=lambda: {
                **{
                    k: record[k]
                    for k in (
                        "artifact_id",
                        "task_id",
                        "attempt_id",
                        "digest",
                        "content",
                    )
                },
                "record": record,
            }
        )

    ctx = N(principal_id="human:a", scope=N(tenant_id="n", security_domain="s"))
    call = N(context=ctx, authority=N(require=require), connection=N(execute=execute))
    _, result = read_basis(call, None, "chat", {"fixedCycleFocus": basis})
    assert result["contentComplete"] is False
    assert result["outputs"][0]["complete"] is False
    assert result["outputs"][0]["totalCharacters"] == 3000
    assert len(result["outputs"][0]["textExcerpt"]) == 2000

    def corrupt(*args):
        result = execute(*args).fetchone()
        result["content"] = "tampered content with unchanged digest and record"
        return N(fetchone=lambda: result)

    call.connection = N(execute=corrupt)
    from agent_console.workbench_owner_authorization import WorkbenchOwnerError

    with pytest.raises(WorkbenchOwnerError, match="FIXED_CHAT_FACT_BINDING_INVALID"):
        read_basis(call, None, "chat", {"fixedCycleFocus": basis})
    call.connection = N(execute=execute)
    bad = {**basis, "conversationId": "foreign"}
    from agent_console.workbench_owner_authorization import WorkbenchOwnerError

    with pytest.raises(WorkbenchOwnerError, match="FIXED_CHAT_FACT_BINDING_INVALID"):
        read_basis(call, None, "chat", {"fixedCycleFocus": bad})


def test_visible_fixed_link_has_only_safe_identity_and_coverage():
    from agent_console.private_conversation import PrivateConversations

    records = object.__new__(PrivateConversations)
    records.resolve_link = lambda *_: {
        "title": "cycle",
        "fixedCycle": {"runId": "run"},
        "fixedCycleContentComplete": False,
    }
    result = records.visible_links(
        None,
        [
            {
                "link_id": "link",
                "target": {
                    "fixedCycleFocus": {
                        "grants": ["private"],
                        "artifacts": ["internal"],
                    }
                },
            }
        ],
    )
    assert result == [
        {
            "link_id": "link",
            "target": None,
            "readable": True,
            "title": "cycle",
            "fixedCycle": {"runId": "run"},
            "fixedCycleContentComplete": False,
        }
    ]

    def denied(*args):
        raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    records.resolve_link = denied
    assert records.visible_links(
        None, [{"link_id": "link", "target": {"fixedCycleFocus": {}}}]
    ) == [{"link_id": "link", "readable": False}]
