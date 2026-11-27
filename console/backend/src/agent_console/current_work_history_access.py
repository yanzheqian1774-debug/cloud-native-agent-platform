"""Bounded explicit preparation of existing owned task-history READ rights."""

from .authority_contracts import AuthorityError
from .conversation_history_access import prepare
from .private_conversation import ConversationError

LIMIT = 20


def prepare_directory(service, records, authorizer, context, after=None):
    with (
        authorizer.controller.protected_request(),
        service.repository.connection_scope() as c,
    ):
        policy = service.experience
        if policy is None or policy.document.historyReadEnabled is not True:
            return {"available": False, "hasMore": False, "partial": False}
        policy._require(service, c, context)
        anchor = None
        if after is not None:
            anchor = c.execute(
                "SELECT created_at,conversation_id "
                "FROM private_conversation.conversations "
                "WHERE tenant_id=%s AND security_domain=%s AND owner_id=%s "
                "AND conversation_id=%s",
                (*records.scope(context), context.principal_id, after),
            ).fetchone()
            if not anchor:
                raise AuthorityError("CONVERSATION_HISTORY_SCOPE_DENIED")
        from .conversation_goal_selection import journal_relation

        rows = c.execute(
            "SELECT DISTINCT v.conversation_id,v.created_at "
            "FROM private_conversation.conversations v "
            f"JOIN {journal_relation(c)} j "
            "USING(tenant_id,security_domain,conversation_id) "
            "WHERE v.tenant_id=%s AND v.security_domain=%s AND v.owner_id=%s "
            "AND v.archived_at IS NULL AND jsonb_typeof(j.state->'problem')='object' "
            "AND length(j.state->>'execution')=64 AND EXISTS(SELECT 1 FROM "
            "private_conversation.links l WHERE l.tenant_id=v.tenant_id "
            "AND l.security_domain=v.security_domain "
            "AND l.conversation_id=v.conversation_id "
            "AND l.target->>'problemId'=j.state->'problem'->>'business_problem_id') "
            + ("AND (v.created_at,v.conversation_id)<(%s,%s) " if anchor else "")
            + "ORDER BY v.created_at DESC,v.conversation_id DESC LIMIT %s",
            (
                *records.scope(context),
                context.principal_id,
                *((anchor["created_at"], anchor["conversation_id"]) if anchor else ()),
                LIMIT + 1,
            ),
        ).fetchall()
    partial = len(rows) > LIMIT
    prepared = 0
    for row in rows[:LIMIT]:
        try:
            with (
                authorizer.controller.protected_request(),
                service.repository.connection_scope() as c,
            ):
                # Selection is only a hint: archive/ownership/lineage and current
                # permissions are all checked again by the original owner.
                # Preserve the original owner's policy/session -> conversation
                # lock order; do not acquire the conversation lock first.
                service.experience._require(service, c, context)
                current = records.owned(c, context, row["conversation_id"], lock=True)
                if (
                    current["owner_id"] != context.principal_id
                    or current["archived_at"]
                ):
                    partial = True
                    continue
                result = prepare(service, records, context, row["conversation_id"], c)
            complete = result["available"] and all(
                item["state"] in {"EFFECTIVE", "APPROVED"} for item in result["items"]
            )
            prepared += int(complete)
            partial |= not complete
        except (AuthorityError, ConversationError):
            partial = True
    return {
        "available": True,
        "hasMore": len(rows) > LIMIT,
        "partial": partial,
        "nextConversationId": rows[LIMIT - 1]["conversation_id"]
        if len(rows) > LIMIT
        else None,
        "checked": min(len(rows), LIMIT),
        "prepared": prepared,
        "failed": min(len(rows), LIMIT) - prepared,
    }
