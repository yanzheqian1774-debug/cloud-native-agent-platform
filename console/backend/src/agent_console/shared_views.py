"""Immutable shared execution truth for internal Product/Technical views."""

from __future__ import annotations

import re
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from agent_core.representation.v0_2 import PlatformExecutionIdentity


class ViewProjectionError(ValueError):
    """Stable failure for malformed or unsupported projection evidence."""


class AuthorizationDecision(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"


class OutcomeStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


MAX_STRING = 2_000
MAX_COLLECTION = 32
MAX_AGGREGATE_TEXT = 64_000
_SECRET = re.compile(
    r"(?:api[_-]?key|authorization|bearer|credential|password|secret|token)",
    re.IGNORECASE,
)


def _text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ViewProjectionError(code)
    if len(value) > MAX_STRING:
        raise ViewProjectionError("PROJECTION_LIMIT_EXCEEDED")
    if _SECRET.search(value):
        raise ViewProjectionError("SECRET_SHAPED_VALUE_REJECTED")
    return value


def _strings(value: object, code: str) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)) or len(value) > MAX_COLLECTION:
        raise ViewProjectionError(code)
    result = tuple(_text(item, code) for item in value)
    if len(set(result)) != len(result):
        raise ViewProjectionError("AMBIGUOUS_PROJECTION_EVIDENCE")
    return result


@dataclass(frozen=True, slots=True)
class RuntimeSupport:
    runtime: str
    classification: str
    availability: str
    support: str


NATIVE_SUPPORT = RuntimeSupport(
    "NATIVE",
    "COMPONENT_TESTED_CANDIDATE / PRIMARY_GOLDEN_PATH_CANDIDATE",
    "AVAILABLE_FOR_BOUNDED_DEMO",
    "NOT_CERTIFIED",
)
OPENCLAW_SUPPORT = RuntimeSupport(
    "OPENCLAW",
    "EXACT_VERSION_CANDIDATE",
    "CURRENTLY_UNAVAILABLE_WITHOUT_LIVE_MANAGED_PROFILE_EVIDENCE",
    "SUPPORT_NOT_GRANTED",
)
HERMES_SUPPORT = RuntimeSupport(
    "HERMES",
    "EXPERIMENTAL / NOT_CURRENTLY_CERTIFIABLE",
    "UNAVAILABLE",
    "SUPPORT_NOT_GRANTED",
)
RUNTIME_SUPPORT = {
    item.runtime: item for item in (NATIVE_SUPPORT, OPENCLAW_SUPPORT, HERMES_SUPPORT)
}


@dataclass(frozen=True, slots=True)
class KnowledgeCitation:
    collection_id: str
    asset_id: str
    revision_id: str
    evidence_id: str
    message_key: str

    def __post_init__(self) -> None:
        prefixes = {
            "collection_id": "knowledge-collection.synthetic.",
            "asset_id": "knowledge-asset.synthetic.",
            "revision_id": "revision.synthetic.",
            "evidence_id": "evidence.synthetic.",
            "message_key": "citation.synthetic.",
        }
        for field, prefix in prefixes.items():
            if not _text(getattr(self, field), "MALFORMED_CITATION").startswith(prefix):
                raise ViewProjectionError("NON_SYNTHETIC_KNOWLEDGE_EVIDENCE")


