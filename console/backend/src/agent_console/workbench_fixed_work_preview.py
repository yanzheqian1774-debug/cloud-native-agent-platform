"""Advisory natural-language configuration preview, original authoring READ gate.

This operation cannot save configuration, approve a model, or start a cycle.
Confirmation remains the original SaveDraft command and its current REVISE/CAS.
"""

from dataclasses import replace

from pydantic import Field

from .digital_employee_definition import digest
from .fixed_work_natural_preview import preview_instruction
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_bff_schemas import StrictWorkbenchModel
from .workbench_fixed_work import grants
from .workbench_owner_authorization import WorkbenchOwnerError


class FixedPreviewReference(StrictWorkbenchModel):
    workId: str = Field(min_length=1, max_length=200)
    revisionId: str = Field(min_length=1, max_length=200)
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class PreviewFixedInstruction(StrictWorkbenchModel):
    instruction: str = Field(min_length=1, max_length=4000)
    title: str | None = Field(default=None, max_length=120)
    previous: FixedPreviewReference | None = None


class FixedWorkPreviewOwner:
    def __init__(self, authoring):
        self.authoring = authoring

    def __call__(self, call):
        body = PreviewFixedInstruction.model_validate(call.payload)
        # Existing collection reader performs current exact team identity/digest,
        # policy/subject/expiry/READ checks. One bounded row, no new discovery scope.
        directory = self.authoring(
            replace(
                call,
                operation="LIST_FIXED_WORK_DRAFTS",
                payload={},
                query={"pageSize": 1},
            )
        )
        previous = None
        if body.previous:
            previous = self.authoring(
                replace(
                    call,
                    operation="READ_FIXED_WORK_DRAFT",
                    payload={},
                    query={},
                    path={
                        **call.path,
                        "work_id": body.previous.workId,
                        "revision_id": body.previous.revisionId,
                    },
                )
            )
            if previous["digest"] != body.previous.digest:
                raise WorkbenchOwnerError("FIXED_WORK_PREVIEW_BASE_CHANGED", 409)
        try:
            parsed = preview_instruction(
                body.instruction, previous["draft"]["trigger"] if previous else None
            )
        except ValueError as exc:
            raise WorkbenchOwnerError("FIXED_WORK_INSTRUCTION_INVALID", 422) from exc
        # A title label is not semantic interpretation of the business goal.
        title = body.title or (
            previous["draft"]["title"] if previous else body.instruction.strip()[:120]
        )
        return {
            **parsed,
            "team": directory["team"],
            "instructionDigest": digest(body.instruction),
            "previous": body.previous.model_dump() if body.previous else None,
            "previousTitle": previous["draft"]["title"] if previous else None,
            "proposedTitle": title,
            "titleDerivation": "EXPLICIT_FIELD"
            if body.title
            else "UNCHANGED"
            if previous
            else "INSTRUCTION_LABEL",
            "configurationCanSave": directory["configurationCanSave"],
        }


def fixed_work_preview_operations(authoring, *, enabled=False):
    if not enabled:
        return ()
    return (
        WorkbenchOperation(
            "PREVIEW_FIXED_WORK_INSTRUCTION",
            "POST",
            PREFIX + "/teams/{team_id}/revisions/{team_revision_id}/fixed-work-preview",
            PreviewFixedInstruction,
            None,
            grants,
            FixedWorkPreviewOwner(authoring),
        ),
    )
