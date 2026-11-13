"""Rejected text never becomes diagnostic content; no real model calls."""

import json
from dataclasses import replace

import pytest
from agent_console.draft_assistance import ObservationState
from agent_console.draft_assistance_policy import (
    V2_SCHEMA_VERSION,
    PolicyValidationError,
    policy_for,
    validate_result,
)
from agent_console.openai_responses_draft_adapter import (
    ExactFileOpenAICredentialResolver,
    OpenAIResponsesDraftTransport,
)
from agent_console.output_validation_diagnostic import record_failure
from test_draft_assistance_policy import content, result
from test_openai_responses_draft_adapter import (
    _completed,
    _configuration,
    _credential_file,
    _profile,
    _ResponsesHandler,
    mock_responses,  # noqa: F401
)


@pytest.mark.parametrize(
    ("mutation", "category", "path"),
    [
        (
            lambda v: v.update(understanding=[]),
            "UNDERSTANDING_COUNT",
            "$.understanding",
        ),
        (
            lambda v: v["understanding"][0].update(sourceRefs=["secret-document-id"]),
            "UNDERSTANDING_REFERENCE",
            "$.understanding[].sourceRefs",
        ),
        (lambda v: v.update(**{"secret-key": "secret-body"}), "RESULT_SHAPE", "$"),
        (lambda v: v.update(questions=["secret-body"]), "DRAFT_READY", "$"),
    ],
)
def test_finite_diagnostics_keep_original_rejection(mutation, category, path):
    value = result()
    mutation(value)
    with pytest.raises(
        PolicyValidationError, match=r"^OUTPUT_SCHEMA_INVALID$"
    ) as error:
        validate_result(
            value, policy_for("v2", V2_SCHEMA_VERSION), frozenset({"user:1"})
        )
    measurement = {}
    record_failure(measurement, "LOCAL_RESULT", error.value)
    actual = measurement["output_validation"]
    assert (actual["category"], actual["path"]) == (category, path)
    assert "secret" not in json.dumps(measurement)


@pytest.mark.parametrize(
    "error",
    [
        KeyError("secret-key"),
        ValueError("secret-body"),
        PolicyValidationError("secret-body", diagnostic="secret-tag"),
    ],
)
def test_unknown_exception_never_leaks(error):
    actual = {}
    record_failure(actual, "ROUTE_BINDING", error)
    assert actual["output_validation"]["category"] == "UNCLASSIFIED"
    assert "secret" not in json.dumps(actual)


@pytest.mark.parametrize("invalid", [False, "reference", "empty_title"])
def test_https_observation_carries_only_safe_diagnostic(mock_responses, invalid):  # noqa: F811
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
    ).resolve(profile, "diagnostic-test")
    value = result()
    if invalid == "reference":
        value["understanding"][0]["sourceRefs"] = ["secret-private-reference"]
    elif invalid == "empty_title":
        value["title"] = ""
    _ResponsesHandler.response = _completed(value)
    prepared = transport.prepare(
        invocation_id="diagnostic-test", content=content(), profile=profile
    )
    observed = transport.dispatch(
        invocation_id="diagnostic-test",
        request=prepared,
        credential=credential,
        profile=profile,
    )
    assert len(_ResponsesHandler.requests) == 1
    if invalid:
        assert observed.state is ObservationState.FAILED
        assert observed.reason_code == "OUTPUT_SCHEMA_INVALID"
        assert observed.measurement["output_validation"]["stage"] == (
            "LOCAL_RESULT" if invalid == "reference" else "FINAL_RESULT"
        )
        assert observed.local_cleanup["reaped"] is True
    else:
        assert observed.state is ObservationState.SUCCEEDED
        assert "output_validation" not in observed.measurement
    assert "secret" not in json.dumps(observed.measurement)
    if invalid:
        from test_draft_assistance import build, context

        app, *_ = build()
        app.transport.dispatch = lambda **_: observed
        saved = app.begin(
            context(),
            key="diagnostic-owner",
            content="A detailed synthetic business question",
        )
        reread = app.read(context(), saved.invocation.invocation_id)
        assert reread.invocation.measurement == observed.measurement
        assert reread.invocation.local_cleanup == observed.local_cleanup
        assert reread.invocation.reason_code == "OUTPUT_SCHEMA_INVALID"
        assert reread.understanding is None


@pytest.mark.parametrize("owner", ["UNDERSTANDING", "NATIVE"])
def test_adoption_source_diagnostics_distinguish_reference_and_owner(owner):
    from agent_console.understanding_adoption_policy import route
    from test_understanding_adoption_policy import full, payload

    value = full()
    if owner == "UNDERSTANDING":
        value["understanding"][0]["sourceRefs"] = ["secret-document-ref"]
        with pytest.raises(PolicyValidationError) as error:
            validate_result(
                value,
                policy_for(
                    "v3-relation-adoption-source",
                    "conversation-understanding-output.v3-relation-adoption",
                ),
                frozenset({"user:1"}),
            )
        stage, category = "LOCAL_RESULT", "UNDERSTANDING_REFERENCE"
    else:
        with pytest.raises(ValueError) as error:
            route(value, payload(owner))
        stage, category = "ROUTE_BINDING", "OWNER_RESULT_KIND"
    observed = {}
    record_failure(observed, stage, error.value)
    assert observed["output_validation"]["category"] == category
    assert "secret" not in json.dumps(observed)
