# ruff: noqa: E501 -- Explicit bounded same-connection owner queries.
"""One retained event's READ requests through the original independent issuer."""

from datetime import UTC, timedelta

from pydantic import Field

from .authority_contracts import ExactGrant
from .conversation_work_history import result_read_targets
from .digital_employee_definition import digest
from .fixed_chat_facts import require
from .fixed_chat_grants import grants_on_connection, static_read_revoked
from .grant_administration_application import GrantDecisionCommand, GrantRequestCommand
from .native_progress_projection import projection_read_grants
from .read_access_recovery import current
from .test_resource_read_access import was_denied
from .workbench_bff_schemas import StrictWorkbenchModel
from .workbench_owner_authorization import WorkbenchOwnerError


class ReadAccess(StrictWorkbenchModel):
    bindingDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    workDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    eventId: str = Field(min_length=1, max_length=200)
    receiptDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    preparationDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    readTargetDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    previousCommandId: str | None = Field(default=None, min_length=1, max_length=160)
    runId: str = Field(min_length=1, max_length=200)
    commandId: str = Field(min_length=1, max_length=160)


def members_for(call, prepared, validator):
    c = call.connection
    members = set(result_read_targets(c, prepared))
    from .execution_preparation_postgres import PreparedExecutionStore
    from .prepared_skill_invocation import planned_outputs

    _, progress = PreparedExecutionStore(c).read(
        prepared.namespace, prepared.security_domain, prepared.run_id
    )
    outputs = planned_outputs(prepared, progress)
    artifacts = {
        row["artifact_id"]
        for row in c.execute(
            "SELECT artifact_id FROM execution_authority.run_artifacts WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s",
            (prepared.namespace, prepared.security_domain, prepared.run_id),
        ).fetchall()
    }
    uses = {
        row["resource_use_id"]
        for row in c.execute(
            "SELECT DISTINCT resource_use_id FROM resource_use.snapshots WHERE namespace=%s AND security_domain=%s AND resource_use_id=ANY(%s)",
            (
                prepared.namespace,
                prepared.security_domain,
                [o["resourceUseId"] for o in outputs],
            ),
        ).fetchall()
    }
    formed_evidence = {
        o["evidenceGrant"] for o in outputs if o["artifactId"] in artifacts
    }
    formed_uses = {o["resourceGrant"] for o in outputs if o["resourceUseId"] in uses}
    members = {
        g
        for g in members
        if (g.owner != "EVIDENCE" or g.exact_resource in formed_evidence)
        and (g.owner != "RESOURCE_USE" or g.exact_resource in formed_uses)
    }
    members.add(
        ExactGrant(
            "EXECUTION", "READ", "governed-execution:prepared:" + prepared.digest
        )
    )
    for task in prepared.participants:
        members.update(
            g
            for g in projection_read_grants(prepared, task)
            if g.action in {"READ", "READ_RESOURCE", "READ_REFERENCE"}
        )
    require(
        len(members) <= 192
        and all(
            g.action in {"READ", "READ_RESOURCE", "READ_REFERENCE"} for g in members
        )
    )
    require(validator is not None)
    members = {
        g
        for g in members
        if validator.is_known_exact_target(call.context, g, connection=c)
    }
    require(
        ExactGrant(
            "EXECUTION", "READ", "governed-execution:prepared:" + prepared.digest
        )
        in members
    )
    return tuple(sorted(members, key=lambda g: (g.owner, g.action, g.exact_resource)))


def target_digest(members):
    return digest(sorted((g.owner, g.action, g.exact_resource) for g in members))


def permits_target_successor(state, previous, current_members):
    if not previous:
        return False
    return (state == "READ_READY" and set(previous) < set(current_members)) or (
        state == "EXPIRED" and set(previous) <= set(current_members)
    )


