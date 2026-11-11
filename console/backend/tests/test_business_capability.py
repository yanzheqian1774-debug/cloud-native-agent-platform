"""Business capability semantics preserve real origins and fixed reference kinds."""

from dataclasses import replace

import pytest
from agent_console.business_capability import (
    BindingKind,
    BusinessCapabilityError,
    BusinessCapabilityRevision,
    CapabilityBinding,
    CapabilityOrigin,
    FixedReference,
    OriginKind,
)
from agent_console.execution_domain import ScopeIdentity


def capability():
    return BusinessCapabilityRevision(
        scope=ScopeIdentity("test-capability", "isolated"),
        capability_id="business-capability:handover",
        revision_id="capability-revision:1",
        title="检查交接材料",
        intent="核对交接说明是否完整",
        inputs="交接说明、适用规范",
        outputs="缺口和原文依据",
        business_scope="材料完整性",
        exclusions="不执行上线或回退",
        manual_involvement="规范不明时集中追问",
        acceptance_criteria=("检查全部原文并标明缺失项",),
        known_limitations="完整性不代表技术正确",
        origin=CapabilityOrigin(OriginKind.INDEPENDENT),
        bindings=tuple(
            CapabilityBinding(
                kind,
                FixedReference(kind.lower() + ":test", "revision:1", "a" * 64),
                "检查材料" if kind is BindingKind.EMPLOYEE else "提供检查依据",
            )
            for kind in (BindingKind.EMPLOYEE, BindingKind.SKILL, BindingKind.KNOWLEDGE)
        ),
    )


def test_independent_and_workflow_origins_roundtrip_without_fabricated_source():
    original = capability()
    assert original.origin.workflow is None
    assert (
        BusinessCapabilityRevision.from_record(original.canonical_record()) == original
    )
    workflow = replace(
        original,
        origin=CapabilityOrigin(
            OriginKind.WORKFLOW_REVISION,
            workflow=FixedReference("workflow:test", "revision:1", "b" * 64),
        ),
    )
    saved = replace(
        original,
        origin=CapabilityOrigin(
            OriginKind.SAVED_PREPARATION, preparation_digest="c" * 64
        ),
    )
    for value in (workflow, saved):
        assert BusinessCapabilityRevision.from_record(value.canonical_record()) == value
        assert value.content_digest != original.content_digest


def test_fixed_employee_and_multikind_changes_affect_digest():
    original = capability()
    member = original.bindings[1]
    changed = replace(
        member, reference=replace(member.reference, revision_id="revision:2")
    )
    successor = replace(
        original, bindings=(original.bindings[0], changed, original.bindings[2])
    )
    assert successor.content_digest != original.content_digest
    assert original.bindings[1].reference.revision_id == "revision:1"
    with pytest.raises(BusinessCapabilityError, match="EMPLOYEE_REQUIRED"):
        replace(original, bindings=original.bindings[1:])
    with pytest.raises(BusinessCapabilityError, match="BINDING_DUPLICATE"):
        replace(original, bindings=(*original.bindings, changed))


@pytest.mark.parametrize(
    "change",
    [
        {"schemaVersion": "unknown"},
        {"unknownField": "must not be dropped"},
        {"acceptance_criteria": "not a collection"},
        {"origin": {"kind": "INDEPENDENT", "preparation_digest": "a" * 64}},
        {"origin": {"kind": "WORKFLOW_REVISION"}},
        {"bindings": [{"kind": "AGENT", "reference": {}, "purpose": "not Employee"}]},
    ],
)
def test_corrupt_or_ambiguous_persisted_records_fail_closed(change):
    record = capability().canonical_record()
    record.update(change)
    with pytest.raises(BusinessCapabilityError, match="RECORD_CORRUPT"):
        BusinessCapabilityRevision.from_record(record)
