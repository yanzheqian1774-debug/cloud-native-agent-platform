"""Bounded business evidence for actual owned drafts; no model or execution calls."""

from .authority_contracts import AuthorityError, ExactGrant
from .context_call_admission import lock, request_row
from .conversation_planning_admission import require_resolved_source
from .draft_assistance import DraftInvocationState, DraftResultKind, DraftScope
from .draft_assistance_authorization import read_grant
from .draft_assistance_postgres import PostgresDraftAssistanceRepository
from .execution_domain import ScopeIdentity
from .owned_business_policy import OwnedBusinessPolicy
from .owned_business_postgres import append, context_binding, require_not_revoked, saved
from .owned_business_result_link import same_result_after_problem_link
from .owned_business_work_reader import OwnedBusinessWorkReader
from .plan_suggestion_domain import ExactReference
from .planning_candidates import read_published
from .understanding_adoption_postgres import read_chain
from .workbench_prepared_resources import reference


def require(condition, reason):
    if not condition:
        raise AuthorityError("OWNED_BUSINESS_" + reason)


class OwnedBusinessAdmission:
    def __init__(self, root, path):
        self.root, self.path = root, path
        self.policy = OwnedBusinessPolicy.load(path)
        self.grants = root.delegation.grants
        self.work_reader = OwnedBusinessWorkReader(
            path,
            self.grants.authorization,
            self.grants.generation.generation,
            self.grants.recovery_epoch,
        )

    def _policy(self, c, context):
        p = self.policy
        require(p.enabled and OwnedBusinessPolicy.load(self.path) == p, "DISABLED")
        require(
            (
                context.scope.tenant_id,
                context.scope.security_domain,
                context.principal_id,
            )
            == (p.tenantId, p.securityDomain, p.subjectId),
            "SCOPE_DENIED",
        )
        account, now, expires = self.root.experience._require(self.root, c, context)
        resolver = getattr(self.root, "understanding_adoption", None)
        require(
            resolver is not None
            and resolver.enabled
            and account["account_id"] == p.accountId
            and self.root.configuration["ledger_id"] == p.ledgerId
            and self.root.experience.document.allowanceId == p.allowanceId
            and self.root.experience.policy_digest == p.rootPolicyDigest
            and self.root.experience.understanding_policy_digest
            == p.rootUnderstandingPolicyDigest
            and resolver.routing.experience.understanding_policy_digest
            == p.adoptionPolicyDigest
            and now < p.expiresAt <= expires,
            "POLICY_BINDING_CHANGED",
        )
        return account, now, p.expiresAt

    def _configured_admissions(self):
        resolver = getattr(self.root, "understanding_adoption", None)
        return (
            self.root,
            *(
                (candidate.routing)
                for candidate in (resolver, *getattr(resolver, "retained", ()))
                if candidate is not None
            ),
        )

    def _context_admission(self, row):
        require(row is not None, "CONTEXT_NOT_FOUND")
        record = row["record"]
        matches = [
            candidate
            for candidate in self._configured_admissions()
            if record.get("configuration") == candidate.configuration
            and record.get("owned_understanding_policy_digest")
            == candidate.experience.understanding_policy_digest
        ]
        require(len(matches) == 1, "CONTEXT_BINDING_CHANGED")
        return matches[0]

    def supports(self, c, context, invocation_id):
        """Select only this opt-in lineage; selection itself is not admission."""
        value = PostgresDraftAssistanceRepository._latest(
            c, DraftScope.from_context(context), invocation_id
        )
        if value is None:
            return False
        row = request_row(c, value.context_id)
        if row is None:
            return False
        if row["record"].get("configuration") == self.root.configuration:
            return bool(row["record"].get("owned_understanding_policy_digest"))
        if not any(
            row["record"].get("configuration") == candidate.configuration
            for candidate in self._configured_admissions()[1:]
        ):
            return False
        _, now, _ = self._policy(c, context)
        chain = read_chain(
            c,
            context,
            invocation_id,
            lambda conn, ctx, original, actual: self._reads(
                conn, ctx, (original, actual), now
            ),
        )
        if not chain:
            return False
        origin = request_row(c, chain[-1]["target"]["original_context_id"])
        return bool(
            origin and origin["record"].get("owned_understanding_policy_digest")
        )

    def _reads(self, c, context, invocations, now):
        members = tuple(read_grant(v) for v in invocations)
        states = self.grants.authorization.has_current_grants(
            context,
            members,
            now=now,
            generation=self.grants.generation.generation,
            recovery_epoch=self.grants.recovery_epoch,
            connection=c,
            configure_transaction=False,
        )
        require(len(states) == len(members) and all(states), "READ_DENIED")

    def _source(self, c, context, invocation_id, *, history=False):
        evidence = self._source_evidence(c, context, invocation_id)
        value = evidence[4]
        selected = self.policy.selected(value.input_source)
        content, _ = read_published(
            c,
            ScopeIdentity(context.scope.tenant_id, context.scope.security_domain),
            "KNOWLEDGE",
            selected.source,
        )
        self.policy.validate_source(value.input_source, content)
        return (*evidence[:5], selected, evidence[5])

    def _source_evidence(self, c, context, invocation_id):
        """Current readable original result; does not grant future business use."""
        account, now, expires = self._policy(c, context)
        value = PostgresDraftAssistanceRepository._latest(
            c, DraftScope.from_context(context), invocation_id
        )
        require(
            value is not None
            and value.initiating_principal_id == context.principal_id
            and value.state is DraftInvocationState.SUCCEEDED
            and value.result_kind is DraftResultKind.DRAFT_READY,
            "READY_RESULT_REQUIRED",
        )
        row = request_row(c, value.context_id)
        require(row is not None, "CONTEXT_NOT_FOUND")
        conversation = row["record"].get("conversation_id")
        owned = c.execute(
            "SELECT owner_id,archived_at FROM private_conversation.conversations "
            "WHERE tenant_id=%s AND security_domain=%s "
            "AND conversation_id=%s FOR UPDATE",
            (context.scope.tenant_id, context.scope.security_domain, conversation),
        ).fetchone()
        require(
            owned is not None
            and owned["owner_id"] == context.principal_id
            and owned["archived_at"] is None,
            "CONVERSATION_DENIED",
        )
        selected_admission = self._context_admission(row)
        contexts = {value.context_id: selected_admission}
        ancestry = ()
        if selected_admission is not self.root:
            ancestry = read_chain(
                c,
                context,
                invocation_id,
                lambda conn, ctx, original, actual: self._reads(
                    conn, ctx, (original, actual), now
                ),
            )
            require(bool(ancestry), "ADOPTION_REFERENCE_REQUIRED")
            for item in ancestry:
                identity = item["target"]["original_context_id"]
                contexts[identity] = self._context_admission(request_row(c, identity))
            require(
                contexts[ancestry[-1]["target"]["original_context_id"]] is self.root,
                "OWNED_ORIGIN_REQUIRED",
            )
            require(
                value.profile_revision_id
                == selected_admission.configuration["profile_revision_id"]
                and value.snapshot is not None
                and value.snapshot.profile_digest
                == selected_admission.configuration["profile_digest"],
                "RESULT_PROFILE_CHANGED",
            )
        else:
            require(
                row["record"].get("configuration") == self.root.configuration
                and value.profile_revision_id
                == self.root.configuration["profile_revision_id"]
                and value.snapshot is not None
                and value.snapshot.profile_digest
                == self.root.configuration["profile_digest"],
                "RESULT_PROFILE_CHANGED",
            )
        self._reads(c, context, (value,), now)
        for identity in sorted(contexts):
            lock(c, identity)
            current = request_row(c, identity)
            admission = contexts[identity]
            require(current is not None, "CONTEXT_NOT_FOUND")
            record = current["record"]
            require(
                (
                    current["tenant_id"],
                    current["security_domain"],
                    current["subject_id"],
                )
                == (
                    context.scope.tenant_id,
                    context.scope.security_domain,
                    context.principal_id,
                )
                and record.get("conversation_id") == conversation
                and record.get("configuration") == admission.configuration
                and record.get("account_id") == account["account_id"]
                and record.get("budget_allowance_id") == self.policy.allowanceId,
                "CONTEXT_BINDING_CHANGED",
            )
            admission.experience._require(admission, c, context)
            admission.experience.require_record(c, context, current)
            # A completed model call is evidence, not an indefinitely renewable
            # execution lease. The separate current standing admission supplies
            # the future business window; explicit revocation still closes it.
            require(
                not c.execute(
                    "SELECT 1 FROM authorization_admin.context_call_decisions d "
                    "JOIN authorization_admin.context_call_revocations r "
                    "USING(admission_id) WHERE d.context_id=%s",
                    (identity,),
                ).fetchone(),
                "CONTEXT_REVOKED",
            )
            require_resolved_source(c, current)
        if ancestry:
            checked = read_chain(
                c,
                context,
                invocation_id,
                lambda conn, ctx, original, actual: self._reads(
                    conn, ctx, (original, actual), now
                ),
            )
            require(checked == ancestry, "ANCESTRY_CHANGED")
        origin_id = (
            ancestry[-1]["target"]["original_context_id"]
            if ancestry
            else value.context_id
        )
        origin = request_row(c, origin_id)
        require(
            origin["record"].get("owned_understanding_policy_digest")
            == self.root.experience.understanding_policy_digest
            and origin["record"].get("question_only") is not True,
            "OWNED_ORIGIN_REQUIRED",
        )
        require(value.input_source is not None, "SOURCE_REQUIRED")
        source_ref = ExactReference.model_validate(value.input_source["source"])
        grant = ExactGrant(
            "KNOWLEDGE",
            "READ_RESOURCE",
            reference("knowledge", source_ref.resource_id, source_ref.revision_id),
        )
        allowed = self.grants.authorization.has_current_grants(
            context,
            (grant,),
            now=now,
            generation=self.grants.generation.generation,
            recovery_epoch=self.grants.recovery_epoch,
            connection=c,
            configure_transaction=False,
        )
        require(len(allowed) == 1 and allowed[0], "SOURCE_READ_DENIED")
        content, _ = read_published(
            c,
            ScopeIdentity(context.scope.tenant_id, context.scope.security_domain),
            "KNOWLEDGE",
            source_ref,
        )
        from .resource_automation_policy import source_digest

        require(
            source_digest(content) == value.input_source.get("sourceContentDigest"),
            "SOURCE_CHANGED",
        )
        return row, account, now, expires, value, ancestry

    def admit(self, c, context, invocation_id):
        source, account, now, expires, value, selected, ancestry = self._source(
            c, context, invocation_id
        )
        previous = saved(c, context, invocation_id)
        bound_problem = c.execute(
            "SELECT invocation_id,resource_id FROM "
            "authorization_admin.context_call_objects "
            "WHERE context_id=%s AND owner='BUSINESS_PROBLEM'",
            (value.context_id,),
        ).fetchone()
        if bound_problem is not None:
            require(
                bound_problem["invocation_id"] == invocation_id,
                "BUSINESS_BINDING_CHANGED",
            )
        else:
            journey = c.execute(
                "SELECT version,state FROM private_conversation.journeys "
                "WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s",
                (
                    context.scope.tenant_id,
                    context.scope.security_domain,
                    source["record"]["conversation_id"],
                ),
            ).fetchone()
            state = journey["state"] if journey else {}
            require(
                state.get("phase") == "CREATE"
                and not state.get("problem")
                and (state.get("draft") or {}).get("invocationId") == invocation_id
                and (state.get("draft") or {}).get("inputSource") == value.input_source,
                "CURRENT_GOAL_CHANGED",
            )
        record = {
            "schemaVersion": "owned-business-admission.v1",
            "policyDigest": self.policy.digest,
            "scope": selected.model_dump(mode="json"),
            "subject": context.principal_id,
            "tenantId": context.scope.tenant_id,
            "securityDomain": context.scope.security_domain,
            "accountId": account["account_id"],
            "conversationId": source["record"]["conversation_id"],
            "contextId": value.context_id,
            "invocationId": value.invocation_id,
            "turnId": value.turn_id,
            "turnVersion": value.turn_version,
            "aggregateVersion": value.aggregate_version,
            "commitment": value.commitment,
            "profileRevision": value.profile_revision_id,
            "profileDigest": value.snapshot.profile_digest,
            "inputSource": value.input_source,
            "ancestryDigests": [r["digest"] for r in ancestry],
            "understandingBindings": [
                context_binding(request_row(c, identity))
                for identity in sorted(
                    {
                        value.context_id,
                        *(item["target"]["original_context_id"] for item in ancestry),
                    }
                )
            ],
            "ledgerId": self.policy.ledgerId,
            "allowanceId": self.policy.allowanceId,
            "generation": self.grants.generation.generation,
            "expiresAt": expires.isoformat(),
        }
        previous = saved(c, context, invocation_id)
        if previous:
            if value.aggregate_version != previous["record"]["aggregateVersion"]:
                require(
                    bound_problem is not None
                    and same_result_after_problem_link(
                        c,
                        context,
                        value,
                        previous["record"]["aggregateVersion"],
                        bound_problem["resource_id"],
                    ),
                    "RESULT_CHANGED",
                )
                record["aggregateVersion"] = previous["record"]["aggregateVersion"]
            require(previous["record"] == record, "ADMISSION_CHANGED")
        else:
            previous = append(c, context, record)
        require_not_revoked(c, previous["admission_id"])
        return source, account, now, expires

    def bound_source(self, c, context, problem_id):
        """Planning consumes an existing business fact, never creates one."""
        current = c.execute(
            "SELECT p.current_revision_id,r.digest FROM "
            "business_problem_authority.problems p JOIN "
            "business_problem_authority.problem_revisions r ON r.namespace=p.namespace "
            "AND r.security_domain=p.security_domain "
            "AND r.revision_id=p.current_revision_id "
            "WHERE p.namespace=%s AND p.security_domain=%s "
            "AND p.business_problem_id=%s",
            (context.scope.tenant_id, context.scope.security_domain, problem_id),
        ).fetchone()
        require(current is not None, "BUSINESS_BINDING_REQUIRED")
        exact = ExactReference(
            resource_id=problem_id,
            revision_id=current["current_revision_id"],
            digest=current["digest"],
        )
        binding = self.work(c, context, exact)
        stored = c.execute(
            "SELECT invocation_id FROM authorization_admin.owned_business_admissions "
            "WHERE admission_id=%s",
            (binding.admission_id,),
        ).fetchone()
        row, account, now, expires, value, _, _ = self._source(
            c, context, stored["invocation_id"]
        )
        row["understanding_input_source"] = value.input_source
        row["owned_business_admission_id"] = binding.admission_id
        row["owned_business_record_digest"] = binding.record_digest
        return row, account, now, min(expires, binding.expires_at)

    def work(self, c, context, problem, *, source_digest=None, history=False):
        return self.work_reader.work(
            c, context, problem, source_digest=source_digest, history=history
        )


def bind_created_object(owner, legacy):
    """Recheck the separate business basis inside the original creation UoW."""

    def bind(c, context, kind, result, **kwargs):
        invocation = kwargs.get("draft_invocation_id")
        if (
            kind == "BUSINESS_PROBLEM"
            and invocation
            and owner.supports(c, context, invocation)
        ):
            from .context_call_admission import bind_problem

            require(
                bind_problem(
                    c,
                    context,
                    result,
                    invocation,
                    retained_authorization=owner.admit,
                ),
                "BUSINESS_BINDING_REQUIRED",
            )
            return result
        return legacy(c, context, kind, result, **kwargs)

    return bind
