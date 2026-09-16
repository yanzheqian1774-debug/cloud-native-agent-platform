from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest
from agent_console.authority_contracts import (
    AuthenticationSource,
    AuthorityScope,
    TrustedRequestContext,
)
from agent_console.draft_assistance import (
    DeterministicSyntheticDraftTransport,
    DraftAssistanceProfileRevision,
    DraftAssistanceService,
    DraftInvocationState,
    DraftScope,
    StaticPepperResolver,
)
from agent_console.draft_assistance_postgres import (
    PostgresContextualResourceUseOwner,
    PostgresDraftAssistanceRepository,
    PostgresDraftEvidenceOwner,
    contextual_reader,
    evidence_reader,
)
from agent_console.draft_assistance_support import (
    ExactProfileModelResolver,
    InMemoryProviderCallBudget,
    OpaqueSyntheticCredentialResolver,
    StaticDraftAuthorization,
)
from agent_console.model_binding_resolution import (
    ExactModelBinding,
    ModelConsumptionScope,
    ResolvedModelBinding,
)
from agent_console.model_governance import (
    ConnectionProfileRevisionIdentity,
    EndpointRevisionIdentity,
    ModelEligibility,
    ModelEligibilityState,
    ModelLifecycleHighWater,
    ModelRevisionIdentity,
    ModelScope,
    ProviderRevisionIdentity,
)
from agent_console.model_governance_postgres import PostgresModelGovernanceRepository

DIGEST = "a" * 64
ROOT = Path(__file__).parents[1]
MIGRATIONS = ROOT / "migrations"


@pytest.fixture(scope="module")
def database_url():
    value = os.environ.get("DRAFT_ASSISTANCE_TEST_DATABASE_URL")
    if not value:
        pytest.skip("DRAFT_ASSISTANCE_TEST_DATABASE_URL is not configured")
    info = psycopg.conninfo.conninfo_to_dict(value)
    if info.get("dbname") != "s5_v023_impl_319":
        pytest.fail("refusing to reset a database not owned by S5-V023-IMPL-319")
    with psycopg.connect(value, autocommit=True) as connection:
        connection.execute("DROP SCHEMA IF EXISTS draft_assistance CASCADE")
        connection.execute("DROP SCHEMA IF EXISTS contextual_resource_use CASCADE")
        connection.execute("DROP SCHEMA IF EXISTS model_evidence CASCADE")
        connection.execute("DROP SCHEMA IF EXISTS model_governance CASCADE")
    return value


def _context() -> TrustedRequestContext:
    return TrustedRequestContext(
        "human:alice",
        AuthorityScope("tenant-a", "quality"),
        "session-319",
        AuthenticationSource.BROWSER_SESSION,
        "policy-319",
    )


def _profile() -> DraftAssistanceProfileRevision:
    return DraftAssistanceProfileRevision(
        "draft-profile-revision-319",
        DIGEST,
        DraftScope("tenant-a", "quality"),
        ExactModelBinding("model-319", "model-revision-319", DIGEST),
        "provider-319",
        "provider-revision-319",
        DIGEST,
        "endpoint-319",
        "endpoint-revision-319",
        DIGEST,
        "connection-profile-319",
        "connection-profile-revision-319",
        DIGEST,
        "synthetic-draft-transport",
        "v1",
    )


def _resolved() -> ResolvedModelBinding:
    return ResolvedModelBinding(
        ModelConsumptionScope("tenant-a", "quality"),
        _profile().binding,
        ProviderRevisionIdentity("provider-319", "provider-revision-319", DIGEST),
        EndpointRevisionIdentity("endpoint-319", "endpoint-revision-319", DIGEST),
        ConnectionProfileRevisionIdentity(
            "connection-profile-319", "connection-profile-revision-319", DIGEST
        ),
        ModelEligibility(
            ModelScope("tenant-a", "quality"),
            ModelRevisionIdentity("model-319", "model-revision-319", DIGEST),
            ModelEligibilityState.PUBLISHED_ENABLED,
            ModelLifecycleHighWater(4, "model-fact-319", DIGEST),
        ),
    )


