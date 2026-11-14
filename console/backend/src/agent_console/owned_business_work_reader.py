"""Current read-only consumption of an existing business admission, including host.

No browser identity is manufactured, no admission is created, and no old model
lease is renewed. Callers supply their original trusted owner/command identity.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from .authority_contracts import AuthorityError, ExactGrant
from .context_call_admission import request_row
from .draft_assistance import DraftInvocationState, DraftResultKind, DraftScope
from .draft_assistance_authorization import read_grant
from .draft_assistance_postgres import PostgresDraftAssistanceRepository
from .execution_domain import ScopeIdentity
from .owned_business_policy import OwnedBusinessPolicy, OwnedBusinessScope
from .owned_business_postgres import context_binding, require_not_revoked, saved
from .owned_business_result_link import same_result_after_problem_link
from .plan_suggestion_domain import ExactReference
from .planning_candidates import read_published
from .understanding_adoption_postgres import read_chain
from .workbench_prepared_resources import reference


def require(condition, reason):
    if not condition:
        raise AuthorityError("OWNED_BUSINESS_" + reason)


@dataclass(frozen=True)
class OwnedBusinessBinding:
    admission_id: str
    record_digest: str
    policy_digest: str
    generation: int
    tenant_id: str
    security_domain: str
    subject_id: str
    scope: OwnedBusinessScope
    problem: ExactReference
    expires_at: datetime
    history_only: bool = False
    ontology_correction: dict | None = None


class OwnedBusinessWorkReader:
    def __init__(
        self,
        path,
        authorization,
        generation,
        recovery_epoch,
        *,
        retained_history_paths=(),
        _retained_read_only=False,
    ):
        self.retained_read_only = _retained_read_only
        self.path = path
        self.policy = OwnedBusinessPolicy.load(path)
        self.authorization = authorization
        self.generation, self.recovery_epoch = generation, recovery_epoch
        from .owned_business_retained_history import retained_readers

        self.retained_history = (
            {}
            if _retained_read_only
            else retained_readers(self, retained_history_paths)
        )

    def _reads(self, c, context, grants, now, *, history=False):
        states = self.authorization.has_current_grants(
            context,
            grants,
            now=now,
            generation=self.generation,
            recovery_epoch=self.recovery_epoch,
            connection=c,
            configure_transaction=False,
        )
        if not history:
            require(len(states) == len(grants) and all(states), "READ_DENIED")
            return
        from .authority_contracts import DynamicAuthorizationState
        from .test_resource_read_access import was_denied

        credential, decisions = self.authorization.read_linearized_authorization_states(
            context,
            grants,
            now=now,
            generation=self.generation,
            recovery_epoch=self.recovery_epoch,
            connection=c,
            configure_transaction=False,
        )
        require(credential is not None and len(decisions) == len(grants), "READ_DENIED")
        identity, _ = self.authorization._current_credential(
            context, credential, now=now
        )
        require(identity is not None, "IDENTITY_DENIED")
        tombstones = self.authorization.generation.static_grant_revocation_tombstones
        for grant, decision in zip(grants, decisions, strict=True):
            require(
                decision
                not in {
                    DynamicAuthorizationState.REVOKED,
                    DynamicAuthorizationState.UNAVAILABLE,
                }
                and (identity.credential_id, grant) not in tombstones
                and (
                    getattr(identity, "grant_source_id", identity.credential_id),
                    grant,
                )
                not in tombstones
                and not was_denied(c, context, grant),
                "READ_DENIED",
            )
            require(
                c.execute(
                    "SELECT 1 FROM authorization_admin.grants WHERE tenant_id=%s "
                    "AND security_domain=%s AND subject_principal_id=%s AND owner=%s "
                    "AND action=%s AND exact_resource=%s LIMIT 1",
                    (
                        context.scope.tenant_id,
                        context.scope.security_domain,
                        context.principal_id,
                        grant.owner,
                        grant.action,
                        grant.exact_resource,
                    ),
                ).fetchone()
                is not None,
                "NO_PRIOR_READ",
            )

    def planning_basis(self, c, planning, source):
        """Budget guard rechecks the basis recorded by the real planning owner.

        This is not an identity/admission API. The dispatch owner separately
        validates the current trusted principal and exact READ/INVOKE grants.
        """
        require(not self.retained_read_only, "HISTORY_ONLY")
        p = self.policy
        require(p.enabled and OwnedBusinessPolicy.load(self.path) == p, "DISABLED")
        proof = planning["record"].get("owned_business") or {}
        row = c.execute(
            "SELECT record,record_digest FROM "
            "authorization_admin.owned_business_admissions "
            "WHERE admission_id=%s AND tenant_id=%s AND security_domain=%s "
            "AND subject_id=%s",
            (
                proof.get("admissionId"),
                planning["tenant_id"],
                planning["security_domain"],
                planning["subject_id"],
            ),
        ).fetchone()
        from .resource_use_domain import canonical_digest

        require(
            row is not None
            and row["record_digest"]
            == proof.get("recordDigest")
            == canonical_digest(row["record"]),
            "BUSINESS_BINDING_CHANGED",
        )
        record = row["record"]
        require(
            (planning["tenant_id"], planning["security_domain"], planning["subject_id"])
            == (p.tenantId, p.securityDomain, p.subjectId)
            and record["policyDigest"] == p.digest
            and record["contextId"] == source["context_id"]
            and record["conversationId"] == planning["record"].get("conversation_id")
            and record["inputSource"]
            == planning["record"].get("understanding_input_source")
            and record["ledgerId"] == p.ledgerId
            and record["allowanceId"] == p.allowanceId
            and datetime.now(UTC)
            < min(p.expiresAt, datetime.fromisoformat(record["expiresAt"])),
            "POLICY_BINDING_CHANGED",
        )
        require_not_revoked(c, proof["admissionId"])
        require(
            not c.execute(
                "SELECT 1 FROM authorization_admin.context_call_decisions d JOIN "
                "authorization_admin.context_call_revocations r USING(admission_id) "
                "WHERE d.context_id=%s",
                (source["context_id"],),
            ).fetchone(),
            "CONTEXT_REVOKED",
        )

    def work(
        self,
        c,
        context,
        problem,
        *,
        source_digest=None,
        history=False,
        _apply_correction=True,
    ):
        require(not self.retained_read_only or history, "HISTORY_ONLY")
        p, now = self.policy, datetime.now(UTC)
        require(isinstance(problem, ExactReference), "EXACT_PROBLEM_REQUIRED")
        require(p.enabled and OwnedBusinessPolicy.load(self.path) == p, "DISABLED")
        if history and self.retained_history:
            from .owned_business_retained_history import select_reader

            retained = select_reader(self, c, context, problem)
            if retained is not None:
                return retained.work(
                    c, context, problem, source_digest=source_digest, history=True
                )
        require(
            (
                context.scope.tenant_id,
                context.scope.security_domain,
                context.principal_id,
            )
            == (p.tenantId, p.securityDomain, p.subjectId),
            "SCOPE_DENIED",
        )
        # Current-grant reads below acquire the governance lock. Take it before
        # admission/revocation locks, matching effect-time authorization callers.
        from .task_identity_continuity import lock_owner_generation

        lock_owner_generation(c)
        generation = c.execute(
            "SELECT generation,recovery_epoch FROM "
            "authorization_admin.active_generation "
            "WHERE singleton=true",
        ).fetchone()
        require(
            generation
            == dict(generation=self.generation, recovery_epoch=self.recovery_epoch),
            "GENERATION_CHANGED",
        )
        account = c.execute(
            "SELECT principal_id,tenant_id,security_domain,status FROM "
            "browser_identity.local_accounts WHERE account_id=%s",
            (p.accountId,),
        ).fetchone()
        require(
            account
            == dict(
                principal_id=p.subjectId,
                tenant_id=p.tenantId,
                security_domain=p.securityDomain,
                status="ENABLED",
            ),
            "ACCOUNT_INACTIVE",
        )
        bound = c.execute(
            "SELECT invocation_id,context_id FROM "
            "authorization_admin.context_call_objects "
            "WHERE tenant_id=%s AND security_domain=%s AND owner='BUSINESS_PROBLEM' "
            "AND resource_id=%s",
            (p.tenantId, p.securityDomain, problem.resource_id),
        ).fetchone()
        require(bound is not None, "BUSINESS_BINDING_REQUIRED")
        stored = saved(c, context, bound["invocation_id"])
        require(stored is not None, "ADMISSION_REQUIRED")
        require_not_revoked(c, stored["admission_id"])
        r = stored["record"]
        require(
            r["policyDigest"] == p.digest
            and r["accountId"] == p.accountId
            and r["ledgerId"] == p.ledgerId
            and r["allowanceId"] == p.allowanceId,
            "POLICY_BINDING_CHANGED",
        )
        selected = p.selected(r["inputSource"])
        require(
            r["scope"] == selected.model_dump(mode="json")
            and (
                source_digest is None or source_digest == selected.sourceContentDigest
            ),
            "SOURCE_CHANGED",
        )
        value = PostgresDraftAssistanceRepository._latest(
            c, DraftScope.from_context(context), bound["invocation_id"]
        )
        require(
            value is not None
            and value.state is DraftInvocationState.SUCCEEDED
            and value.result_kind is DraftResultKind.DRAFT_READY
            and value.initiating_principal_id == p.subjectId
            and value.context_id == bound["context_id"] == r["contextId"]
            and value.turn_id == r["turnId"]
            and value.turn_version == r["turnVersion"]
            and value.commitment == r["commitment"]
            and same_result_after_problem_link(
                c, context, value, r["aggregateVersion"], problem.resource_id
            )
            and value.profile_revision_id == r["profileRevision"]
            and value.snapshot is not None
            and value.snapshot.profile_digest == r["profileDigest"]
            and value.input_source == r["inputSource"],
            "RESULT_CHANGED",
        )
        self._reads(c, context, (read_grant(value),), now, history=history)
        chain = (
            read_chain(
                c,
                context,
                value.invocation_id,
                lambda conn, ctx, original, actual: self._reads(
                    conn,
                    ctx,
                    (read_grant(original), read_grant(actual)),
                    now,
                    history=history,
                ),
            )
            if r["ancestryDigests"]
            else ()
        )
        require(
            [item["digest"] for item in chain] == r["ancestryDigests"],
            "ANCESTRY_CHANGED",
        )
        contexts = {
            value.context_id,
            *(item["target"]["original_context_id"] for item in chain),
        }
        original_id = (
            chain[-1]["target"]["original_context_id"] if chain else value.context_id
        )
        frozen = r.get("understandingBindings")
        require(
            isinstance(frozen, list)
            and len(frozen) == len(contexts)
            and all(
                isinstance(item, dict) and isinstance(item.get("contextId"), str)
                for item in frozen
            ),
            "CONTEXT_BINDING_CHANGED",
        )
        bindings = {item["contextId"]: item for item in frozen}
        require(set(bindings) == contexts, "CONTEXT_BINDING_CHANGED")
        for identity in sorted(contexts):
            row = request_row(c, identity)
            require(
                row is not None
                and row["subject_id"] == p.subjectId
                and (row["tenant_id"], row["security_domain"])
                == (p.tenantId, p.securityDomain)
                and row["record"].get("conversation_id") == r["conversationId"]
                and row["record"].get("account_id") == p.accountId
                and row["record"].get("budget_allowance_id") == p.allowanceId
                and row["record"].get("experience_policy_digest") == p.rootPolicyDigest
                and context_binding(row) == bindings[identity]
                and (
                    row["record"].get("owned_understanding_policy_digest")
                    == p.rootUnderstandingPolicyDigest
                    if identity == original_id
                    else bool(row["record"].get("owned_understanding_policy_digest"))
                ),
                "CONTEXT_BINDING_CHANGED",
            )
            require(
                (row["record"].get("question_only") is not True)
                if identity == original_id
                else row["record"].get("question_only") is True,
                "CONTEXT_BINDING_CHANGED",
            )
            if not history:
                from .conversation_planning_admission import require_resolved_source

                require_resolved_source(c, row)
            require(
                not c.execute(
                    "SELECT 1 FROM authorization_admin.context_call_decisions d JOIN "
                    "authorization_admin.context_call_revocations r "
                    "USING(admission_id) "
                    "WHERE d.context_id=%s",
                    (identity,),
                ).fetchone(),
                "CONTEXT_REVOKED",
            )
        conversation = c.execute(
            "SELECT owner_id,archived_at FROM private_conversation.conversations "
            "WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s",
            (p.tenantId, p.securityDomain, r["conversationId"]),
        ).fetchone()
        require(
            conversation is not None
            and conversation["owner_id"] == p.subjectId
            and conversation["archived_at"] is None,
            "CONVERSATION_DENIED",
        )
        self._reads(
            c,
            context,
            (
                ExactGrant(
                    "KNOWLEDGE",
                    "READ_RESOURCE",
                    reference(
                        "knowledge",
                        selected.source.resource_id,
                        selected.source.revision_id,
                    ),
                ),
            ),
            now,
            history=history,
        )
        content, _ = read_published(
            c, ScopeIdentity(p.tenantId, p.securityDomain), "KNOWLEDGE", selected.source
        )
        self.policy.validate_source(r["inputSource"], content)
        actual = c.execute(
            "SELECT p.owner_id,p.current_revision_id,r.digest FROM "
            "business_problem_authority.problems p JOIN "
            "business_problem_authority.problem_revisions r ON r.namespace=p.namespace "
            "AND r.security_domain=p.security_domain "
            "AND r.revision_id=p.current_revision_id "
            "WHERE p.namespace=%s AND p.security_domain=%s "
            "AND p.business_problem_id=%s",
            (p.tenantId, p.securityDomain, problem.resource_id),
        ).fetchone()
        require(
            actual
            == dict(
                owner_id=p.subjectId,
                current_revision_id=problem.revision_id,
                digest=problem.digest,
            ),
            "PROBLEM_VERSION_CHANGED",
        )
        expiry = min(p.expiresAt, datetime.fromisoformat(r["expiresAt"]))
        require(history or now < expiry, "EXPIRED")
        result = OwnedBusinessBinding(
            stored["admission_id"],
            stored["record_digest"],
            p.digest,
            self.generation,
            p.tenantId,
            p.securityDomain,
            p.subjectId,
            selected,
            problem,
            expiry,
            history,
        )

        if _apply_correction:
            from .ontology_action_correction import project

            return project(self, c, context, result)
        return result
