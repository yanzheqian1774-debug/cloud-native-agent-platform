from agent_core.execution_contract import ScopeIdentity
from agent_core.execution_repositories import (
    ExecutionEvidencePort,
    ExecutionIdentityRepository,
    ExecutionRelationshipQueryPort,
    InterventionPort,
    OutcomePort,
    PlacementRepository,
    RuntimeDesiredStateRepository,
    RuntimeObservationRepository,
)


def test_repository_candidates_are_protocols_not_storage_implementations() -> None:
    expected = {
        ExecutionIdentityRepository: {"save", "get_attempt"},
        PlacementRepository: {"decide", "get", "get_by_request"},
        RuntimeDesiredStateRepository: {"append", "get", "read_runtime"},
        RuntimeObservationRepository: {"append", "get", "read_runtime"},
        ExecutionEvidencePort: {"read_attempt"},
        OutcomePort: {"read_workflow"},
        InterventionPort: {"read_runtime", "read_assignment"},
        ExecutionRelationshipQueryPort: {"attempts_for_runtime_agent"},
    }
    for repository, members in expected.items():
        assert repository._is_protocol  # type: ignore[attr-defined]
        assert repository.__protocol_attrs__ == members  # type: ignore[attr-defined]


def test_every_repository_operation_requires_scope_identity() -> None:
    repositories = (
        ExecutionIdentityRepository,
        PlacementRepository,
        RuntimeDesiredStateRepository,
        RuntimeObservationRepository,
        ExecutionEvidencePort,
        OutcomePort,
        InterventionPort,
        ExecutionRelationshipQueryPort,
    )
    for repository in repositories:
        for member in repository.__protocol_attrs__:  # type: ignore[attr-defined]
            annotations = getattr(repository, member).__annotations__
            assert annotations["scope"] is ScopeIdentity
