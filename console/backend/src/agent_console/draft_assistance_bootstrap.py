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
from agent_console.draft_assistance_policy import PolicyValidationError, policy_for
from agent_console.draft_assistance_postgres import (
    PostgresContextualResourceUseOwner,
    PostgresDraftAssistanceRepository,
    PostgresDraftEvidenceOwner,
)
from agent_console.draft_assistance_support import (
    InMemoryProviderCallBudget,
    OpaqueSyntheticCredentialResolver,
)
from agent_console.draft_provider_budget_postgres import PostgresProviderCallBudget
from agent_console.kimi_responses_draft_adapter import (
    ADAPTER_ID as KIMI_ADAPTER_ID,
)
from agent_console.kimi_responses_draft_adapter import (
    PROTOCOL as KIMI_PROTOCOL,
)
from agent_console.kimi_responses_draft_adapter import (
    ExactFileKimiCredentialResolver,
    KimiResponsesConfiguration,
    KimiResponsesDraftTransport,
)
from agent_console.model_binding_resolution import (
    ExactModelBinding,
    ExactModelUse,
    ModelConsumptionScope,
)
from agent_console.model_governance import ModelScope
from agent_console.model_governance_authorization import ModelGovernanceExactResolver
from agent_console.model_governance_postgres import PostgresModelGovernanceRepository
from agent_console.openai_responses_draft_adapter import (
    ADAPTER_ID as OPENAI_ADAPTER_ID,
)
from agent_console.openai_responses_draft_adapter import (
    PROTOCOL as OPENAI_PROTOCOL,
)
from agent_console.openai_responses_draft_adapter import (
    ExactFileOpenAICredentialResolver,
    OpenAIResponsesConfiguration,
    OpenAIResponsesDraftTransport,
)


class _UnavailableAuthorization:
    """The formal Workbench authority adapter replaces this before serving."""

    def __getattr__(self, name):
        del name
        raise DraftAssistanceError("DRAFT_AUTHORIZATION_UNAVAILABLE")


class GovernedProfileModelResolver:
    """Adapt the exact Model owner resolver to one server-owned assistance profile."""

    def __init__(
        self,
        repository: PostgresModelGovernanceRepository,
        real_configuration: (
            OpenAIResponsesConfiguration | KimiResponsesConfiguration | None
        ) = None,
    ) -> None:
        self.repository = repository
        self.resolver = ModelGovernanceExactResolver(repository, repository, repository)
        self.real_configuration = real_configuration

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
        if self.real_configuration is not None:
            owner_scope = ModelScope(
                profile.scope.namespace, profile.scope.security_domain
            )
            revision = self.repository.get_revision(
                owner_scope, profile.binding.resource_id, profile.binding.revision_id
            )
            configuration = self.repository.resolve_exact(
                owner_scope,
                value.provider,
                value.endpoint,
                value.connection_profile,
            )
            limits = {item.name: item.value for item in revision.invocation_limits}
            if (
                revision.provider_native_model_id
                != self.real_configuration.native_model_id
                or configuration.provider.adapter_contract_id != profile.adapter_id
                or configuration.provider.adapter_contract_revision_id
                != profile.adapter_revision
                or configuration.endpoint.normalized_address_reference
                != self.real_configuration.responses_url
                or configuration.connection_profile.secret_reference.reference_id
                != self.real_configuration.credential_reference
                or configuration.connection_profile.secret_reference.version
                != self.real_configuration.credential_version
                or configuration.connection_profile.connect_timeout_seconds
                != self.real_configuration.connect_timeout_seconds
                or configuration.connection_profile.request_timeout_seconds
                != self.real_configuration.total_timeout_seconds
                or limits.get("max_input_tokens")
                != self.real_configuration.maximum_input_tokens
                or limits.get("max_output_tokens")
                != self.real_configuration.maximum_output_tokens
            ):
                raise DraftAssistanceError("MODEL_BINDING_MISMATCH")
        return value


@dataclass(slots=True)
class DraftAssistanceComposition:
    service: DraftAssistanceService
    draft_repository: PostgresDraftAssistanceRepository
    resource_use_owner: PostgresContextualResourceUseOwner
    evidence_owner: PostgresDraftEvidenceOwner
    model_repository: PostgresModelGovernanceRepository
    budget_owner: PostgresProviderCallBudget | None = None

    def close(self) -> None:
        if self.budget_owner is not None:
            self.budget_owner.close()
        self.evidence_owner.close()
        self.resource_use_owner.close()
        self.draft_repository.close()
        self.model_repository.close()


