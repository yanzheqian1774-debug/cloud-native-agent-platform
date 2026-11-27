# ruff: noqa: E501 -- Exact scoped immutable owner records.
"""Same-transaction private storage. This port never grants or dispatches."""

import hashlib
from pathlib import Path

from psycopg.types.json import Jsonb

from .authority_contracts import AuthorityError
from .fixed_question_types import (
    DelegatedAnswerReceipt,
    QuestionIdentity,
    QuestionPresentation,
)


def require(value):
    if not value:
        raise AuthorityError("FIXED_QUESTION_RECORD_BINDING_INVALID")


class FixedQuestionStore:
    def __init__(self, c, scope):
        self.c, self.scope = c, tuple(scope)

    @staticmethod
    def compatible(c):
        path = (
            Path(__file__).parents[2] / "migrations/0078_fixed_question_delegation.sql"
        )
        present = c.execute(
            "SELECT to_regclass('fixed_question.schema_migrations') AS relation"
        ).fetchone()
        require(present["relation"] is not None)
        row = c.execute(
            "SELECT checksum,adapter FROM fixed_question.schema_migrations WHERE version=78"
        ).fetchone()
        require(
            row
            == {
                "checksum": hashlib.sha256(path.read_bytes()).hexdigest(),
                "adapter": "fixed-question-delegation.v1",
            }
        )

    @staticmethod
    def migrate(c):
        path = (
            Path(__file__).parents[2] / "migrations/0078_fixed_question_delegation.sql"
        )
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        expected = {"checksum": checksum, "adapter": "fixed-question-delegation.v1"}
        c.execute("SELECT pg_advisory_xact_lock(3260078)")
        exists = c.execute(
            "SELECT to_regclass('fixed_question.schema_migrations') AS relation"
        ).fetchone()
        if exists["relation"]:
            prior = c.execute(
                "SELECT checksum,adapter FROM fixed_question.schema_migrations WHERE version=78"
            ).fetchone()
            require(prior == expected)
            return
        c.execute(path.read_text())
        c.execute(
            "INSERT INTO fixed_question.schema_migrations(version,checksum,adapter) VALUES(78,%s,%s)",
            (checksum, expected["adapter"]),
        )

    def anchor(self, identity):
        require(isinstance(identity, QuestionIdentity))
        require(self.scope == (identity.tenantId, identity.securityDomain))
        old = self.question(identity.digest)
        if old:
            require(old == identity)
            return old
        self.c.execute(
            "INSERT INTO fixed_question.questions(tenant_id,security_domain,conversation_id,identity_digest,record) VALUES(%s,%s,%s,%s,%s)",
            (
                *self.scope,
                identity.conversationId,
                identity.digest,
                Jsonb(identity.model_dump(mode="json")),
            ),
        )
        return identity

    def question(self, commitment):
        row = self.c.execute(
            "SELECT * FROM fixed_question.questions WHERE tenant_id=%s AND security_domain=%s AND identity_digest=%s",
            (*self.scope, commitment),
        ).fetchone()
        if row is None:
            return None
        value = QuestionIdentity.model_validate(row["record"])
        require(
            (row["tenant_id"], row["security_domain"])
            == self.scope
            == (value.tenantId, value.securityDomain)
        )
        require(
            row["conversation_id"] == value.conversationId
            and row["identity_digest"] == commitment == value.digest
        )
        return value

    def presentation(self, presentation_id):
        row = self.c.execute(
            "SELECT * FROM fixed_question.presentations WHERE tenant_id=%s AND security_domain=%s AND presentation_id=%s",
            (*self.scope, presentation_id),
        ).fetchone()
        return self._presentation(row) if row else None

    def presentation_command(self, conversation, actor, command):
        row = self.c.execute(
            "SELECT * FROM fixed_question.presentations WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s AND actor_id=%s AND command_id=%s",
            (*self.scope, conversation, actor, command),
        ).fetchone()
        return self._presentation(row) if row else None

    def _presentation(self, row):
        p = QuestionPresentation.model_validate(row["record"])
        i = p.identity
        require(
            (row["tenant_id"], row["security_domain"])
            == self.scope
            == (i.tenantId, i.securityDomain)
        )
        require(
            (
                row["conversation_id"],
                row["presentation_id"],
                row["identity_digest"],
                row["actor_id"],
                row["command_id"],
                row["request_digest"],
                row["record_digest"],
            )
            == (
                i.conversationId,
                p.presentationId,
                i.digest,
                p.actorId,
                p.commandId,
                p.requestDigest,
                p.digest,
            )
        )
        require(self.question(i.digest) == i)
        return p

    def append_presentation(self, value):
        require(isinstance(value, QuestionPresentation))
        i = value.identity
        require(self.question(i.digest) == i)
        old = self.presentation_command(
            i.conversationId, value.actorId, value.commandId
        )
        if old:
            require(old == value)
            return old
        self.c.execute(
            "INSERT INTO fixed_question.presentations(tenant_id,security_domain,conversation_id,presentation_id,identity_digest,actor_id,command_id,request_digest,record,record_digest) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *self.scope,
                i.conversationId,
                value.presentationId,
                i.digest,
                value.actorId,
                value.commandId,
                value.requestDigest,
                Jsonb(value.model_dump(mode="json")),
                value.digest,
            ),
        )
        return value

    def answer(self, presentation_id):
        row = self.c.execute(
            "SELECT * FROM fixed_question.answers WHERE tenant_id=%s AND security_domain=%s AND presentation_id=%s",
            (*self.scope, presentation_id),
        ).fetchone()
        if row is None:
            return None
        a = DelegatedAnswerReceipt.model_validate(row["record"])
        p = self.presentation(presentation_id)
        require(p is not None)
        require((row["tenant_id"], row["security_domain"]) == self.scope)
        require(
            (
                row["conversation_id"],
                row["presentation_id"],
                row["identity_digest"],
                row["actor_id"],
                row["command_id"],
                row["request_digest"],
                row["message_id"],
                row["record_digest"],
            )
            == (
                p.identity.conversationId,
                a.presentationId,
                a.questionIdentityDigest,
                a.actorId,
                a.commandId,
                a.requestDigest,
                a.inputMessageId,
                a.digest,
            )
        )
        require(
            a.presentationDigest == p.digest
            and a.questionIdentityDigest == p.identity.digest
            and a.actorId == p.actorId
            and a.executionSubject == p.identity.executionSubject
        )
        require(
            a.generation == p.identity.generation
            and a.recoveryEpoch == p.identity.recoveryEpoch
        )
        require(p.createdAt <= a.acceptedAt <= p.expiresAt)
        return a

    def append_answer(self, value):
        require(isinstance(value, DelegatedAnswerReceipt))
        p = self.presentation(value.presentationId)
        require(p is not None and value.presentationDigest == p.digest)
        require(
            value.questionIdentityDigest == p.identity.digest
            and value.actorId == p.actorId
            and value.executionSubject == p.identity.executionSubject
        )
        require(
            value.generation == p.identity.generation
            and value.recoveryEpoch == p.identity.recoveryEpoch
        )
        require(p.createdAt <= value.acceptedAt <= p.expiresAt)
        old = self.answer(value.presentationId)
        if old:
            require(old == value)
            return old
        self.c.execute(
            "INSERT INTO fixed_question.answers(tenant_id,security_domain,conversation_id,presentation_id,identity_digest,actor_id,command_id,request_digest,message_id,record,record_digest) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *self.scope,
                p.identity.conversationId,
                value.presentationId,
                value.questionIdentityDigest,
                value.actorId,
                value.commandId,
                value.requestDigest,
                value.inputMessageId,
                Jsonb(value.model_dump(mode="json")),
                value.digest,
            ),
        )
        return value
