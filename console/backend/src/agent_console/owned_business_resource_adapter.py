"""Consume a saved business admission through existing resource/execution owners.

No admission, grant, resource or execution is created by this adapter.
"""

from dataclasses import replace
from typing import Any

from pydantic import Field, model_serializer

from .authority_contracts import AuthorityError
from .plan_suggestion_domain import ExactReference
from .resource_automation_policy import WorkScope


class OwnedResourceWork(WorkScope):
    admissionId: str
    admissionRecordDigest: str
    admissionPolicyDigest: str
    businessScope: Any
    historyRead: bool = False
    ontologyCorrection: dict | None = None
    assemblyAdoption: dict | None = None
    selectionAdmission: dict | None = Field(default=None, exclude=True)
    selectedOntologySuccessor: ExactReference | None = Field(default=None, exclude=True)

    @model_serializer(mode="wrap")
    def compatible_work(self, handler):
        result = handler(self)
        if self.assemblyAdoption is None:
            result.pop("assemblyAdoption", None)
        return result


def derive_work(
    owner, connection, context, problem, *, source_digest=None, history=False, plan=None
):
    binding = owner.work(
        connection,
        context,
        problem,
        source_digest=source_digest,
        **({"plan": plan} if plan is not None else {}),
        **({"history": True} if history else {}),
    )
    return from_binding(binding, context, problem, history=history)


def from_binding(binding, context, problem, *, history=False):
    if (
        (getattr(binding, "history_only", False) and not history)
        or binding.problem != problem
        or binding.subject_id != context.principal_id
        or binding.tenant_id != context.scope.tenant_id
        or binding.security_domain != context.scope.security_domain
        or binding.scope.effectPolicy != "READ_ONLY"
        or binding.scope.externalWrites is not False
        or not binding.scope.operations
    ):
        raise AuthorityError("OWNED_BUSINESS_RESOURCE_SCOPE_DENIED")
    return OwnedResourceWork(
        namespace=context.scope.tenant_id,
        securityDomain=context.scope.security_domain,
        subject=context.principal_id,
        problem=problem,
        sourceContentDigests=(binding.scope.sourceContentDigest,),
        expiresAt=binding.expires_at,
        admissionId=binding.admission_id,
        admissionRecordDigest=binding.record_digest,
        admissionPolicyDigest=binding.policy_digest,
        businessScope=binding.scope,
        historyRead=history,
        ontologyCorrection=getattr(binding, "ontology_correction", None),
        assemblyAdoption=getattr(binding, "assembly_adoption", None),
    )


def evidence(work):
    if not isinstance(work, OwnedResourceWork):
        return None
    result = {
        "admissionId": work.admissionId,
        "recordDigest": work.admissionRecordDigest,
        "policyDigest": work.admissionPolicyDigest,
        "scopeId": work.businessScope.scopeId,
        "authorizationBasisDigest": work.businessScope.authorizationBasisDigest,
    }
    if work.assemblyAdoption is not None:
        result["assemblyAdoption"] = work.assemblyAdoption
    return result


def digest_basis(basis, work):
    proof = evidence(work)
    return [*basis, proof] if proof else basis


def require_reference(work, kind, reference):
    if not isinstance(work, OwnedResourceWork):
        return
    scope = work.businessScope
    allowed = {
        "agent": scope.agents,
        "employee": scope.employees,
        "skill": scope.skills,
        "runtime": scope.runtimes,
        "knowledge": (scope.source,),
    }
    if reference not in allowed.get(kind, ()):
        raise AuthorityError("OWNED_BUSINESS_RESOURCE_NOT_AUTHORIZED")


def require_plan(work, plan, *, check_references=True, selection_predecessor=None):
    if not isinstance(work, OwnedResourceWork):
        return
    from .planning_source_change import approved_source

    if (
        work.selectionAdmission is not None
        and selection_predecessor is None
        and check_references
    ):
        raise AuthorityError("OWNED_BUSINESS_SUCCESSOR_SELECTION_ONLY")
    if work.assemblyAdoption is not None:
        from .owned_resource_assembly import plan_reference

        if (
            plan_reference(selection_predecessor or plan).model_dump(mode="json")
            != work.assemblyAdoption["plan"]
        ):
            raise AuthorityError("OWNED_ASSEMBLY_PLAN_CHANGED")
    from .owned_ontology_successor import MARKER, marker

    ontology_refs = [v for v in plan.semantics.boundaries if v.startswith(MARKER)]
    if ontology_refs and (
        work.businessScope.documentRules is None
        or ontology_refs != [marker(work.businessScope.documentRules.ontology)]
    ):
        raise AuthorityError("OWNED_ONTOLOGY_SUCCESSOR_PLAN_BINDING_CHANGED")
    if selection_predecessor is not None:
        from .owned_resource_assembly import require_selection_rebinding

        require_selection_rebinding(work, selection_predecessor, plan)

    if work.ontologyCorrection is not None:
        ref = ExactReference.model_validate(work.ontologyCorrection["originalPlan"])
        if (plan.plan_id, str(plan.version), plan.digest) != (
            ref.resource_id,
            ref.revision_id,
            ref.digest,
        ):
            raise AuthorityError("OWNED_BUSINESS_CORRECTION_PLAN_MISMATCH")

    if (
        plan.semantics.target.problem != work.problem
        or approved_source(plan.semantics) != work.businessScope.source
        or any(
            t.operation not in work.businessScope.operations
            for t in plan.semantics.tasks
        )
    ):
        raise AuthorityError("OWNED_BUSINESS_PLAN_NOT_AUTHORIZED")
    if not check_references:
        return
    for requirement in plan.semantics.requirements:
        if requirement.selected is not None:
            kind = {"RUNTIME": "runtime"}.get(
                requirement.kind, requirement.kind.lower()
            )
            require_reference(work, kind, requirement.selected)


