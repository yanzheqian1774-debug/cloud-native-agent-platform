"""Strict retained identity checks. Read facts do not authorize any command."""

from zoneinfo import ZoneInfo

from .digital_employee_definition import digest
from .fixed_work_bound_policy import BoundServicePlanningPolicy, compile_windows
from .fixed_work_service_admission import event_key
from .plan_suggestion_domain import ExactReference, ProblemTarget
from .plan_suggestion_invocation import PlanningRequest
from .workbench_owner_authorization import WorkbenchOwnerError


def require(ok):
    if not ok:
        raise WorkbenchOwnerError("FIXED_CHAT_FACT_BINDING_INVALID", 409)


def source_fact(row, scope, subject, conversation, work):
    require(row is not None)
    value = row["record"]
    require(
        digest(value) == row["digest"]
        and (row["namespace"], row["security_domain"]) == scope
        and row["subject_id"] == value["subjectId"] == subject
        and row["conversation_id"] == value["conversationId"] == conversation
        and row["command_id"] == value["commandId"]
        and row["work_id"] == work.resource_id
        and row["revision_id"] == work.revision_id
        and value["work"] == work.model_dump(mode="json")
        and value["executionEnabled"] is False
    )
    return value


def binding_facts(bound, handoff, saved, permit):
    scope = permit.tenantId, permit.securityDomain
    work = permit.work
    b = source_fact(bound, scope, permit.subjectId, permit.conversationId, work)
    h = source_fact(handoff, scope, permit.subjectId, permit.conversationId, work)
    value = saved["record"]
    require(
        b["schemaVersion"] == "fixed-work-confirmed-source.v1"
        and h["schemaVersion"] == "fixed-work-conversation.v1"
        and bound["digest"] == permit.bindingDigest
        and b["handoffDigest"] == handoff["digest"]
        and saved["digest"] == work.digest == digest(value)
        and value["workId"] == work.resource_id
        and value["revisionId"] == work.revision_id
        and b["team"] == h["team"] == value["team"]
        and b["instructionDigest"]
        == h["instructionDigest"]
        == digest(value["instruction"])
    )
    ProblemTarget.model_validate(b["target"])
    ExactReference.model_validate(b["inputSource"]["source"])
    return b


def event_facts(row, admission, binding, saved, prepared, permit):
    """Validate saved service policy, columns and original prepared source chain.

    Intentionally does not require the historical service credential or Human
    model lease to remain live: this function validates retained facts only.
    Current viewer/READ policy authorization belongs to the enclosing owner.
    """
    require(admission is not None)
    policy = BoundServicePlanningPolicy.model_validate(admission["policy"])
    record, context = admission["record"], admission["context"]
    scope = permit.tenantId, permit.securityDomain
    work = permit.work.model_dump(mode="json")
    require(
        (row["namespace"], row["security_domain"]) == scope
        and (admission["namespace"], admission["security_domain"]) == scope
        and (policy.tenantId, policy.securityDomain) == scope
        and row["actor_id"]
        == admission["subject_id"]
        == policy.subjectId
        == context["principal"]
        and admission["credential_id"] == policy.credentialId == context["credential"]
        and row["work_id"] == admission["work_id"] == permit.work.resource_id
        and row["revision_id"] == admission["revision_id"] == permit.work.revision_id
        and row["work_digest"] == permit.work.digest
        and policy.work.model_dump(mode="json") == work
        and row["event_id"] == admission["event_id"]
        and row["policy_digest"] == admission["policy_digest"] == policy.digest
        and admission["expires_at"] == policy.expiresAt
        and admission["record_digest"] == digest(record)
        and record["target"]["invocation_id"] == admission["invocation_id"]
        and (record["target"]["namespace"], record["target"]["security_domain"])
        == scope
        and record["target"]["problem"]
        == policy.target.model_dump(mode="json")
        == binding["target"]
        and record["target"]["resource_snapshot"]
        == policy.resourceSnapshot.model_dump(mode="json")
        and policy.sourceBindingDigest == permit.bindingDigest
        and (prepared.namespace, prepared.security_domain) == scope
        and prepared.digest == row["preparation_digest"]
        and prepared.run_id == row["workflow_run_id"]
        and prepared.semantics.target.problem == policy.target.problem
        and prepared.source_snapshot == policy.resourceSnapshot
    )
    windows = compile_windows(
        policy.work, saved["record"]["trigger"], policy.scheduleWindow
    )
    require(
        windows == policy.eventWindows and set(windows) == set(policy.allowedEventIds)
    )
    require(row["event_id"] in windows)
    source = ExactReference.model_validate(binding["inputSource"]["source"])
    actual = {
        (r.reference.resource_id, r.reference.revision_id, r.reference.digest)
        for participant in prepared.participants
        for r in participant.resources
        if r.kind == "KNOWLEDGE"
    }
    require(actual == {(source.resource_id, source.revision_id, source.digest)})
    scheduled = windows[row["event_id"]][0]
    zone = saved["record"]["trigger"]["timezone"]
    return {
        "eventId": row["event_id"],
        "receiptDigest": digest(
            {k: v.isoformat() if hasattr(v, "isoformat") else v for k, v in row.items()}
        ),
        "recordedAt": row["recorded_at"].isoformat(),
        "scheduledAt": scheduled.isoformat(),
        "plannedLocalDate": scheduled.astimezone(ZoneInfo(zone)).date().isoformat(),
        "timezone": zone,
        "preparationDigest": prepared.digest,
        "runId": row["workflow_run_id"],
        "sourceSnapshot": prepared.source_snapshot.model_dump(mode="json"),
    }


