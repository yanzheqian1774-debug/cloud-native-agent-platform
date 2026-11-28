# ruff: noqa: E501 -- Parameterized exact scoped SQL and bounded audit labels.
"""Bounded coverage over existing exact, readable owner facts; no resource creation.

Selection is permission to enter verification, never execution admission. Unknown
semantic families and missing evidence fail closed without name-based guessing.
"""

from dataclasses import replace

from pydantic import BaseModel, ConfigDict, Field

from . import owned_business_resource_adapter as owned_resources
from .authority_contracts import AuthorityError
from .digital_employee_definition import EmployeeDefinitionError
from .execution_domain import ScopeIdentity
from .execution_preparation import ExecutionPreparationError
from .plan_suggestion_domain import ConfirmedPlanRevision, ExactReference, PlanningError
from .planning_candidates import (
    identities,
    read_employee_member,
    read_published,
    require_read,
)
from .planning_source_change import approved_source
from .resource_automation_validation import validate
from .resource_policy_lineage import require_supported_lineage
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError

GAPS = ("DATA", "MAPPING", "RULES", "TOOL", "ENVIRONMENT_OR_CREDENTIAL", "PERMISSION")
KINDS = {
    "AGENT": "agent",
    "SKILL": "skill",
    "KNOWLEDGE": "knowledge",
    "RUNTIME_PROFILE": "runtime",
    "MCP": "mcp",
    "WORKFLOW": "workflow",
}


class CoverageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)
    digest: str = Field(pattern="^[a-f0-9]{64}$")
    expectedProposalRevision: int = Field(ge=1)
    idempotencyKey: str = Field(min_length=1, max_length=120)


class CoverageQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)


class CoverageRecovery(CoverageQuery):
    key: str = Field(min_length=1, max_length=120)


def gap_for(reason):
    if any(
        token in reason
        for token in ("UNREADABLE", "NOT_READABLE", "PERMISSION", "AUTHORIZ")
    ):
        return "PERMISSION"
    if "SOURCE" in reason.split("_") or "KNOWLEDGE" in reason:
        return "DATA"
    if "RUNTIME" in reason or "PROFILE" in reason or "CREDENTIAL" in reason:
        return "ENVIRONMENT_OR_CREDENTIAL"
    if "OPERATION" in reason or "EXECUTOR" in reason or "TOOL" in reason:
        return "TOOL"
    if "FAMILY" in reason or "RULE" in reason:
        return "RULES"
    return "MAPPING"


