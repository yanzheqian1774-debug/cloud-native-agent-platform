# ruff: noqa: E501, RUF001 -- Exact approved Chinese lineage text and parameterized SQL.
"""D10 formal old/new-source review; existing owners retain all authority."""

import json
from copy import deepcopy
from datetime import UTC, datetime

from psycopg.types.json import Jsonb
from pydantic import Field

from .cost_execution_revision import (
    DELIVERY_SYNTHETIC_ONLY,
    EXECUTION_ONLY,
    PLANNING_ONLY,
    READ_ONLY_PLANNING,
    SALES_SYNTHETIC_ONLY,
    SYNTHETIC_ONLY,
    TABULAR_SYNTHETIC_ONLY,
)
from .plan_suggestion_domain import (
    ConfirmedPlanRevision,
    ExactReference,
    FlexiblePlanSemantics,
    Identity,
    Immutable,
    PlanningConflict,
    PlanningError,
    PolicySourceChangeOrigin,
    ProblemTarget,
    ProposalRevision,
    SourceChangeOrigin,
)
from .planning_candidates import read_published, require_read
from .planning_source_reference import approved_source, is_source_boundary
from .resource_use_domain import canonical_digest, stable_id


class SourceChangeRequest(Immutable):
    plan_version: int = Field(ge=1)
    plan_digest: str = Field(pattern="^[a-f0-9]{64}$")
    expected_proposal_revision: int = Field(ge=1)
    old_source: ExactReference
    new_source: ExactReference
    reason: str = Field(min_length=1, max_length=1000)
    idempotency_key: Identity
    new_target: ProblemTarget | None = None
    criterion_revision_map: dict[str, str] = Field(default_factory=dict, max_length=128)


def source_content(c, scope, authority, principal, ref, *, historical=False):
    require_read(authority, principal, "KNOWLEDGE", ref)
    content, name = read_published(c, scope, "KNOWLEDGE", ref, historical=historical)
    documents = content.get("documents", [])
    if len(documents) != 1 or len(documents[0].get("chunks", [])) != 1:
        raise PlanningError("SOURCE_CHANGE_SINGLE_SNAPSHOT_REQUIRED")
    raw = documents[0]["chunks"][0]["content"]
    import hashlib

    if hashlib.sha256(raw.encode()).hexdigest() != documents[0]["contentDigest"]:
        raise PlanningError("SOURCE_CHANGE_DOCUMENT_CORRUPT")
    try:
        source = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise PlanningError("SOURCE_CHANGE_SCHEMA_UNSUPPORTED") from exc
    if not isinstance(source, dict) or source.get("synthetic") is not True:
        raise PlanningError("SOURCE_CHANGE_SYNTHETIC_SNAPSHOT_REQUIRED")
    return source, name, documents[0]["contentDigest"]


def validate_data(source):
    from .skill_executor import SkillExecutorFailure

    try:
        if source.get("schemaVersion") == "sales-diagnostic-source.v1":
            from .sales_diagnostic_skill import validate_source

            validate_source(source)
        elif source.get("schemaVersion") == "synthetic-delivery-source.v1":
            from .synthetic_delivery_skill import analyze

            analyze(source)
        elif source.get("schemaVersion") == "document-review-source.v1":
            from .native_document_tools import validate_source

            validate_source(source)
        elif source.get("schemaVersion") == "tabular-diagnostic-source.v1":
            from .tabular_diagnostic_skill import validate_source

            validate_source(source)
        else:
            raise PlanningError("SOURCE_CHANGE_SCHEMA_UNSUPPORTED")
    except SkillExecutorFailure as exc:
        raise PlanningError("SOURCE_CHANGE_SOURCE_INVALID") from exc


