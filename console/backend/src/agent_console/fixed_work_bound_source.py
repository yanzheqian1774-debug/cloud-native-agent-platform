"""Same-transaction source proof checks; never borrow the Human's permissions."""

from .authority_contracts import ExactGrant
from .execution_domain import ScopeIdentity
from .fixed_work_bound_policy import BoundServicePlanningPolicy, compile_windows
from .fixed_work_service_admission import require
from .fixed_work_sources_postgres import read
from .plan_suggestion_domain import ExactReference
from .planning_candidates import read_published
from .resource_automation_policy import source_digest
from .workbench_prepared_resources import reference


def require_bound_source(c, context, policy, saved, authorization, kwargs):
    require(isinstance(policy, BoundServicePlanningPolicy))
    scope = policy.tenantId, policy.securityDomain
    bound = read(c, scope, "bindings", policy.work.resource_id, policy.work.revision_id)
    handoff = read(
        c, scope, "handoffs", policy.work.resource_id, policy.work.revision_id
    )
    require(bound and handoff, "FIXED_WORK_BOUND_SOURCE_REQUIRED")
    record = bound["record"]
    require(
        bound["digest"] == policy.sourceBindingDigest
        and record["work"] == policy.work.model_dump(mode="json")
        and record["target"] == policy.target.model_dump(mode="json")
        and record["team"] == saved["record"]["team"]
        and record["handoffDigest"] == handoff["digest"]
        and record["subjectId"] == handoff["record"]["subjectId"]
        and record["conversationId"] == handoff["record"]["conversationId"]
        and record["instructionDigest"] == handoff["record"]["instructionDigest"],
        "FIXED_WORK_BOUND_SOURCE_CHANGED",
    )
    head = c.execute(
        "SELECT head_revision_id FROM fixed_work_authoring.heads WHERE namespace=%s "
        "AND security_domain=%s AND work_id=%s FOR SHARE",
        (*scope, policy.work.resource_id),
    ).fetchone()
    require(
        head and head["head_revision_id"] == policy.work.revision_id,
        "FIXED_WORK_SERVICE_WORK_CHANGED",
    )
    expected = compile_windows(
        policy.work, saved["record"]["trigger"], policy.scheduleWindow
    )
    require(
        set(expected) == set(policy.allowedEventIds)
        and expected == policy.eventWindows,
        "FIXED_WORK_BOUND_SCHEDULE_CHANGED",
    )
    selected = record["inputSource"]
    source = ExactReference.model_validate(selected["source"])
    grants = (
        ExactGrant(
            "KNOWLEDGE",
            "READ_RESOURCE",
            reference("knowledge", source.resource_id, source.revision_id),
        ),
    )
    authorization.require_current_context(context, grants, **kwargs)
    require(
        authorization.has_current_grants(
            context, grants, configure_transaction=False, **kwargs
        )
        == (True,),
        "FIXED_WORK_BOUND_SOURCE_READ_REQUIRED",
    )
    content, _ = read_published(c, ScopeIdentity(*scope), "KNOWLEDGE", source)
    require(
        source_digest(content) == selected["sourceContentDigest"],
        "FIXED_WORK_BOUND_SOURCE_CHANGED",
    )
    return bound["digest"]


def require_bound_preparation(c, policy, receipt):
    """Before commit, bind the actual prepared input to the confirmed source."""
    from .execution_preparation_postgres import PreparedExecutionStore

    require(isinstance(policy, BoundServicePlanningPolicy))
    scope = policy.tenantId, policy.securityDomain
    bound = read(c, scope, "bindings", policy.work.resource_id, policy.work.revision_id)
    require(
        bound and bound["digest"] == policy.sourceBindingDigest,
        "FIXED_WORK_BOUND_SOURCE_CHANGED",
    )
    source = ExactReference.model_validate(bound["record"]["inputSource"]["source"])
    prepared, _ = PreparedExecutionStore(c).read(*scope, receipt["runId"])
    actual = {
        (r.reference.resource_id, r.reference.revision_id, r.reference.digest)
        for participant in prepared.participants
        for r in participant.resources
        if r.kind == "KNOWLEDGE"
    }
    require(
        prepared.digest == receipt["preparationDigest"]
        and prepared.source_snapshot == policy.resourceSnapshot
        and actual == {(source.resource_id, source.revision_id, source.digest)},
        "FIXED_WORK_BOUND_EXECUTION_SOURCE_CHANGED",
    )