def assess(semantics, members, contents, work, runtime, *, sales_v2_candidate=False):
    """Pure exact contract checks; inputs already authorized by every owner."""
    from .planning_contracts import validation_report

    validation_report(semantics)
    roles = [r for r in semantics.requirements if r.kind == "EMPLOYEE"]
    if not roles or len({r.selected for r in roles if r.selected is not None}) > 1:
        raise ValueError("SINGLE_EXACT_EMPLOYEE_REQUIRED")
    required_source = approved_source(semantics)
    grouped = {}
    for m in members:
        grouped.setdefault(KINDS[m["kind"]], []).append(m)
    expected = {"agent", "skill", "knowledge", "runtime"}
    if set(grouped) != expected or any(
        len(grouped[k]) != 1 for k in ("agent", "knowledge", "runtime")
    ):
        raise ValueError("READONLY_COMPOSITION_MAPPING_UNSUPPORTED")
    refs = {
        k: ExactReference(
            resource_id=v[0]["resource_id"],
            revision_id=v[0]["revision_id"],
            digest=v[0]["digest"].removeprefix("sha256:"),
        )
        for k, v in grouped.items()
    }
    if refs["knowledge"] != required_source:
        raise ValueError("APPROVED_SOURCE_EXACT_VERSION_REQUIRED")
    from .pending_member_requirements import resolve

    semantics, requirement_bindings = resolve(semantics, members, contents)
    source = validate("knowledge", contents["knowledge"], work)
    schema = source["sourceSchema"]
    for kind in ("agent", "runtime"):
        validate(kind, contents[kind], work, expected_source_schema=schema)
    from .task_member_binding import bind_steps

    skills = contents.get("_skills", [(refs["skill"], contents["skill"])])
    case = {
        "document-review-source.v1": "document",
        "tabular-diagnostic-source.v1": "tabular",
        "sales-diagnostic-source.v1": "sales",
        "synthetic-delivery-source.v1": "delivery",
    }.get(schema)
    from .native_readonly_protocol import scope_adapter

    native_adapter = scope_adapter(work)
    if native_adapter is not None:
        if native_adapter.sourceSchema != schema:
            raise ValueError("NATIVE_DATA_SOURCE_SCHEMA_MISMATCH")
        case = "native_readonly"
    if case is None:
        raise ValueError("BUSINESS_RULE_FAMILY_UNSUPPORTED")
    bindings = bind_steps(
        semantics,
        skills,
        source_schema=schema,
        case=case,
        sales_v2_candidate=sales_v2_candidate,
    )
    if sales_v2_candidate:
        import json

        from .sales_gross_profit_integration import is_v2, require_source

        if any(
            is_v2(
                v["operation"]["executorId"],
                v["operation"]["executorRevision"],
                v["operation"]["executorConfigurationDigest"],
            )
            for v in bindings.values()
        ):
            require_source(
                json.loads(
                    contents["knowledge"]["documents"][0]["chunks"][0]["content"]
                )
            )
    if runtime.get("status") != "PASSED":
        raise ValueError("LIVE_RUNTIME_NOT_AVAILABLE")
    return {
        "sourceSchema": schema,
        "sourceContentDigest": source["sourceContentDigest"],
        "operations": sorted({t.operation for t in semantics.tasks}),
        "stepBindings": [
            {
                "taskId": task_id,
                "skill": value["reference"].model_dump(mode="json"),
                "operation": value["operation"]["name"],
                "basis": value["basis"],
            }
            for task_id, value in bindings.items()
        ],
        "requirementBindings": requirement_bindings,
        "exactMembers": len(members),
        "runtime": "LIVE_PROBE_PASSED",
        "actualTests": "REQUIRED_IN_RESOURCE_PREPARATION",
        "executionReady": False,
    }


