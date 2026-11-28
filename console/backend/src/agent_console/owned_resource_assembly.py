"""Explicit same-scope resource adoption through immutable selection receipts.

Publication alone never activates a resource. Only the existing selection owner
may persist this proof, with its explicitly confirmed successor Plan. Consumers
revalidate the original admission, current permissions and exact publications.
"""

from dataclasses import replace
from datetime import UTC, datetime

from .authority_contracts import AuthorityError, ExactGrant
from .execution_domain import ScopeIdentity
from .plan_suggestion_domain import ConfirmedPlanRevision, ExactReference
from .planning_candidates import read_published
from .resource_use_domain import canonical_digest
from .workbench_prepared_resources import OWNERS, reference

MODE = "SAME_SCOPE_SELECTED_V1"


def require(condition, reason):
    if not condition:
        raise AuthorityError("OWNED_ASSEMBLY_" + reason)


def plan_reference(plan):
    if isinstance(plan, ExactReference):
        return plan
    return ExactReference(
        resource_id=plan.plan_id, revision_id=str(plan.version), digest=plan.digest
    )


def admission_basis(work):
    return {
        "admissionId": work.admissionId,
        "recordDigest": work.admissionRecordDigest,
        "policyDigest": work.admissionPolicyDigest,
        "scopeId": work.businessScope.scopeId,
        "authorizationBasisDigest": work.businessScope.authorizationBasisDigest,
    }


def members_of(employee):
    result = []
    for item in employee["members"]:
        kind = {"RUNTIME_PROFILE": "runtime"}.get(item["kind"], item["kind"].lower())
        require(kind in {"knowledge", "agent", "skill", "runtime"}, "MEMBER_KIND")
        result.append(
            (
                kind,
                ExactReference(
                    resource_id=item["resource_id"],
                    revision_id=item["revision_id"],
                    digest=item["digest"].removeprefix("sha256:"),
                ),
            )
        )
    require(len(result) == len(set(result)), "DUPLICATE_MEMBER")
    return sorted(
        result, key=lambda item: (item[0], item[1].resource_id, item[1].revision_id)
    )


def require_current_employee(c, scope, employee):
    published = c.execute(
        "SELECT revision_id,revision_digest FROM digital_employee_definition.facts "
        "WHERE namespace=%s AND security_domain=%s AND definition_id=%s "
        "AND action='PUBLISH' ORDER BY ordinal DESC LIMIT 1",
        (scope.namespace, scope.security_domain, employee.resource_id),
    ).fetchone()
    require(
        published
        == {"revision_id": employee.revision_id, "revision_digest": employee.digest},
        "EMPLOYEE_CURRENT_REQUIRED",
    )