def criterion_impacts(app, principal, c, old, target, source, mapping):
    app.validate_target(principal, target, c)
    changed_target = target != old.target
    if changed_target and target.problem != old.target.problem:
        raise PlanningConflict("SOURCE_CHANGE_PROBLEM_CHANGED")
    if mapping:
        if set(mapping) != set(old.target.criterion_revision_ids) or set(
            mapping.values()
        ) != set(target.criterion_revision_ids):
            raise PlanningConflict("SOURCE_CHANGE_CRITERION_MAPPING_INVALID")
        for left, right in mapping.items():
            a = app.problems.get_criterion_revision(
                app.scope(principal), left, authorized=True, connection=c
            )
            b = app.problems.get_criterion_revision(
                app.scope(principal), right, authorized=True, connection=c
            )
            if a.success_criterion_id != b.success_criterion_id:
                raise PlanningConflict("SOURCE_CHANGE_CRITERION_IDENTITY_CHANGED")
            ca, cb = deepcopy(a.digest_contract()), deepcopy(b.digest_contract())
            for key in (
                "revision_id",
                "revision",
                "predecessor_revision_id",
                "created_by",
            ):
                ca.pop(key, None)
                cb.pop(key, None)
            ca["applicability"].pop("sourceContentDigest", None)
            cb["applicability"].pop("sourceContentDigest", None)
            if ca != cb:
                raise PlanningConflict("SOURCE_CHANGE_CRITERION_MEANING_CHANGED")
    elif changed_target:
        raise PlanningConflict("SOURCE_CHANGE_CRITERION_MAPPING_REQUIRED")
    digest = canonical_digest(source)
    impacts = []
    for identity in target.criterion_revision_ids:
        criterion = app.problems.get_criterion_revision(
            app.scope(principal), identity, authorized=True, connection=c
        )
        pinned = criterion.applicability.get("sourceContentDigest")
        if pinned and pinned != digest:
            impacts.append(
                {
                    "criterionRevisionId": identity,
                    "reason": "CRITERION_SOURCE_CONTENT_MISMATCH",
                }
            )
    return impacts


def preview(app, principal, c, identity, request):
    scope = app.scope(principal)
    result = app.repository.read_plan(c, scope, identity, request.plan_version)
    plan = ConfirmedPlanRevision.model_validate(result["plan"])
    if plan.digest != request.plan_digest or not isinstance(
        plan.semantics, FlexiblePlanSemantics
    ):
        raise PlanningConflict("SOURCE_CHANGE_PLAN_MISMATCH")
    head = c.execute(
        "SELECT max(revision) revision FROM workflow_planning.proposals WHERE namespace=%s AND security_domain=%s AND proposal_id=%s",
        (scope.namespace, scope.security_domain, identity),
    ).fetchone()["revision"]
    current = c.execute(
        "SELECT max(version) version FROM workflow_planning.plans WHERE namespace=%s AND security_domain=%s AND plan_id=%s",
        (scope.namespace, scope.security_domain, identity),
    ).fetchone()["version"]
    if current != request.plan_version or head != request.expected_proposal_revision:
        raise PlanningConflict("SOURCE_CHANGE_HEAD_CHANGED")
    if (
        approved_source(plan.semantics) != request.old_source
        or request.old_source == request.new_source
    ):
        raise PlanningConflict("SOURCE_CHANGE_OLD_OR_NEW_SOURCE_MISMATCH")
    before, old_name, before_bytes = source_content(
        c, scope, app.authority, principal, request.old_source, historical=True
    )
    after, new_name, after_bytes = source_content(
        c, scope, app.authority, principal, request.new_source
    )
    if before.get("schemaVersion") != after.get("schemaVersion"):
        raise PlanningConflict("SOURCE_CHANGE_SCHEMA_INCOMPATIBLE")
    if after.get("schemaVersion") == "document-review-source.v1":
        raise PlanningConflict("DOCUMENT_SOURCE_SUCCESSOR_NOT_SUPPORTED")
    validate_data(before)
    validate_data(after)
    target = request.new_target or plan.semantics.target
    impacts = criterion_impacts(
        app, principal, c, plan.semantics, target, after, request.criterion_revision_map
    )
    # Schema compatibility does not change metric/period/date business meaning.
    stable = (
        ("periods", "mapping")
        if after["schemaVersion"] == "tabular-diagnostic-source.v1"
        else ("periods", "metric")
        if after["schemaVersion"] == "sales-diagnostic-source.v1"
        else ("assessmentDate", "timezone")
    )
    if any(before.get(k) != after.get(k) for k in stable):
        raise PlanningConflict("SOURCE_CHANGE_BUSINESS_SCOPE_CHANGED")
    return plan, {
        "state": "BLOCKED_CRITERIA" if impacts else "READY_FOR_SEPARATE_CONFIRMATION",
        "before": {
            "name": old_name,
            "reference": request.old_source.model_dump(mode="json"),
            "contentDigest": canonical_digest(before),
            "documentContentDigest": before_bytes,
        },
        "after": {
            "name": new_name,
            "reference": request.new_source.model_dump(mode="json"),
            "contentDigest": canonical_digest(after),
            "documentContentDigest": after_bytes,
        },
        "schema": after["schemaVersion"],
        "contentChanged": before != after,
        "criterionImpacts": impacts,
        "executionReady": False,
        "automaticModelCalls": 0,
        "automaticRuns": 0,
        "requiredNextSteps": [
            "CONFIRM_SUCCESSOR",
            "FRESH_SOURCE_BOUND_MAPPING",
            "INDEPENDENT_EXECUTION_ADMISSION",
        ],
    }


