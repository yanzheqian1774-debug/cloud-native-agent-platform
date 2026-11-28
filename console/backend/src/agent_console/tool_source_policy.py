"""Private exact-source allowlist; never authorizes arbitrary uploaded code."""

import hashlib
import os
import stat
from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

SHA = r"^[a-f0-9]{64}$"


class SourceBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    namespace: str
    securityDomain: str
    subject: str
    toolId: str
    revisionId: str
    digest: str = Field(pattern=SHA)
    sourceDigest: str = Field(pattern=SHA)
    entrypoint: str
    entrypointDigest: str = Field(pattern=SHA)
    runtime: Literal["reviewed-python-function.v1"]
    runtimeRevision: str = Field(min_length=1, max_length=120)
    endpoint: str
    expiresAt: datetime
    maximumCalls: int = Field(ge=1, le=20)
    timeoutMs: int = Field(ge=1, le=5000)
    maximumInputBytes: int = Field(ge=1, le=65536)
    maximumOutputBytes: int = Field(ge=1, le=65536)
    syntheticReadOnly: Literal[True]

    @model_validator(mode="after")
    def local_registered_runtime(self):
        p = urlsplit(self.endpoint)
        if (
            p.scheme != "http"
            or p.hostname != "127.0.0.1"
            or not p.port
            or p.username
            or p.password
            or p.path
            or p.query
            or p.fragment
            or self.endpoint != f"http://127.0.0.1:{p.port}"
            or self.expiresAt.tzinfo is None
        ):
            raise ValueError("TOOL_SOURCE_RUNTIME_NOT_ALLOWLISTED")
        return self


class SourcePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: Literal["tool-source-test-policy.v1"]
    enabled: bool = False
    bindings: tuple[SourceBinding, ...] = Field(max_length=128)


class PrivateSourcePolicy:
    def __init__(self, path):
        self.path = Path(path)
        raw = self.read()
        self.digest = hashlib.sha256(raw).hexdigest()
        self.policy = SourcePolicy.model_validate_json(raw)
        identities = [
            (b.namespace, b.securityDomain, b.subject, b.toolId, b.revisionId)
            for b in self.policy.bindings
        ]
        if len(set(identities)) != len(identities):
            raise ValueError("TOOL_SOURCE_POLICY_DUPLICATE")

    def read(self):
        if not self.path.is_absolute() or self.path != self.path.resolve():
            raise ValueError("TOOL_SOURCE_PRIVATE_POLICY_REQUIRED")
        fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_mode & 0o077
                or info.st_uid != os.getuid()
                or info.st_size > 200000
            ):
                raise ValueError("TOOL_SOURCE_PRIVATE_POLICY_REQUIRED")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                return stream.read(200001)
        finally:
            os.close(fd)

    def binding(self, context, current, now):
        if hashlib.sha256(self.read()).hexdigest() != self.digest:
            raise ValueError("TOOL_SOURCE_POLICY_CHANGED")
        if not self.policy.enabled:
            raise ValueError("TOOL_SOURCE_POLICY_DISABLED")
        identity = (
            context.scope.tenant_id,
            context.scope.security_domain,
            context.principal_id,
            current["toolId"],
            current["revisionId"],
            current["digest"],
            current["sourceDigest"],
        )
        matches = [
            b
            for b in self.policy.bindings
            if (
                b.namespace,
                b.securityDomain,
                b.subject,
                b.toolId,
                b.revisionId,
                b.digest,
                b.sourceDigest,
            )
            == identity
            and now < b.expiresAt
        ]
        if len(matches) != 1:
            raise ValueError("TOOL_SOURCE_EXACT_AUTHORIZATION_REQUIRED")
        return matches[0]