def read_assembly(
    reader,
    c,
    context,
    original_scope,
    employee,
    *,
    selecting,
    history=False,
    ontology_successor=None,
    _ontology_evidence=None,
):
    """Current READ/ontology USE plus published immutable complete composition.

    Resource invocation/assignment grants remain the original prepared execution
    owner's job; no invented generic USE action or grant is introduced here.
    """
    from .digital_employee_definition import EmployeeRevision
    from .digital_employee_definition_postgres import (
        PostgresEmployeeDefinitionRepository,
    )
    from .owned_business_resource_adapter import OwnedResourceWork
    from .resource_automation_validation import validate

    scope = ScopeIdentity(context.scope.tenant_id, context.scope.security_domain)
    g = ExactGrant(
        "EMPLOYEE", "READ", f"employee:{employee.resource_id}:{employee.revision_id}"
    )
    reader._reads(c, context, (g,), datetime.now(UTC), history=history)
    content, _ = read_published(c, scope, "EMPLOYEE", employee)
    if selecting:
        require_current_employee(c, scope, employee)
    PostgresEmployeeDefinitionRepository.validate_members(
        c, EmployeeRevision.from_record(content), published_binding=not selecting
    )
    members = members_of(content)
    grouped = {
        kind: tuple(ref for k, ref in members if k == kind)
        for kind in ("knowledge", "agent", "skill", "runtime")
    }
    require(grouped["knowledge"] == (original_scope.source,), "SOURCE_CHANGED")
    require(set(grouped["runtime"]) == set(original_scope.runtimes), "RUNTIME_CHANGED")
    require(grouped["agent"] and grouped["skill"], "MEMBERS_REQUIRED")
    require(original_scope.capability is None, "CAPABILITY_SUCCESSOR_REQUIRED")
    grants = [
        ExactGrant(
            OWNERS[k], "READ_RESOURCE", reference(k, r.resource_id, r.revision_id)
        )
        for k, r in members
    ]
    if original_scope.documentRules is not None:
        from .ontology_service import resource

        ontology = original_scope.documentRules.ontology
        grants.extend(
            ExactGrant(
                "BUSINESS_ONTOLOGY",
                action,
                resource(ontology.resource_id, ontology.revision_id),
            )
            for action in ("READ", "USE")
        )
    reader._reads(c, context, tuple(grants), datetime.now(UTC), history=history)
    # Compare against the standing policy's exact registered contracts. A new
    # executor, operation, IO schema, external effect or model/profile is denied.
    allowed_skills = []
    for ref in original_scope.skills:
        value, _ = read_published(c, scope, "SKILL", ref, _published_binding=True)
        allowed_skills.append(canonical_digest(value.get("operations", [])))
    allowed_agents = []
    for ref in original_scope.agents:
        value, _ = read_published(c, scope, "AGENT", ref, _published_binding=True)
        allowed_agents.append(
            canonical_digest(
                {
                    key: value.get(key)
                    for key in (
                        "data",
                        "knowledge",
                        "skills",
                        "capabilities",
                        "runtimes",
                        "bindings",
                    )
                }
            )
        )
    for kind, ref in members:
        value, _ = read_published(
            c, scope, kind.upper(), ref, _published_binding=not selecting
        )
        if kind == "skill":
            require(
                canonical_digest(value.get("operations", [])) in allowed_skills,
                "EXECUTOR_CONTRACT_CHANGED",
            )
        elif kind == "agent":
            require(
                canonical_digest(
                    {
                        key: value.get(key)
                        for key in (
                            "data",
                            "knowledge",
                            "skills",
                            "capabilities",
                            "runtimes",
                            "bindings",
                        )
                    }
                )
                in allowed_agents,
                "AGENT_AUTHORITY_CHANGED",
            )
    from .owned_ontology_successor import resolve as resolve_ontology

    document_rules, ontology_evidence = resolve_ontology(
        reader,
        c,
        context,
        original_scope,
        employee,
        grouped["skill"],
        requested=ontology_successor,
        history=history,
        selecting=selecting,
    )
    if _ontology_evidence is not None and ontology_evidence is not None:
        _ontology_evidence.update(ontology_evidence)
    if document_rules is not None:
        from .ontology_execution import published_content

        ontology_content = published_content(c, scope, document_rules)
        for ref in grouped["skill"]:
            skill, _ = read_published(
                c, scope, "SKILL", ref, _published_binding=not selecting
            )
            require(
                all(
                    any(
                        action.skill == ref
                        and action.operation == op["name"]
                        and (
                            action.executor_id,
                            action.executor_revision,
                            action.executor_digest,
                        )
                        == (
                            op["executorId"],
                            op["executorRevision"],
                            op["executorConfigurationDigest"],
                        )
                        for action in ontology_content.actions
                    )
                    for op in skill.get("operations", [])
                ),
                "ONTOLOGY_SUCCESSOR_REQUIRED",
            )
    projected = type(original_scope).model_validate(
        {
            **original_scope.model_dump(mode="json"),
            "employees": (employee,),
            "agents": grouped["agent"],
            "skills": grouped["skill"],
            "documentRules": document_rules,
        }
    )
    # Run the existing registered read-only validators without granting anything.
    validating_work = OwnedResourceWork(
        namespace=scope.namespace,
        securityDomain=scope.security_domain,
        subject=context.principal_id,
        problem=ExactReference(
            resource_id="assembly-validation", revision_id="1", digest="0" * 64
        ),
        sourceContentDigests=(projected.sourceContentDigest,),
        expiresAt=reader.policy.expiresAt,
        admissionId="validation",
        admissionRecordDigest="0" * 64,
        admissionPolicyDigest=reader.policy.digest,
        businessScope=projected,
    )
    for kind, ref in members:
        value, _ = read_published(
            c, scope, kind.upper(), ref, _published_binding=not selecting
        )
        validate(kind, value, validating_work)
    return projected, [
        {"kind": kind, "reference": ref.model_dump(mode="json")}
        for kind, ref in members
    ]


