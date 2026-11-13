# ruff: noqa: E501 -- Exact scoped owner queries.
"""Private failed-understanding successor checks; no model or authorization issuer."""

from .draft_assistance import DraftAssistanceError
from .private_conversation import digest


def require(condition, reason="CONVERSATION_FAILED_RETRY_CONTEXT_CHANGED"):
    if not condition:
        raise DraftAssistanceError(reason)


def successor_key(invocation_id):
    return "failed-understanding:" + digest(["v1", invocation_id])


def settled_failure(invocation):
    return (
        invocation.state.value == "FAILED"
        and invocation.reason_code == "OUTPUT_SCHEMA_INVALID"
        and invocation.settlement_status == "ESTIMATE_SETTLED"
        and bool((invocation.local_cleanup or {}).get("reaped"))
        and bool(invocation.terminal_observation_id)
    )


def require_snapshot(
    invocation, *, subject, conversation, message_id, snapshot, source
):
    metadata = invocation.conversation_context or {}
    target = metadata.get("target") or {}
    require(settled_failure(invocation), "CONVERSATION_FAILED_RETRY_NOT_SETTLED")
    require(
        invocation.initiating_principal_id == subject
        and metadata.get("conversationId") == conversation
        and metadata.get("messageId") == message_id
        and target.get("kind") == "UNDERSTANDING"
        and isinstance(snapshot, dict)
        and snapshot.get("conversationId") == conversation
        and snapshot.get("messageId") == message_id
        and snapshot.get("target") == target
        and snapshot.get("contextDigest") == metadata.get("contextDigest")
        and snapshot.get("currentQuestionToken") == metadata.get("currentQuestionToken")
        and source == invocation.input_source
    )
    return target


def require_retry_claim(connection, candidate):
    """Caller transaction owns the new idempotency claim; failures roll it back.

    Conversation lock precedes original question-context lock (the latter remains
    in require_unconsumed_question). No external calls or model work occur here.
    """
    metadata = candidate.conversation_context or {}
    original_id = metadata.get("failedRetryOf")
    if original_id is None:
        return
    from .draft_assistance_postgres import PostgresDraftAssistanceRepository

    scope = candidate.scope
    conversation, message_id = metadata.get("conversationId"), metadata.get("messageId")
    row = connection.execute(
        "SELECT owner_id,archived_at FROM private_conversation.conversations "
        "WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s FOR UPDATE",
        (scope.namespace, scope.security_domain, conversation),
    ).fetchone()
    require(
        row is not None
        and row["owner_id"] == candidate.initiating_principal_id
        and row["archived_at"] is None
    )
    original = PostgresDraftAssistanceRepository._latest(connection, scope, original_id)
    require(original is not None, "CONVERSATION_FAILED_RETRY_NOT_FOUND")
    require_snapshot(
        original,
        subject=candidate.initiating_principal_id,
        conversation=conversation,
        message_id=message_id,
        snapshot=metadata,
        source=candidate.input_source,
    )
    require(
        candidate.scoped_idempotency_key
        == "conversation:"
        + digest([conversation, message_id, successor_key(original_id)])
    )
    user = connection.execute(
        "SELECT m.author_id,m.content,f.message_id AS assistant_fact FROM private_conversation.messages m "
        "LEFT JOIN private_conversation.message_facts f ON f.tenant_id=m.tenant_id "
        "AND f.security_domain=m.security_domain AND f.conversation_id=m.conversation_id "
        "AND f.message_id=m.message_id AND f.facts->>'assistantResponse'='true' "
        "WHERE m.tenant_id=%s AND m.security_domain=%s AND m.conversation_id=%s AND m.message_id=%s",
        (scope.namespace, scope.security_domain, conversation, message_id),
    ).fetchone()
    require(
        user is not None
        and user["author_id"] == candidate.initiating_principal_id
        and user["assistant_fact"] is None
    )
    require(metadata.get("failedRetryInputDigest") == digest(user["content"]))
    journal = connection.execute(
        "SELECT version,state FROM private_conversation.journeys WHERE tenant_id=%s "
        "AND security_domain=%s AND conversation_id=%s FOR UPDATE",
        (scope.namespace, scope.security_domain, conversation),
    ).fetchone()
    target = metadata["target"]
    state = (journal or {}).get("state") or {}
    draft = state.get("draft") or {}
    require(
        journal is not None
        and journal["version"] == target.get("journalVersion")
        and state.get("key") == target.get("journeyKey")
        and state.get("phase") == "CLARIFY"
        and not state.get("pending")
        and not state.get("error")
        and not state.get("execution")
        and all(
            draft.get(k) == target.get(k) and target.get(k) is not None
            for k in (
                "invocationId",
                "contextId",
                "turnId",
                "turnVersion",
                "aggregateVersion",
            )
        )
    )
    # Selected source is also verified by the existing source owner before model
    # admission; pin the current journal selection here against concurrent edits.
    source = state.get("source")
    require(isinstance(source, dict) and isinstance(candidate.input_source, dict))
    require(
        all(
            source.get(k) == candidate.input_source.get(k)
            for k in ("source", "sourceContentDigest")
        )
    )


