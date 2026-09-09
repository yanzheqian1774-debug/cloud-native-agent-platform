# ruff: noqa: E501
"""Focused PostgreSQL structure checks for initialized Console domains."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class Column:
    name: str
    data_type: str


@dataclass(frozen=True, slots=True)
class Constraint:
    kind: Literal["p", "u", "f"]
    columns: tuple[str, ...]
    references: str | None = None
    referenced_columns: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Table:
    relation: str
    columns: tuple[Column, ...]
    constraints: tuple[Constraint, ...] = ()
    triggers: tuple[str, ...] = ()


def _columns(connection: Any, relation: str) -> dict[str, tuple[str, bool]]:
    rows = connection.execute(
        """SELECT attribute.attname AS name,
                  pg_catalog.format_type(attribute.atttypid, attribute.atttypmod) AS data_type,
                  attribute.attnotnull AS not_null
           FROM pg_catalog.pg_attribute AS attribute
           WHERE attribute.attrelid = to_regclass(%s)
             AND attribute.attnum > 0
             AND NOT attribute.attisdropped""",
        (relation,),
    ).fetchall()
    return {row["name"]: (row["data_type"], row["not_null"]) for row in rows}


def _constraints(connection: Any, relation: str) -> set[tuple[Any, ...]]:
    rows = connection.execute(
        """SELECT con.contype AS kind,
                  ARRAY(
                    SELECT attribute.attname
                    FROM unnest(con.conkey) WITH ORDINALITY AS key(attnum, ordinal)
                    JOIN pg_catalog.pg_attribute AS attribute
                      ON attribute.attrelid = con.conrelid
                     AND attribute.attnum = key.attnum
                    ORDER BY key.ordinal
                  ) AS columns,
                  CASE WHEN con.contype = 'f'
                    THEN con.confrelid::regclass::text ELSE NULL END AS references,
                  CASE WHEN con.contype = 'f' THEN ARRAY(
                    SELECT attribute.attname
                    FROM unnest(con.confkey) WITH ORDINALITY AS key(attnum, ordinal)
                    JOIN pg_catalog.pg_attribute AS attribute
                      ON attribute.attrelid = con.confrelid
                     AND attribute.attnum = key.attnum
                    ORDER BY key.ordinal
                  ) ELSE ARRAY[]::name[] END AS referenced_columns
           FROM pg_catalog.pg_constraint AS con
           WHERE con.conrelid = to_regclass(%s)
             AND con.contype IN ('p', 'u', 'f')""",
        (relation,),
    ).fetchall()
    return {
        (
            row["kind"],
            tuple(row["columns"]),
            row["references"],
            tuple(row["referenced_columns"]),
        )
        for row in rows
    }


def schema_is_compatible(connection: Any, tables: tuple[Table, ...]) -> bool:
    """Check required relations, non-null columns/types, and identity constraints."""
    for table in tables:
        relation = connection.execute(
            """SELECT class.relkind AS kind
               FROM pg_catalog.pg_class AS class
               WHERE class.oid = to_regclass(%s)""",
            (table.relation,),
        ).fetchone()
        if relation is None or relation["kind"] not in {"r", "p"}:
            return False
        actual_columns = _columns(connection, table.relation)
        if any(
            actual_columns.get(column.name) != (column.data_type, True)
            for column in table.columns
        ):
            return False
        actual_constraints = _constraints(connection, table.relation)
        if any(
            (
                constraint.kind,
                constraint.columns,
                constraint.references,
                constraint.referenced_columns,
            )
            not in actual_constraints
            for constraint in table.constraints
        ):
            return False
        if table.triggers:
            actual_triggers = {
                row["name"]
                for row in connection.execute(
                    """SELECT trigger.tgname AS name
                       FROM pg_catalog.pg_trigger AS trigger
                       WHERE trigger.tgrelid = to_regclass(%s)
                         AND NOT trigger.tgisinternal""",
                    (table.relation,),
                ).fetchall()
            }
            if not set(table.triggers).issubset(actual_triggers):
                return False
    return True


def columns(*items: tuple[str, str]) -> tuple[Column, ...]:
    return tuple(Column(*item) for item in items)


def primary(*names: str) -> Constraint:
    return Constraint("p", names)


def unique(*names: str) -> Constraint:
    return Constraint("u", names)


def foreign(
    names: tuple[str, ...], relation: str, referenced_names: tuple[str, ...]
) -> Constraint:
    return Constraint("f", names, relation, referenced_names)


LEDGER_COLUMNS = columns(
    ("version", "integer"), ("checksum", "text"), ("adapter", "text")
)