def selection_work(
    automation, call, work, old_plan, employee, *, ontology_successor=None
):
    """Selection owner's temporary candidate, never a dispatch authorization."""
    from .owned_business_resource_adapter import OwnedResourceWork

    if not isinstance(work, OwnedResourceWork):
        return work, None
    already_adopted = employee in work.businessScope.employees and (
        work.assemblyAdoption is not None or work.selectionAdmission is not None
    )
    if (
        employee in work.businessScope.employees
        and not already_adopted
        and ontology_successor is None
    ):
        return work, None
    if getattr(work.businessScope, "trustedAssemblyAdoption", None) != MODE:
        from .owned_business_resource_adapter import require_reference

        # Preserve the legacy default-OFF denial and its registered reason code.
        require_reference(work, "employee", employee)
    require(not work.historyRead, "HISTORY_NOT_EXECUTABLE")
    require(
        work.ontologyCorrection is None,
        "ONTOLOGY_CORRECTION_SELECTION_REQUIRES_SUCCESSOR",
    )
    reader = automation.owned_business.work_reader
    ensure_no_pending_execution(call.connection, call.context, plan_reference(old_plan))
    original = reader.policy.selected(
        {
            "source": work.businessScope.source.model_dump(mode="json"),
            "sourceContentDigest": work.businessScope.sourceContentDigest,
            "sourceSchema": "document-review-source.v1"
            if work.businessScope.case == "document"
            else getattr(
                work.businessScope, "sourceSchema", "sales-diagnostic-source.v1"
            ),
        }
    )
    ontology_lineage = None
    if (
        work.assemblyAdoption is not None
        and work.businessScope.documentRules != original.documentRules
    ):
        from .owned_ontology_successor import adopted_evidence

        ontology_lineage = adopted_evidence(
            reader,
            call.connection,
            call.context,
            work,
            plan_reference(old_plan),
            work.businessScope.skills,
        )
        require(ontology_lineage is not None, "ONTOLOGY_ADOPTED_LINEAGE_REQUIRED")
        original = work.businessScope
    ontology_evidence = {}
    projected, members = read_assembly(
        reader,
        call.connection,
        call.context,
        original,
        employee,
        selecting=not already_adopted,
        ontology_successor=ontology_successor,
        _ontology_evidence=ontology_evidence,
    )
    old_refs = [
        r.selected
        for r in old_plan.semantics.requirements
        if r.kind == "EMPLOYEE" and r.selected is not None
    ]
    require(
        len(old_refs) == 1 and old_refs[0] in work.businessScope.employees,
        "PREDECESSOR_EMPLOYEE_REQUIRED",
    )
    proof = {
        "schemaVersion": "same-scope-resource-assembly.v1",
        "admission": admission_basis(work),
        "previousPlan": plan_reference(old_plan).model_dump(mode="json"),
        "employee": employee.model_dump(mode="json"),
        "members": members,
        "scope": projected.model_dump(mode="json"),
        "authorityGeneration": reader.generation,
        "recoveryEpoch": reader.recovery_epoch,
        "subject": call.context.principal_id,
    }
    if ontology_evidence:
        proof["ontologySuccessor"] = ontology_evidence
    if ontology_lineage:
        proof["ontologyPredecessor"] = ontology_lineage["plan"]
        proof["ontologyPredecessorDigest"] = ontology_lineage["digest"]
    # Only this owner-local candidate bypasses the old exact arrays; all other
    # gates are retained and the new Plan/receipt must commit in the same UoW.
    return work.model_copy(
        update={
            "businessScope": projected,
            "selectedOntologySuccessor": projected.documentRules.ontology
            if (ontology_evidence or ontology_lineage)
            else None,
        }
    ), proof


def finish_proof(proof, confirmed):
    if proof is None:
        return None
    plan = ConfirmedPlanRevision.model_validate(confirmed["plan"])
    previous = ExactReference.model_validate(proof["previousPlan"])
    require(
        plan.plan_id == previous.resource_id
        and plan.version == int(previous.revision_id) + 1
        and plan.predecessor_digest == previous.digest,
        "SUCCESSOR_REQUIRED",
    )
    body = {**proof, "plan": plan_reference(plan).model_dump(mode="json")}
    return {"body": body, "digest": canonical_digest(body)}


