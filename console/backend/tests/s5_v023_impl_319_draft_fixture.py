"""Synthetic, exact-model Draft Assistance fixture for S5-V023-IMPL-319."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from agent_console.draft_assistance_bootstrap import (
    DraftAssistanceComposition,
    build_draft_assistance_composition,
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


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def build_fixture(
    database_url: str, runtime_directory: Path
) -> DraftAssistanceComposition:
    now = datetime(2029, 1, 1, tzinfo=UTC)
    scope = ModelScope("tenant-a", "quality")
    definition = ModelDefinition(
        scope,
        "model:s5-319-synthetic",
        "team:draft-assistance",
        "human:fixture-owner",
        now,
    )
    provider = ModelProviderRevision(
        scope,
        "provider:s5-319-synthetic",
        "provider-revision:s5-319:1",
        "adapter:deterministic-synthetic",
        "adapter-revision:1",
        ("CHAT",),
        "human:fixture-owner",
        now,
    )
    endpoint = ModelEndpointRevision(
        scope,
        "endpoint:s5-319-synthetic",
        "endpoint-revision:s5-319:1",
        "https://synthetic.invalid/v1",
        "test-only",
        ("SYNTHETIC",),
        "human:fixture-owner",
        now,
    )
    connection = ModelConnectionProfileRevision(
        scope,
        "connection-profile:s5-319-synthetic",
        "connection-profile-revision:s5-319:1",
        endpoint.identity,
        SecretReference("secret-reference:s5-319-none", "synthetic-v1"),
        5,
        30,
        "human:fixture-owner",
        now,
    )
    revision = ModelRevision(
        scope,
        definition.model_id,
        "model-revision:s5-319:1",
        1,
        None,
        provider.identity,
        endpoint.identity,
        connection.identity,
        "synthetic-problem-draft-v1",
        ("JSON_SCHEMA",),
        ("CHAT", "STRUCTURED_OUTPUT"),
        (
            InvocationLimit("max_input_tokens", 4096, "TOKEN"),
            InvocationLimit("max_output_tokens", 1024, "TOKEN"),
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
                f"model-fact:s5-319:{ordinal}",
                revision.identity,
                ordinal,
                action,
                "human:fixture-reviewer",
                f"decision:s5-319:{ordinal}",
                now,
            )
        )
    repository.close()

    runtime_directory.mkdir(parents=True, exist_ok=True)
    pepper_path = runtime_directory / "draft-idempotency-pepper.bin"
    pepper_path.write_bytes(b"s5-319-synthetic-pepper-value-01")
    runtime_path = runtime_directory / "draft-assistance-runtime.json"
    runtime_path.write_text(
        json.dumps(
            {
                "schemaVersion": "draft-assistance-runtime.v1",
                "transportKind": "SYNTHETIC",
                "scope": {
                    "namespace": scope.namespace,
                    "securityDomain": scope.security_domain,
                },
                "profileRevisionId": "draft-profile-revision:s5-319:1",
                "profileDigest": _sha("draft-profile:s5-319:1"),
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
                "adapter": {
                    "id": "deterministic-synthetic-draft",
                    "revision": "v1",
                },
                "outputSchemaVersion": "problem-draft-assistance-output.v1",
                "targetFormatVersion": "draft-assistance-target.v1",
                "maximumInputBytes": 16384,
                "maximumOutputTokens": 1024,
                "totalTimeoutSeconds": 30,
                "pepperReference": "pepper-reference:s5-319",
                "pepperVersion": "v1",
                "pepperFile": str(pepper_path),
            },
            sort_keys=True,
        )
    )
    return build_draft_assistance_composition(
        database_url=database_url,
        runtime_configuration_path=runtime_path,
        migrations_path=MIGRATIONS,
    )
