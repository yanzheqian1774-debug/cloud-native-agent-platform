"""Revalidate capability provenance before the existing confirmation owner writes."""

from pydantic import BaseModel, Field, model_validator

from .capability_conversation_source import verify_work_association
from .capability_execution_constraints import verify_plan
from .workbench_owner_authorization import WorkbenchOwnerError


class CapabilityPlanSource(BaseModel):
    capabilityConversationId: str | None = Field(
        default=None, min_length=1, max_length=128
    )
    capabilityMessageId: str | None = Field(default=None, min_length=1, max_length=128)
    capabilityContractDigest: str | None = Field(
        default=None, pattern=r"^[a-f0-9]{64}$"
    )

    @model_validator(mode="after")
    def complete_source(self):
        values = (
            self.capabilityConversationId,
            self.capabilityMessageId,
            self.capabilityContractDigest,
        )
        if any(v is not None for v in values) and not all(
            v is not None for v in values
        ):
            raise ValueError("CAPABILITY_CONFIRMATION_REFERENCE_INCOMPLETE")
        return self


def validate_source(automation, call, request, proposal, current):
    marked = any(
        "capabilityContractDigest" in (criterion.get("applicability") or {})
        for criterion in current["criteria"]
    )
    if request.capabilityConversationId is None:
        if marked:
            raise WorkbenchOwnerError("CAPABILITY_CONFIRMATION_SOURCE_REQUIRED", 409)
        return
    reader = getattr(automation, "capability_contract_reader", None)
    if reader is None:
        raise WorkbenchOwnerError("CAPABILITY_CONTRACT_READER_UNAVAILABLE", 503)
    resolved = reader(
        call, request.capabilityConversationId, request.capabilityMessageId
    )
    if resolved["contractDigest"] != request.capabilityContractDigest:
        raise WorkbenchOwnerError("CAPABILITY_CONTRACT_DIGEST_MISMATCH", 409)
    verify_work_association(
        call, resolved, proposal.semantics.target.problem.model_dump(mode="json")
    )
    verify_plan(resolved, proposal, current)

    return resolved
