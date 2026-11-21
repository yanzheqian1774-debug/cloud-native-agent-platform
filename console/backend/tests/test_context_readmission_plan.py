import hashlib
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as N

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.context_call_admission import ContextApproval
from agent_console.context_readmission_plan import ReadmissionPlan, configured_plan
from agent_console.task_delegation import digest


def data(expired=False):
    now = datetime.now(UTC)
    config = {"ledger_id": "ledger", "calls": 100, "cost_microusd": 10000000}
    record = {
        "subject_id": "human:u",
        "account_id": "a",
        "account_revision": 1,
        "configuration": config,
    }
    row = {
        "context_id": "c",
        "subject_id": "human:u",
        "tenant_id": "t",
        "security_domain": "d",
        "account_id": "a",
        "account_revision": 1,
        "record": record,
        "digest": digest(record),
    }
    expiry = now + timedelta(hours=1)
    prior = {
        "admission_id": "old",
        "subject_id": "human:u",
        "expires_at": now - timedelta(seconds=1) if expired else expiry,
        "record": {"request": record, "request_digest": row["digest"]},
    }
    spec = ContextApproval(
        request_digest=row["digest"], expires_at=expiry, idempotency_key="k"
    )
    plan = ReadmissionPlan.model_validate(
        dict(
            schema_version="context-readmission.v1",
            issuer_id="admin",
            generation=2,
            recovery_epoch=1,
            authorization_evidence_digest="a" * 64,
            global_expires_at=expiry,
            entries=[
                dict(
                    context_id="c",
                    subject_id="human:u",
                    tenant_id="t",
                    security_domain="d",
                    request_digest=row["digest"],
                    configuration=config,
                    allowance_id="original",
                    allowance_authorization_digest="d" * 64,
                    prior_admission_id="old",
                    prior_record_digest=digest(prior["record"]),
                    idempotency_key="k",
                    expires_at=expiry,
                    lease_mode="EXPIRED_LEASE" if expired else "KEEP_EXPIRY",
                )
            ],
        )
    )
    service = N(
        configuration=config,
        delegation=N(grants=N(generation=N(generation=2), recovery_epoch=1)),
    )
    ctx = N(principal_id="admin")

    class Connection:
        revoked = False

        def execute(self, sql, args):
            if "local_accounts" in sql:
                return N(
                    fetchone=lambda: dict(
                        status="ENABLED",
                        revision=1,
                        principal_id="human:u",
                        tenant_id="t",
                        security_domain="d",
                    )
                )
            return N(fetchone=lambda: self.revoked if "revocations" in sql else prior)

    return plan, service, Connection(), ctx, row, spec, prior, now


@pytest.mark.parametrize("expired", [False, True])
def test_exact_lease_and_receipt(expired, monkeypatch):
    plan, service, c, ctx, row, spec, prior, now = data(expired)
    monkeypatch.setattr(
        "agent_console.provider_budget_allowance.require_context",
        lambda *a: N(expiresAt=plan.global_expires_at),
    )
    receipt = plan.require(service, c, ctx, row, spec, prior, None, now)
    assert receipt["authorizationEvidenceDigest"] == "a" * 64
    assert receipt["planDigest"] == digest(plan.model_dump(mode="json"))


@pytest.mark.parametrize(
    "change",
    ["generation", "revoke", "configuration", "request", "expiry", "prior", "issuer"],
)
def test_boundaries(change, monkeypatch):
    plan, service, c, ctx, row, spec, prior, now = data()
    monkeypatch.setattr(
        "agent_console.provider_budget_allowance.require_context",
        lambda *a: N(expiresAt=plan.global_expires_at),
    )
    if change == "generation":
        service.delegation.grants.generation.generation = 3
    elif change == "revoke":
        c.revoked = True
    elif change == "configuration":
        service.configuration = {"calls": 200}
    elif change == "request":
        row["record"] = {**row["record"], "extra": True}
    elif change == "expiry":
        spec = spec.model_copy(
            update={"expires_at": spec.expires_at + timedelta(seconds=1)}
        )
    elif change == "prior":
        prior = {**prior, "admission_id": "other"}
    else:
        ctx.principal_id = "other"
    with pytest.raises(AuthorityError):
        plan.require(service, c, ctx, row, spec, prior, None, now)


def test_expired_lease_is_not_available_for_live_prior(monkeypatch):
    plan, service, c, ctx, row, spec, prior, now = data(True)
    monkeypatch.setattr(
        "agent_console.provider_budget_allowance.require_context",
        lambda *a: N(expiresAt=plan.global_expires_at),
    )
    prior["expires_at"] = now + timedelta(seconds=1)
    with pytest.raises(AuthorityError, match="LEASE_INVALID"):
        plan.require(service, c, ctx, row, spec, prior, None, now)


def test_plan_exact_pin_permissions_symlink_and_defaultoff(tmp_path):
    assert configured_plan(None, None) is None
    plan, *_ = data()
    p = tmp_path / "plan.json"
    raw = plan.model_dump_json().encode()
    p.write_bytes(raw)
    p.chmod(0o600)
    pin = hashlib.sha256(raw).hexdigest()
    assert configured_plan(str(p), pin) == plan
    with pytest.raises(AuthorityError, match="PIN_MISMATCH"):
        configured_plan(str(p), "f" * 64)
    p.chmod(0o644)
    with pytest.raises(AuthorityError, match="FILE_INVALID"):
        configured_plan(str(p), pin)
    link = tmp_path / "link"
    link.symlink_to(p)
    with pytest.raises(OSError):
        configured_plan(str(link), pin)


@pytest.mark.parametrize("kind", ["cutoff", "account_scope", "service_subject"])
def test_original_deadline_and_current_subject_are_not_plan_assertions(
    monkeypatch, kind
):
    plan, service, c, ctx, row, spec, prior, now = data()
    original_deadline = plan.global_expires_at
    monkeypatch.setattr(
        "agent_console.provider_budget_allowance.require_context",
        lambda *a: N(expiresAt=original_deadline),
    )
    if kind == "cutoff":
        plan = plan.model_copy(
            update={"global_expires_at": original_deadline + timedelta(hours=1)}
        )
    elif kind == "account_scope":
        execute = c.execute

        def changed(sql, args):
            if "local_accounts" in sql:
                return N(
                    fetchone=lambda: dict(
                        status="ENABLED",
                        revision=1,
                        principal_id="human:u",
                        tenant_id="foreign",
                        security_domain="d",
                    )
                )
            return execute(sql, args)

        c.execute = changed
    else:
        row["subject_id"] = "service:u"
    with pytest.raises(AuthorityError, match="PLAN_MISMATCH"):
        plan.require(service, c, ctx, row, spec, prior, None, now)