@dataclass(frozen=True, slots=True)
class SharedExecutionView:
    """Single source from which both views are projected; never reconstructed."""

    platform_execution_identity: PlatformExecutionIdentity
    definition_id: str
    definition_revision: str
    instance_id: str
    task_id: str
    workflow_id: str
    digital_employee_name_key: str
    role_title_key: str
    role_description_key: str
    responsibility_keys: tuple[str, ...]
    allowed_activity_keys: tuple[str, ...]
    prohibited_activity_keys: tuple[str, ...]
    suggested_team_ids: tuple[str, ...]
    instance_count: int
    work_plan_keys: tuple[str, ...]
    business_progress_code: str
    approval_state: str
    requested_runtime: str
    effective_runtime: str | None
    provider_native_correlation_id: str | None
    capability_decision: AuthorizationDecision
    capability_reason_code: str
    provider_call_count: int
    outcome_status: OutcomeStatus
    outcome_summary_key: str
    citations: tuple[KnowledgeCitation, ...]
    limitation_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        tuple_fields = (
            "responsibility_keys",
            "allowed_activity_keys",
            "prohibited_activity_keys",
            "suggested_team_ids",
            "work_plan_keys",
            "limitation_codes",
        )
        for field in tuple_fields:
            object.__setattr__(
                self,
                field,
                _strings(getattr(self, field), "MALFORMED_PROJECTION_COLLECTION"),
            )
        if (
            not isinstance(self.citations, (tuple, list))
            or len(self.citations) > MAX_COLLECTION
        ):
            raise ViewProjectionError("MALFORMED_CITATION_COLLECTION")
        citations = tuple(self.citations)
        if not all(isinstance(item, KnowledgeCitation) for item in citations):
            raise ViewProjectionError("MALFORMED_CITATION")
        object.__setattr__(self, "citations", citations)
        required = (
            self.definition_id,
            self.definition_revision,
            self.instance_id,
            self.task_id,
            self.workflow_id,
            self.digital_employee_name_key,
            self.role_title_key,
            self.role_description_key,
            self.business_progress_code,
            self.approval_state,
            self.requested_runtime,
            self.capability_reason_code,
            self.outcome_summary_key,
        )
        if not isinstance(self.platform_execution_identity, PlatformExecutionIdentity):
            raise ViewProjectionError("PLATFORM_EXECUTION_IDENTITY_REQUIRED")
        for value in required:
            _text(value, "MALFORMED_PROJECTION_EVIDENCE")
        if not isinstance(self.instance_count, int) or isinstance(
            self.instance_count, bool
        ):
            raise ViewProjectionError("INVALID_COUNT")
        if not isinstance(self.provider_call_count, int) or isinstance(
            self.provider_call_count, bool
        ):
            raise ViewProjectionError("INVALID_COUNT")
        if self.instance_count < 0 or self.provider_call_count < 0:
            raise ViewProjectionError("INVALID_COUNT")
        if not isinstance(self.capability_decision, AuthorizationDecision):
            raise ViewProjectionError("INVALID_CAPABILITY_DECISION")
        if not isinstance(self.outcome_status, OutcomeStatus):
            raise ViewProjectionError("INVALID_OUTCOME_STATUS")
        if (
            len({self.definition_id, self.instance_id, self.task_id, self.workflow_id})
            != 4
        ):
            raise ViewProjectionError("IDENTITY_DOMAIN_COLLISION")
        if self.provider_native_correlation_id is not None:
            _text(self.provider_native_correlation_id, "INVALID_NATIVE_CORRELATION")
            if (
                self.provider_native_correlation_id
                == self.platform_execution_identity.value
            ):
                raise ViewProjectionError("NATIVE_ID_CANNOT_BE_PLATFORM_AUTHORITY")
        if self.requested_runtime not in RUNTIME_SUPPORT:
            raise ViewProjectionError("UNSUPPORTED_REQUESTED_RUNTIME")
        if (
            self.effective_runtime is not None
            and self.effective_runtime not in RUNTIME_SUPPORT
        ):
            raise ViewProjectionError("UNSUPPORTED_EFFECTIVE_RUNTIME")
        if self.effective_runtime is not None and (
            RUNTIME_SUPPORT[self.effective_runtime].support == "SUPPORT_NOT_GRANTED"
        ):
            raise ViewProjectionError("UNSUPPORTED_RUNTIME_EVIDENCE")
        if (
            self.effective_runtime is not None
            and self.effective_runtime != self.requested_runtime
        ):
            raise ViewProjectionError("RUNTIME_SUBSTITUTION_NOT_ALLOWED")
        if self.capability_decision == AuthorizationDecision.DENY and (
            self.provider_call_count != 0 or self.citations
        ):
            raise ViewProjectionError("DENY_REQUIRES_ZERO_PROVIDER_EFFECTS")
        if (
            self.capability_decision == AuthorizationDecision.ALLOW
            and not self.citations
        ):
            raise ViewProjectionError("ALLOW_REQUIRES_SYNTHETIC_CITATIONS")
        if (
            self.capability_decision == AuthorizationDecision.ALLOW
            and self.provider_call_count == 0
        ):
            raise ViewProjectionError("ALLOW_REQUIRES_PROVIDER_CALL_EVIDENCE")
        if len({item.evidence_id for item in self.citations}) != len(self.citations):
            raise ViewProjectionError("AMBIGUOUS_CITATION_EVIDENCE")
        aggregate = sum(len(value) for value in required)
        aggregate += sum(
            len(value) for field in tuple_fields for value in getattr(self, field)
        )
        aggregate += sum(
            len(value) for item in self.citations for value in asdict(item).values()
        )
        if aggregate > MAX_AGGREGATE_TEXT:
            raise ViewProjectionError("PROJECTION_LIMIT_EXCEEDED")


