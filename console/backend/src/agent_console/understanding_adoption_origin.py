"""Exact adopted business lineage guard; never enabled by the C1 profile.

This resolver may only be composed with the separately registered initial-adoption
profile and its current admission. It does not issue grants or change contexts.
"""

from .context_call_admission import active, request_row
from .conversation_planning_admission import require_resolved_source
from .draft_assistance import DraftInvocationState, DraftResultKind, DraftScope
from .draft_assistance_authorization import read_grant
from .draft_assistance_postgres import PostgresDraftAssistanceRepository
from .understanding_adoption_postgres import read_chain
from .understanding_result_adoption import require


class AdoptionOrigin:
    def __init__(self, root, routing, profile, *, enabled=False, retained=()):
        self.root, self.routing, self.profile = root, routing, profile
        self.enabled = enabled
        self.retained = tuple(retained)

    def for_result(self, invocation):
        matches = [
            candidate
            for candidate in (self, *self.retained)
            if invocation is not None
            and invocation.profile_revision_id == candidate.profile.profile_revision_id
            and invocation.snapshot is not None
            and invocation.snapshot.profile_digest == candidate.profile.profile_digest
        ]
        require(len(matches) == 1, "PROFILE_MISMATCH")
        return matches[0]

    def for_record(self, record):
        matches = [
            candidate
            for candidate in (self, *self.retained)
            if record.get("configuration") == candidate.routing.configuration
            and record.get("owned_understanding_policy_digest")
            == candidate.routing.experience.understanding_policy_digest
        ]
        require(len(matches) == 1, "CONFIGURATION_CHANGED")
        return matches[0]

    def business_source(self, connection, context, invocation_id):
        require(
            self.enabled is True
            and self.profile.adapter_revision
            in {
                "v3-relation-adoption",
                "v3-relation-adoption-source",
                "v3-relation-adoption-source-answers",
            }
            and self.routing.experience.root is self.root
            and self.routing.experience.routing_document.scopeMode
            == "EXISTING_WORK_AND_INITIAL_UNDERSTANDING",
            "BRIDGE_DISABLED",
        )
        root = self.root
        account, now, expires = root.experience._require(root, connection, context)
        self.routing.experience._require(self.routing, connection, context)
        observed = PostgresDraftAssistanceRepository._latest(
            connection, DraftScope.from_context(context), invocation_id
        )
        selected = self.for_result(observed)
        if selected is not self:
            return selected.business_source(connection, context, invocation_id)
        grants = root.delegation.grants

        def authorize(c, ctx, original, current):
            allowed = grants.authorization.has_current_grants(
                ctx,
                (read_grant(original), read_grant(current)),
                now=now,
                generation=grants.generation.generation,
                recovery_epoch=grants.recovery_epoch,
                connection=c,
                configure_transaction=False,
            )
            require(len(allowed) == 2 and all(allowed), "READ_DENIED")

        chain = read_chain(connection, context, invocation_id, authorize)
        require(bool(chain), "REFERENCE_REQUIRED")
        result = PostgresDraftAssistanceRepository._latest(
            connection, DraftScope.from_context(context), invocation_id
        )
        require(
            result is not None
            and result.state is DraftInvocationState.SUCCEEDED
            and result.result_kind is DraftResultKind.DRAFT_READY
            and result.profile_revision_id == self.profile.profile_revision_id
            and result.snapshot is not None
            and result.snapshot.profile_digest == self.profile.profile_digest,
            "RESULT_NOT_ADOPTABLE",
        )
        origin = request_row(connection, chain[-1]["target"]["original_context_id"])
        source = request_row(connection, result.context_id)
        require(origin is not None and source is not None, "CONTEXT_NOT_FOUND")
        require(
            origin["subject_id"] == source["subject_id"] == context.principal_id
            and not origin["record"].get("owned_understanding_policy_digest")
            and origin["record"].get("experience_policy_digest")
            == root.experience.policy_digest
            and origin["record"].get("conversation_id")
            in root.experience.document.conversations
            and source["record"].get("conversation_id")
            == origin["record"]["conversation_id"]
            == chain[0]["target"]["conversation_id"]
            and source["record"].get("question_only") is True
            and source["record"].get("owned_understanding_policy_digest")
            == self.routing.experience.understanding_policy_digest
            and source["record"].get("experience_policy_digest")
            == root.experience.policy_digest,
            "BUSINESS_SCOPE_DENIED",
        )
        for row, configuration in (
            (origin, root.configuration),
            (source, self.routing.configuration),
        ):
            require(
                row["record"]["configuration"] == configuration, "CONFIGURATION_CHANGED"
            )
            require(
                row["record"].get("budget_allowance_id")
                == root.experience.document.allowanceId
                and row["record"]["account_id"] == account["account_id"],
                "ALLOWANCE_CHANGED",
            )
            decision = active(connection, row, configuration)
            expires = min(expires, decision["expires_at"])
            require_resolved_source(connection, row)
        return source, account, now, expires
