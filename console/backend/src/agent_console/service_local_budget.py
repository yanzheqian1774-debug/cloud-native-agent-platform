# ruff: noqa: E501 -- Exact same-transaction owner SQL and scoped identities.
"""Opt-in sub-budget on the original ledger; provenance is verified by original owners."""

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .draft_assistance import DraftAssistanceError
from .draft_provider_budget_postgres import _digest
from .plan_suggestion_domain import ExactReference

ENV = "NATIVE_BOUND_SERVICE_LOCAL_BUDGET_POLICY"


def require(ok, reason):
    if not ok:
        raise DraftAssistanceError("SERVICE_LOCAL_BUDGET_" + reason)


class ServiceBudgetPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: Literal["service-local-budget.v1"]
    namespace: str = Field(min_length=1)
    securityDomain: str = Field(min_length=1)
    ledgerId: str = Field(min_length=1)
    subjectId: str = Field(pattern=r"^service:[A-Za-z0-9:._-]+$")
    credentialId: str = Field(min_length=1)
    work: ExactReference
    sourceBindingDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    servicePolicyDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    allowedEventIds: tuple[str, ...] = Field(min_length=1, max_length=128)
    expiresAt: datetime
    callCap: int = Field(strict=True, ge=1, le=20)
    totalCostCapMicrousd: int = Field(strict=True, ge=1, le=1_000_000)
    authorizationEvidenceDigest: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def bounded(self):
        require(
            self.expiresAt.tzinfo is not None
            and len(set(self.allowedEventIds)) == len(self.allowedEventIds),
            "POLICY_INVALID",
        )
        return self

    @property
    def scope_id(self):
        # Changing policy, event, expiry, evidence or cap cannot mint a new counter
        # for the same exact Service credential/work/source binding.
        return _digest(
            [
                self.namespace,
                self.securityDomain,
                self.ledgerId,
                self.subjectId,
                self.credentialId,
                self.work.model_dump(mode="json"),
                self.sourceBindingDigest,
            ]
        )

    def match(self, policy):
        from .fixed_work_bound_policy import BoundServicePlanningPolicy

        require(isinstance(policy, BoundServicePlanningPolicy), "BOUND_POLICY_REQUIRED")
        require(
            (
                policy.tenantId,
                policy.securityDomain,
                policy.ledgerId,
                policy.subjectId,
                policy.credentialId,
                policy.work,
            )
            == (
                self.namespace,
                self.securityDomain,
                self.ledgerId,
                self.subjectId,
                self.credentialId,
                self.work,
            )
            and getattr(policy, "sourceBindingDigest", None) == self.sourceBindingDigest
            and policy.digest == self.servicePolicyDigest
            and set(policy.allowedEventIds) == set(self.allowedEventIds)
            and self.expiresAt <= policy.expiresAt,
            "SERVICE_SCOPE_MISMATCH",
        )


@dataclass(frozen=True)
class NativeBudgetCall:
    command: object
    skill_invocation_id: str


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_POLICY_FIELD")
        result[key] = value
    return result


class Selection:
    def __init__(self, path):
        self.path = Path(path)
        self.raw = self._read()
        self.policy = ServiceBudgetPolicy.model_validate(
            json.loads(self.raw, object_pairs_hook=unique_object)
        )

    def _read(self):
        p = self.path
        require(
            p.is_absolute() and p.resolve() == p and not p.is_symlink() and p.is_file(),
            "PRIVATE_POLICY_REQUIRED",
        )
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            require(
                stat.S_ISREG(info.st_mode)
                and info.st_uid == os.getuid()
                and stat.S_IMODE(info.st_mode) == 0o600,
                "PRIVATE_POLICY_REQUIRED",
            )
            data = stream.read(1_048_577)
            after = p.lstat()
            require(
                len(data) <= 1_048_576
                and (after.st_dev, after.st_ino) == (info.st_dev, info.st_ino),
                "PRIVATE_POLICY_CHANGED",
            )
            return data

    def verify(self):
        require(self._read() == self.raw, "POLICY_CHANGED")
        return self.policy


def configure(owner, path):
    selection = Selection(path)
    p = selection.policy
    require(
        (p.namespace, p.securityDomain, p.ledgerId) == scope(owner), "LEDGER_MISMATCH"
    )
    owner.service_local_budget = selection


def configure_from_environment(owner, environment=None):
    environment = os.environ if environment is None else environment
    if environment.get(ENV):
        configure(owner, environment[ENV])


def scope(owner):
    return (
        owner.profile.scope.namespace,
        owner.profile.scope.security_domain,
        owner.ledger_id,
    )


def migrate(owner):
    """Explicit operator startup operation; never invoked by reserve/dispatch."""
    path = owner.migration_path.parent / "0080_service_local_budget.sql"
    expected = {
        "checksum": hashlib.sha256(path.read_bytes()).hexdigest(),
        "adapter": "service-local-budget-v1",
    }
    with owner._connection() as c:
        c.execute("SELECT pg_advisory_xact_lock(3240080)")
        old = c.execute(
            "SELECT checksum,adapter FROM draft_provider_budget.schema_migrations WHERE version=80"
        ).fetchone()
        require(old is None or old == expected, "SCHEMA_CONFLICT")
        if old is None:
            c.execute(path.read_text())
            c.execute(
                "INSERT INTO draft_provider_budget.schema_migrations VALUES(80,%s,%s)",
                (expected["checksum"], expected["adapter"]),
            )


