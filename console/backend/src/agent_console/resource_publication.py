"""Current eligibility and exact owner publication proof, without upgrading refs."""


def same_digest(a, b):
    return (
        isinstance(a, str)
        and isinstance(b, str)
        and a.removeprefix("sha256:") == b.removeprefix("sha256:")
    )


def publication_proven(record, revision):
    """Old heads require the owner's retained exact publication fact."""
    for fact in record.get("facts", []):
        if fact.get("event") not in {"REVISION_PUBLISHED", "KNOWLEDGE_PUBLISHED"}:
            continue
        subject = fact.get("subject", fact)
        if subject.get("revisionId") == revision.get("revisionId") and same_digest(
            subject.get("digest"), revision.get("digest")
        ):
            return True
    return False


def eligible(record, revision, ref, *, frozen=False):
    return bool(
        revision
        and same_digest(revision.get("digest"), ref.digest)
        and revision.get("state") == "PUBLISHED"
        and record.get("enabled", True) is True
        and not record.get("archived")
        and record.get("publishedRevisionId") is not None
        and record.get("lifecycleState")
        not in {
            "DEPRECATED",
            "ARCHIVED",
            "REVOKED",
            "DISABLED",
            "UNPUBLISHED",
            "NOT_PUBLISHED",
        }
        and (
            record.get("publishedRevisionId") == ref.revision_id
            or (frozen and publication_proven(record, revision))
        )
    )
