"""Typed planning v2 operations on the existing trusted transactional BFF."""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import ExactGrant
from .plan_suggestion_application import PlanningApplication
from .plan_suggestion_domain import PlanningConflict, PlanningError, ProposalRevision
from .plan_suggestion_postgres import PostgresPlanningRepository
from .plan_suggestion_resources import EmployeePlanningReader, PlanningResourceResolver
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError


class Version(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)


class ConfirmSuggestion(Version):
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    expectedPlanVersion: int = Field(ge=0)
    idempotencyKey: str = Field(min_length=1, max_length=200)


def _grant(action):
    def build(context, path, payload, query):
        return (ExactGrant("PLAN", action, f"plan:v2:{path['proposal_id']}"),)

    return build


@dataclass
class PlanningOwnerAdapter:
    application: PlanningApplication
    employees: object = None

    def __call__(self, call):
        principal = OwnerPrincipal(
            call.context.principal_id,
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        repo = PostgresPlanningRepository(
            self.application.repository.pool, call.connection
        )
        app = PlanningApplication(repo, self.application.problems, call.authority)
        identity = call.path.get("proposal_id", call.path.get("problem_id"))
        try:
            if call.operation == "READ_PLANNING_INPUT_V2":
                return app.current_input(principal, identity, call.connection)
            if call.operation == "CONFIRM_PLAN_V2":
                body = ConfirmSuggestion.model_validate(call.payload)
                return app.confirm(
                    principal,
                    identity,
                    body.version,
                    body.digest,
                    expected_plan_version=body.expectedPlanVersion,
                    key=body.idempotencyKey,
                )
            app.require(principal, "READ", identity)
            scope = app.scope(principal)
            with repo.transaction(scope, identity, authorized=True) as cursor:
                history = repo.history(cursor, scope, identity)
                if not history["proposals"]:
                    raise PlanningError("PLANNING_NOT_FOUND")
                for record in history["proposals"]:
                    proposal = ProposalRevision.model_validate(record)
                    app.validate_target(
                        principal,
                        proposal.semantics.target,
                        call.connection,
                        current=False,
                    )
                if call.operation == "READ_PLAN_HISTORY_V2":
                    return history
                version = (
                    call.payload["version"]
                    if call.operation == "REFRESH_PLAN_RESOURCES_V2"
                    else call.query["version"]
                )
                proposal = repo.proposal(cursor, scope, identity, version)
                if call.operation == "REFRESH_PLAN_RESOURCES_V2":
                    readers = {}
                    if self.employees is not None:
                        readers["EMPLOYEE"] = EmployeePlanningReader(
                            self.employees, call.authority, app.scope, call.connection
                        )
                    snapshot = PlanningResourceResolver(readers).resolve(
                        principal, proposal
                    )
                    repo.save_resources(cursor, scope, proposal, snapshot)
                    return {
                        "snapshot": snapshot.model_dump(mode="json"),
                        "pending_required": snapshot.pending_required(proposal),
                    }
                snapshot = cursor.execute(
                    "SELECT record FROM workflow_planning.resource_snapshots "
                    "WHERE namespace=%s AND security_domain=%s AND proposal_id=%s "
                    "AND revision=%s ORDER BY record->>'checked_at' DESC LIMIT 1",
                    (scope.namespace, scope.security_domain, identity, version),
                ).fetchone()
                return {
                    "proposal": proposal.model_dump(mode="json"),
                    "digest": proposal.digest,
                    "execution_status": "NOT_STARTED",
                    "snapshot": snapshot["record"] if snapshot else None,
                }
        except PlanningConflict as exc:
            raise WorkbenchOwnerError(str(exc), 409) from exc
        except PlanningError as exc:
            raise WorkbenchOwnerError(str(exc), 404) from exc


def planning_operations(application, employees=None):
    handler = PlanningOwnerAdapter(application, employees)
    path = f"{PREFIX}/planning-v2/{{proposal_id}}"
    return (
        WorkbenchOperation(
            "READ_PLANNING_INPUT_V2",
            "GET",
            f"{PREFIX}/planning-input/{{problem_id}}",
            None,
            None,
            lambda ctx, path, payload, query: (
                ExactGrant(
                    "BUSINESS_PROBLEM", "READ", f"business-problem:{path['problem_id']}"
                ),
            ),
            handler,
        ),
        WorkbenchOperation(
            "REFRESH_PLAN_RESOURCES_V2",
            "POST",
            path + "/resources",
            Version,
            None,
            _grant("READ"),
            handler,
        ),
        WorkbenchOperation(
            "READ_PLAN_PROPOSAL_V2", "GET", path, None, Version, _grant("READ"), handler
        ),
        WorkbenchOperation(
            "READ_PLAN_HISTORY_V2",
            "GET",
            path + "/history",
            None,
            None,
            _grant("READ"),
            handler,
        ),
        WorkbenchOperation(
            "CONFIRM_PLAN_V2",
            "POST",
            path + "/confirm",
            ConfirmSuggestion,
            None,
            _grant("APPROVE"),
            handler,
        ),
    )


class PlanningGrantTargetValidator:
    """Exact v2 grant discovery; no wildcard or cross-scope target inference."""

    def is_known_exact_target(self, context, grant, *, connection=None):
        if connection is None or grant.owner != "PLAN":
            return False
        prefix = "plan:v2:"
        if not grant.exact_resource.startswith(prefix):
            return False
        if grant.action not in {"READ", "APPROVE"}:
            return False
        identity = grant.exact_resource[len(prefix) :]
        row = connection.execute(
            "SELECT 1 FROM workflow_planning.proposals WHERE namespace=%s "
            "AND security_domain=%s AND proposal_id=%s LIMIT 1",
            (context.scope.tenant_id, context.scope.security_domain, identity),
        ).fetchone()
        return row is not None
