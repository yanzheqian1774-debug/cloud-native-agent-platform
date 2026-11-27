"""Explicit private goal journals; no automatic classification or execution."""

from fastapi import Query, Request
from pydantic import Field

from . import conversation_goal_slots as slots
from .conversation_goal_adoption import AdoptGoal, from_app
from .workbench_bff_schemas import StrictWorkbenchModel


class SaveGoalJournal(StrictWorkbenchModel):
    expectedVersion: int = Field(ge=0)
    state: dict


def _view(c, records, ctx, conversation, goal):
    original = slots.owned(c, records, ctx, conversation, goal)
    return {
        **slots.read(c, records, ctx, conversation, goal),
        "goalId": goal,
        "goalDigest": original["record_digest"],
        "rootMessageId": original["root_message_id"],
        "goalMode": "INDEPENDENT_GOAL",
    }


def install(app, records, safe):
    def adopting():
        owner = from_app(app)
        slots.require(owner is not None, "CONVERSATION_GOAL_ADOPTION_UNAVAILABLE")
        return owner

    @app.post("/api/workbench/v1/conversations/{conversation}/goals/adoptions")
    def adopt(request: Request, conversation: str, body: AdoptGoal):
        return safe(
            request, lambda ctx: adopting().apply(ctx, conversation, body), True
        )

    @app.get("/api/workbench/v1/conversations/{conversation}/goals/adoptions")
    def adoption_receipt(
        request: Request,
        conversation: str,
        commandId: str = Query(min_length=1, max_length=128),
    ):
        return safe(request, lambda ctx: adopting().read(ctx, conversation, commandId))

    @app.post("/api/workbench/v1/conversations/{conversation}/goals")
    def create(request: Request, conversation: str, body: slots.CreateGoal):
        def operation(ctx):
            with records.connect() as c:
                return slots.create(c, records, ctx, conversation, body)

        return safe(request, operation, True)

    @app.get("/api/workbench/v1/conversations/{conversation}/goals")
    def receipt(
        request: Request,
        conversation: str,
        commandId: str | None = Query(default=None, min_length=1, max_length=128),
        cursor: str | None = Query(default=None, min_length=1, max_length=128),
    ):
        def operation(ctx):
            with records.connect() as c:
                slots.require_schema(c)
                chat = records.owned(c, ctx, conversation)
                slots.require(
                    chat["owner_id"] == ctx.principal_id and not chat["archived_at"]
                )
                key = (*records.scope(ctx), conversation)
                if commandId is not None:
                    slots.require(cursor is None, "CONVERSATION_GOAL_QUERY_INVALID")
                    row = c.execute(
                        "SELECT goal_id FROM conversation_goals.slots "
                        "WHERE tenant_id=%s AND security_domain=%s "
                        "AND conversation_id=%s AND command_key=%s",
                        (*key, commandId),
                    ).fetchone()
                    if row is None:
                        return {
                            "state": "NOT_RECORDED",
                            "conversationId": conversation,
                            "commandId": commandId,
                        }
                    value = slots.owned(c, records, ctx, conversation, row["goal_id"])
                    return {
                        "state": "RECORDED",
                        "conversationId": conversation,
                        "commandId": commandId,
                        "goalId": value["goal_id"],
                        "goalDigest": value["record_digest"],
                    }
                anchor = (
                    slots.owned(c, records, ctx, conversation, cursor)
                    if cursor is not None
                    else None
                )
                rows = c.execute(
                    "SELECT g.goal_id FROM conversation_goals.slots g "
                    "WHERE g.tenant_id=%s AND g.security_domain=%s AND "
                    "g.conversation_id=%s "
                    "AND EXISTS (SELECT 1 FROM conversation_goals.claimed_messages m "
                    "JOIN authorization_admin.context_call_objects o ON "
                    "o.tenant_id=m.tenant_id "
                    "AND o.security_domain=m.security_domain AND "
                    "o.invocation_id=m.invocation_id "
                    "JOIN authorization_admin.context_call_requests r ON "
                    "r.context_id=o.context_id "
                    "WHERE m.tenant_id=g.tenant_id AND "
                    "m.security_domain=g.security_domain "
                    "AND m.conversation_id=g.conversation_id AND (m.goal_id=g.goal_id "
                    "OR EXISTS (SELECT 1 FROM conversation_goals.result_adoptions a "
                    "WHERE a.tenant_id=g.tenant_id "
                    "AND a.security_domain=g.security_domain "
                    "AND a.conversation_id=g.conversation_id AND a.goal_id=g.goal_id "
                    "AND a.invocation_id=m.invocation_id)) "
                    "AND o.owner='BUSINESS_PROBLEM' AND r.subject_id=g.owner_id "
                    "AND r.tenant_id=g.tenant_id AND "
                    "r.security_domain=g.security_domain "
                    "AND r.record->>'conversation_id'=g.conversation_id) "
                    + ("AND (g.created_at,g.goal_id)<(%s,%s) " if anchor else "")
                    + "ORDER BY g.created_at DESC,g.goal_id DESC LIMIT 21",
                    (*key, *((anchor["created_at"], cursor) if anchor else ())),
                ).fetchall()
                items = []
                for row in rows[:20]:
                    value = slots.owned(c, records, ctx, conversation, row["goal_id"])
                    message = c.execute(
                        "SELECT content,author_id FROM private_conversation.messages "
                        "WHERE tenant_id=%s AND security_domain=%s "
                        "AND conversation_id=%s AND message_id=%s",
                        (*key, value["root_message_id"]),
                    ).fetchone()
                    slots.require(message and message["author_id"] == ctx.principal_id)
                    items.append(
                        {
                            "goalId": value["goal_id"],
                            "goalDigest": value["record_digest"],
                            "rootMessageId": value["root_message_id"],
                            "createdAt": value["created_at"],
                            "title": message["content"],
                        }
                    )
                return {
                    "conversationId": conversation,
                    "items": items,
                    "hasMore": len(rows) > 20,
                    "nextCursor": rows[19]["goal_id"] if len(rows) > 20 else None,
                }

        return safe(request, operation)

    @app.get("/api/workbench/v1/conversations/{conversation}/goals/{goal}/journey")
    def read(request: Request, conversation: str, goal: str):
        def operation(ctx):
            with records.connect() as c:
                return _view(c, records, ctx, conversation, goal)

        return safe(request, operation)

    @app.post("/api/workbench/v1/conversations/{conversation}/goals/{goal}/journey")
    def save(request: Request, conversation: str, goal: str, body: SaveGoalJournal):
        def operation(ctx):
            with records.connect() as c:
                slots.save(
                    c,
                    records,
                    ctx,
                    conversation,
                    goal,
                    body.expectedVersion,
                    body.state,
                )
                return _view(c, records, ctx, conversation, goal)

        return safe(request, operation, True)
