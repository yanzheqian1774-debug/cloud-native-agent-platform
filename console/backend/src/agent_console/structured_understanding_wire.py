"""Unregistered successor wire compiler; never invokes, authorizes or repairs."""

import copy
import json
import re

from .conversation_typed_answer_policy import SCHEMA, validate
from .draft_assistance_policy import FIELDS, PolicyValidationError
from .native_question_contracts import validate_contract, validate_meaning

VERSION = "conversation-understanding-wire.v4"
REVISION = "v4-structured-conversation"
SLOTS = FIELDS[:-1]
FULL = {"DRAFT_READY", "NEEDS_CLARIFICATION"}


def fail(code):
    raise PolicyValidationError("OUTPUT_SCHEMA_INVALID", diagnostic=code)


def closed(properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def exact(value):
    return {"type": "null"} if value is None else {"type": "string", "enum": [value]}


def current(snapshot):
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("kind") != "SERVER_CURRENT_CONVERSATION"
    ):
        fail("WIRE_CONTEXT")
    if not snapshot.get("currentQuestion"):
        return None
    if not isinstance(snapshot["currentQuestion"], str):
        fail("WIRE_CONTEXT")
    kind, token = (
        snapshot.get("currentQuestionType"),
        snapshot.get("currentQuestionToken"),
    )
    if (
        kind not in {"UNDERSTANDING", "NATIVE", "PLANNING"}
        or not isinstance(token, str)
        or re.fullmatch(r"[a-f0-9]{64}", token) is None
    ):
        fail("WIRE_CONTEXT")
    return kind, token


def meanings(contract):
    contract = validate_contract(contract)
    proposed = contract["proposedCandidateId"]
    candidates = [item["id"] for item in contract["candidates"]]
    values = [("REJECT", None), ("UNCLEAR", None)]
    if proposed is not None:
        values.append(("CONFIRM", proposed))
    values.extend(("CHANGE", item) for item in candidates if item != proposed)
    return {
        "anyOf": [
            closed(
                {
                    "decision": exact(decision),
                    "candidateId": exact(candidate),
                    "questionContractDigest": exact(contract["contractDigest"]),
                }
            )
            for decision, candidate in values
        ]
    }


def compile_schema(snapshot):
    """Caller supplies the sealed server snapshot, never user-provided metadata."""
    question = current(snapshot)
    pairs = [
        (relation, kind)
        for relation in ("INDEPENDENT", "CURRENT_WORK")
        for kind in (
            "DIRECT_ANSWER",
            "NEEDS_DATA",
            "NEEDS_CLARIFICATION",
            "DRAFT_READY",
        )
    ] + [("AMBIGUOUS", "NEEDS_CLARIFICATION")]
    if question:
        pairs.extend(
            ("CURRENT_QUESTION", kind)
            for kind in (
                ("DRAFT_READY", "NEEDS_DATA", "NEEDS_CLARIFICATION")
                if question[0] == "UNDERSTANDING"
                else ("CURRENT_QUESTION_ANSWER",)
            )
        )
    item = copy.deepcopy(SCHEMA["properties"]["understanding"]["items"])
    item["properties"].pop("field")
    item["required"].remove("field")
    understanding = closed(
        {
            **{slot: copy.deepcopy(item) for slot in SLOTS},
            "openItems": {"type": "array", "maxItems": 7, "items": copy.deepcopy(item)},
        }
    )
    branches = []
    for relation, kind in pairs:
        fields = copy.deepcopy(SCHEMA["properties"])
        fields.update(kind=exact(kind), relation=exact(relation))
        fields["currentQuestionToken"] = exact(
            question[1] if relation == "CURRENT_QUESTION" else None
        )
        fields["questionAnswer"] = {"type": "null"}
        if (
            relation == "CURRENT_QUESTION"
            and question[0] == "NATIVE"
            and snapshot.get("answerContract") is not None
        ):
            fields["questionAnswer"] = meanings(snapshot["answerContract"])
        fields["understanding"] = (
            copy.deepcopy(understanding)
            if kind in FULL
            else {"type": "array", "maxItems": 0, "items": item}
        )
        if kind in {"DRAFT_READY", "CURRENT_QUESTION_ANSWER"}:
            fields["intent"] = exact("TASK")
        elif kind == "DIRECT_ANSWER":
            fields["intent"] = exact("ANSWER")
        for name in ("answer", "title", "description", "clarificationQuestion"):
            present = (
                (name == "answer" and kind == "DIRECT_ANSWER")
                or (name in {"title", "description"} and kind == "DRAFT_READY")
                or (name == "clarificationQuestion" and kind == "NEEDS_CLARIFICATION")
            )
            if not present:
                fields[name] = {"type": "null"}
            else:
                fields[name]["type"] = "string"
        fields["questions"]["minItems"] = 1 if kind == "NEEDS_CLARIFICATION" else 0
        fields["questions"]["maxItems"] = 2 if kind == "NEEDS_CLARIFICATION" else 0
        fields["dataNeeds"]["minItems"] = 1 if kind == "NEEDS_DATA" else 0
        fields["dataNeeds"]["maxItems"] = 6 if kind == "NEEDS_DATA" else 0
        branches.append(closed(fields))
    return closed({"result": {"anyOf": branches}})