def require_employee(work, employee, refs):
    if not isinstance(work, OwnedResourceWork):
        return
    if not employee or not employee[1]["published"]:
        raise AuthorityError("OWNED_BUSINESS_PUBLISHED_EMPLOYEE_REQUIRED")
    require_reference(work, "employee", employee[0])
    for kind, ref in refs:
        require_reference(work, kind, ref)
    members = {
        (
            m["kind"],
            m["resource_id"],
            m["revision_id"],
            m["digest"].removeprefix("sha256:"),
        )
        for m in employee[1]["revision"]["members"]
    }
    actual = {
        (
            "RUNTIME_PROFILE" if kind == "runtime" else kind.upper(),
            ref.resource_id,
            ref.revision_id,
            ref.digest,
        )
        for kind, ref in refs
    }
    if members != actual:
        raise AuthorityError("OWNED_BUSINESS_EXACT_EMPLOYEE_MEMBERS_REQUIRED")


def require_ready(work, ready):
    if not isinstance(work, OwnedResourceWork):
        return
    if ready.get("ownedBusiness") != evidence(work):
        raise AuthorityError("OWNED_BUSINESS_PREPARATION_CHANGED")
    require_reference(
        work, "employee", ExactReference.model_validate(ready["assembly"]["definition"])
    )
    for item in ready["resources"]:
        require_reference(
            work, item["kind"], ExactReference.model_validate(item["reference"])
        )


def readonly_work(work):
    from .readonly_continuation_policy import ReadonlyWork

    scope = work.businessScope
    from .native_readonly_protocol import NativeReadonlyWork

    projected = NativeReadonlyWork if scope.case == "native_readonly" else ReadonlyWork
    return projected(
        **{
            key: getattr(work, key)
            for key in (
                "namespace",
                "securityDomain",
                "subject",
                "problem",
                "sourceContentDigests",
                "expiresAt",
            )
        },
        **({"adapter": scope.adapter} if scope.case == "native_readonly" else {}),
        case=scope.case,
        nativeAgentName=scope.nativeAgentName,
        documentRules=scope.documentRules,
    )


def require_capability(automation, call, work, resolved=None):
    if not isinstance(work, OwnedResourceWork):
        return
    from .business_capability_postgres import PostgresBusinessCapabilityRepository
    from .workbench_business_capability import CapabilityOwner, CapabilityReferences

    ref = work.businessScope.capability
    if ref is None:
        if resolved is not None:
            raise AuthorityError("OWNED_BUSINESS_CAPABILITY_MISMATCH")
        return
    if resolved is not None and resolved["contract"]["capability"] != ref.model_dump(
        mode="json"
    ):
        raise AuthorityError("OWNED_BUSINESS_CAPABILITY_MISMATCH")
    owner = CapabilityOwner(
        PostgresBusinessCapabilityRepository(None),
        CapabilityReferences(automation.employees, automation.services),
        None,
    )
    value = owner(
        replace(
            call,
            operation="READ_CAPABILITY_REVISION",
            path={"capability_id": ref.resource_id, "revision_id": ref.revision_id},
        )
    )
    if value["state"] != "PUBLISHED" or value["digest"] != ref.digest:
        raise AuthorityError("OWNED_BUSINESS_CAPABILITY_NOT_PUBLISHED")
    for binding in value["revision"]["bindings"]:
        kind = binding["kind"]
        reference = ExactReference.model_validate(binding["reference"])
        if kind == "ONTOLOGY":
            rules = work.businessScope.documentRules
            if rules is None or rules.ontology != reference:
                raise AuthorityError("OWNED_BUSINESS_ONTOLOGY_MISMATCH")
        else:
            require_reference(
                work, {"RUNTIME_PROFILE": "runtime"}.get(kind, kind.lower()), reference
            )