def verified_retry_metadata(connection, actual, current):
    """Revalidate immutable failed origin and current owner before adoption."""
    require_retry_claim(connection, actual)
    from .draft_assistance_postgres import PostgresDraftAssistanceRepository

    metadata = actual.conversation_context
    original = PostgresDraftAssistanceRepository._latest(
        connection, actual.scope, metadata["failedRetryOf"]
    )
    require_snapshot(
        original,
        subject=actual.initiating_principal_id,
        conversation=metadata["conversationId"],
        message_id=metadata["messageId"],
        snapshot=current,
        source=actual.input_source,
    )
    return {
        **current,
        "failedRetryOf": original.invocation_id,
        "failedRetryInputDigest": metadata["failedRetryInputDigest"],
    }


def discover(
    actions,
    context,
    conversation,
    service,
    service_for,
    payload,
    routing_reader,
    source_reader,
):
    """Bounded current-authorized failure projection; never resumes an invocation."""
    from .conversation_source_input import bind_attachment, current_source_metadata
    from .draft_assistance import DraftScope

    with actions.records.connect() as c:
        owned = actions.records.owned(c, context, conversation)
        require(owned["archived_at"] is None, "CONVERSATION_ARCHIVED")
        candidates = c.execute(
            "SELECT x.record,m.content AS original_text FROM draft_assistance.invocations i "
            "JOIN LATERAL (SELECT record FROM draft_assistance.invocation_versions v WHERE "
            "v.namespace=i.namespace AND v.security_domain=i.security_domain AND v.invocation_id=i.invocation_id "
            "ORDER BY aggregate_version DESC LIMIT 1) x ON true "
            "JOIN private_conversation.messages m ON m.tenant_id=i.namespace AND m.security_domain=i.security_domain "
            "AND m.conversation_id=%s AND m.message_id=x.record->'conversationContext'->>'messageId' "
            "WHERE i.namespace=%s AND i.security_domain=%s AND i.initiating_principal_id=%s "
            "AND m.author_id=%s AND x.record->'conversationContext'->>'conversationId'=%s "
            "AND x.record->>'state'='FAILED' AND x.record->>'reasonCode'='OUTPUT_SCHEMA_INVALID' "
            "AND NOT EXISTS(SELECT 1 FROM private_conversation.message_facts f WHERE f.tenant_id=m.tenant_id "
            "AND f.security_domain=m.security_domain AND f.conversation_id=m.conversation_id "
            "AND f.message_id=m.message_id AND f.facts->>'assistantResponse'='true') "
            "ORDER BY i.created_at DESC,i.invocation_id DESC LIMIT 21",
            (
                conversation,
                *actions.records.scope(context),
                context.principal_id,
                context.principal_id,
                conversation,
            ),
        ).fetchall()
    items = []
    incomplete = len(candidates) > 20
    for row in candidates[:20]:
        record = row["record"]
        identity = record["invocationId"]
        try:
            response = service_for(context, identity).read(context, identity)
            invocation = response.invocation
            require(invocation.initiating_principal_id == context.principal_id)
            metadata = invocation.conversation_context or {}
            require(metadata.get("conversationId") == conversation)
            if (
                invocation.state.value != "FAILED"
                or invocation.reason_code != "OUTPUT_SCHEMA_INVALID"
            ):
                continue
            message_id = metadata["messageId"]
            eligible = False
            if settled_failure(invocation) and routing_reader and source_reader:
                try:
                    snapshot = routing_reader(
                        context, conversation, message_id, service
                    )
                    with bind_attachment(
                        source_reader(context, conversation, message_id)
                    ):
                        source = current_source_metadata()
                    require_snapshot(
                        invocation,
                        subject=context.principal_id,
                        conversation=conversation,
                        message_id=message_id,
                        snapshot=snapshot,
                        source=source,
                    )
                    eligible = True
                except Exception:
                    eligible = False
            new_key = successor_key(identity)
            successor = service.repository.get_by_key(
                DraftScope.from_context(context),
                context.principal_id,
                "conversation:" + digest([conversation, message_id, new_key]),
            )
            successor_value = None
            if successor is not None:
                successor_value = payload(
                    service_for(context, successor.invocation_id).read(
                        context, successor.invocation_id
                    )
                )["result"]
                from .conversation_answer_retention import read_retained

                successor_value = read_retained(
                    actions,
                    context,
                    conversation,
                    successor_value,
                    request_key=new_key,
                    message_id=message_id,
                )
                eligible = False
            items.append(
                {
                    "invocationId": identity,
                    "messageId": message_id,
                    "originalText": row["original_text"],
                    "state": invocation.state.value,
                    "reasonCode": invocation.reason_code,
                    "target": metadata.get("target"),
                    "inputSource": invocation.input_source,
                    "continuationEligible": eligible,
                    "successorRequestKey": new_key,
                    "successor": successor_value,
                    "settlementStatus": invocation.settlement_status,
                    "localWorkerState": "REAPED"
                    if (invocation.local_cleanup or {}).get("reaped")
                    else "NOT_PROVEN",
                }
            )
        except Exception:
            incomplete = True
    return {"items": items, "complete": not incomplete, "modelDispatched": False}


