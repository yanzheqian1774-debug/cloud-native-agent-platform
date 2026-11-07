# ruff: noqa: E501 -- Parameterized exact owner SQL.
"""Restrict existing Native worker and evaluator to admitted continuation receipts."""

from datetime import UTC, datetime

from .authority_contracts import AuthorityError
from .execution_preparation import ExecutionPreparationError
from .ontology_execution import parse_preparation
from .prepared_result_review import PreparedResultReview
from .readonly_continuation_policy import ReadonlyContinuationPolicy
from .workbench_business_problem import OwnerPrincipal


class ContinuationWork:
    def __init__(
        self, repository, policy, authority_factory, *, sales_v2_candidate=False
    ):
        self.repository, self.policy, self.authority_factory = (
            repository,
            policy,
            authority_factory,
        )

        self.sales_v2_candidate = sales_v2_candidate

    @classmethod
    def load(cls, repository, path, authority_factory, *, sales_v2_candidate=False):
        return cls(
            repository,
            ReadonlyContinuationPolicy.load(path),
            authority_factory,
            sales_v2_candidate=sales_v2_candidate,
        )

    def receipts(self):
        if not self.policy.enabled:
            return []
        with self.repository.pool.connection() as c:
            rows = c.execute(
                "SELECT namespace,security_domain,result FROM "
                "execution_authority.prepared_resource_commands "
                "WHERE result->>'schemaVersion'='readonly-continuation.v1'"
            ).fetchall()
        now = datetime.now(UTC)
        eligible = []
        for row in rows:
            r = row["result"]
            if r.get("executionAuthorizationDigest") != self.policy.digest:
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
            if len(matches) == 1:
                eligible.append((row["namespace"], row["security_domain"], r))
        return eligible

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
