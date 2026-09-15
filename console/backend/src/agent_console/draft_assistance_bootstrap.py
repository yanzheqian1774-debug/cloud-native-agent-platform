"""Fail-closed PostgreSQL composition for governed synthetic Draft Assistance."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from agent_console.draft_assistance import (
    DeterministicSyntheticDraftTransport,
    DraftAssistanceError,
    DraftAssistanceProfileRevision,
    DraftAssistanceService,
    DraftScope,
    StaticPepperResolver,
)
from agent_console.draft_assistance_postgres import (
    PostgresContextualResourceUseOwner,
    PostgresDraftAssistanceRepository,
    PostgresDraftEvidenceOwner,
)
from agent_console.draft_assistance_support import OpaqueSyntheticCredentialResolver
from agent_console.model_binding_resolution import (
    ExactModelBinding,
    ExactModelUse,
    ModelConsumptionScope,
)
from agent_console.model_governance_authorization import ModelGovernanceExactResolver
from agent_console.model_governance_postgres import PostgresModelGovernanceRepository


class _UnavailableAuthorization:
    """The formal Workbench authority adapter replaces this before serving."""

    def __getattr__(self, name):
        del name
        raise DraftAssistanceError("DRAFT_AUTHORIZATION_UNAVAILABLE")


class GovernedProfileModelResolver:
    """Adapt the exact Model owner resolver to one server-owned assistance profile."""

    def __init__(self, repository: PostgresModelGovernanceRepository) -> None:
        self.resolver = ModelGovernanceExactResolver(repository, repository, repository)

    def resolve_exact(
        self,
        profile: DraftAssistanceProfileRevision,
        exact_use: ExactModelUse,
    ):
        scope = ModelConsumptionScope(
            profile.scope.namespace, profile.scope.security_domain
        )
        value = self.resolver.resolve_exact(scope, exact_use.binding)
        if value is None:
            raise DraftAssistanceError("MODEL_BINDING_NOT_FOUND")
        return value


@dataclass(slots=True)
class DraftAssistanceComposition:
    service: DraftAssistanceService
    draft_repository: PostgresDraftAssistanceRepository
    resource_use_owner: PostgresContextualResourceUseOwner
    evidence_owner: PostgresDraftEvidenceOwner
    model_repository: PostgresModelGovernanceRepository

    def close(self) -> None:
        self.evidence_owner.close()
        self.resource_use_owner.close()
        self.draft_repository.close()
        self.model_repository.close()


def _profile(document: object) -> tuple[DraftAssistanceProfileRevision, Path]:
    if not isinstance(document, dict) or set(document) != {
        "schemaVersion",
        "transportKind",
        "scope",
        "profileRevisionId",
        "profileDigest",
        "model",
        "provider",
        "endpoint",
        "connectionProfile",
        "adapter",
        "outputSchemaVersion",
        "targetFormatVersion",
        "maximumInputBytes",
        "maximumOutputTokens",
        "totalTimeoutSeconds",
        "pepperReference",
        "pepperVersion",
        "pepperFile",
    }:
        raise DraftAssistanceError("DRAFT_PROFILE_INVALID")
    if (
        document["schemaVersion"] != "draft-assistance-runtime.v1"
        or document["transportKind"] != "SYNTHETIC"
    ):
        raise DraftAssistanceError("DRAFT_PROFILE_INVALID")
    scope = document["scope"]
    model = document["model"]
    provider = document["provider"]
    endpoint = document["endpoint"]
    connection = document["connectionProfile"]
    adapter = document["adapter"]
    if not all(
        isinstance(value, dict)
        for value in (scope, model, provider, endpoint, connection, adapter)
    ):
        raise DraftAssistanceError("DRAFT_PROFILE_INVALID")
    try:
        value = DraftAssistanceProfileRevision(
            document["profileRevisionId"],
            document["profileDigest"],
            DraftScope(scope["namespace"], scope["securityDomain"]),
            ExactModelBinding(model["id"], model["revisionId"], model["digest"]),
            provider["id"],
            provider["revisionId"],
            provider["digest"],
            endpoint["id"],
            endpoint["revisionId"],
            endpoint["digest"],
            connection["id"],
            connection["revisionId"],
            connection["digest"],
            adapter["id"],
            adapter["revision"],
            document["outputSchemaVersion"],
            document["targetFormatVersion"],
            document["maximumInputBytes"],
            document["maximumOutputTokens"],
            document["totalTimeoutSeconds"],
        )
        pepper_path = Path(document["pepperFile"])
    except (KeyError, TypeError, ValueError) as exc:
        raise DraftAssistanceError("DRAFT_PROFILE_INVALID") from exc
    if not pepper_path.is_absolute():
        raise DraftAssistanceError("DRAFT_PROFILE_INVALID")
    return value, pepper_path


def build_draft_assistance_composition(
    *,
    database_url: str,
    runtime_configuration_path: Path,
    migrations_path: Path,
) -> DraftAssistanceComposition:
    if not runtime_configuration_path.is_absolute():
        raise DraftAssistanceError("DRAFT_PROFILE_INVALID")
    try:
        document = json.loads(runtime_configuration_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DraftAssistanceError("DRAFT_PROFILE_UNAVAILABLE") from exc
    profile, pepper_path = _profile(document)
    try:
        pepper = pepper_path.read_bytes()
    except OSError as exc:
        raise DraftAssistanceError("IDEMPOTENCY_PEPPER_UNAVAILABLE") from exc
    if len(pepper) < 32:
        raise DraftAssistanceError("IDEMPOTENCY_PEPPER_INVALID")

    model_repository = PostgresModelGovernanceRepository(
        database_url,
        migration_path=migrations_path / "0019_model_governance.sql",
    )
    draft_repository = None
    resource_use_owner = None
    evidence_owner = None
    try:
        draft_repository = PostgresDraftAssistanceRepository(
            database_url,
            migration_path=migrations_path / "0023_draft_assistance.sql",
        )
        resource_use_owner = PostgresContextualResourceUseOwner(database_url)
        evidence_owner = PostgresDraftEvidenceOwner(database_url)
        model_repository.migrate()
        draft_repository.migrate()
        service = DraftAssistanceService(
            draft_repository,
            profile,
            _UnavailableAuthorization(),
            GovernedProfileModelResolver(model_repository),
            StaticPepperResolver(
                document["pepperReference"], document["pepperVersion"], pepper
            ),
            OpaqueSyntheticCredentialResolver(),
            DeterministicSyntheticDraftTransport(),
            resource_use_owner,
            evidence_owner,
        )
        return DraftAssistanceComposition(
            service,
            draft_repository,
            resource_use_owner,
            evidence_owner,
            model_repository,
        )
    except Exception:
        if evidence_owner is not None:
            evidence_owner.close()
        if resource_use_owner is not None:
            resource_use_owner.close()
        if draft_repository is not None:
            draft_repository.close()
        model_repository.close()
        raise
