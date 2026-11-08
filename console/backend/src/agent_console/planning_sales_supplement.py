"""Explicit same-source supplement with immutable original planning/execution."""

from copy import deepcopy

from psycopg.types.json import Jsonb
from pydantic import Field

from .authority_contracts import ExactGrant
from .business_problem_domain import BusinessProblemError
from .digital_employee_definition import EmployeeDefinitionError
from .digital_employee_definition_postgres import PostgresEmployeeDefinitionRepository
from .plan_suggestion_application import PlanningApplication
from .plan_suggestion_domain import (
    ConfirmedPlanRevision,
    ExactReference,
    FlexiblePlanSemantics,
    HumanResourceSupplementOrigin,
    Identity,
    Immutable,
    PlanningConflict,
    PlanningError,
    ProblemTarget,
    ProposalRevision,
)
from .plan_suggestion_postgres import PostgresPlanningRepository
from .planning_candidates import read_published, require_read
from .planning_source_change import source_content
from .planning_source_reference import approved_source
from .resource_use_domain import canonical_digest
from .sales_gross_profit_evaluation import CHECKS, criterion_candidate
from .sales_gross_profit_integration import SOURCE_DIGEST, validate_operation
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError

TASK_CHECKS = {
    "READ_DATA": ("source",),
    "VALIDATE_DATA": ("source", "exceptions"),
    "SUMMARIZE": ("totals", "reconciliations"),
    "ANALYZE_DATA": (
        "gross_profit_dimensions",
        "row_contributions",
        "reconciliations",
        "claim_boundary",
    ),
    "RENDER_REPORT": CHECKS,
}


class SalesSupplementRequest(Immutable):
    plan_version: int = Field(ge=1)
    plan_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    expected_proposal_revision: int = Field(ge=1)
    source_snapshot: ExactReference
    new_target: ProblemTarget
    employee: ExactReference
    skill: ExactReference
    reason: str = Field(min_length=1, max_length=500)
    idempotency_key: Identity


def grants(context, path, payload, query):
    actions = ("READ", "PREPARE") if payload else ("READ",)
    return tuple(
        ExactGrant("PLAN", action, "plan:v2:" + path["proposal_id"])
        for action in actions
    )


def member_refs(employee):
    return {
        (
            m["kind"],
            m["resource_id"],
            m["revision_id"],
            m["digest"].removeprefix("sha256:"),
        )
        for m in employee["members"]
    }


def employee_descends_from(c, app, principal, original, after):
    """Historical links prove lineage only; each remains exactly READ-authorized."""
    scope = app.scope(principal)
    cursor = after.get("predecessorRevisionId")
    seen = {after["revisionId"]}
    for _ in range(64):
        if cursor == original.revision_id:
            return True
        if not cursor or cursor in seen:
            return False
        seen.add(cursor)
        require_read(
            app.authority,
            principal,
            "EMPLOYEE",
            original.model_copy(update={"revision_id": cursor}),
        )
        try:
            value = PostgresEmployeeDefinitionRepository.read_revision_for_workbench(
                c, scope, original.resource_id, cursor, authorized=True
            )
        except EmployeeDefinitionError as exc:
            raise PlanningError("SUPPLEMENT_EMPLOYEE_UNAVAILABLE") from exc
        if value["publicationState"] != "PUBLISHED":
            return False
        cursor = value["revision"].get("predecessorRevisionId")
    return False


