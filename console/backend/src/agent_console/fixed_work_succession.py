"""Exact configuration-update preview, never authority to save or execute."""

from copy import deepcopy
from dataclasses import asdict
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field

from .digital_employee_definition import digest
from .plan_suggestion_domain import ExactReference
from .workbench_bff_schemas import StrictWorkbenchModel
from .workbench_owner_authorization import WorkbenchOwnerError


class SuccessionCommand(StrictWorkbenchModel):
    predecessor: ExactReference
    predecessorHandoffDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    team: ExactReference
    commandId: str = Field(min_length=1, max_length=200)
    previewDigest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


def require(ok, reason):
    if not ok:
        raise WorkbenchOwnerError("FIXED_WORK_SUCCESSION_" + reason, 409)


def preview(saved, handoff, old_team, new_team, subject, conversation):
    """Owner supplies current, authorized rows; this does not prove current rights.

    The first transition changes exact team/member resource versions only. The
    original instruction and schedule are preserved, not reconstructed by a model.
    The transaction owner must also prove the original conversation is empty and
    never bound/started under shared locks before saving any successor.
    """
    old = saved["record"]
    work = ExactReference(
        resource_id=old["workId"], revision_id=old["revisionId"], digest=saved["digest"]
    )
    h = handoff["record"]
    old_ref = {
        "teamId": old_team.team_id,
        "revisionId": old_team.revision_id,
        "digest": old_team.content_digest,
    }
    require(digest(old) == work.digest, "WORK_CHANGED")
    require(
        digest(h) == handoff["digest"]
        and h["schemaVersion"]
        in {"fixed-work-conversation.v1", "fixed-work-conversation.v2"}
        and h["work"] == work.model_dump(mode="json")
        and h["team"] == old["team"] == old_ref
        and h["subjectId"] == old["createdBy"] == subject
        and h["conversationId"] == conversation
        and h["instructionDigest"] == digest(old["instruction"])
        and h["mode"] == "TARGET_REVIEW_ONLY"
        and h["executionEnabled"] is False,
        "ORIGINAL_SOURCE_CHANGED",
    )
    require(
        new_team.scope == old_team.scope
        and new_team.team_id == old_team.team_id
        and new_team.predecessor_revision_id == old_team.revision_id
        and new_team.revision_id != old_team.revision_id,
        "EXACT_TEAM_SUCCESSOR_REQUIRED",
    )
    require(
        not old_team.work_links and not new_team.work_links,
        "EXISTING_WORK_LINK_REQUIRES_SEPARATE_TRANSITION",
    )
    old_members = {m.employee_definition_id: m for m in old_team.members}
    new_members = {m.employee_definition_id: m for m in new_team.members}
    members = []
    for identity in sorted(old_members.keys() | new_members.keys()):
        before, after = old_members.get(identity), new_members.get(identity)
        if before != after:
            members.append(
                {
                    "employeeDefinitionId": identity,
                    "before": asdict(before) if before else None,
                    "after": asdict(after) if after else None,
                }
            )
    return {
        "schemaVersion": "fixed-work-succession-preview.v1",
        "predecessor": work.model_dump(mode="json"),
        "predecessorHandoffDigest": handoff["digest"],
        "subjectId": subject,
        "conversationId": conversation,
        "teamBefore": old_ref,
        "teamAfter": {
            "teamId": new_team.team_id,
            "revisionId": new_team.revision_id,
            "digest": new_team.content_digest,
        },
        "teamChanges": {
            field: {
                "before": getattr(old_team, field),
                "after": getattr(new_team, field),
            }
            for field in ("title", "goal", "owner_id")
            if getattr(old_team, field) != getattr(new_team, field)
        },
        "memberChanges": members,
        "preserved": deepcopy({k: old[k] for k in ("title", "instruction", "trigger")}),
        "effectivePoint": "BEFORE_FIRST_TARGET_ONLY",
        "configurationOnly": True,
        "executionEnabled": False,
        "currentOwnerChecksRequired": True,
    }


def successor_ids(scope, logical_work_id, command_id):
    """Stable internal identities; a retry cannot create another visible clone."""
    seed = digest((tuple(scope), logical_work_id, command_id))
    return (
        "fixed-work:" + str(uuid5(NAMESPACE_URL, "fixed-work-successor:" + seed)),
        "fixed-revision:" + str(uuid5(NAMESPACE_URL, "fixed-work-revision:" + seed)),
    )
