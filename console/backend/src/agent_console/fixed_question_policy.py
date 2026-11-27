"""Explicit independent question authority, never inferred from READ or START."""

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from .authority_contracts import AuthenticationSource
from .fixed_chat_read_policy import BindingReadScope, FixedChatReadPolicy
from .fixed_question_types import StrictValue
from .native_wait_types import Digest, Identity
from .resource_use_domain import canonical_digest
from .workbench_owner_authorization import WorkbenchOwnerError


class QuestionScope(BindingReadScope):
    executionSubject: str = Field(pattern=r"^service:.{1,190}$")
    serviceCredentialId: Identity


class FixedQuestionPolicy(StrictValue):
    schemaVersion: Literal["fixed-question-delegation-policy.v1"]
    policyId: Identity
    enabled: bool = False
    generation: int = Field(strict=True, gt=0)
    generationDigest: Digest
    recoveryEpoch: int = Field(strict=True, gt=0)
    issuerId: Identity
    issuerCredentialId: Identity
    expiresAt: datetime
    grantTTLSeconds: int = Field(strict=True, ge=1, le=3600)
    scopes: tuple[QuestionScope, ...] = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def valid(self):
        keys = [
            (s.tenantId, s.securityDomain, s.subjectId, s.conversationId)
            for s in self.scopes
        ]
        if self.expiresAt.tzinfo is None or len(set(keys)) != len(keys):
            raise ValueError("FIXED_QUESTION_POLICY_INVALID")
        if any(
            s.subjectId == self.issuerId or s.executionSubject == self.issuerId
            for s in self.scopes
        ):
            raise ValueError("FIXED_QUESTION_INDEPENDENT_ISSUER_REQUIRED")
        return self

    @classmethod
    def load(cls, path, expected_sha256):
        # Reuse the original pinned private-file reader; validation dispatches
        # through this class, not the READ policy schema or its authority.
        return FixedChatReadPolicy.load.__func__(cls, path, expected_sha256)

    @property
    def digest(self):
        return canonical_digest(self.model_dump(mode="json"))

    def require(self, call, conversation, now):
        ctx = call.context
        if not self.enabled or now >= self.expiresAt:
            raise WorkbenchOwnerError("FIXED_QUESTION_DELEGATION_UNAVAILABLE", 503)
        matches = [
            s
            for s in self.scopes
            if (s.tenantId, s.securityDomain, s.subjectId, s.conversationId)
            == (
                ctx.scope.tenant_id,
                ctx.scope.security_domain,
                ctx.principal_id,
                conversation,
            )
        ]
        if (
            ctx.authentication_source is not AuthenticationSource.BROWSER_SESSION
            or len(matches) != 1
            or call.policy_generation != self.generation
            or call.recovery_epoch != self.recoveryEpoch
            or call.authority.adapter.controller.readiness.generation_digest
            != self.generationDigest
        ):
            raise WorkbenchOwnerError("FIXED_QUESTION_DELEGATION_NOT_AUTHORIZED", 403)
        return matches[0]