def _project(reader, c, context, binding, plan):
    """Exact Plan readback only; never chooses latest or alters the base scope."""
    if plan is None:
        return binding
    requested = plan_reference(plan)
    if getattr(binding.scope, "trustedAssemblyAdoption", None) != MODE:
        return binding
    present = c.execute(
        "SELECT to_regclass("
        "'execution_authority.resource_policy_plan_commands') AS name"
    ).fetchone()
    if present["name"] is None:
        return binding
    rows = c.execute(
        "SELECT request_key,record FROM "
        "execution_authority.resource_policy_plan_commands "
        "WHERE namespace=%s AND security_domain=%s AND subject_id=%s "
        "AND record ? 'assemblyAdoption' "
        "AND record->'assemblyAdoption'->'body'->'plan'->>'resource_id'=%s "
        "AND record->'assemblyAdoption'->'body'->'plan'->>'revision_id'=%s",
        (
            binding.tenant_id,
            binding.security_domain,
            binding.subject_id,
            requested.resource_id,
            requested.revision_id,
        ),
    ).fetchall()
    if not rows:
        return execution_projection(reader, c, context, binding, requested)
    require(len(rows) == 1, "AMBIGUOUS_BINDING")
    result = rows[0]["record"]
    proof = result["assemblyAdoption"]
    body = proof["body"]
    require(proof["digest"] == canonical_digest(body), "PROOF_CORRUPT")
    expected = {
        "admissionId": binding.admission_id,
        "recordDigest": binding.record_digest,
        "policyDigest": binding.policy_digest,
        "scopeId": binding.scope.scopeId,
        "authorizationBasisDigest": binding.scope.authorizationBasisDigest,
    }
    require(
        body["schemaVersion"] == "same-scope-resource-assembly.v1"
        and body["admission"] == expected
        and body["subject"] == context.principal_id == binding.subject_id
        and body["authorityGeneration"] == reader.generation
        and body["recoveryEpoch"] == reader.recovery_epoch
        and body["plan"] == requested.model_dump(mode="json"),
        "BINDING_CHANGED",
    )
    confirmed = ConfirmedPlanRevision.model_validate(result["confirmation"]["plan"])
    require(
        plan_reference(confirmed) == requested
        and result["confirmation"]["digest"] == requested.digest,
        "PLAN_CHANGED",
    )
    from .plan_suggestion_postgres import PostgresPlanningRepository

    repository = PostgresPlanningRepository(None, connection=c)
    identity = ScopeIdentity(binding.tenant_id, binding.security_domain)
    actual = repository.read_plan(
        c, identity, requested.resource_id, int(requested.revision_id)
    )
    require(
        actual["digest"] == requested.digest
        and actual["plan"] == result["confirmation"]["plan"]
        and actual["approval"] == result["confirmation"]["approval"]
        and actual["approval"]["decision"] == "APPROVE",
        "PLAN_CHANGED",
    )
    require(confirmed.semantics.target.problem == binding.problem, "PROBLEM_CHANGED")
    previous = ExactReference.model_validate(body["previousPlan"])
    require(
        confirmed.predecessor_digest == previous.digest
        and confirmed.plan_id == previous.resource_id
        and confirmed.version == int(previous.revision_id) + 1,
        "SUCCESSOR_REQUIRED",
    )
    require(result["ownedBusiness"] == expected, "ADMISSION_CHANGED")
    employee = ExactReference.model_validate(body["employee"])
    ontology_evidence = {}
    adopted_ontology = body.get("ontologySuccessor")
    effective_scope = binding.scope
    ontology_predecessor = body.get("ontologyPredecessor")
    if ontology_predecessor:
        from .owned_business_resource_adapter import from_binding
        from .owned_ontology_successor import adopted_evidence, lineage_guard

        require(
            ontology_predecessor == body["previousPlan"],
            "ONTOLOGY_LINEAGE_PLAN_CHANGED",
        )
        with lineage_guard(requested):
            prior_binding = reader.work(
                c, context, binding.problem, history=True, plan=previous
            )
        require(
            prior_binding.admission_id == binding.admission_id
            and prior_binding.ontology_correction is None
            and prior_binding.scope.documentRules is not None
            and prior_binding.scope.documentRules != binding.scope.documentRules,
            "ONTOLOGY_LINEAGE_ADMISSION_CHANGED",
        )
        witness = from_binding(prior_binding, context, binding.problem, history=True)
        lineage = adopted_evidence(
            reader, c, context, witness, previous, witness.businessScope.skills
        )
        require(
            lineage is not None
            and lineage["plan"] == ontology_predecessor
            and lineage["digest"] == body.get("ontologyPredecessorDigest"),
            "ONTOLOGY_LINEAGE_PROOF_CHANGED",
        )
        # Scope is a contract comparison template. The current outer admission
        # and fresh member/ontology READ+USE checks below authorize this work.
        effective_scope = prior_binding.scope
    projected, members = read_assembly(
        reader,
        c,
        context,
        effective_scope,
        employee,
        selecting=False,
        history=binding.history_only,
        ontology_successor=adopted_ontology["ontology"] if adopted_ontology else None,
        _ontology_evidence=ontology_evidence,
    )
    if adopted_ontology:
        from .owned_ontology_successor import marker

        require(
            ontology_evidence == adopted_ontology
            and marker(projected.documentRules.ontology)
            in confirmed.semantics.boundaries,
            "ONTOLOGY_SUCCESSOR_PROOF_CHANGED",
        )
    else:
        require(not ontology_evidence, "ONTOLOGY_SUCCESSOR_PROOF_REQUIRED")
    if ontology_predecessor:
        from .owned_ontology_successor import marker

        require(
            marker(projected.documentRules.ontology) in confirmed.semantics.boundaries,
            "ONTOLOGY_LINEAGE_PLAN_BINDING_CHANGED",
        )
    require(
        body["scope"] == projected.model_dump(mode="json")
        and body["members"] == members,
        "COMPOSITION_CHANGED",
    )
    return replace(
        binding,
        scope=projected,
        assembly_adoption={
            "digest": proof["digest"],
            "plan": body["plan"],
            "requestKey": rows[0]["request_key"],
        },
    )


