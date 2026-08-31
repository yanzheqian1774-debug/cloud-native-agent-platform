"""Private Knowledge Workbench API schemas."""

from typing import Any

from pydantic import BaseModel


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


class KnowledgeResponse(BaseModel):
    knowledge: dict[str, Any]
    productProjection: dict[str, Any]
    technicalProjection: dict[str, Any]
