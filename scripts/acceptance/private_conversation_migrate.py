"""Additive migrations; feature-off rollback always retains private records."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import psycopg


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    folder = Path(__file__).resolve().parents[2] / "console/backend/migrations"
    results = []
    with psycopg.connect(os.environ["CONVERSATION_DATABASE_URL"]) as c:
        if not args.apply:
            c.execute("SET TRANSACTION READ ONLY")
        else:
            c.execute(
                "SELECT "
                "pg_advisory_xact_lock(hashtextextended('private-conversation-v1',0))"
            )
            c.execute("CREATE SCHEMA IF NOT EXISTS private_conversation")
            c.execute(
                "CREATE TABLE IF NOT EXISTS private_conversation.schema_migrations "
                "(version integer PRIMARY KEY, checksum text NOT NULL, "
                "applied_at timestamptz NOT NULL DEFAULT now())"
            )
        for version, name in [
            (1, "0046_private_conversation.sql"),
            (2, "0047_conversation_action_facts.sql"),
        ]:
            source = folder / name
            checksum = hashlib.sha256(source.read_bytes()).hexdigest()
            row = c.execute(
                "SELECT checksum FROM private_conversation.schema_migrations "
                "WHERE version=%s",
                (version,),
            ).fetchone()
            if row and row[0] != checksum:
                raise RuntimeError(
                    "Migration checksum mismatch; retained records not modified"
                )
            if not row:
                if not args.apply:
                    raise RuntimeError("Migration not applied")
                c.execute(source.read_text())
                c.execute(
                    "INSERT INTO "
                    "private_conversation.schema_migrations(version,checksum) "
                    "VALUES(%s,%s)",
                    (version, checksum),
                )
            results.append(
                {
                    "migration": 45 + version,
                    "schemaVersion": version,
                    "checksum": checksum,
                }
            )
    print(
        json.dumps(
            {
                "migrations": results,
                "appliedOrVerified": True,
                "rollback": "Disable PRIVATE_CONVERSATIONS_ENABLED; retain all records",
            }
        )
    )


if __name__ == "__main__":
    main()
