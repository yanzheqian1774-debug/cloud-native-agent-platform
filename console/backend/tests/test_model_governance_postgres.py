# ruff: noqa: E501
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest
from agent_console.model_governance import (
    ConnectionProfileRevisionIdentity,
    EndpointRevisionIdentity,
    InvocationLimit,
    ModelConnectionProfileRevision,
    ModelDefinition,
    ModelEligibilityState,
    ModelEndpointRevision,
    ModelGovernanceConflict,
    ModelGovernanceError,
    ModelGovernanceNotFound,
    ModelLifecycleAction,
    ModelLifecycleFact,
    ModelProviderRevision,
    ModelRevision,
    ModelScope,
    ProviderRevisionIdentity,
    SecretReference,
)
from agent_console.model_governance_postgres import (
    ADAPTER,
    MIGRATION_VERSION,
    PostgresModelGovernanceRepository,
)

DATABASE_URL = os.environ.get("MODEL_GOVERNANCE_TEST_DATABASE_URL") or os.environ.get(
    "WORKFLOW_RUNTIME_TEST_DATABASE_URL"
)
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL 15 required")
MIGRATION = Path(__file__).parents[1] / "migrations/0019_model_governance.sql"


def records(suffix: str):
    scope = ModelScope(f"model-governance-{suffix}", "acceptance")
    now = datetime.now(UTC)
    definition = ModelDefinition(
        scope,
        f"model:{suffix}",
        "team:model-governance",
        "principal:creator",
        now,
    )
    provider = ModelProviderRevision(
        scope,
        f"provider:{suffix}",
        f"provider-revision:{suffix}",
        "adapter:openai-compatible",
        "adapter-revision:1",
        ("CHAT", "EMBED"),
        "principal:operator",
        now,
    )
    endpoint = ModelEndpointRevision(
        scope,
        f"endpoint:{suffix}",
        f"endpoint-revision:{suffix}",
        "https://models.example.invalid/v1",
        "eu-west",
        ("HTTPS", "TLS_1_3"),
        "principal:operator",
        now,
    )
    profile = ModelConnectionProfileRevision(
        scope,
        f"profile:{suffix}",
        f"profile-revision:{suffix}",
        endpoint.identity,
        SecretReference(f"secret:model:{suffix}", "1"),
        10,
        60,
        "principal:operator",
        now,
    )
    revision = ModelRevision(
        scope,
        definition.model_id,
        f"model-revision:{suffix}",
        1,
        None,
        provider.identity,
        endpoint.identity,
        profile.identity,
        "reviewer-2026-09",
        ("JSON_SCHEMA", "TOOLS"),
        ("CHAT", "STRUCTURED_OUTPUT"),
        (
            InvocationLimit("max_input_tokens", 32_000, "TOKEN"),
            InvocationLimit("max_output_tokens", 4_096, "TOKEN"),
        ),
        "principal:operator",
        now,
    )
    return scope, definition, provider, endpoint, profile, revision


def fact(
    revision: ModelRevision, ordinal: int, action: ModelLifecycleAction
) -> ModelLifecycleFact:
    return ModelLifecycleFact(
        revision.scope,
        f"model-fact:{revision.model_id}:{ordinal}:{uuid.uuid4().hex}",
        revision.identity,
        ordinal,
        action,
        "principal:reviewer",
        f"decision:{ordinal}:{uuid.uuid4().hex}",
        datetime.now(UTC),
    )


def migrated_repository() -> PostgresModelGovernanceRepository:
    repository = PostgresModelGovernanceRepository(
        DATABASE_URL or "", migration_path=MIGRATION
    )
    repository.migrate()
    repository.compatibility()
    return repository


def persist_exact_graph(repository, values) -> None:
    _, definition, provider, endpoint, profile, revision = values
    repository.create(definition)
    repository.add_provider_revision(provider)
    repository.add_endpoint_revision(endpoint)
    repository.add_connection_profile_revision(profile)
    repository.add_revision(revision)