def prepare(app, principal, identity, request, *, policy_basis=None):
    if (
        policy_basis is None and not principal.principal_id.startswith("human:")
    ) or not request.reason.strip():
        raise PlanningError("SOURCE_CHANGE_HUMAN_REASON_REQUIRED")
    app.require(principal, "READ", identity)
    app.require(principal, "PREPARE", identity)
    actor = policy_basis.issuer if policy_basis is not None else principal.principal_id
    if policy_basis is not None:
        policy_basis.record(actor)
        if policy_basis.subject != principal.principal_id:
            raise PlanningError("SOURCE_CHANGE_POLICY_SUBJECT_MISMATCH")
    scope = app.scope(principal)
    payload = {"proposal_id": identity, **request.model_dump(mode="json")}
    payload_digest = (
        canonical_digest([payload, policy_basis.record(actor)])
        if policy_basis
        else canonical_digest(payload)
    )
    with app.repository.transaction(scope, identity, authorized=True) as cursor:
        c = cursor.connection
        c.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (
                canonical_digest(
                    [
                        "source-change",
                        scope.namespace,
                        scope.security_domain,
                        actor,
                        request.idempotency_key,
                    ]
                ),
            ),
        )
        prior = c.execute(
            "SELECT record,payload_digest FROM workflow_planning.source_changes WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND request_key=%s",
            (
                scope.namespace,
                scope.security_domain,
                actor,
                request.idempotency_key,
            ),
        ).fetchone()
        if prior:
            if prior["payload_digest"] != payload_digest:
                raise PlanningConflict("SOURCE_CHANGE_IDEMPOTENCY_CONFLICT")
            # Replay does not waive current access to either source.
            source_content(
                c, scope, app.authority, principal, request.old_source, historical=True
            )
            source_content(c, scope, app.authority, principal, request.new_source)
            return read(app, principal, c, identity, prior["record"]["requestId"])
        plan, evidence = preview(app, principal, c, identity, request)
        if policy_basis is not None and (
            evidence["contentChanged"]
            or request.new_target
            or request.criterion_revision_map
        ):
            raise PlanningConflict("POLICY_SOURCE_CHANGE_BUSINESS_DECISION_REQUIRED")
        request_id = stable_id(
            "planning-source-change",
            scope.namespace,
            scope.security_domain,
            actor,
            payload_digest,
        )
        successor = None
        if evidence["state"] == "READY_FOR_SEPARATE_CONFIRMATION":
            head = app.repository.proposal(
                cursor, scope, identity, request.expected_proposal_revision
            )
            semantics = plan.semantics.model_dump(mode="json")
            semantics["business_rules"] = [
                PLANNING_ONLY if text == EXECUTION_ONLY else text
                for text in semantics["business_rules"]
            ]
            if PLANNING_ONLY not in semantics["business_rules"]:
                semantics["business_rules"].append(PLANNING_ONLY)
            semantics["boundaries"] = [
                text
                for text in semantics["boundaries"]
                if not is_source_boundary(text)
                and not text.startswith("执行准备映射SHA256：")
                and text
                not in {
                    DELIVERY_SYNTHETIC_ONLY,
                    SALES_SYNTHETIC_ONLY,
                    SYNTHETIC_ONLY,
                    TABULAR_SYNTHETIC_ONLY,
                    READ_ONLY_PLANNING,
                }
            ]
            semantics["boundaries"] += [
                READ_ONLY_PLANNING,
                f"隔离合成来源：{request.new_source.resource_id}；修订：{request.new_source.revision_id}；SHA256：{request.new_source.digest}",
            ]
            for r in semantics["requirements"]:
                if r["kind"] == "KNOWLEDGE" and r.get(
                    "selected"
                ) == request.old_source.model_dump(mode="json"):
                    r["selected"] = request.new_source.model_dump(mode="json")
            if request.new_target:
                semantics["target"] = request.new_target.model_dump(mode="json")
                for task in semantics["tasks"]:
                    task["criterion_revision_ids"] = [
                        request.criterion_revision_map[i]
                        for i in task["criterion_revision_ids"]
                    ]
            successor = ProposalRevision(
                proposal_id=identity,
                revision=head.revision + 1,
                predecessor_digest=head.digest,
                invocation_id=None,
                origin=(
                    PolicySourceChangeOrigin if policy_basis else SourceChangeOrigin
                )(
                    namespace=scope.namespace,
                    security_domain=scope.security_domain,
                    root=plan.semantics.target.problem,
                    source_snapshot=request.new_source,
                    request_id=request_id,
                    prepared_by=actor,
                    **(
                        {"policy_basis": policy_basis.record(actor)}
                        if policy_basis
                        else {}
                    ),
                ),
                semantics=FlexiblePlanSemantics.model_validate(semantics),
            )
            app.repository.add_proposal(cursor, scope, successor)
        record = {
            "requestId": request_id,
            "actor": actor,
            "createdAt": datetime.now(UTC).isoformat(),
            "request": payload,
            "evidence": evidence,
            "proposal": successor.model_dump(mode="json") if successor else None,
            "digest": successor.digest if successor else None,
            "previousPlan": {
                "planId": plan.plan_id,
                "version": plan.version,
                "digest": plan.digest,
            },
            "confirmationRequired": bool(successor) and policy_basis is None,
            **(
                {
                    "subjectActor": principal.principal_id,
                    "policyBasis": policy_basis.record(actor),
                    "confirmationMode": "POLICY_OWNER_TRANSACTION",
                }
                if policy_basis
                else {}
            ),
            "executionStarted": False,
        }
        c.execute(
            "INSERT INTO workflow_planning.source_changes VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                scope.namespace,
                scope.security_domain,
                request_id,
                actor,
                request.idempotency_key,
                payload_digest,
                Jsonb(record),
                identity,
                successor.revision if successor else None,
            ),
        )
        return record


