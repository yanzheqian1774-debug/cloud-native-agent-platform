# ruff: noqa: E501 -- Scoped same-transaction SQL.
"""Internal checkpoint storage, called only after the owner locks and authorizes.

This class neither opens/commits a transaction nor dispatches an effect. It is not
an endpoint or an authorization substitute. The composition owner must hold the
exact command, Skill projection and prepared progress locks, in that order.
"""

import hashlib
import json
from pathlib import Path

from psycopg.types.json import Jsonb

from .authority_contracts import AuthorityError
from .native_wait_types import (
    ClaimObservation,
    ContinuationClaim,
    SkillJobWaiting,
    WaitCheckpoint,
)
from .resource_use_domain import canonical_digest


class NativeWaitStore:
    def __init__(self, connection, identity):
        self.connection = connection
        self.identity = identity
        self.key = identity.skill_key

    @staticmethod
    def migrate(connection):
        path = Path(__file__).parents[2] / "migrations/0068_native_human_wait.sql"
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        expected = {"checksum": checksum, "adapter": "native-human-wait.v1"}
        connection.execute("SELECT pg_advisory_xact_lock(3260068)")
        prior = connection.execute(
            "SELECT checksum,adapter FROM skill_invocation.schema_migrations WHERE version=68"
        ).fetchone()
        if prior:
            if prior != expected:
                raise AuthorityError("NATIVE_WAIT_SCHEMA_MISMATCH")
            return
        connection.execute(path.read_text())
        connection.execute(
            "INSERT INTO skill_invocation.schema_migrations(version,checksum,adapter) VALUES(68,%s,%s)",
            (checksum, expected["adapter"]),
        )

    def head(self):
        return self.connection.execute(
            "SELECT checkpoint_digest,version,state FROM skill_invocation.native_wait_heads "
            "WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s FOR UPDATE",
            self.key,
        ).fetchone()

    def checkpoint(self, commitment):
        row = self.connection.execute(
            "SELECT record FROM skill_invocation.native_wait_checkpoints WHERE "
            "namespace=%s AND security_domain=%s AND skill_invocation_id=%s AND checkpoint_digest=%s",
            (*self.key, commitment),
        ).fetchone()
        if not row:
            raise AuthorityError("NATIVE_WAIT_NOT_FOUND")
        value = WaitCheckpoint.model_validate_json(json.dumps(row["record"]))
        if value.digest != commitment or value.identity != self.identity:
            raise AuthorityError("NATIVE_WAIT_BINDING_CHANGED")
        return value

    def register(self, checkpoint, question, input_request_digest):
        """Question, original INPUT claim and checkpoint share the caller transaction."""
        if (
            checkpoint.identity != self.identity
            or input_request_digest != checkpoint.input_request_digest
        ):
            raise AuthorityError("NATIVE_WAIT_BINDING_CHANGED")
        head = self.head()
        if head and head["checkpoint_digest"] == checkpoint.digest:
            if self.checkpoint(checkpoint.digest) != checkpoint:
                raise AuthorityError("NATIVE_WAIT_BINDING_CHANGED")
            return SkillJobWaiting(
                identity=self.identity, checkpoint_digest=checkpoint.digest
            )
        if head and head["state"] != "COMPLETED":
            raise AuthorityError("NATIVE_WAIT_ALREADY_ACTIVE")
        if (
            head
            and self.checkpoint(head["checkpoint_digest"]).ordinal >= checkpoint.ordinal
        ):
            raise AuthorityError("NATIVE_WAIT_ORDINAL_CONFLICT")
        self.connection.execute(
            "INSERT INTO skill_invocation.native_wait_checkpoints "
            "(namespace,security_domain,skill_invocation_id,checkpoint_digest,ordinal,command_id,record,created_at,human_expires_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *self.key,
                checkpoint.digest,
                checkpoint.ordinal,
                self.identity.command_id,
                Jsonb(checkpoint.model_dump(mode="json")),
                checkpoint.created_at,
                checkpoint.human_expires_at,
            ),
        )
        # Deliberately no ON CONFLICT: an uncheckpointed prior INPUT/question is
        # ambiguity, not permission to adopt or overwrite an earlier call.
        self.connection.execute(
            "INSERT INTO skill_invocation.native_loop_records "
            "(namespace,security_domain,skill_invocation_id,record_key,request_digest) VALUES(%s,%s,%s,%s,%s)",
            (*self.key, checkpoint.question_key, checkpoint.input_request_digest),
        )
        self.connection.execute(
            "INSERT INTO skill_invocation.native_loop_records "
            "(namespace,security_domain,skill_invocation_id,record_key,request_digest,result,completed_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,clock_timestamp())",
            (
                *self.key,
                checkpoint.question_key + ":question",
                checkpoint.question_digest,
                Jsonb(question),
            ),
        )
        version = 1 if head is None else head["version"] + 1
        self.connection.execute(
            "INSERT INTO skill_invocation.native_wait_heads "
            "(namespace,security_domain,skill_invocation_id,checkpoint_digest,version,state) "
            "VALUES(%s,%s,%s,%s,%s,'QUIESCING') ON CONFLICT(namespace,security_domain,skill_invocation_id) "
            "DO UPDATE SET checkpoint_digest=excluded.checkpoint_digest,version=excluded.version,state=excluded.state",
            (*self.key, checkpoint.digest, version),
        )
        self._observe(
            checkpoint.digest,
            version,
            "REGISTERED",
            {"checkpointDigest": checkpoint.digest},
        )
        return SkillJobWaiting(
            identity=self.identity, checkpoint_digest=checkpoint.digest
        )

    def _observe(self, commitment, version, kind, record):
        self.connection.execute(
            "INSERT INTO skill_invocation.native_wait_observations "
            "(namespace,security_domain,skill_invocation_id,checkpoint_digest,version,kind,record_digest,record) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *self.key,
                commitment,
                version,
                kind,
                canonical_digest(record),
                Jsonb(record),
            ),
        )

    def transition(self, head, state, kind, record):
        next_version = head["version"] + 1
        changed = self.connection.execute(
            "UPDATE skill_invocation.native_wait_heads SET state=%s,version=%s WHERE namespace=%s "
            "AND security_domain=%s AND skill_invocation_id=%s AND checkpoint_digest=%s "
            "AND version=%s AND state=%s RETURNING version",
            (
                state,
                next_version,
                *self.key,
                head["checkpoint_digest"],
                head["version"],
                head["state"],
            ),
        ).fetchone()
        if not changed:
            raise AuthorityError("NATIVE_WAIT_VERSION_CONFLICT")
        self._observe(head["checkpoint_digest"], next_version, kind, record)

    def observation(self, commitment, kind):
        rows = self.connection.execute(
            "SELECT record,record_digest FROM skill_invocation.native_wait_observations "
            "WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s "
            "AND checkpoint_digest=%s AND kind=%s ORDER BY version",
            (*self.key, commitment, kind),
        ).fetchall()
        if len(rows) > 1 or any(
            canonical_digest(r["record"]) != r["record_digest"] for r in rows
        ):
            raise AuthorityError("NATIVE_WAIT_OBSERVATION_CONFLICT")
        return rows[0]["record"] if rows else None

    def claim(self, head, claim):
        """Duplicate returns never confer advance permission, including same worker."""
        row = self.connection.execute(
            "SELECT record,claim_digest FROM skill_invocation.native_wait_continuations "
            "WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s AND checkpoint_digest=%s",
            (*self.key, head["checkpoint_digest"]),
        ).fetchone()
        if row:
            if canonical_digest(row["record"]) != row["claim_digest"]:
                raise AuthorityError("NATIVE_WAIT_CLAIM_CHANGED")
            return ClaimObservation(
                newly_claimed=False,
                claim=ContinuationClaim.model_validate(row["record"]),
            )
        if (
            claim.checkpoint_digest != head["checkpoint_digest"]
            or head["state"] != "ANSWER_SAVED"
        ):
            raise AuthorityError("NATIVE_WAIT_NOT_RESUMABLE")
        record = claim.model_dump(mode="json")
        self.connection.execute(
            "INSERT INTO skill_invocation.native_wait_continuations "
            "(namespace,security_domain,skill_invocation_id,checkpoint_digest,claim_digest,record) VALUES(%s,%s,%s,%s,%s,%s)",
            (
                *self.key,
                claim.checkpoint_digest,
                canonical_digest(record),
                Jsonb(record),
            ),
        )
        self.transition(head, "CONTINUATION_CLAIMED", "CONTINUATION_CLAIMED", record)
        return ClaimObservation(newly_claimed=True, claim=claim)

    def require_fence(self, claim, *, worker_id, startup_record_digest):
        """Caller must hold this transaction until its effect-journal claim commits."""
        head = self.head()
        row = self.connection.execute(
            "SELECT record,claim_digest FROM skill_invocation.native_wait_continuations "
            "WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s AND checkpoint_digest=%s",
            (*self.key, claim.checkpoint_digest),
        ).fetchone()
        expected = claim.model_dump(mode="json")
        if (
            not head
            or head["checkpoint_digest"] != claim.checkpoint_digest
            or head["state"] not in {"CONTINUATION_CLAIMED", "ADVANCING"}
            or row != {"record": expected, "claim_digest": canonical_digest(expected)}
            or worker_id != claim.worker_id
            or startup_record_digest != claim.startup_record_digest
        ):
            raise AuthorityError("NATIVE_WAIT_CONTINUATION_FENCED")
        return head
