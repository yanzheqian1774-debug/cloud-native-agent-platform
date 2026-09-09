"""Unit checks for batched PostgreSQL structure-result mapping."""

from unittest.mock import Mock

import pytest
from agent_console.postgres_schema_compatibility import (
    Table,
    columns,
    foreign,
    primary,
    schema_is_compatible,
    unique,
)


def _connection(rows: list[dict[str, object]]) -> Mock:
    connection = Mock()
    connection.execute.return_value.fetchall.return_value = rows
    return connection


def test_owner_structure_is_loaded_with_one_catalog_query() -> None:
    connection = _connection(
        [
            {
                "relation": "owner.parents",
                "kind": "r",
                "columns": {"id": ["uuid", True]},
                "constraints": [["p", ["id"], None, []]],
                "triggers": ["parents_audit"],
            },
            {
                "relation": "owner.children",
                "kind": "p",
                "columns": {
                    "id": ["uuid", True],
                    "parent_id": ["uuid", True],
                },
                "constraints": [
                    ["u", ["id"], None, []],
                    ["f", ["parent_id"], "owner.parents", ["id"]],
                ],
                "triggers": [],
            },
        ]
    )
    tables = (
        Table(
            "owner.parents",
            columns(("id", "uuid")),
            (primary("id"),),
            ("parents_audit",),
        ),
        Table(
            "owner.children",
            columns(("id", "uuid"), ("parent_id", "uuid")),
            (
                unique("id"),
                foreign(("parent_id",), "owner.parents", ("id",)),
            ),
        ),
    )

    assert schema_is_compatible(connection, tables)
    connection.execute.assert_called_once()
    assert connection.execute.call_args.args[1] == (
        ["owner.parents", "owner.children"],
    )


@pytest.mark.parametrize("missing", ("relation", "column", "constraint", "trigger"))
def test_catalog_result_from_one_relation_cannot_prove_another(
    missing: str,
) -> None:
    complete = {
        "kind": "r",
        "columns": {"id": ["uuid", True]},
        "constraints": [["p", ["id"], None, []]],
        "triggers": ["audit"],
    }
    incomplete = dict(complete)
    if missing == "relation":
        incomplete["kind"] = None
    elif missing == "column":
        incomplete["columns"] = {}
    elif missing == "constraint":
        incomplete["constraints"] = []
    else:
        incomplete["triggers"] = []
    connection = _connection(
        [
            {"relation": "owner.first", **complete},
            {"relation": "owner.second", **incomplete},
        ]
    )
    required = (
        Table(
            "owner.first",
            columns(("id", "uuid")),
            (primary("id"),),
            ("audit",),
        ),
        Table(
            "owner.second",
            columns(("id", "uuid")),
            (primary("id"),),
            ("audit",),
        ),
    )

    assert not schema_is_compatible(connection, required)
    connection.execute.assert_called_once()
