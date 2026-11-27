# ruff: noqa: E501 -- Exact immutable receipt-column predicates.
"""Independent C1 result origin, distinct from answering a current question."""

from .conversation_goal_slots import require, require_schema
from .draft_assistance import DraftInvocationState, DraftResultKind
from .owned_business_policy import OwnedBusinessPolicyV3
from .owned_business_result_link import same_result_after_problem_link
from .private_conversation import digest


def result_identity(value):
    return {
        "invocationId": value.invocation_id,
        "contextId": value.context_id,
        "turnId": value.turn_id,
        "turnVersion": value.turn_version,
        "commitment": value.commitment,
        "profileRevisionId": value.profile_revision_id,
        "profileDigest": value.snapshot.profile_digest if value.snapshot else None,
        "adapterRevision": value.snapshot.adapter_revision if value.snapshot else None,
        "resultKind": value.result_kind.value if value.result_kind else None,
        "inputSource": value.input_source,
        "conversationContext": value.conversation_context,
        "conversationRoute": value.conversation_route,
        "reservationId": value.budget_reservation_id,
        "terminalObservationId": value.terminal_observation_id,
    }


def saved(c, context, invocation_id):
    if not c.execute(
        "SELECT to_regclass('conversation_goals.result_adoptions') t"
    ).fetchone()["t"]:
        return None
    require_schema(c)
    row = c.execute(
        "SELECT * FROM conversation_goals.result_adoptions WHERE tenant_id=%s "
        "AND security_domain=%s AND invocation_id=%s",
        (context.scope.tenant_id, context.scope.security_domain, invocation_id),
    ).fetchone()
    if row is None:
        return None
    r = row["record"]
    require(
        r.get("schemaVersion") == "conversation-independent-goal-adoption.v1"
        and digest(r) == row["record_digest"]
        and r.get("requestDigest")
        == digest(
            {
                "commandId": r.get("commandId"),
                "messageId": r.get("messageId"),
                "requestKey": r.get("requestKey"),
                "expectedConversationVersion": r.get("expectedConversationVersion"),
            }
        )
        and all(
            r.get(k) == row[col]
            for k, col in (
                ("tenantId", "tenant_id"),
                ("securityDomain", "security_domain"),
                ("conversationId", "conversation_id"),
                ("invocationId", "invocation_id"),
                ("goalId", "goal_id"),
                ("ownerId", "owner_id"),
                ("messageId", "message_id"),
                ("commandId", "command_key"),
                ("requestDigest", "request_digest"),
            )
        )
        and row["owner_id"] == context.principal_id,
        "CONVERSATION_GOAL_ADOPTION_CHANGED",
    )
    return row


def validate(c, context, value, policy):
    row = saved(c, context, value.invocation_id)
    if row is None:
        return None
    r = row["record"]
    require(
        isinstance(policy, OwnedBusinessPolicyV3), "CONVERSATION_GOAL_ORIGIN_DISABLED"
    )
    profile = policy.independentGoalProfile
    require(
        r["ownedPolicyDigest"] == policy.digest
        and r["result"] == result_identity(value)
        and value.state is DraftInvocationState.SUCCEEDED
        and value.result_kind
        in {
            DraftResultKind.DRAFT_READY,
            DraftResultKind.NEEDS_DATA,
            DraftResultKind.NEEDS_CLARIFICATION,
        }
        and value.initiating_principal_id == context.principal_id == policy.subjectId
        and value.snapshot is not None
        and (
            value.profile_revision_id,
            value.snapshot.profile_digest,
            value.snapshot.adapter_revision,
        )
        == (profile.profileRevisionId, profile.profileDigest, profile.adapterRevision)
        and (value.conversation_route or {}).get("intent") == "TASK"
        and (value.conversation_route or {}).get("relation") == "INDEPENDENT"
        and (value.conversation_route or {}).get("currentQuestionToken") is None
        and same_result_after_problem_link(
            c, context, value, r["aggregateVersion"], value.problem_id
        ),
        "CONVERSATION_GOAL_ORIGIN_CHANGED",
    )
    metadata = value.conversation_context or {}
    require(
        metadata.get("conversationId") == r["conversationId"]
        and metadata.get("messageId") == r["messageId"]
        and metadata.get("naturalGoalIntentVersion") == "v1"
        and metadata.get("goalId") is None
        and metadata.get("target") is None
        and metadata.get("currentQuestionToken") is None,
        "CONVERSATION_GOAL_ORIGIN_CHANGED",
    )
    mapping = c.execute(
        "SELECT s.* FROM conversation_goals.slots s "
        "JOIN conversation_goals.messages m USING(tenant_id,security_domain,conversation_id,goal_id) "
        "WHERE s.tenant_id=%s AND s.security_domain=%s AND s.conversation_id=%s "
        "AND s.goal_id=%s AND m.message_id=%s",
        (
            r["tenantId"],
            r["securityDomain"],
            r["conversationId"],
            r["goalId"],
            r["messageId"],
        ),
    ).fetchone()
    require(
        mapping
        and mapping["record_digest"] == r["goalDigest"] == digest(mapping["record"])
        and all(
            mapping["record"].get(k) == mapping[col]
            for k, col in (
                ("tenantId", "tenant_id"),
                ("securityDomain", "security_domain"),
                ("conversationId", "conversation_id"),
                ("goalId", "goal_id"),
                ("ownerId", "owner_id"),
                ("rootMessageId", "root_message_id"),
                ("commandId", "command_key"),
                ("requestDigest", "request_digest"),
            )
        )
        and mapping["record"]["rootMessageId"] == r["messageId"]
        and mapping["record"]["ownerId"] == context.principal_id,
        "CONVERSATION_GOAL_ORIGIN_CHANGED",
    )
    return row
