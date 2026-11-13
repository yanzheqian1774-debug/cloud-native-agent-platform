"""Renew retained-response READ access; no execution or GET writes."""

from datetime import timedelta
from uuid import uuid4

from .authority_contracts import AuthorityError, ExactGrant, GrantDecision, GrantId
from .context_call_admission import lock, request_row
from .grant_administration_application import GrantRequestCommand
from .read_access_recovery import current
from .resource_automation import bound_grants
from .task_delegation import digest
from .test_resource_read_access import was_denied


def source_grant(c, context, source, *, policy=None, conversation=None):
    """Only canonical original-owner invocation records can establish a target."""
    if source.get("kind") != "DRAFT":
        return None
    row = c.execute(
        "SELECT record FROM draft_assistance.invocation_versions "
        "WHERE namespace=%s AND security_domain=%s AND invocation_id=%s "
        "ORDER BY aggregate_version DESC LIMIT 1",
        (
            context.scope.tenant_id,
            context.scope.security_domain,
            source["invocationId"],
        ),
    ).fetchone()
    if (
        not row
        or row["record"]["initiatingPrincipalId"] != context.principal_id
        or any(
            row["record"][key] != source.get(key)
            for key in ("invocationId", "contextId", "turnId", "turnVersion")
        )
    ):
        raise AuthorityError("CONVERSATION_HISTORY_SOURCE_MISMATCH")
    if policy is not None:
        admitted = request_row(c, source["contextId"])
        if (
            not admitted
            or admitted["subject_id"] != context.principal_id
            or admitted["record"].get("conversation_id") != conversation
            or admitted["record"].get("owned_understanding_policy_digest")
            != policy.understanding_policy_digest
        ):
            raise AuthorityError("CONVERSATION_HISTORY_SOURCE_MISMATCH")
        policy.require_record(c, context, admitted)
    return ExactGrant(
        "DRAFT_ASSISTANCE",
        "READ_DRAFT_ASSISTANCE_INVOCATION",
        "draft-assistance:invocation:" + source["invocationId"],
    )


def retained_policy(service, c, source, *, general):
    """Choose only an explicitly configured policy matching the saved context."""
    if source.get("kind") != "DRAFT":
        return None
    row = request_row(c, source.get("contextId"))
    recorded = (row or {}).get("record", {}).get("owned_understanding_policy_digest")
    if not recorded:
        if general:
            raise AuthorityError("CONVERSATION_HISTORY_SOURCE_MISMATCH")
        return None
    for candidate in (
        service,
        getattr(service, "conversation_relation", None),
        *getattr(service, "retained_conversation_relations", ()),
    ):
        if (
            candidate is not None
            and candidate.experience is not None
            and candidate.experience.understanding_policy_digest == recorded
        ):
            return candidate
    raise AuthorityError("CONVERSATION_HISTORY_SOURCE_MISMATCH")