def test_real_postgresql_exact_graph_lifecycle_and_restart_readback() -> None:
    suffix = uuid.uuid4().hex
    values = records(suffix)
    scope, definition, provider, endpoint, profile, revision = values
    first = migrated_repository()
    persist_exact_graph(first, values)
    advanced = first.advance_head(
        scope,
        definition.model_id,
        revision.revision_id,
        expected_aggregate_version=1,
    )
    lifecycle = (
        fact(revision, 1, ModelLifecycleAction.VALIDATED),
        fact(revision, 2, ModelLifecycleAction.HUMAN_REVIEWED),
        fact(revision, 3, ModelLifecycleAction.PUBLISHED),
    )
    for item in lifecycle:
        first.append_fact(item)

    assert advanced.aggregate_version == 2
    assert advanced.current_revision_id == revision.revision_id
    assert (
        first.get_revision(scope, definition.model_id, revision.revision_id) == revision
    )
    assert (
        first.resolve_exact(
            scope, provider.identity, endpoint.identity, profile.identity
        ).connection_profile
        == profile
    )
    assert (
        first.read_lifecycle(
            scope, definition.model_id, revision.revision_id, through_ordinal=2
        ).state
        is ModelEligibilityState.HUMAN_REVIEWED
    )
    first.close()

    restarted = PostgresModelGovernanceRepository(
        DATABASE_URL or "", migration_path=MIGRATION
    )
    restarted.compatibility()
    recovered_definition = restarted.get(scope, definition.model_id)
    recovered_revision = restarted.get_revision(
        scope, definition.model_id, revision.revision_id
    )
    recovered_configuration = restarted.resolve_exact(
        scope, provider.identity, endpoint.identity, profile.identity
    )
    recovered_lifecycle = restarted.read_lifecycle(
        scope, definition.model_id, revision.revision_id
    )

    assert recovered_definition == advanced
    assert restarted.list(scope) == (advanced,)
    assert recovered_revision == revision
    assert recovered_revision.identity == revision.identity
    assert recovered_configuration.provider == provider
    assert recovered_configuration.endpoint == endpoint
    assert recovered_configuration.connection_profile == profile
    assert recovered_lifecycle.state is ModelEligibilityState.PUBLISHED_ENABLED
    assert recovered_lifecycle.allows_new_use is True
    assert recovered_lifecycle.high_water.fact_id == lifecycle[-1].fact_id
    assert recovered_lifecycle.high_water.fact_digest == lifecycle[-1].digest
    with pytest.raises(ModelGovernanceNotFound, match="MODEL_DEFINITION_NOT_FOUND"):
        restarted.get(ModelScope(scope.namespace, "foreign"), definition.model_id)
    restarted.close()