def validate_resources(c, app, principal, old, spec):
    scope = app.scope(principal)
    old_employee = [
        r.selected for r in old.semantics.requirements if r.kind == "EMPLOYEE"
    ]
    old_skill = [r.selected for r in old.semantics.requirements if r.kind == "SKILL"]
    if (
        len(old_employee) != 1
        or len(old_skill) != 1
        or not all(old_employee + old_skill)
    ):
        raise PlanningConflict("SUPPLEMENT_SINGLE_ORIGINAL_COMPOSITION_REQUIRED")
    old_employee, old_skill = old_employee[0], old_skill[0]
    if (
        spec.employee.resource_id != old_employee.resource_id
        or spec.skill.resource_id != old_skill.resource_id
        or spec.employee.revision_id == old_employee.revision_id
        or spec.skill.revision_id == old_skill.revision_id
    ):
        raise PlanningConflict("SUPPLEMENT_EXACT_SUCCESSORS_REQUIRED")
    values = []
    for kind, ref in [
        ("EMPLOYEE", old_employee),
        ("EMPLOYEE", spec.employee),
        ("SKILL", old_skill),
        ("SKILL", spec.skill),
    ]:
        require_read(app.authority, principal, kind, ref)
        try:
            if kind == "EMPLOYEE" and ref == old_employee:
                # Historical composition is evidence, not a fresh runnable binding.
                value = (
                    PostgresEmployeeDefinitionRepository.read_revision_for_workbench(
                        c, scope, ref.resource_id, ref.revision_id, authorized=True
                    )
                )
                if (
                    value["digest"] != ref.digest
                    or value["publicationState"] != "PUBLISHED"
                ):
                    raise PlanningError("SUPPLEMENT_PREDECESSOR_UNAVAILABLE")
                values.append(value["revision"])
            else:
                values.append(
                    read_published(c, scope, kind, ref, historical=ref == old_skill)[0]
                )
        except EmployeeDefinitionError as exc:
            raise PlanningError("SUPPLEMENT_EMPLOYEE_UNAVAILABLE") from exc
    before, after, _, skill = values
    original_member = (
        "SKILL",
        old_skill.resource_id,
        old_skill.revision_id,
        old_skill.digest,
    )
    if (
        original_member not in member_refs(before)
        or before["role"] != after["role"]
        or before["responsibilities"] != after["responsibilities"]
        or member_refs(after)
        != (
            member_refs(before)
            - {
                (
                    "SKILL",
                    old_skill.resource_id,
                    old_skill.revision_id,
                    old_skill.digest,
                )
            }
        )
        | {("SKILL", spec.skill.resource_id, spec.skill.revision_id, spec.skill.digest)}
    ):
        raise PlanningConflict("SUPPLEMENT_MEMBER_CHANGE_OUT_OF_SCOPE")
    if not employee_descends_from(c, app, principal, old_employee, after):
        raise PlanningConflict("SUPPLEMENT_EMPLOYEE_PREDECESSOR_MISMATCH")
    operations = skill.get("operations", [])
    if (
        skill.get("sideEffect") != "READ"
        or any(op.get("sideEffectClass") != "READ_ONLY" for op in operations)
        or len(operations) != len(TASK_CHECKS)
        or {op["name"] for op in operations} != set(TASK_CHECKS)
    ):
        raise PlanningConflict("SUPPLEMENT_SALES_OPERATIONS_REQUIRED")
    try:
        for op in operations:
            validate_operation(op, bounded=True)
    except ValueError as exc:
        raise PlanningConflict("SUPPLEMENT_SALES_V2_CONTRACT_REQUIRED") from exc
    row = c.execute(
        "SELECT record FROM skill_mcp_resource.resources "
        "WHERE namespace=%s AND security_domain=%s "
        "AND kind='skill' AND resource_id=%s",
        (scope.namespace, scope.security_domain, spec.skill.resource_id),
    ).fetchone()
    revisions = {r["revisionId"]: r for r in row["record"]["revisions"]}
    cursor = spec.skill.revision_id
    for _ in range(64):
        if cursor == old_skill.revision_id:
            return
        cursor = revisions.get(cursor, {}).get("predecessorRevisionId")
        if not cursor:
            break
    raise PlanningConflict("SUPPLEMENT_SKILL_PREDECESSOR_MISMATCH")


def read_checks(app, principal, c, target, *, current):
    app.validate_target(principal, target, c, current=current)
    checks = {}
    for identity in target.criterion_revision_ids:
        criterion = app.problems.get_criterion_revision(
            app.scope(principal),
            identity,
            authorized=True,
            connection=c,
        )
        check = criterion.applicability.get("check")
        if check not in CHECKS or check in checks:
            raise PlanningConflict("SUPPLEMENT_EXACT_SEVEN_CRITERIA_REQUIRED")
        expected = criterion_candidate(check)
        if any(
            getattr(criterion, key) != expected[key]
            for key in (
                "evaluator_type",
                "evaluator_version",
                "measurement",
                "applicability",
            )
        ):
            raise PlanningConflict("SUPPLEMENT_CRITERION_CONTRACT_MISMATCH")
        if (
            criterion.criterion_type.value != expected["criterion_type"]
            or tuple(criterion.required_evidence_kinds)
            != tuple(expected["required_evidence_kinds"])
            or not criterion.created_by.startswith("human:")
        ):
            raise PlanningConflict("SUPPLEMENT_EXPLICIT_CRITERIA_OWNER_REQUIRED")
        checks[check] = identity
    if set(checks) != set(CHECKS):
        raise PlanningConflict("SUPPLEMENT_EXACT_SEVEN_CRITERIA_REQUIRED")
    return checks


