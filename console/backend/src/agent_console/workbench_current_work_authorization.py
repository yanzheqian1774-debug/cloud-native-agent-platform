"""Exact batch reads for a directory within the existing owner transaction."""

from .authority_configuration import validate_registered_grant
from .authority_contracts import AuthorityError
from .workbench_owner_authorization import WorkbenchOwnerError


def readable_grants(call, grants):
    """Return exact decisions in input order; never treat outage as denial."""
    unique = tuple(dict.fromkeys(grants))
    if not unique:
        return ()
    for grant in unique:
        validate_registered_grant(grant, allow_meta=False)
    authority = call.authority
    adapter = authority.adapter
    try:
        results = adapter.authorization.has_current_grants(
            call.context,
            unique,
            now=adapter.clock(),
            generation=authority.generation,
            recovery_epoch=adapter.controller.readiness.recovery_epoch,
            connection=call.connection,
            configure_transaction=False,
            require_available=True,
        )
    except AuthorityError as exc:
        if exc.reason_code != "AUTHORIZATION_STATE_UNAVAILABLE":
            raise
        raise WorkbenchOwnerError("CURRENT_WORK_AUTHORITY_UNAVAILABLE", 503) from exc
    readable = dict(zip(unique, results, strict=True))
    for grant, allowed in readable.items():
        if allowed:
            authority.decisions[(grant.owner, grant.action, grant.exact_resource)] = (
                adapter._decision(call.context, grant, authority.generation)
            )
    return tuple(readable[g] for g in grants)


def readable_runs(call, rows):
    """Filter run facts by both existing root policies before any UI projection.

    Input must be the internal single-statement snapshot. Missing fixed problem
    versions of otherwise readable executions are failures, never substituted
    with a newer revision or silently excluded from a supposedly complete total.
    """
    from .authority_contracts import ExactGrant
    from .business_problem_authorization import problem_resource

    execution_grants = tuple(
        ExactGrant("EXECUTION", "READ", "governed-execution:prepared:" + row["digest"])
        for row in rows
    )
    admitted = [
        row
        for row, allowed in zip(
            rows, readable_grants(call, execution_grants), strict=True
        )
        if allowed
    ]
    for row in admitted:
        if not all(
            row.get(field)
            for field in (
                "business_problem_id",
                "problem_revision_id",
                "problem_digest",
            )
        ):
            raise WorkbenchOwnerError("CURRENT_WORK_PROBLEM_VERSION_UNAVAILABLE", 503)
    problem_grants = tuple(
        ExactGrant(
            "BUSINESS_PROBLEM", "READ", problem_resource(row["business_problem_id"])
        )
        for row in admitted
    )
    return [
        row
        for row, allowed in zip(
            admitted, readable_grants(call, problem_grants), strict=True
        )
        if allowed
    ]