def check_schema(c, owner):
    path = owner.migration_path.parent / "0080_service_local_budget.sql"
    expected = {
        "checksum": hashlib.sha256(path.read_bytes()).hexdigest(),
        "adapter": "service-local-budget-v1",
    }
    row = c.execute(
        "SELECT checksum,adapter FROM draft_provider_budget.schema_migrations WHERE version=80"
    ).fetchone()
    tables = c.execute(
        "SELECT to_regclass('draft_provider_budget.service_scopes') scopes,to_regclass('draft_provider_budget.service_reservations') reservations"
    ).fetchone()
    require(row == expected and all(tables.values()), "SCHEMA_REQUIRED")


def provenance(c, owner, invocation, quote):
    selection = getattr(owner, "service_local_budget", None)
    if selection is None:
        registry = getattr(owner, "service_planning_admission", None)
        bridge = getattr(owner, "service_budget_native_bridge", None)
        registry = registry or getattr(bridge, "registry", None)
        if (
            registry is not None
            and c.execute(
                "SELECT to_regclass('draft_provider_budget.service_scopes') name"
            ).fetchone()["name"]
            is not None
        ):
            policy = registry._policy()
            existing = c.execute(
                "SELECT 1 FROM draft_provider_budget.service_scopes WHERE namespace=%s AND security_domain=%s AND ledger_id=%s AND record->>'subjectId'=%s AND record->>'credentialId'=%s",
                (*scope(owner), policy.subjectId, policy.credentialId),
            ).fetchone()
            require(existing is None, "SELECTION_REQUIRED")
        return None
    p = selection.verify()
    check_schema(c, owner)
    require(
        scope(owner) == (p.namespace, p.securityDomain, p.ledgerId), "LEDGER_MISMATCH"
    )
    now = c.execute("SELECT clock_timestamp() now").fetchone()["now"]
    require(now < p.expiresAt, "EXPIRED")
    require(
        c.execute(
            "SELECT to_regclass('draft_provider_budget.service_scopes') name"
        ).fetchone()["name"]
        is not None,
        "SCHEMA_REQUIRED",
    )
    native = getattr(invocation, "service_budget_call", None)
    if native is None:
        registry = getattr(owner, "service_planning_admission", None)
        require(
            registry is not None and registry.guard(c, owner, invocation, quote),
            "PLANNING_PROOF_REQUIRED",
        )
        policy = registry._policy()
        p.match(policy)
        row = c.execute(
            "SELECT subject_id,credential_id,event_id,policy_digest,record_digest FROM fixed_work_service.planning_preparations WHERE namespace=%s AND security_domain=%s AND invocation_id=%s",
            (*scope(owner)[:2], invocation.invocation_id),
        ).fetchone()
        require(
            row is not None
            and row["subject_id"] == p.subjectId
            and row["credential_id"] == p.credentialId
            and row["event_id"] in p.allowedEventIds
            and row["policy_digest"] == p.servicePolicyDigest,
            "PLANNING_PROOF_REQUIRED",
        )
        proof = {
            "kind": "PLANNING",
            "eventId": row["event_id"],
            "recordDigest": row["record_digest"],
        }
    else:
        from .authority_contracts import (
            AuthenticationSource,
            AuthorityScope,
            TrustedRequestContext,
        )
        from .bound_service_execution import BoundServiceExecutionBridge

        bridge = getattr(owner, "service_budget_native_bridge", None)
        require(
            isinstance(native, NativeBudgetCall)
            and isinstance(bridge, BoundServiceExecutionBridge),
            "NATIVE_PROOF_REQUIRED",
        )
        policy = bridge.registry._policy()
        p.match(policy)
        command = native.command
        require(
            (command.principal_id, command.credential_id, command.authentication_source)
            == (p.subjectId, p.credentialId, "SERVICE_CREDENTIAL"),
            "NATIVE_IDENTITY_MISMATCH",
        )
        context = TrustedRequestContext(
            command.principal_id,
            AuthorityScope(p.namespace, p.securityDomain),
            command.credential_id,
            AuthenticationSource.SERVICE_CREDENTIAL,
            bridge.registry.authorization.generation.policy_version,
        )
        bound = bridge.authorize(c, context, command)
        require(
            bound.event_id in p.allowedEventIds
            and bound.binding_digest == p.sourceBindingDigest
            and bound.work_digest == p.work.digest,
            "NATIVE_BINDING_MISMATCH",
        )
        row = c.execute(
            "SELECT attempt_id FROM skill_invocation.invocations WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s",
            (*scope(owner)[:2], native.skill_invocation_id),
        ).fetchone()
        require(
            row is not None and row["attempt_id"] == str(command.attempt_id),
            "NATIVE_ATTEMPT_MISMATCH",
        )
        prefix = native.skill_invocation_id + ":"
        key = invocation.invocation_id
        tail = key[len(prefix) :] if key.startswith(prefix) else ""
        ordinal = tail.removesuffix(":MODEL")
        require(
            tail.endswith(":MODEL")
            and ordinal.isdigit()
            and str(int(ordinal)) == ordinal
            and 0 <= int(ordinal) < 8,
            "NATIVE_DECISION_KEY_INVALID",
        )
        journal = c.execute(
            "SELECT request_digest FROM skill_invocation.native_loop_records WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s AND record_key=%s",
            (*scope(owner)[:2], native.skill_invocation_id, key),
        ).fetchone()
        require(journal is not None, "NATIVE_JOURNAL_REQUIRED")
        proof = {
            "kind": "NATIVE",
            "eventId": bound.event_id,
            "attemptId": str(command.attempt_id),
            "skillInvocationId": native.skill_invocation_id,
            "journalDigest": journal["request_digest"],
            "receiptDigest": bound.receipt_digest,
        }
    require(
        owner.profile.profile_revision_id == policy.profileRevisionId
        and owner.profile.profile_digest == policy.profileDigest
        and 1 <= quote.input_token_upper_bound <= policy.maximumInputTokens
        and quote.output_token_ceiling <= policy.maximumOutputTokens,
        "PROFILE_OR_QUOTE_MISMATCH",
    )
    return p, {**proof, "scopeId": p.scope_id, "invocationId": invocation.invocation_id}


