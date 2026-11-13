"""Opt-in, exact standing-policy approval in the existing Model owner."""

import hashlib
import json
import os
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .model_governance import ModelGovernanceError, canonical_payload

DEADLINE = datetime.fromisoformat("2026-12-12T23:30:12.350586+00:00")


def digest(value):
    return hashlib.sha256(canonical_payload(value)).hexdigest()


def require(condition, reason="BINDING_INVALID"):
    if not condition:
        raise ModelGovernanceError("MODEL_POLICY_" + reason)


class ExactModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    modelId: str = Field(min_length=1, max_length=200)
    revisionId: str = Field(min_length=1, max_length=200)
    digest: str = Field(pattern="^[a-f0-9]{64}$")


class PinnedFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: str
    sha256: str = Field(pattern="^[a-f0-9]{64}$")

    def bytes(self):
        path = Path(self.path)
        require(path.is_absolute() and not path.is_symlink(), "EVIDENCE_INVALID")
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == self.sha256, "EVIDENCE_CHANGED")
        return raw

    def read(self):
        return json.loads(self.bytes())


class ExactProvider(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    providerId: str
    revisionId: str
    digest: str = Field(pattern="^[a-f0-9]{64}$")
    adapterContractId: str
    adapterContractRevisionId: str


class ModelPublicationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: Literal["model-standing-publication.v1"]
    enabled: bool = False
    policyId: str = Field(min_length=1, max_length=200)
    policyVersion: str = Field(min_length=1, max_length=200)
    namespace: str
    securityDomain: str
    publisherId: str
    nativeModel: Literal["gpt-6.1-sol"]
    purpose: Literal["F3_ORIGINAL_CONVERSATION_CLOSURE"]
    baseline: ExactModel
    candidate: ExactModel
    profileDigest: str = Field(pattern="^[a-f0-9]{64}$")
    adapterDigest: str = Field(pattern="^[a-f0-9]{64}$")
    schemaDigest: str = Field(pattern="^[a-f0-9]{64}$")
    provider: ExactProvider
    codeVerification: PinnedFile
    schemaArtifact: PinnedFile
    standingAuthorization: PinnedFile
    candidateEvidence: PinnedFile
    sourcePolicy: PinnedFile
    ledgerId: str
    allowanceId: str
    allowanceDigest: str = Field(pattern="^[a-f0-9]{64}$")
    cumulativeCallCap: Literal[100]
    cumulativeCostMicrousd: Literal[10000000]
    expiresAt: datetime
    externalWrites: Literal[False]

    @model_validator(mode="after")
    def bounded(self):
        require(
            self.expiresAt.tzinfo is not None and self.expiresAt <= DEADLINE,
            "DEADLINE_INVALID",
        )
        require(
            self.candidate.modelId == self.baseline.modelId
            and self.candidate.revisionId != self.baseline.revisionId,
            "SUCCESSOR_REQUIRED",
        )
        require(
            all(
                v.strip() == v and v
                for v in (
                    self.namespace,
                    self.securityDomain,
                    self.publisherId,
                    self.ledgerId,
                    self.allowanceId,
                )
            ),
            "SCOPE_INVALID",
        )
        return self

    @property
    def digest(self):
        return digest(self.model_dump(mode="json"))

    @classmethod
    def load(cls, path):
        path = Path(path)
        require(path.is_absolute(), "PRIVATE_POLICY_REQUIRED")
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as stream:
                metadata = os.fstat(stream.fileno())
                require(
                    stat.S_ISREG(metadata.st_mode)
                    and metadata.st_uid == os.getuid()
                    and metadata.st_mode & 0o077 == 0,
                    "PRIVATE_POLICY_REQUIRED",
                )
                raw = stream.read(1024 * 1024 + 1)
                require(len(raw) <= 1024 * 1024, "PRIVATE_POLICY_REQUIRED")
        except OSError as exc:
            raise ModelGovernanceError("MODEL_POLICY_PRIVATE_POLICY_REQUIRED") from exc
        value = cls.model_validate_json(raw)
        require(value.enabled, "DISABLED")
        return value

    def evidence(self):
        standing = self.standingAuthorization.read()
        require(
            standing.get("doesNotAssertIndividualReview") is True
            and standing.get("budgetIncreaseAuthorized") is False
            and standing.get("externalBusinessWritesAuthorized") is False,
            "STANDING_AUTHORIZATION_INVALID",
        )
        verification = self.codeVerification.read()
        require(
            verification.get("status") == "PASS_OFFLINE_ONLY"
            and verification.get("modelDigest") == self.candidate.digest
            and verification.get("connectionProfileDigest") == self.profileDigest
            and verification.get("adapterPolicyDigest") == self.adapterDigest
            and verification.get("schemaDigest") == self.schemaDigest
            and verification.get("provider") == self.provider.model_dump()
            and verification.get("standingAuthorizationDigest")
            == self.standingAuthorization.sha256
            and verification.get("sourcePolicyDigest") == self.sourcePolicy.sha256
            and verification.get("sameOriginalBudget") is True
            and verification.get("modelCalled") is False,
            "CODE_VERIFICATION_INVALID",
        )
        files = verification.get("sourceFiles")
        require(
            isinstance(files, list) and 0 < len(files) <= 128,
            "CODE_VERIFICATION_INVALID",
        )
        for item in files:
            PinnedFile.model_validate(item).bytes()
        require(
            digest(self.schemaArtifact.read()) == self.schemaDigest, "SCHEMA_CHANGED"
        )
        evidence = self.candidateEvidence.read()
        require(
            evidence
            == dict(
                modelDigest=self.candidate.digest,
                profileDigest=self.profileDigest,
                adapterDigest=self.adapterDigest,
                schemaDigest=self.schemaDigest,
                sourcePolicyDigest=self.sourcePolicy.sha256,
                codeVerificationDigest=self.codeVerification.sha256,
                validationState="PASSED",
                externalWrites=False,
            ),
            "CANDIDATE_EVIDENCE_INVALID",
        )
        # Pin the already-authorized perimeter; publication grants no source use.
        self.sourcePolicy.read()
        return dict(
            standingAuthorizationDigest=self.standingAuthorization.sha256,
            candidateEvidenceDigest=self.candidateEvidence.sha256,
            codeVerificationDigest=self.codeVerification.sha256,
            schemaArtifactDigest=self.schemaArtifact.sha256,
            sourcePolicyDigest=self.sourcePolicy.sha256,
        )


def now():
    return datetime.now(UTC)