def decode(text, snapshot, refs):
    """Strict structural projection; all old business/provenance checks remain."""

    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                fail("WIRE_DUPLICATE_KEY")
            value[key] = item
        return value

    try:
        wire = json.loads(
            text, object_pairs_hook=unique, parse_constant=lambda _: fail("WIRE_JSON")
        )
    except PolicyValidationError:
        raise
    except (ValueError, TypeError) as exc:
        raise PolicyValidationError(
            "OUTPUT_SCHEMA_INVALID", diagnostic="WIRE_JSON"
        ) from exc
    if not isinstance(wire, dict) or set(wire) != {"result"}:
        fail("WIRE_SHAPE")
    result = wire["result"]
    if not isinstance(result, dict) or set(result) != set(SCHEMA["required"]):
        fail("WIRE_SHAPE")
    question = current(snapshot)
    schema = compile_schema(snapshot)
    allowed = {
        (b["properties"]["relation"]["enum"][0], b["properties"]["kind"]["enum"][0])
        for b in schema["properties"]["result"]["anyOf"]
    }
    relation, kind = result["relation"], result["kind"]
    if (
        not isinstance(relation, str)
        or not isinstance(kind, str)
        or (relation, kind) not in allowed
    ):
        fail("WIRE_BRANCH")
    expected_token = question[1] if relation == "CURRENT_QUESTION" else None
    if result["currentQuestionToken"] != expected_token:
        fail("WIRE_TOKEN")
    result = copy.deepcopy(result)
    if kind in FULL:
        slots = result["understanding"]
        if not isinstance(slots, dict) or set(slots) != {*SLOTS, "openItems"}:
            fail("WIRE_UNDERSTANDING")
        if not isinstance(slots["openItems"], list) or len(slots["openItems"]) > 7:
            fail("WIRE_UNDERSTANDING")
        pairs = [(name, slots[name]) for name in SLOTS] + [
            ("openItem", item) for item in slots["openItems"]
        ]
        if any(
            not isinstance(item, dict) or set(item) != {"value", "source", "sourceRefs"}
            for _, item in pairs
        ):
            fail("WIRE_UNDERSTANDING")
        result["understanding"] = [{"field": name, **item} for name, item in pairs]
    validate(result, refs)
    contract = snapshot.get("answerContract")
    if (
        relation == "CURRENT_QUESTION"
        and question[0] == "NATIVE"
        and contract is not None
    ):
        validate_meaning(result["questionAnswer"], validate_contract(contract))
    elif result["questionAnswer"] is not None:
        fail("WIRE_QUESTION_CONTRACT")
    return result


def template_schema():
    """Immutable upper template; actual requests only narrow its legal choices."""
    root = compile_schema({"kind": "SERVER_CURRENT_CONVERSATION"})
    branches = root["properties"]["result"]["anyOf"]
    for kind in ("UNDERSTANDING", "NATIVE"):
        specialized = compile_schema(
            {
                "kind": "SERVER_CURRENT_CONVERSATION",
                "currentQuestion": "Template only; never sent to a provider",
                "currentQuestionType": kind,
                "currentQuestionToken": "0" * 64,
            }
        )
        for branch in specialized["properties"]["result"]["anyOf"]:
            fields = branch["properties"]
            if fields["relation"]["enum"] != ["CURRENT_QUESTION"]:
                continue
            fields["currentQuestionToken"] = {
                "type": "string",
                "pattern": "^[a-f0-9]{64}$",
            }
            if kind == "NATIVE":
                fields["questionAnswer"] = copy.deepcopy(
                    SCHEMA["properties"]["questionAnswer"]
                )
            branches.append(branch)
    return root


def decode_request(text, payload, refs):
    """Use the original prepared request, never a current journal lookup."""
    sent = json.loads(payload)
    frames = sent.get("input", [])
    if len(frames) not in (2, 3):
        fail("WIRE_CONTEXT")
    snapshot = json.loads(frames[-1]["content"][0]["text"])
    if sent["text"]["format"]["schema"] != compile_schema(snapshot):
        fail("WIRE_SCHEMA_CHANGED")
    return decode(text, snapshot, refs)
