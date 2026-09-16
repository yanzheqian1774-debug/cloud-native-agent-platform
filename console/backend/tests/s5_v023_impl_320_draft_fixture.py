"""Exact Kimi Draft Assistance fixture owned by S5-V023-IMPL-320."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from agent_console.draft_assistance_bootstrap import (
    DraftAssistanceComposition,
    build_draft_assistance_composition,
)
from agent_console.kimi_responses_draft_adapter import (
    ADAPTER_ID,
    ADAPTER_REVISION,
    PROTOCOL,
)
from agent_console.model_governance import (
    InvocationLimit,
    ModelConnectionProfileRevision,
    ModelDefinition,
    ModelEndpointRevision,
    ModelLifecycleAction,
    ModelLifecycleFact,
    ModelProviderRevision,
    ModelRevision,
    ModelScope,
    SecretReference,
)
from agent_console.model_governance_postgres import PostgresModelGovernanceRepository

MIGRATIONS = Path(__file__).parents[1] / "migrations"
QUOTE_LABEL = "TEST_ONLY_SYNTHETIC_USD_QUOTE / NOT_KIMI_PRICE"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def build_fixture(
    database_url: str,
    runtime_directory: Path,
    *,
    responses_url: str | None = None,
    ca_file: Path | None = None,
    credential_file: Path | None = None,
) -> DraftAssistanceComposition:
    if responses_url is None or ca_file is None or credential_file is None:
        raise ValueError("S5_320_LOCAL_KIMI_FIXTURE_INCOMPLETE")
    now = datetime(2029, 1, 1, tzinfo=UTC)
    scope = ModelScope("tenant-a", "quality")
    definition = ModelDefinition(
        scope,
        "model:s5-320-kimi-mock",
        "team:draft-assistance",
        "human:fixture-owner",
        now,
    )
    provider = ModelProviderRevision(
        scope,
        "provider:s5-320-kimi-mock",
        "provider-revision:s5-320:1",
        ADAPTER_ID,
        ADAPTER_REVISION,
        ("CHAT",),
        "human:fixture-owner",
        now,
    )
    endpoint = ModelEndpointRevision(
        scope,
        "endpoint:s5-320-kimi-mock",
        "endpoint-revision:s5-320:1",
        responses_url,
        "test-only",
        ("HTTPS", "NO_REDIRECT"),
        "human:fixture-owner",
        now,
    )
    connection = ModelConnectionProfileRevision(
        scope,
        "connection-profile:s5-320-kimi-mock",
        "connection-profile-revision:s5-320:1",
        endpoint.identity,
        SecretReference("secret-reference:s5-320-kimi-mock", "mock-v1"),
        2,
        5,
        "human:fixture-owner",
        now,
    )
    revision = ModelRevision(
        scope,
        definition.model_id,
        "model-revision:s5-320:1",
        1,
        None,
        provider.identity,
        endpoint.identity,
        connection.identity,
        "mock-kimi-k3-320",
        ("JSON_SCHEMA",),
        ("CHAT", "STRUCTURED_OUTPUT"),
        (
            InvocationLimit("max_input_tokens", 20_000, "TOKEN"),
            InvocationLimit("max_output_tokens", 4096, "TOKEN"),
        ),
        "human:fixture-owner",
        now,
    )
    repository = PostgresModelGovernanceRepository(
        database_url, migration_path=MIGRATIONS / "0019_model_governance.sql"
    )
    repository.migrate()
    repository.create(definition)
    repository.add_provider_revision(provider)
    repository.add_endpoint_revision(endpoint)
    repository.add_connection_profile_revision(connection)
    repository.add_revision(revision)
    repository.advance_head(
        scope,
        definition.model_id,
        revision.revision_id,
        expected_aggregate_version=1,
    )
    for ordinal, action in enumerate(
        (
            ModelLifecycleAction.VALIDATED,
            ModelLifecycleAction.HUMAN_REVIEWED,
            ModelLifecycleAction.PUBLISHED,
        ),
        1,
    ):
        repository.append_fact(
            ModelLifecycleFact(
                scope,
                f"model-fact:s5-320:{ordinal}",
                revision.identity,
                ordinal,
                action,
                "human:fixture-reviewer",
                f"decision:s5-320:{ordinal}",
                now,
            )
        )
    repository.close()

    runtime_directory.mkdir(parents=True, exist_ok=True)
    pepper_path = runtime_directory / "draft-idempotency-pepper-320.bin"
    pepper_path.write_bytes(b"s5-320-kimi-mock-pepper-value-001")
    runtime_path = runtime_directory / "draft-assistance-runtime-320.json"
    runtime_document = {
        "schemaVersion": "draft-assistance-runtime.v1",
        "transportKind": "REAL_PROVIDER",
        "scope": {
            "namespace": scope.namespace,
            "securityDomain": scope.security_domain,
        },
        "profileRevisionId": "draft-profile-revision:s5-320:1",
        "profileDigest": _sha("draft-profile:s5-320:1"),
        "model": {
            "id": revision.model_id,
            "revisionId": revision.revision_id,
            "digest": revision.digest,
        },
        "provider": {
            "id": provider.provider_id,
            "revisionId": provider.revision_id,
            "digest": provider.digest,
        },
        "endpoint": {
            "id": endpoint.endpoint_id,
            "revisionId": endpoint.revision_id,
            "digest": endpoint.digest,
        },
        "connectionProfile": {
            "id": connection.profile_id,
            "revisionId": connection.revision_id,
            "digest": connection.digest,
        },
        "adapter": {"id": ADAPTER_ID, "revision": ADAPTER_REVISION},
        "outputSchemaVersion": "problem-draft-assistance-output.v1",
        "targetFormatVersion": "draft-assistance-target.v1",
        "maximumInputBytes": 32_768,
        "maximumOutputTokens": 4096,
        "totalTimeoutSeconds": 5,
        "pepperReference": "pepper-reference:s5-320",
        "pepperVersion": "v1",
        "pepperFile": str(pepper_path),
        "providerProtocol": PROTOCOL,
        "executionClass": "LOCAL_HTTPS_MOCK",
        "responsesUrl": responses_url,
        "nativeModelId": "mock-kimi-k3-320",
        "reasoningEffort": "low",
        "maximumInputTokens": 20_000,
        "maximumResponseBytes": 64_000,
        "connectTimeoutSeconds": 2,
        "readTimeoutSeconds": 3,
        "credential": {
            "reference": "secret-reference:s5-320-kimi-mock",
            "version": "mock-v1",
            "resolverId": "exact-file-resolver",
            "resolverRevision": "v1",
            "file": str(credential_file),
        },
        "tls": {"caFile": str(ca_file)},
        "budget": {
            "ledgerId": "s5-v023-impl-320-kimi-mock-provider",
            "currency": "USD",
            "callCap": 10,
            "totalCostCapMicrousd": 10_000_000,
            "inputPriceMicrousdPerMillionTokens": 1_000_000,
            "outputPriceMicrousdPerMillionTokens": 2_000_000,
        },
    }
    runtime_path.write_text(json.dumps(runtime_document, sort_keys=True))
    (runtime_directory / "s5-v023-impl-320-quote-label.txt").write_text(QUOTE_LABEL)
    return build_draft_assistance_composition(
        database_url=database_url,
        runtime_configuration_path=runtime_path,
        migrations_path=MIGRATIONS,
        allow_local_https_mock=True,
    )
