"""Exact persisted conversation link, under the current-work visibility policy.

Caller must already authorize the exact execution and its parent resources.
The task page independently revalidates this navigation hint before use.
"""

from .development_administrator import for_call


def read_execution_origin(call, digest, problem_id):
    row = call.connection.execute(
        """
        SELECT l.conversation_id,
          coalesce(j.state->>'execution'=%s,false) AS verified
        FROM private_conversation.links l
        JOIN private_conversation.conversations c
          USING(tenant_id,security_domain,conversation_id)
        LEFT JOIN private_conversation.journeys j
          USING(tenant_id,security_domain,conversation_id)
        WHERE l.tenant_id=%s AND l.security_domain=%s
          AND c.schema_version=1 AND (c.owner_id=%s OR %s)
          AND l.target->>'problemId'=%s
          AND (l.target->>'executionDigest'=%s OR (
            l.target->>'executionDigest' IS NULL
            AND j.state->>'execution'=%s
            AND j.state#>>'{problem,business_problem_id}'=%s))
        ORDER BY verified DESC,l.created_at,l.conversation_id,l.link_id
        LIMIT 1
        """,
        (
            digest,
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
            call.context.principal_id,
            for_call(call),
            problem_id,
            digest,
            digest,
            problem_id,
        ),
    ).fetchone()
    return {
        "originConversationId": row["conversation_id"] if row else None,
        "originVerified": bool(row and row["verified"]),
    }
