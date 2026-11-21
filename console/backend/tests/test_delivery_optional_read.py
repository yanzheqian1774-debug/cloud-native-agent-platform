# ruff: noqa: F401,F811 -- Shared isolated PostgreSQL fixture.
"""Optional acceptance errors preserve original result reads, not grant failures."""

from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.prepared_delivery_acceptance import migrate
from agent_console.workbench_prepared_execution import PreparedExecutionOwner
from psycopg.rows import dict_row
from test_plan_suggestion_v2 import repository
from test_prepared_delivery_acceptance import Authority, delivered
from test_prepared_result_review import setup_case


def test_original_result_projection_survives_missing_acceptance_tables(repository):
    p, principal = setup_case(repository)
    with repository.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        delivered(c, p, principal)
        authority = Authority()
        call = SimpleNamespace(connection=c, authority=authority)
        app = SimpleNamespace(principal=principal, validate=lambda _: None)
        original = PreparedExecutionOwner.read(call, app, p)
        assert "deliveryAcceptance" not in original
        unavailable = PreparedExecutionOwner.read(
            call, app, p, delivery_acceptance_enabled=True
        )
        assert unavailable.pop("deliveryAcceptance") == {"status": "UNAVAILABLE"}
        assert unavailable == original
        migrate(c)
        for table in ("packages", "events", "heads"):
            with c.transaction(force_rollback=True):
                c.execute(
                    "ALTER TABLE prepared_delivery." + table + " RENAME TO missing"
                )
                value = PreparedExecutionOwner.read(
                    call, app, p, delivery_acceptance_enabled=True
                )
                assert value.pop("deliveryAcceptance") == {"status": "UNAVAILABLE"}
                assert value == original
                assert c.execute("SELECT 1 n").fetchone()["n"] == 1
        authority.denied = ("EVIDENCE", "READ_REFERENCE")
        with pytest.raises(AuthorityError):
            PreparedExecutionOwner.read(call, app, p, delivery_acceptance_enabled=True)
