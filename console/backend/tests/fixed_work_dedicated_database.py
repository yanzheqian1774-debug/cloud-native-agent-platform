"""Opt-in exact disposable database; never CREATE/DROP DATABASE or terminate peers.

Only for this isolated fixed-work suite while another suite owns the server's
postgres database. Production modules never import this helper.
"""

import os

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

NAME = "fixed_work_completion_20261114"


def selected(url):
    if os.environ.get("FIXED_WORK_DEDICATED_DATABASE") != NAME:
        return None
    values = conninfo_to_dict(url)
    assert values.get("host") == "127.0.0.1"
    assert values.get("port") == "53428"
    assert values.get("dbname") == NAME
    assert values.get("user") == "postgres"
    return NAME


def checked(url):
    assert selected(url) == NAME
    connection = psycopg.connect(url, autocommit=True, connect_timeout=3)
    try:
        assert connection.execute("SELECT current_database()").fetchone()[0] == NAME
        connection.execute("SET lock_timeout='2s'")
        connection.execute("SET statement_timeout='5s'")
    except BaseException:
        connection.close()
        raise
    return connection


def require_empty(url):
    with checked(url) as c:
        assert not c.execute(
            "SELECT 1 FROM pg_namespace WHERE nspname <> 'public' "
            "AND nspname <> 'information_schema' AND nspname NOT LIKE 'pg_%'"
        ).fetchone(), "dedicated database must be empty before fixture setup"
        assert not c.execute(
            "SELECT 1 FROM pg_tables WHERE schemaname='public'"
        ).fetchone()


def clean(url):
    with checked(url) as c:
        # Fail closed if the fixture leaked a peer. Never terminate any process.
        assert not c.execute(
            "SELECT 1 FROM pg_stat_activity WHERE datname=current_database() "
            "AND pid<>pg_backend_pid()"
        ).fetchone(), "dedicated fixture connections must close before cleanup"
        rows = c.execute(
            "SELECT nspname FROM pg_namespace WHERE nspname <> 'information_schema' "
            "AND nspname NOT LIKE 'pg_%' ORDER BY nspname"
        ).fetchall()
        for (name,) in rows:
            c.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(name)))
        c.execute("CREATE SCHEMA public")
    require_empty(url)
