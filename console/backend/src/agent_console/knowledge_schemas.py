"""Private Knowledge Workbench API schemas."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class KnowledgeSourceInput(BaseModel):
    sourceId: str
    documentId: str
    kind: str = "TEXT"
    provenance: str
    content: str


class CreateKnowledge(BaseModel):
    name: str
    source: KnowledgeSourceInput


class VersionCommand(BaseModel):
    expectedVersion: int


class DigestCommand(VersionCommand):
    digest: str


class PurgeCommand(VersionCommand):
    authorizationId: str
    reasonClassification: str


class SuccessorCommand(VersionCommand):
    content: str


class RetrievalCommand(VersionCommand):
    authorization: str
    authorizationDecisionId: str
    query: str


class KnowledgeResponse(BaseModel):
    knowledge: dict[str, Any]
    productProjection: dict[str, Any]
    technicalProjection: dict[str, Any]


class SearchCommand(StrictModel):
    query: str
    mode: str = "HYBRID"
    topK: int = Field(default=5, ge=1, le=20)
    knowledgeId: str | None = None
    sourceId: str | None = None
    documentId: str | None = None
    contentType: str | None = None
    revisionId: str | None = None
    snapshotId: str | None = None


class EvaluationCommand(StrictModel):
    datasetVersion: str = "1"
    mode: str = "HYBRID"
    topK: int = Field(default=5, ge=1, le=20)
    cases: list[dict[str, Any]]
    comparisonToRunId: str | None = None
    knowledgeRevision: str = "CURRENT_AUTHORIZED"
    qdrantSnapshotIdentity: str = "AUTHORIZED_ACTIVE_SNAPSHOTS"


class ImportPreviewCommand(StrictModel):
    format: str
    content: str


class DuplicateDecisionCommand(StrictModel):
    candidateId: str
    classification: str
