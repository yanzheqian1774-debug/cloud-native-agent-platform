"""No free HTTP/model runner. Exact private mapping to existing Skill test owner."""

import hashlib
import os
import stat
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .resource_management import target
from .skill_invocation_domain import SkillInvocationError
from .skill_resource_testing import run, schema_check
from .workbench_business_problem import OwnerPrincipal
from .workbench_prepared_resources import bind_service, reference


class Mapping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    namespace: str
    securityDomain: str
    subject: str
    toolId: str
    revisionId: str
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    skillId: str
    skillRevisionId: str
    skillDigest: str = Field(pattern=r"^(?:sha256:)?[a-f0-9]{64}$")
    operation: str
    expiresAt: datetime


class TestPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: Literal["tool-contract-test-policy.v1"]
    enabled: bool = False
    bindings: tuple[Mapping, ...] = Field(max_length=128)


class ToolContractTesting:
    def __init__(self, path, manager):
        self.path = Path(path)
        raw = self.read_policy()
        self.sha = hashlib.sha256(raw).hexdigest()
        self.policy = TestPolicy.model_validate_json(raw)
        self.manager = manager
        if self.policy.enabled and manager is None:
            raise ValueError("TOOL_TEST_MANAGEMENT_REQUIRED")

    def read_policy(self):
        if not self.path.is_absolute() or self.path != self.path.resolve():
            raise ValueError("TOOL_TEST_PRIVATE_POLICY_REQUIRED")
        fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_mode & 0o077
                or info.st_uid != os.getuid()
                or info.st_size > 200000
            ):
                raise ValueError("TOOL_TEST_PRIVATE_POLICY_REQUIRED")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                return stream.read(200001)
        finally:
            os.close(fd)

    def run(self, call, current, command):
        result = {
            "status": "NOT_EXECUTED",
            "actual": None,
            "actualExecution": False,
            "toolSourceInvoked": False,
            "revisionId": current["revisionId"],
            "revisionDigest": current["digest"],
            "reasonCode": "TOOL_EXECUTOR_NOT_CONFIGURED",
            "modelCalls": 0,
            "businessRunStarted": False,
            "verificationLevel": "ISOLATED_REGISTERED_SKILL_COMPUTATION",
        }
        # API/ZIP contents are not permission to execute arbitrary external/code
        # sources. MCP uses its separate published tool-test owner and grants.
        if current["record"]["operation"]["source"]["kind"] != "PLUGIN":
            return {
                **result,
                "reasonCode": "TOOL_SOURCE_REQUIRES_ORIGINAL_INVOCATION_OWNER",
            }
        try:
            unchanged = hashlib.sha256(self.read_policy()).hexdigest() == self.sha
        except (OSError, ValueError):
            unchanged = False
        if not unchanged or not self.policy.enabled:
            return {**result, "reasonCode": "TOOL_TEST_POLICY_CHANGED_OR_DISABLED"}
        ctx = call.context
        now = self.manager.grants.clock()
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
            )
            == (
                ctx.scope.tenant_id,
                ctx.scope.security_domain,
                ctx.principal_id,
                current["toolId"],
                current["revisionId"],
                current["digest"],
            )
            and b.expiresAt.tzinfo
            and now < b.expiresAt
        ]
        if len(matches) != 1:
            return result
        b = matches[0]
        # Recheck original independent management policy/issuer and current exact
        # Skill authority on the same authorized transaction; no grant is minted.
        self.manager.scope(ctx, "skill")
        principal = OwnerPrincipal(
            ctx.principal_id, ctx.scope.tenant_id, ctx.scope.security_domain
        )
        call.authority.require(
            principal, "SKILL", "MANAGE_RESOURCE", target("skill", b.skillId)
        )
        call.authority.require(
            principal,
            "SKILL",
            "READ_RESOURCE",
            reference("skill", b.skillId, b.skillRevisionId),
        )
        if not self.manager.owned(call, "skill", b.skillId):
            return {**result, "reasonCode": "TOOL_TEST_SKILL_NOT_OWNED"}
        service = bind_service(self.manager.services["skill"], call.connection)
        scope = service.scope(ctx.scope.tenant_id, ctx.scope.security_domain)
        record = service._load(scope, "skill", b.skillId)
        revision = next(
            (
                r
                for r in record["revisions"]
                if r["revisionId"] == b.skillRevisionId and r["digest"] == b.skillDigest
            ),
            None,
        )
        if revision is None or record["publishedRevisionId"] != b.skillRevisionId:
            return {**result, "reasonCode": "TOOL_TEST_EXACT_PUBLISHED_SKILL_REQUIRED"}
        if not command.expectedOutput:
            return {**result, "reasonCode": "TOOL_TEST_EXPECTATION_REQUIRED"}
        operation = current["record"]["operation"]
        try:
            schema_check(
                command.input,
                operation["inputSchema"],
                "TOOL_TEST_INPUT_CONTRACT_INVALID",
            )
            from .resource_automation_validation import executor_registry

            observed = run(
                service,
                scope,
                b.skillId,
                ctx.principal_id,
                record["aggregateVersion"],
                operation=b.operation,
                name=command.testName,
                inputs=command.input,
                expected_output=command.expectedOutput,
                comparison=command.comparison,
                revision_id=b.skillRevisionId,
                persist=False,
                executor_registry=executor_registry(),
            )["testResult"]
            result.update(observed)
            result.update(
                revisionId=current["revisionId"],
                revisionDigest=current["digest"],
                skillRevisionId=b.skillRevisionId,
                skillDigest=b.skillDigest,
                verificationLevel="ISOLATED_REGISTERED_SKILL_COMPUTATION",
                modelCalls=0,
                mappingPolicyDigest=self.sha,
            )
            if result["actualExecution"] and result["actual"] is not None:
                schema_check(
                    result["actual"],
                    operation["outputSchema"],
                    "TOOL_TEST_OUTPUT_CONTRACT_INVALID",
                )
        except SkillInvocationError as exc:
            result.update(status="FAILED", reasonCode=str(exc))
        return result
