"""Opt-in exact D9 creation binding, after the existing owner's grant check.

A pinned new case is independent of closed ARCH-323 continuity. This does not
issue a grant, adopt an old case, or authorize planning/execution.
"""

import hashlib

from pydantic import Field

from .authority_contracts import AuthorityError
from .plan_suggestion_domain import Digest, Identity, Immutable


class InitialCaseCreation(Immutable):
    tenant_id: Identity
    security_domain: Identity
    subject_id: Identity
    root_id: Identity
    title: str = Field(min_length=1, max_length=200)
    description_digest: Digest
    source_content_digest: Digest


def _exact_supplement_criterion(revision, expected):
    from .resource_use_domain import canonical_digest
    from .sales_gross_profit_evaluation import CHECKS, criterion_candidate
    from .sales_gross_profit_integration import SOURCE_DIGEST

    check = revision.get("applicability", {}).get("check")
    return (
        expected.source_content_digest == SOURCE_DIGEST
        and check in CHECKS
        and revision.get("revision") == 1
        and revision.get("predecessor_revision_id") is None
        and canonical_digest(
            {key: revision.get(key) for key in criterion_candidate(check)}
        )
        == canonical_digest(criterion_candidate(check))
    )


def bind_created_object(legacy, bindings, *, sales_supplement_enabled=False):
    def bind(connection, context, owner, result, **kwargs):
        revision = result["revision"]
        root = (
            revision.get("business_problem_id")
            if owner == "BUSINESS_PROBLEM"
            else kwargs.get("problem_id")
        )
        matches = [
            b
            for b in bindings
            if (b.tenant_id, b.security_domain, b.subject_id, b.root_id)
            == (
                context.scope.tenant_id,
                context.scope.security_domain,
                context.principal_id,
                root,
            )
        ]
        if not matches:
            return legacy(connection, context, owner, result, **kwargs)
        if len(matches) != 1 or revision["created_by"] != context.principal_id:
            raise AuthorityError("INITIAL_CASE_CREATION_DENIED")
        expected = matches[0]
        if owner == "BUSINESS_PROBLEM":
            if (
                kwargs.get("draft_invocation_id") is not None
                or revision["revision"] != 1
                or revision["title"] != expected.title
                or hashlib.sha256(revision["description"].encode()).hexdigest()
                != expected.description_digest
            ):
                raise AuthorityError("INITIAL_CASE_CREATION_DENIED")
        elif owner == "SUCCESS_CRITERION":
            from .sales_evaluation import CHECKS

            if sales_supplement_enabled and _exact_supplement_criterion(
                revision, expected
            ):
                return result
            if (
                revision["evaluator_type"] != "SYNTHETIC_SALES"
                or revision["evaluator_version"] != "1"
                or revision["applicability"].get("sourceContentDigest")
                != expected.source_content_digest
                or revision["applicability"].get("check") not in CHECKS
            ):
                raise AuthorityError("INITIAL_CASE_CRITERION_DENIED")
        else:
            raise AuthorityError("INITIAL_CASE_CREATION_DENIED")
        return result

    return bind
