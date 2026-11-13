"""Exact saved owner evidence for adoption; no client result or dispatch port."""

from .understanding_result_adoption import AdoptionTarget, require, target_identity


def target_from_result(result):
    """Only accepts the persisted invocation's sealed context, never request JSON."""
    metadata = result.conversation_context or {}
    target = metadata.get("target") or {}
    required = {
        "kind",
        "invocationId",
        "contextId",
        "turnId",
        "turnVersion",
        "aggregateVersion",
        "inputSourceDigest",
        "journalVersion",
        "journeyKey",
    }
    require(
        set(target) == required and target["kind"] == "UNDERSTANDING", "TARGET_INVALID"
    )
    require(
        all(
            type(target[k]) is int and target[k] > 0
            for k in ("turnVersion", "aggregateVersion", "journalVersion")
        )
        and all(
            isinstance(target[k], str) and target[k]
            for k in required - {"turnVersion", "aggregateVersion", "journalVersion"}
        )
        and isinstance(metadata.get("conversationId"), str)
        and bool(metadata["conversationId"])
        and isinstance(metadata.get("messageId"), str)
        and bool(metadata["messageId"])
        and isinstance(metadata.get("currentQuestionToken"), str),
        "TARGET_INVALID",
    )
    value = AdoptionTarget(
        metadata["conversationId"],
        metadata["messageId"],
        result.initiating_principal_id,
        target["contextId"],
        target["invocationId"],
        target["turnId"],
        target["turnVersion"],
        target["aggregateVersion"],
        target["inputSourceDigest"],
        metadata["currentQuestionToken"],
        target["journalVersion"],
        target["journeyKey"],
    )
    require(target_identity(value) == target, "TARGET_INVALID")
    return value


def retained_evidence(result, target, facts, request_key):
    """Check an exact database-retained reply before constructing a reference."""
    require(
        facts.get("assistantResponse") is True
        and facts.get("state") == "SUCCEEDED"
        and facts.get("invokedBy") == target.subject_id
        and facts.get("requestKey") == request_key
        and facts.get("userMessageId") == target.message_id
        and facts.get("source")
        == {
            "kind": "DRAFT",
            "invocationId": result.invocation_id,
            "contextId": result.context_id,
            "turnId": result.turn_id,
            "turnVersion": result.turn_version,
        },
        "RETAINED_RESULT_MISMATCH",
    )
    saved = facts.get("response") or {}
    require(
        saved.get("resultKind") == result.result_kind.value
        and saved.get("conversationRoute") == result.conversation_route
        and saved.get("inputSource") == result.input_source,
        "RETAINED_RESULT_MISMATCH",
    )
    return {
        "invocationId": result.invocation_id,
        "contextId": result.context_id,
        "turnId": result.turn_id,
        "aggregateVersion": result.aggregate_version,
        "terminalObservationId": result.terminal_observation_id,
        "resultKind": result.result_kind.value,
        "userMessageId": target.message_id,
    }
