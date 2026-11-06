"""Authorized read-only status over the execution owner's existing records."""

from .authority_contracts import AuthorityError


def execution_summary(c, principal, authority, plan):
    # Legacy databases/unknown owner availability must never imply not started.
    if not c.execute(
        "SELECT to_regclass('execution_authority.prepared_candidates') name"
    ).fetchone()["name"]:
        return {"state": "UNKNOWN", "basis": "EXECUTION_OWNER_UNAVAILABLE"}
    rows = c.execute(
        "SELECT digest FROM execution_authority.prepared_candidates WHERE "
        "namespace=%s AND security_domain=%s AND plan_id=%s AND plan_version=%s",
        (
            principal.tenant_id,
            principal.security_domain,
            plan["plan_id"],
            plan["version"],
        ),
    ).fetchall()
    if not rows:
        return {
            "state": "NOT_STARTED",
            "basis": "NO_PREPARED_CANDIDATE_FOR_PLAN_VERSION",
        }
    states, executions = [], []
    for row in rows:
        try:
            authority.require(
                principal,
                "EXECUTION",
                "READ",
                "governed-execution:prepared:" + row["digest"],
            )
        except AuthorityError:
            return {"state": "UNKNOWN", "basis": "EXECUTION_STATE_NOT_READABLE"}
        progress = c.execute(
            "SELECT record->>'state' state FROM "
            "execution_authority.prepared_run_progress WHERE namespace=%s "
            "AND security_domain=%s AND workflow_run_id=%s",
            (
                principal.tenant_id,
                principal.security_domain,
                "workflow-run:" + row["digest"],
            ),
        ).fetchone()
        states.append(progress["state"] if progress else "NOT_STARTED")
        executions.append(
            {
                "digest": row["digest"],
                "state": states[-1],
                "planVersion": plan["version"],
            }
        )
    state = (
        states[0]
        if len(set(states)) == 1
        else "RUNNING"
        if any(s in {"PENDING", "RUNNING"} for s in states)
        else "MULTIPLE_STATES"
    )
    return {
        "state": state,
        "basis": "AUTHORIZED_EXECUTION_OWNER_READBACK",
        "executions": sorted(executions, key=lambda x: x["digest"]),
    }