def require_preparation(work, preparation):
    if not isinstance(work, OwnedResourceWork):
        return
    if work.historyRead:
        raise AuthorityError("OWNED_BUSINESS_HISTORY_NOT_EXECUTABLE")
    if preparation.semantics.target.problem != work.problem:
        raise AuthorityError("OWNED_BUSINESS_PREPARATION_TARGET_MISMATCH")
    if work.ontologyCorrection is not None:
        ref = ExactReference.model_validate(work.ontologyCorrection["originalPlan"])
        if (
            preparation.plan_id != ref.resource_id
            or preparation.plan_version != int(ref.revision_id) + 1
        ):
            raise AuthorityError("OWNED_BUSINESS_CORRECTION_PLAN_MISMATCH")
    require_reference(work, "knowledge", preparation.source_snapshot)
    for participant in preparation.participants:
        if work.businessScope.case == "native_readonly":
            from .native_data_skill import exact_executor
            from .skill_invocation_domain import ExecutorRevision

            try:
                adapter = exact_executor(
                    ExecutorRevision(
                        participant.executor_id,
                        participant.executor_revision,
                        participant.executor_digest,
                    )
                ).adapter
            except ValueError as exc:
                raise AuthorityError("OWNED_BUSINESS_NATIVE_ADAPTER_MISMATCH") from exc
            if adapter.descriptor() != work.businessScope.adapter.model_dump(
                mode="json"
            ):
                raise AuthorityError("OWNED_BUSINESS_NATIVE_ADAPTER_MISMATCH")
        require_reference(work, "employee", participant.definition)
        require_reference(work, "runtime", participant.profile)
        for resource in (participant.skill, *participant.resources):
            require_reference(work, resource.kind.lower(), resource.reference)
        if participant.skill.operation not in work.businessScope.operations:
            raise AuthorityError("OWNED_BUSINESS_OPERATION_NOT_AUTHORIZED")
    rules = getattr(preparation, "business_semantics", None)
    if rules != work.businessScope.documentRules:
        raise AuthorityError("OWNED_BUSINESS_ONTOLOGY_MISMATCH")


def authorize_dispatch(owner, connection, command, context):
    """Effect-time guard in the original authority transaction; never dispatches.

    A legacy receipt keeps its existing grant checks. A receipt naming the new
    admission cannot be consumed by a host without that same current owner.
    """
    from datetime import UTC, datetime

    from .ontology_execution import parse_preparation
    from .prepared_execution_lineage import prepared_attempt

    if not command.authorization_resource.startswith("governed-execution:prepared:"):
        return True
    bound = prepared_attempt(connection, command.scope, command.attempt_id)
    if bound is None:
        return False
    preparation = parse_preparation(bound["preparation"])
    if (
        command.authorization_resource
        != "governed-execution:prepared:" + preparation.digest
    ):
        return False
    present = connection.execute(
        "SELECT to_regclass('execution_authority.prepared_resource_commands') AS name"
    ).fetchone()["name"]
    if present is None:
        return True  # Historical preparation owner without continuation feature.
    rows = connection.execute(
        "SELECT result FROM execution_authority.prepared_resource_commands "
        "WHERE namespace=%s AND security_domain=%s AND actor_id=%s "
        "AND result->>'preparationDigest'=%s",
        (
            command.scope.namespace,
            command.scope.security_domain,
            command.principal_id,
            preparation.digest,
        ),
    ).fetchall()
    if not rows:
        return True  # Non-continuation preparation retains its original owner.
    if len(rows) != 1:
        return False
    receipt = rows[0]["result"]
    if receipt.get("ownedBusiness") is None:
        return True
    if owner is None or context.principal_id != receipt["subject"]:
        return False
    try:
        work = derive_work(
            owner,
            connection,
            context,
            preparation.semantics.target.problem,
            source_digest=receipt["sourceContentDigest"],
            plan=(
                ExactReference(
                    resource_id=receipt["sourcePlanId"],
                    revision_id=str(receipt["sourcePlanVersion"]),
                    digest=receipt["sourcePlanDigest"],
                )
                if receipt["ownedBusiness"].get("assemblyAdoption")
                else None
            ),
        )
        if (
            evidence(work) != receipt["ownedBusiness"]
            or receipt["runId"] != str(bound["workflow_run_id"])
            or work.businessScope.case != receipt["case"]
            or work.businessScope.nativeAgentName != receipt["nativeAgentName"]
            or command.agent_name != receipt["nativeAgentName"]
            or datetime.fromisoformat(receipt["authorizationExpiresAt"])
            <= datetime.now(UTC)
        ):
            return False
        if receipt.get("ontologyActionCorrection") != work.ontologyCorrection:
            return False
        if work.ontologyCorrection is not None:
            ref = ExactReference.model_validate(work.ontologyCorrection["originalPlan"])
            if (
                receipt.get("sourcePlanId"),
                str(receipt.get("sourcePlanVersion")),
                receipt.get("sourcePlanDigest"),
            ) != (ref.resource_id, ref.revision_id, ref.digest) or receipt[
                "executionPlan"
            ]["plan"].get("predecessor_digest") != ref.digest:
                return False
        require_preparation(work, preparation)
        return True
    except (AuthorityError, ValueError):
        return False