class FixedChatReadAccess:
    def __init__(self, delivery):
        self.delivery = delivery

    def basis(self):
        policy = self.delivery.policy
        return (
            "fixed-chat-read:"
            + policy.policyId
            + ":"
            + digest(policy.model_dump(mode="json"))
        )

    def identity(self, call, conversation, event_id, receipt_digest, command_id):
        permit, _bound, _event, prepared = self.delivery.selected(
            call, conversation, event_id, receipt_digest
        )
        identity = dict(
            conversationId=conversation,
            bindingDigest=permit.bindingDigest,
            workDigest=permit.work.digest,
            eventId=event_id,
            receiptDigest=receipt_digest,
            preparationDigest=prepared.digest,
            runId=prepared.run_id,
            commandId=command_id,
        )
        prefix = (
            "fixed-chat-read:"
            + digest(
                [
                    permit.tenantId,
                    permit.securityDomain,
                    permit.subjectId,
                    conversation,
                    permit.bindingDigest,
                    event_id,
                    receipt_digest,
                ]
            )
            + ":"
        )
        return identity, prepared, prefix, prefix + digest(command_id)

    def observed(self, call, key):
        c, context = call.connection, call.context
        claim = c.execute(
            "SELECT result_id,result_kind,result_record,payload_digest FROM authorization_admin.idempotency_claims "
            "WHERE tenant_id=%s AND security_domain=%s AND actor_id=%s "
            "AND command_type=%s AND idempotency_key=%s",
            (
                context.scope.tenant_id,
                context.scope.security_domain,
                context.principal_id,
                "SUBMIT_GRANT_REQUEST:RECOVERY_EPOCH:" + str(call.recovery_epoch),
                key,
            ),
        ).fetchone()
        if not claim:
            return "NOT_PREPARED", (), None
        if (
            not claim["result_id"]
            or claim["result_kind"] != "GRANT_REQUEST"
            or claim["result_record"] != {"id": claim["result_id"]}
        ):
            return "UNKNOWN", (), None
        row = c.execute(
            "SELECT r.*,d.approved,d.basis_type,d.basis_reference_digest,d.issuer_principal_id,d.decision_id FROM authorization_admin.grant_requests r "
            "LEFT JOIN authorization_admin.grant_decisions d USING(request_id) WHERE r.request_id=%s",
            (claim["result_id"],),
        ).fetchone()
        if (
            not row
            or (row["tenant_id"], row["security_domain"], row["subject_principal_id"])
            != (
                context.scope.tenant_id,
                context.scope.security_domain,
                context.principal_id,
            )
            or row["state"] != "APPROVED"
            or row["approved"] is not True
            or row["purpose"] != "RESOURCE_PREPARATION"
            or row["issuer_principal_id"] != self.delivery.automation.policy.issuer
            or row["basis_type"] != "POLICY"
            or row["basis_reference_digest"]
            != digest({"type": "POLICY", "reference": self.basis()})
        ):
            return "UNKNOWN", (), None
        grants = c.execute(
            "SELECT owner,action,exact_resource,expires_at,tenant_id,security_domain,subject_principal_id,decision_id FROM authorization_admin.grants WHERE request_id=%s",
            (claim["result_id"],),
        ).fetchall()
        if any(
            (g["tenant_id"], g["security_domain"], g["subject_principal_id"])
            != (
                context.scope.tenant_id,
                context.scope.security_domain,
                context.principal_id,
            )
            or g["decision_id"] != row["decision_id"]
            or g["expires_at"] is None
            or g["expires_at"]
            > min(
                self.delivery.policy.expiresAt,
                row["created_at"]
                + timedelta(seconds=self.delivery.policy.grantTTLSeconds),
            )
            for g in grants
        ):
            return "UNKNOWN", (), None
        requested = c.execute(
            "SELECT owner,action,exact_resource FROM authorization_admin.grant_request_members WHERE request_id=%s ORDER BY ordinal",
            (claim["result_id"],),
        ).fetchall()

        if claim["payload_digest"] != digest(
            dict(
                subject=context.principal_id,
                tenant=context.scope.tenant_id,
                securityDomain=context.scope.security_domain,
                purpose="RESOURCE_PREPARATION",
                members=[
                    [r["owner"], r["action"], r["exact_resource"]] for r in requested
                ],
                continuationDigest=None,
            )
        ):
            return "UNKNOWN", (), None

        def triple(r):
            return (r["owner"], r["action"], r["exact_resource"])

        if not grants or {triple(r) for r in grants} != {triple(r) for r in requested}:
            return "UNKNOWN", (), None
        bound = grants_on_connection(self.delivery.automation.grants, c)
        members = tuple(ExactGrant(*triple(r)) for r in grants)
        if any(
            g.action not in {"READ", "READ_RESOURCE", "READ_REFERENCE"} for g in members
        ):
            return "UNKNOWN", (), None
        if static_read_revoked(bound.generation, context, members):
            return "UNKNOWN", (), None
        if any(
            current(bound, context, (g,)) == "REVOKED" or was_denied(c, context, g)
            for g in members
        ):
            return "UNKNOWN", (), None
        now = self.delivery.automation.grants.clock()
        if all(r["expires_at"] is not None and r["expires_at"] <= now for r in grants):
            return "EXPIRED", members, min(r["expires_at"] for r in grants)
        if call.authority.current_action_grants(members) == (True,) * len(members):
            return "READ_READY", members, min(r["expires_at"] for r in grants)
        return "UNKNOWN", (), None

    def status(self, call, conversation, event_id, receipt_digest, command_id):
        identity, p, _prefix, key = self.identity(
            call, conversation, event_id, receipt_digest, command_id
        )
        state, prior, _expiry = self.observed(call, key)
        current_targets = members_for(
            call, p, self.delivery.automation.grants.target_validator
        )
        relation = (
            "SAME"
            if prior and set(prior) == set(current_targets)
            else (
                "STRICT_SUPERSET"
                if prior and set(prior) < set(current_targets)
                else "INCOMPATIBLE"
            )
        )
        return {
            **identity,
            "state": state,
            "readTargetDigest": target_digest(prior) if prior else None,
            "currentReadTargetDigest": target_digest(current_targets),
            "readTargetRelation": relation,
        }

    def prepare(self, call, conversation, command):
        identity, p, prefix, key = self.identity(
            call,
            conversation,
            command.eventId,
            command.receiptDigest,
            command.commandId,
        )
        require(
            {
                k: identity[k]
                for k in type(command).model_fields
                if k not in {"readTargetDigest", "previousCommandId"}
            }
            == command.model_dump(exclude={"readTargetDigest", "previousCommandId"})
        )
        c, context = call.connection, call.context
        c.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,73))", (prefix,))
        members = members_for(call, p, self.delivery.automation.grants.target_validator)
        require(target_digest(members) == command.readTargetDigest)
        old, old_members, _ = self.observed(call, key)
        if old != "NOT_PREPARED":
            if old_members:
                require(target_digest(old_members) == command.readTargetDigest)
            return self.status(
                call,
                conversation,
                command.eventId,
                command.receiptDigest,
                command.commandId,
            )
        others = c.execute(
            "SELECT idempotency_key FROM authorization_admin.idempotency_claims WHERE tenant_id=%s "
            "AND security_domain=%s AND actor_id=%s AND command_type=%s AND idempotency_key LIKE %s",
            (
                context.scope.tenant_id,
                context.scope.security_domain,
                context.principal_id,
                "SUBMIT_GRANT_REQUEST:RECOVERY_EPOCH:" + str(call.recovery_epoch),
                prefix + "%",
            ),
        ).fetchall()
        cap = self.delivery.policy.expiresAt
        if others:
            require(command.previousCommandId is not None)
            prior_key = prefix + digest(command.previousCommandId)
            require(any(r["idempotency_key"] == prior_key for r in others))
            prior_state, prior_members, prior_expiry = self.observed(call, prior_key)
            require(permits_target_successor(prior_state, prior_members, members))
            for r in others:
                state, old_set, _ = self.observed(call, r["idempotency_key"])
                require(
                    state in {"READ_READY", "EXPIRED"} and set(old_set) <= set(members)
                )
            if prior_state == "READ_READY":
                # Full request snapshot remains immutable; existing READs are not
                # extended early when a newly formed artifact is added.
                cap = min(cap, prior_expiry)
        else:
            require(command.previousCommandId is None)
        automation, policy = self.delivery.automation, self.delivery.policy
        bound = grants_on_connection(automation.grants, c)
        if static_read_revoked(bound.generation, context, members):
            raise WorkbenchOwnerError("FIXED_CHAT_READ_NOT_AUTHORIZED", 403)
        for grant in members:
            state = current(bound, context, (grant,))
            if state in {"UNAVAILABLE", "REVOKED"} or was_denied(c, context, grant):
                raise WorkbenchOwnerError("FIXED_CHAT_READ_NOT_AUTHORIZED", 403)
        issuer = automation.authenticate(context)
        require(issuer.principal_id != context.principal_id)
        credential = bound.generation.credential_by_id(
            issuer.session_id_or_service_credential_id
        )
        require(credential is not None)
        cap = min(cap, credential.expires_at)
        request = bound.submit_request(
            context, GrantRequestCommand("RESOURCE_PREPARATION", members, key)
        )
        expires = min(
            cap,
            request.created_at + timedelta(seconds=policy.grantTTLSeconds),
        )
        if expires <= bound.clock():
            raise WorkbenchOwnerError("FIXED_CHAT_READ_EXPIRED", 409)
        bound.decide_request(
            issuer,
            GrantDecisionCommand(
                request.request_id,
                True,
                "ASSIGNED_BUSINESS_DUTY",
                "POLICY",
                self.basis(),
                None,
                expires.astimezone(UTC),
                "fixed-chat-decision:" + digest([key, request.request_id]),
                expected_version=1,
            ),
        )
        automation.proof_grants(call, members)
        return self.status(
            call,
            conversation,
            command.eventId,
            command.receiptDigest,
            command.commandId,
        )