def read(app, principal, c, identity, request_id, *, by_key=False):
    app.require(principal, "READ", identity)
    clause = (
        "(actor_id=%s OR record->>'subjectActor'=%s) AND request_key=%s"
        if by_key
        else "request_id=%s"
    )
    row = c.execute(
        "SELECT record FROM workflow_planning.source_changes WHERE namespace=%s AND security_domain=%s AND proposal_id=%s AND "
        + clause,
        (
            principal.tenant_id,
            principal.security_domain,
            identity,
            *(
                [principal.principal_id, principal.principal_id, request_id]
                if by_key
                else [request_id]
            ),
        ),
    ).fetchone()
    if not row:
        raise PlanningError("SOURCE_CHANGE_NOT_FOUND")
    value = row["record"]
    spec = SourceChangeRequest.model_validate(
        {k: v for k, v in value["request"].items() if k != "proposal_id"}
    )
    base = app.repository.read_plan(
        c, app.scope(principal), identity, spec.plan_version
    )
    plan = ConfirmedPlanRevision.model_validate(base["plan"])
    app.validate_target(
        principal, spec.new_target or plan.semantics.target, c, current=False
    )
    source_content(
        c,
        app.scope(principal),
        app.authority,
        principal,
        spec.old_source,
        historical=True,
    )
    source_content(c, app.scope(principal), app.authority, principal, spec.new_source)
    return value


