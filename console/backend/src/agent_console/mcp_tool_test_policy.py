"""Private exact published MCP testing scope; never authorization by tool annotation."""

import os
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import AuthorityError, ExactGrant
from .plan_suggestion_domain import ExactReference
from .resource_automation_policy import AutomationPolicy
from .resource_use_domain import canonical_digest


def require(value, reason):
    if not value:
        raise AuthorityError("MCP_TOOL_TEST_" + reason)


class ToolBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    namespace: str
    securityDomain: str
    subject: str
    mcp: ExactReference
    source: ExactReference
    sourceContentDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    endpoint: str
    selectionId: str
    snapshotId: str
    snapshotDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    toolName: str = Field(min_length=1, max_length=128)
    inputSchema: dict
    arguments: dict
    sideEffect: Literal["READ"]
    expiresAt: datetime

    @property
    def digest(self):
        return canonical_digest(self.model_dump(mode="json", exclude={"expiresAt"}))

    @property
    def grant(self):
        return ExactGrant(
            "SKILL", "INVOKE_MCP_TOOL", "skill-invocation:mcp-tool-test:" + self.digest
        )


class ToolTestPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: Literal["mcp-published-tool-test.v1"]
    enabled: bool = False
    policyId: str
    policyVersion: str
    issuer: str
    credentialPath: Path
    grantTTLSeconds: int = Field(default=300, ge=60, le=600)
    timeoutSeconds: float = Field(default=3, ge=0.1, le=10)
    bindings: tuple[ToolBinding, ...] = Field(min_length=1, max_length=32)

    @property
    def digest(self):
        return canonical_digest(self.model_dump(mode="json"))

    def authenticate(self, grants, context):
        return AutomationPolicy.authenticate(self, grants, context)

    @classmethod
    def load(cls, value):
        path = Path(value)
        require(path.is_absolute() and not path.is_symlink(), "POLICY_INVALID")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            import stat

            st = os.fstat(fd)
            require(
                stat.S_ISREG(st.st_mode)
                and st.st_uid == os.getuid()
                and not st.st_mode & 0o077,
                "POLICY_INVALID",
            )
            with os.fdopen(fd, "r", closefd=False) as stream:
                result = cls.model_validate_json(stream.read(200001))
        finally:
            os.close(fd)
        require(result.credentialPath.is_absolute(), "POLICY_INVALID")
        require(
            all(b.expiresAt.tzinfo is not None for b in result.bindings),
            "POLICY_INVALID",
        )
        require(
            len({b.digest for b in result.bindings}) == len(result.bindings),
            "POLICY_INVALID",
        )
        return result

    def binding(self, context, digest, now):
        require(self.enabled, "DISABLED")
        matches = [
            b
            for b in self.bindings
            if b.digest == digest
            and b.namespace == context.scope.tenant_id
            and b.securityDomain == context.scope.security_domain
            and b.subject == context.principal_id
            and b.expiresAt > now
        ]
        require(len(matches) == 1, "SCOPE_DENIED")
        return matches[0]
