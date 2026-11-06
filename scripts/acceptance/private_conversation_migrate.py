"""Additive migration; disable the feature for rollback, retaining all records."""

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
    source = (
        Path(__file__).resolve().parents[2]
        / "console/backend/migrations/0046_private_conversation.sql"
    )
    checksum = hashlib.sha256(source.read_bytes()).hexdigest()
    with psycopg.connect(os.environ["CONVERSATION_DATABASE_URL"]) as c:
        if not args.apply:
            c.execute("SET TRANSACTION READ ONLY")
        else:
            c.execute(
                "SELECT pg_advisory_xact_lock("
                "hashtextextended('private-conversation-v1',0))"
            )
            c.execute("CREATE SCHEMA IF NOT EXISTS private_conversation")
            c.execute(
                "CREATE TABLE IF NOT EXISTS private_conversation.schema_migrations "
                "(version integer PRIMARY KEY, checksum text NOT NULL, "
                "applied_at timestamptz NOT NULL DEFAULT now())"
            )
        row = c.execute(
            "SELECT checksum FROM private_conversation.schema_migrations "
            "WHERE version=1"
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
                "INSERT INTO private_conversation.schema_migrations(version,checksum) "
                "VALUES(1,%s)",
                (checksum,),
            )
    print(
        json.dumps(
            {
                "migration": 46,
                "schemaVersion": 1,
                "checksum": checksum,
                "appliedOrVerified": True,
                "rollback": "Disable PRIVATE_CONVERSATIONS_ENABLED; retain all records",
            }
        )
    )


if __name__ == "__main__":
    main()
