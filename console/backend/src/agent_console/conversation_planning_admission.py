"""Planning continuation of an exact ordinary-account conversation admission.

Uses existing context decisions and preparations, never an administrator allowance.
This is call admission only: CRUD, plan and model grants remain independently required.
"""

from datetime import timedelta

from psycopg.types.json import Jsonb

from .authority_contracts import AuthorityError
from .context_call_admission import active, lock, request_row
from .conversation_experience_admission import LEDGER
from .conversation_planning_source import require_same_source
from .task_delegation import digest


class ConversationPlanningAdmission:
    def __init__(self, understanding, configuration):
        self.understanding = understanding
        self.experience = understanding.experience
        self.configuration = dict(configuration)
        if self.experience is None or (
            configuration["ledger_id"],
            configuration["calls"],
            configuration["cost_microusd"],
        ) != (
            LEDGER,
            self.experience.document.configuration.calls,
            self.experience.document.configuration.cost_microusd,
        ):
            raise AuthorityError("CONTEXT_ADMISSION_CONFIGURATION_MISMATCH")

    def require_source(self, service, c, context, problem):
        account, now, expires = self.experience._require(self.understanding, c, context)
        if service.configuration != self.configuration:
            raise AuthorityError("CONTEXT_ADMISSION_CONFIGURATION_MISMATCH")
        source = c.execute(
            "SELECT r.*,o.invocation_id AS source_invocation FROM "
            "authorization_admin.context_call_objects o JOIN "
            "authorization_admin.context_call_requests r USING(context_id) "
            "WHERE o.tenant_id=%s AND o.security_domain=%s "
            "AND o.owner='BUSINESS_PROBLEM' AND o.resource_id=%s",
            (context.scope.tenant_id, context.scope.security_domain, problem),
        ).fetchone()
        if not source or (
            source["subject_id"] != context.principal_id
            or source["record"].get("experience_policy_digest")
            != self.experience.policy_digest
            or source["record"].get("conversation_id")
            not in self.experience.document.conversations
        ):
            raise AuthorityError("CONTEXT_ADMISSION_CONVERSATION_BINDING_REQUIRED")
        decision = active(c, source, self.understanding.configuration)
        invocation = c.execute(
            "SELECT record FROM draft_assistance.invocation_versions WHERE "
            "namespace=%s AND security_domain=%s AND invocation_id=%s "
            "ORDER BY aggregate_version DESC LIMIT 1",
            (
                source["tenant_id"],
                source["security_domain"],
                source["source_invocation"],
            ),
        ).fetchone()
        value = invocation["record"] if invocation else {}
        if (
            value.get("state") != "SUCCEEDED"
            or value.get("resultKind") != "DRAFT_READY"
            or value.get("contextId") != source["context_id"]
            or value.get("initiatingPrincipalId") != context.principal_id
        ):
            raise AuthorityError("CONTEXT_ADMISSION_DRAFT_INVALID")
        require_resolved_source(c, source)
        source["understanding_input_source"] = value.get("inputSource")
        return source, account, now, min(expires, decision["expires_at"])

    def prepare(self, service, c, context, request, record):
        if not self.experience.matches(context):
            return None
        if (
            record["target"]["problem"]["problem"]["resource_id"]
            != request.target.problem.resource_id
        ):
            raise AuthorityError("CONTEXT_ADMISSION_SCOPE_DENIED")
        source, account, now, expires = self.require_source(
            service, c, context, request.target.problem.resource_id
        )
        saved_request = (
            record["request"]
            if "request" in record
            else request.model_dump(mode="json")
        )
        require_same_source(source["understanding_input_source"], saved_request)
        scope = (context.scope.tenant_id, context.scope.security_domain)
        key = (*scope, context.principal_id, request.idempotency_key)
        lock(c, "planning:" + digest(key))
        previous = c.execute(
            "SELECT * FROM authorization_admin.planning_call_preparations "
            "WHERE tenant_id=%s AND security_domain=%s "
            "AND subject_id=%s AND request_key=%s",
            key,
        ).fetchone()
        if previous:
            if previous["input_commitment"] != record["target"]["input_commitment"]:
                raise AuthorityError("IDEMPOTENCY_PAYLOAD_CONFLICT")
            row = request_row(c, previous["context_id"])
            self.require(service, c, context, row)
            return service._projection(c, row, previous["record"])
        from .conversation_planning_successor import successor

        identity, expires = successor(
            self, service, c, context, source, saved_request, record["target"], expires
        )
        payload = dict(
            task_id="F3-CONVERSATION-EXPERIENCE",
            phase="planning",
            synthetic_only=True,
            external_writes=False,
            context_id=identity,
            first_invocation_id=record["target"]["invocation_id"],
            source_context_id=source["context_id"],
            configuration=self.configuration,
            subject_id=context.principal_id,
            account_id=account["account_id"],
            account_revision=account["revision"],
            target=record["target"],
            experience_policy_digest=self.experience.policy_digest,
            conversation_id=source["record"]["conversation_id"],
            cumulative_call_cap=self.configuration["calls"],
            total_cost_cap_microusd=self.configuration["cost_microusd"],
            maximum_new_calls=1,
            understanding_input_source=source["understanding_input_source"],
            **(
                {
                    "budget_allowance_id": source["record"]["budget_allowance_id"],
                    "authorization_digest": source["record"]["authorization_digest"],
                }
                if source["record"].get("budget_allowance_id")
                else {}
            ),
        )
        c.execute(
            "INSERT INTO authorization_admin.context_call_requests "
            "(context_id,tenant_id,security_domain,subject_id,account_id,account_revision,"
            "first_invocation_id,record,digest) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                identity,
                *scope,
                context.principal_id,
                account["account_id"],
                account["revision"],
                record["target"]["invocation_id"],
                Jsonb(payload),
                digest(payload),
            ),
        )
        saved = {
            **record,
            "request": record["request"]
            if "request" in record
            else request.model_dump(mode="json"),
            "bounded_new_calls": 1,
        }
        c.execute(
            "INSERT INTO authorization_admin.planning_call_preparations "
            "VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (*key, identity, record["target"]["input_commitment"], Jsonb(saved)),
        )
        decision = {
            "type": "F3_CONVERSATION_PLANNING",
            "request": payload,
            "policy_digest": self.experience.policy_digest,
            "ledger_unchanged": True,
        }
        grants = service.delegation.grants
        c.execute(
            "INSERT INTO authorization_admin.context_call_decisions VALUES"
            "(%s,%s,1,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                "f3-planning:" + digest(identity),
                identity,
                "policy:f3-conversation-experience",
                context.principal_id,
                grants.generation.generation,
                grants.recovery_epoch,
                "f3:" + identity,
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
            reason="BOUNDED_SYNTHETIC_PLANNING",
            occurred_at=now,
            scope=context.scope,
            subject_id=identity,
            generation=grants.generation.generation,
            recovery_epoch=grants.recovery_epoch,
        )
        return service._projection(c, request_row(c, identity), saved)

    def require(self, service, c, context, row):
        source, _, _, _ = self.require_source(
            service,
            c,
            context,
            row["record"]["target"]["problem"]["problem"]["resource_id"],
        )
        if (
            row["subject_id"] != context.principal_id
            or row["record"].get("source_context_id") != source["context_id"]
            or row["record"].get("experience_policy_digest")
            != self.experience.policy_digest
        ):
            raise AuthorityError("CONTEXT_ADMISSION_SCOPE_DENIED")
        if (
            row["record"].get("understanding_input_source")
            != source["understanding_input_source"]
        ):
            raise AuthorityError("CONTEXT_ADMISSION_SOURCE_MISMATCH")
        active(c, row, self.configuration)
        from .conversation_planning_successor import validated_predecessor

        target = row["record"]["target"]
        validated_predecessor(self, service, c, context, source, target, target)