def _profile(
    document: object,
    *,
    allow_local_https_mock: bool = False,
) -> tuple[
    DraftAssistanceProfileRevision,
    Path,
    OpenAIResponsesConfiguration | KimiResponsesConfiguration | None,
    dict[str, int | str] | None,
]:
    common = {
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
    }
    if not isinstance(document, dict):
        raise DraftAssistanceError("DRAFT_PROFILE_INVALID")
    transport_kind = document.get("transportKind")
    real_fields = {
        "providerProtocol",
        "executionClass",
        "responsesUrl",
        "nativeModelId",
        "maximumInputTokens",
        "maximumResponseBytes",
        "connectTimeoutSeconds",
        "readTimeoutSeconds",
        "credential",
        "tls",
        "budget",
    }
    provider_protocol = document.get("providerProtocol")
    provider_fields = (
        {"reasoningEffort"} if provider_protocol == KIMI_PROTOCOL else set()
    )
    expected = (
        common
        if transport_kind == "SYNTHETIC"
        else (common | real_fields | provider_fields)
    )
    if (
        isinstance(document.get("adapter"), dict)
        and document["adapter"].get("revision") == "v2"
    ):
        expected = expected | {"policyDigest"}
    if (
        set(document) != expected
        or document.get("schemaVersion") != ("draft-assistance-runtime.v1")
        or transport_kind not in {"SYNTHETIC", "REAL_PROVIDER"}
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
    ) or (
        set(scope) != {"namespace", "securityDomain"}
        or set(model) != {"id", "revisionId", "digest"}
        or set(provider) != {"id", "revisionId", "digest"}
        or set(endpoint) != {"id", "revisionId", "digest"}
        or set(connection) != {"id", "revisionId", "digest"}
        or set(adapter) != {"id", "revision"}
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
    if transport_kind == "SYNTHETIC":
        return value, pepper_path, None, None
    credential = document["credential"]
    tls = document["tls"]
    budget = document["budget"]
    if (
        (
            document["executionClass"] != "REAL_PROVIDER"
            and not (
                allow_local_https_mock
                and document["executionClass"] == "LOCAL_HTTPS_MOCK"
            )
        )
        or not isinstance(credential, dict)
        or set(credential)
        != {"reference", "version", "resolverId", "resolverRevision", "file"}
        or not isinstance(tls, dict)
        or set(tls) != {"caFile"}
        or not isinstance(budget, dict)
        or set(budget)
        != {
            "ledgerId",
            "currency",
            "callCap",
            "totalCostCapMicrousd",
            "inputPriceMicrousdPerMillionTokens",
            "outputPriceMicrousdPerMillionTokens",
        }
        or budget["currency"] != "USD"
        or not isinstance(budget["ledgerId"], str)
        or not budget["ledgerId"]
        or budget["ledgerId"].strip() != budget["ledgerId"]
        or any(
            not isinstance(budget[field], int)
            or isinstance(budget[field], bool)
            or budget[field] < 1
            for field in ("callCap", "totalCostCapMicrousd")
        )
        or any(
            not isinstance(budget[field], int)
            or isinstance(budget[field], bool)
            or budget[field] < 0
            for field in (
                "inputPriceMicrousdPerMillionTokens",
                "outputPriceMicrousdPerMillionTokens",
            )
        )
    ):
        raise DraftAssistanceError("DRAFT_PROFILE_INVALID")
    try:
        credential_file = Path(credential["file"])
        ca_file = None if tls["caFile"] is None else Path(tls["caFile"])
        common_configuration = (
            document["executionClass"],
            document["responsesUrl"],
            document["nativeModelId"],
            credential["reference"],
            credential["version"],
            credential["resolverId"],
            credential["resolverRevision"],
            credential_file,
            document["connectTimeoutSeconds"],
            document["readTimeoutSeconds"],
            document["totalTimeoutSeconds"],
            document["maximumInputTokens"],
            document["maximumOutputTokens"],
            document["maximumResponseBytes"],
            budget["inputPriceMicrousdPerMillionTokens"],
            budget["outputPriceMicrousdPerMillionTokens"],
        )
        policy = policy_for(value.adapter_revision, value.output_schema_version)
        if policy.revision == "v2" and document["policyDigest"] != policy.digest:
            raise DraftAssistanceError("DRAFT_POLICY_MISMATCH")
        adapter_tuple = (
            document["providerProtocol"],
            value.adapter_id,
        )
        if adapter_tuple == (
            OPENAI_PROTOCOL,
            OPENAI_ADAPTER_ID,
        ):
            real_configuration = OpenAIResponsesConfiguration(
                *common_configuration, ca_file
            )
        elif adapter_tuple == (
            KIMI_PROTOCOL,
            KIMI_ADAPTER_ID,
        ):
            real_configuration = KimiResponsesConfiguration(
                *common_configuration, document["reasoningEffort"], ca_file
            )
        else:
            raise DraftAssistanceError("DRAFT_PROFILE_INVALID")
        normalized_budget = {
            "ledgerId": budget["ledgerId"],
            "callCap": budget["callCap"],
            "totalCostCapMicrousd": budget["totalCostCapMicrousd"],
            "inputPriceMicrousdPerMillionTokens": budget[
                "inputPriceMicrousdPerMillionTokens"
            ],
            "outputPriceMicrousdPerMillionTokens": budget[
                "outputPriceMicrousdPerMillionTokens"
            ],
        }
    except (TypeError, ValueError, PolicyValidationError) as exc:
        raise DraftAssistanceError("DRAFT_PROFILE_INVALID") from exc
    return value, pepper_path, real_configuration, normalized_budget


def build_draft_assistance_composition(
    *,
    database_url: str,
    runtime_configuration_path: Path,
    migrations_path: Path,
    allow_local_https_mock: bool = False,
) -> DraftAssistanceComposition:
    if not runtime_configuration_path.is_absolute():
        raise DraftAssistanceError("DRAFT_PROFILE_INVALID")
    try:
        document = json.loads(runtime_configuration_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DraftAssistanceError("DRAFT_PROFILE_UNAVAILABLE") from exc
    profile, pepper_path, real_configuration, budget_configuration = _profile(
        document, allow_local_https_mock=allow_local_https_mock
    )
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
    budget_owner = None
    try:
        draft_repository = PostgresDraftAssistanceRepository(
            database_url,
            migration_path=migrations_path / "0023_draft_assistance.sql",
        )
        resource_use_owner = PostgresContextualResourceUseOwner(database_url)
        evidence_owner = PostgresDraftEvidenceOwner(database_url)
        model_repository.migrate()
        draft_repository.migrate()
        if real_configuration is None:
            credentials = OpaqueSyntheticCredentialResolver()
            transport = DeterministicSyntheticDraftTransport()
            budget_owner_for_service = InMemoryProviderCallBudget()
        else:
            if budget_configuration is None:
                raise DraftAssistanceError("PROVIDER_BUDGET_PROFILE_INVALID")
            budget_owner = PostgresProviderCallBudget(
                database_url,
                migration_path=migrations_path / "0024_draft_provider_budget.sql",
                profile=profile,
                ledger_id=str(budget_configuration["ledgerId"]),
                call_cap=int(budget_configuration["callCap"]),
                total_cost_cap_microusd=int(
                    budget_configuration["totalCostCapMicrousd"]
                ),
                input_price_microusd_per_million_tokens=int(
                    budget_configuration["inputPriceMicrousdPerMillionTokens"]
                ),
                output_price_microusd_per_million_tokens=int(
                    budget_configuration["outputPriceMicrousdPerMillionTokens"]
                ),
            )
            budget_owner.migrate_and_configure()
            resolver_arguments = {
                "expected_profile_revision_id": profile.profile_revision_id,
                "expected_connection_profile_id": profile.connection_profile_id,
                "expected_connection_profile_revision_id": (
                    profile.connection_profile_revision_id
                ),
            }
            if isinstance(real_configuration, KimiResponsesConfiguration):
                credentials = ExactFileKimiCredentialResolver(
                    real_configuration, **resolver_arguments
                )
                transport = KimiResponsesDraftTransport(real_configuration)
            else:
                credentials = ExactFileOpenAICredentialResolver(
                    real_configuration, **resolver_arguments
                )
                transport = OpenAIResponsesDraftTransport(real_configuration)
            budget_owner_for_service = budget_owner
        service = DraftAssistanceService(
            draft_repository,
            profile,
            _UnavailableAuthorization(),
            GovernedProfileModelResolver(model_repository, real_configuration),
            StaticPepperResolver(
                document["pepperReference"], document["pepperVersion"], pepper
            ),
            credentials,
            transport,
            resource_use_owner,
            evidence_owner,
            budget_owner_for_service,
        )
        return DraftAssistanceComposition(
            service,
            draft_repository,
            resource_use_owner,
            evidence_owner,
            model_repository,
            budget_owner,
        )
    except Exception:
        if budget_owner is not None:
            budget_owner.close()
        if evidence_owner is not None:
            evidence_owner.close()
        if resource_use_owner is not None:
            resource_use_owner.close()
        if draft_repository is not None:
            draft_repository.close()
        model_repository.close()
        raise