def product_view(source: SharedExecutionView) -> dict[str, Any]:
    """Project locale-neutral business semantics from the shared source."""
    return {
        "platformExecutionIdentity": source.platform_execution_identity.value,
        "definitionId": source.definition_id,
        "definitionRevision": source.definition_revision,
        "digitalEmployeeNameKey": source.digital_employee_name_key,
        "roleTitleKey": source.role_title_key,
        "roleDescriptionKey": source.role_description_key,
        "responsibilityKeys": list(source.responsibility_keys),
        "allowedActivityKeys": list(source.allowed_activity_keys),
        "prohibitedActivityKeys": list(source.prohibited_activity_keys),
        "suggestedTeamIds": list(source.suggested_team_ids),
        "instanceCount": source.instance_count,
        "workPlanKeys": list(source.work_plan_keys),
        "businessProgressCode": source.business_progress_code,
        "approvalState": source.approval_state,
        "outcomeStatus": source.outcome_status.value,
        "outcomeSummaryKey": source.outcome_summary_key,
        "citations": [asdict(item) for item in source.citations],
    }


def technical_view(source: SharedExecutionView) -> dict[str, Any]:
    """Project technical evidence without promoting native IDs to authority."""
    requested = RUNTIME_SUPPORT[source.requested_runtime]
    effective = (
        RUNTIME_SUPPORT[source.effective_runtime]
        if source.effective_runtime is not None
        else None
    )
    return {
        "platformExecutionIdentity": source.platform_execution_identity.value,
        "definition": {
            "id": source.definition_id,
            "revision": source.definition_revision,
        },
        "instanceId": source.instance_id,
        "taskId": source.task_id,
        "workflowId": source.workflow_id,
        "requestedRuntime": asdict(requested),
        "effectiveRuntime": asdict(effective) if effective else None,
        "providerNativeCorrelation": {
            "id": source.provider_native_correlation_id,
            "authority": "CORRELATION_ONLY",
        },
        "capability": {
            "decision": source.capability_decision.value,
            "reasonCode": source.capability_reason_code,
            "providerCallCount": source.provider_call_count,
        },
        "outcome": {
            "status": source.outcome_status.value,
            "summaryMessageKey": source.outcome_summary_key,
        },
        "knowledgeEvidence": [asdict(item) for item in source.citations],
        "limitationCodes": list(source.limitation_codes),
    }


def sibling_snapshot_views(
    snapshot: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return sibling projections while preserving every shared authority field."""
    required = (
        "platformExecutionIdentity",
        "sharedSnapshotId",
        "graphSnapshotId",
        "authorization",
        "runtime",
        "outcome",
        "evidence",
        "citations",
        "graph",
    )
    if not isinstance(snapshot, Mapping) or any(
        key not in snapshot for key in required
    ):
        raise ViewProjectionError("SHARED_EXECUTION_SNAPSHOT_REQUIRED")
    shared = {key: deepcopy(snapshot[key]) for key in required}
    product = {
        **shared,
        "projectionContext": "PRODUCT",
        "state": snapshot.get("state"),
        "sourceVersions": deepcopy(snapshot.get("sourceVersions", {})),
    }
    technical = {
        **deepcopy(shared),
        "projectionContext": "TECHNICAL",
        "state": snapshot.get("state"),
        "sourceVersions": deepcopy(snapshot.get("sourceVersions", {})),
    }
    return product, technical
