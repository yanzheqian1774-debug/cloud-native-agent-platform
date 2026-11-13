"""Read-only interpretation of the exact recorded input adapter, not model text."""

from .draft_assistance import DraftInvocationState
from .private_conversation import digest


def source_input_observation(response):
    value = response.invocation
    source = value.input_source
    state = "UNVERIFIED"
    snapshot = value.snapshot
    metadata = value.conversation_context or {}
    target = metadata.get("target") or {}
    route = value.conversation_route or {}
    if (
        source
        and not response.synthetic
        and value.state is DraftInvocationState.SUCCEEDED
        and snapshot
        and snapshot.adapter_id == "openai-responses-draft"
        and snapshot.profile_revision_id == value.profile_revision_id
        and snapshot.snapshot_id == value.snapshot_candidate_id
        and value.terminal_observation_id
        and value.terminal_observation_id == value.last_observation_id
        and target.get("kind") == "UNDERSTANDING"
        and target.get("inputSourceDigest") in {digest(None), digest(source)}
        and metadata.get("contextDigest")
        and metadata.get("contextDigest") == route.get("contextDigest")
        and route.get("relation") == "CURRENT_QUESTION"
    ):
        if snapshot.adapter_revision == "v3-relation-adoption":
            state = "METADATA_ONLY"
        elif snapshot.adapter_revision in {
            "v3-relation-adoption-source",
            "v3-relation-adoption-source-answers",
            "v4-structured-conversation",
        }:
            # Match provider_attachment's body branch, not merely its adapter.
            # Old minimal metadata omits input; absence is not body evidence.
            current = metadata.get("sourceInputBranch")
            if (
                isinstance(current, dict)
                and current.get("currentQuestionType") == "UNDERSTANDING"
                and current.get("hasCurrentQuestion") is True
            ):
                state = "BODY_CONTEXT"
    return {
        "state": state,
        "invocationId": value.invocation_id,
        "aggregateVersion": value.aggregate_version,
        "source": source,
        "basis": "RECORDED_ADAPTER_CONTRACT",
    }


def current_source_capability(service, available):
    if (
        service is None
        or not available
        or service.profile.adapter_id != "openai-responses-draft"
    ):
        return "UNAVAILABLE"
    return {
        "v3-relation-adoption": "METADATA_ONLY",
        "v3-relation-adoption-source": "BODY_SUPPORTED",
        "v3-relation-adoption-source-answers": "BODY_SUPPORTED",
        "v4-structured-conversation": "BODY_SUPPORTED",
    }.get(service.profile.adapter_revision, "UNAVAILABLE")
