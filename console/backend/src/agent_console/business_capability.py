"""Business delivery definitions; exact references confer no execution authority."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum

from .digital_employee_definition import digest, identifier
from .execution_domain import ScopeIdentity


class BusinessCapabilityError(ValueError):
    """Bounded definition/repository failure, never raw storage diagnostics."""


def _text(value: object, limit: int, code: str) -> None:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
        or any(ord(c) < 32 and c not in "\n\t" for c in value)
    ):
        raise BusinessCapabilityError(code)


def _identity(value: str) -> None:
    try:
        identifier(value)
    except ValueError as exc:
        raise BusinessCapabilityError("CAPABILITY_IDENTITY_INVALID") from exc


def _digest(value: object) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise BusinessCapabilityError("CAPABILITY_REFERENCE_DIGEST_INVALID")


class BindingKind(StrEnum):
    EMPLOYEE = "EMPLOYEE"
    SKILL = "SKILL"
    MCP = "MCP"
    KNOWLEDGE = "KNOWLEDGE"
    ONTOLOGY = "ONTOLOGY"
    TOOL = "TOOL"
    RUNTIME_PROFILE = "RUNTIME_PROFILE"


@dataclass(frozen=True)
class FixedReference:
    resource_id: str
    revision_id: str
    digest: str

    def __post_init__(self):
        _identity(self.resource_id)
        _identity(self.revision_id)
        _digest(self.digest)


@dataclass(frozen=True)
class CapabilityBinding:
    kind: BindingKind
    reference: FixedReference
    purpose: str

    def __post_init__(self):
        if not isinstance(self.kind, BindingKind) or not isinstance(
            self.reference, FixedReference
        ):
            raise BusinessCapabilityError("CAPABILITY_BINDING_INVALID")
        _text(self.purpose, 1000, "CAPABILITY_BINDING_PURPOSE_REQUIRED")


class OriginKind(StrEnum):
    INDEPENDENT = "INDEPENDENT"
    WORKFLOW_REVISION = "WORKFLOW_REVISION"
    SAVED_PREPARATION = "SAVED_PREPARATION"


@dataclass(frozen=True)
class CapabilityOrigin:
    kind: OriginKind
    workflow: FixedReference | None = None
    preparation_digest: str | None = None

    def __post_init__(self):
        if not isinstance(self.kind, OriginKind):
            raise BusinessCapabilityError("CAPABILITY_ORIGIN_INVALID")
        if self.kind is OriginKind.INDEPENDENT:
            valid = self.workflow is None and self.preparation_digest is None
        elif self.kind is OriginKind.WORKFLOW_REVISION:
            valid = (
                isinstance(self.workflow, FixedReference)
                and self.preparation_digest is None
            )
        else:
            _digest(self.preparation_digest)
            valid = self.workflow is None
        if not valid:
            raise BusinessCapabilityError("CAPABILITY_ORIGIN_INVALID")


@dataclass(frozen=True)
class BusinessCapabilityRevision:
    scope: ScopeIdentity
    capability_id: str
    revision_id: str
    title: str
    intent: str
    inputs: str
    outputs: str
    business_scope: str
    exclusions: str
    manual_involvement: str
    acceptance_criteria: tuple[str, ...]
    known_limitations: str
    origin: CapabilityOrigin
    bindings: tuple[CapabilityBinding, ...]
    predecessor_revision_id: str | None = None
    business_domain: str | None = None

    def __post_init__(self):
        if not isinstance(self.scope, ScopeIdentity):
            raise BusinessCapabilityError("CAPABILITY_SCOPE_REQUIRED")
        for value in (self.capability_id, self.revision_id):
            _identity(value)
        if self.predecessor_revision_id is not None:
            _identity(self.predecessor_revision_id)
            if self.predecessor_revision_id == self.revision_id:
                raise BusinessCapabilityError("CAPABILITY_PREDECESSOR_INVALID")
        if self.business_domain is not None:
            _text(self.business_domain, 80, "CAPABILITY_DOMAIN_INVALID")
            if (
                self.business_domain != self.business_domain.strip()
                or self.business_domain == "__UNASSIGNED__"
            ):
                raise BusinessCapabilityError("CAPABILITY_DOMAIN_INVALID")
        _text(self.title, 120, "CAPABILITY_TITLE_REQUIRED")
        for field in (
            "intent",
            "inputs",
            "outputs",
            "business_scope",
            "exclusions",
            "manual_involvement",
            "known_limitations",
        ):
            _text(getattr(self, field), 2000, "CAPABILITY_DESCRIPTION_REQUIRED")
        if not isinstance(self.origin, CapabilityOrigin):
            raise BusinessCapabilityError("CAPABILITY_ORIGIN_REQUIRED")
        if not isinstance(self.acceptance_criteria, tuple) or not (
            1 <= len(self.acceptance_criteria) <= 32
        ):
            raise BusinessCapabilityError("CAPABILITY_CRITERIA_REQUIRED")
        for value in self.acceptance_criteria:
            _text(value, 1000, "CAPABILITY_CRITERION_INVALID")
        if len(set(self.acceptance_criteria)) != len(self.acceptance_criteria):
            raise BusinessCapabilityError("CAPABILITY_CRITERION_DUPLICATE")
        if (
            not isinstance(self.bindings, tuple)
            or not 1 <= len(self.bindings) <= 64
            or any(not isinstance(b, CapabilityBinding) for b in self.bindings)
        ):
            raise BusinessCapabilityError("CAPABILITY_BINDINGS_REQUIRED")
        keys = {(b.kind, b.reference.resource_id) for b in self.bindings}
        if len(keys) != len(self.bindings):
            raise BusinessCapabilityError("CAPABILITY_BINDING_DUPLICATE")
        if not any(b.kind is BindingKind.EMPLOYEE for b in self.bindings):
            raise BusinessCapabilityError("CAPABILITY_EMPLOYEE_REQUIRED")

    def canonical_record(self) -> dict:
        record = {"schemaVersion": "business-capability.v1", **asdict(self)}
        if self.business_domain is None:
            record.pop("business_domain")
        return record

    @property
    def content_digest(self) -> str:
        return digest(self.canonical_record())

    @classmethod
    def from_record(cls, record: dict) -> BusinessCapabilityRevision:
        try:
            value = dict(record)
            if value.pop("schemaVersion") != "business-capability.v1":
                raise ValueError("schema")
            value["scope"] = ScopeIdentity(**value["scope"])
            origin = dict(value["origin"])
            origin["kind"] = OriginKind(origin["kind"])
            if origin.get("workflow") is not None:
                origin["workflow"] = FixedReference(**origin["workflow"])
            value["origin"] = CapabilityOrigin(**origin)
            if not isinstance(value["bindings"], (list, tuple)) or not isinstance(
                value["acceptance_criteria"], (list, tuple)
            ):
                raise ValueError("collections")
            value["bindings"] = tuple(
                CapabilityBinding(
                    kind=BindingKind(b["kind"]),
                    reference=FixedReference(**b["reference"]),
                    purpose=b["purpose"],
                )
                for b in value["bindings"]
                if set(b) == {"kind", "reference", "purpose"}
            )
            if len(value["bindings"]) != len(record["bindings"]):
                raise ValueError("binding fields")
            value["acceptance_criteria"] = tuple(value["acceptance_criteria"])
            return cls(**value)
        except (KeyError, TypeError, ValueError) as exc:
            raise BusinessCapabilityError("CAPABILITY_RECORD_CORRUPT") from exc
