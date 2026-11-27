# ruff: noqa: E501 -- Exact same-connection retained C1 evidence.
"""Consume one real human C1 result bound to an immutable service question."""

from agent_runtime.native_loop import digest as native_digest

from .authority_contracts import AuthorityError
from .conversation_typed_answer_policy import REVISION
from .draft_assistance import DraftScope
from .draft_assistance_authorization import read_grant
from .draft_assistance_postgres import PostgresDraftAssistanceRepository
from .fixed_question_context import from_presentation
from .native_question_contracts import validate_contract, validate_meaning
from .private_conversation import digest as conversation_digest
from .resource_use_domain import canonical_digest
from .workbench_business_problem import OwnerPrincipal


def require(ok):
    if not ok:
        raise AuthorityError("FIXED_QUESTION_INTERPRETATION_INVALID")


def verified(call, presentation, message_id, request_key, *, settlement_reader):
    """Client provides references only. No client answer/meaning is accepted."""
    c, ctx, identity = call.connection, call.context, presentation.identity
    scope = identity.tenantId, identity.securityDomain
    conversation = identity.conversationId
    require(presentation.actorId == ctx.principal_id)
    require(scope == (ctx.scope.tenant_id, ctx.scope.security_domain))
    owned = c.execute(
        "SELECT owner_id,archived_at FROM private_conversation.conversations WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s FOR UPDATE",
        (*scope, conversation),
    ).fetchone()
    require(
        owned and owned["owner_id"] == ctx.principal_id and owned["archived_at"] is None
    )
    message = c.execute(
        "SELECT m.content,m.author_id,m.focus_link_id,f.facts FROM private_conversation.messages m LEFT JOIN private_conversation.message_facts f USING(tenant_id,security_domain,conversation_id,message_id) WHERE m.tenant_id=%s AND m.security_domain=%s AND m.conversation_id=%s AND m.message_id=%s",
        (*scope, conversation, message_id),
    ).fetchone()
    require(
        message
        and message["author_id"] == ctx.principal_id
        and not (message["facts"] or {}).get("assistantResponse")
    )
    require(
        message["focus_link_id"] == presentation.focusLinkId
        and message["content"].strip()
    )
    claim = c.execute(
        "SELECT invocation_id FROM draft_assistance.idempotency_claims WHERE namespace=%s AND security_domain=%s AND initiating_principal_id=%s AND action='REQUEST_DRAFT_ASSISTANCE' AND scoped_idempotency_key=%s",
        (
            *scope,
            ctx.principal_id,
            "conversation:"
            + conversation_digest([conversation, message_id, request_key]),
        ),
    ).fetchone()
    require(claim is not None)
    invocation = PostgresDraftAssistanceRepository._latest(
        c, DraftScope(*scope), claim["invocation_id"]
    )
    require(
        invocation
        and invocation.snapshot
        and invocation.snapshot.adapter_revision
        in {REVISION, "v4-structured-conversation"}
    )
    g = read_grant(invocation)
    call.authority.require(
        OwnerPrincipal(ctx.principal_id, *scope), g.owner, g.action, g.exact_resource
    )
    require(callable(settlement_reader))
    settlement = settlement_reader(c, invocation)
    require(
        settlement.get("status") == "ESTIMATE_SETTLED"
        and settlement.get("reservation_retained") is False
    )
    expected = from_presentation(presentation, message_id)
    metadata, route = (
        invocation.conversation_context or {},
        invocation.conversation_route or {},
    )
    require(
        invocation.initiating_principal_id == ctx.principal_id
        and invocation.state.value == "SUCCEEDED"
        and invocation.result_kind is not None
        and invocation.result_kind.value == "CURRENT_QUESTION_ANSWER"
        and invocation.settlement_status == "ESTIMATE_SETTLED"
        and (invocation.local_cleanup or {}).get("reaped") is True
        and invocation.terminal_observation_id == invocation.last_observation_id
        and invocation.terminal_observation_id
        and invocation.admission_id
        and invocation.budget_reservation_id
        and all(
            metadata.get(k) == expected[k]
            for k in (
                "conversationId",
                "messageId",
                "contextDigest",
                "currentQuestionToken",
                "target",
            )
        )
        and route.get("relation") == "CURRENT_QUESTION"
        and route.get("contextDigest") == expected["contextDigest"]
        and route.get("currentQuestionToken") == presentation.currentQuestionToken
    )
    retained = c.execute(
        "SELECT facts FROM private_conversation.message_facts WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s AND facts->>'assistantResponse'='true' AND facts#>>'{source,invocationId}'=%s LIMIT 2",
        (*scope, conversation, invocation.invocation_id),
    ).fetchall()
    require(len(retained) == 1)
    facts = retained[0]["facts"]
    require(
        facts.get("invokedBy") == ctx.principal_id
        and facts.get("userMessageId") == message_id
        and facts.get("requestKey") == request_key
        and (facts.get("response") or {}).get("conversationRoute") == route
    )
    proof = dict(
        schemaVersion="fixed-question-understanding.v1",
        presentationId=presentation.presentationId,
        presentationDigest=presentation.digest,
        actorId=ctx.principal_id,
        executionSubject=identity.executionSubject,
        questionDigest=identity.questionDigest,
        invocationId=invocation.invocation_id,
        inputMessageId=message_id,
        inputDigest=native_digest(message["content"]),
        profileRevisionId=invocation.profile_revision_id,
        profileDigest=invocation.snapshot.profile_digest,
    )
    contract = presentation.question.get("answerContract")
    interpretation = None
    if contract is not None:
        try:
            validate_contract(contract)
            meaning = validate_meaning(route.get("questionAnswer"), contract)
        except ValueError as exc:
            raise AuthorityError("FIXED_QUESTION_INTERPRETATION_INVALID") from exc
        require(
            contract["sourceReference"]
            == identity.sourceSnapshot.model_dump(mode="json")
        )
        interpretation = dict(
            schemaVersion="native-verified-question-answer.v1",
            **meaning,
            invocationId=invocation.invocation_id,
            inputMessageId=message_id,
            inputDigest=proof["inputDigest"],
            profileRevisionId=invocation.profile_revision_id,
            profileDigest=invocation.snapshot.profile_digest,
            questionDigest=identity.questionDigest,
        )
        interpretation["interpretationDigest"] = native_digest(interpretation)
        proof["typedInterpretationDigest"] = interpretation["interpretationDigest"]
    else:
        require(route.get("questionAnswer") is None)
    proof["interpretationDigest"] = canonical_digest(proof)
    return message["content"], interpretation, proof
