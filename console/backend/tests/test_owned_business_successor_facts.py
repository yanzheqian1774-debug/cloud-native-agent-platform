"""Typed immutable receipt parsing, not a simulated permission/admission owner."""

from copy import deepcopy
from types import SimpleNamespace as NS

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.owned_business_admission_successor import PREFIX, SCHEMA, read_exact
from agent_console.resource_use_domain import canonical_digest


class Facts:
    def __init__(self, fact, old, *, revoked=False, context_revoked=False):
        self.fact, self.old = fact, old
        self.revoked, self.context_revoked = revoked, context_revoked
        self.reads = []

    def execute(self, sql, args=None):
        self.reads.append((sql, args))
        row = None
        if "to_regclass" in sql:
            row = {"name": None}
        elif "FROM execution_authority.resource_policy_plan_commands" in sql:
            if args == ("tenant", "domain", "actor", self.fact["identity"]):
                row = {
                    "record": self.fact,
                    "payload_digest": canonical_digest(self.fact),
                }
        elif "FROM authorization_admin.owned_business_admissions" in sql:
            if args == ("owned-business:original", "tenant", "domain", "actor"):
                row = self.old
        elif "FROM authorization_admin.owned_business_revocations" in sql:
            row = {"exists": 1} if self.revoked else None
        elif "context_call_revocations" in sql:
            row = {"exists": 1} if self.context_revoked else None
        else:
            assert sql.startswith("SELECT pg_advisory_xact_lock"), sql
        return NS(fetchone=lambda: row)


@pytest.fixture
def facts():
    record = {
        "schemaVersion": "owned-business-admission.v1",
        "subject": "actor",
        "tenantId": "tenant",
        "securityDomain": "domain",
        "invocationId": "real-invocation",
        "accountId": "same-account",
        "inputSource": {
            "source": "same-exact-source",
            "sourceContentDigest": "same-digest",
        },
        "contextId": "original-context",
        "policyDigest": "old",
        "scope": {"source": "same-source"},
        "expiresAt": "2026-11-28T00:00:00+00:00",
        "ledgerId": "same-ledger",
        "allowanceId": "same-allowance",
        "generation": 36,
        "understandingBindings": [
            {"contextId": "original-context", "configuration": {"calls": 200}}
        ],
    }
    old = {
        "admission_id": "owned-business:original",
        "record": deepcopy(record),
        "record_digest": canonical_digest(record),
    }
    record.update(policyDigest="current", expiresAt="2026-11-29T00:00:00+00:00")
    record["scope"]["trustedAssemblyAdoption"] = "SAME_SCOPE_SELECTED_V1"
    basis = {"previousAdmissionId": old["admission_id"], "selectionKey": "explicit"}
    fact = {
        "schemaVersion": SCHEMA,
        "identityBasis": basis,
        "identity": PREFIX + canonical_digest(basis),
        "admission": record,
        "recordDigest": canonical_digest(record),
        "previous": {
            "admissionId": old["admission_id"],
            "recordDigest": old["record_digest"],
        },
        "revocationMode": "ORIGINAL_CONTEXT_LINEAGE",
    }
    return fact, old


def test_exact_typed_fact_keeps_original_identity_and_has_no_write(facts):
    fact, old = facts
    c = Facts(fact, old)
    result = read_exact(c, fact["identity"], "tenant", "domain", "actor")
    assert result["record"]["invocationId"] == old["record"]["invocationId"]
    assert (
        result["record"]["understandingBindings"]
        == old["record"]["understandingBindings"]
    )
    assert all(sql.startswith("SELECT") for sql, _ in c.reads)


@pytest.mark.parametrize(
    "field,value",
    [
        ("accountId", "different-account"),
        (
            "inputSource",
            {"source": "different-source", "sourceContentDigest": "same-digest"},
        ),
        ("ledgerId", "new-ledger"),
        ("allowanceId", "new-allowance"),
        ("generation", 37),
        ("invocationId", "invented-invocation"),
        ("contextId", "other-goal"),
        (
            "understandingBindings",
            [{"contextId": "original-context", "configuration": {"calls": 201}}],
        ),
    ],
)
def test_even_rehashed_fact_cannot_change_origin_or_budget(facts, field, value):
    fact, old = facts
    fact["admission"][field] = value
    fact["recordDigest"] = canonical_digest(fact["admission"])
    with pytest.raises(AuthorityError, match="ORIGIN_CHANGED"):
        read_exact(Facts(fact, old), fact["identity"], "tenant", "domain", "actor")


@pytest.mark.parametrize(
    "fault",
    [
        "wrong_actor",
        "wrong_digest",
        "missing_field",
        "wrong_type",
        "root_revoked",
        "context_revoked",
    ],
)
def test_typed_fact_is_not_a_generic_historical_bypass(facts, fault):
    fact, old = facts
    actor = "other" if fault == "wrong_actor" else "actor"
    if fault == "wrong_digest":
        fact["recordDigest"] = "0" * 64
    if fault == "missing_field":
        del fact["identityBasis"]
    if fault == "wrong_type":
        fact["schemaVersion"] = "owned-business-admission.v1"
    with pytest.raises(AuthorityError):
        read_exact(
            Facts(
                fact,
                old,
                revoked=fault == "root_revoked",
                context_revoked=fault == "context_revoked",
            ),
            fact["identity"],
            "tenant",
            "domain",
            actor,
        )
