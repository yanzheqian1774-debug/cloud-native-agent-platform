"""Explicit Service-only native capability policy; v1 remains unchanged."""

import json
from typing import Literal

from pydantic import Field

from .authority_contracts import AuthenticationSource, AuthorityError
from .native_data_adapters import resolve
from .native_data_skill import exact_executor
from .native_readonly_protocol import NativeReadonlyWork
from .plan_suggestion_domain import ExactReference
from .readonly_continuation_policy import ReadonlyContinuationPolicy, ReadonlyWork
from .resource_automation_policy import source_digest
from .resource_use_domain import canonical_digest
from .skill_invocation_domain import ExecutorRevision


def require(ok):
    if not ok:
        raise AuthorityError("READONLY_NATIVE_SERVICE_BINDING_INVALID")


class ServiceNativeReadonlyWork(NativeReadonlyWork):
    subject: str = Field(pattern=r"^service:.+$")
    sourceContentDigests: tuple[str, ...] = Field(min_length=1, max_length=1)
    source: ExactReference
    skill: ExactReference
    employee: ExactReference
    agent: ExactReference
    runtime: ExactReference

    @property
    def binding_digest(self):
        return canonical_digest(self.model_dump(mode="json", exclude_none=True))


class ReadonlyContinuationPolicyV2(ReadonlyContinuationPolicy):
    schemaVersion: Literal["readonly-work-policy.v2"]
    works: tuple[ReadonlyWork | ServiceNativeReadonlyWork, ...] = Field(max_length=128)

    def work(self, context, root, source_digest, now):
        selected = super().work(context, root, source_digest, now)
        if isinstance(selected, ServiceNativeReadonlyWork):
            require(
                context.authentication_source == AuthenticationSource.SERVICE_CREDENTIAL
            )
        return selected


def require_source(work, reference, content):
    if not isinstance(work, ServiceNativeReadonlyWork):
        return
    require(
        reference == work.source and source_digest(content) in work.sourceContentDigests
    )
    try:
        data = json.loads(content["documents"][0]["chunks"][0]["content"])
        resolve(work.adapter.model_dump(mode="json")).validate(data)
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise AuthorityError("READONLY_NATIVE_SERVICE_SOURCE_INVALID") from exc


def require_ready(work, ready):
    if not isinstance(work, ServiceNativeReadonlyWork):
        return
    expected = {
        "knowledge": work.source,
        "skill": work.skill,
        "agent": work.agent,
        "runtime": work.runtime,
    }
    rows = ready.get("resources", ())
    require(len(rows) == len(expected))
    actual = {
        row["kind"]: ExactReference.model_validate(row["reference"]) for row in rows
    }
    require(actual == expected)
    require(
        ExactReference.model_validate(ready["assembly"]["definition"]) == work.employee
    )


def require_preparation(work, prepared, receipt):
    if not isinstance(work, ServiceNativeReadonlyWork):
        return
    require(receipt.get("nativeServiceScopeDigest") == work.binding_digest)
    require_prepared_members(work, prepared)


def require_prepared_members(work, prepared):
    if not isinstance(work, ServiceNativeReadonlyWork):
        return
    require(prepared.semantics.target.problem == work.problem)
    for participant in prepared.participants:
        try:
            registered = exact_executor(
                ExecutorRevision(
                    participant.executor_id,
                    participant.executor_revision,
                    participant.executor_digest,
                )
            )
        except ValueError as exc:
            raise AuthorityError("READONLY_NATIVE_SERVICE_BINDING_INVALID") from exc
        require(registered.adapter.descriptor() == work.adapter.model_dump(mode="json"))
        require(
            participant.definition == work.employee
            and participant.skill.reference == work.skill
        )
        require(participant.profile == work.runtime)
        require(
            tuple((r.kind, r.reference) for r in participant.resources)
            == (("KNOWLEDGE", work.source),)
        )
        require(participant.skill.operation in work.adapter.operations)