def _service(database_url):
    repository = PostgresDraftAssistanceRepository(
        database_url, migration_path=MIGRATIONS / "0023_draft_assistance.sql"
    )
    repository.migrate()
    resource_use = PostgresContextualResourceUseOwner(database_url)
    evidence = PostgresDraftEvidenceOwner(database_url)
    transport = DeterministicSyntheticDraftTransport()
    service = DraftAssistanceService(
        repository,
        _profile(),
        StaticDraftAuthorization(clock=lambda: datetime(2029, 1, 1, tzinfo=UTC)),
        ExactProfileModelResolver(_resolved()),
        StaticPepperResolver("pepper:s5-319", "v1", b"p" * 32),
        OpaqueSyntheticCredentialResolver(),
        transport,
        resource_use,
        evidence,
        InMemoryProviderCallBudget(),
        clock=lambda: datetime(2029, 1, 1, tzinfo=UTC),
    )
    return service, repository, resource_use, evidence, transport


def test_0019_and_0023_install_without_reusing_another_task_database(database_url):
    models = PostgresModelGovernanceRepository(
        database_url, migration_path=MIGRATIONS / "0019_model_governance.sql"
    )
    models.migrate()
    models.compatibility()
    models.close()
    service, repository, resource_use, evidence, _ = _service(database_url)
    del service
    repository.close()
    resource_use.close()
    evidence.close()


def test_restart_preserves_metadata_and_never_persists_raw_content(database_url):
    raw = "S5-319-RAW-正文-季度末将缺陷率降至百分之一"
    service, repository, resource_use, evidence, transport = _service(database_url)
    result = service.begin(_context(), key="postgres-key-319", content=raw)
    assert result.invocation.state is DraftInvocationState.SUCCEEDED
    assert transport.dispatch_count == 1
    invocation_id = result.invocation.invocation_id
    service.observe(_context(), invocation_id)
    assert transport.dispatch_count == 1
    with psycopg.connect(database_url) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM model_evidence.records"
            ).fetchone()[0]
            == 1
        )
        assert (
            connection.execute(
                "SELECT count(*) FROM contextual_resource_use.facts"
            ).fetchone()[0]
            == 2
        )
    repository.close()
    resource_use.close()
    evidence.close()

    reopened = PostgresDraftAssistanceRepository(
        database_url, migration_path=MIGRATIONS / "0023_draft_assistance.sql"
    )
    restored = reopened.get(DraftScope("tenant-a", "quality"), invocation_id)
    assert restored is not None
    assert restored.state is DraftInvocationState.SUCCEEDED
    with psycopg.connect(database_url) as connection:
        count = connection.execute(
            "SELECT count(*) FROM ("
            "SELECT record::text AS body FROM draft_assistance.invocation_versions "
            "UNION ALL SELECT record::text FROM contextual_resource_use.operations "
            "UNION ALL SELECT record::text FROM contextual_resource_use.uses "
            "UNION ALL SELECT record::text FROM contextual_resource_use.facts "
            "UNION ALL SELECT record::text FROM model_evidence.records"
            ") AS records WHERE body LIKE %s",
            (f"%{raw}%",),
        ).fetchone()[0]
        evidence_record = connection.execute(
            "SELECT record FROM model_evidence.records LIMIT 1"
        ).fetchone()[0]
        use_record = connection.execute(
            "SELECT record FROM contextual_resource_use.uses LIMIT 1"
        ).fetchone()[0]
    assert count == 0
    assert evidence_reader(evidence_record) is not None
    assert contextual_reader(use_record) is not None
    assert evidence_reader({"schemaVersion": "future.v99"}) is None
    assert contextual_reader({"schemaVersion": "future.v99"}) is None
    reopened.close()

    serialized = str(evidence_record)
    for forbidden in (raw, "prompt", "response", "commitment", "pepper", "credential"):
        assert forbidden.lower() not in serialized.lower()
    assert evidence_record["modelId"] == "model-319"
    assert evidence_record["providerId"] == "provider-319"
    assert evidence_record["endpointId"] == "endpoint-319"
    assert evidence_record["adapterId"] == "synthetic-draft-transport"
    assert evidence_record["callCount"] == 1
    assert evidence_record["costMeasurement"] == "NOT_COLLECTED"

    with psycopg.connect(database_url) as connection, pytest.raises(psycopg.Error):
        connection.execute("UPDATE model_evidence.records SET record='{}'::jsonb")
