"""Recognize only the exact formal post-result problem-link CAS successor."""


def same_result_after_problem_link(c, context, value, recorded_version, problem_id):
    if value.aggregate_version == recorded_version:
        return True
    if value.aggregate_version != recorded_version + 1:
        return False
    rows = c.execute(
        "SELECT aggregate_version,record FROM draft_assistance.invocation_versions "
        "WHERE namespace=%s AND security_domain=%s AND invocation_id=%s "
        "AND aggregate_version BETWEEN %s AND %s ORDER BY aggregate_version",
        (
            context.scope.tenant_id,
            context.scope.security_domain,
            value.invocation_id,
            recorded_version,
            value.aggregate_version,
        ),
    ).fetchall()
    if len(rows) != 2:
        return False
    before, after = rows[0]["record"], rows[1]["record"]
    links = ("problemId", "problemRevisionId", "problemDigest")
    if (
        before.get("aggregateVersion") != recorded_version
        or any(before.get(key) is not None for key in links)
        or after.get("problemId") != problem_id
        or not all(after.get(key) for key in links)
    ):
        return False
    expected = {**before, "aggregateVersion": recorded_version + 1}
    expected.update({key: after[key] for key in links})
    if after != expected:
        return False
    receipt = c.execute(
        "SELECT cr.revision_id,cr.revision_digest FROM "
        "business_problem_authority.creator_receipts cr JOIN "
        "business_problem_authority.problem_revisions pr ON "
        "pr.namespace=cr.namespace AND pr.security_domain=cr.security_domain "
        "AND pr.business_problem_id=cr.business_problem_id "
        "AND pr.revision_id=cr.revision_id AND pr.digest=cr.revision_digest "
        "WHERE cr.namespace=%s AND cr.security_domain=%s "
        "AND cr.business_problem_id=%s AND cr.creator_principal_id=%s "
        "AND pr.created_by=%s AND cr.revision=1 AND pr.revision=1",
        (
            context.scope.tenant_id,
            context.scope.security_domain,
            problem_id,
            context.principal_id,
            context.principal_id,
        ),
    ).fetchone()
    return bool(
        receipt
        and (value.problem_id, value.problem_revision_id, value.problem_digest)
        == (problem_id, receipt["revision_id"], receipt["revision_digest"])
        and (after["problemRevisionId"], after["problemDigest"])
        == (receipt["revision_id"], receipt["revision_digest"])
    )
