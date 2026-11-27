"""Optional, exact conversation admission on one immutable experience ledger.

This adapter never creates a budget, changes identity, or permits external writes.
The local operator configuration is authority; browser content is not authority.
"""

from contextvars import ContextVar
from datetime import timedelta
from pathlib import Path
from typing import Literal
from uuid import uuid4

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .authority_contracts import AuthenticationSource, AuthorityError
from .draft_assistance import DraftAssistanceError
from .task_delegation import Limits, digest

LEDGER = "ledger:f3-main-experience:20261112"
_binding = ContextVar("verified_conversation_experience_request", default=None)


class ExperiencePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: Literal[
        "f3-conversation-experience.v1",
        "f3-conversation-experience.v2",
        "f3-conversation-experience.v3",
    ]
    tenantId: Literal["s5-323-demo"]
    securityDomain: Literal["isolated-real-demo"]
    subjectId: Literal["human:demo323-approver"]
    accountId: Literal["local-account:reviewer324"]
    authorizationDigest: str = Field(pattern="^[a-f0-9]{64}$")
    configuration: Limits
    conversations: dict[
        str, Literal["SYNTHETIC_DOCUMENT_REVIEW", "SYNTHETIC_SALES_ANALYSIS"]
    ] = Field(min_length=1, max_length=2)
    externalWrites: Literal[False]
    allowanceId: str | None = Field(default=None, min_length=1, max_length=200)
    historyReadEnabled: bool | None = None
    ownedConversationUnderstanding: Literal[True] | None = None
    predecessorSchemaVersion: (
        Literal["f3-conversation-experience.v1", "f3-conversation-experience.v2"] | None
    ) = None
    predecessorPolicyDigest: str | None = Field(default=None, pattern="^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def allowance_version(self):
        successor = self.schemaVersion == "f3-conversation-experience.v3"
        if successor != bool(self.ownedConversationUnderstanding) or successor != bool(
            self.predecessorSchemaVersion and self.predecessorPolicyDigest
        ):
            raise ValueError("CONTEXT_ADMISSION_POLICY_SUCCESSOR_INVALID")
        if not successor and (
            self.predecessorSchemaVersion or self.predecessorPolicyDigest
        ):
            raise ValueError("CONTEXT_ADMISSION_POLICY_SUCCESSOR_INVALID")
        effective_schema = (
            self.predecessorSchemaVersion if successor else self.schemaVersion
        )
        if (effective_schema == "f3-conversation-experience.v2") != (
            self.allowanceId is not None
        ):
            raise ValueError("CONTEXT_ADMISSION_ALLOWANCE_VERSION_MISMATCH")
        return self


def begin_bound(
    service, context, *, conversation, message_id, question_only=False, **kwargs
):
    """Called only after the API has verified ownership and exact user content."""
    admission = getattr(
        getattr(service, "authorization", None), "context_admission", None
    )
    experience = getattr(admission, "experience", None)
    if question_only and (
        not experience
        or not experience.matches(context)
        or not experience.document.ownedConversationUnderstanding
        or any(
            kwargs.get(k)
            for k in (
                "parent_context_id",
                "parent_turn_id",
                "predecessor_invocation_id",
            )
        )
    ):
        raise DraftAssistanceError("CONVERSATION_ROUTING_CONTEXT_INVALID")
    if experience and experience.matches(context):
        try:
            with admission.repository.connection_scope() as c:
                experience._require(admission, c, context)
                experience.conversation_scope(
                    c, context, conversation, message_id, question_only=question_only
                )
        except AuthorityError as exc:
            raise DraftAssistanceError(exc.reason_code) from exc
    goal_metadata = None
    if conversation and message_id and admission is not None:
        from .conversation_goal_selection import PORT
        from .conversation_goal_slots import enabled, message_goal

        with admission.repository.connection_scope() as c:
            goal_id = message_goal(c, PORT, context, conversation, message_id)
            if goal_id is not None:
                if not enabled():
                    raise DraftAssistanceError("CONVERSATION_GOALS_DISABLED")
                goal_metadata = {
                    "conversationId": conversation,
                    "messageId": message_id,
                    "goalId": goal_id,
                }
    from .conversation_relation_context import bind_goal

    token = _binding.set((conversation, message_id, kwargs["key"], question_only))
    try:
        with bind_goal(goal_metadata):
            return service.begin(context, **kwargs)
    finally:
        _binding.reset(token)


class ConversationExperienceAdmission:
    def __init__(self, path, configuration):
        self.path = Path(path)
        if not self.path.is_absolute() or self.path.stat().st_mode & 0o077:
            raise AuthorityError("CONTEXT_ADMISSION_EXPERIENCE_POLICY_INVALID")
        self.document = ExperiencePolicy.model_validate_json(self.path.read_text())
        base = self.document.model_dump(
            mode="json",
            exclude_none=True,
            exclude={
                "historyReadEnabled",
                "ownedConversationUnderstanding",
                "predecessorSchemaVersion",
                "predecessorPolicyDigest",
            },
        )
        if self.document.ownedConversationUnderstanding:
            base["schemaVersion"] = self.document.predecessorSchemaVersion
        self.policy_digest = digest(base)
        if self.document.ownedConversationUnderstanding and (
            self.document.predecessorPolicyDigest != self.policy_digest
        ):
            raise AuthorityError("CONTEXT_ADMISSION_POLICY_PREDECESSOR_MISMATCH")
        self.understanding_policy_digest = digest(
            self.document.model_dump(
                mode="json", exclude_none=True, exclude={"historyReadEnabled"}
            )
        )
        self.history_policy_digest = digest(
            self.document.model_dump(mode="json", exclude_none=True)
        )
        limits = self.document.configuration.model_dump()
        if (
            limits != configuration
            or limits["ledger_id"] != LEDGER
            or (
                self.document.allowanceId is None
                and (limits["calls"], limits["cost_microusd"]) != (20, 1_000_000)
            )
            or limits["calls"] > 100
            or limits["cost_microusd"] > 10_000_000
            or any(
                not key.strip() or len(key) > 128 for key in self.document.conversations
            )
        ):
            raise AuthorityError("CONTEXT_ADMISSION_CONFIGURATION_MISMATCH")

    def matches(self, context):
        return context.principal_id == self.document.subjectId

    def _require(self, service, c, context):
        policy = self.document
        # Removing/replacing the operator file closes admission, not a lease renewal.
        try:
            current = ExperiencePolicy.model_validate_json(self.path.read_text())
        except (OSError, ValueError) as exc:
            raise AuthorityError("CONTEXT_ADMISSION_EXPERIENCE_POLICY_INVALID") from exc
        if current != policy or self.path.stat().st_mode & 0o077:
            raise AuthorityError("CONTEXT_ADMISSION_EXPERIENCE_POLICY_CHANGED")
        if (
            not self.matches(context)
            or context.authentication_source is not AuthenticationSource.BROWSER_SESSION
            or (context.scope.tenant_id, context.scope.security_domain)
            != (policy.tenantId, policy.securityDomain)
            or service.configuration != policy.configuration.model_dump()
        ):
            raise AuthorityError("CONTEXT_ADMISSION_SCOPE_DENIED")
        account = c.execute(
            "SELECT a.* FROM browser_identity.local_accounts a JOIN "
            "browser_identity.local_account_sessions s USING(account_id) "
            "WHERE s.session_id=%s AND a.account_id=%s AND a.principal_id=%s "
            "AND a.tenant_id=%s AND a.security_domain=%s "
            "AND a.revision=s.account_revision AND a.status='ENABLED' FOR SHARE OF a",
            (
                context.session_id_or_service_credential_id,
                policy.accountId,
                policy.subjectId,
                policy.tenantId,
                policy.securityDomain,
            ),
        ).fetchone()
        if not account:
            raise AuthorityError("CONTEXT_ADMISSION_ACCOUNT_INACTIVE")
        generation = c.execute(
            "SELECT generation,recovery_epoch FROM "
            "authorization_admin.active_generation "
            "WHERE singleton=true FOR SHARE"
        ).fetchone()
        if generation != {
            "generation": service.delegation.grants.generation.generation,
            "recovery_epoch": service.delegation.grants.recovery_epoch,
        }:
            raise AuthorityError("CONTEXT_ADMISSION_GENERATION_MISMATCH")
        budget = c.execute(
            "SELECT * FROM draft_provider_budget.policies WHERE namespace=%s "
            "AND security_domain=%s AND ledger_id=%s FOR SHARE",
            (policy.tenantId, policy.securityDomain, LEDGER),
        ).fetchone()
        if not budget or (budget["call_cap"], budget["total_cost_cap_microusd"]) != (
            20,
            1_000_000,
        ):
            raise AuthorityError("CONTEXT_ADMISSION_BUDGET_MISMATCH")
        expires = budget["created_at"] + timedelta(hours=24)
        if policy.allowanceId is not None:
            from .provider_budget_allowance import require_context

            allowance = require_context(
                c,
                policy.tenantId,
                policy.securityDomain,
                LEDGER,
                policy.allowanceId,
                policy.authorizationDigest,
                policy.configuration.model_dump(),
            )
            expires = allowance.expiresAt
        now = c.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        if not budget["created_at"] <= now < expires:
            raise AuthorityError("CONTEXT_ADMISSION_EXPERIENCE_EXPIRED")
        return account, now, expires

    def conversation_scope(
        self, c, context, conversation, message_id, *, question_only=False
    ):
        if conversation in self.document.conversations and not question_only:
            return False
        if not self.document.ownedConversationUnderstanding:
            raise AuthorityError("CONTEXT_ADMISSION_CONVERSATION_BINDING_REQUIRED")
        known = c.execute(
            "SELECT 1 FROM private_conversation.conversations v JOIN "
            "private_conversation.messages m "
            "USING(tenant_id,security_domain,conversation_id) "
            "WHERE v.tenant_id=%s AND v.security_domain=%s AND v.conversation_id=%s "
            "AND v.owner_id=%s AND v.archived_at IS NULL AND m.message_id=%s "
            "AND m.author_id=%s AND NOT EXISTS (SELECT 1 FROM "
            "private_conversation.message_facts f WHERE f.tenant_id=m.tenant_id "
            "AND f.security_domain=m.security_domain "
            "AND f.conversation_id=m.conversation_id "
            "AND f.message_id=m.message_id) FOR SHARE OF v,m",
            (
                context.scope.tenant_id,
                context.scope.security_domain,
                conversation,
                context.principal_id,
                message_id,
                context.principal_id,
            ),
        ).fetchone()
        if not known:
            raise AuthorityError("CONTEXT_ADMISSION_CONVERSATION_BINDING_REQUIRED")
        return True

    def require_record(self, c, context, row):
        if not row or not row["record"].get("owned_understanding_policy_digest"):
            return
        record = row["record"]
        if (
            not self.document.ownedConversationUnderstanding
            or record["owned_understanding_policy_digest"]
            != self.understanding_policy_digest
            or row["subject_id"] != context.principal_id
        ):
            raise AuthorityError("CONTEXT_ADMISSION_SCOPE_DENIED")
        if not self.conversation_scope(
            c,
            context,
            record["conversation_id"],
            record["first_user_message_id"],
            question_only=record.get("question_only", False),
        ):
            raise AuthorityError("CONTEXT_ADMISSION_SCOPE_DENIED")

    def prepare(self, service, c, context, invocation):
        from .context_call_admission import active, lock, request_row

        account, now, expires = self._require(service, c, context)
        binding = _binding.get()
        if (
            not binding
            or not binding[1]
            or binding[2] != invocation.scoped_idempotency_key
            or invocation.initiating_principal_id != context.principal_id
            or invocation.profile_revision_id
            != service.configuration["profile_revision_id"]
        ):
            raise AuthorityError("CONTEXT_ADMISSION_CONVERSATION_BINDING_REQUIRED")
        general = self.conversation_scope(
            c, context, binding[0], binding[1], question_only=binding[3]
        )
        lock(c, invocation.context_id)
        row = request_row(c, invocation.context_id)
        if row:
            if (
                row["record"].get("experience_policy_digest"),
                row["record"].get("conversation_id"),
            ) != (self.policy_digest, binding[0]):
                raise AuthorityError("CONTEXT_ADMISSION_CONFIGURATION_MISMATCH")
            if bool(row["record"].get("question_only")) != binding[3]:
                raise AuthorityError("CONTEXT_ADMISSION_SCOPE_DENIED")
            self.require_record(c, context, row)
            active(c, row, service.configuration)
            return True
        history = c.execute(
            "SELECT record FROM draft_assistance.invocation_versions WHERE "
            "namespace=%s AND security_domain=%s AND record->>'contextId'=%s",
            (
                self.document.tenantId,
                self.document.securityDomain,
                invocation.context_id,
            ),
        ).fetchall()
        if not history or any(
            r["record"]["state"] != "AUTHORIZATION_PENDING" for r in history
        ):
            raise AuthorityError("CONTEXT_ADMISSION_HISTORY_DENIED")
        record = {
            "task_id": "F3-CONVERSATION-EXPERIENCE",
            "phase": "understanding",
            "synthetic_only": not general,
            "external_writes": False,
            "context_id": invocation.context_id,
            "first_invocation_id": invocation.invocation_id,
            "subject_id": context.principal_id,
            "account_id": account["account_id"],
            "account_revision": account["revision"],
            "tenant_id": self.document.tenantId,
            "security_domain": self.document.securityDomain,
            "configuration": service.configuration,
            "experience_policy_digest": self.policy_digest,
            "authorization_digest": self.document.authorizationDigest,
            "conversation_id": binding[0],
            "first_user_message_id": binding[1],
            "scenario": "GENERAL_CONVERSATION_UNDERSTANDING"
            if general
            else self.document.conversations[binding[0]],
            **({"question_only": True} if binding[3] else {}),
            **(
                {"owned_understanding_policy_digest": self.understanding_policy_digest}
                if general
                else {}
            ),
            "ledger_expires_at": expires.isoformat(),
            **(
                {"budget_allowance_id": self.document.allowanceId}
                if self.document.allowanceId
                else {}
            ),
        }
        c.execute(
            "INSERT INTO authorization_admin.context_call_requests "
            "(context_id,tenant_id,security_domain,subject_id,account_id,account_revision,"
            "first_invocation_id,record,digest) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                invocation.context_id,
                self.document.tenantId,
                self.document.securityDomain,
                context.principal_id,
                account["account_id"],
                account["revision"],
                invocation.invocation_id,
                Jsonb(record),
                digest(record),
            ),
        )
        decision = {
            "type": "F3_CONVERSATION_EXPERIENCE",
            "request": record,
            "policy_digest": self.understanding_policy_digest
            if general
            else self.policy_digest,
            "ledger_unchanged": True,
        }
        c.execute(
            "INSERT INTO authorization_admin.context_call_decisions VALUES"
            "(%s,%s,1,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                "f3-experience:" + digest(invocation.context_id),
                invocation.context_id,
                "policy:f3-conversation-experience",
                context.principal_id,
                service.delegation.grants.generation.generation,
                service.delegation.grants.recovery_epoch,
                "f3:" + invocation.context_id,
                digest(decision),
                Jsonb(decision),
                now,
                min(expires, now + timedelta(hours=8)),
            ),
        )
        service.repository._audit(
            c,
            event_type="CONTEXT_CALL_ADMISSION",
            actor_id="policy:f3-conversation-experience",
            outcome="APPROVED",
            reason="BOUNDED_GENERAL_UNDERSTANDING"
            if general
            else "BOUNDED_SYNTHETIC_EXPERIENCE",
            occurred_at=now,
            scope=context.scope,
            subject_id=invocation.context_id,
            generation=service.delegation.grants.generation.generation,
            recovery_epoch=service.delegation.grants.recovery_epoch,
        )
        return True

    def authorize_requests(self, service, context, invocation, request_ids):
        """Issue only the two existing exact owner/model requests for this call."""
        from .authority_contracts import GrantDecision, GrantId, GrantRequestStatus
        from .context_call_admission import active, request_row
        from .draft_assistance_authorization import (
            cancel_grant,
            model_grant,
            read_grant,
            request_grant,
        )

        grants = service.delegation.grants
        expected = {
            "PROBLEM_DRAFT_ASSISTANCE": {
                request_grant(invocation),
                read_grant(invocation),
                cancel_grant(invocation),
            },
            "PROBLEM_DRAFT_MODEL_INVOKE": {model_grant(invocation)},
        }
        with service.repository.connection_scope() as c:
            _, now, expires = self._require(service, c, context)
            row = request_row(c, invocation.context_id)
            if (
                not row
                or row["record"].get("experience_policy_digest") != self.policy_digest
            ):
                raise AuthorityError("CONTEXT_ADMISSION_SCOPE_DENIED")
            self.require_record(c, context, row)
            general = bool(row["record"].get("owned_understanding_policy_digest"))
            basis = self.understanding_policy_digest if general else self.policy_digest
            active(c, row, service.configuration)
            credential_id = service.repository._current_credential_id(
                c,
                context,
                now=now,
                recovery_epoch=grants.recovery_epoch,
                lock_session=True,
            )
            # Local accounts intentionally outlive their bootstrap credential.
            # _require locked the current account revision; this locks and checks
            # the authenticated session using the existing identity owner.
            if credential_id != self.document.accountId:
                raise AuthorityError("CONTEXT_ADMISSION_ACCOUNT_INACTIVE")
            expires = min(expires, now + timedelta(hours=8))
            if expires <= now:
                raise AuthorityError("CONTEXT_ADMISSION_ACCOUNT_INACTIVE")
            for request_id in request_ids:
                c.execute(
                    "SELECT request_id FROM authorization_admin.grant_requests "
                    "WHERE request_id=%s FOR UPDATE",
                    (request_id,),
                )
                request = service.repository._request(c, request_id)
                if (
                    request.subject_principal_id != context.principal_id
                    or request.scope != context.scope
                    or set(request.members) != expected.get(request.purpose)
                    or any(
                        not grants.target_validator.is_known_exact_target(
                            context, member, connection=c
                        )
                        for member in request.members
                    )
                ):
                    raise AuthorityError("CONTEXT_ADMISSION_EXACT_TARGET_DENIED")
                # Never renew a decided/revoked request or reinterpret a rejection.
                if request.status is not GrantRequestStatus.PENDING:
                    continue
                decision = GrantDecision(
                    "grant-decision-" + uuid4().hex,
                    request_id,
                    "policy:f3-conversation-experience",
                    invocation.context_id,
                    True,
                    "BOUNDED_GENERAL_UNDERSTANDING"
                    if general
                    else "BOUNDED_SYNTHETIC_EXPERIENCE",
                    "POLICY",
                    basis,
                    grants.generation.policy_version,
                    "f3-experience:" + invocation.context_id,
                    now,
                )
                c.execute(
                    "INSERT INTO authorization_admin.grant_decisions "
                    "(decision_id,request_id,issuer_principal_id,issuer_meta_decision_id,"
                    "approved,reason_category,basis_type,basis_reference_digest,policy_version,"
                    "audit_source,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        decision.decision_id,
                        request_id,
                        decision.issuer_principal_id,
                        decision.issuer_meta_decision_id,
                        True,
                        decision.reason_category,
                        "POLICY",
                        basis,
                        decision.policy_version,
                        decision.audit_source,
                        now,
                    ),
                )
                for member in request.members:
                    service.repository._insert_grant(
                        c,
                        GrantId("grant-" + uuid4().hex),
                        request,
                        decision,
                        member,
                        now,
                        expires,
                        grants.recovery_epoch,
                    )
                c.execute(
                    "UPDATE authorization_admin.grant_requests SET state='APPROVED',"
                    "aggregate_version=aggregate_version+1,decided_at=%s "
                    "WHERE request_id=%s",
                    (now, request_id),
                )
                service.repository._audit(
                    c,
                    event_type="CONTEXT_EXPERIENCE_EXACT_GRANTED",
                    actor_id=decision.issuer_principal_id,
                    outcome="APPROVED",
                    reason="BOUNDED_GENERAL_UNDERSTANDING"
                    if general
                    else "BOUNDED_SYNTHETIC_EXPERIENCE",
                    occurred_at=now,
                    scope=context.scope,
                    subject_id=request_id,
                    generation=grants.generation.generation,
                    recovery_epoch=grants.recovery_epoch,
                )
