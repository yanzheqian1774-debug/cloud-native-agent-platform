# ruff: noqa: E501 -- Preserve the existing exact scoped SQL statements.
"""Batched already-authorized terminal snapshot reads on the caller transaction."""


def basis_rows(connection, key, target):
    with connection.pipeline():
        criteria_cursor = connection.execute(
            "SELECT digest,canonical_bytes,problem_revision_id FROM "
            "business_problem_authority.criteria_sets "
            "WHERE namespace=%s AND security_domain=%s AND set_revision_id=%s AND business_problem_id=%s",
            (*key, target.criteria.revision_id, target.problem.resource_id),
        )
        problem_cursor = connection.execute(
            "SELECT digest,canonical_bytes FROM business_problem_authority.problem_revisions "
            "WHERE namespace=%s AND security_domain=%s AND business_problem_id=%s AND revision_id=%s",
            (*key, target.problem.resource_id, target.problem.revision_id),
        )
    return criteria_cursor.fetchone(), problem_cursor.fetchone()


def output_rows(connection, key, run_id):
    with connection.pipeline():
        artifacts_cursor = connection.execute(
            "SELECT artifact_id,task_id,attempt_id,record,digest,content FROM "
            "execution_authority.run_artifacts "
            "WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s ORDER BY artifact_id",
            (*key, run_id),
        )
        uses_cursor = connection.execute(
            "SELECT DISTINCT ON (u.resource_use_id) "
            "u.resource_use_id,s.snapshot_id,s.digest,s.high_water,s.record "
            "FROM resource_use.uses u JOIN resource_use.snapshots s "
            "USING(namespace,security_domain,resource_use_id) "
            "WHERE u.namespace=%s AND u.security_domain=%s AND u.workflow_run_id=%s "
            "ORDER BY u.resource_use_id,s.high_water DESC",
            (*key, run_id),
        )
        events_cursor = connection.execute(
            "SELECT max(version) AS high_water FROM "
            "execution_authority.prepared_run_events "
            "WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s",
            (*key, run_id),
        )
    return (
        artifacts_cursor.fetchall(),
        uses_cursor.fetchall(),
        events_cursor.fetchone()["high_water"],
    )
