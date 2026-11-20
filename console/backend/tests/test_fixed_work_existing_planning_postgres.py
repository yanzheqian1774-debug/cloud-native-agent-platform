"""Real existing pricing/model repositories; no provider or authority mutation."""

import json
import os
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from agent_console.draft_assistance_bootstrap import _profile
from agent_console.draft_provider_budget_postgres import (
    PostgresProviderCallBudget,
    _digest,
)
from agent_console.fixed_work_existing_planning import build_existing_planning
from agent_console.model_governance_postgres import PostgresModelGovernanceRepository
from agent_console.provider_profile_pricing import prepare_revision
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

M = Path(__file__).parents[1] / "migrations"


@pytest.fixture
def database():
    url = os.environ.get("PLANNING323_TEST_DATABASE_URL")
    if not url:
        pytest.skip("isolated test PostgreSQL not configured")
    values = conninfo_to_dict(url)
    assert values.get("host") == "127.0.0.1" and values.get("port") == "53428"
    name = "cycle_entry_" + uuid4().hex
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        isolated = make_conninfo(url, dbname=name)
        try:
            yield isolated
        finally:
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def test_existing_runtime_checks_original_pricing_without_any_new_rows(
    database, tmp_path, monkeypatch
):
    document = json.loads(
        (
            Path(__file__).parents[3]
            / "docs/exec-plans/active/S5-V023-ARCH-323-PLANNING-RUNTIME.example.json"
        ).read_text()
    )
    pepper = tmp_path / "test-pepper"
    pepper.write_bytes(b"test-only-commitment" * 3)
    document["pepperFile"] = str(pepper)
    document["profileRevisionId"] = "cycle-successor"
    document["profileDigest"] = "b" * 64
    profile, _, _, cfg = _profile(document, planning=True)
    common = dict(
        database_url=database,
        migration_path=M / "0024_draft_provider_budget.sql",
        ledger_id=cfg["ledgerId"],
        call_cap=cfg["callCap"],
        total_cost_cap_microusd=cfg["totalCostCapMicrousd"],
        input_price_microusd_per_million_tokens=cfg[
            "inputPriceMicrousdPerMillionTokens"
        ],
        output_price_microusd_per_million_tokens=cfg[
            "outputPriceMicrousdPerMillionTokens"
        ],
    )
    with ExitStack() as cleanup:
        model = PostgresModelGovernanceRepository(
            database, migration_path=M / "0019_model_governance.sql"
        )
        cleanup.callback(model.close)
        model.migrate()
        root = PostgresProviderCallBudget(
            **common,
            profile=replace(
                profile, profile_revision_id="original-root", profile_digest="a" * 64
            ),
        )
        cleanup.callback(root.close)
        root.migrate_and_configure()
        with root.pool.connection() as c:
            record = c.execute(
                "SELECT record FROM draft_provider_budget.policies"
            ).fetchone()["record"]
        document["budget"]["profilePricingRootDigest"] = _digest(record)
        successor = PostgresProviderCallBudget(
            **common, profile=profile, profile_pricing_root_digest=_digest(record)
        )
        cleanup.callback(successor.close)
        with successor.pool.connection() as c, c.transaction():
            prepare_revision(c, successor)
        path = tmp_path / "planning.json"
        path.write_text(json.dumps(document))
        tables = (
            "policies",
            "profile_pricing_revisions",
            "reservations",
            "settlements",
        )

        def footprint():
            with root.pool.connection() as c:
                return tuple(
                    c.execute(
                        sql.SQL(
                            "SELECT count(*) n FROM draft_provider_budget.{}"
                        ).format(sql.Identifier(t))
                    ).fetchone()["n"]
                    for t in tables
                )

        before = footprint()

        def forbidden(*args, **kwargs):
            raise AssertionError("startup must not migrate, configure or reserve")

        monkeypatch.setattr(PostgresModelGovernanceRepository, "migrate", forbidden)
        monkeypatch.setattr(
            PostgresProviderCallBudget, "migrate_and_configure", forbidden
        )
        monkeypatch.setattr(PostgresProviderCallBudget, "reserve", forbidden)
        runtime = build_existing_planning(database, path, M)
        try:
            assert runtime.dependencies.provider.transport.dispatch_count == 0
            assert runtime.budget.ledger_id == root.ledger_id
            assert runtime.budget.profile_pricing_root_digest == _digest(record)
            assert runtime.dependencies.exact_admission_factory is None
            assert footprint() == before == (1, 1, 0, 0)
        finally:
            runtime.close()
        document["budget"]["callCap"] += 1
        path.write_text(json.dumps(document))
        with pytest.raises(Exception, match="PROFILE_CONFLICT"):
            build_existing_planning(database, path, M)
        assert footprint() == before
