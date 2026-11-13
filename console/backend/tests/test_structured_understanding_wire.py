import copy
import json

import pytest
from agent_console.draft_assistance_policy import FIELDS, PolicyValidationError
from agent_console.structured_understanding_wire import compile_schema, decode
from agent_runtime.native_loop import digest


def snapshot(kind="UNDERSTANDING"):
    return {
        "kind": "SERVER_CURRENT_CONVERSATION",
        "currentQuestion": "Which source?" if kind else None,
        "currentQuestionType": kind,
        "currentQuestionToken": "a" * 64 if kind else None,
    }


def draft():
    item = {"value": "Confirmed", "source": "USER_STATEMENT", "sourceRefs": ["user:1"]}
    return {
        "kind": "DRAFT_READY",
        "intent": "TASK",
        "relation": "CURRENT_QUESTION",
        "currentQuestionToken": "a" * 64,
        "questionAnswer": None,
        "title": "Title",
        "description": "Description",
        "answer": None,
        "clarificationQuestion": None,
        "questions": [],
        "dataNeeds": [],
        "understanding": {
            **{key: copy.deepcopy(item) for key in FIELDS[:-1]},
            "openItems": [],
        },
    }


def read(value, context=None):
    return decode(
        json.dumps({"result": value}), context or snapshot(), frozenset({"user:1"})
    )


@pytest.mark.parametrize("count", [0, 7])
def test_fixed_slots_preserve_text_refs_and_open_items(count):
    value = draft()
    value["understanding"]["openItems"] = [
        copy.deepcopy(value["understanding"]["goal"]) for _ in range(count)
    ]
    original = copy.deepcopy(value)
    result = read(value)
    assert len(result["understanding"]) == 5 + count
    assert [v["field"] for v in result["understanding"][:5]] == list(FIELDS[:-1])
    assert result["currentQuestionToken"] == value["currentQuestionToken"]
    assert value == original


@pytest.mark.parametrize(
    "change", ["missing", "extra", "old-array", "too-many", "item-field", "bad-ref"]
)
def test_invalid_understanding_never_repaired(change):
    value = draft()
    slots = value["understanding"]
    if change == "missing":
        del slots["goal"]
    elif change == "extra":
        slots["goal2"] = slots["goal"]
    elif change == "old-array":
        value["understanding"] = [{"field": "goal", **slots["goal"]}] * 5
    elif change == "too-many":
        slots["openItems"] = [slots["goal"]] * 8
    elif change == "item-field":
        slots["goal"]["field"] = "scope"
    else:
        slots["goal"]["sourceRefs"] = ["foreign-message"]
    with pytest.raises(PolicyValidationError):
        read(value)


@pytest.mark.parametrize("token", [None, "", "b" * 64, 4])
def test_current_question_token_must_be_returned_exactly(token):
    value = draft()
    value["currentQuestionToken"] = token
    with pytest.raises(PolicyValidationError) as caught:
        read(value)
    assert caught.value.diagnostic == "WIRE_TOKEN"


@pytest.mark.parametrize("kind", [None, "NATIVE", "PLANNING"])
def test_full_adoption_only_for_current_understanding(kind):
    with pytest.raises(PolicyValidationError):
        read(draft(), snapshot(kind))


def test_duplicate_json_keys_are_rejected_not_last_wins():
    text = json.dumps({"result": draft()}).replace(
        '"title": "Title"', '"title": "Title", "title": "Replacement"'
    )
    with pytest.raises(PolicyValidationError) as caught:
        decode(text, snapshot(), frozenset({"user:1"}))
    assert caught.value.diagnostic == "WIRE_DUPLICATE_KEY"


def test_independent_answer_does_not_consume_current_question():
    value = draft()
    value.update(
        kind="DIRECT_ANSWER",
        intent="ANSWER",
        relation="INDEPENDENT",
        currentQuestionToken=None,
        understanding=[],
        title=None,
        description=None,
        answer="Hello",
    )
    assert read(value)["relation"] == "INDEPENDENT"


def contract():
    value = {
        "schemaVersion": "native-question-answer.v1",
        "kind": "POLICY_SCOPE",
        "sourceSnapshotDigest": "c" * 64,
        "sourceReference": {"resource_id": "source"},
        "candidates": [
            {"id": x, "label": x, "resourceId": x, "contentDigest": "d" * 64}
            for x in ("p", "q")
        ],
        "proposedCandidateId": "p",
    }
    return {**value, "contractDigest": digest(value)}


@pytest.mark.parametrize(
    "decision,candidate",
    [("CONFIRM", "p"), ("CHANGE", "q"), ("REJECT", None), ("UNCLEAR", None)],
)
def test_typed_answer_preserves_one_returned_meaning(decision, candidate):
    context = {**snapshot("NATIVE"), "answerContract": contract()}
    value = draft()
    value.update(
        kind="CURRENT_QUESTION_ANSWER",
        understanding=[],
        title=None,
        description=None,
        questionAnswer={
            "decision": decision,
            "candidateId": candidate,
            "questionContractDigest": context["answerContract"]["contractDigest"],
        },
    )
    assert read(value, context)["questionAnswer"] == value["questionAnswer"]
    value["questionAnswer"]["candidateId"] = "foreign"
    with pytest.raises(ValueError):
        read(value, context)


@pytest.mark.parametrize("kind", [None, "UNDERSTANDING", "PLANNING", "NATIVE"])
def test_schema_is_closed_nested_union_and_exact_token(kind):
    context = snapshot(kind)
    if kind == "NATIVE":
        context["answerContract"] = contract()
    schema = compile_schema(context)
    assert schema["type"] == "object" and "anyOf" not in schema

    def inspect(node):
        if isinstance(node, dict):
            assert not set(node) & {
                "if",
                "then",
                "else",
                "not",
                "allOf",
                "dependentSchemas",
                "uniqueItems",
            }
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for value in node.values():
                inspect(value)
        elif isinstance(node, list):
            for value in node:
                inspect(value)

    inspect(schema)
    branches = schema["properties"]["result"]["anyOf"]
    current = [
        b["properties"]
        for b in branches
        if b["properties"]["relation"]["enum"] == ["CURRENT_QUESTION"]
    ]
    assert bool(current) == bool(kind)
    for fields in current:
        assert fields["currentQuestionToken"] == {"type": "string", "enum": ["a" * 64]}
        assert fields["kind"]["enum"][0] != "DIRECT_ANSWER"
