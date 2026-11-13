"""Controlled typed meanings, not live natural-language acceptance."""

import json
from copy import deepcopy

import pytest
from agent_console.conversation_typed_answer_policy import (
    REVISION,
    SCHEMA_VERSION,
    route,
)
from agent_console.draft_assistance_policy import policy_for, validate_result
from agent_console.native_document_tools import NativeDocumentTools
from agent_console.native_loop_provider import action_schema
from agent_console.native_question_contracts import (
    consume_interpretation,
    scope_contracts,
    validate_meaning,
)
from agent_runtime.native_loop import digest
from test_conversation_relation_policy import direct, reply
from test_native_document_tools import REFERENCE, SOURCE
from test_understanding_adoption_policy import payload


def library():
    return NativeDocumentTools(deepcopy(SOURCE), deepcopy(REFERENCE))


def meaning(c, decision, candidate=None):
    return {
        "decision": decision,
        "candidateId": candidate,
        "questionContractDigest": c["contractDigest"],
    }


def request(c, attached=False):
    request = json.loads(payload("NATIVE"))
    frame = request["input"][-1]["content"][0]
    snapshot = json.loads(frame["text"])
    snapshot["answerContract"] = c
    frame["text"] = json.dumps(snapshot)
    if attached:
        request["input"].insert(
            1,
            {
                "content": [
                    {"text": json.dumps({"kind": "SERVER_READ_SELECTED_SOURCE"})}
                ]
            },
        )
    return json.dumps(request)


@pytest.mark.parametrize("attached", [False, True])
@pytest.mark.parametrize("decision", ["CONFIRM", "REJECT", "CHANGE", "UNCLEAR"])
def test_one_response_uses_exact_current_contract(decision, attached):
    c = scope_contracts(library())[0]
    selected = (
        c["proposedCandidateId"]
        if decision == "CONFIRM"
        else c["candidates"][1]["id"]
        if decision == "CHANGE"
        else None
    )
    value = {**reply(), "questionAnswer": meaning(c, decision, selected)}
    validate_result(value, policy_for(REVISION, SCHEMA_VERSION), frozenset())
    assert (
        route(value, request(c, attached))["questionAnswer"] == value["questionAnswer"]
    )


@pytest.mark.parametrize(
    "decision,candidate",
    [
        ("CONFIRM", None),
        ("CHANGE", "invented"),
        ("REJECT", "invented"),
        ("UNCLEAR", "invented"),
        ("EXECUTE", None),
    ],
)
def test_meaning_cannot_invent_candidate_or_execution(decision, candidate):
    c = scope_contracts(library())[0]
    with pytest.raises(ValueError):
        validate_meaning(meaning(c, decision, candidate), c)


def test_first_question_contract_needs_no_prior_tool_and_is_source_bound():
    lib = library()
    c = lib.question_contracts()[0]
    assert lib.resolve_question_contract(c["contractDigest"]) == c
    lib.documents["staging"]["text"] += "changed rule"
    with pytest.raises(ValueError):
        lib.resolve_question_contract(c["contractDigest"])


def test_consumption_rejection_clears_previous_confirmation():
    lib = library()
    c = lib.question_contracts()[0]
    for decision in ["CONFIRM", "REJECT", "UNCLEAR"]:
        value = {
            "schemaVersion": "native-verified-question-answer.v1",
            **meaning(
                c, decision, c["proposedCandidateId"] if decision == "CONFIRM" else None
            ),
        }
        value["interpretationDigest"] = digest(value)
        consume_interpretation(lib, c, value)
        assert lib.confirmed_scope == ("staging" if decision == "CONFIRM" else None)


def test_old_schema_unchanged_and_new_contract_explicit_opt_in():
    old = action_schema([])
    new = action_schema([], question_contracts=scope_contracts(library()))
    assert "questionContractId" not in json.dumps(old)
    assert "questionContractId" in json.dumps(new)
    assert action_schema([]) == old


