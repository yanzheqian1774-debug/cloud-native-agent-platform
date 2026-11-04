"""Business ontology SQL adapter; callers provide an authorized owner transaction."""

import hashlib
import json
from pathlib import Path

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .ontology_domain import OntologyError, content_digest
from .resource_use_domain import canonical_digest

MIGRATION = Path(__file__).parents[2] / "migrations/0044_business_ontology.sql"


def migrate(connection):
    connection.execute("SELECT pg_advisory_xact_lock(440044)")
    present = connection.execute(
        "SELECT to_regclass('business_ontology.schema_migrations')"
    ).fetchone()
    # The adapter works with both tuple and dictionary row factories.
    exists = next(iter(present.values())) if isinstance(present, dict) else present[0]
    digest = hashlib.sha256(MIGRATION.read_bytes()).hexdigest()
    if not exists:
        connection.execute(MIGRATION.read_text())
        connection.execute(
            "INSERT INTO business_ontology.schema_migrations VALUES (44,%s)",
            (digest,),
        )
    else:
        connection.row_factory = dict_row
        rows = connection.execute(
            "SELECT version,checksum FROM business_ontology.schema_migrations"
            " ORDER BY version"
        ).fetchall()
        if rows != [{"version": 44, "checksum": digest}]:
            raise OntologyError("ONTOLOGY_SCHEMA_INCOMPATIBLE")


class PostgresOntologyRepository:
    def __init__(self, connection):
        self.c = connection
        self.c.row_factory = dict_row

    def read(self, scope, identity, revision):
        row = self.c.execute(
            "SELECT r.*,d.version,d.head_revision FROM business_ontology.revisions r "
            "JOIN business_ontology.definitions d USING(namespace,security_do"
            "main,ontology_id) "
            "WHERE r.namespace=%s AND r.security_domain=%s AND r.ontology_id="
            "%s AND r.revision_id=%s",
            (*scope, identity, revision),
        ).fetchone()
        if row is None:
            raise OntologyError("ONTOLOGY_NOT_FOUND")
        if (
            content_digest(
                scope, identity, revision, row["predecessor"], row["content"]
            )
            != row["digest"]
        ):
            raise OntologyError("ONTOLOGY_CONTENT_CORRUPT")
        facts = self.c.execute(
            "SELECT action,actor,result,ordinal FROM business_ontology.lifecycle_facts "
            "WHERE namespace=%s AND security_domain=%s AND ontology_id=%s AND"
            " revision_id=%s ORDER BY ordinal",
            (*scope, identity, revision),
        ).fetchall()
        return {
            **row,
            "facts": facts,
            "state": facts[-1]["action"] if facts else "DRAFT",
        }

    def command(self, scope, actor, identity, action, command, *, evidence=None):
        c = self.c
        # Stable lock order across request and aggregate keys, no nested connections.
        for key in sorted(([*scope, actor, command.request_key], [*scope, identity])):
            c.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (json.dumps(key),),
            )
        cd = canonical_digest(
            {
                "identity": identity,
                "action": action,
                "command": command.model_dump(mode="json"),
            }
        )
        prior = c.execute(
            "SELECT command_digest,result FROM business_ontology.lifecycle_facts "
            "WHERE namespace=%s AND security_domain=%s AND actor=%s AND request_key=%s",
            (*scope, actor, command.request_key),
        ).fetchone()
        if prior:
            if prior["command_digest"] != cd:
                raise OntologyError("ONTOLOGY_REPLAY_CONFLICT")
            return prior["result"]
        head = c.execute(
            "SELECT * FROM business_ontology.definitions WHERE namespace=%s A"
            "ND security_domain=%s AND ontology_id=%s FOR UPDATE",
            (*scope, identity),
        ).fetchone()
        if (head["version"] if head else 0) != command.expected_version:
            raise OntologyError("ONTOLOGY_VERSION_CONFLICT")
        revision = command.revision_id
        if action in {"CREATE", "REVISE"}:
            if command.content is None or (action == "CREATE") != (head is None):
                raise OntologyError("ONTOLOGY_DRAFT_INVALID")
            predecessor = head["head_revision"] if head else None
            if c.execute(
                "SELECT 1 FROM business_ontology.revisions WHERE namespace=%s "
                "AND security_domain=%s AND ontology_id=%s AND revision_id=%s",
                (*scope, identity, revision),
            ).fetchone():
                raise OntologyError("ONTOLOGY_REVISION_EXISTS")
            content = command.content.model_dump(mode="json")
            digest = content_digest(scope, identity, revision, predecessor, content)
            c.execute(
                "INSERT INTO business_ontology.definitions VALUES (%s,%s,%s,1,%s) "
                "ON CONFLICT(namespace,security_domain,ontology_id) DO UPDATE"
                " SET version=business_ontology.definitions.version+1,head_re"
                "vision=EXCLUDED.head_revision",
                (*scope, identity, revision),
            )
            c.execute(
                "INSERT INTO business_ontology.revisions VALUES (%s,%s,%s,%s,"
                "%s,%s,%s,%s)",
                (
                    *scope,
                    identity,
                    revision,
                    digest,
                    actor,
                    predecessor,
                    Jsonb(content),
                ),
            )
            for kind, refs in (
                ("SOURCE", [m.source for m in command.content.mappings]),
                ("SKILL", [a.skill for a in command.content.actions]),
            ):
                for ref in refs:
                    c.execute(
                        "INSERT INTO business_ontology.dependency_refs VALUES"
                        " (%s,%s,%s,%s,%s,%s)",
                        (
                            *scope,
                            identity,
                            revision,
                            kind,
                            Jsonb(ref.model_dump(mode="json")),
                        ),
                    )
        else:
            if command.content is not None or head is None:
                raise OntologyError("ONTOLOGY_COMMAND_INVALID")
            record = self.read(scope, identity, revision)
            digest = record["digest"]
            if command.digest != digest:
                raise OntologyError("ONTOLOGY_DIGEST_MISMATCH")
            required = {
                "VALIDATE": {"CREATE", "REVISE"},
                "TEST": {"VALIDATE"},
                "REVIEW": {"TEST"},
                "PUBLISH": {"REVIEW"},
                "DEPRECATE": {"PUBLISH"},
            }
            if action not in required or record["state"] not in required[action]:
                raise OntologyError("ONTOLOGY_LIFECYCLE_INVALID")
            if action != "DEPRECATE" and head["head_revision"] != revision:
                raise OntologyError("ONTOLOGY_HEAD_CHANGED")
            if action == "REVIEW" and record["author"] == actor:
                raise OntologyError("ONTOLOGY_INDEPENDENT_REVIEW_REQUIRED")
            c.execute(
                "UPDATE business_ontology.definitions SET version=version+1 W"
                "HERE namespace=%s AND security_domain=%s AND ontology_id=%s",
                (*scope, identity),
            )
        version = command.expected_version + 1
        result = {
            "ontology_id": identity,
            "revision_id": revision,
            "digest": digest,
            "version": version,
            "state": action,
        }
        if evidence is not None:
            result["checks"] = evidence
        c.execute(
            "INSERT INTO business_ontology.lifecycle_facts(namespace,security"
            "_domain,ontology_id,revision_id,digest,action,actor,request_key,"
            "command_digest,result) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *scope,
                identity,
                revision,
                digest,
                action,
                actor,
                command.request_key,
                cd,
                Jsonb(result),
            ),
        )
        return result
