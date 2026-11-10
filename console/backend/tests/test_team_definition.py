"""Team content invariants, not persistence or end-to-end acceptance."""

from dataclasses import FrozenInstanceError, replace

import pytest
from agent_console.execution_domain import ScopeIdentity
from agent_console.team_definition import TeamDefinitionError, TeamMember, TeamRevision


def team():
    return TeamRevision(
        scope=ScopeIdentity("test-tenant", "isolated"),
        team_id="team:handoff",
        revision_id="team-revision:1",
        title="上线交接核对团队",
        goal="核对材料完整性并保留缺失项",
        owner_id="human:accountable",
        members=(
            TeamMember(
                "employee:reviewer",
                "employee-revision:1",
                "a" * 64,
                "在本团队核对交接材料",
                "交付缺失说明清单",
            ),
        ),
    )


def test_team_local_duties_do_not_change_shared_employee_reference():
    original = team()
    changed = replace(
        original,
        revision_id="team-revision:2",
        predecessor_revision_id=original.revision_id,
        members=(replace(original.members[0], responsibility="核对回退说明"),),
    )
    assert original.members[0].responsibility == "在本团队核对交接材料"
    assert changed.members[0].employee_digest == original.members[0].employee_digest
    assert changed.content_digest != original.content_digest
    with pytest.raises(FrozenInstanceError):
        original.members[0].responsibility = "overwrite"


def test_scope_and_exact_member_revision_are_digest_bound():
    original = team()
    assert (
        replace(original, scope=ScopeIdentity("other", "isolated")).content_digest
        != original.content_digest
    )
    assert (
        replace(
            original,
            members=(
                replace(
                    original.members[0], employee_revision_id="employee-revision:2"
                ),
            ),
        ).content_digest
        != original.content_digest
    )
    assert replace(original).content_digest == original.content_digest


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"members": ()}, "TEAM_MEMBERS_INVALID"),
        ({"title": " "}, "TEAM_TITLE_INVALID"),
        ({"goal": ""}, "TEAM_GOAL_INVALID"),
        ({"scope": None}, "TEAM_SCOPE_REQUIRED"),
        ({"predecessor_revision_id": "team-revision:1"}, "TEAM_PREDECESSOR_INVALID"),
    ],
)
def test_invalid_team_does_not_become_a_definition(changes, code):
    with pytest.raises(TeamDefinitionError, match=code):
        replace(team(), **changes)


def test_same_employee_cannot_appear_twice_even_with_different_revision():
    original = team()
    with pytest.raises(TeamDefinitionError, match="TEAM_MEMBER_DUPLICATE"):
        replace(
            original,
            members=(
                *original.members,
                replace(
                    original.members[0], employee_revision_id="employee-revision:2"
                ),
            ),
        )


def test_member_requires_exact_digest_and_local_duty():
    member = team().members[0]
    with pytest.raises(TeamDefinitionError, match="TEAM_MEMBER_DIGEST_INVALID"):
        replace(member, employee_digest="current")
    with pytest.raises(TeamDefinitionError, match="TEAM_RESPONSIBILITY_INVALID"):
        replace(member, responsibility=" ")


def test_stored_team_roundtrip_and_malformed_records():
    original = team()
    assert TeamRevision.from_record(original.canonical_record()) == original
    for change in (
        {"schemaVersion": "team-definition.v2"},
        {"members": [{"employee_definition_id": "missing-fields"}]},
        {"unexpected": "must-not-be-dropped"},
        {"scope": {}},
    ):
        with pytest.raises(TeamDefinitionError, match="TEAM_RECORD_CORRUPT"):
            TeamRevision.from_record({**original.canonical_record(), **change})


def test_work_reference_is_exact_and_legacy_digest_remains_unchanged():
    from agent_console.digital_employee_definition import digest
    from agent_console.team_definition import TeamWorkReference

    original = team()
    legacy = {
        "schemaVersion": "team-definition.v1",
        "scope": {"namespace": "test-tenant", "security_domain": "isolated"},
        "team_id": "team:handoff",
        "revision_id": "team-revision:1",
        "title": "上线交接核对团队",
        "goal": "核对材料完整性并保留缺失项",
        "owner_id": "human:accountable",
        "members": [
            {
                "employee_definition_id": "employee:reviewer",
                "employee_revision_id": "employee-revision:1",
                "employee_digest": "a" * 64,
                "responsibility": "在本团队核对交接材料",
                "handoff": "交付缺失说明清单",
            }
        ],
        "predecessor_revision_id": None,
    }
    assert original.content_digest == digest(legacy)
    assert replace(original, work_links=()).content_digest == digest(legacy)
    link = TeamWorkReference(
        "run:1", "b" * 64, "problem:1", "problem-revision:1", "c" * 64
    )
    linked = replace(original, work_links=(link,))
    assert linked.canonical_record()["schemaVersion"] == "team-definition.v2"
    assert TeamRevision.from_record(linked.canonical_record()) == linked
    assert (
        linked.content_digest
        != replace(
            linked,
            work_links=(replace(link, problem_revision_id="problem-revision:2"),),
        ).content_digest
    )
    with pytest.raises(TeamDefinitionError, match="TEAM_WORK_DUPLICATE"):
        replace(original, work_links=(link, link))
    with pytest.raises(TeamDefinitionError, match="TEAM_RECORD_CORRUPT"):
        TeamRevision.from_record({**legacy, "work_links": []})
    with pytest.raises(TeamDefinitionError, match="TEAM_RECORD_CORRUPT"):
        TeamRevision.from_record({**linked.canonical_record(), "work_links": []})