def selection_semantics(semantics, projected_scope, *, ontology_reference=None):
    """Rebind only selected member requirements in the explicit new assembly.

    Task graph, operations, criteria and business semantics are never edited.
    Ambiguous member selection remains a normal explicit clarification.
    """
    options = {
        "AGENT": projected_scope.agents,
        "SKILL": projected_scope.skills,
        "RUNTIME": projected_scope.runtimes,
        "KNOWLEDGE": (projected_scope.source,),
    }
    value = semantics.model_dump(mode="json")
    if ontology_reference is not None:
        from .owned_ontology_successor import MARKER, marker

        value["boundaries"] = [
            s for s in value["boundaries"] if not s.startswith(MARKER)
        ] + [marker(ontology_reference)]
    for item in value["requirements"]:
        choices = options.get(item["kind"])
        if choices is None or item.get("selected") is None:
            continue
        current = ExactReference.model_validate(item["selected"])
        if current in choices:
            continue
        same_identity = [r for r in choices if r.resource_id == current.resource_id]
        matches = same_identity if same_identity else list(choices)
        require(len(matches) == 1, "MEMBER_SELECTION_AMBIGUOUS")
        item["selected"] = matches[0].model_dump(mode="json")
    return type(semantics).model_validate(value)


def ensure_no_pending_execution(c, context, previous):
    """An unknown/active old execution is observed, never superseded/replayed."""
    tables = c.execute(
        "SELECT to_regclass("
        "'execution_authority.prepared_resource_commands') AS receipts, "
        "to_regclass('execution_authority.native_dispatch_commands') AS commands"
    ).fetchone()
    if not tables["receipts"] or not tables["commands"]:
        return
    row = c.execute(
        "SELECT 1 FROM execution_authority.prepared_resource_commands r JOIN "
        "execution_authority.native_dispatch_commands d ON d.namespace=r.namespace "
        "AND d.security_domain=r.security_domain AND d.principal_id=r.actor_id "
        "AND d.authorization_resource='governed-execution:prepared:'||"
        "(r.result->>'preparationDigest') "
        "WHERE r.namespace=%s AND r.security_domain=%s AND r.actor_id=%s "
        "AND (r.result->>'sourcePlanId'=%s OR "
        "r.result->'executionPlan'->'plan'->>'plan_id'=%s) "
        "AND d.state NOT IN ('SUCCEEDED','FAILED','CANCELLED','REJECTED') LIMIT 1",
        (
            context.scope.tenant_id,
            context.scope.security_domain,
            context.principal_id,
            previous.resource_id,
            previous.resource_id,
        ),
    ).fetchone()
    require(row is None, "PRIOR_EXECUTION_UNRESOLVED")
    progress = c.execute(
        "SELECT to_regclass('execution_authority.prepared_run_progress') AS name"
    ).fetchone()
    if progress["name"]:
        active = c.execute(
            "SELECT 1 FROM execution_authority.prepared_resource_commands r JOIN "
            "execution_authority.prepared_run_progress p ON p.namespace=r.namespace "
            "AND p.security_domain=r.security_domain "
            "AND p.workflow_run_id=r.result->>'runId' "
            "WHERE r.namespace=%s AND r.security_domain=%s AND r.actor_id=%s "
            "AND (r.result->>'sourcePlanId'=%s OR "
            "r.result->'executionPlan'->'plan'->>'plan_id'=%s) "
            "AND p.record->>'state' IN ('PENDING','RUNNING') LIMIT 1",
            (
                context.scope.tenant_id,
                context.scope.security_domain,
                context.principal_id,
                previous.resource_id,
                previous.resource_id,
            ),
        ).fetchone()
        require(active is None, "PRIOR_EXECUTION_UNRESOLVED")