def test_independent_answer_cannot_consume_question():
    c = scope_contracts(library())[0]
    value = {**direct(), "questionAnswer": None}
    assert route(value, request(c))["relation"] == "INDEPENDENT"
    value["questionAnswer"] = meaning(c, "CONFIRM", c["proposedCandidateId"])
    with pytest.raises(ValueError):
        route(value, request(c))


@pytest.mark.parametrize("decision", ["CONFIRM", "REJECT", "CHANGE", "UNCLEAR"])
def test_typed_runtime_real_adapter_prepare_keeps_original_budget(
    tmp_path, monkeypatch, decision
):
    from types import SimpleNamespace

    from agent_console.conversation_relation_context import (
        bind_snapshot,
        sealed_snapshot,
    )
    from agent_console.draft_assistance_bootstrap import _profile
    from agent_console.draft_assistance_policy import V3_CONTEXT_VERSION
    from agent_console.model_governance import canonical_digest
    from agent_console.openai_responses_draft_adapter import (
        OpenAIResponsesDraftTransport,
    )
    from test_draft_assistance_policy import content
    from test_openai_responses_draft_adapter import _real_runtime_document

    document = _real_runtime_document(
        SimpleNamespace(server_port=1), tmp_path / "unused", tmp_path
    )
    policy = policy_for(REVISION, SCHEMA_VERSION)
    document["adapter"]["revision"] = REVISION
    document.update(
        outputSchemaVersion=SCHEMA_VERSION,
        policyDigest=policy.digest,
        maximumInputTokens=65536,
    )
    document.pop("profileDigest")
    document["profileDigest"] = canonical_digest(document)
    profile, _, configuration, budget = _profile(document, allow_local_https_mock=True)
    transport = OpenAIResponsesDraftTransport(configuration)
    envelope = json.loads(content())
    envelope.update(schemaVersion=V3_CONTEXT_VERSION, previousAssistantResponse=None)
    contract = scope_contracts(library())[0]
    current = sealed_snapshot(
        "chat",
        "message",
        {"kind": "NATIVE"},
        {
            "goal": "read only",
            "currentQuestionType": "NATIVE",
            "currentQuestion": "Which scope?",
            "answerContract": contract,
        },
    )
    with bind_snapshot(current):
        prepared = transport.prepare(
            invocation_id="typed-offline", content=json.dumps(envelope), profile=profile
        )
    sent = json.loads(prepared.payload)
    assert sent["text"]["format"]["schema"] == policy.schema
    assert (
        json.loads(sent["input"][-1]["content"][0]["text"])["answerContract"]
        == contract
    )
    assert budget["callCap"] == document["budget"]["callCap"]
    assert budget["totalCostCapMicrousd"] == document["budget"]["totalCostCapMicrousd"]
    assert transport.dispatch_count == 0

    from agent_console.draft_assistance import ObservationState
    from test_openai_responses_draft_adapter import _completed

    candidate = (
        contract["proposedCandidateId"]
        if decision == "CONFIRM"
        else (contract["candidates"][1]["id"] if decision == "CHANGE" else None)
    )
    value = {
        **reply(),
        "currentQuestionToken": current["currentQuestionToken"],
        "questionAnswer": meaning(contract, decision, candidate),
    }
    calls = []

    def exchange(**kwargs):
        calls.append(kwargs)
        return 200, json.dumps(_completed(value)).encode(), "controlled", 1

    monkeypatch.setattr(transport, "exchange", exchange)
    observed = transport._dispatch_observation(
        invocation_id="typed-offline",
        request=prepared,
        credential=None,
        profile=profile,
    )
    assert observed.state is ObservationState.SUCCEEDED
    assert observed.conversation_route["questionAnswer"] == value["questionAnswer"]
    assert len(calls) == 1


