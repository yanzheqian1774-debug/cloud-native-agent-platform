"""Typed planning v2 operations on the existing trusted transactional BFF."""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import ExactGrant
from .cost_execution_revision import CostExecutionRevisionRequest
from .plan_suggestion_application import PlanningApplication
from .plan_suggestion_domain import PlanningConflict, PlanningError, ProposalRevision
from .plan_suggestion_postgres import PostgresPlanningRepository
from .plan_suggestion_resources import EmployeePlanningReader, PlanningResourceResolver
from .planning_contracts import validation_report
from .synthetic_validation_plan import SyntheticValidationRequest
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError


class Version(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)


class CandidateQuery(Version):
    kind: (
        Literal["EMPLOYEE", "SKILL", "MCP", "KNOWLEDGE", "WORKFLOW", "RUNTIME", "AGENT"]
        | None
    ) = None


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
            if call.operation == "PREPARE_SYNTHETIC_VALIDATION_PLAN":
                return app.prepare_synthetic_validation(
                    principal, SyntheticValidationRequest.model_validate(call.payload)
                )
            if call.operation == "READ_PLANNING_INPUT_V2":
                return app.current_input(principal, identity, call.connection)
            if call.operation == "PREPARE_COST_EXECUTION_REVISION":
                return app.prepare_cost_execution_revision(
                    principal,
                    identity,
                    CostExecutionRevisionRequest.model_validate(call.payload),
                )
            if call.operation == "READ_SOURCE_CHANGE_CURRENT_TARGET":
                from .planning_source_change import current_target

                return current_target(
                    app, principal, call.connection, identity, call.query["version"]
                )
            if call.operation in {
                "PREVIEW_PLAN_SOURCE_CHANGE",
                "PREPARE_PLAN_SOURCE_CHANGE",
            }:
                from .planning_source_change import (
                    SourceChangeRequest,
                    prepare,
                    preview,
                )

                spec = SourceChangeRequest.model_validate(call.payload)
                if call.operation == "PREPARE_PLAN_SOURCE_CHANGE":
                    return prepare(app, principal, identity, spec)
                app.require(principal, "READ", identity)
                with repo.transaction(app.scope(principal), identity, authorized=True):
                    _, evidence = preview(
                        app, principal, call.connection, identity, spec
                    )
                    return evidence
            if call.operation in {
                "READ_PLAN_SOURCE_CHANGE",
                "RECOVER_PLAN_SOURCE_CHANGE",
            }:
                from .planning_source_change import read

                return read(
                    app,
                    principal,
                    call.connection,
                    identity,
                    call.path.get("request_id", call.path.get("request_key")),
                    by_key=call.operation == "RECOVER_PLAN_SOURCE_CHANGE",
                )
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
                if call.operation == "READ_PLAN_CANDIDATES":
                    from .planning_candidates import discover

                    query = CandidateQuery.model_validate(call.query)
                    proposal = repo.proposal(cursor, scope, identity, query.version)
                    if proposal.revision != max(
                        p["revision"] for p in history["proposals"]
                    ):
                        raise PlanningConflict("CANDIDATE_PROPOSAL_STALE")
                    app.validate_target(
                        principal, proposal.semantics.target, call.connection
                    )
                    requirements = (
                        [
                            SimpleNamespace(
                                kind=query.kind,
                                requirement_id="catalog:" + query.kind,
                                selected=None,
                            )
                        ]
                        if query.kind
                        else proposal.semantics.requirements
                    )
                    groups = [
                        discover(
                            call.connection,
                            scope,
                            call.authority,
                            principal,
                            proposal,
                            r,
                        )
                        for r in requirements
                    ]
                    return {
                        "proposalDigest": proposal.digest,
                        "proposalRevision": proposal.revision,
                        "groups": groups,
                        "executionReady": False,
                    }
                if call.operation == "READ_PLAN_HISTORY_V2":
                    from .planning_execution_projection import execution_summary

                    for approved in history["plans"]:
                        approved["execution_summary"] = execution_summary(
                            call.connection, principal, call.authority, approved["plan"]
                        )
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
                    from .planning_candidates import ExactPlanningOwnerReader

                    for kind in ("SKILL", "KNOWLEDGE", "WORKFLOW"):
                        readers[kind] = ExactPlanningOwnerReader(
                            call.connection, scope, call.authority, kind
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
                from .planning_translation import display_translation

                return {
                    "display_translation": display_translation(proposal),
                    "proposal": proposal.model_dump(mode="json"),
                    "digest": proposal.digest,
                    "execution_status": "NOT_STARTED",
                    "snapshot": snapshot["record"] if snapshot else None,
                    "validation": validation_report(proposal.semantics),
                    "generated_at": next(
                        (
                            m["generated_at"]
                            for m in history["conversation"]
                            if m["invocation_id"] == proposal.invocation_id
                        ),
                        None,
                    ),
                }
        except PlanningConflict as exc:
            raise WorkbenchOwnerError(str(exc), 409) from exc
        except PlanningError as exc:
            raise WorkbenchOwnerError(str(exc), 404) from exc


def planning_operations(application, employees=None):
    handler = PlanningOwnerAdapter(application, employees)
    path = f"{PREFIX}/planning-v2/{{proposal_id}}"
    from .planning_source_change import SourceChangeRequest

    return (
        WorkbenchOperation(
            "READ_SOURCE_CHANGE_CURRENT_TARGET",
            "GET",
            path + "/source-change-target",
            None,
            Version,
            _grant("READ"),
            handler,
        ),
        WorkbenchOperation(
            "RECOVER_PLAN_SOURCE_CHANGE",
            "GET",
            path + "/source-changes/by-key/{request_key}",
            None,
            None,
            _grant("READ"),
            handler,
        ),
        WorkbenchOperation(
            "READ_PLAN_CANDIDATES",
            "GET",
            path + "/candidates",
            None,
            CandidateQuery,
            _grant("READ"),
            handler,
        ),
        WorkbenchOperation(
            "PREVIEW_PLAN_SOURCE_CHANGE",
            "POST",
            path + "/source-change-preview",
            SourceChangeRequest,
            None,
            _grant("READ"),
            handler,
        ),
        WorkbenchOperation(
            "PREPARE_PLAN_SOURCE_CHANGE",
            "POST",
            path + "/source-changes",
            SourceChangeRequest,
            None,
            _grant("PREPARE"),
            handler,
        ),
        WorkbenchOperation(
            "READ_PLAN_SOURCE_CHANGE",
            "GET",
            path + "/source-changes/{request_id}",
            None,
            None,
            _grant("READ"),
            handler,
        ),
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
            "PREPARE_SYNTHETIC_VALIDATION_PLAN",
            "POST",
            f"{PREFIX}/planning-v2/synthetic-validation",
            SyntheticValidationRequest,
            None,
            lambda ctx, path, payload, query: (
                ExactGrant(
                    "PLAN",
                    "PREPARE",
                    "plan:prepare:"
                    + payload["semantics"]["target"]["problem"]["resource_id"],
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
            "PREPARE_COST_EXECUTION_REVISION",
            "POST",
            path + "/execution-revision",
            CostExecutionRevisionRequest,
            None,
            _grant("PREPARE"),
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

    def __init__(self, profile=None):
        self.profile = profile

    def is_known_exact_target(self, context, grant, *, connection=None):
        if connection is None:
            return False
        if grant.owner == "MODEL_GOVERNANCE" and grant.action == "INVOKE_MODEL":
            if self.profile is None:
                return False
            from .model_governance_authorization import PostgresModelGrantTargetLookup

            return PostgresModelGrantTargetLookup(None).is_known_planning_target(
                context.scope, grant, self.profile.model, connection=connection
            )
        if grant.owner != "PLAN":
            return False
        for action, prefix in (
            ("PREPARE", "plan:prepare:"),
            ("READ", "plan:prepared:"),
        ):
            if grant.action == action and grant.exact_resource.startswith(prefix):
                return (
                    connection.execute(
                        "SELECT 1 FROM business_problem_authority.problems "
                        "WHERE namespace=%s AND security_domain=%s "
                        "AND business_problem_id=%s FOR SHARE",
                        (
                            context.scope.tenant_id,
                            context.scope.security_domain,
                            grant.exact_resource[len(prefix) :],
                        ),
                    ).fetchone()
                    is not None
                )
        prefix = "plan:v2:"
        if not grant.exact_resource.startswith(prefix):
            return False
        if grant.action not in {"READ", "APPROVE", "PREPARE"}:
            return False
        identity = grant.exact_resource[len(prefix) :]
        row = connection.execute(
            "SELECT 1 FROM workflow_planning.proposals WHERE namespace=%s "
            "AND security_domain=%s AND proposal_id=%s LIMIT 1",
            (context.scope.tenant_id, context.scope.security_domain, identity),
        ).fetchone()
        return row is not None
