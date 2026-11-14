"""Authenticated F3 task directory, assembled from existing owner facts."""

from .development_administrator import for_call
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_current_work_attribution import in_scope, requester
from .workbench_current_work_authorization import readable_runs
from .workbench_current_work_page import directory_page
from .workbench_current_work_projection import project_runs
from .workbench_current_work_query import CurrentWorkQuery
from .workbench_current_work_snapshot import read_current_work_snapshot


class CurrentWorkDirectory:
    def __init__(self, cursors):
        self.cursors = cursors

    def __call__(self, call):
        administrator = for_call(call)
        query = CurrentWorkQuery.model_validate(call.query).resolved(
            verified_development_administrator=administrator
        )
        generation = call.policy_generation
        epoch = call.recovery_epoch
        # Reject stale or cross-subject/filter cursors before expensive reads.
        query.after(
            self.cursors, call.context, generation=generation, recovery_epoch=epoch
        )
        rows = read_current_work_snapshot(
            call.connection,
            namespace=call.context.scope.tenant_id,
            security_domain=call.context.scope.security_domain,
        )
        read_at = rows[0]["read_at"] if rows else call.authority.adapter.clock()
        visible = readable_runs(call, rows)
        # Attribution is metadata, not admission. Apply only after exact READs;
        # use the same predicate as counts/pages before expensive evidence reads.
        selected = [
            row
            for row in visible
            for attribution in [
                requester(row, call.context.principal_id, administrator=administrator)
            ]
            if (
                in_scope(
                    query.scopeFilter,
                    call.context.principal_id,
                    attribution.requested_by,
                    attribution.kind,
                    row["initiators"],
                )
            )
            and query.query.casefold()
            in (row["title"] + " " + row["workflow_run_id"]).casefold()
        ]
        single_page = len(selected) <= query.pageSize and not query.cursor
        items = project_runs(
            call,
            selected,
            verified_administrator=administrator,
            include_outcomes=single_page,
        )
        page = directory_page(
            items,
            query,
            self.cursors,
            call.context,
            generation=generation,
            recovery_epoch=epoch,
            read_at=read_at,
        )
        if single_page:
            return page
        # Only visible rows expose business outcomes. Keep global run/question
        # counts independent from per-page evidence reads and outcome checks.
        page_ids = {item["workflowRunId"] for item in page["items"]}
        enriched = project_runs(
            call,
            [row for row in selected if row["workflow_run_id"] in page_ids],
            verified_administrator=administrator,
        )
        outcomes = {item.workflowRunId: item for item in enriched}
        for item in page["items"]:
            verified = outcomes[item["workflowRunId"]]
            item["businessResolution"] = verified.businessResolution
            item["outcomeVersion"] = verified.outcomeVersion
        return page


def operations(cursors):
    return (
        WorkbenchOperation(
            name="LIST_CURRENT_WORK",
            method="GET",
            path=PREFIX + "/current-work",
            request_model=None,
            query_model=CurrentWorkQuery,
            grant_builder=lambda context, path, payload, query: (),
            handler=CurrentWorkDirectory(cursors),
        ),
    )