def require_resolved_source(c, source):
    """Unknowns block their original context, not unrelated conversations."""
    if c.execute(
        "SELECT 1 FROM draft_assistance.invocations i JOIN LATERAL "
        "(SELECT record FROM draft_assistance.invocation_versions v WHERE "
        "(v.namespace,v.security_domain,v.invocation_id)="
        "(i.namespace,i.security_domain,i.invocation_id) "
        "ORDER BY aggregate_version DESC LIMIT 1) v ON true "
        "WHERE i.namespace=%s AND i.security_domain=%s "
        "AND v.record->>'contextId'=%s AND "
        "(v.record->>'state' IN ('OUTCOME_UNKNOWN','CANCELLATION_REQUESTED') "
        "OR v.record->'localCleanup'->>'reason'='CLEANUP_FAILURE' "
        "OR EXISTS(SELECT 1 FROM draft_provider_budget.reservations r "
        "LEFT JOIN draft_provider_budget.settlements s "
        "USING(namespace,security_domain,ledger_id,reservation_id) "
        "WHERE r.namespace=i.namespace AND r.security_domain=i.security_domain "
        "AND r.invocation_id=i.invocation_id AND s.reservation_id IS NULL))",
        (source["tenant_id"], source["security_domain"], source["context_id"]),
    ).fetchone():
        raise AuthorityError("CONTEXT_ADMISSION_OUTCOME_UNKNOWN")


def limits(c, row, budget):
    configuration = row["record"]["configuration"]
    policy = c.execute(
        "SELECT call_cap,total_cost_cap_microusd FROM draft_provider_budget.policies "
        "WHERE namespace=%s AND security_domain=%s AND ledger_id=%s FOR SHARE",
        (row["tenant_id"], row["security_domain"], budget.ledger_id),
    ).fetchone()
    if (
        budget.ledger_id != LEDGER
        or configuration["ledger_id"] != LEDGER
        or policy != {"call_cap": 20, "total_cost_cap_microusd": 1_000_000}
    ):
        raise AuthorityError("CONTEXT_ADMISSION_BUDGET_MISMATCH")
    source = request_row(c, row["record"]["source_context_id"])
    if (
        not source
        or source["subject_id"] != row["subject_id"]
        or source["record"].get("experience_policy_digest")
        != row["record"]["experience_policy_digest"]
        or source["record"].get("budget_allowance_id")
        != row["record"].get("budget_allowance_id")
        or (
            source["record"].get("budget_allowance_id") is not None
            and source["record"].get("authorization_digest")
            != row["record"].get("authorization_digest")
        )
        or any(
            source["record"]["configuration"][key] != configuration[key]
            for key in ("ledger_id", "calls", "cost_microusd")
        )
    ):
        raise AuthorityError("CONTEXT_ADMISSION_SCOPE_DENIED")
    active(c, source, source["record"]["configuration"])
    from .provider_budget_allowance import experience_limits

    return experience_limits(c, row, budget)