def coverage(automation, call, plan):
    c = call.connection
    scope = ScopeIdentity(
        call.context.scope.tenant_id, call.context.scope.security_domain
    )
    p = OwnerPrincipal(
        call.context.principal_id, scope.namespace, scope.security_domain
    )
    automation.authenticate(call.context)
    work = automation.work(
        call.context,
        plan.semantics.target.problem,
        automation.grants.clock(),
        connection=c,
    )
    owned_resources.require_plan(work, plan, check_references=False)
    owned_resources.require_capability(automation, call, work)
    automation.bound_app(call).validate_target(p, plan.semantics.target, c)
    runtime = automation.runtime_probe(scope.namespace)
    candidates = []
    rows = (
        [
            {
                "identity": ref.resource_id,
                "revision": ref.revision_id,
                "digest": ref.digest,
            }
            for ref in work.businessScope.employees
        ]
        if isinstance(work, owned_resources.OwnedResourceWork)
        else identities(c, scope, "EMPLOYEE", limit=201)
    )
    for row in rows:
        ref = ExactReference(
            resource_id=row["identity"],
            revision_id=row["revision"],
            digest=row["digest"].removeprefix("sha256:"),
        )
        try:
            require_read(call.authority, p, "EMPLOYEE", ref)
        except AuthorityError:
            continue  # Do not expose hidden identity, count or metadata.
        item = {
            "reference": ref.model_dump(mode="json"),
            "directoryExists": True,
            "access": "READABLE",
            "state": "REJECTED",
            "executionReady": False,
        }
        try:
            definition, name = read_published(c, scope, "EMPLOYEE", ref)
            item.update(name=name, publication="PUBLISHED")
            contents = {"_skills": []}
            visible = []
            for m in definition["members"]:
                kind = "RUNTIME" if m["kind"] == "RUNTIME_PROFILE" else m["kind"]
                exact = ExactReference(
                    resource_id=m["resource_id"],
                    revision_id=m["revision_id"],
                    digest=m["digest"].removeprefix("sha256:"),
                )
                owned_resources.require_reference(work, kind.lower(), exact)
                require_read(call.authority, p, kind, exact)
                content, member_name = read_employee_member(c, scope, ref, kind, exact)
                contents[KINDS[m["kind"]]] = content
                if kind == "SKILL":
                    contents["_skills"].append((exact, content))
                visible.append(
                    {
                        "kind": kind,
                        "name": member_name,
                        "reference": exact.model_dump(mode="json"),
                    }
                )
            checks = assess(
                plan.semantics,
                definition["members"],
                contents,
                work,
                runtime,
                sales_v2_candidate=automation.sales_v2_candidate,
            )
            item.update(
                state="SELECTABLE_FOR_VERIFICATION",
                semanticApplicability="APPROVED_SOURCE_AND_REGISTERED_OPERATION_FAMILY",
                compatibility="EXACT_IO_AND_DEPENDENCY_CHECKED",
                checks=checks,
                members=visible,
                reason="EXACT_CONTRACTS_REQUIRE_FRESH_ACTUAL_VERIFICATION",
            )
        except (
            AuthorityError,
            PlanningError,
            EmployeeDefinitionError,
            ExecutionPreparationError,
            ValueError,
            KeyError,
        ) as exc:
            reason = str(exc)
            # Only bounded codes, never exception strings containing owner data.
            import re

            reason = (
                reason
                if re.fullmatch(r"[A-Z0-9_]{1,120}", reason)
                else "COVERAGE_CONFIGURATION_INVALID"
            )
            item.update(reason=reason, gap=gap_for(reason))
        candidates.append(item)
    current = {
        r.selected
        for r in plan.semantics.requirements
        if r.kind == "EMPLOYEE" and r.selected
    }
    eligible = sorted(
        (x for x in candidates if x["state"] == "SELECTABLE_FOR_VERIFICATION"),
        key=lambda x: (
            ExactReference.model_validate(x["reference"]) not in current,
            x["checks"]["exactMembers"],
            x["reference"]["resource_id"],
            x["reference"]["revision_id"],
        ),
    )
    selected = eligible[0]["reference"] if eligible else None
    present = {x.get("gap") for x in candidates}
    return {
        "schemaVersion": "problem-resource-coverage.v1",
        "subject": p.principal_id,
        "scope": {"tenantId": scope.namespace, "securityDomain": scope.security_domain},
        "planId": plan.plan_id,
        "planVersion": plan.version,
        "planDigest": plan.digest,
        "activity": {
            "formationBasis": "EXISTING_CONFIRMED_PLAN",
            "naturalLanguageGoalCoverage": "NOT_INDEPENDENTLY_VERIFIED",
            "title": plan.semantics.title,
            "target": plan.semantics.target.model_dump(mode="json"),
            "source": approved_source(plan.semantics).model_dump(mode="json"),
            "effect": plan.semantics.effect,
            "boundaries": list(plan.semantics.boundaries),
            "tasks": [
                {
                    "operation": t.operation,
                    "inputs": list(t.inputs),
                    "outputs": list(t.outputs),
                    "dependsOn": list(t.depends_on),
                    "criteria": list(t.criterion_revision_ids),
                }
                for t in plan.semantics.tasks
            ],
        },
        "candidates": candidates,
        "selection": selected,
        "selectionRule": "EXACT_COMMITTED_COMPATIBLE_THEN_MEMBER_COUNT_THEN_CANONICAL_ID",
        "gaps": [
            {
                "kind": kind,
                "status": "INSUFFICIENT_VISIBLE_EVIDENCE"
                if not candidates
                else "OBSERVED"
                if kind in present
                else "NOT_OBSERVED_IN_VISIBLE_CANDIDATES",
            }
            for kind in GAPS
        ],
        "scanLimit": 201,
        "coverageComplete": False,
        "state": "SELECTION_AVAILABLE" if selected else "BLOCKED",
        "executionReady": False,
        "limitations": [
            "CURRENT_AUTHORIZED_PUBLISHED_EMPLOYEE_COMPOSITIONS_ONLY",
            "NO_NEW_RESOURCE_OR_CODE_GENERATION",
            "REGISTERED_SOURCE_OPERATION_FAMILIES_ONLY",
            "HIDDEN_OR_UNSCANNED_RESOURCES_NOT_ASSESSED",
            "ACTUAL_TESTS_AND_EXECUTION_ADMISSION_STILL_REQUIRED",
        ],
    }


