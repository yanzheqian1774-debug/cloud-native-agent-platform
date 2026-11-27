"""Exact new Service scope and unchanged v1 semantics, without network effects."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthenticationSource, AuthorityError
from agent_console.plan_suggestion_domain import ExactReference
from agent_console.readonly_continuation_policy import ReadonlyContinuationPolicy
from agent_console.readonly_native_policy import (
    ReadonlyContinuationPolicyV2,
    require_preparation,
    require_ready,
    require_source,
)
from agent_console.resource_use_domain import canonical_digest
from test_owned_native_business_policy import candidate


def value():
    owned, content = candidate()
    source = owned["scopes"][0]

    def ref(kind):
        return dict(resource_id=kind, revision_id="r", digest="a" * 64)

    work = dict(
        namespace="test",
        securityDomain="isolated",
        subject="service:cycle",
        problem=ref("problem"),
        sourceContentDigests=[source["sourceContentDigest"]],
        case="native_readonly",
        nativeAgentName="native-test",
        expiresAt=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        adapter=source["adapter"],
        source=source["source"],
        skill=ref("skill"),
        employee=ref("employee"),
        agent=ref("agent"),
        runtime=ref("runtime"),
    )
    return dict(
        schemaVersion="readonly-work-policy.v2",
        policyId="test",
        policyVersion="2",
        enabled=True,
        works=[work],
    ), content


def test_explicit_v2_and_legacy_digest_remain_separate(tmp_path):
    raw, _ = value()
    with pytest.raises(ValueError):
        ReadonlyContinuationPolicy.model_validate(raw)
    path = tmp_path / "policy.json"
    import json

    path.write_text(json.dumps(raw))
    current = ReadonlyContinuationPolicy.load(path)
    assert isinstance(current, ReadonlyContinuationPolicyV2)
    legacy = deepcopy(raw)
    legacy["schemaVersion"] = "readonly-work-policy.v1"
    legacy["works"][0]["case"] = "delivery"
    for key in ("adapter", "source", "skill", "employee", "agent", "runtime"):
        legacy["works"][0].pop(key)
    old = ReadonlyContinuationPolicy.model_validate(legacy)
    path.write_text(json.dumps(legacy))
    assert ReadonlyContinuationPolicy.load(path) == old
    assert old.digest == canonical_digest(
        old.model_dump(mode="json", exclude_none=True)
    )
    legacy["schemaVersion"] = "readonly-work-policy.v3"
    path.write_text(json.dumps(legacy))
    with pytest.raises(ValueError):
        ReadonlyContinuationPolicy.load(path)


def test_service_identity_exact_source_and_ready_members():
    raw, content = value()
    policy = ReadonlyContinuationPolicyV2.model_validate(raw)
    work = policy.works[0]
    context = SimpleNamespace(
        principal_id=work.subject,
        scope=SimpleNamespace(
            tenant_id=work.namespace, security_domain=work.securityDomain
        ),
        authentication_source=AuthenticationSource.SERVICE_CREDENTIAL,
    )
    assert (
        policy.work(
            context, work.problem, work.sourceContentDigests[0], datetime.now(UTC)
        )
        == work
    )
    context.authentication_source = AuthenticationSource.BROWSER_SESSION
    with pytest.raises(AuthorityError):
        policy.work(
            context, work.problem, work.sourceContentDigests[0], datetime.now(UTC)
        )
    require_source(work, work.source, content)
    with pytest.raises(AuthorityError):
        require_source(
            work, work.source.model_copy(update={"revision_id": "other"}), content
        )
    ready = dict(
        resources=[
            dict(kind=k, reference=v.model_dump(mode="json"))
            for k, v in (
                ("knowledge", work.source),
                ("skill", work.skill),
                ("agent", work.agent),
                ("runtime", work.runtime),
            )
        ],
        assembly=dict(definition=work.employee.model_dump(mode="json")),
    )
    require_ready(work, ready)
    ready["resources"][1]["reference"]["digest"] = "f" * 64
    with pytest.raises(AuthorityError):
        require_ready(work, ready)


@pytest.mark.parametrize(
    "field,change",
    [("adapterRevision", "999"), ("externalWrites", True), ("operations", ["START"])],
)
def test_unregistered_or_write_adapter_cannot_become_policy(field, change):
    raw, _ = value()
    raw["works"][0]["adapter"][field] = change
    with pytest.raises(ValueError):
        ReadonlyContinuationPolicyV2.model_validate(raw)


def test_preparation_cannot_rebind_saved_service_scope():
    raw, _ = value()
    work = ReadonlyContinuationPolicyV2.model_validate(raw).works[0]
    from agent_console.native_data_skill import executors

    executor = next(
        e
        for e in executors()
        if e.adapter.descriptor() == work.adapter.model_dump(mode="json")
    ).revision
    participant = SimpleNamespace(
        executor_id=executor.executor_id,
        executor_revision=executor.executor_revision,
        executor_digest=executor.configuration_digest,
        definition=work.employee,
        skill=SimpleNamespace(reference=work.skill, operation="READ_DATA"),
        profile=work.runtime,
        resources=(SimpleNamespace(kind="KNOWLEDGE", reference=work.source),),
    )
    prepared = SimpleNamespace(
        semantics=SimpleNamespace(target=SimpleNamespace(problem=work.problem)),
        participants=(participant,),
    )
    receipt = {"nativeServiceScopeDigest": work.binding_digest}
    require_preparation(work, prepared, receipt)
    participant.skill.reference = ExactReference(
        resource_id="other", revision_id="r", digest="a" * 64
    )
    with pytest.raises(AuthorityError):
        require_preparation(work, prepared, receipt)
