"""Private, explicitly pinned renewal entries; never an invocation dispatcher."""

import hashlib
import json
import os
import stat
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import AuthorityError
from .task_delegation import digest


class RenewalEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    context_id: str
    subject_id: str
    tenant_id: str
    security_domain: str
    request_digest: str = Field(pattern="^[a-f0-9]{64}$")
    configuration: dict
    allowance_id: str
    allowance_authorization_digest: str = Field(pattern="^[a-f0-9]{64}$")
    prior_admission_id: str
    prior_record_digest: str = Field(pattern="^[a-f0-9]{64}$")
    idempotency_key: str
    expires_at: datetime
    lease_mode: Literal["KEEP_EXPIRY", "EXPIRED_LEASE"]


def valid_original_decision(original, row):
    """Read original writer shapes without rewriting historical admission facts."""
    if not isinstance(original, dict) or not isinstance(original.get("record"), dict):
        return False
    record = original["record"]
    request = row["record"]
    if record.get("request") != request:
        return False
    if "type" not in record:
        return record.get("request_digest") == row["digest"]
    kind = record.get("type")
    expected_phase = {
        "F3_CONVERSATION_EXPERIENCE": "understanding",
        "F3_CONVERSATION_PLANNING": "planning",
    }.get(kind)
    if expected_phase is None:
        return False
    policy = request.get("experience_policy_digest")
    if expected_phase == "understanding":
        policy = request.get("owned_understanding_policy_digest", policy)
    return (
        set(record) == {"type", "request", "policy_digest", "ledger_unchanged"}
        and request.get("phase") == expected_phase
        and request.get("task_id") == "F3-CONVERSATION-EXPERIENCE"
        and request.get("external_writes") is False
        and isinstance(policy, str)
        and len(policy) == 64
        and all(ch in "0123456789abcdef" for ch in policy)
        and record["policy_digest"] == policy
        and record["ledger_unchanged"] is True
        and original.get("issuer_id") == "policy:f3-conversation-experience"
        and original.get("ordinal") == 1
        and original.get("context_id") == row["context_id"]
        and original.get("idempotency_key") == "f3:" + row["context_id"]
        and original.get("admission_id")
        == ("f3-experience:" if expected_phase == "understanding" else "f3-planning:")
        + digest(row["context_id"])
        and original.get("payload_digest") == digest(record)
        and digest(request) == row["digest"]
        and all(
            request.get(k) == row.get(k)
            for k in (
                "context_id",
                "subject_id",
                "account_id",
                "account_revision",
                "first_invocation_id",
            )
        )
        and (
            expected_phase == "planning"
            or all(
                request.get(k) == row.get(k) for k in ("tenant_id", "security_domain")
            )
        )
    )


class ReadmissionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["context-readmission.v1"]
    issuer_id: str
    generation: int = Field(gt=0)
    recovery_epoch: int = Field(ge=0)
    authorization_evidence_digest: str = Field(pattern="^[a-f0-9]{64}$")
    global_expires_at: datetime
    entries: tuple[RenewalEntry, ...] = Field(min_length=1, max_length=256)

    def entry(self, context_id):
        matches = [e for e in self.entries if e.context_id == context_id]
        if len(matches) != 1:
            raise AuthorityError("CONTEXT_READMISSION_PLAN_MISMATCH")
        return matches[0]

    def require(self, service, c, context, row, spec, prior, previous, now):
        e = self.entry(row["context_id"])
        if (
            service.configuration != e.configuration
            or row["record"].get("configuration") != e.configuration
        ):
            raise AuthorityError("CONTEXT_READMISSION_PLAN_MISMATCH")
        grants = service.delegation.grants
        from .provider_budget_allowance import require_context

        allowance = require_context(
            c,
            row["tenant_id"],
            row["security_domain"],
            service.configuration["ledger_id"],
            e.allowance_id,
            e.allowance_authorization_digest,
            service.configuration,
        )
        account = c.execute(
            "SELECT status,revision,principal_id,tenant_id,security_domain FROM "
            "browser_identity.local_accounts WHERE account_id=%s FOR SHARE",
            (row["account_id"],),
        ).fetchone()
        if (
            account
            != {
                "status": "ENABLED",
                "revision": row["account_revision"],
                "principal_id": row["subject_id"],
                "tenant_id": row["tenant_id"],
                "security_domain": row["security_domain"],
            }
            or not row["subject_id"].startswith("human:")
            or self.global_expires_at != allowance.expiresAt
            or (
                row["record"].get("budget_allowance_id") is not None
                and (
                    row["record"]["budget_allowance_id"] != e.allowance_id
                    or row["record"].get("authorization_digest")
                    != e.allowance_authorization_digest
                )
            )
            or context.principal_id != self.issuer_id
            or (grants.generation.generation, grants.recovery_epoch)
            != (self.generation, self.recovery_epoch)
            or (row["subject_id"], row["tenant_id"], row["security_domain"])
            != (e.subject_id, e.tenant_id, e.security_domain)
            or row["record"].get("subject_id") != row["subject_id"]
            or row["record"].get("account_id") != row["account_id"]
            or row["record"].get("account_revision") != row["account_revision"]
            or row["digest"] != e.request_digest
            or digest(row["record"]) != e.request_digest
            or row["record"]["configuration"] != e.configuration
            or service.configuration != e.configuration
            or spec.request_digest != e.request_digest
            or spec.idempotency_key != e.idempotency_key
            or spec.expires_at != e.expires_at
            or self.global_expires_at.utcoffset() != timedelta(0)
            or e.expires_at.utcoffset() != timedelta(0)
            or not now < e.expires_at <= self.global_expires_at
            or not prior
        ):
            raise AuthorityError("CONTEXT_READMISSION_PLAN_MISMATCH")
        original = c.execute(
            "SELECT * FROM authorization_admin.context_call_decisions "
            "WHERE context_id=%s AND admission_id=%s",
            (row["context_id"], e.prior_admission_id),
        ).fetchone()
        if (
            not original
            or digest(original["record"]) != e.prior_record_digest
            or not valid_original_decision(original, row)
            or original["subject_id"] != e.subject_id
            or (previous is None and prior["admission_id"] != e.prior_admission_id)
            or (
                previous is not None
                and (
                    prior["admission_id"] != previous["admission_id"]
                    or previous["record"].get("predecessor_id") != e.prior_admission_id
                    or previous["record"].get("readmission") != self.receipt(e)
                )
            )
            or c.execute(
                "SELECT 1 FROM authorization_admin.context_call_revocations "
                "WHERE admission_id=ANY(%s)",
                ([e.prior_admission_id, prior["admission_id"]],),
            ).fetchone()
        ):
            raise AuthorityError("CONTEXT_READMISSION_PRIOR_INVALID")
        if e.lease_mode == "KEEP_EXPIRY":
            valid = e.expires_at == original["expires_at"]
        else:
            # A replay is observation of this same bounded decision, not a new lease.
            issued_at = previous["created_at"] if previous else now
            valid = (
                original["expires_at"]
                <= issued_at
                < e.expires_at
                <= issued_at + timedelta(hours=8)
            )
        if not valid:
            raise AuthorityError("CONTEXT_READMISSION_LEASE_INVALID")
        return self.receipt(e)

    def receipt(self, e):
        return {
            "schemaVersion": "context-readmission-receipt.v1",
            "planDigest": digest(self.model_dump(mode="json")),
            "authorizationEvidenceDigest": self.authorization_evidence_digest,
            "leaseMode": e.lease_mode,
            "priorAdmissionId": e.prior_admission_id,
        }


def configured_plan(path, expected_sha256):
    if not path and not expected_sha256:
        return None
    if not path or not expected_sha256 or not Path(path).is_absolute():
        raise AuthorityError("CONTEXT_READMISSION_PLAN_PIN_REQUIRED")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size > 1048576
        ):
            raise AuthorityError("CONTEXT_READMISSION_PLAN_FILE_INVALID")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(1048577)
        if hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise AuthorityError("CONTEXT_READMISSION_PLAN_PIN_MISMATCH")

        def unique_pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise AuthorityError("CONTEXT_READMISSION_PLAN_AMBIGUOUS")
                result[key] = value
            return result

        document = json.loads(raw, object_pairs_hook=unique_pairs)
        plan = ReadmissionPlan.model_validate(document)
        if len({e.context_id for e in plan.entries}) != len(plan.entries) or len(
            {e.idempotency_key for e in plan.entries}
        ) != len(plan.entries):
            raise AuthorityError("CONTEXT_READMISSION_PLAN_AMBIGUOUS")
        return plan
    finally:
        os.close(fd)