def register(c, owner, verified):
    if verified is None:
        return
    p, _ = verified
    value = p.model_dump(mode="json")
    c.execute(
        "INSERT INTO draft_provider_budget.service_scopes VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
        (*scope(owner), p.scope_id, Jsonb(value), _digest(value)),
    )
    saved = c.execute(
        "SELECT record,digest FROM draft_provider_budget.service_scopes WHERE namespace=%s AND security_domain=%s AND ledger_id=%s AND scope_id=%s",
        (*scope(owner), p.scope_id),
    ).fetchone()
    require(saved == {"record": value, "digest": _digest(value)}, "SCOPE_CONFLICT")


def check_existing(c, owner, reservation_id, verified):
    # An unselected owner cannot reuse a selected Service reservation either.
    exists = c.execute(
        "SELECT to_regclass('draft_provider_budget.service_reservations') name"
    ).fetchone()["name"]
    if exists is None:
        require(verified is None, "SCHEMA_REQUIRED")
        return
    row = c.execute(
        "SELECT scope_id,provenance,digest FROM draft_provider_budget.service_reservations WHERE namespace=%s AND security_domain=%s AND ledger_id=%s AND reservation_id=%s",
        (*scope(owner), reservation_id),
    ).fetchone()
    if verified is None:
        require(row is None, "SELECTION_REQUIRED")
        return
    p, proof = verified
    require(row is not None, "RESERVATION_PROOF_MISMATCH")
    value = p.model_dump(mode="json")
    registered = c.execute(
        "SELECT record,digest FROM draft_provider_budget.service_scopes WHERE namespace=%s AND security_domain=%s AND ledger_id=%s AND scope_id=%s",
        (*scope(owner), p.scope_id),
    ).fetchone()
    require(registered == {"record": value, "digest": _digest(value)}, "SCOPE_CONFLICT")
    require(
        row == {"scope_id": p.scope_id, "provenance": proof, "digest": _digest(proof)},
        "RESERVATION_PROOF_MISMATCH",
    )


def check_new(c, owner, verified, quote):
    if verified is None:
        return
    register(c, owner, verified)
    p, _ = verified
    totals = c.execute(
        "SELECT count(*) calls,coalesce(sum(coalesce(s.actual_cost_microusd,r.worst_case_cost_microusd)),0) cost FROM draft_provider_budget.service_reservations b JOIN draft_provider_budget.reservations r USING(namespace,security_domain,ledger_id,reservation_id) LEFT JOIN draft_provider_budget.settlements s USING(namespace,security_domain,ledger_id,reservation_id) WHERE b.namespace=%s AND b.security_domain=%s AND b.ledger_id=%s AND b.scope_id=%s",
        (*scope(owner), p.scope_id),
    ).fetchone()
    require(
        totals["calls"] + 1 <= p.callCap
        and totals["cost"] + quote.worst_case_cost_microusd <= p.totalCostCapMicrousd,
        "EXHAUSTED",
    )


def bind(c, owner, reservation_id, verified):
    if verified is not None:
        p, proof = verified
        c.execute(
            "INSERT INTO draft_provider_budget.service_reservations VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (*scope(owner), reservation_id, p.scope_id, Jsonb(proof), _digest(proof)),
        )


def dispatch(c, owner, invocation, quote):
    verified = provenance(c, owner, invocation, quote)
    reservation = (
        "provider-budget-reservation:"
        + hashlib.sha256(invocation.invocation_id.encode()).hexdigest()
    )
    check_existing(c, owner, reservation, verified)
