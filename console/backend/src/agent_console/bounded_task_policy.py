"""D324-7 immutable signed boundaries; pure checks used before owner effects."""

from datetime import datetime, timedelta
from typing import Literal

from pydantic import Field, model_validator

from .authority_contracts import AuthorityError, ExactGrant
from .plan_suggestion_domain import Digest, ExactReference, Identity, Immutable


class TaskPermission(Immutable):
    owner: Identity
    action: Identity
    exact_resource: Identity

    @model_validator(mode="after")
    def registered(self):
        from .authority_configuration import validate_registered_grant

        validate_registered_grant(
            ExactGrant(self.owner, self.action, self.exact_resource), allow_meta=False
        )
        return self


class DerivedPermission(Immutable):
    owner: Literal["PLAN"]
    action: Literal["READ", "PREPARE", "APPROVE"]
    phase: Literal["planning"]


class ConfigurationRevision(Immutable):
    revision_id: Identity
    predecessor_digest: Digest
    configuration_digest: Digest
    ledger_id: Identity
    model_target: Identity
    connect_seconds: Literal[5] = 5
    read_seconds: Literal[55] = 55
    total_seconds: Literal[60] = 60
    cleanup_seconds: Literal[2] = 2
    cumulative_call_cap: Literal[21] = 21
    total_cost_cap_microusd: Literal[10000000] = 10000000


class TaskAuthorizationRequest(Immutable):
    task_id: Literal["S5-V023-IMPL-324"] = "S5-V023-IMPL-324"
    purpose: Literal["SAME_CASE_DELIVERY", "ISOLATED_NATIVE_VALIDATION"]
    root: ExactReference
    source_snapshot: ExactReference
    determination_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    idempotency_key: Identity
    permissions: tuple[TaskPermission, ...] = Field(min_length=1, max_length=128)
    derived_permissions: tuple[DerivedPermission, ...] = ()
    configuration: ConfigurationRevision | None = None
    recovery_invocation_id: Identity | None = None

    @model_validator(mode="after")
    def bounded_purpose(self):
        if self.purpose == "ISOLATED_NATIVE_VALIDATION" and (
            self.configuration is not None or self.recovery_invocation_id is not None
        ):
            raise ValueError("NATIVE_VALIDATION_CANNOT_AUTHORIZE_MODEL")
        if (self.configuration is None) != (self.recovery_invocation_id is None):
            raise ValueError("EXACT_RECOVERY_REQUIRED")
        return self


class TaskSignature(Immutable):
    request_digest: Digest
    idempotency_key: Identity
    not_before: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def window(self):
        if (
            self.not_before.utcoffset() != timedelta(0)
            or self.expires_at.utcoffset() != timedelta(0)
            or not timedelta(0)
            < self.expires_at - self.not_before
            <= timedelta(hours=8)
        ):
            raise ValueError("TASK_AUTHORIZATION_WINDOW_INVALID")
        return self


def require_scope(purpose, scope):
    expected = {
        "SAME_CASE_DELIVERY": ("s5-323-demo", "isolated-real-demo"),
        "ISOLATED_NATIVE_VALIDATION": (
            "s5-324-native-capability",
            "isolated-native-validation",
        ),
    }[purpose]
    if tuple(scope) != expected:
        raise AuthorityError("TASK_AUTHORIZATION_SCOPE_DENIED")


def require_current(row, decision, account, generation, now, *, revoked):
    if account != {
        "status": "ENABLED",
        "revision": row["account_revision"],
        "principal_id": row["subject_id"],
        "tenant_id": row["tenant_id"],
        "security_domain": row["security_domain"],
    }:
        raise AuthorityError("TASK_AUTHORIZATION_ACCOUNT_INACTIVE")
    if (
        decision is None
        or revoked
        or not decision["not_before"] <= now < decision["expires_at"]
        or any(decision[k] != generation[k] for k in ("generation", "recovery_epoch"))
    ):
        raise AuthorityError("TASK_AUTHORIZATION_REQUIRED")


def require_configuration(signed, actual, *, cleanup_seconds):
    """No configuration substitution; read is bounded by total, cleanup is separate."""
    if signed is None or not {
        "configuration_digest",
        "ledger_id",
        "model_target",
        "connect_seconds",
        "read_seconds",
        "total_seconds",
        "cost_microusd",
    }.issubset(actual):
        raise AuthorityError("TASK_AUTHORIZATION_CONFIGURATION_MISMATCH")
    if (
        signed.configuration_digest != actual["configuration_digest"]
        or signed.ledger_id != actual["ledger_id"]
        or signed.model_target != actual["model_target"]
        or (
            actual["connect_seconds"],
            actual["read_seconds"],
            actual["total_seconds"],
            cleanup_seconds,
        )
        != (
            signed.connect_seconds,
            signed.read_seconds,
            signed.total_seconds,
            signed.cleanup_seconds,
        )
        or actual["cost_microusd"] != signed.total_cost_cap_microusd
    ):
        raise AuthorityError("TASK_AUTHORIZATION_CONFIGURATION_MISMATCH")
