"""Non-content, finite diagnostics for failed local Responses validation only."""

PATHS = {
    "UNDERSTANDING_COUNT": "$.understanding",
    "UNDERSTANDING_SHAPE": "$.understanding[]",
    "UNDERSTANDING_VALUE": "$.understanding[]",
    "UNDERSTANDING_DUPLICATE": "$.understanding[].field",
    "UNDERSTANDING_REFERENCE": "$.understanding[].sourceRefs",
    "UNDERSTANDING_PROVENANCE": "$.understanding[].source",
    "UNDERSTANDING_REQUIRED": "$.understanding[].field",
    "RESULT_SHAPE": "$",
    "INTENT_KIND": "$.intent",
    "RESULT_KIND": "$.kind",
    "DATA_NEEDS": "$.dataNeeds",
    "EMPTY_FIELDS": "$",
    "DIRECT_ANSWER": "$.answer",
    "NEEDS_DATA": "$.dataNeeds",
    "ANSWER_DATA_EXCLUSIVE": "$",
    "QUESTIONS": "$.questions",
    "CLARIFICATION": "$.clarificationQuestion",
    "DRAFT_READY": "$",
    "ADOPTION_TOKEN_KIND": "$.currentQuestionToken",
    "RELATION": "$.relation",
    "RELATION_ANSWER": "$",
    "RELATION_TOKEN": "$.currentQuestionToken",
}
ROUTES = {
    "CONVERSATION_ROUTING_CONTEXT_REQUIRED": ("CONTEXT_REQUIRED", "$"),
    "CONVERSATION_ROUTING_CONTEXT_INVALID": ("CONTEXT_INVALID", "$"),
    "CONVERSATION_ROUTING_CONTEXT_TOO_LARGE": ("CONTEXT_LIMIT", "$"),
    "CONVERSATION_ROUTING_SOURCE_CONFLICT": ("SOURCE_BINDING", "$"),
    "CONVERSATION_ROUTING_QUESTION_MISMATCH": (
        "QUESTION_BINDING",
        "$.currentQuestionToken",
    ),
    "CONVERSATION_ROUTING_OWNER_RESULT_MISMATCH": ("OWNER_RESULT_KIND", "$.kind"),
}
STAGES = {
    "JSON_PARSE",
    "REQUEST_REFERENCES",
    "LOCAL_RESULT",
    "ROUTE_BINDING",
    "FINAL_RESULT",
}


def record_failure(measurement, stage, error=None):
    if not isinstance(measurement, dict) or stage not in STAGES:
        return
    category, path = "UNCLASSIFIED", "$"
    tag = getattr(error, "diagnostic", None)
    if isinstance(tag, str) and tag in PATHS:
        category, path = tag, PATHS[tag]
    elif type(error) is ValueError and len(error.args) == 1:
        reason = error.args[0]
        if isinstance(reason, str) and reason in ROUTES:
            category, path = ROUTES[reason]
    elif stage == "JSON_PARSE":
        category = "INVALID_JSON"
    measurement["output_validation"] = {
        "version": "output-validation.v1",
        "stage": stage,
        "category": category,
        "path": path,
    }
