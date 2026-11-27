# ruff: noqa: F401,F811,E501 -- Original isolated fixtures and exact SQL.
"""Immutable 0078 receipt storage, not product authorization acceptance."""

from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.fixed_question_store import FixedQuestionStore
from agent_console.fixed_question_types import DelegatedAnswerReceipt
from test_native_wait_delegated_answer import presentation
from test_native_wait_owner import repository, waiting


@pytest.mark.parametrize("waiting", ["service"], indirect=True)
def test_immutable_question_receipts_and_full_persistent_column_checks(waiting):
    e = waiting
    p = presentation(e)
    i = p.identity
    scope = i.tenantId, i.securityDomain
    with e.repo.pool.connection() as c, c.transaction():
        c.execute(
            (
                Path(__file__).parents[1] / "migrations/0046_private_conversation.sql"
            ).read_text()
        )
        c.execute(
            "INSERT INTO private_conversation.conversations(tenant_id,security_domain,conversation_id,owner_id,title,request_key,request_digest) VALUES(%s,%s,%s,%s,'controlled question','setup',%s)",
            (*scope, i.conversationId, p.actorId, "1" * 64),
        )
        c.execute(
            "INSERT INTO private_conversation.messages(tenant_id,security_domain,conversation_id,message_id,sequence,author_id,content,disposition,request_key,request_digest) VALUES(%s,%s,%s,'answer-message',1,%s,'production','ACCEPTED','setup-message',%s)",
            (*scope, i.conversationId, p.actorId, "2" * 64),
        )
        FixedQuestionStore.migrate(c)
        FixedQuestionStore.migrate(c)
        store = FixedQuestionStore(c, scope)
        assert store.anchor(i) == i
        assert store.append_presentation(p) == p
        assert store.append_presentation(p) == p
        a = DelegatedAnswerReceipt(
            presentationId=p.presentationId,
            presentationDigest=p.digest,
            questionIdentityDigest=i.digest,
            actorId=p.actorId,
            executionSubject=i.executionSubject,
            commandId="answer-command",
            requestDigest="3" * 64,
            inputMessageId="answer-message",
            interpretationInvocationId="controlled-c1",
            interpretationDigest="4" * 64,
            answerDigest="5" * 64,
            generation=i.generation,
            recoveryEpoch=i.recoveryEpoch,
            acceptedAt=datetime.now(UTC),
        )
        assert store.append_answer(a) == a
        assert store.append_answer(a) == a
        assert store.answer(p.presentationId) == a
        for table in ("questions", "presentations", "answers"):
            with pytest.raises(psycopg.Error, match="immutable"), c.transaction():
                c.execute("DELETE FROM fixed_question." + table)
        assert (
            c.execute("SELECT count(*) n FROM fixed_question.answers").fetchone()["n"]
            == 1
        )

        class CorruptRead:
            def __init__(self, table, column):
                self.table, self.column = table, column

            def execute(self, query, params=()):
                cursor = c.execute(query, params)
                if "SELECT * FROM fixed_question." + self.table + " " not in query:
                    return cursor
                row = cursor.fetchone()
                assert row is not None
                changed = {**row, self.column: "tampered"}
                return type("ReadPort", (), {"fetchone": lambda _: changed})()

        for table, fields in {
            "questions": (
                "tenant_id",
                "security_domain",
                "conversation_id",
                "identity_digest",
            ),
            "presentations": (
                "tenant_id",
                "security_domain",
                "conversation_id",
                "presentation_id",
                "identity_digest",
                "actor_id",
                "command_id",
                "request_digest",
                "record_digest",
            ),
            "answers": (
                "tenant_id",
                "security_domain",
                "conversation_id",
                "presentation_id",
                "identity_digest",
                "actor_id",
                "command_id",
                "request_digest",
                "message_id",
                "record_digest",
            ),
        }.items():
            for field in fields:
                with pytest.raises(AuthorityError, match="RECORD_BINDING_INVALID"):
                    FixedQuestionStore(CorruptRead(table, field), scope).answer(
                        p.presentationId
                    )
        assert store.answer(p.presentationId) == a
