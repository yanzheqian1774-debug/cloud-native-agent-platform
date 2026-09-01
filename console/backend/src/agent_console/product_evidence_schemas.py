"""Private derived Product/Technical/Evidence traceability schemas."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TraceabilitySubject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(min_length=1)
    resourceId: str = Field(min_length=1)
    revisionId: str = Field(min_length=1)
    digest: str = Field(min_length=1)


class ProductClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claimKey: str
    productLabel: str
    status: str
    limitationCodes: list[str] = []
    evidenceRefs: list[str] = []
    technicalFactKeys: list[str] = []
    affectedBusinessStepIds: list[str] = []


class TraceabilityEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidenceId: str
    evidenceType: str
    subject: TraceabilitySubject
    provenance: dict[str, Any]
    observedAt: str | None = None
    limitationCodes: list[str] = []


class TechnicalFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    factKey: str
    valueClassification: str
    provenance: dict[str, Any]
    affectedClaimKeys: list[str] = []
    affectedBusinessStepIds: list[str] = []


class TraceabilityDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: TraceabilitySubject
    claims: list[ProductClaim]
    evidence: list[TraceabilityEvidence]
    technicalFacts: list[TechnicalFact]
