# ruff: noqa: RUF001 -- Explicit Chinese punctuation in user instructions.
"""Read bounded original-user scope evidence; never synthesize an answer."""

import re

from agent_runtime.native_loop import digest


def classify_scope(messages, scopes):
    """Recognize direct instructions only, not document prose or guessed intent."""
    available = tuple(dict.fromkeys(scopes))
    mentioned, selected = set(), []
    uncertain = False
    for message in messages:
        for clause in re.split(r"[。；;\n]", message["content"]):
            present = {scope for scope in available if scope in clause}
            if not present:
                continue
            mentioned.update(present)
            # Negation of the scope is different from a no-deployment constraint.
            negative = any(
                re.search(
                    r"(?:不要|别按|不按|不是|并非|不能|不用).{0,12}" + re.escape(scope),
                    clause,
                )
                or re.search(
                    r"\b(?:not|don't)\s+(?:(?:use|apply)\s+)?" + re.escape(scope),
                    clause,
                    re.IGNORECASE,
                )
                for scope in present
            )
            if negative or re.search(
                r"不确定|未确定|待确认|是否|可能|还是|或者|\b(?:maybe|whether|or)\b",
                clause,
                re.IGNORECASE,
            ):
                uncertain = True
                continue
            for scope in present:
                prefix = r"^\s*(?:(?:请|帮我|麻烦|本次|这次|仅)\s*)*"
                affirmative = re.search(
                    prefix
                    + r"(?:按|按照|使用|采用|依据)\s*[“「\"]?"
                    + re.escape(scope)
                    + r"(?=交接规范|规范|范围|\s|[，,。；;]|$)",
                    clause,
                ) or re.search(
                    r"^\s*(?:please\s+)?(?:use|apply)\s+"
                    + re.escape(scope)
                    + r"(?:\b|$)",
                    clause,
                    re.IGNORECASE,
                )
                if affirmative:
                    selected.append((scope, message["message_id"]))
    chosen = {scope for scope, _ in selected}
    if uncertain or len(mentioned) > 1 or len(chosen) != 1:
        return None
    scope = next(iter(chosen))
    return {
        "scope": scope,
        "messageIds": sorted({key for value, key in selected if value == scope}),
    }


def _context_start(connection, preparation, principal, origin):
    """Resolve immutable owner lineage; a conversation alone is not a work boundary."""
    tables = connection.execute(
        "SELECT to_regclass('authorization_admin.context_call_objects') AS objects, "
        "to_regclass('authorization_admin.context_call_requests') AS requests, "
        "to_regclass('draft_assistance.invocation_versions') AS invocations"
    ).fetchone()
    if not any(tables.values()):
        return {"legacy": True}
    if not all(tables.values()):
        return None
    rows = connection.execute(
        "SELECT o.context_id,o.invocation_id,r.subject_id,r.record FROM "
        "authorization_admin.context_call_objects o JOIN "
        "authorization_admin.context_call_requests r ON r.context_id=o.context_id "
        "AND r.tenant_id=o.tenant_id AND r.security_domain=o.security_domain "
        "WHERE o.tenant_id=%s AND o.security_domain=%s "
        "AND o.owner='BUSINESS_PROBLEM' AND o.resource_id=%s LIMIT 2",
        (
            preparation.namespace,
            preparation.security_domain,
            preparation.semantics.target.problem.resource_id,
        ),
    ).fetchall()
    if not rows:
        return {"legacy": True}
    if len(rows) != 1:
        return None
    row = rows[0]
    record = row["record"]
    if (
        row["subject_id"] != principal
        or record.get("subject_id") != principal
        or record.get("context_id") != row["context_id"]
        or record.get("conversation_id") != origin["conversation_id"]
    ):
        return None
    invocation = connection.execute(
        "SELECT record FROM draft_assistance.invocation_versions WHERE "
        "namespace=%s AND security_domain=%s AND invocation_id=%s "
        "ORDER BY aggregate_version DESC LIMIT 1",
        (preparation.namespace, preparation.security_domain, row["invocation_id"]),
    ).fetchone()
    value = invocation["record"] if invocation else {}
    if (
        value.get("state") != "SUCCEEDED"
        or value.get("resultKind") != "DRAFT_READY"
        or value.get("contextId") != row["context_id"]
        or value.get("initiatingPrincipalId") != principal
        or (
            value.get("problemId"),
            value.get("problemRevisionId"),
            value.get("problemDigest"),
        )
        != (
            preparation.semantics.target.problem.resource_id,
            preparation.semantics.target.problem.revision_id,
            preparation.semantics.target.problem.digest,
        )
    ):
        return None
    first = connection.execute(
        "SELECT sequence FROM private_conversation.messages WHERE "
        "tenant_id=%s AND security_domain=%s AND conversation_id=%s "
        "AND message_id=%s AND author_id=%s AND schema_version=1 AND created_at<=%s",
        (
            preparation.namespace,
            preparation.security_domain,
            origin["conversation_id"],
            record.get("first_user_message_id", ""),
            principal,
            origin["created_at"],
        ),
    ).fetchone()
    if first is None:
        return None
    return {"legacy": False, "sequence": first["sequence"]}


def read_confirmed_scope(connection, preparation, principal, scopes):
    """Owner-scoped exact Problem lineage; ambiguous origins require clarification."""
    problem = preparation.semantics.target.problem
    origins = connection.execute(
        """SELECT l.conversation_id,l.link_id,l.created_at
        FROM private_conversation.links l
        JOIN private_conversation.conversations c
          USING(tenant_id,security_domain,conversation_id)
        WHERE l.tenant_id=%s AND l.security_domain=%s
          AND c.owner_id=%s AND l.created_by=%s
          AND c.schema_version=1 AND l.schema_version=1
          AND l.target->>'problemId'=%s
          AND l.target->>'revisionId'=%s
          AND l.target->>'problemDigest'=%s
        ORDER BY l.created_at,l.link_id LIMIT 2""",
        (
            preparation.namespace,
            preparation.security_domain,
            principal,
            principal,
            problem.resource_id,
            problem.revision_id,
            problem.digest,
        ),
    ).fetchall()
    if len(origins) != 1:
        return None
    origin = origins[0]
    start = _context_start(connection, preparation, principal, origin)
    if start is None:
        return None
    messages = connection.execute(
        """SELECT message_id,content,request_digest,sequence
        FROM private_conversation.messages
        WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s
          AND author_id=%s AND schema_version=1 AND created_at<=%s
          AND sequence >= %s
        ORDER BY sequence LIMIT 33""",
        (
            preparation.namespace,
            preparation.security_domain,
            origin["conversation_id"],
            principal,
            origin["created_at"],
            start.get("sequence", 0),
        ),
    ).fetchall()
    if start["legacy"] and len(messages) != 1:
        return None
    if len(messages) > 32 or sum(len(m["content"]) for m in messages) > 32768:
        return None
    choice = classify_scope(messages, scopes)
    if choice is None:
        return None
    return {
        "schemaVersion": "native-confirmed-scope.v1",
        "scope": choice["scope"],
        "conversationId": origin["conversation_id"],
        "linkId": origin["link_id"],
        "principal": principal,
        "problem": problem.model_dump(mode="json"),
        "messages": [
            {
                "messageId": m["message_id"],
                "contentDigest": digest(m["content"]),
                "requestDigest": m["request_digest"],
            }
            for m in messages
        ],
        "affirmativeMessageIds": choice["messageIds"],
        "authority": "USER_SCOPE_CONTEXT_ONLY_NOT_PERMISSION",
    }