def test_postgresql_transactions_reject_conflicts_without_partial_writes() -> None:
    suffix = uuid.uuid4().hex
    values = records(suffix)
    scope, definition, provider, endpoint, profile, revision = values
    repository = migrated_repository()
    repository.create(definition)
    with pytest.raises(ModelGovernanceConflict, match="MODEL_DEFINITION_CONFLICT"):
        repository.create(definition)

    with pytest.raises(
        ModelGovernanceConflict,
        match="MODEL_CONNECTION_PROFILE_REVISION_CONFLICT",
    ):
        repository.add_connection_profile_revision(profile)
    repository.add_provider_revision(provider)
    repository.add_endpoint_revision(endpoint)
    repository.add_connection_profile_revision(profile)

    missing_configuration = ModelRevision(
        scope,
        definition.model_id,
        f"model-revision:missing:{suffix}",
        1,
        None,
        ProviderRevisionIdentity("provider:missing", "revision:1", "a" * 64),
        EndpointRevisionIdentity("endpoint:missing", "revision:1", "b" * 64),
        ConnectionProfileRevisionIdentity("profile:missing", "revision:1", "c" * 64),
        "native-model",
        (),
        (),
        (),
        "principal:operator",
        datetime.now(UTC),
    )
    with pytest.raises(ModelGovernanceConflict, match="MODEL_REVISION_CONFLICT"):
        repository.add_revision(missing_configuration)
    with pytest.raises(ModelGovernanceNotFound, match="MODEL_REVISION_NOT_FOUND"):
        repository.get_revision(
            scope, definition.model_id, missing_configuration.revision_id
        )

    repository.add_revision(revision)
    repository.advance_head(
        scope,
        definition.model_id,
        revision.revision_id,
        expected_aggregate_version=1,
    )
    with pytest.raises(ModelGovernanceConflict, match="MODEL_DEFINITION_STALE"):
        repository.advance_head(
            scope,
            definition.model_id,
            revision.revision_id,
            expected_aggregate_version=1,
        )

    with pytest.raises(ModelGovernanceConflict, match="MODEL_LIFECYCLE_CONFLICT"):
        repository.append_fact(fact(revision, 1, ModelLifecycleAction.HUMAN_REVIEWED))
    validated = fact(revision, 1, ModelLifecycleAction.VALIDATED)
    repository.append_fact(validated)
    with pytest.raises(ModelGovernanceConflict, match="MODEL_LIFECYCLE_CONFLICT"):
        repository.append_fact(fact(revision, 3, ModelLifecycleAction.PUBLISHED))
    reviewed = fact(revision, 2, ModelLifecycleAction.HUMAN_REVIEWED)
    repository.append_fact(reviewed)
    assert (
        repository.read_lifecycle(
            scope, definition.model_id, revision.revision_id
        ).high_water.fact_id
        == reviewed.fact_id
    )
    repository.close()


def test_postgresql_immutable_history_and_corrupt_record_fail_closed() -> None:
    suffix = uuid.uuid4().hex
    values = records(suffix)
    scope, definition, provider, _, _, _ = values
    repository = migrated_repository()
    persist_exact_graph(repository, values)

    with (
        repository.pool.connection() as connection,
        pytest.raises(psycopg.Error, match="IMMUTABLE_MODEL_GOVERNANCE_HISTORY"),
        connection.transaction(),
    ):
        connection.execute(
            "UPDATE model_governance.provider_revisions SET digest=%s WHERE namespace=%s AND security_domain=%s AND provider_id=%s AND revision_id=%s",
            (
                "f" * 64,
                scope.namespace,
                scope.security_domain,
                provider.provider_id,
                provider.revision_id,
            ),
        )

    corrupt_scope = ModelScope(
        f"model-governance-corrupt-{uuid.uuid4().hex}", "acceptance"
    )
    with repository.pool.connection() as connection, connection.transaction():
        connection.execute(
            "INSERT INTO model_governance.definitions(namespace,security_domain,model_id,owner_id,created_by,created_at,aggregate_version,current_revision_id,record) VALUES(%s,%s,%s,'owner','creator',now(),1,NULL,'{}'::jsonb)",
            (*repository._scope(corrupt_scope), "model:corrupt"),
        )
    with pytest.raises(ModelGovernanceError, match="MODEL_GOVERNANCE_STORAGE_CORRUPT"):
        repository.get(corrupt_scope, "model:corrupt")

    assert repository.get(scope, definition.model_id) == definition
    repository.close()


def test_migration_ledger_rejects_changed_bytes_after_restart(tmp_path: Path) -> None:
    repository = migrated_repository()
    with repository.pool.connection() as connection:
        ledger = connection.execute(
            "SELECT version,checksum,adapter FROM model_governance.schema_migrations WHERE version=%s",
            (MIGRATION_VERSION,),
        ).fetchone()
    assert ledger == {
        "version": MIGRATION_VERSION,
        "checksum": repository.migration_checksum,
        "adapter": ADAPTER,
    }
    repository.close()

    changed = tmp_path / "0019_model_governance.sql"
    changed.write_bytes(MIGRATION.read_bytes() + b"\n-- changed bytes\n")
    restarted = PostgresModelGovernanceRepository(
        DATABASE_URL or "", migration_path=changed
    )
    with pytest.raises(
        ModelGovernanceError, match="MODEL_GOVERNANCE_SCHEMA_INCOMPATIBLE"
    ):
        restarted.compatibility()
    restarted.close()
