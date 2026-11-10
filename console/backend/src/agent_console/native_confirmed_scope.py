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
    messages = connection.execute(
        """SELECT message_id,content,request_digest,sequence
        FROM private_conversation.messages
        WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s
          AND author_id=%s AND schema_version=1 AND created_at<=%s
        ORDER BY sequence LIMIT 33""",
        (
            preparation.namespace,
            preparation.security_domain,
            origin["conversation_id"],
            principal,
            origin["created_at"],
        ),
    ).fetchall()
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
