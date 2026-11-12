"""Explicit cumulative allowance on an existing ledger, never a fresh budget."""

from datetime import datetime, timedelta
from typing import Literal

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .draft_assistance import DraftAssistanceError
from .draft_provider_budget_postgres import _digest


class Allowance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: Literal["provider-budget-allowance.v1"]
    allowanceId: str = Field(min_length=1, max_length=200)
    ledgerId: str = Field(min_length=1, max_length=200)
    namespace: str
    securityDomain: str
    rootPolicyDigest: str = Field(pattern="^[a-f0-9]{64}$")
    authorizationDigest: str = Field(pattern="^[a-f0-9]{64}$")
    callCap: int = Field(ge=1, le=100)
    totalCostCapMicrousd: int = Field(ge=1, le=10_000_000)
    notBefore: datetime
    expiresAt: datetime
    externalWrites: Literal[False]

    @model_validator(mode="after")
    def bounded_window(self):
        if (
            self.notBefore.tzinfo is None
            or self.expiresAt.tzinfo is None
            or not timedelta(0) < self.expiresAt - self.notBefore <= timedelta(days=30)
        ):
            raise ValueError("fixed bounded window required")
        return self


def scope(owner):
    return (
        owner.profile.scope.namespace,
        owner.profile.scope.security_domain,
        owner.ledger_id,
    )


def prepare(owner, document):
    """Operator-only preparation; no HTTP route and no runtime activation."""
    value = Allowance.model_validate(document)
    with owner._connection() as c:
        path = owner.migration_path.parent / "0062_provider_budget_allowance.sql"
        from hashlib import sha256

        checksum = sha256(path.read_bytes()).hexdigest()
        c.execute("SELECT pg_advisory_xact_lock(3240062)")
        prior = c.execute(
            "SELECT checksum,adapter FROM draft_provider_budget.schema_migrations "
            "WHERE version=62"
        ).fetchone()
        expected = {"checksum": checksum, "adapter": "provider-budget-allowance-v1"}
        if prior and prior != expected:
            raise DraftAssistanceError("PROVIDER_ALLOWANCE_SCHEMA_INCOMPATIBLE")
        c.execute(path.read_text())
        if not prior:
            c.execute(
                "INSERT INTO draft_provider_budget.schema_migrations "
                "(version,checksum,adapter) VALUES(62,%s,%s)",
                (checksum, expected["adapter"]),
            )
        root = c.execute(
            "SELECT record FROM draft_provider_budget.policies WHERE namespace=%s "
            "AND security_domain=%s AND ledger_id=%s FOR UPDATE",
            scope(owner),
        ).fetchone()
        if (
            (value.namespace, value.securityDomain, value.ledgerId) != scope(owner)
            or not root
            or _digest(root["record"]) != value.rootPolicyDigest
        ):
            raise DraftAssistanceError("PROVIDER_ALLOWANCE_SCOPE_MISMATCH")
        record = value.model_dump(mode="json")
        c.execute(
            "INSERT INTO draft_provider_budget.allowances "
            "(namespace,security_domain,ledger_id,allowance_id,record,digest) "
            "VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (*scope(owner), value.allowanceId, Jsonb(record), _digest(record)),
        )
        saved = c.execute(
            "SELECT record,digest FROM draft_provider_budget.allowances "
            "WHERE namespace=%s "
            "AND security_domain=%s AND ledger_id=%s AND allowance_id=%s",
            (*scope(owner), value.allowanceId),
        ).fetchone()
        if saved != {"record": record, "digest": _digest(record)}:
            raise DraftAssistanceError("PROVIDER_ALLOWANCE_CONFLICT")
        return record


def require(c, owner):
    identity = getattr(owner, "allowance_id", None)
    if identity is None:
        return None
    if not c.execute(
        "SELECT to_regclass('draft_provider_budget.allowances') name"
    ).fetchone()["name"]:
        raise DraftAssistanceError("PROVIDER_ALLOWANCE_NOT_PREPARED")
    row = c.execute(
        "SELECT a.record,a.digest,p.record root,clock_timestamp() now "
        "FROM draft_provider_budget.allowances a JOIN draft_provider_budget.policies p "
        "USING(namespace,security_domain,ledger_id) WHERE a.namespace=%s "
        "AND a.security_domain=%s AND a.ledger_id=%s AND a.allowance_id=%s "
        "FOR SHARE OF a",
        (*scope(owner), identity),
    ).fetchone()
    if not row:
        raise DraftAssistanceError("PROVIDER_ALLOWANCE_NOT_PREPARED")
    try:
        value = Allowance.model_validate(row["record"])
    except ValueError as exc:
        raise DraftAssistanceError("PROVIDER_ALLOWANCE_INVALID") from exc
    if (
        row["digest"] != _digest(row["record"])
        or value.rootPolicyDigest != _digest(row["root"])
        or (value.namespace, value.securityDomain, value.ledgerId) != scope(owner)
        or value.allowanceId != identity
    ):
        raise DraftAssistanceError("PROVIDER_ALLOWANCE_SCOPE_MISMATCH")
    if not value.notBefore <= row["now"] < value.expiresAt:
        raise DraftAssistanceError("PROVIDER_ALLOWANCE_EXPIRED")
    return value


def require_context(
    c, namespace, domain, ledger, identity, authorization, configuration
):
    """Same immutable allowance, additionally bounded by the exact conversation."""
    from types import SimpleNamespace

    from .authority_contracts import AuthorityError

    owner = SimpleNamespace(
        allowance_id=identity,
        ledger_id=ledger,
        profile=SimpleNamespace(
            scope=SimpleNamespace(namespace=namespace, security_domain=domain)
        ),
    )
    try:
        value = require(c, owner)
    except DraftAssistanceError as exc:
        raise AuthorityError(str(exc)) from exc
    if (
        value is None
        or value.authorizationDigest != authorization
        or configuration["ledger_id"] != ledger
        or not 1 <= configuration["calls"] <= value.callCap
        or not 1 <= configuration["cost_microusd"] <= value.totalCostCapMicrousd
    ):
        raise AuthorityError("CONTEXT_ADMISSION_ALLOWANCE_MISMATCH")
    return value


def experience_limits(c, row, budget):
    from .authority_contracts import AuthorityError

    record = row["record"]
    configuration = record["configuration"]
    identity = record.get("budget_allowance_id")
    if identity != getattr(budget, "allowance_id", None):
        raise AuthorityError("CONTEXT_ADMISSION_ALLOWANCE_MISMATCH")
    if identity is not None:
        require_context(
            c,
            row["tenant_id"],
            row["security_domain"],
            budget.ledger_id,
            identity,
            record.get("authorization_digest"),
            configuration,
        )
    elif (configuration["calls"], configuration["cost_microusd"]) != (20, 1_000_000):
        raise AuthorityError("CONTEXT_ADMISSION_BUDGET_MISMATCH")
    return configuration["calls"], configuration["cost_microusd"]