def prepare(service, records, context, conversation, c):
    policy = service.experience
    if policy is None or policy.document.historyReadEnabled is not True:
        return {"available": False, "items": []}
    # This is the current business eligibility window, not the old 8h call lease.
    _, now, lifetime = policy._require(service, c, context)
    general = conversation not in policy.document.conversations
    if general and not policy.document.ownedConversationUnderstanding:
        return {"available": False, "items": []}
    owned = records.owned(c, context, conversation, lock=True)
    if owned["owner_id"] != context.principal_id:
        raise AuthorityError("CONVERSATION_HISTORY_SCOPE_DENIED")
    facts = c.execute(
        "SELECT facts FROM private_conversation.message_facts WHERE tenant_id=%s "
        "AND security_domain=%s AND conversation_id=%s ORDER BY message_id",
        (context.scope.tenant_id, context.scope.security_domain, conversation),
    ).fetchall()
    targets = {}
    for fact in facts:
        for key in ("source", "authorizationSource"):
            source = fact["facts"].get(key)
            if not source:
                continue
            selected = retained_policy(service, c, source, general=general)
            selected_policy = selected.experience if selected else None
            if selected:
                selected_policy._require(selected, c, context)
            grant = source_grant(
                c, context, source, policy=selected_policy, conversation=conversation
            )
            if grant:
                targets[grant] = selected_policy or policy
    from .conversation_work_history import targets as work_targets

    work_reads = work_targets(service, records, c, context, conversation)
    targets.update({grant: policy for grant in work_reads})
    grants = service.delegation.grants
    bound = bound_grants(grants, c)
    results = []
    for grant in sorted(targets, key=lambda g: g.exact_resource):
        policy = targets[grant]
        lock(c, "history-read:" + context.principal_id + ":" + grant.exact_resource)
        state = current(bound, context, (grant,))
        if state == "UNAVAILABLE":
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE")
        if state == "REVOKED" or was_denied(c, context, grant):
            results.append({"state": "REVOKED" if state == "REVOKED" else "DENIED"})
            continue
        if state == "EFFECTIVE":
            results.append({"state": state})
            continue
        prior = c.execute(
            "SELECT g.grant_id,r.purpose FROM authorization_admin.grants g "
            "JOIN authorization_admin.grant_requests r USING(request_id) "
            "WHERE g.tenant_id=%s "
            "AND g.security_domain=%s AND g.subject_principal_id=%s AND g.owner=%s "
            "AND g.action=%s AND g.exact_resource=%s "
            "ORDER BY g.created_at DESC,g.grant_id "
            "LIMIT 1",
            (
                context.scope.tenant_id,
                context.scope.security_domain,
                context.principal_id,
                grant.owner,
                grant.action,
                grant.exact_resource,
            ),
        ).fetchone()
        if not prior:
            results.append({"state": "NO_PRIOR_READ"})
            continue
        if (
            not bound.target_validator
            or not bound.target_validator.is_known_exact_target(
                context, grant, connection=c
            )
        ):
            raise AuthorityError("CONVERSATION_HISTORY_TARGET_UNAVAILABLE")
        key = "conversation-history:" + digest(
            [
                policy.history_policy_digest,
                conversation,
                grant.exact_resource,
                prior["grant_id"],
            ]
        )
        request = bound.submit_request(
            context,
            GrantRequestCommand(
                prior["purpose"] if grant in work_reads else "PROBLEM_DRAFT_ASSISTANCE",
                (grant,),
                key,
            ),
        )
        if request.status.value != "PENDING":
            results.append({"state": request.status.value})
            continue
        decision = GrantDecision(
            "grant-decision-" + uuid4().hex,
            request.request_id,
            "policy:f3-conversation-history-read",
            conversation,
            True,
            "RETAINED_CONVERSATION_READ",
            "POLICY",
            policy.history_policy_digest,
            grants.generation.policy_version,
            "f3-history-read:" + conversation,
            now,
        )
        c.execute(
            "INSERT INTO authorization_admin.grant_decisions "
            "(decision_id,request_id,issuer_principal_id,issuer_meta_decision_id,"
            "approved,reason_category,basis_type,basis_reference_digest,policy_version,"
            "audit_source,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                decision.decision_id,
                request.request_id,
                decision.issuer_principal_id,
                conversation,
                True,
                decision.reason_category,
                "POLICY",
                policy.history_policy_digest,
                decision.policy_version,
                decision.audit_source,
                now,
            ),
        )
        expiry = min(lifetime, now + timedelta(hours=8))
        service.repository._insert_grant(
            c,
            GrantId("grant-" + uuid4().hex),
            request,
            decision,
            grant,
            now,
            expiry,
            grants.recovery_epoch,
        )
        c.execute(
            "UPDATE authorization_admin.grant_requests SET state='APPROVED',"
            "aggregate_version=aggregate_version+1,decided_at=%s WHERE request_id=%s",
            (now, request.request_id),
        )
        service.repository._audit(
            c,
            event_type="CONVERSATION_HISTORY_READ_GRANTED",
            actor_id=decision.issuer_principal_id,
            outcome="APPROVED",
            reason="RETAINED_CONVERSATION_READ",
            occurred_at=now,
            scope=context.scope,
            subject_id=request.request_id,
            generation=grants.generation.generation,
            recovery_epoch=grants.recovery_epoch,
        )
        results.append({"state": "APPROVED", "expiresAt": expiry.isoformat()})
    return {"available": True, "items": results}


def install_history_access(service, authorizer):
    from fastapi import Request
    from pydantic import BaseModel, ConfigDict

    class PrepareHistory(BaseModel):
        model_config = ConfigDict(extra="forbid")

    def install(app, authenticate, require_csrf, boundary_policy):
        app.state.conversation_history_access_available = lambda context: bool(
            service.experience
            and service.experience.document.historyReadEnabled is True
            and service.experience.matches(context)
        )

        @app.post("/api/workbench/v1/conversations/{conversation}/history-access")
        def prepare_history(conversation: str, request: Request, spec: PrepareHistory):
            session, context = authenticate(request)
            require_csrf(request, session)
            actions = getattr(app.state, "conversation_actions", None)
            if actions is None or request.query_params:
                raise AuthorityError("CONVERSATION_HISTORY_UNAVAILABLE")
            with (
                authorizer.controller.protected_request(),
                service.repository.connection_scope() as c,
            ):
                return {
                    "result": prepare(
                        service, actions.records, context, conversation, c
                    )
                }

    return install