def project(reader, c, context, binding, plan):
    """Malformed/corrupt receipts deny; they never become a permissive fallback."""
    try:
        return _project(reader, c, context, binding, plan)
    except (KeyError, TypeError, IndexError, AttributeError) as exc:
        raise AuthorityError("OWNED_ASSEMBLY_PROOF_INVALID") from exc


def prepared_binding(owner, c, context, command, preparation):
    """Wait/answer owners reuse the exact source Plan of this prepared command.

    No latest/admission-wide lookup. Legacy scopes keep their original read path.
    """
    try:
        base = owner.work(c, context, preparation.semantics.target.problem)
    except AuthorityError as exc:
        if str(exc) != "OWNED_BUSINESS_POLICY_BINDING_CHANGED":
            raise
        # A successor fact is selected only by the exact approved receipt below.
        # Never fall back to a retained history binding for execution.
        base = None
    if (
        base is not None
        and getattr(base.scope, "trustedAssemblyAdoption", None) != MODE
    ):
        return base
    rows = c.execute(
        "SELECT result FROM execution_authority.prepared_resource_commands "
        "WHERE namespace=%s AND security_domain=%s AND actor_id=%s "
        "AND result->>'preparationDigest'=%s",
        (
            preparation.namespace,
            preparation.security_domain,
            context.principal_id,
            preparation.digest,
        ),
    ).fetchall()
    require(len(rows) == 1, "PREPARATION_RECEIPT_REQUIRED")
    receipt = rows[0]["result"]
    if not receipt.get("ownedBusiness", {}).get("assemblyAdoption"):
        require(base is not None, "SUCCESSOR_RECEIPT_REQUIRED")
        return base
    require(
        receipt["subject"] == context.principal_id == command.principal_id,
        "SUBJECT_CHANGED",
    )
    executed = ConfirmedPlanRevision.model_validate(receipt["executionPlan"]["plan"])
    require(
        (executed.plan_id, executed.version, executed.digest)
        == (preparation.plan_id, preparation.plan_version, preparation.plan_digest),
        "PREPARATION_CHANGED",
    )
    selected = ExactReference(
        resource_id=receipt["sourcePlanId"],
        revision_id=str(receipt["sourcePlanVersion"]),
        digest=receipt["sourcePlanDigest"],
    )
    bound = owner.work(c, context, preparation.semantics.target.problem, plan=selected)
    expected = receipt["ownedBusiness"]["assemblyAdoption"]
    require(bound.assembly_adoption == expected, "BINDING_CHANGED")
    require(
        bound.scope.documentRules == getattr(preparation, "business_semantics", None),
        "ONTOLOGY_CHANGED",
    )
    return bound


