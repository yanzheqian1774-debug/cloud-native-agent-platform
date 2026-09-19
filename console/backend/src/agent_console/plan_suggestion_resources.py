"""Read-only, authorized owner facts; provider claims never establish readiness."""

from contextlib import nullcontext
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from .plan_suggestion_domain import (
    ExactReference,
    ResourceObservation,
    ResourceSnapshot,
)


class ResourceOwnerReader(Protocol):
    def observe(self, principal, requirement) -> ResourceObservation: ...


class PlanningResourceResolver:
    def __init__(self, readers: dict[str, ResourceOwnerReader]):
        self.readers = readers

    def resolve(self, principal, proposal):
        observations = []
        for requirement in proposal.semantics.requirements:
            if requirement.selected is None:
                status = "MISSING" if requirement.required else "NOT_REQUIRED"
                observation = ResourceObservation(
                    requirement_id=requirement.requirement_id,
                    status=status,
                    reason="EXPLICIT_UNRESOLVED_REQUIREMENT"
                    if requirement.required
                    else "OPTIONAL_NOT_SELECTED",
                )
            elif requirement.kind not in self.readers:
                observation = ResourceObservation(
                    requirement_id=requirement.requirement_id,
                    status="UNKNOWN",
                    reason="OWNER_READER_NOT_CONFIGURED",
                )
            else:
                observation = self.readers[requirement.kind].observe(
                    principal, requirement
                )
                if observation.requirement_id != requirement.requirement_id:
                    raise ValueError("RESOURCE_OWNER_TARGET_MISMATCH")
            observations.append(observation)
        return ResourceSnapshot(
            snapshot_id=str(uuid4()),
            proposal_digest=proposal.digest,
            checked_at=datetime.now(UTC).isoformat(),
            observations=tuple(observations),
        )


class EmployeePlanningReader:
    """Use the Employee owner exact publication reader after current authorization."""

    def __init__(self, repository, authority, scope_factory, connection=None):
        self.repository = repository
        self.authority = authority
        self.scope_factory = scope_factory
        self.connection = connection

    def observe(self, principal, requirement):
        from .authority_contracts import AuthorityError
        from .digital_employee_definition import EmployeeDefinitionError

        reference: ExactReference = requirement.selected
        try:
            self.authority.require(
                principal,
                "EMPLOYEE",
                "READ",
                f"employee:{reference.resource_id}:{reference.revision_id}",
            )
        except AuthorityError:
            return ResourceObservation(
                requirement_id=requirement.requirement_id,
                status="UNREADABLE",
                reason="RESOURCE_NOT_READABLE",
            )
        try:
            with (
                nullcontext(self.connection)
                if self.connection is not None
                else self.repository.pool.connection()
            ) as connection:
                value = self.repository.read_for_plan(
                    connection,
                    self.scope_factory(principal),
                    reference.resource_id,
                    reference.revision_id,
                    reference.digest,
                    authorized=True,
                )
        except EmployeeDefinitionError:
            return ResourceObservation(
                requirement_id=requirement.requirement_id,
                status="UNAVAILABLE",
                reason="EXACT_PUBLISHED_REFERENCE_UNAVAILABLE",
            )
        return ResourceObservation(
            requirement_id=requirement.requirement_id,
            status="MATCHED",
            reason="OWNER_EXACT_PUBLISHED_REFERENCE",
            owner_high_water=str(value["digest"]),
        )