def test_old_question_meaning_cannot_answer_changed_source_contract():
    original = scope_contracts(library())[0]
    accepted = meaning(original, "CONFIRM", original["proposedCandidateId"])
    changed = library()
    changed.documents["staging"]["text"] += "New scope restriction"
    current = scope_contracts(changed)[0]
    assert current["contractDigest"] != original["contractDigest"]
    with pytest.raises(ValueError, match="MEANING_INVALID"):
        validate_meaning(accepted, current)


def test_change_cannot_relabel_proposed_candidate_or_confirm_alternative():
    contract = scope_contracts(library())[0]
    proposed = contract["proposedCandidateId"]
    alternative = contract["candidates"][1]["id"]
    for value in [
        meaning(contract, "CHANGE", proposed),
        meaning(contract, "CONFIRM", alternative),
    ]:
        with pytest.raises(ValueError, match="MEANING_INVALID"):
            validate_meaning(value, contract)


def test_rule_bound_scope_does_not_offer_other_readable_policy():
    from types import SimpleNamespace

    lib = library()
    lib.binding = SimpleNamespace(scope="production")
    contracts = scope_contracts(lib)
    assert len(contracts) == 1
    assert [c["label"] for c in contracts[0]["candidates"]] == ["production"]


def test_native_v7_schema_keeps_exact_runtime_profile_and_budget(monkeypatch):
    from types import SimpleNamespace

    from agent_console import native_loop_provider as provider
    from agent_console.plan_suggestion_runtime import budget_quote

    config = SimpleNamespace(
        native_model_id="controlled-native-model",
        maximum_output_tokens=256,
        planning_model_policy=None,
        maximum_input_tokens=100000,
        maximum_response_bytes=100000,
        input_price_microusd_per_million_tokens=1000000,
        output_price_microusd_per_million_tokens=2000000,
    )
    original = dict(vars(config))
    profile = object()
    sent, credentials = [], []

    def exchange(**kw):
        sent.append(kw["request"])
        return 400, b"{}", None, 0

    def credentials_for(actual_config, actual_profile):
        assert actual_config is config and actual_profile is profile
        credentials.append((actual_config, actual_profile))
        return SimpleNamespace(
            resolve=lambda selected, _: (
                None if selected is profile else pytest.fail("profile changed")
            )
        )

    monkeypatch.setattr(
        provider,
        "planning_transport",
        lambda c: (
            SimpleNamespace(exchange=exchange)
            if c is config
            else pytest.fail("runtime changed")
        ),
    )
    monkeypatch.setattr(provider, "planning_credentials", credentials_for)
    monkeypatch.setattr(provider, "measurement", lambda *a, **kw: {})
    contracts = scope_contracts(library())
    for typed in (False, True):
        context = {"domain": "DOCUMENT_REVIEW"}
        if typed:
            context["questionContracts"] = contracts
        provider.NativeDecisionJob(
            config, profile, "controlled", {"context": context, "tools": []}
        ).run(lambda _: None)
    old, new = [json.loads(v.payload) for v in sent]
    assert len(sent) == len(credentials) == 2  # one per independently tested request
    assert sent[0].quote == sent[1].quote == budget_quote(config)
    assert vars(config) == original
    assert old["model"] == new["model"] == config.native_model_id
    assert old["max_output_tokens"] == new["max_output_tokens"] == 256
    assert old["text"]["format"]["schema"] == action_schema([])
    assert new["text"]["format"]["schema"] == action_schema(
        [], question_contracts=contracts
    )
    assert "including the FIRST question" not in old["instructions"]
    assert "including the FIRST question" in new["instructions"]
    assert (
        "copy the selected contract's contractDigest into questionContractId"
        in new["instructions"]
    )


def test_legacy_prepared_policy_rejects_unknown_payload_without_new_profile_fallback():
    from agent_console.draft_assistance_policy import (
        PolicyValidationError,
        prepared_policy,
    )

    for invalid_payload in (b"{}", b"not-json"):
        with pytest.raises(PolicyValidationError, match="DRAFT_POLICY_MISMATCH"):
            prepared_policy(invalid_payload)