def retry_content(actions, context, conversation, message_id, content):
    import json

    with actions.records.connect() as c:
        actions.records.owned(c, context, conversation)
        row = c.execute(
            "SELECT content,author_id FROM private_conversation.messages WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s AND message_id=%s",
            (*actions.records.scope(context), conversation, message_id),
        ).fetchone()
    require(row is not None and row["author_id"] == context.principal_id)
    expected = {
        "schemaVersion": "conversation-understanding-context.v2",
        "uiRevision": 1,
        "messages": [{"id": "user:" + message_id, "text": row["content"]}],
        "currentDraft": None,
        "previousUnderstanding": None,
        "previousQuestion": None,
        "previousAssistantResponse": None,
    }
    try:
        value = json.loads(content)
    except (ValueError, TypeError):
        raise DraftAssistanceError("CONVERSATION_FAILED_RETRY_INPUT_CHANGED") from None
    require(value == expected, "CONVERSATION_FAILED_RETRY_INPUT_CHANGED")
    return digest(row["content"])


def begin_retry(service, context, **kwargs):
    """Concurrent claimant may exist before its exact READ grant is installed.

    Do not disclose or authorize that invocation. Report only an uncertain
    in-progress request, preserving the key for normal authorized GET recovery.
    """
    from .conversation_experience_admission import begin_bound
    from .draft_assistance import DraftScope

    try:
        return begin_bound(service, context, **kwargs)
    except DraftAssistanceError as exc:
        if exc.reason_code != "DRAFT_ASSISTANCE_NOT_FOUND":
            raise
        existing = service.repository.get_by_key(
            DraftScope.from_context(context), context.principal_id, kwargs["key"]
        )
        if existing is not None and (existing.conversation_context or {}).get(
            "failedRetryOf"
        ):
            raise DraftAssistanceError("CONVERSATION_FAILED_RETRY_IN_PROGRESS") from exc
        raise
