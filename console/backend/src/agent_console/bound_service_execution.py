# ruff: noqa: E501 -- Exact original service/BOUND receipt queries.
"""Exact service execution provenance from original 0070/0073 owners, not Human admission."""

import os
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

from .authority_contracts import AuthenticationSource, AuthorityError
from .digital_employee_definition import digest
from .fixed_chat_facts import binding_facts, event_facts
from .fixed_work_authoring_postgres import read as read_work
from .fixed_work_bound_policy import BoundServicePlanningPolicy
from .fixed_work_service_admission import ServicePlanningRegistry


def require(ok):
    if not ok:
        raise AuthorityError("BOUND_SERVICE_EXECUTION_BINDING_INVALID")


@dataclass(frozen=True)
class BoundServiceExecution:
    conversation_id: str
    execution_subject: str
    source: object
    expires_at: datetime
    binding_digest: str
    work_digest: str
    event_id: str
    receipt_digest: str


class BoundServiceExecutionBridge:
    def __init__(self, registry):
        if not isinstance(registry, ServicePlanningRegistry):
            raise TypeError("BOUND_SERVICE_EXECUTION_REGISTRY_REQUIRED")
        self.registry = registry

    @classmethod
    def load(cls, path, repository, authorization):
        path = Path(path)

        def raw():
            require(path.is_absolute() and path.resolve() == path)
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                require(
                    stat.S_ISREG(info.st_mode)
                    and info.st_uid == os.getuid()
                    and stat.S_IMODE(info.st_mode) == 0o600
                )
                data = stream.read(1_048_577)
                current = path.lstat()
                require(
                    len(data) <= 1_048_576
                    and (current.st_dev, current.st_ino) == (info.st_dev, info.st_ino)
                )
                return data

        expected = sha256(raw()).hexdigest()

        def policy_reader():
            data = raw()
            require(sha256(data).hexdigest() == expected)
            policy = BoundServicePlanningPolicy.model_validate_json(data)
            require(policy.enabled and policy.expiresAt > datetime.now(UTC))
            return policy

        policy_reader()
        return cls(ServicePlanningRegistry(repository, authorization, policy_reader))

    def require_scope(self, scope):
        policy = self.registry._policy()
        require(
            tuple(scope) == (policy.tenantId, policy.securityDomain, policy.subjectId)
        )

    def authorize(self, c, context, command):
        from .ontology_execution import parse_preparation
        from .prepared_execution_lineage import prepared_attempt

        row = prepared_attempt(c, command.scope, command.attempt_id)
        require(row is not None)
        return self.read(c, context, command, parse_preparation(row["preparation"]))

    def read(self, c, context, command, preparation):
        require(
            context.authentication_source is AuthenticationSource.SERVICE_CREDENTIAL
        )
        policy = self.registry._policy()
        require(isinstance(policy, BoundServicePlanningPolicy))
        require(context.principal_id == command.principal_id == policy.subjectId)
        require(
            context.session_id_or_service_credential_id
            == command.credential_id
            == policy.credentialId
        )
        self.registry._check(c, context, policy)
        scope = policy.tenantId, policy.securityDomain
        require((command.scope.namespace, command.scope.security_domain) == scope)
        require(
            command.authorization_resource
            == "governed-execution:prepared:" + preparation.digest
        )
        rows = c.execute(
            "SELECT * FROM fixed_work_triggers.receipts WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND workflow_run_id=%s AND preparation_digest=%s",
            (*scope, policy.subjectId, preparation.run_id, preparation.digest),
        ).fetchall()
        require(len(rows) == 1)
        event = rows[0]
        admission = c.execute(
            "SELECT * FROM fixed_work_service.planning_preparations WHERE namespace=%s AND security_domain=%s AND work_id=%s AND event_id=%s",
            (*scope, policy.work.resource_id, event["event_id"]),
        ).fetchone()
        require(
            admission is not None
            and admission["policy_digest"] == policy.digest
            and admission["policy"] == policy.model_dump(mode="json")
        )
        from .fixed_work_sources_postgres import read

        bound = read(
            c, scope, "bindings", policy.work.resource_id, policy.work.revision_id
        )
        handoff = read(
            c, scope, "handoffs", policy.work.resource_id, policy.work.revision_id
        )
        require(bound is not None and handoff is not None)
        saved = read_work(c, scope, policy.work.resource_id, policy.work.revision_id)
        # This is a fact-comparison value, not a TrustedRequestContext. All current
        # service checks above use the original service credential exclusively.
        permit = SimpleNamespace(
            tenantId=scope[0],
            securityDomain=scope[1],
            subjectId=bound["record"]["subjectId"],
            conversationId=bound["record"]["conversationId"],
            work=policy.work,
            bindingDigest=policy.sourceBindingDigest,
        )
        binding = binding_facts(bound, handoff, saved, permit)
        event_view = event_facts(event, admission, binding, saved, preparation, permit)
        owned = c.execute(
            "SELECT owner_id,archived_at FROM private_conversation.conversations WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s",
            (*scope, permit.conversationId),
        ).fetchone()
        require(
            owned is not None
            and owned["owner_id"] == permit.subjectId
            and owned["archived_at"] is None
        )
        require(event["start_command_key"].endswith(":start"))
        row = c.execute(
            "SELECT result FROM execution_authority.prepared_resource_commands WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND command_key=%s",
            (*scope, policy.subjectId, event["start_command_key"][:-6]),
        ).fetchone()
        require(row is not None)
        receipt = row["result"]
        require(
            receipt["subject"] == policy.subjectId
            and receipt["runId"] == preparation.run_id
            and receipt["preparationDigest"] == preparation.digest
            and receipt["executionStarted"] is True
        )
        require(
            event["payload_digest"]
            == digest(
                dict(
                    work=policy.work.model_dump(mode="json"),
                    event=event["event_id"],
                    plan=receipt["sourcePlanDigest"],
                )
            )
        )
        require(
            event["start_command_key"]
            == "readonly-continuation:" + receipt["sourcePlanDigest"] + ":start"
        )
        expiry = min(
            policy.expiresAt, datetime.fromisoformat(receipt["authorizationExpiresAt"])
        )
        require(expiry > datetime.now(UTC))
        return BoundServiceExecution(
            permit.conversationId,
            policy.subjectId,
            preparation.source_snapshot,
            expiry,
            policy.sourceBindingDigest,
            policy.work.digest,
            event["event_id"],
            event_view["receiptDigest"],
        )
