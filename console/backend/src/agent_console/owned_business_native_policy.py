"""Explicit v4 Native capability scope; prior policy models remain unchanged."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .authority_contracts import AuthorityError
from .native_data_adapters import resolve
from .owned_business_policy import OwnedBusinessPolicyV3, OwnedBusinessScope
from .plan_suggestion_domain import ExactReference


class NativeAdapterBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    adapterId: str = Field(min_length=1, max_length=128)
    adapterRevision: str = Field(min_length=1, max_length=64)
    configurationDigest: str = Field(pattern="^[a-f0-9]{64}$")
    sourceSchema: str = Field(min_length=1, max_length=128)
    operations: tuple[str, ...] = Field(min_length=1, max_length=32)
    effectPolicy: Literal["READ_ONLY"]
    externalWrites: Literal[False]

    @model_validator(mode="after")
    def registered(self):
        resolve(self.model_dump(mode="json"))
        return self


class NativeReadonlyBusinessScope(OwnedBusinessScope):
    case: Literal["native_readonly"]
    sourceSchema: str = Field(min_length=1, max_length=128)
    adapter: NativeAdapterBinding

    @model_validator(mode="after")
    def exact_adapter(self):
        if (
            self.sourceSchema != self.adapter.sourceSchema
            or self.operations != self.adapter.operations
        ):
            raise ValueError("OWNED_NATIVE_ADAPTER_SCOPE_MISMATCH")
        return self


class OwnedBusinessPolicyV4(OwnedBusinessPolicyV3):
    schemaVersion: Literal["owned-business-admission.v4"]
    # A fresh isolated domain may have no predecessors. Configured history paths
    # still must exactly match these pins; existing deployment supplies its old pins.
    retainedReadPolicyDigests: tuple[str, ...] = Field(max_length=8)
    scopes: tuple[OwnedBusinessScope | NativeReadonlyBusinessScope, ...] = Field(
        min_length=1, max_length=16
    )

    def selected(self, metadata):
        if not metadata:
            raise AuthorityError("OWNED_BUSINESS_SOURCE_REQUIRED")
        ref = ExactReference.model_validate(metadata["source"])
        native = [
            s
            for s in self.scopes
            if isinstance(s, NativeReadonlyBusinessScope)
            and s.source == ref
            and s.sourceContentDigest == metadata.get("sourceContentDigest")
            and s.sourceSchema == metadata.get("sourceSchema")
        ]
        if native:
            if len(native) != 1:
                raise AuthorityError("OWNED_BUSINESS_SOURCE_NOT_AUTHORIZED")
            resolve(native[0].adapter.model_dump(mode="json"))
            return native[0]
        # Legacy scope selection is precisely the original method, excluding all
        # native scopes so its historical non-document -> sales mapping cannot apply.
        legacy = self.model_copy(
            update={
                "scopes": tuple(
                    s
                    for s in self.scopes
                    if not isinstance(s, NativeReadonlyBusinessScope)
                )
            }
        )
        return super(OwnedBusinessPolicyV4, legacy).selected(metadata)

    def validate_source(self, metadata, content):
        import json

        from .skill_executor import SkillExecutorFailure

        try:
            selected = super().validate_source(metadata, content)
        except AuthorityError:
            raise
        except (
            ValueError,
            TypeError,
            KeyError,
            IndexError,
            SkillExecutorFailure,
        ) as exc:
            raise AuthorityError("OWNED_BUSINESS_NATIVE_SOURCE_INVALID") from exc
        if isinstance(selected, NativeReadonlyBusinessScope):
            try:
                resolve(selected.adapter.model_dump(mode="json")).validate(
                    json.loads(content["documents"][0]["chunks"][0]["content"])
                )
            except (ValueError, TypeError, KeyError, SkillExecutorFailure) as exc:
                raise AuthorityError("OWNED_BUSINESS_NATIVE_SOURCE_INVALID") from exc
        return selected