def execution_projection(reader, c, context, binding, requested):
    """Inherit only the exact fixed composition of a real approved execution Plan.

    This is read-only provenance, not a new adoption, authorization or dispatch.
    Other Plans and the old pre-adoption Plan retain their original static scope.
    """
    from .cost_execution_revision import (
        CostExecutionRevisionRequest,
        execution_successor,
    )
    from .native_readonly_protocol import NativeExecutionRevisionRequest
    from .owned_business_resource_adapter import (
        OwnedResourceWork,
        evidence,
        readonly_work,
        require_preparation,
        require_ready,
    )
    from .plan_suggestion_domain import PolicyResourcePreparationOrigin
    from .plan_suggestion_postgres import PostgresPlanningRepository
    from .readonly_native_policy import require_prepared_members
    from .workbench_prepared_execution import candidate

    table = c.execute(
        "SELECT to_regclass('execution_authority.prepared_resource_commands') AS name"
    ).fetchone()
    if table["name"] is None:
        return binding
    rows = c.execute(
        "SELECT command_key,result FROM execution_authority.prepared_resource_commands "
        "WHERE namespace=%s AND security_domain=%s AND actor_id=%s "
        "AND result->'executionPlan'->'plan'->>'plan_id'=%s "
        "AND result->'executionPlan'->'plan'->>'version'=%s",
        (
            binding.tenant_id,
            binding.security_domain,
            binding.subject_id,
            requested.resource_id,
            requested.revision_id,
        ),
    ).fetchall()
    if not rows:
        return binding
    require(len(rows) == 1, "EXECUTION_RECEIPT_AMBIGUOUS")
    receipt = rows[0]["result"]
    adoption = receipt.get("ownedBusiness", {}).get("assemblyAdoption")
    if adoption is None:
        return binding
    require(
        receipt["schemaVersion"] == "readonly-continuation.v1"
        and receipt["developmentJourney"] is False
        and receipt["executionStarted"] is True
        and receipt["subject"] == context.principal_id == binding.subject_id,
        "EXECUTION_RECEIPT_CHANGED",
    )
    require(
        binding.history_only
        or datetime.now(UTC)
        < min(
            binding.expires_at,
            datetime.fromisoformat(receipt["authorizationExpiresAt"]),
        ),
        "EXECUTION_RECEIPT_EXPIRED",
    )
    source = ExactReference(
        resource_id=receipt["sourcePlanId"],
        revision_id=str(receipt["sourcePlanVersion"]),
        digest=receipt["sourcePlanDigest"],
    )
    require(
        set(adoption) == {"digest", "plan", "requestKey"}
        and adoption["plan"] == source.model_dump(mode="json")
        and source.resource_id == requested.resource_id
        and int(source.revision_id) + 1 == int(requested.revision_id),
        "EXECUTION_SOURCE_PLAN_CHANGED",
    )
    # Source must be the explicit adoption Plan itself, never an arbitrary
    # inherited execution Plan or recursive latest/admission-wide binding.
    original = _project(reader, c, context, binding, source)
    require(original.assembly_adoption == adoption, "EXECUTION_ASSEMBLY_CHANGED")
    scope = ScopeIdentity(binding.tenant_id, binding.security_domain)
    repo = PostgresPlanningRepository(None, connection=c)
    source_row = repo.read_plan(c, scope, source.resource_id, int(source.revision_id))
    source_plan = ConfirmedPlanRevision.model_validate(source_row["plan"])
    require(source_plan.digest == source.digest, "EXECUTION_SOURCE_PLAN_CHANGED")
    actual = repo.read_plan(c, scope, requested.resource_id, int(requested.revision_id))
    executed = ConfirmedPlanRevision.model_validate(actual["plan"])
    require(
        plan_reference(executed) == requested
        and actual == receipt["executionPlan"]
        and actual["approval"]["decision"] == "APPROVE"
        and actual["approval"]["reason_category"]
        == "POLICY_READONLY_EXECUTION_APPROVAL"
        and actual["approval"]["actor_id"] == receipt["policyIssuer"]
        and executed.predecessor_digest == source.digest,
        "EXECUTION_PLAN_CHANGED",
    )
    basis = actual["approval"]["authority_basis"]
    prefix = (
        "POLICY_READONLY_EXECUTION:" + receipt["executionAuthorizationDigest"] + ":"
    )
    require(
        basis.startswith(prefix)
        and basis[len(prefix) :] in receipt["policyDecisionIds"],
        "EXECUTION_APPROVAL_CHANGED",
    )
    preparation = candidate(c, scope, receipt["preparationDigest"])
    require(
        preparation.digest == receipt["preparationDigest"]
        and preparation.run_id == receipt["runId"]
        and (preparation.plan_id, preparation.plan_version, preparation.plan_digest)
        == (executed.plan_id, executed.version, executed.digest)
        and preparation.semantics == executed.semantics
        and preparation.approval_id == actual["approval"]["approval_decision_id"],
        "EXECUTION_PREPARATION_CHANGED",
    )
    # Validate every member and semantic binding against the original exact
    # adopted assembly, with the unchanged original prepared Native checks.
    work = OwnedResourceWork(
        namespace=original.tenant_id,
        securityDomain=original.security_domain,
        subject=original.subject_id,
        problem=original.problem,
        sourceContentDigests=(original.scope.sourceContentDigest,),
        expiresAt=original.expires_at,
        admissionId=original.admission_id,
        admissionRecordDigest=original.record_digest,
        admissionPolicyDigest=original.policy_digest,
        businessScope=original.scope,
        assemblyAdoption=original.assembly_adoption,
        historyRead=original.history_only,
    )
    require(
        receipt["ownedBusiness"] == evidence(work)
        and receipt["case"] == original.scope.case
        and receipt["nativeAgentName"] == original.scope.nativeAgentName
        and receipt["sourceContentDigest"] == original.scope.sourceContentDigest,
        "EXECUTION_ASSEMBLY_CHANGED",
    )
    if not original.history_only:
        require_preparation(work, preparation)
    else:
        from .owned_business_resource_adapter import require_reference

        require(
            preparation.source_snapshot == original.scope.source
            and getattr(preparation, "business_semantics", None)
            == original.scope.documentRules,
            "EXECUTION_ASSEMBLY_CHANGED",
        )
        for participant in preparation.participants:
            require_reference(work, "employee", participant.definition)
            require_reference(work, "runtime", participant.profile)
            for resource in (participant.skill, *participant.resources):
                require_reference(work, resource.kind.lower(), resource.reference)
    require_prepared_members(readonly_work(work), preparation)
    mapping = receipt["instanceBinding"]
    require(
        mapping["mappingDigest"] == preparation.mapping_digest
        and all(
            preparation.model_dump(mode="json").get(key) == value
            for key, value in mapping["mapping"].items()
        ),
        "EXECUTION_MAPPING_CHANGED",
    )
    ready = c.execute(
        "SELECT record FROM execution_authority.resource_automation WHERE namespace=%s "
        "AND security_domain=%s AND subject_id=%s AND plan_id=%s AND plan_version=%s "
        "AND request_key=%s",
        (
            binding.tenant_id,
            binding.security_domain,
            binding.subject_id,
            source.resource_id,
            int(source.revision_id),
            receipt["resourcePreparationKey"],
        ),
    ).fetchone()
    require(
        ready is not None and ready["record"]["state"] == "READY",
        "EXECUTION_READY_REQUIRED",
    )
    require_ready(work, ready["record"])
    source_proposal = repo.proposal(
        c, scope, source_plan.source_proposal_id, source_plan.source_proposal_revision
    )
    request_type = (
        NativeExecutionRevisionRequest
        if original.scope.case == "native_readonly"
        else CostExecutionRevisionRequest
    )
    request = request_type(
        case=original.scope.case,
        plan_version=source_plan.version,
        plan_digest=source_plan.digest,
        source_snapshot=original.scope.source,
        mapping_digest=preparation.mapping_digest,
        selections={
            r.requirement_id: r.selected
            for r in source_plan.semantics.requirements
            if r.selected is not None
        },
        **(
            {"adapter": original.scope.adapter}
            if original.scope.case == "native_readonly"
            else {}
        ),
    )
    expected, _ = execution_successor(source_plan, source_proposal, request)
    proposal = repo.proposal(
        c, scope, executed.source_proposal_id, executed.source_proposal_revision
    )
    require(
        executed.semantics == expected.semantics == proposal.semantics
        and proposal.digest == executed.source_proposal_digest
        and proposal.revision == expected.revision
        and proposal.predecessor_digest == source_proposal.digest
        and proposal.invocation_id is None
        and isinstance(proposal.origin, PolicyResourcePreparationOrigin)
        and proposal.origin.predecessor_plan == source
        and proposal.origin.source_snapshot == original.scope.source
        and proposal.origin.root == original.problem
        and proposal.origin.prepared_by == receipt["policyIssuer"],
        "EXECUTION_SEMANTICS_CHANGED",
    )
    return replace(
        original,
        assembly_adoption={
            **adoption,
            "plan": requested.model_dump(mode="json"),
            "sourcePlan": source.model_dump(mode="json"),
            "executionReceiptDigest": canonical_digest(receipt),
        },
    )


def require_selection_rebinding(work, predecessor, prospective):
    """Only the explicit selection owner may derive this exact local candidate.

    Never treat its changed digest as a persisted/admitted Plan. The new Plan
    still requires its original owner confirmation and immutable adoption receipt.
    """
    require(
        getattr(work.businessScope, "trustedAssemblyAdoption", None) == MODE
        and not work.historyRead,
        "SELECTION_NOT_AUTHORIZED",
    )
    require(len(work.businessScope.employees) == 1, "MEMBER_SELECTION_AMBIGUOUS")
    semantics = selection_semantics(
        predecessor.semantics,
        work.businessScope,
        ontology_reference=work.selectedOntologySuccessor,
    )
    raw = semantics.model_dump(mode="json")
    for requirement in raw["requirements"]:
        if requirement["kind"] == "EMPLOYEE":
            requirement["selected"] = work.businessScope.employees[0].model_dump(
                mode="json"
            )
    expected = predecessor.model_copy(
        update={
            "semantics": type(predecessor.semantics).model_validate(raw),
        }
    )
    require(prospective == expected, "SELECTION_PLAN_CHANGED")
