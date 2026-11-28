"""Separate standing business scope; owned chat and READ are not execution authority."""

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from .authority_contracts import AuthorityError
from .ontology_execution import DocumentSemanticsBinding
from .plan_suggestion_domain import ExactReference
from .resource_use_domain import canonical_digest


class OwnedBusinessScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    scopeId: str = Field(min_length=1, max_length=128)
    authorizationBasisDigest: str = Field(pattern="^[a-f0-9]{64}$")
    source: ExactReference
    sourceContentDigest: str = Field(pattern="^[a-f0-9]{64}$")
    case: Literal["document", "sales"]
    capability: ExactReference | None = None
    employees: tuple[ExactReference, ...] = Field(min_length=1, max_length=16)
    agents: tuple[ExactReference, ...] = Field(min_length=1, max_length=16)
    skills: tuple[ExactReference, ...] = Field(min_length=1, max_length=16)
    runtimes: tuple[ExactReference, ...] = Field(min_length=1, max_length=16)
    nativeAgentName: str = Field(pattern=r"^[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?$")
    operations: tuple[str, ...] = Field(min_length=1, max_length=32)
    effectPolicy: Literal["READ_ONLY"]
    externalWrites: Literal[False]
    documentRules: DocumentSemanticsBinding | None = None
    trustedAssemblyAdoption: Literal["SAME_SCOPE_SELECTED_V1"] | None = None

    @model_serializer(mode="wrap")
    def compatible_scope(self, handler):
        value = handler(self)
        if self.trustedAssemblyAdoption is None:
            value.pop("trustedAssemblyAdoption", None)
        return value

    @model_validator(mode="after")
    def exact_document(self):
        if any(
            not operation.strip() or len(operation) > 128
            for operation in self.operations
        ):
            raise ValueError("OWNED_BUSINESS_OPERATION_INVALID")
        if self.case == "document" and (
            self.documentRules is None or self.documentRules.source != self.source
        ):
            raise ValueError("OWNED_BUSINESS_DOCUMENT_BINDING_REQUIRED")
        if self.case != "document" and self.documentRules is not None:
            raise ValueError("OWNED_BUSINESS_DOCUMENT_CASE_MISMATCH")
        return self


class OwnedBusinessPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: Literal["owned-business-admission.v1"]
    policyId: str = Field(min_length=1, max_length=128)
    policyVersion: str = Field(min_length=1, max_length=128)
    enabled: bool = False
    tenantId: Literal["s5-323-demo"]
    securityDomain: Literal["isolated-real-demo"]
    subjectId: Literal["human:demo323-approver"]
    accountId: Literal["local-account:reviewer324"]
    rootPolicyDigest: str = Field(pattern="^[a-f0-9]{64}$")
    rootUnderstandingPolicyDigest: str = Field(pattern="^[a-f0-9]{64}$")
    adoptionPolicyDigest: str = Field(pattern="^[a-f0-9]{64}$")
    ledgerId: Literal["ledger:f3-main-experience:20261112"]
    allowanceId: str = Field(min_length=1, max_length=200)
    expiresAt: datetime
    externalWrites: Literal[False]
    scopes: tuple[OwnedBusinessScope, ...] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def unique_scope(self):
        if self.expiresAt.tzinfo is None or len(
            {s.scopeId for s in self.scopes}
        ) != len(self.scopes):
            raise ValueError("OWNED_BUSINESS_POLICY_INVALID")
        refs = [(s.source, s.sourceContentDigest) for s in self.scopes]
        if any(refs.count(ref) != 1 for ref in refs):
            raise ValueError("OWNED_BUSINESS_SCOPE_AMBIGUOUS")
        return self

    @property
    def digest(self):
        return canonical_digest(self.model_dump(mode="json"))

    @classmethod
    def load(cls, path):
        path = Path(path)
        try:
            if not path.is_absolute() or path.stat().st_mode & 0o077:
                raise AuthorityError("OWNED_BUSINESS_POLICY_INVALID")
            raw = json.loads(path.read_text())
            if not isinstance(raw, dict):
                raise AuthorityError("OWNED_BUSINESS_POLICY_INVALID")
            if raw.get("schemaVersion") == "owned-business-admission.v4":
                from .owned_business_native_policy import OwnedBusinessPolicyV4

                return OwnedBusinessPolicyV4.model_validate(raw)
            policy_type = (
                OwnedBusinessPolicyV3
                if raw.get("schemaVersion") == "owned-business-admission.v3"
                else OwnedBusinessPolicyV2
                if raw.get("schemaVersion") == "owned-business-admission.v2"
                else cls
            )
            return policy_type.model_validate(raw)
        except (OSError, ValueError) as exc:
            raise AuthorityError("OWNED_BUSINESS_POLICY_INVALID") from exc

    def selected(self, metadata):
        if not metadata:
            raise AuthorityError("OWNED_BUSINESS_SOURCE_REQUIRED")
        ref = ExactReference.model_validate(metadata["source"])
        matches = [
            s
            for s in self.scopes
            if s.source == ref
            and s.sourceContentDigest == metadata.get("sourceContentDigest")
            and metadata.get("sourceSchema")
            == (
                "document-review-source.v1"
                if s.case == "document"
                else "sales-diagnostic-source.v1"
            )
        ]
        if len(matches) != 1:
            raise AuthorityError("OWNED_BUSINESS_SOURCE_NOT_AUTHORIZED")
        return matches[0]

    def validate_source(self, metadata, content):
        import json

        from .resource_automation_policy import source_digest

        selected = self.selected(metadata)
        if source_digest(content) != selected.sourceContentDigest:
            raise AuthorityError("OWNED_BUSINESS_SOURCE_CHANGED")
        raw = json.loads(content["documents"][0]["chunks"][0]["content"])
        if raw.get("synthetic") is not True or raw.get("schemaVersion") != metadata.get(
            "sourceSchema"
        ):
            raise AuthorityError("OWNED_BUSINESS_SOURCE_NOT_AUTHORIZED")
        return selected


class OwnedBusinessPolicyV2(OwnedBusinessPolicy):
    """Explicit read-only inheritance; v1 serialization remains unchanged."""

    schemaVersion: Literal["owned-business-admission.v2"]
    retainedReadPolicyDigests: tuple[str, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def exact_retained(self):
        import re

        pins = self.retainedReadPolicyDigests
        if len(set(pins)) != len(pins) or any(
            re.fullmatch(r"[a-f0-9]{64}", pin) is None for pin in pins
        ):
            raise ValueError("OWNED_BUSINESS_RETAINED_HISTORY_INVALID")
        return self


class IndependentGoalProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    profileRevisionId: str = Field(min_length=1, max_length=200)
    profileDigest: str = Field(pattern="^[a-f0-9]{64}$")
    adapterRevision: Literal["v4-structured-conversation"]


class OwnedBusinessPolicyV3(OwnedBusinessPolicyV2):
    """Explicit single-response independent goal origin; old policy bytes unchanged."""

    schemaVersion: Literal["owned-business-admission.v3"]
    independentGoalProfile: IndependentGoalProfile
