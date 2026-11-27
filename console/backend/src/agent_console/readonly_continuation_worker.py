# ruff: noqa: E501 -- Parameterized exact owner SQL.
"""Restrict existing Native worker and evaluator to admitted continuation receipts."""

from datetime import UTC, datetime

from . import owned_business_resource_adapter as owned_resources
from .authority_contracts import AuthorityError
from .execution_preparation import ExecutionPreparationError
from .ontology_execution import parse_preparation
from .prepared_result_review import PreparedResultReview
from .readonly_continuation_policy import ReadonlyContinuationPolicy
from .workbench_business_problem import OwnerPrincipal


class ContinuationWork:
    def __init__(
        self,
        repository,
        policy,
        authority_factory,
        *,
        sales_v2_candidate=False,
        owned_business=None,
        bound_service_execution=None,
    ):
        self.repository, self.policy, self.authority_factory = (
            repository,
            policy,
            authority_factory,
        )

        self.sales_v2_candidate = sales_v2_candidate
        self.owned_business = owned_business
        self.bound_service_execution = bound_service_execution
        self.exact_host_scope = None

    @classmethod
    def load(
        cls,
        repository,
        path,
        authority_factory,
        *,
        sales_v2_candidate=False,
        owned_business=None,
        bound_service_execution=None,
    ):
        return cls(
            repository,
            ReadonlyContinuationPolicy.load(path),
            authority_factory,
            sales_v2_candidate=sales_v2_candidate,
            owned_business=owned_business,
            bound_service_execution=bound_service_execution,
        )

    def receipts(self):
        if not self.policy.enabled:
            return []
        query = (
            "SELECT namespace,security_domain,result FROM "
            "execution_authority.prepared_resource_commands "
            "WHERE result->>'schemaVersion'='readonly-continuation.v1'"
        )
        parameters = ()
        if self.exact_host_scope is not None:
            ns, domain, principal, resources = self.exact_host_scope
            query += (
                " AND namespace=%s AND security_domain=%s AND actor_id=%s "
                "AND ('governed-execution:prepared:' || "
                "(result->>'preparationDigest'))=ANY(%s)"
            )
            parameters = (ns, domain, principal, list(resources))
        with self.repository.pool.connection() as c:
            rows = c.execute(query, parameters).fetchall()
        now = datetime.now(UTC)
        eligible = []
        for row in rows:
            r = row["result"]
            if self.exact_host_scope is not None:
                ns, domain, principal, resources = self.exact_host_scope
                if (row["namespace"], row["security_domain"], r.get("subject")) != (
                    ns,
                    domain,
                    principal,
                ) or (
                    "governed-execution:prepared:" + r.get("preparationDigest", "")
                ) not in resources:
                    continue
            if r.get("executionAuthorizationDigest") != self.policy.digest:
                continue
            if r.get("developmentJourney") is True:
                if (
                    r.get("subject") != "human:development-admin"
                    or datetime.fromisoformat(r["authorizationExpiresAt"]) <= now
                ):
                    continue
                with self.repository.pool.connection() as c:
                    command = c.execute(
                        "SELECT payload FROM execution_authority.native_dispatch_commands "
                        "WHERE namespace=%s AND security_domain=%s AND "
                        "payload->>'authorization_resource'=%s ORDER BY queued_at LIMIT 1",
                        (
                            row["namespace"],
                            row["security_domain"],
                            "governed-execution:prepared:" + r["preparationDigest"],
                        ),
                    ).fetchone()
                    if command is None:
                        continue
                    try:
                        context, authority = self.authority_factory(
                            c, self.repository._dispatch_command(command["payload"])
                        )
                        authority.require(
                            OwnerPrincipal(
                                context.principal_id,
                                row["namespace"],
                                row["security_domain"],
                            ),
                            "EXECUTION",
                            "READ",
                            "governed-execution:prepared:" + r["preparationDigest"],
                        )
                    except AuthorityError:
                        continue
                eligible.append((row["namespace"], row["security_domain"], r))
                continue
            if r.get("ownedBusiness") is not None:
                if self._owned_receipt(row, now):
                    eligible.append((row["namespace"], row["security_domain"], r))
                continue
            matches = [
                w
                for w in self.policy.works
                if (
                    w.namespace,
                    w.securityDomain,
                    w.subject,
                    w.problem.model_dump(mode="json"),
                )
                == (
                    row["namespace"],
                    row["security_domain"],
                    r["subject"],
                    r["executionPlan"]["plan"]["semantics"]["target"]["problem"],
                )
                and w.expiresAt.tzinfo is not None
                and w.expiresAt > now
                and r.get("sourceContentDigest") in w.sourceContentDigests
                and w.case == r.get("case")
                and w.nativeAgentName == r.get("nativeAgentName")
            ]
            if len(matches) == 1 and (
                self.bound_service_execution is None or self._service_receipt(row, now)
            ):
                eligible.append((row["namespace"], row["security_domain"], r))
        return eligible

    def _service_receipt(self, row, now):
        bridge = self.bound_service_execution
        if bridge is None:
            return False
        receipt = row["result"]
        try:
            bridge.require_scope(
                (row["namespace"], row["security_domain"], receipt["subject"])
            )
            if datetime.fromisoformat(receipt["authorizationExpiresAt"]) <= now:
                return False
            with self.repository.pool.connection() as c:
                saved = c.execute(
                    "SELECT payload FROM execution_authority.native_dispatch_commands "
                    "WHERE namespace=%s AND security_domain=%s AND principal_id=%s "
                    "AND authorization_resource=%s ORDER BY queued_at,command_id LIMIT 1",
                    (
                        row["namespace"],
                        row["security_domain"],
                        receipt["subject"],
                        "governed-execution:prepared:" + receipt["preparationDigest"],
                    ),
                ).fetchone()
                if saved is None:
                    return False
                command = self.repository._dispatch_command(saved["payload"])
                context, authority = self.authority_factory(c, command)
                bridge.authorize(c, context, command)
                if receipt.get("case") == "native_readonly":
                    from .execution_preparation_postgres import PreparedExecutionStore
                    from .plan_suggestion_domain import ExactReference
                    from .readonly_native_policy import require_preparation

                    selected = self.policy.work(
                        context,
                        ExactReference.model_validate(
                            receipt["executionPlan"]["plan"]["semantics"]["target"][
                                "problem"
                            ]
                        ),
                        receipt["sourceContentDigest"],
                        now,
                    )
                    prepared, _ = PreparedExecutionStore(c).read(
                        row["namespace"], row["security_domain"], receipt["runId"]
                    )
                    require_preparation(selected, prepared, receipt)
                authority.require(
                    OwnerPrincipal(
                        context.principal_id, row["namespace"], row["security_domain"]
                    ),
                    "EXECUTION",
                    "START",
                    "governed-execution:prepared:" + receipt["preparationDigest"],
                )
                return True
        except (AuthorityError, ValueError, ExecutionPreparationError):
            return False

    def _owned_receipt(self, row, now):
        if self.owned_business is None:
            return False
        receipt = row["result"]
        if datetime.fromisoformat(receipt["authorizationExpiresAt"]) <= now:
            return False
        with self.repository.pool.connection() as c:
            command = c.execute(
                "SELECT payload FROM execution_authority.native_dispatch_commands "
                "WHERE namespace=%s AND security_domain=%s AND "
                "payload->>'authorization_resource'=%s ORDER BY queued_at LIMIT 1",
                (
                    row["namespace"],
                    row["security_domain"],
                    "governed-execution:prepared:" + receipt["preparationDigest"],
                ),
            ).fetchone()
            if command is None:
                return False
            try:
                saved_command = self.repository._dispatch_command(command["payload"])
                context, authority = self.authority_factory(c, saved_command)
                if context.principal_id != receipt["subject"]:
                    return False
                if not owned_resources.authorize_dispatch(
                    self.owned_business, c, saved_command, context
                ):
                    return False
                principal = OwnerPrincipal(
                    context.principal_id, row["namespace"], row["security_domain"]
                )
                # Current grants remain the existing execution owner's responsibility.
                authority.require(
                    principal,
                    "EXECUTION",
                    "START",
                    "governed-execution:prepared:" + receipt["preparationDigest"],
                )
                return True
            except (AuthorityError, ValueError, ExecutionPreparationError):
                return False

    def dispatches(self):
        with self.repository.pool.connection() as c:
            active = {
                (r["namespace"], r["security_domain"], r["workflow_run_id"])
                for r in c.execute(
                    "SELECT namespace,security_domain,workflow_run_id FROM execution_authority.prepared_run_progress "
                    "WHERE record->>'state' IN ('PENDING','RUNNING')"
                ).fetchall()
            }
        return tuple(
            (namespace, domain, "governed-execution:prepared:" + r["preparationDigest"])
            for namespace, domain, r in self.receipts()
            if (namespace, domain, r["runId"]) in active
        )

    def evaluate_terminal(self):
        counts = {"evaluated": 0, "blocked": 0}
        for namespace, domain, receipt in self.receipts():
            with self.repository.pool.connection() as c, c.transaction():
                row = c.execute(
                    "SELECT p.record FROM execution_authority.run_preparations p "
                    "JOIN execution_authority.prepared_run_progress s "
                    "USING(namespace,security_domain,workflow_run_id) "
                    "WHERE p.namespace=%s AND p.security_domain=%s AND p.workflow_run_id=%s "
                    "AND s.record->>'state' IN ('SUCCEEDED','FAILED','CANCELLED') "
                    "AND NOT EXISTS (SELECT 1 FROM product_outcome.heads h "
                    "WHERE h.namespace=p.namespace AND h.security_domain=p.security_domain "
                    "AND h.workflow_run_id=p.workflow_run_id)",
                    (namespace, domain, receipt["runId"]),
                ).fetchone()
                if row is None:
                    continue
                p = parse_preparation(row["record"])
                if p.digest != receipt["preparationDigest"]:
                    raise ExecutionPreparationError(
                        "READONLY_WORKER_PREPARATION_MISMATCH"
                    )
                command = c.execute(
                    "SELECT payload FROM execution_authority.native_dispatch_commands "
                    "WHERE namespace=%s AND security_domain=%s "
                    "AND payload->>'authorization_resource'=%s ORDER BY queued_at LIMIT 1",
                    (namespace, domain, "governed-execution:prepared:" + p.digest),
                ).fetchone()
                if command is None:
                    continue
                try:
                    with c.transaction():
                        context, authority = self.authority_factory(
                            c, self.repository._dispatch_command(command["payload"])
                        )
                        principal = OwnerPrincipal(
                            context.principal_id, namespace, domain
                        )
                        PreparedResultReview(
                            c,
                            principal,
                            authority,
                            sales_v2_candidate=self.sales_v2_candidate,
                        ).evaluate(p, "readonly-terminal:" + p.digest)
                        counts["evaluated"] += 1
                except (AuthorityError, ExecutionPreparationError):
                    counts["blocked"] += 1
        return counts


class ContinuationDispatchRepository:
    """Atomic Native owner filtering; never claim another source's queued work."""

    def __init__(self, repository, work):
        self.repository, self.work = repository, work

    def __getattr__(self, name):
        return getattr(self.repository, name)

    def claim_next(self, worker_id, **kwargs):
        return self.repository.claim_next(
            worker_id, eligible_dispatches=self.work.dispatches(), **kwargs
        )