class ProblemResourceCoverage:
    def __init__(self, automation):
        self.automation = automation

    def __call__(self, call):
        from .resource_automation import SelectEmployeeResources

        a = self.automation
        args = call.query if call.operation.startswith("READ_") else call.payload
        scope = ScopeIdentity(
            call.context.scope.tenant_id, call.context.scope.security_domain
        )
        app = a.bound_app(call)
        with app.repository.transaction(
            scope, call.path["proposal_id"], authorized=True
        ) as cur:
            baseline = app.repository.read_plan(
                cur, scope, call.path["proposal_id"], args["version"]
            )
            plan = ConfirmedPlanRevision.model_validate(baseline["plan"])
            if baseline["digest"] != plan.digest:
                raise WorkbenchOwnerError(
                    "AUTOMATIC_SELECTION_SOURCE_DIGEST_MISMATCH", 409
                )
            require_supported_lineage(app, cur, scope, plan)
            if call.operation == "READ_PROBLEM_RESOURCE_COVERAGE":
                return coverage(a, call, plan)
            a.authenticate(call.context)
            work = a.work(
                call.context,
                plan.semantics.target.problem,
                a.grants.clock(),
                connection=cur.connection,
                history=call.operation == "READ_PROBLEM_RESOURCE_SELECTION",
            )
            owned_resources.require_plan(work, plan, check_references=False)
            owned_resources.require_capability(a, call, work)
            key = args.get("key", args.get("idempotencyKey"))
            old = call.connection.execute(
                "SELECT record FROM execution_authority.resource_policy_plan_commands WHERE namespace=%s AND security_domain=%s AND subject_id=%s AND request_key=%s",
                (
                    scope.namespace,
                    scope.security_domain,
                    call.context.principal_id,
                    key,
                ),
            ).fetchone()
            if old:
                result = old["record"]
                if owned_resources.evidence(work) and result.get(
                    "ownedBusiness"
                ) != owned_resources.evidence(work):
                    raise AuthorityError("OWNED_BUSINESS_PREPARATION_CHANGED")
                proof = result.get("automaticCoverage")
                if not proof or proof["planDigest"] != plan.digest:
                    raise WorkbenchOwnerError("AUTOMATIC_SELECTION_KEY_CONFLICT", 409)
                if call.operation == "SELECT_PROBLEM_RESOURCES" and (
                    args["digest"] != plan.digest
                    or args["expectedProposalRevision"] != plan.source_proposal_revision
                ):
                    raise WorkbenchOwnerError("AUTOMATIC_SELECTION_KEY_CONFLICT", 409)
                if result["policyBasis"]["policy_digest"] != a.policy.digest:
                    raise WorkbenchOwnerError("AUTOMATIC_SELECTION_POLICY_CHANGED", 409)
                principal = OwnerPrincipal(
                    call.context.principal_id, scope.namespace, scope.security_domain
                )
                for candidate in proof["candidates"]:
                    require_read(
                        call.authority,
                        principal,
                        "EMPLOYEE",
                        ExactReference.model_validate(candidate["reference"]),
                    )
                    for member in candidate.get("members", []):
                        require_read(
                            call.authority,
                            principal,
                            member["kind"],
                            ExactReference.model_validate(member["reference"]),
                        )
                a.recheck(call, result["preflight"])
                return result
            if call.operation == "READ_PROBLEM_RESOURCE_SELECTION":
                raise WorkbenchOwnerError("AUTOMATIC_SELECTION_NOT_FOUND", 404)
            request = CoverageRequest.model_validate(args)
            if (
                request.digest != plan.digest
                or request.expectedProposalRevision != plan.source_proposal_revision
            ):
                raise WorkbenchOwnerError("AUTOMATIC_SELECTION_PLAN_CONFLICT", 409)
            report = coverage(a, call, plan)
            if report["selection"] is None:
                raise WorkbenchOwnerError("AUTOMATIC_SELECTION_COVERAGE_BLOCKED", 409)
            command = SelectEmployeeResources(
                **request.model_dump(), employee=report["selection"]
            )
            return a.select_employee(
                replace(
                    call,
                    operation="SELECT_POLICY_EMPLOYEE_RESOURCES",
                    payload=command.model_dump(mode="json"),
                ),
                automatic_coverage=report,
            )
