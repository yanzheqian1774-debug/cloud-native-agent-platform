"""Allowlisted facts for an already-authorized exact Skill revision."""

from .skill_resource_testing import coverage


def version_basis(record, revision):
    """No input/output, raw errors, policy internals or adjacent-version facts."""
    revision_id, digest = revision["revisionId"], revision["digest"]
    tests = coverage(record, revision)
    checks = tests["checks"]
    publications = [
        fact
        for fact in record.get("facts", [])
        if fact.get("event") == "REVISION_PUBLISHED"
        and fact.get("subject", {}).get("revisionId") == revision_id
        and fact.get("subject", {}).get("digest") == digest
    ]
    reviews = [
        review
        for review in record.get("reviews", [])
        if review.get("revisionId") == revision_id
        and review.get("digest") == digest
        and review.get("decision") == "APPROVED"
    ]
    publication = publications[-1] if publications else None
    review = reviews[-1] if reviews else None
    basis_type = (
        "POLICY"
        if review and review.get("policyBasis", {}).get("type") == "POLICY"
        else "HUMAN"
        if review
        and not review.get("policyBasis")
        and str(review.get("actor", "")).startswith("human:")
        else "UNKNOWN"
    )
    return {
        "schemaVersion": "resource-version-basis.v1",
        "revisionId": revision_id,
        "revisionDigest": digest,
        "executionAuthority": "NONE",
        "businessAcceptance": "NOT_ESTABLISHED",
        "validation": {
            "validatedAt": revision.get("validatedAt"),
            "errorCount": len(revision.get("validationErrors", [])),
        },
        "tests": {
            "scope": "ISOLATED_SYNTHETIC_ONLY_NOT_BUSINESS_ACCEPTANCE",
            "ready": tests["ready"],
            "operations": [
                {
                    "operation": check["operation"],
                    "passed": check["passed"],
                    "caseCount": len(check["cases"]),
                }
                for check in checks
            ],
        },
        "publication": {
            "recorded": publication is not None,
            "publishedAt": publication["subject"].get("publishedAt")
            if publication
            else None,
            "basisType": basis_type if publication else "UNKNOWN",
        },
    }
