# ruff: noqa: E501 -- Exact owner-scoped queries.
"""Read an actual saved interpretation; clients never submit semantic authority."""

from agent_runtime.native_loop import digest

from .authority_contracts import AuthorityError
from .conversation_typed_answer_policy import REVISION
from .draft_assistance import DraftScope
from .draft_assistance_authorization import read_grant
from .draft_assistance_postgres import PostgresDraftAssistanceRepository
from .native_question_contracts import validate_contract, validate_meaning
from .private_conversation import digest as conversation_digest


def require(value):
    if not value:
        raise AuthorityError("NATIVE_TYPED_ANSWER_BINDING_INVALID")


def verified_interpretation(
    call, app, preparation, question, body, *, settlement_reader=None
):
    contract = question.get("answerContract")
    if contract is None:
        return None
    try:
        validate_contract(contract)
    except ValueError as exc:
        raise AuthorityError("NATIVE_TYPED_ANSWER_BINDING_INVALID") from exc
    ref = body.get("interpretationReference")
    require(isinstance(ref, dict) and set(ref) == {"messageId", "requestKey"})
    c, context = call.connection, call.context
    scope = (preparation.namespace, preparation.security_domain)
    conversation = body["conversationId"]
    owned = c.execute(
        "SELECT owner_id,archived_at FROM private_conversation.conversations WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s FOR UPDATE",
        (*scope, conversation),
    ).fetchone()
    require(
        owned
        and owned["owner_id"] == context.principal_id
        and owned["archived_at"] is None
    )
    message = c.execute(
        "SELECT m.content,m.author_id,f.facts FROM private_conversation.messages m LEFT JOIN private_conversation.message_facts f USING(tenant_id,security_domain,conversation_id,message_id) WHERE m.tenant_id=%s AND m.security_domain=%s AND m.conversation_id=%s AND m.message_id=%s",
        (*scope, conversation, ref["messageId"]),
    ).fetchone()
    require(
        message
        and message["author_id"] == context.principal_id
        and not (message["facts"] or {}).get("assistantResponse")
        and message["content"].strip() == body["answer"].strip()
    )
    claim = c.execute(
        "SELECT invocation_id FROM draft_assistance.idempotency_claims WHERE namespace=%s AND security_domain=%s AND initiating_principal_id=%s AND action='REQUEST_DRAFT_ASSISTANCE' AND scoped_idempotency_key=%s",
        (
            *scope,
            context.principal_id,
            "conversation:"
            + conversation_digest([conversation, ref["messageId"], ref["requestKey"]]),
        ),
    ).fetchone()
    require(claim)
    invocation = PostgresDraftAssistanceRepository._latest(
        c, DraftScope(*scope), claim["invocation_id"]
    )
    require(
        invocation
        and invocation.snapshot
        and invocation.snapshot.adapter_revision
        in {REVISION, "v4-structured-conversation"}
    )
    grant = read_grant(invocation)
    call.authority.require(
        app.principal, grant.owner, grant.action, grant.exact_resource
    )
    require(callable(settlement_reader))
    settlement = settlement_reader(c, invocation)
    require(
        settlement.get("status") == "ESTIMATE_SETTLED"
        and settlement.get("reservation_retained") is False
    )
    metadata, route = (
        invocation.conversation_context or {},
        invocation.conversation_route or {},
    )
    target = metadata.get("target") or {}
    require(
        invocation.initiating_principal_id == context.principal_id
        and invocation.state.value == "SUCCEEDED"
        and invocation.result_kind is not None
        and invocation.result_kind.value == "CURRENT_QUESTION_ANSWER"
        and invocation.settlement_status == "ESTIMATE_SETTLED"
        and (invocation.local_cleanup or {}).get("reaped") is True
        and invocation.terminal_observation_id == invocation.last_observation_id
        and invocation.terminal_observation_id
        and invocation.admission_id
        and invocation.budget_reservation_id
        and metadata.get("conversationId") == conversation
        and metadata.get("messageId") == ref["messageId"]
        and route.get("relation") == "CURRENT_QUESTION"
        and route.get("contextDigest") == metadata.get("contextDigest")
        and route.get("currentQuestionToken") == metadata.get("currentQuestionToken")
        and target.get("kind") == "NATIVE"
        and target.get("invocationId") == body["invocationId"]
        and target.get("questionKey") == body["questionKey"]
        and target.get("questionDigest") == body["questionDigest"]
        and target.get("executionDigest") == preparation.digest
        and target.get("runId") == preparation.run_id
        and target.get("expiresAt") == question["expiresAt"]
        and contract["sourceReference"]
        == preparation.source_snapshot.model_dump(mode="json")
    )
    from .conversation_goal_selection import selected_journal

    journal = selected_journal(
        c, context, conversation, invocation=invocation, lock=True
    )
    require(
        journal
        and journal["version"] == target.get("journalVersion")
        and journal["state"].get("key") == target.get("journeyKey")
    )
    retained = c.execute(
        "SELECT facts FROM private_conversation.message_facts WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s AND facts->>'assistantResponse'='true' AND facts#>>'{source,invocationId}'=%s LIMIT 2",
        (*scope, conversation, invocation.invocation_id),
    ).fetchall()
    require(len(retained) == 1)
    facts = retained[0]["facts"]
    require(
        facts.get("invokedBy") == context.principal_id
        and facts.get("userMessageId") == ref["messageId"]
        and facts.get("requestKey") == ref["requestKey"]
        and (facts.get("response") or {}).get("conversationRoute") == route
    )
    try:
        meaning = validate_meaning(route.get("questionAnswer"), contract)
    except ValueError as exc:
        raise AuthorityError("NATIVE_TYPED_ANSWER_BINDING_INVALID") from exc
    value = {
        "schemaVersion": "native-verified-question-answer.v1",
        **meaning,
        "invocationId": invocation.invocation_id,
        "inputMessageId": ref["messageId"],
        "inputDigest": digest(message["content"]),
        "profileRevisionId": invocation.profile_revision_id,
        "profileDigest": invocation.snapshot.profile_digest,
        "questionDigest": body["questionDigest"],
    }
    return {**value, "interpretationDigest": digest(value)}


def settlement_reader_for_services(*services):
    """Select only an explicitly retained exact profile; never the latest budget."""
    readers = {}
    for service in services:
        if service is None:
            continue
        profile = service.profile
        require(profile.adapter_revision in {REVISION, "v4-structured-conversation"})
        key = (
            profile.adapter_revision,
            profile.profile_revision_id,
            profile.profile_digest,
        )
        require(key not in readers)
        readers[key] = service.budget.read_invocation_settlement
    if not readers:
        return None

    def read(connection, invocation):
        require(invocation.snapshot is not None)
        snapshot = invocation.snapshot
        key = (
            snapshot.adapter_revision,
            invocation.profile_revision_id,
            snapshot.profile_digest,
        )
        reader = readers.get(key)
        require(reader is not None)
        # Original budget owner rechecks scope, reservation/invocation, pricing
        # and authoritative settlement on this same caller connection.
        return reader(connection, invocation)

    return read
