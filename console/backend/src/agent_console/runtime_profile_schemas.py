"""Private Runtime Profile Workbench schemas."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Resources(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cpuRequest: str = Field(pattern=r"^[1-9][0-9]*m$")
    cpuLimit: str = Field(pattern=r"^[1-9][0-9]*m$")
    memoryRequest: str = Field(pattern=r"^[1-9][0-9]*(Mi|Gi)$")
    memoryLimit: str = Field(pattern=r"^[1-9][0-9]*(Mi|Gi)$")


class RuntimeProfileContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["NATIVE_KUBERNETES", "OPENCLAW"]
    resources: Resources
    isolation: Literal["NAMESPACE", "DEDICATED_RUNTIME"]
    stateMode: Literal["STATELESS", "EXTERNAL_REFERENCE"]
    sessionAffinity: Literal["NONE", "REQUIRED"]
    secretReferences: list[str] = []
    openClawPackageRef: str | None = None

    @model_validator(mode="after")
    def provider_contract(self):
        if self.provider == "OPENCLAW" and not self.openClawPackageRef:
            raise ValueError("OPENCLAW_PACKAGE_REFERENCE_REQUIRED")
        if self.provider == "NATIVE_KUBERNETES" and self.openClawPackageRef:
            raise ValueError("OPENCLAW_FIELD_FORBIDDEN")
        return self


class CreateRuntimeProfile(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    content: RuntimeProfileContent


class EditRuntimeProfile(BaseModel):
    expectedVersion: int
    content: RuntimeProfileContent


class VersionCommand(BaseModel):
    expectedVersion: int


class ReviewCommand(VersionCommand):
    digest: str
    decision: Literal["APPROVE", "REJECT"] = "APPROVE"
    reason: str


class PublishCommand(VersionCommand):
    digest: str
    reviewId: str


class RuntimeProfileResponse(BaseModel):
    profile: dict[str, Any]
    productProjection: dict[str, Any]
    technicalProjection: dict[str, Any]