def validate_confirmation(app, principal, c, proposal):
    if not isinstance(proposal.origin, SourceChangeOrigin):
        return
    value = read(app, principal, c, proposal.proposal_id, proposal.origin.request_id)
    # A later execution successor retains provenance but has its own mapping /
    # boundary checks. Only the exact original source-change revision is bound.
    if value["proposal"]["revision"] != proposal.revision:
        if approved_source(proposal.semantics) != proposal.origin.source_snapshot:
            raise PlanningConflict("SOURCE_CHANGE_PROVENANCE_MISMATCH")
        return
    if (
        value["digest"] != proposal.digest
        or value["evidence"]["state"] != "READY_FOR_SEPARATE_CONFIRMATION"
    ):
        raise PlanningConflict("SOURCE_CHANGE_PROVENANCE_MISMATCH")
    confirmed = c.execute(
        "SELECT 1 FROM workflow_planning.plans WHERE namespace=%s AND security_domain=%s AND proposal_id=%s AND proposal_revision=%s",
        (
            principal.tenant_id,
            principal.security_domain,
            proposal.proposal_id,
            proposal.revision,
        ),
    ).fetchone()
    if confirmed:
        return
    spec = SourceChangeRequest.model_validate(
        {k: v for k, v in value["request"].items() if k != "proposal_id"}
    )
    _, evidence = preview(
        app,
        principal,
        c,
        proposal.proposal_id,
        spec.model_copy(update={"expected_proposal_revision": proposal.revision}),
    )
    if evidence != value["evidence"]:
        raise PlanningConflict("SOURCE_CHANGE_RECHECK_CHANGED")


def current_target(app, principal, c, identity, version):
    app.require(principal, "READ", identity)
    old = ConfirmedPlanRevision.model_validate(
        app.repository.read_plan(c, app.scope(principal), identity, version)["plan"]
    )
    app.validate_target(principal, old.semantics.target, c, current=False)
    value = app.current_input(principal, old.semantics.target.problem.resource_id, c)
    current = {item["success_criterion_id"]: item for item in value["criteria"]}
    mapping = {}
    for ref in old.semantics.target.criterion_revision_ids:
        before = app.problems.get_criterion_revision(
            app.scope(principal), ref, authorized=True, connection=c
        )
        after = current.get(before.success_criterion_id)
        if not after:
            raise PlanningConflict("SOURCE_CHANGE_CRITERION_IDENTITY_CHANGED")
        mapping[ref] = after["revision_id"]
    return {
        "target": value["target"],
        "criterionRevisionMap": mapping,
        "criteria": [
            {
                "revision": r["revision"],
                "check": r["applicability"].get("check"),
                "revisionId": r["revision_id"],
            }
            for r in value["criteria"]
        ],
    }