def validate_confirmation(app, principal, c, proposal):
    if not isinstance(proposal.origin, HumanResourceSupplementOrigin):
        return
    origin = proposal.origin
    row = c.execute(
        "SELECT result FROM execution_authority.prepared_resource_commands "
        "WHERE namespace=%s AND security_domain=%s AND actor_id=%s "
        "AND command_key=%s",
        (
            principal.tenant_id,
            principal.security_domain,
            origin.prepared_by,
            "planning-sales-supplement:" + origin.request_key,
        ),
    ).fetchone()
    if not row or row["result"].get("digest") != proposal.digest:
        raise PlanningConflict("SUPPLEMENT_PROVENANCE_RECEIPT_MISMATCH")
    spec = SalesSupplementRequest.model_validate(row["result"]["request"])
    app.require(principal, "READ", proposal.proposal_id)
    base = app.repository.read_plan(
        c, app.scope(principal), proposal.proposal_id, spec.plan_version
    )
    old = ConfirmedPlanRevision.model_validate(base["plan"])
    if (
        old.digest != spec.plan_digest
        or approved_source(proposal.semantics) != spec.source_snapshot
    ):
        raise PlanningConflict("SUPPLEMENT_PROVENANCE_RECEIPT_MISMATCH")
    read_checks(app, principal, c, spec.new_target, current=True)
    source_content(
        c, app.scope(principal), app.authority, principal, spec.source_snapshot
    )
    validate_resources(c, app, principal, old, spec)


