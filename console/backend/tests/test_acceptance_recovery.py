"""Recovery failure tests use private temporary assets and fake owner ports only."""

from contextlib import ExitStack, nullcontext
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from agent_console import acceptance_recovery as recovery
from agent_console import authority_foundation as authority
from agent_console.authority_contracts import AuthorityError
from agent_console.authority_postgres import ADAPTER, PostgresAuthorityRepository
from agent_console.browser_session_application import BrowserSessionPolicy
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_assets_reject_change_missing_permissions_and_symlink(tmp_path):
    asset = (tmp_path / "key").resolve()
    asset.write_bytes(b"isolated-test-asset")
    asset.chmod(0o600)
    expected = {str(asset): recovery.file_identity(asset)}
    recovery.verify_files(expected)
    asset.chmod(0o644)
    with pytest.raises(recovery.RecoveryError, match="ASSET_MISMATCH"):
        recovery.verify_files(expected)
    asset.chmod(0o600)
    asset.write_bytes(b"changed")
    with pytest.raises(recovery.RecoveryError, match="ASSET_MISMATCH"):
        recovery.verify_files(expected)
    asset.unlink()
    with pytest.raises(recovery.RecoveryError, match="ASSET_UNAVAILABLE"):
        recovery.verify_files(expected)
    asset.symlink_to(tmp_path / "missing")
    with pytest.raises(recovery.RecoveryError, match="ASSET_OWNERSHIP"):
        recovery.verify_files(expected)


@pytest.mark.parametrize(
    "field", ["systemIdentifier", "database", "tables", "columnsDigest"]
)
def test_database_changes_are_not_repaired(field):
    expected = dict.fromkeys(
        ["systemIdentifier", "database", "tables", "columnsDigest"], "original"
    )
    changed = {**expected, field: "changed"}
    with pytest.raises(recovery.RecoveryError, match="DATABASE_SNAPSHOT_MISMATCH"):
        recovery.verify_database(expected, changed)
    assert changed[field] == "changed"


@pytest.mark.parametrize("lock,clients", [(False, 0), (True, 1)])
def test_competing_writer_refused(lock, clients):
    results = iter([(lock,), (clients,)])
    connection = SimpleNamespace(
        execute=lambda *_: SimpleNamespace(fetchone=lambda: next(results))
    )
    with pytest.raises(recovery.RecoveryError, match="COMPETING"):
        recovery.acquire_writer(connection, "isolated")


def test_mutation_routes_never_reach_application():
    app = FastAPI()
    called = []

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    def endpoint(path):
        called.append(path)
        return {"ok": True}

    recovery.install_recovery_boundary(app, lambda: None)
    with TestClient(app) as client:
        for path in [
            "problems",
            "draft-assistance/invocations",
            "draft-assistance/invocations/x/observe",
            "authorization/grant-requests",
            "authorization/grant-requests/x/decisions",
        ]:
            assert client.post("/api/workbench/v1/" + path, json={}).status_code == 403
        assert called == []
        assert client.get("/api/workbench/v1/problems").status_code == 200
        assert client.post("/api/workbench/v1/session").status_code == 200


def test_changed_epoch_blocks_login_as_well_as_reads():
    app = FastAPI()

    def stale():
        raise AuthorityError("AUTHORITY_RECOVERY_REQUIRED")

    recovery.install_recovery_boundary(app, stale)
    with TestClient(app) as client:
        assert client.get("/api/workbench/v1/login").status_code == 503
        assert client.get("/api/workbench/v1/problems").status_code == 503
        assert client.post("/api/workbench/v1/session").status_code == 503


@pytest.mark.parametrize("valid", [True, False])
def test_existing_schema_validation_executes_no_ddl(tmp_path, valid):
    migration = tmp_path / "0018_test.sql"
    migration.write_text("must never execute this DDL")
    repo = object.__new__(PostgresAuthorityRepository)
    repo.migration_path = migration
    queries = []
    rows = (
        [{"version": 18, "checksum": repo.migration_checksum, "adapter": ADAPTER}]
        if valid
        else []
    )

    def execute(query, *_):
        queries.append(query)
        return SimpleNamespace(fetchall=lambda: rows)

    connection = SimpleNamespace(execute=execute, transaction=nullcontext)
    repo.pool = SimpleNamespace(connection=lambda: nullcontext(connection))
    if valid:
        repo.verify_existing_schema()
    else:
        with pytest.raises(AuthorityError):
            repo.verify_existing_schema()
    assert all(q.startswith(("SET TRANSACTION READ ONLY", "SELECT")) for q in queries)
    assert migration.read_text() == "must never execute this DDL"


