"""Private exact BOUND read eligibility; never an execution or model authority."""

import hashlib
import json
import os
import stat
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .authority_contracts import AuthenticationSource
from .plan_suggestion_domain import ExactReference
from .workbench_owner_authorization import WorkbenchOwnerError


class BindingReadScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    tenantId: str = Field(min_length=1, max_length=200)
    securityDomain: str = Field(min_length=1, max_length=200)
    subjectId: str = Field(pattern=r"^human:.{1,190}$")
    conversationId: str = Field(min_length=1, max_length=200)
    bindingDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    work: ExactReference


class FixedChatReadPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: Literal["fixed-chat-read-policy.v1"]
    policyId: str = Field(min_length=1, max_length=200)
    enabled: bool = False
    expiresAt: datetime
    grantTTLSeconds: int = Field(strict=True, ge=60, le=3600)
    scopes: tuple[BindingReadScope, ...] = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def unique(self):
        keys = [
            (s.tenantId, s.securityDomain, s.subjectId, s.conversationId)
            for s in self.scopes
        ]
        if self.expiresAt.tzinfo is None or len(set(keys)) != len(keys):
            raise ValueError("aware expiry and unique original conversations required")
        return self

    @classmethod
    def load(cls, path, expected_sha256):
        try:
            p = Path(path)
            info = p.lstat()
            if (
                not p.is_absolute()
                or not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size > 1024 * 1024
            ):
                raise ValueError("private regular policy required")
            raw = p.read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected_sha256:
                raise ValueError("policy pin mismatch")

            def unique_pairs(pairs):
                values = dict(pairs)
                if len(values) != len(pairs):
                    raise ValueError("duplicate policy key")
                return values

            return cls.model_validate(json.loads(raw, object_pairs_hook=unique_pairs))
        except (OSError, TypeError, ValueError) as exc:
            raise WorkbenchOwnerError(
                "FIXED_CHAT_READ_POLICY_UNAVAILABLE", 503
            ) from exc

    def require(self, context, conversation, now):
        if not self.enabled or now >= self.expiresAt:
            raise WorkbenchOwnerError("FIXED_CHAT_READ_POLICY_UNAVAILABLE", 503)
        matches = [
            s
            for s in self.scopes
            if (s.tenantId, s.securityDomain, s.subjectId, s.conversationId)
            == (
                context.scope.tenant_id,
                context.scope.security_domain,
                context.principal_id,
                conversation,
            )
        ]
        if (
            context.authentication_source != AuthenticationSource.BROWSER_SESSION
            or len(matches) != 1
        ):
            raise WorkbenchOwnerError("FIXED_CHAT_READ_NOT_AUTHORIZED", 403)
        return matches[0]