class PlanningSalesSupplementOwner:
    def __init__(self, application):
        self.application = application

    def __call__(self, call):
        context, c = call.context, call.connection
        if not context.principal_id.startswith("human:"):
            raise WorkbenchOwnerError("EXPLICIT_SALES_SUPPLEMENT_REQUIRED", 403)
        p = OwnerPrincipal(
            context.principal_id, context.scope.tenant_id, context.scope.security_domain
        )
        repo = PostgresPlanningRepository(self.application.repository.pool, c)
        app = PlanningApplication(repo, self.application.problems, call.authority)
        identity = call.path["proposal_id"]
        writing = call.operation == "PREPARE_SALES_SUPPLEMENT"
        if not writing and call.operation != "READ_SALES_SUPPLEMENT":
            raise WorkbenchOwnerError("WORKBENCH_OPERATION_INVALID", 500)
        for g in grants(context, call.path, call.payload, call.query):
            call.authority.require(p, g.owner, g.action, g.exact_resource)
        spec = SalesSupplementRequest.model_validate(call.payload) if writing else None
        if spec is not None and not spec.reason.strip():
            raise WorkbenchOwnerError("SUPPLEMENT_REASON_REQUIRED", 422)
        key = spec.idempotency_key if spec else call.path["request_key"]
        scope = app.scope(p)
        storage_key = "planning-sales-supplement:" + key
        if writing:
            c.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (
                    canonical_digest(
                        [
                            scope.namespace,
                            scope.security_domain,
                            p.principal_id,
                            storage_key,
                        ]
                    ),
                ),
            )
        prior = c.execute(
            "SELECT digest,result FROM execution_authority.prepared_resource_commands "
            "WHERE namespace=%s AND security_domain=%s AND actor_id=%s "
            "AND command_key=%s",
            (scope.namespace, scope.security_domain, p.principal_id, storage_key),
        ).fetchone()
        digest = canonical_digest([identity, call.payload]) if writing else None
        try:
            if prior:
                result = prior["result"]
                if result["proposal"]["proposal_id"] != identity:
                    raise PlanningError("SUPPLEMENT_RECEIPT_NOT_FOUND")
                if writing and prior["digest"] != digest:
                    raise PlanningConflict("SUPPLEMENT_KEY_CONFLICT")
                proposal = ProposalRevision.model_validate(result["proposal"])
                read_checks(app, p, c, proposal.semantics.target, current=False)
                for r in proposal.semantics.requirements:
                    if r.selected is not None:
                        require_read(app.authority, p, r.kind, r.selected)
                return result
            if not writing:
                raise PlanningError("SUPPLEMENT_RECEIPT_NOT_FOUND")
            with repo.transaction(scope, identity, authorized=True) as cursor:
                value = repo.read_plan(cursor, scope, identity, spec.plan_version)
                old = ConfirmedPlanRevision.model_validate(value["plan"])
                latest = c.execute(
                    "SELECT max(version) v FROM workflow_planning.plans "
                    "WHERE namespace=%s AND security_domain=%s AND plan_id=%s",
                    (scope.namespace, scope.security_domain, identity),
                ).fetchone()["v"]
                head = c.execute(
                    "SELECT max(revision) v FROM workflow_planning.proposals "
                    "WHERE namespace=%s AND security_domain=%s AND proposal_id=%s",
                    (scope.namespace, scope.security_domain, identity),
                ).fetchone()["v"]
                if (
                    latest != spec.plan_version
                    or old.digest != spec.plan_digest
                    or head != spec.expected_proposal_revision
                ):
                    raise PlanningConflict("SUPPLEMENT_HEAD_CHANGED")
                source = approved_source(old.semantics)
                if (
                    source != spec.source_snapshot
                    or old.semantics.target.problem != spec.new_target.problem
                    or old.semantics.target.criteria == spec.new_target.criteria
                ):
                    raise PlanningConflict("SUPPLEMENT_TARGET_OR_SOURCE_CHANGED")
                app.validate_target(p, old.semantics.target, c, current=False)
                data, _, _ = source_content(c, scope, app.authority, p, source)
                if canonical_digest(data) != SOURCE_DIGEST:
                    raise PlanningConflict("SUPPLEMENT_EXACT_SALES_SOURCE_REQUIRED")
                checks = read_checks(app, p, c, spec.new_target, current=True)
                validate_resources(c, app, p, old, spec)
                semantics = deepcopy(old.semantics.model_dump(mode="json"))
                if len(semantics["requirements"]) != 3 or {
                    r["kind"] for r in semantics["requirements"]
                } != {"EMPLOYEE", "SKILL", "KNOWLEDGE"}:
                    raise PlanningConflict("SUPPLEMENT_ORIGINAL_COMPOSITION_REQUIRED")
                if {t["operation"] for t in semantics["tasks"]} != set(
                    TASK_CHECKS
                ) or len(semantics["tasks"]) != len(TASK_CHECKS):
                    raise PlanningConflict("SUPPLEMENT_ORIGINAL_SALES_GRAPH_REQUIRED")
                semantics["target"] = spec.new_target.model_dump(mode="json")
                for task in semantics["tasks"]:
                    task["criterion_revision_ids"] = [
                        checks[x] for x in TASK_CHECKS[task["operation"]]
                    ]
                for r in semantics["requirements"]:
                    if r["kind"] in {"EMPLOYEE", "SKILL"}:
                        r["selected"] = (
                            spec.employee if r["kind"] == "EMPLOYEE" else spec.skill
                        ).model_dump(mode="json")
                proposal = ProposalRevision(
                    proposal_id=identity,
                    revision=head + 1,
                    predecessor_digest=repo.proposal(
                        cursor, scope, identity, head
                    ).digest,
                    invocation_id=None,
                    semantics=FlexiblePlanSemantics.model_validate(semantics),
                    origin=HumanResourceSupplementOrigin(
                        namespace=scope.namespace,
                        security_domain=scope.security_domain,
                        root=spec.new_target.problem,
                        source_snapshot=source,
                        predecessor_plan=ExactReference(
                            resource_id=identity,
                            revision_id=str(old.version),
                            digest=old.digest,
                        ),
                        prepared_by=p.principal_id,
                        request_key=key,
                        reason=spec.reason,
                    ),
                )
                saved = repo.add_proposal(cursor, scope, proposal)
                result = {
                    "schemaVersion": "planning-sales-supplement-receipt.v1",
                    "proposal": saved.model_dump(mode="json"),
                    "digest": saved.digest,
                    "request": spec.model_dump(mode="json"),
                    "requestKey": key,
                    "confirmation_required": True,
                    "executionStarted": False,
                    "modelCalls": 0,
                    "businessAcceptance": "OPEN",
                }
                c.execute(
                    "INSERT INTO execution_authority.prepared_resource_commands"
                    "(namespace,security_domain,actor_id,command_key,digest,result) "
                    "VALUES(%s,%s,%s,%s,%s,%s)",
                    (
                        scope.namespace,
                        scope.security_domain,
                        p.principal_id,
                        storage_key,
                        digest,
                        Jsonb(result),
                    ),
                )
                return result
        except PlanningConflict as exc:
            raise WorkbenchOwnerError(str(exc), 409) from exc
        except PlanningError as exc:
            raise WorkbenchOwnerError(str(exc), 404) from exc
        except BusinessProblemError as exc:
            raise WorkbenchOwnerError("SUPPLEMENT_TARGET_UNAVAILABLE", 404) from exc


def operations(application):
    path = f"{PREFIX}/planning-v2/{{proposal_id}}/sales-supplements"
    handler = PlanningSalesSupplementOwner(application)
    return (
        WorkbenchOperation(
            "PREPARE_SALES_SUPPLEMENT",
            "POST",
            path,
            SalesSupplementRequest,
            None,
            grants,
            handler,
        ),
        WorkbenchOperation(
            "READ_SALES_SUPPLEMENT",
            "GET",
            path + "/by-key/{request_key}",
            None,
            None,
            grants,
            handler,
        ),
    )
