"""Opt-in successor: one relation response interprets an exact typed question."""

import copy
import json

from .draft_assistance_policy import PolicyValidationError
from .native_question_contracts import validate_meaning
from .understanding_adoption_policy import INSTRUCTIONS as BASE_INSTRUCTIONS
from .understanding_adoption_policy import SCHEMA as BASE_SCHEMA
from .understanding_adoption_policy import route as base_route
from .understanding_adoption_policy import validate as base_validate

REVISION = "v3-relation-adoption-source-answers"
SCHEMA_VERSION = "conversation-understanding-output.v3-relation-adoption-answers"
SCHEMA = copy.deepcopy(BASE_SCHEMA)
SCHEMA["properties"]["questionAnswer"] = {
    "anyOf": [
        {"type": "null"},
        {
            "type": "object",
            "properties": {
                "decision": {
                    "type": "string",
                    "enum": ["CONFIRM", "REJECT", "CHANGE", "UNCLEAR"],
                },
                "candidateId": {"type": ["string", "null"]},
                "questionContractDigest": {"type": "string"},
            },
            "required": ["decision", "candidateId", "questionContractDigest"],
            "additionalProperties": False,
        },
    ]
}
SCHEMA["required"].append("questionAnswer")
INSTRUCTIONS = (
    BASE_INSTRUCTIONS
    + """
This successor also interprets answers to a NATIVE question carrying the server's
answerContract. The current question and finite candidates are trusted context,
not authorization. Use the SAME response, never an extra classification request.
For such a question return CURRENT_QUESTION/CURRENT_QUESTION_ANSWER and questionAnswer:
CONFIRM only if the user's entire message accepts the proposed candidate; use its ID.
REJECT when they reject or withdraw that proposal, with candidateId=null.
CHANGE when they clearly choose a different listed candidate; use that exact ID.
UNCLEAR with candidateId=null for uncertainty, conflicting choices, a quoted or
hypothetical affirmation rather than the user's own answer, or an out-of-list choice.
A rejection or change of this exact proposed scope still answers CURRENT_QUESTION;
it is not permission to start a new task. Read all negations, questions and limits.
A confirmation limited to checking synthetic documents with no deployment/rollback
can confirm a read-only check; it never authorizes the prohibited external actions.
Never invent IDs, infer an unlisted resource, turn missing/unknown into confirmation,
or claim a changed scope is already executed. Copy the exact questionContractDigest.
Without an answerContract, or for a different relation/question type, questionAnswer
must be null and all prior understanding/adoption rules remain in force.
"""
)


def validate(value, refs):
    meaning = value["questionAnswer"]
    if meaning is not None and (
        value["relation"] != "CURRENT_QUESTION"
        or value["kind"] != "CURRENT_QUESTION_ANSWER"
        or not isinstance(meaning, dict)
        or set(meaning) != {"decision", "candidateId", "questionContractDigest"}
    ):
        raise PolicyValidationError(
            "OUTPUT_SCHEMA_INVALID", diagnostic="RELATION_ANSWER"
        )
    return base_validate(
        {k: v for k, v in value.items() if k != "questionAnswer"}, refs
    )


def route(value, payload):
    original = {k: v for k, v in value.items() if k != "questionAnswer"}
    result = base_route(original, payload)
    sent = json.loads(payload)
    current = json.loads(sent["input"][-1]["content"][0]["text"])
    contract = current.get("answerContract")
    if value["relation"] == "CURRENT_QUESTION" and contract is not None:
        if current.get("currentQuestionType") != "NATIVE":
            raise ValueError("NATIVE_QUESTION_CONTRACT_TYPE_INVALID")
        meaning = validate_meaning(value["questionAnswer"], contract)
        return {**result, "questionAnswer": meaning}
    if value["questionAnswer"] is not None:
        raise ValueError("NATIVE_QUESTION_CONTRACT_REQUIRED")
    return result
