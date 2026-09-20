"""Persistent task-scoped reservation ledger for real Draft provider calls."""

from __future__ import annotations

import hashlib
import json
import math
from contextlib import contextmanager
from pathlib import Path

from psycopg import Error as PsycopgError
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from agent_console.draft_assistance import (
    DraftAssistanceError,
    DraftAssistanceProfileRevision,
    DraftInvocation,
    ProviderBudgetQuote,
    ProviderObservation,
)

ADAPTER = "draft-provider-budget-postgresql-v1"
MIGRATION_VERSION = 24


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class PostgresProviderCallBudget:
    def __init__(
        self,
        database_url: str,
        *,
        migration_path: Path,
        profile: DraftAssistanceProfileRevision,
        ledger_id: str,
        call_cap: int,
        total_cost_cap_microusd: int,
        input_price_microusd_per_million_tokens: int,
        output_price_microusd_per_million_tokens: int,
        timeout: float = 5.0,
    ) -> None:
        if (
            not database_url
            or not ledger_id
            or call_cap < 1
            or total_cost_cap_microusd < 1
            or input_price_microusd_per_million_tokens < 0
            or output_price_microusd_per_million_tokens < 0
        ):
            raise DraftAssistanceError("PROVIDER_BUDGET_PROFILE_INVALID")
        self.migration_path = migration_path
        self.profile = profile
        self.ledger_id = ledger_id
        self.call_cap = call_cap
        self.total_cost_cap_microusd = total_cost_cap_microusd
        self.input_price = input_price_microusd_per_million_tokens
        self.output_price = output_price_microusd_per_million_tokens
        self.pool = ConnectionPool(
            database_url,
            min_size=1,
            max_size=4,
            timeout=timeout,
            kwargs={"row_factory": dict_row, "autocommit": False},
            open=True,
        )
        self.pool.wait(timeout=timeout)

    @contextmanager
    def _connection(self):
        with self.pool.connection() as connection, connection.transaction():
            yield connection

    @property
    def migration_checksum(self) -> str:
        return hashlib.sha256(self.migration_path.read_bytes()).hexdigest()

    def migrate_and_configure(self) -> None:
        if not self.migration_path.name.startswith("0024_"):
            raise DraftAssistanceError("PROVIDER_BUDGET_SCHEMA_INCOMPATIBLE")
        policy = {
            "schemaVersion": "draft-provider-budget-policy.v1",
            "ledgerId": self.ledger_id,
            "scope": [self.profile.scope.namespace, self.profile.scope.security_domain],
            "profileRevisionId": self.profile.profile_revision_id,
            "profileDigest": self.profile.profile_digest,
            "currency": "USD",
            "callCap": self.call_cap,
            "totalCostCapMicrousd": self.total_cost_cap_microusd,
            "inputPriceMicrousdPerMillionTokens": self.input_price,
            "outputPriceMicrousdPerMillionTokens": self.output_price,
            "limitation": "TASK_SCOPED_ACCEPTANCE_GUARD_NOT_ACCOUNT_BILLING",
        }
        try:
            with self._connection() as connection:
                connection.execute("SET LOCAL statement_timeout='30s'")
                connection.execute("SET LOCAL lock_timeout='3s'")
                connection.execute(self.migration_path.read_text())
                row = connection.execute(
                    "SELECT checksum,adapter FROM "
                    "draft_provider_budget.schema_migrations WHERE version=%s",
                    (MIGRATION_VERSION,),
                ).fetchone()
                expected = {"checksum": self.migration_checksum, "adapter": ADAPTER}
                if row is None:
                    connection.execute(
                        "INSERT INTO draft_provider_budget.schema_migrations"
                        "(version,checksum,adapter) VALUES(%s,%s,%s)",
                        (MIGRATION_VERSION, self.migration_checksum, ADAPTER),
                    )
                elif row != expected:
                    raise DraftAssistanceError("PROVIDER_BUDGET_SCHEMA_INCOMPATIBLE")
                inserted = connection.execute(
                    "INSERT INTO draft_provider_budget.policies"
                    "(namespace,security_domain,ledger_id,profile_revision_id,"
                    "profile_digest,currency,call_cap,total_cost_cap_microusd,"
                    "input_price_microusd_per_million_tokens,"
                    "output_price_microusd_per_million_tokens,record) "
                    "VALUES(%s,%s,%s,%s,%s,'USD',%s,%s,%s,%s,%s) "
                    "ON CONFLICT DO NOTHING RETURNING ledger_id",
                    (
                        self.profile.scope.namespace,
                        self.profile.scope.security_domain,
                        self.ledger_id,
                        self.profile.profile_revision_id,
                        self.profile.profile_digest,
                        self.call_cap,
                        self.total_cost_cap_microusd,
                        self.input_price,
                        self.output_price,
                        Jsonb(policy),
                    ),
                ).fetchone()
                if inserted is None:
                    existing = connection.execute(
                        "SELECT record FROM draft_provider_budget.policies "
                        "WHERE namespace=%s AND security_domain=%s AND ledger_id=%s",
                        (
                            self.profile.scope.namespace,
                            self.profile.scope.security_domain,
                            self.ledger_id,
                        ),
                    ).fetchone()
                    if existing is None or existing["record"] != policy:
                        raise DraftAssistanceError("PROVIDER_BUDGET_PROFILE_CONFLICT")
        except DraftAssistanceError:
            raise
        except (OSError, PsycopgError) as exc:
            raise DraftAssistanceError("PROVIDER_BUDGET_STORAGE_UNAVAILABLE") from exc

    @contextmanager
    def dispatch_guard(self, invocation, quote):
        """Pin admission; revocation does not cancel an admitted call."""
        from .task_delegation import guard_budget

        with self._connection() as connection:
            guard_budget(connection, self, invocation, quote)
            yield

    def reserve(
        self,
        operation_id: str,
        invocation: DraftInvocation,
        quote: ProviderBudgetQuote,
    ) -> str:
        if (
            invocation.scope != self.profile.scope
            or invocation.profile_revision_id != self.profile.profile_revision_id
            or quote.output_token_ceiling != self.profile.maximum_output_tokens
            or quote.worst_case_cost_microusd
            != self._cost(quote.input_token_upper_bound, self.input_price)
            + self._cost(quote.output_token_ceiling, self.output_price)
        ):
            raise DraftAssistanceError("PROVIDER_BUDGET_QUOTE_INVALID")
        reservation_digest = hashlib.sha256(
            invocation.invocation_id.encode()
        ).hexdigest()
        reservation_id = f"provider-budget-reservation:{reservation_digest}"
        payload = {
            "invocationId": invocation.invocation_id,
            "inputTokenUpperBound": quote.input_token_upper_bound,
            "outputTokenCeiling": quote.output_token_ceiling,
            "worstCaseCostMicrousd": quote.worst_case_cost_microusd,
        }
        payload_digest = _digest(payload)
        scope = (
            invocation.scope.namespace,
            invocation.scope.security_domain,
            self.ledger_id,
        )
        try:
            with self._connection() as connection:
                from .task_delegation import guard_budget

                guard_budget(connection, self, invocation, quote)
                policy = connection.execute(
                    "SELECT call_cap,total_cost_cap_microusd "
                    "FROM draft_provider_budget.policies WHERE namespace=%s "
                    "AND security_domain=%s AND ledger_id=%s FOR UPDATE",
                    scope,
                ).fetchone()
                if policy is None:
                    raise DraftAssistanceError("PROVIDER_BUDGET_PROFILE_INVALID")
                existing = connection.execute(
                    "SELECT reservation_id,payload_digest "
                    "FROM draft_provider_budget.reservations WHERE namespace=%s "
                    "AND security_domain=%s AND ledger_id=%s AND operation_id=%s",
                    (*scope, operation_id),
                ).fetchone()
                if existing is not None:
                    if existing != {
                        "reservation_id": reservation_id,
                        "payload_digest": payload_digest,
                    }:
                        raise DraftAssistanceError("PROVIDER_BUDGET_OPERATION_CONFLICT")
                    return reservation_id
                totals = connection.execute(
                    "SELECT count(*) AS calls,"
                    "COALESCE(sum(COALESCE(s.actual_cost_microusd,"
                    "r.worst_case_cost_microusd)),0) AS cost "
                    "FROM draft_provider_budget.reservations r "
                    "LEFT JOIN draft_provider_budget.settlements s "
                    "USING(namespace,security_domain,ledger_id,reservation_id) "
                    "WHERE r.namespace=%s AND r.security_domain=%s "
                    "AND r.ledger_id=%s",
                    scope,
                ).fetchone()
                if (
                    totals["calls"] + 1 > policy["call_cap"]
                    or totals["cost"] + quote.worst_case_cost_microusd
                    > policy["total_cost_cap_microusd"]
                ):
                    raise DraftAssistanceError("PROVIDER_BUDGET_EXHAUSTED")
                connection.execute(
                    "INSERT INTO draft_provider_budget.reservations"
                    "(namespace,security_domain,ledger_id,reservation_id,"
                    "operation_id,invocation_id,input_token_upper_bound,"
                    "output_token_ceiling,worst_case_cost_microusd,payload_digest) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        *scope,
                        reservation_id,
                        operation_id,
                        invocation.invocation_id,
                        quote.input_token_upper_bound,
                        quote.output_token_ceiling,
                        quote.worst_case_cost_microusd,
                        payload_digest,
                    ),
                )
                return reservation_id
        except DraftAssistanceError:
            raise
        except PsycopgError as exc:
            raise DraftAssistanceError("PROVIDER_BUDGET_STORAGE_UNAVAILABLE") from exc

    @staticmethod
    def _cost(tokens: int, price: int) -> int:
        return math.ceil(tokens * price / 1_000_000)

    def record_usage(
        self,
        operation_id: str,
        reservation_id: str,
        observation: ProviderObservation,
    ) -> None:
        if observation.input_tokens is None or observation.output_tokens is None:
            return
        if observation.input_tokens < 1 or observation.output_tokens < 0:
            return
        scope = (
            self.profile.scope.namespace,
            self.profile.scope.security_domain,
            self.ledger_id,
        )
        try:
            with self._connection() as connection:
                reservation = connection.execute(
                    "SELECT input_token_upper_bound,output_token_ceiling,"
                    "worst_case_cost_microusd "
                    "FROM draft_provider_budget.reservations WHERE namespace=%s "
                    "AND security_domain=%s AND ledger_id=%s AND reservation_id=%s",
                    (*scope, reservation_id),
                ).fetchone()
                if reservation is None:
                    raise DraftAssistanceError("PROVIDER_BUDGET_RESERVATION_NOT_FOUND")
                if (
                    observation.input_tokens > reservation["input_token_upper_bound"]
                    or observation.output_tokens > reservation["output_token_ceiling"]
                ):
                    return
                actual_cost = self._cost(
                    observation.input_tokens, self.input_price
                ) + self._cost(observation.output_tokens, self.output_price)
                if actual_cost > reservation["worst_case_cost_microusd"]:
                    return
                payload = {
                    "observationId": observation.observation_id,
                    "inputTokens": observation.input_tokens,
                    "outputTokens": observation.output_tokens,
                    "actualCostMicrousd": actual_cost,
                }
                payload_digest = _digest(payload)
                inserted = connection.execute(
                    "INSERT INTO draft_provider_budget.settlements"
                    "(namespace,security_domain,ledger_id,reservation_id,"
                    "operation_id,observation_id,input_tokens,output_tokens,"
                    "actual_cost_microusd,payload_digest) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT DO NOTHING RETURNING reservation_id",
                    (
                        *scope,
                        reservation_id,
                        operation_id,
                        observation.observation_id,
                        observation.input_tokens,
                        observation.output_tokens,
                        actual_cost,
                        payload_digest,
                    ),
                ).fetchone()
                if inserted is None:
                    existing = connection.execute(
                        "SELECT operation_id,payload_digest "
                        "FROM draft_provider_budget.settlements WHERE namespace=%s "
                        "AND security_domain=%s AND ledger_id=%s "
                        "AND reservation_id=%s",
                        (*scope, reservation_id),
                    ).fetchone()
                    if existing != {
                        "operation_id": operation_id,
                        "payload_digest": payload_digest,
                    }:
                        raise DraftAssistanceError(
                            "PROVIDER_BUDGET_SETTLEMENT_CONFLICT"
                        )
        except DraftAssistanceError:
            raise
        except PsycopgError as exc:
            raise DraftAssistanceError("PROVIDER_BUDGET_STORAGE_UNAVAILABLE") from exc

    def read_settlement(self, reservation_id):
        with self._connection() as connection:
            row = connection.execute(
                "SELECT input_tokens,output_tokens,actual_cost_microusd "
                "FROM draft_provider_budget.settlements WHERE namespace=%s "
                "AND security_domain=%s AND ledger_id=%s AND reservation_id=%s",
                (
                    self.profile.scope.namespace,
                    self.profile.scope.security_domain,
                    self.ledger_id,
                    reservation_id,
                ),
            ).fetchone()
        if row is None:
            return {"status": "PENDING_RECONCILIATION", "reservation_retained": True}
        return {
            "status": "ESTIMATE_SETTLED",
            "reservation_retained": False,
            "estimate_microusd": row["actual_cost_microusd"],
            "input_tokens": row["input_tokens"],
            "output_tokens": row["output_tokens"],
            "provider_invoice": "NOT_VERIFIED",
        }

    def pricing(self):
        from .business_problem_domain import canonical_digest

        owner = self
        document = {
            "ledger_id": owner.ledger_id,
            "profile_revision_id": owner.profile.profile_revision_id,
            "profile_digest": owner.profile.profile_digest,
            "currency": "USD",
            "unit": "MICROUSD_PER_MILLION_TOKENS",
            "input_price": owner.input_price,
            "output_price": owner.output_price,
            "calculation_version": "draft-provider-budget.v1.ceil-separate-totals",
            "cached_input_policy": "INCLUDED_AT_STANDARD_INPUT_RATE_NO_ADDITION",
            "classification": "TOKEN_COST_ESTIMATE_NOT_PROVIDER_INVOICE",
        }
        return {**document, "price_version_digest": canonical_digest(document)}

    def close(self) -> None:
        self.pool.close()
