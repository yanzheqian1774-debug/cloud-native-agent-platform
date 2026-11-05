"""No owner writes; operation resolution and explicit member boundaries."""

from copy import deepcopy

import pytest
from agent_console.pending_member_requirements import resolve
from agent_console.plan_suggestion_domain import ExactReference, FlexiblePlanSemantics
from test_planning_contracts import modern


def sample():
    doc = modern(("READ_DATA", "RENDER_REPORT"))
    doc["requirements"] = [r for r in doc["requirements"] if r["kind"] == "EMPLOYEE"]
    proto = doc["requirements"][0]
    doc["requirements"].append(
        {
            **proto,
            "requirement_id": "skill",
            "kind": "SKILL",
            "required": True,
            "selected": None,
        }
    )
    for t in doc["tasks"]:
        t["requirement_ids"] = ["skill"]
    skill = ExactReference(
        resource_id="skill:inside", revision_id="revision:1", digest="a" * 64
    )
    member = {
        "kind": "SKILL",
        "resource_id": skill.resource_id,
        "revision_id": skill.revision_id,
        "digest": skill.digest,
    }
    content = {"operations": [{"name": "READ_DATA"}, {"name": "RENDER_REPORT"}]}
    return doc, member, skill, content


def test_missing_and_ambiguous_and_foreign_are_not_filled_by_developer():
    doc, m, ref, content = sample()
    sem = FlexiblePlanSemantics.model_validate(doc)
    with pytest.raises(ValueError, match="UNAVAILABLE"):
        resolve(sem, [], {})
    second = {**m, "resource_id": "skill:second"}
    other = ExactReference(
        resource_id=second["resource_id"],
        revision_id=ref.revision_id,
        digest=ref.digest,
    )
    with pytest.raises(ValueError, match="AMBIGUOUS"):
        resolve(sem, [m, second], {"_skills": [(ref, content), (other, content)]})
    doc["requirements"][-1]["selected"] = {
        **ref.model_dump(),
        "revision_id": "revision:changed",
    }
    with pytest.raises(ValueError, match="MAPPING_MISMATCH"):
        resolve(
            FlexiblePlanSemantics.model_validate(doc),
            [m],
            {"_skills": [(ref, content)]},
        )


def test_pending_resolution_does_not_mutate_input_or_weaken_task_membership():
    doc, m, ref, content = sample()
    sem = FlexiblePlanSemantics.model_validate(doc)
    before = deepcopy(doc)
    value, bindings = resolve(sem, [m], {"_skills": [(ref, content)]})
    assert doc == before and sem.requirements[-1].selected is None
    assert value.requirements[-1].selected == ref
    assert bindings[-1]["basis"] == "SYSTEM_EXACT_MEMBER_CONTRACT"
