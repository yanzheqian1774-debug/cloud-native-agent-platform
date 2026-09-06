"""Durable Business Problem and Success Criteria domain values."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from agent_console.execution_domain import ScopeIdentity


class BusinessProblemError(RuntimeError):
    """Stable, non-disclosing domain failure."""


class BusinessProblemConflict(BusinessProblemError):
    pass


class BusinessProblemNotAuthorized(BusinessProblemError):
    pass


class BusinessProblemState(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class CriterionType(StrEnum):
    DETERMINISTIC_BOOLEAN = "DETERMINISTIC_BOOLEAN"
    NUMERIC_THRESHOLD = "NUMERIC_THRESHOLD"
    CATEGORICAL_RESULT = "CATEGORICAL_RESULT"
    EVIDENCE_PRESENCE = "EVIDENCE_PRESENCE"
    HUMAN_EVALUATED = "HUMAN_EVALUATED"
    NOT_MEASURABLE = "NOT_MEASURABLE"


@dataclass(frozen=True, slots=True)
class BusinessProblemLifecycleEvent:
    event_id: str
    business_problem_id: str
    ordinal: int
    event_type: str
    from_state: BusinessProblemState | None
    to_state: BusinessProblemState
    actor_id: str
    event_digest: str
    occurred_at: datetime


TRANSITIONS = {
    BusinessProblemState.DRAFT: {BusinessProblemState.ACTIVE},
    BusinessProblemState.ACTIVE: {BusinessProblemState.IN_PROGRESS},
    BusinessProblemState.IN_PROGRESS: {BusinessProblemState.RESOLVED},
    BusinessProblemState.RESOLVED: {
        BusinessProblemState.CLOSED,
        BusinessProblemState.IN_PROGRESS,
    },
    BusinessProblemState.CLOSED: {BusinessProblemState.IN_PROGRESS},
}


def _canonical(value: Any) -> Any:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, dict):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class BusinessProblemRevision:
    scope: ScopeIdentity
    business_problem_id: str
    revision_id: str
    revision: int
    predecessor_revision_id: str | None
    title: str
    description: str
    owner_id: str
    created_by: str
    created_at: datetime
    digest: str = ""

    def __post_init__(self) -> None:
        if self.revision < 1 or not self.title.strip() or not self.description.strip():
            raise BusinessProblemError("BUSINESS_PROBLEM_REVISION_INVALID")
        expected = canonical_digest(self.digest_contract())
        if self.digest and self.digest != expected:
            raise BusinessProblemError("BUSINESS_PROBLEM_DIGEST_MISMATCH")
        object.__setattr__(self, "digest", expected)

    def digest_contract(self) -> dict[str, Any]:
        return {
            "schema_version": "business-problem-revision.v1",
            "namespace": self.scope.namespace,
            "security_domain": self.scope.security_domain,
            "business_problem_id": self.business_problem_id,
            "revision_id": self.revision_id,
            "revision": self.revision,
            "predecessor_revision_id": self.predecessor_revision_id,
            "title": self.title.strip(),
            "description": self.description.strip(),
            "owner_id": self.owner_id,
            "created_by": self.created_by,
        }


@dataclass(frozen=True, slots=True)
class SuccessCriterionRevision:
    scope: ScopeIdentity
    success_criterion_id: str
    revision_id: str
    revision: int
    predecessor_revision_id: str | None
    criterion_type: CriterionType
    measurement: dict[str, Any]
    required_evidence_kinds: tuple[str, ...]
    evaluator_type: str
    evaluator_version: str
    applicability: dict[str, Any]
    created_by: str
    created_at: datetime
    digest: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.criterion_type, CriterionType):
            raise BusinessProblemError("SUCCESS_CRITERION_TYPE_INVALID")
        validate_measurement(self.criterion_type, self.measurement)
        expected = canonical_digest(self.digest_contract())
        if self.digest and self.digest != expected:
            raise BusinessProblemError("SUCCESS_CRITERION_DIGEST_MISMATCH")
        object.__setattr__(self, "digest", expected)

    def digest_contract(self) -> dict[str, Any]:
        return {
            "schema_version": "success-criterion-revision.v1",
            "namespace": self.scope.namespace,
            "security_domain": self.scope.security_domain,
            "success_criterion_id": self.success_criterion_id,
            "revision_id": self.revision_id,
            "revision": self.revision,
            "predecessor_revision_id": self.predecessor_revision_id,
            "criterion_type": self.criterion_type,
            "measurement": self.measurement,
            "required_evidence_kinds": self.required_evidence_kinds,
            "evaluator_type": self.evaluator_type,
            "evaluator_version": self.evaluator_version,
            "applicability": self.applicability,
            "created_by": self.created_by,
        }


def validate_measurement(kind: CriterionType, measurement: dict[str, Any]) -> None:
    valid = {
        CriterionType.DETERMINISTIC_BOOLEAN: set(measurement) == {"expected"}
        and isinstance(measurement.get("expected"), bool),
        CriterionType.NUMERIC_THRESHOLD: set(measurement)
        == {"operator", "threshold", "unit"}
        and measurement.get("operator") in {"LT", "LTE", "EQ", "GTE", "GT"}
        and isinstance(measurement.get("threshold"), (int, float))
        and not isinstance(measurement.get("threshold"), bool),
        CriterionType.CATEGORICAL_RESULT: set(measurement) == {"allowed_values"}
        and bool(measurement.get("allowed_values")),
        CriterionType.EVIDENCE_PRESENCE: set(measurement) == {"minimum_count"}
        and isinstance(measurement.get("minimum_count"), int)
        and measurement["minimum_count"] > 0,
        CriterionType.HUMAN_EVALUATED: set(measurement) == {"rubric"}
        and bool(str(measurement.get("rubric", "")).strip()),
        CriterionType.NOT_MEASURABLE: measurement == {"reason": "NOT_MEASURABLE"},
    }
    if not valid[kind]:
        raise BusinessProblemError("SUCCESS_CRITERION_MEASUREMENT_INVALID")


@dataclass(frozen=True, slots=True)
class SuccessCriteriaSetRevision:
    scope: ScopeIdentity
    set_revision_id: str
    business_problem_id: str
    problem_revision_id: str
    revision: int
    predecessor_set_revision_id: str | None
    ordered_criterion_revision_ids: tuple[str, ...]
    created_by: str
    created_at: datetime
    digest: str = ""

    def __post_init__(self) -> None:
        if self.revision < 1 or not self.ordered_criterion_revision_ids:
            raise BusinessProblemError("SUCCESS_CRITERIA_SET_INVALID")
        if len(set(self.ordered_criterion_revision_ids)) != len(
            self.ordered_criterion_revision_ids
        ):
            raise BusinessProblemError("SUCCESS_CRITERIA_SET_INVALID")
        expected = canonical_digest(self.digest_contract())
        if self.digest and self.digest != expected:
            raise BusinessProblemError("SUCCESS_CRITERIA_SET_DIGEST_MISMATCH")
        object.__setattr__(self, "digest", expected)

    def digest_contract(self) -> dict[str, Any]:
        return {
            "schema_version": "success-criteria-set-revision.v1",
            "namespace": self.scope.namespace,
            "security_domain": self.scope.security_domain,
            "set_revision_id": self.set_revision_id,
            "business_problem_id": self.business_problem_id,
            "problem_revision_id": self.problem_revision_id,
            "revision": self.revision,
            "predecessor_set_revision_id": self.predecessor_set_revision_id,
            "ordered_criterion_revision_ids": self.ordered_criterion_revision_ids,
            "created_by": self.created_by,
        }


@dataclass(frozen=True, slots=True)
class PlanProblemBinding:
    scope: ScopeIdentity
    binding_id: str
    plan_id: str
    plan_version: int
    plan_digest: str
    business_problem_id: str
    problem_revision_id: str
    problem_revision_digest: str
    criteria_set_revision_id: str
    criteria_set_digest: str
    actor_id: str
    created_at: datetime
    digest: str = ""

    def __post_init__(self) -> None:
        expected = canonical_digest(self.digest_contract())
        if self.digest and self.digest != expected:
            raise BusinessProblemError("PLAN_PROBLEM_BINDING_MISMATCH")
        object.__setattr__(self, "digest", expected)

    def digest_contract(self) -> dict[str, Any]:
        return {
            "schema_version": "plan-problem-binding.v1",
            "namespace": self.scope.namespace,
            "security_domain": self.scope.security_domain,
            "binding_id": self.binding_id,
            "plan_id": self.plan_id,
            "plan_version": self.plan_version,
            "plan_digest": self.plan_digest,
            "business_problem_id": self.business_problem_id,
            "problem_revision_id": self.problem_revision_id,
            "problem_revision_digest": self.problem_revision_digest,
            "criteria_set_revision_id": self.criteria_set_revision_id,
            "criteria_set_digest": self.criteria_set_digest,
            "actor_id": self.actor_id,
        }
