"""The optional lookup index changes access paths, not grant ownership or scope."""

from pathlib import Path

from test_workbench_authorization_postgres import repository  # noqa: F401

INDEX = (
    Path(__file__).resolve().parents[3]
    / "scripts/maintenance/authority_exact_grant_lookup.sql"
)


def test_exact_lookup_index_is_valid_nonunique_and_scoped(repository):  # noqa: F811
    with repository.pool.connection() as connection:
        connection.autocommit = True
        try:
            before = connection.execute(
                "SELECT count(*) AS n FROM authorization_admin.grants"
            ).fetchone()["n"]
            connection.execute(INDEX.read_text())
            row = connection.execute(
                "SELECT i.indisvalid,i.indisready,i.indisunique,"
                "pg_get_indexdef(i.indexrelid) AS definition "
                "FROM pg_index i WHERE i.indexrelid="
                "'authorization_admin.grants_exact_lookup_idx'::regclass"
            ).fetchone()
            assert row["indisvalid"] and row["indisready"]
            assert not row["indisunique"]
            assert row["definition"].endswith(
                "USING btree (subject_principal_id, tenant_id, security_domain, "
                "owner, action, exact_resource)"
            )
            assert (
                connection.execute(
                    "SELECT count(*) AS n FROM authorization_admin.grants"
                ).fetchone()["n"]
                == before
            )
        finally:
            connection.autocommit = False
