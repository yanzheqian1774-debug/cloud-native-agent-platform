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


def schema_is_compatible(connection: Any, tables: tuple[Table, ...]) -> bool:
    """Check required relations, non-null columns/types, and identity constraints."""
    rows = connection.execute(
        """WITH required(relation) AS (SELECT unnest(%s::text[]))
           SELECT required.relation,
                  class.relkind AS kind,
                  COALESCE((
                    SELECT jsonb_object_agg(
                      attribute.attname,
                      jsonb_build_array(
                        pg_catalog.format_type(attribute.atttypid, attribute.atttypmod),
                        attribute.attnotnull
                      )
                    )
                    FROM pg_catalog.pg_attribute AS attribute
                    WHERE attribute.attrelid = class.oid
                      AND attribute.attnum > 0
                      AND NOT attribute.attisdropped
                  ), '{}'::jsonb) AS columns,
                  COALESCE((
                    SELECT jsonb_agg(jsonb_build_array(
                      con.contype,
                      ARRAY(
                        SELECT attribute.attname
                        FROM unnest(con.conkey) WITH ORDINALITY AS key(attnum, ordinal)
                        JOIN pg_catalog.pg_attribute AS attribute
                          ON attribute.attrelid = con.conrelid
                         AND attribute.attnum = key.attnum
                        ORDER BY key.ordinal
                      ),
                      CASE WHEN con.contype = 'f'
                        THEN con.confrelid::regclass::text ELSE NULL END,
                      CASE WHEN con.contype = 'f' THEN ARRAY(
                        SELECT attribute.attname
                        FROM unnest(con.confkey) WITH ORDINALITY AS key(attnum, ordinal)
                        JOIN pg_catalog.pg_attribute AS attribute
                          ON attribute.attrelid = con.confrelid
                         AND attribute.attnum = key.attnum
                        ORDER BY key.ordinal
                      ) ELSE ARRAY[]::name[] END
                    ))
                    FROM pg_catalog.pg_constraint AS con
                    WHERE con.conrelid = class.oid
                      AND con.contype IN ('p', 'u', 'f')
                  ), '[]'::jsonb) AS constraints,
                  COALESCE((
                    SELECT jsonb_agg(trigger.tgname)
                    FROM pg_catalog.pg_trigger AS trigger
                    WHERE trigger.tgrelid = class.oid
                      AND NOT trigger.tgisinternal
                  ), '[]'::jsonb) AS triggers
           FROM required
           LEFT JOIN pg_catalog.pg_class AS class
             ON class.oid = to_regclass(required.relation)""",
        ([table.relation for table in tables],),
    ).fetchall()
    actual = {row["relation"]: row for row in rows}
    for table in tables:
        relation = actual[table.relation]
        if relation is None or relation["kind"] not in {"r", "p"}:
            return False
        if any(
            relation["columns"].get(column.name) != [column.data_type, True]
            for column in table.columns
        ):
            return False
        actual_constraints = {
            (kind, tuple(names), references, tuple(referenced_names))
            for kind, names, references, referenced_names in relation["constraints"]
        }
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
        if not set(table.triggers).issubset(relation["triggers"]):
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
