"""Read-only requester provenance, never a permission or execution decision."""

from dataclasses import dataclass
from typing import Literal

AttributionKind = Literal["VERIFIED_REQUESTER", "DIRECT_START", "UNVERIFIED"]


@dataclass(frozen=True)
class Attribution:
    requested_by: str | None
    kind: AttributionKind


def requester(row, principal_id, *, administrator):
    """Validate existing immutable source facts after run READ authorization.

    Mirrors the exact context predicates of native_confirmed_scope._context_start.
    Unlike that execution helper, a legacy start never asserts a user question.
    No message text, lease renewal, grants or mutable journey state are involved.
    """
    sources = row.get("attribution_sources", [])
    if not sources:
        return Attribution(None, "UNVERIFIED" if row.get("origins") else "DIRECT_START")
    unknown = Attribution(None, "UNVERIFIED")
    if len(sources) != 1:
        return unknown
    source = sources[0]
    subject = source.get("subjectId")
    context = source.get("contextId")
    invocation = source.get("invocation") or {}
    if (
        not subject
        or not context
        or not source.get("conversationId")
        or source.get("conversationSchema") != 1
        or source.get("messageSchema") != 1
        or source.get("messageIsUser") is not True
        or source.get("messagePredatesRun") is not True
        or any(
            source.get(key) != subject
            for key in ("recordSubjectId", "conversationOwnerId", "messageAuthorId")
        )
        or source.get("recordContextId") != context
        or invocation.get("contextId") != context
        or invocation.get("initiatingPrincipalId") != subject
        or invocation.get("state") != "SUCCEEDED"
        or invocation.get("resultKind") != "DRAFT_READY"
        or any(
            not row.get(field) or invocation.get(key) != row[field]
            for key, field in (
                ("problemId", "business_problem_id"),
                ("problemRevisionId", "problem_revision_id"),
                ("problemDigest", "problem_digest"),
            )
        )
        or not (administrator or subject == principal_id)
    ):
        return unknown
    return Attribution(subject, "VERIFIED_REQUESTER")


def in_scope(scope, principal_id, requested_by, kind, start_actors):
    """Shared scope predicate for preselection, totals and pagination.

    Old direct-start tasks retain unique-actor membership without being labelled
    as verified original questions. Ambiguous/broken context never falls back.
    """
    return (
        scope == "visible"
        or (kind == "VERIFIED_REQUESTER" and requested_by == principal_id)
        or (kind == "DIRECT_START" and start_actors == [principal_id])
    )
