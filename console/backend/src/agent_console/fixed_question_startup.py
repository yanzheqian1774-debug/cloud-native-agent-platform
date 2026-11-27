"""Explicit startup-only assembly of a delegated document question owner."""

import hashlib
import json
import os
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field

from .fixed_question_composition import FixedQuestionComposition
from .fixed_question_policy import FixedQuestionPolicy
from .fixed_question_types import StrictValue
from .native_typed_answer import settlement_reader_for_services
from .native_typed_document_skill import NativeTypedQuestionDocumentSkillExecutor


class PinnedFile(StrictValue):
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def read_pin(pin):
    """Verify private bytes on the same non-symlink descriptor that is read."""
    path = Path(pin.path)
    if not path.is_absolute():
        raise ValueError("FIXED_QUESTION_STARTUP_PIN_INVALID")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or not 0 < info.st_size <= 1024 * 1024
        ):
            raise ValueError("FIXED_QUESTION_STARTUP_PIN_INVALID")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(1024 * 1024 + 1)
        if len(raw) != info.st_size or hashlib.sha256(raw).hexdigest() != pin.sha256:
            raise ValueError("FIXED_QUESTION_STARTUP_PIN_CHANGED")
        return raw
    finally:
        os.close(fd)


def unique(pairs):
    values = dict(pairs)
    if len(values) != len(pairs):
        raise ValueError("FIXED_QUESTION_STARTUP_DUPLICATE_KEY")
    return values


class StartupConfiguration(StrictValue):
    schemaVersion: Literal["fixed-question-startup.v1"]
    enabled: bool = False
    questionPolicy: PinnedFile
    policySetConfiguration: PinnedFile
    servicePolicyDigest: str = Field(pattern=r"^[a-f0-9]{64}$")


class StartedQuestionOwner:
    def __init__(self, assembly, composition):
        self.assembly, self.composition = assembly, composition
        self.closed = False

    def close(self):
        if not self.closed:
            self.closed = True
            self.assembly.close()


def policy_set_factory(path, environment):
    # Fixed import, never a configurable plugin name. Dependency is opt-in only.
    from agent_operator.native_host_policy_set_assembly import PolicySetAssembly
    from agent_operator.native_host_policy_set_config import PolicySetConfiguration

    return PolicySetAssembly(PolicySetConfiguration(path, environment=environment))


def configure(environment, services, *, factory=policy_set_factory):
    path = environment.get("FIXED_QUESTION_DELEGATION_CONFIGURATION")
    sha = environment.get("FIXED_QUESTION_DELEGATION_CONFIGURATION_SHA256")
    if not path and not sha:
        return None
    pin = PinnedFile(path=path, sha256=sha)
    raw = read_pin(pin)
    configuration = StartupConfiguration.model_validate(
        json.loads(raw, object_pairs_hook=unique)
    )
    if not configuration.enabled:
        return None
    policy = FixedQuestionPolicy.model_validate(
        json.loads(read_pin(configuration.questionPolicy), object_pairs_hook=unique)
    )
    if not policy.enabled or datetime.now(UTC) >= policy.expiresAt:
        raise ValueError("FIXED_QUESTION_POLICY_NOT_ENABLED")
    scopes = {
        (s.tenantId, s.securityDomain, s.executionSubject, s.serviceCredentialId)
        for s in policy.scopes
    }
    if len(scopes) != 1:
        raise ValueError("FIXED_QUESTION_SINGLE_SERVICE_LEAF_REQUIRED")
    tenant, domain, subject, credential = next(iter(scopes))
    read_pin(configuration.policySetConfiguration)
    settlement = settlement_reader_for_services(*services)
    if not callable(settlement):
        raise ValueError("FIXED_QUESTION_TYPED_UNDERSTANDING_REQUIRED")
    try:
        assembly = factory(configuration.policySetConfiguration.path, dict(environment))
    except (ImportError, TypeError) as exc:
        raise ValueError("FIXED_QUESTION_STARTUP_ASSEMBLY_UNAVAILABLE") from exc
    try:
        # Recheck before binding any API capability, including constructor gaps.
        if read_pin(pin) != raw:
            raise ValueError("FIXED_QUESTION_STARTUP_PIN_CHANGED")
        read_pin(configuration.questionPolicy)
        read_pin(configuration.policySetConfiguration)
        leaf = assembly.service_leaf(
            (tenant, domain),
            credential_id=credential,
            policy_digest=configuration.servicePolicyDigest,
        )
        runtime = leaf.runtime
        expected = NativeTypedQuestionDocumentSkillExecutor.revision
        wait = runtime.durable_wait
        if (
            runtime.subject != subject
            or wait is None
            or not getattr(wait, "typedQuestions", False)
            or (
                wait.executorId,
                wait.executorRevision,
                wait.executorConfigurationDigest,
            )
            != (
                expected.executor_id,
                expected.executor_revision,
                expected.configuration_digest,
            )
        ):
            raise ValueError("FIXED_QUESTION_TYPED_DOCUMENT_RUNTIME_REQUIRED")
        bridge = leaf.work.bound_service_execution
        composition = FixedQuestionComposition(
            policy,
            bridge.registry,
            runtime,
            leaf.execution_repository,
            leaf.work,
            settlement_reader=settlement,
            clock=lambda: datetime.now(UTC),
        )
        return StartedQuestionOwner(assembly, composition)
    except (ImportError, TypeError) as exc:
        assembly.close()
        raise ValueError("FIXED_QUESTION_STARTUP_BINDING_INVALID") from exc
    except BaseException:
        assembly.close()
        raise