@pytest.mark.parametrize("active", [(1, "a" * 64, 1), None, (2, "b" * 64, 2)])
def test_existing_foundation_never_migrates_or_activates(monkeypatch, tmp_path, active):
    generation = SimpleNamespace(generation=1, digest="a" * 64, local_accounts=())
    monkeypatch.setattr(
        authority.StaticAuthorityLoader, "load", lambda *a, **k: generation
    )
    calls = []
    repository = SimpleNamespace(
        verify_existing_schema=lambda: calls.append("verify"),
        active_generation=lambda: active,
        close=lambda: None,
    )
    monkeypatch.setattr(
        authority, "PostgresAuthorityRepository", lambda *a, **k: repository
    )
    gate = SimpleNamespace(require_ready=lambda **kwargs: calls.append("gate"))
    monkeypatch.setattr(authority, "HostRecoveryControl", lambda *a: gate)
    key = tmp_path / "key"
    key.write_bytes(b"k" * 32)
    runtime = SimpleNamespace(
        generation_path=Path("/not-used"),
        generation_digest="a" * 64,
        database_url="not-used",
        migration_path=Path("/not-used"),
        recovery_control_path=Path("/not-used"),
        database_fingerprint="test",
        csrf_signing_key_path=key,
        continuation_signing_key_path=key,
    )
    policy = BrowserSessionPolicy(
        login_nonce_lifetime=timedelta(minutes=5),
        idle_lifetime=timedelta(minutes=30),
        absolute_lifetime=timedelta(hours=8),
        csrf_lifetime=timedelta(minutes=10),
    )
    if active == (1, "a" * 64, 1):
        authority.build_authority_foundation(runtime, policy, existing_only=True)
        assert calls == ["verify", "gate"]
    else:
        with pytest.raises(AuthorityError, match="AUTHORITY_RECOVERY_REQUIRED"):
            authority.build_authority_foundation(runtime, policy, existing_only=True)
        assert calls == ["verify"]
    assert key.read_bytes() == b"k" * 32


def test_recovery_composition_has_no_provider_or_creation(monkeypatch):
    captured = {}
    fake_pool = SimpleNamespace(close=lambda: None)
    problems = SimpleNamespace(pool=fake_pool)
    drafts = SimpleNamespace(close=lambda: None)
    foundation = SimpleNamespace(
        generation_controller=object(),
        repository=object(),
        grants=SimpleNamespace(authorization=object()),
        sessions=object(),
        close=lambda: None,
    )
    monkeypatch.setattr(
        recovery, "PostgresBusinessProblemRepository", lambda *a, **k: problems
    )
    monkeypatch.setattr(
        recovery, "PostgresDraftAssistanceRepository", lambda *a, **k: drafts
    )

    def build(*a, **kwargs):
        assert kwargs["existing_only"] is True
        return foundation

    def bff(*a, **kwargs):
        captured.update(kwargs)
        return FastAPI()

    monkeypatch.setattr(recovery, "build_authority_foundation", build)
    monkeypatch.setattr(recovery, "create_workbench_bff", bff)
    with ExitStack() as stack:
        recovery.build_application(
            SimpleNamespace(database_url="isolated"), Path("/migrations"), stack
        )
    assert [op.name for op in captured["operations"]] == [
        "LIST_PROBLEMS",
        "READ_PROBLEM",
    ]
    assert "grant_administration" not in captured
    app = FastAPI()
    captured["route_installers"][0](app, None, None, None)
    routes = [r for r in app.routes if r.path.startswith("/api/")]
    assert len(routes) == 1 and routes[0].methods == {"GET"}