def planning_facts(admission, binding, saved, permit):
    """A committed planning admission proves discovery, not a running provider."""
    policy = BoundServicePlanningPolicy.model_validate(admission["policy"])
    record, context = admission["record"], admission["context"]
    scope = permit.tenantId, permit.securityDomain
    require(
        (admission["namespace"], admission["security_domain"]) == scope
        and (policy.tenantId, policy.securityDomain) == scope
        and admission["subject_id"] == policy.subjectId == context["principal"]
        and admission["credential_id"] == policy.credentialId == context["credential"]
        and admission["work_id"] == permit.work.resource_id
        and admission["revision_id"] == permit.work.revision_id
        and policy.work == permit.work
        and admission["policy_digest"] == policy.digest
        and admission["expires_at"] == policy.expiresAt
        and admission["record_digest"] == digest(record)
        and record["target"]["invocation_id"] == admission["invocation_id"]
        and (record["target"]["namespace"], record["target"]["security_domain"])
        == scope
        and record["target"]["problem"]
        == policy.target.model_dump(mode="json")
        == binding["target"]
        and record["target"]["resource_snapshot"]
        == policy.resourceSnapshot.model_dump(mode="json")
        and policy.sourceBindingDigest == permit.bindingDigest
        and record["profile"]["profile_revision_id"] == policy.profileRevisionId
        and record["profile"]["profile_digest"] == policy.profileDigest
        and record["profile"]["model"] == policy.model.model_dump(mode="json")
    )
    request = PlanningRequest(
        target=policy.target,
        policy=policy.planningPolicy,
        idempotency_key=event_key(policy.work, admission["event_id"]),
    )
    require(admission["request_digest"] == digest(request.model_dump(mode="json")))
    require(record["target_digest"] == digest(record["target"]))
    windows = compile_windows(
        policy.work, saved["record"]["trigger"], policy.scheduleWindow
    )
    require(
        windows == policy.eventWindows and set(windows) == set(policy.allowedEventIds)
    )
    require(admission["event_id"] in windows)
    scheduled = windows[admission["event_id"]][0]
    zone = saved["record"]["trigger"]["timezone"]
    return dict(
        eventId=admission["event_id"],
        discoveryDigest=admission["record_digest"],
        phase="PLANNING",
        receiptDigest=None,
        recordedAt=record.get("submitted_at"),
        scheduledAt=scheduled.isoformat(),
        plannedLocalDate=scheduled.astimezone(ZoneInfo(zone)).date().isoformat(),
        timezone=zone,
        preparationDigest=None,
        runId=None,
        readTargetDigest=None,
        sourceSnapshot=None,
        readState="UNVERIFIED",
        execution=None,
    )
