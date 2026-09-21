from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest
from agent_console.draft_assistance import DraftAssistanceError, ObservationState
from agent_console.draft_assistance_policy import (
    CONTEXT_VERSION,
    FIELDS,
    V1_SCHEMA_VERSION,
    V2_SCHEMA_VERSION,
    PolicyValidationError,
    context_references,
    legacy_content,
    policy_for,
    validate_result,
)
from agent_console.openai_responses_draft_adapter import (
    ExactFileOpenAICredentialResolver,
    OpenAIResponsesDraftTransport,
)
from test_kimi_responses_draft_adapter import kimi_mock  # noqa: F401
from test_openai_responses_draft_adapter import (
    _completed,
    _configuration,
    _credential_file,
    _profile,
    _real_runtime_document,
    _ResponsesHandler,
    mock_responses,  # noqa: F401 - reuse task-isolated ephemeral HTTPS fixture
)

CASES = json.loads(
    (Path(__file__).parent / "fixtures/s5_321_quality_cases.json").read_text()
)["cases"]


def content(messages=None):
    return json.dumps(
        {
            "schemaVersion": CONTEXT_VERSION,
            "uiRevision": 2,
            "messages": messages or [{"id": "user:1", "text": "Supplier A only"}],
            "currentDraft": None,
            "previousUnderstanding": None,
            "previousQuestion": None,
        }
    )


def result():
    return {
        "kind": "DRAFT_READY",
        "clarificationQuestion": None,
        "questions": [],
        "title": "Supplier quality",
        "description": "Supplier A only",
        "understanding": [
            {
                "field": field,
                "value": "Supplier A" if field == "scope" else "Unknown",
                "source": "USER_STATEMENT" if field == "scope" else "UNKNOWN",
                "sourceRefs": ["user:1"] if field == "scope" else [],
            }
            for field in FIELDS[:-1]
        ],
    }


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_all_synthetic_cases_fit_context_contract_without_claiming_quality(case):
    messages = [
        {"id": f"user:{i + 1}", "text": text} for i, text in enumerate(case["turns"])
    ]
    wire = content(messages)
    assert len(wire.encode()) < 16384
    assert context_references(wire) == frozenset(m["id"] for m in messages)
    assert case["oracle"]
    assert case["realMetrics"]["status"] == "NOT_MEASURED"
    assert all(v is None for k, v in case["realMetrics"].items() if k != "status")


@pytest.mark.parametrize(
    "mutation",
    [
        lambda x: x["understanding"][1].update(sourceRefs=["user:foreign"]),
        lambda x: x["understanding"][1].update(sourceRefs=[]),
        lambda x: x["understanding"][0].update(
            source="MODEL_SUGGESTION", sourceRefs=["user:1"]
        ),
        lambda x: x["understanding"].pop(),
        lambda x: x["understanding"][0].update(field="ownerId"),
        lambda x: x.update(questions=["one", "two", "three"]),
        lambda x: x.update(title="x" * 201),
        lambda x: x.update(approved=True),
    ],
)
def test_v2_rejects_unknown_sources_authority_fields_and_unbounded_output(mutation):
    output = result()
    mutation(output)
    with pytest.raises(PolicyValidationError, match=r"^OUTPUT_SCHEMA_INVALID$"):
        validate_result(
            output, policy_for("v2", V2_SCHEMA_VERSION), frozenset({"user:1"})
        )


def test_two_focused_questions_and_unknowns_are_valid():
    output = result()
    output.update(
        kind="NEEDS_CLARIFICATION",
        title=None,
        description=None,
        questions=["Which outcome?", "Which scope?"],
        clarificationQuestion="Which outcome?\nWhich scope?",
    )
    assert validate_result(
        output, policy_for("v2", V2_SCHEMA_VERSION), frozenset({"user:1"})
    )
    output["clarificationQuestion"] = "Different question"
    with pytest.raises(PolicyValidationError):
        validate_result(
            output, policy_for("v2", V2_SCHEMA_VERSION), frozenset({"user:1"})
        )


def test_policy_is_exact_and_v1_rollback_preserves_legacy_prompt():
    old = policy_for("v1", V1_SCHEMA_VERSION)
    new = policy_for("v2", V2_SCHEMA_VERSION)
    assert old.digest != new.digest
    schema = new.schema
    schema["properties"].clear()
    assert new.schema["properties"]
    for revision, version in (
        ("latest", V2_SCHEMA_VERSION),
        ("v2", V1_SCHEMA_VERSION),
        ("v1", V2_SCHEMA_VERSION),
    ):
        with pytest.raises(PolicyValidationError):
            policy_for(revision, version)
    assert legacy_content("unchanged original input") == "unchanged original input"
    assert legacy_content(content()) == "Supplier A only"


