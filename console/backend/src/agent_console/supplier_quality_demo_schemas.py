"""Strict internal DTOs for the Package 7 supplier-quality demo bridge."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from agent_console.live_journey_schemas import LiveJourneyResponse


class StrictDemoModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SupplierQualityDemoStartRequest(StrictDemoModel):
    scenarioId: Literal["s5-v0.2-supplier-quality-v1"]
    replayIdentity: str = Field(min_length=1, max_length=200)
    locale: Literal["en", "zh-CN"] = "en"
    question: str = Field(
        default="某供应商近期交付质量持续下降, 请分析原因并制定整改计划。",
        min_length=8,
        max_length=500,
    )


class SupplierQualityDemoCallCounts(StrictDemoModel):
    planningGenerator: int = Field(ge=0)
    matchingRequests: int = Field(ge=0)
    knowledgeSourceReads: int = Field(ge=0)
    placementEvaluations: int = Field(ge=0)
    coordinatorExecutions: int = Field(ge=0)
    nativeProviderInvocations: int = Field(ge=0)
    capabilityGatewayInvocations: int = Field(ge=0)
    fixtureExecutions: int = Field(ge=0)


class SupplierQualityDemoStartResponse(StrictDemoModel):
    schemaVersion: Literal[1] = 1
    scenarioId: Literal["s5-v0.2-supplier-quality-v1"]
    namespace: Literal["s5-v02-supplier-quality-demo"]
    journeyId: str
    resetConfirmationToken: str
    replayed: bool
    callCounts: SupplierQualityDemoCallCounts
    live: LiveJourneyResponse


class SupplierQualityDemoResetRequest(StrictDemoModel):
    scenarioId: Literal["s5-v0.2-supplier-quality-v1"]
    namespace: Literal["s5-v02-supplier-quality-demo"]
    tenantId: Literal["tenant-a"]
    securityDomain: Literal["supplier-quality"]
    confirmationToken: str = Field(min_length=1, max_length=200)


class SupplierQualityDemoResetResponse(StrictDemoModel):
    schemaVersion: Literal[1] = 1
    scenarioId: Literal["s5-v0.2-supplier-quality-v1"]
    namespace: Literal["s5-v02-supplier-quality-demo"]
    journeyId: str
    state: Literal["RESET"] = "RESET"
    reasonCode: Literal["SUPPLIER_QUALITY_DEMO_RESET"] = "SUPPLIER_QUALITY_DEMO_RESET"


class SupplierQualityDemoError(StrictDemoModel):
    schemaVersion: Literal[1] = 1
    state: Literal[
        "DENIED",
        "NOT_FOUND",
        "AUTHORITY_MISSING",
        "STALE",
        "CONFLICT",
        "ERROR",
    ]
    reasonCode: str
    message: str
