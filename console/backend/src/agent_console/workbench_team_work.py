"""Explicit team-work references; grouping never conveys execution authority."""

from .business_problem_authorization import problem_resource
from .development_administrator import for_call
from .team_definition import TeamDefinitionError
from .workbench_current_work_authorization import readable_runs
from .workbench_current_work_projection import project_runs
from .workbench_current_work_snapshot import read_current_work_snapshot


def matches(link, row):
    return all(
        row.get(key) == value
        for key, value in (
            ("workflow_run_id", link.workflow_run_id),
            ("digest", link.preparation_digest),
            ("business_problem_id", link.business_problem_id),
            ("problem_revision_id", link.problem_revision_id),
            ("problem_digest", link.problem_digest),
        )
    )


def snapshot(call):
    return read_current_work_snapshot(
        call.connection,
        namespace=call.context.scope.tenant_id,
        security_domain=call.context.scope.security_domain,
    )


def validate_work_links(call, principal, links):
    """Authorize every exact reference, including replay, before persisting it."""
    if not links:
        return
    for link in links:
        call.authority.require(
            principal,
            "EXECUTION",
            "READ",
            "governed-execution:prepared:" + link.preparation_digest,
        )
        call.authority.require(
            principal,
            "BUSINESS_PROBLEM",
            "READ",
            problem_resource(link.business_problem_id),
        )
    rows = snapshot(call)
    for link in links:
        if sum(matches(link, row) for row in rows) != 1:
            raise TeamDefinitionError("TEAM_WORK_REFERENCE_UNAVAILABLE")


def project_team_work(call, revision):
    """Only explicit links; recheck current work visibility and outcome integrity."""
    links = revision.work_links or ()
    if not links:
        return {"items": [], "linkedCount": 0, "unavailableCount": 0}
    rows = snapshot(call)
    selected = [row for row in rows if any(matches(link, row) for link in links)]
    visible = readable_runs(call, selected)
    items = project_runs(call, visible, verified_administrator=for_call(call))
    return {
        "items": [item.model_dump(mode="json") for item in items],
        "linkedCount": len(links),
        "unavailableCount": len(links) - len(items),
    }