def test_https_v2_request_result_and_unknown_metadata_read_do_not_retain_content(
    mock_responses,  # noqa: F811
):
    server, cert, tmp = mock_responses
    configuration = _configuration(server, cert, _credential_file(tmp))
    profile = replace(
        _profile(), adapter_revision="v2", output_schema_version=V2_SCHEMA_VERSION
    )
    transport = OpenAIResponsesDraftTransport(configuration)
    credential = ExactFileOpenAICredentialResolver(
        configuration,
        expected_profile_revision_id=profile.profile_revision_id,
        expected_connection_profile_id=profile.connection_profile_id,
        expected_connection_profile_revision_id=profile.connection_profile_revision_id,
    ).resolve(profile, "321-test")
    _ResponsesHandler.response = _completed(result())
    request = transport.prepare(
        invocation_id="321-test", content=content(), profile=profile
    )
    observation = transport.dispatch(
        invocation_id="321-test",
        request=request,
        credential=credential,
        profile=profile,
    )
    assert observation.state is ObservationState.SUCCEEDED
    assert observation.understanding == result()["understanding"]
    sent = _ResponsesHandler.requests[-1]["body"]
    assert sent["store"] is False
    assert sent["instructions"] == policy_for("v2", V2_SCHEMA_VERSION).instructions
    assert "understanding" not in repr(observation)
    # Service persists only allowlisted invocation metadata, never this observation.
    from test_draft_assistance import build, context

    app, *_ = build()
    app.transport.dispatch = lambda **_: observation
    initial = app.begin(
        context(),
        key="321-no-content",
        content="A sufficiently detailed synthetic business question",
    )
    applied = initial
    assert applied.understanding == observation.understanding
    assert "understanding" not in asdict(applied.invocation)
    assert app.read(context(), initial.invocation.invocation_id).understanding is None


def test_invalid_v2_context_fails_before_network_or_credentials(mock_responses):  # noqa: F811
    server, cert, tmp = mock_responses
    transport = OpenAIResponsesDraftTransport(
        _configuration(server, cert, _credential_file(tmp))
    )
    profile = replace(
        _profile(), adapter_revision="v2", output_schema_version=V2_SCHEMA_VERSION
    )
    with pytest.raises(DraftAssistanceError, match="DRAFT_CONTEXT_INVALID"):
        transport.prepare(
            invocation_id="321-invalid", content="raw invalid input", profile=profile
        )
    assert transport.dispatch_count == 0
    assert _ResponsesHandler.requests == []


def test_v2_bootstrap_requires_exact_policy_digest(mock_responses):  # noqa: F811
    from agent_console.draft_assistance_bootstrap import _profile as parse

    server, cert, tmp = mock_responses
    document = _real_runtime_document(server, cert, tmp)
    document["adapter"]["revision"] = "v2"
    document["outputSchemaVersion"] = V2_SCHEMA_VERSION
    with pytest.raises(DraftAssistanceError):
        parse(document, allow_local_https_mock=True)
    document["policyDigest"] = "0" * 64
    with pytest.raises(DraftAssistanceError):
        parse(document, allow_local_https_mock=True)
    document["policyDigest"] = policy_for("v2", V2_SCHEMA_VERSION).digest
    profile, *_ = parse(document, allow_local_https_mock=True)
    assert profile.adapter_revision == "v2"


def test_context_preserves_bounded_maximum_field_edit():
    message = {
        "id": "user:edit",
        "text": "title=" + "x" * 200 + "\ndescription=" + "y" * 2000,
    }
    assert context_references(content([message])) == frozenset({"user:edit"})


def test_v2_kimi_ipc_carries_validated_understanding(kimi_mock):  # noqa: F811
    from test_kimi_responses_draft_adapter import (
        KimiResponsesDraftTransport,
        _KimiHandler,
        _resolver,
    )
    from test_kimi_responses_draft_adapter import (
        _completed as kimi_completed,
    )
    from test_kimi_responses_draft_adapter import (
        _configuration as configuration_for,
    )
    from test_kimi_responses_draft_adapter import (
        _credential_file as credential_for,
    )
    from test_kimi_responses_draft_adapter import (
        _profile as profile_for,
    )

    server, cert, tmp = kimi_mock
    configuration = configuration_for(server, cert, credential_for(tmp))
    profile = replace(
        profile_for(), adapter_revision="v2", output_schema_version=V2_SCHEMA_VERSION
    )
    transport = KimiResponsesDraftTransport(configuration)
    _KimiHandler.response = kimi_completed(result())
    observation = transport.dispatch(
        invocation_id="321-v2-kimi",
        request=transport.prepare(
            invocation_id="321-v2-kimi", content=content(), profile=profile
        ),
        profile=profile,
        credential=_resolver(configuration).resolve(profile, "321-v2-kimi"),
    )
    assert observation.state is ObservationState.SUCCEEDED
    assert observation.understanding == result()["understanding"]


def test_v1_synthetic_fallback_unwraps_new_client_context():
    from agent_console.draft_assistance import DeterministicSyntheticDraftTransport

    transport = DeterministicSyntheticDraftTransport()
    request = transport.prepare(
        invocation_id="321-v1", content=content(), profile=_profile()
    )
    assert request.payload == "Supplier A only"
    observation = transport.dispatch(
        invocation_id="321-v1", request=request, credential=None, profile=_profile()
    )
    assert observation.result_kind.value == "NEEDS_CLARIFICATION"
    assert observation.understanding is None
