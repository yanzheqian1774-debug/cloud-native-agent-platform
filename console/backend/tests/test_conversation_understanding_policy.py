"""Additive result contract; these tests enable no runtime profile."""

from copy import deepcopy

import pytest
from agent_console.draft_assistance_policy import (
    V1_SCHEMA_VERSION,
    V2_SCHEMA_VERSION,
    V3_SCHEMA_VERSION,
    PolicyValidationError,
    policy_for,
    validate_result,
)
from test_draft_assistance_policy import result
from test_openai_responses_draft_adapter import mock_responses  # noqa: F401


def direct():
    return {
        "kind": "DIRECT_ANSWER",
        "answer": "可以先明确目标。再核对所需资料。",
        "title": None,
        "description": None,
        "clarificationQuestion": None,
        "questions": [],
        "understanding": [],
        "dataNeeds": [],
    }


def test_direct_answer_is_not_a_business_draft_or_a_question():
    p = policy_for("v3", V3_SCHEMA_VERSION)
    assert validate_result(direct(), p, frozenset()) == []
    task = result()
    task.update(answer=None, dataNeeds=[])
    assert validate_result(task, p, frozenset({"user:1"}))


@pytest.mark.parametrize(
    "change",
    [
        {"answer": " "},
        {"answer": "x" * 8001},
        {"title": "invented task"},
        {"clarificationQuestion": "repeat?"},
        {"questions": ["repeat?"]},
        {"dataNeeds": ["an unnecessary source"]},
        {"kind": []},
    ],
)
def test_ambiguous_direct_payload_is_rejected(change):
    r = direct()
    r.update(change)
    with pytest.raises(PolicyValidationError):
        validate_result(r, policy_for("v3", V3_SCHEMA_VERSION), frozenset())


def test_data_requirement_is_explicit_without_an_answer_or_execution_claim():
    r = direct()
    r.update(kind="NEEDS_DATA", answer=None, dataNeeds=["待核对的上线交接说明"])
    assert validate_result(r, policy_for("v3", V3_SCHEMA_VERSION), frozenset()) == []
    for change in [{"dataNeeds": []}, {"answer": "已经检查完毕"}, {"dataNeeds": [""]}]:
        invalid = {**r, **change}
        with pytest.raises(PolicyValidationError):
            validate_result(invalid, policy_for("v3", V3_SCHEMA_VERSION), frozenset())


def test_new_policy_is_isolated_from_existing_versions():
    for revision, schema in [
        ("v1", V1_SCHEMA_VERSION),
        ("v2", V2_SCHEMA_VERSION),
        ("v2-zh-CN", V2_SCHEMA_VERSION),
    ]:
        p = policy_for(revision, schema)
        original = deepcopy(p.schema)
        assert "answer" not in original["properties"]
        with pytest.raises(PolicyValidationError):
            validate_result(direct(), p, frozenset())
        new = policy_for("v3", V3_SCHEMA_VERSION).schema
        new["properties"]["kind"]["enum"].clear()
        assert p.schema == original
    with pytest.raises(PolicyValidationError):
        policy_for("v2", V3_SCHEMA_VERSION)


@pytest.mark.parametrize("kind", ["DIRECT_ANSWER", "NEEDS_DATA"])
def test_v3_https_adapter_and_service_preserve_result_kind_without_task_creation(
    mock_responses,  # noqa: F811
    kind,
):
    from dataclasses import replace

    from agent_console.draft_assistance import ObservationState
    from agent_console.draft_assistance_api import _payload
    from agent_console.openai_responses_draft_adapter import (
        ExactFileOpenAICredentialResolver,
        OpenAIResponsesDraftTransport,
    )
    from test_draft_assistance import build, context
    from test_draft_assistance_policy import content
    from test_openai_responses_draft_adapter import (
        _completed,
        _configuration,
        _credential_file,
        _profile,
        _ResponsesHandler,
    )

    server, cert, tmp = mock_responses
    configuration = _configuration(server, cert, _credential_file(tmp))
    profile = replace(
        _profile(), adapter_revision="v3", output_schema_version=V3_SCHEMA_VERSION
    )
    transport = OpenAIResponsesDraftTransport(configuration)
    credential = ExactFileOpenAICredentialResolver(
        configuration,
        expected_profile_revision_id=profile.profile_revision_id,
        expected_connection_profile_id=profile.connection_profile_id,
        expected_connection_profile_revision_id=profile.connection_profile_revision_id,
    ).resolve(profile, "conversation-v3")
    output = direct()
    if kind == "NEEDS_DATA":
        output.update(kind=kind, answer=None, dataNeeds=["上线交接说明"])
    _ResponsesHandler.response = _completed(output)
    prepared = transport.prepare(
        invocation_id="conversation-v3", content=content(), profile=profile
    )
    observation = transport.dispatch(
        invocation_id="conversation-v3",
        request=prepared,
        credential=credential,
        profile=profile,
    )
    assert observation.state is ObservationState.SUCCEEDED
    assert observation.result_kind.value == kind
    assert len(_ResponsesHandler.requests) == 1
    assert _ResponsesHandler.requests[0]["body"]["store"] is False
    app, *_ = build()
    app.transport.dispatch = lambda **_: observation
    response = app.begin(
        context(),
        key="conversation-v3",
        content="An explicit synthetic conversation request",
    )
    assert response.invocation.problem_id is None
    payload = _payload(response)["result"]
    assert payload["answer"] == output["answer"]
    assert payload["dataNeeds"] == output["dataNeeds"]
    assert payload["draft"] is None
    # Invocation metadata stays content-free; conversation retention is separate.
    replay = _payload(app.read(context(), response.invocation.invocation_id))["result"]
    assert replay["answer"] is None
    assert replay["reasonCode"] == "RESULT_CONTENT_NOT_RETAINED"


def test_v3_followup_context_does_not_change_legacy_context_validation():
    import json

    from agent_console.draft_assistance_policy import (
        V3_CONTEXT_VERSION,
        context_references,
        conversation_context_references,
    )
    from test_draft_assistance_policy import content

    value = json.loads(content())
    value.update(
        schemaVersion=V3_CONTEXT_VERSION,
        previousAssistantResponse={
            "invocationId": "prior",
            "answer": "A previous answer",
        },
        previousUnderstanding=[],
    )
    assert conversation_context_references(json.dumps(value)) == frozenset({"user:1"})
    with pytest.raises(PolicyValidationError):
        context_references(json.dumps(value))
    value["previousAssistantResponse"]["answer"] = ""
    with pytest.raises(PolicyValidationError):
        conversation_context_references(json.dumps(value))
