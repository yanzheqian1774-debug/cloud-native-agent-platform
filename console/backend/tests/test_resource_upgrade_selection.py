"""Selected upgrades cannot lose duties or change unrelated fixed bindings."""

from dataclasses import replace

import pytest
from agent_console.business_capability import FixedReference
from agent_console.digital_employee_definition import (
    CompositionMember,
    MemberKind,
    ResponsibilityBinding,
)
from agent_console.execution_domain import ScopeIdentity
from agent_console.resource_upgrade_selection import (
    SelectedReplacement,
    UpgradeSelectionError,
    capability_successor,
    employee_successor,
)
from test_business_capability import capability
from test_digital_employee_definition import revision


def selection(scope):
    return SelectedReplacement(
        scope,
        "SKILL",
        FixedReference("skill:test", "revision:1", "a" * 64),
        FixedReference("skill:test", "revision:2", "b" * 64),
    )


def employee():
    base = revision()
    skill = CompositionMember(MemberKind.SKILL, "skill:test", "revision:1", "a" * 64)
    knowledge = CompositionMember(
        MemberKind.KNOWLEDGE, "knowledge:test", "v1", "c" * 64
    )
    return replace(
        base,
        members=(*base.members, skill, knowledge),
        responsibility_bindings=(
            ResponsibilityBinding(base.responsibilities[0], skill),
            ResponsibilityBinding(base.responsibilities[0], knowledge),
        ),
        responsibility_bindings_explicit=True,
    )


def test_employee_preserves_duties_and_unselected_member_while_rebinding_skill():
    original = employee()
    snapshot = original.record
    new = employee_successor(original, "employee:new", (selection(original.scope),))
    assert original.record == snapshot
    assert new.role == original.role
    assert new.responsibilities == original.responsibilities
    assert new.members[0] == original.members[0]
    assert new.members[2] == original.members[2]
    assert new.members[1].revision_id == "revision:2"
    assert new.responsibility_bindings[0].member == new.members[1]
    assert new.responsibility_bindings[1] == original.responsibility_bindings[1]
    assert new.predecessor_revision_id == original.revision_id
    assert new.digest != original.digest


def test_capability_preserves_business_content_origin_and_unselected_bindings():
    original = capability()
    new = capability_successor(original, "capability:new", (selection(original.scope),))
    before, after = original.canonical_record(), new.canonical_record()
    for key in before:
        if key not in {"revision_id", "predecessor_revision_id", "bindings"}:
            assert before[key] == after[key]
    assert new.bindings[0] == original.bindings[0]
    assert new.bindings[2] == original.bindings[2]
    assert new.bindings[1].purpose == original.bindings[1].purpose
    assert new.bindings[1].reference.revision_id == "revision:2"


@pytest.mark.parametrize(
    "builder,source",
    [(employee_successor, employee), (capability_successor, capability)],
)
@pytest.mark.parametrize(
    "field,value", [("revision_id", "other:revision"), ("digest", "d" * 64)]
)
def test_selected_old_version_or_digest_mismatch_never_silently_switches(
    builder, source, field, value
):
    original = source()
    chosen = selection(original.scope)
    chosen = replace(chosen, before=replace(chosen.before, **{field: value}))
    with pytest.raises(UpgradeSelectionError, match="ORIGINAL_REFERENCE_MISMATCH"):
        builder(original, "new:revision", (chosen,))


def test_duplicate_or_cross_scope_selection_rejected_before_successor():
    original = capability()
    chosen = selection(original.scope)
    with pytest.raises(UpgradeSelectionError, match="DUPLICATE_SELECTION"):
        capability_successor(original, "new:revision", (chosen, chosen))
    with pytest.raises(UpgradeSelectionError, match="SCOPE_MISMATCH"):
        capability_successor(
            original,
            "new:revision",
            (replace(chosen, scope=ScopeIdentity("other", "scope")),),
        )


def test_identity_change_and_unchanged_revision_cannot_masquerade_as_upgrade():
    chosen = selection(capability().scope)
    with pytest.raises(UpgradeSelectionError, match="IDENTITY_CHANGED"):
        replace(chosen, after=replace(chosen.after, resource_id="skill:unselected"))
    with pytest.raises(UpgradeSelectionError, match="NEW_REVISION_REQUIRED"):
        replace(
            chosen, after=replace(chosen.after, revision_id=chosen.before.revision_id)
        )


def test_no_selected_reference_cannot_create_spurious_successor():
    original = capability()
    chosen = selection(original.scope)
    chosen = replace(
        chosen,
        before=replace(chosen.before, resource_id="skill:absent"),
        after=replace(chosen.after, resource_id="skill:absent"),
    )
    with pytest.raises(UpgradeSelectionError, match="NO_SELECTED_REFERENCE"):
        capability_successor(original, "new:revision", (chosen,))


@pytest.mark.parametrize("kind", ["MCP", "KNOWLEDGE"])
def test_exact_replacement_preserves_employee_duties_and_skill_reference(kind):
    original = employee()
    mcp = CompositionMember(MemberKind(kind), "resource:test", "revision:1", "a" * 64)
    original = replace(
        original,
        members=(*original.members, mcp),
        responsibility_bindings=(
            *original.responsibility_bindings,
            ResponsibilityBinding(original.responsibilities[0], mcp),
        ),
    )
    chosen = SelectedReplacement(
        original.scope,
        kind,
        FixedReference("resource:test", "revision:1", "a" * 64),
        FixedReference("resource:test", "revision:2", "b" * 64),
    )
    updated = employee_successor(original, "employee:mcp-new", (chosen,))
    assert updated.members[:-1] == original.members[:-1]
    assert updated.members[-1].revision_id == "revision:2"
    assert updated.responsibility_bindings[-1].member == updated.members[-1]
    with pytest.raises(UpgradeSelectionError, match="ORIGINAL_REFERENCE_MISMATCH"):
        employee_successor(
            original,
            "employee:bad",
            (replace(chosen, before=replace(chosen.before, digest="c" * 64)),),
        )


def test_skill_selection_canonical_record_stays_compatible_and_mcp_is_separate():
    from dataclasses import asdict

    from agent_console.resource_upgrade_preview import UpgradeSelection

    chosen = selection(capability().scope)
    legacy = UpgradeSelection(chosen.before, chosen.after, (), ())
    expected = asdict(legacy)
    expected.pop("resource_kind")
    assert legacy.record() == expected
    assert replace(legacy, resource_kind="mcp").record() == {
        **expected,
        "resource_kind": "mcp",
    }


def test_knowledge_root_grant_uses_existing_knowledge_owner():
    from agent_console.workbench_resource_upgrade import root_grant

    ref = {
        "resourceId": "knowledge:test",
        "revisionId": "revision:new",
        "digest": "a" * 64,
    }
    (grant,) = root_grant(
        None,
        {},
        {
            "resourceKind": "knowledge",
            "oldSkill": {**ref, "revisionId": "revision:old"},
            "newSkill": ref,
        },
        {},
    )
    assert grant.owner == "KNOWLEDGE"
    assert grant.exact_resource == "knowledge:resource-management:knowledge:test"
