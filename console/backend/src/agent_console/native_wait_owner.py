# ruff: noqa: E501 -- Exact same-transaction owner SQL.
"""Private durable-wait owner; callers supply the original authorized transaction.

No routes or runtime are enabled by importing this module. Authorization is a
mandatory composition port, invoked inside the existing authorization barrier.
It must recheck the actual command's current START/USE/source/budget policy.
"""

from datetime import UTC, datetime
from secrets import token_hex

from agent_runtime.native_loop import digest
from psycopg.types.json import Jsonb

from .authority_contracts import AuthorityError
from .execution_preparation_postgres import PreparedExecutionStore
from .native_wait_store import NativeWaitStore
from .native_wait_types import ContinuationClaim
from .resource_use_domain import canonical_digest


class NativeWaitOwner:
    def __init__(
        self,
        authorize,
        skill_repository,
        *,
        clock=lambda: datetime.now(UTC),
        authorize_delegated_answer=None,
    ):
        if not callable(authorize):
            raise TypeError("NATIVE_WAIT_AUTHORITY_PORT_REQUIRED")
        self.authorize = authorize
        self.skill_repository = skill_repository
        self.clock = clock
        if authorize_delegated_answer is not None and not callable(
            authorize_delegated_answer
        ):
            raise TypeError("NATIVE_WAIT_DELEGATED_AUTHORITY_PORT_REQUIRED")
        self.authorize_delegated_answer = authorize_delegated_answer

    def _lock(self, c, cp, operation):
        # Caller holds generation barrier; callback uses THIS connection. It may
        # not grant authority or accept a browser-supplied subject/boolean.
        self.authorize(c, cp, operation)
        i = cp.identity
        if self.clock() >= cp.authority_expires_at:
            raise AuthorityError("NATIVE_WAIT_AUTHORITY_EXPIRED")
        command = c.execute(
            "SELECT state,attempt_id,principal_id,terminal_record FROM execution_authority.native_dispatch_commands "
            "WHERE namespace=%s AND security_domain=%s AND command_id=%s FOR UPDATE",
            (i.namespace, i.security_domain, i.command_id),
        ).fetchone()
        if command != {
            "state": "EFFECT_STARTED",
            "attempt_id": i.attempt_id,
            "principal_id": i.principal_id,
            "terminal_record": None,
        }:
            raise AuthorityError("NATIVE_WAIT_COMMAND_NOT_ACTIVE")
        skill = c.execute(
            "SELECT p.state,i.attempt_id,i.workflow_run_id,i.executor_id,i.executor_revision,"
            "i.executor_configuration_digest FROM skill_invocation.invocations i "
            "JOIN skill_invocation.projections p USING(namespace,security_domain,skill_invocation_id) "
            "WHERE i.namespace=%s AND i.security_domain=%s AND i.skill_invocation_id=%s FOR UPDATE OF p",
            i.skill_key,
        ).fetchone()
        expected_state = skill["state"] if skill else None
        allowed_states = (
            {"RUNNING", "DISPATCH_RECORDED"} if operation == "REGISTER" else {"RUNNING"}
        )
        if expected_state not in allowed_states or skill != {
            "state": expected_state,
            "attempt_id": i.attempt_id,
            "workflow_run_id": i.workflow_run_id,
            "executor_id": cp.executor_id,
            "executor_revision": cp.executor_revision,
            "executor_configuration_digest": cp.executor_configuration_digest,
        }:
            raise AuthorityError("NATIVE_WAIT_SKILL_NOT_ACTIVE")
        p, progress = PreparedExecutionStore(c).read(
            i.namespace, i.security_domain, i.workflow_run_id, lock=True
        )
        task = next((t for t in progress.tasks if t.task_id == i.task_id), None)
        if (
            p.digest != i.preparation_digest
            or p.source_snapshot.digest != cp.source_digest
            or progress.state != "RUNNING"
            or progress.cancellation_request_id
            or task is None
            or task.state != "RUNNING"
            or task.attempt_id != i.attempt_id
        ):
            raise AuthorityError("NATIVE_WAIT_PREPARATION_NOT_ACTIVE")
        root = c.execute(
            "SELECT request_digest,result FROM skill_invocation.native_loop_records "
            "WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s AND record_key=%s",
            (*i.skill_key, cp.root_key),
        ).fetchone()
        if root != {"request_digest": cp.root_digest, "result": None}:
            raise AuthorityError("NATIVE_WAIT_ROOT_NOT_ACTIVE")
        return NativeWaitStore(c, i)

    def register(self, c, checkpoint, question):
        store = self._lock(c, checkpoint, "REGISTER")
        cp = checkpoint
        if self.clock() >= cp.human_expires_at:
            raise AuthorityError("NATIVE_WAIT_EXPIRED")
        contract = question.get("answerContract")
        extra = {}
        if contract is not None:
            from .native_question_contracts import validate_contract

            if (cp.executor_id, cp.executor_revision) != (
                "native-document-review",
                "7",
            ):
                raise AuthorityError("NATIVE_WAIT_TYPED_QUESTION_NOT_ENABLED")
            validate_contract(contract)
            p, _ = PreparedExecutionStore(c).read(
                cp.identity.namespace,
                cp.identity.security_domain,
                cp.identity.workflow_run_id,
            )
            if contract["sourceReference"] != p.source_snapshot.model_dump(mode="json"):
                raise AuthorityError("NATIVE_WAIT_TYPED_SOURCE_CHANGED")
            extra = {"answerContract": contract}
        if (
            question
            != {
                "kind": "NATIVE_QUESTION",
                "question": question.get("question"),
                "questionKey": cp.question_key,
                "principal": cp.identity.principal_id,
                "workflowRunId": cp.identity.workflow_run_id,
                "expiresAt": cp.human_expires_at.isoformat(),
                **extra,
            }
            or not isinstance(question.get("question"), str)
            or not question["question"].strip()
        ):
            raise AuthorityError("NATIVE_WAIT_QUESTION_BINDING_INVALID")
        if digest(question) != cp.question_digest:
            raise AuthorityError("NATIVE_WAIT_QUESTION_BINDING_INVALID")
        action = {"action": "CLARIFY", "question": question["question"]}
        if contract is not None:
            action["questionContractId"] = contract["contractDigest"]
        if digest(action) != cp.input_request_digest:
            raise AuthorityError("NATIVE_WAIT_INPUT_BINDING_INVALID")
        self._effects(c, cp, action)
        result = store.register(cp, question, cp.input_request_digest)
        from .native_wait_skill import record_running

        record_running(self.skill_repository, c, cp, self.clock())
        return result

    @staticmethod
    def _effects(c, cp, action):
        rows = c.execute(
            "SELECT record_key,request_digest,result FROM skill_invocation.native_loop_records "
            "WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s",
            cp.identity.skill_key,
        ).fetchall()
        effects = {
            r["record_key"]: r
            for r in rows
            if r["record_key"].endswith((":MODEL", ":TOOL", ":INPUT", ":VERIFY"))
        }
        expected = {r.key: r for r in cp.completed_effects}
        # Register replay can have its single outstanding INPUT, never another
        # unsettled decision/tool. All earlier effects are exact settled receipts.
        effects.pop(cp.question_key, None)
        if effects.keys() != expected.keys():
            raise AuthorityError("NATIVE_WAIT_EFFECT_SET_CHANGED")
        for key, ref in expected.items():
            row = effects[key]
            if (
                row["request_digest"] != ref.request_digest
                or row["result"] is None
                or digest(row["result"]) != ref.result_digest
            ):
                raise AuthorityError("NATIVE_WAIT_EFFECT_NOT_SETTLED")
        if effects[f"{cp.root_key}:{cp.ordinal}:MODEL"]["result"] != action:
            raise AuthorityError("NATIVE_WAIT_DECISION_NOT_CLARIFICATION")

    def confirm_stopped(self, c, cp, observation, verify_exit):
        # Stop observer proves exact child birth/nonce/exit; not callable by an
        # ordinary answer endpoint. Proof verification precedes persistence.
        if (
            observation.checkpoint_digest != cp.digest
            or observation.command_id != cp.identity.command_id
            or observation.worker_id != cp.worker_id
            or observation.startup_record_digest != cp.startup_record_digest
        ):
            raise AuthorityError("NATIVE_WAIT_STOP_BINDING_INVALID")
        verify_exit(c, cp, observation)
        store = self._lock(c, cp, "STOP_OBSERVATION")
        head = store.head()
        prior = store.observation(cp.digest, "STOP_CONFIRMED")
        record = observation.model_dump(mode="json")
        if prior:
            if prior != record:
                raise AuthorityError("NATIVE_WAIT_STOP_CONFLICT")
            return
        if (
            not head
            or head["checkpoint_digest"] != cp.digest
            or head["state"] not in {"QUIESCING", "ANSWER_SAVED"}
        ):
            raise AuthorityError("NATIVE_WAIT_NOT_QUIESCING")
        if (
            observation.stopped_at < cp.created_at
            or observation.stopped_at > self.clock()
        ):
            raise AuthorityError("NATIVE_WAIT_STOP_TIME_INVALID")
        state = (
            "ANSWER_SAVED"
            if store.observation(cp.digest, "ANSWER_SAVED")
            else "WAITING_FOR_USER"
        )
        store.transition(head, state, "STOP_CONFIRMED", record)

    def accept_answer(self, c, cp, answer):
        store = self._lock(c, cp, "ANSWER")
        head = store.head()
        if not head or head["checkpoint_digest"] != cp.digest:
            raise AuthorityError("NATIVE_WAIT_QUESTION_NOT_CURRENT")
        if (
            set(answer)
            != (
                {"kind", "answer", "conversationId", "principal", "questionDigest"}
                | (
                    {"verifiedInterpretation"}
                    if "verifiedInterpretation" in answer
                    else set()
                )
            )
            or answer["kind"] != "NATIVE_ANSWER"
            or answer["principal"] != cp.identity.principal_id
            or answer["conversationId"] != cp.identity.conversation_id
            or answer["questionDigest"] != cp.question_digest
            or not isinstance(answer["answer"], str)
            or not answer["answer"].strip()
        ):
            raise AuthorityError("NATIVE_WAIT_ANSWER_BINDING_INVALID")
        return self._save_answer(c, cp, answer, store, head)

    def accept_delegated_answer(self, c, cp, answer):
        """Explicit actor/subject path; original execution authorization still runs.

        The installed private port verifies the presented question, current human
        QUESTION_ANSWER grant and saved C1 interpretation on this connection.
        Default-off callers cannot supply a boolean proof or impersonate service.
        """
        from .fixed_question_types import DelegatedAnswer, QuestionPresentation

        if self.authorize_delegated_answer is None:
            raise AuthorityError("NATIVE_WAIT_DELEGATION_NOT_ENABLED")
        try:
            value = DelegatedAnswer.model_validate(answer)
        except ValueError as exc:
            raise AuthorityError("NATIVE_WAIT_DELEGATED_ANSWER_INVALID") from exc
        store = self._lock(c, cp, "DELEGATED_ANSWER")
        head = store.head()
        if (
            not head
            or head["checkpoint_digest"] != cp.digest
            or store.checkpoint(cp.digest) != cp
        ):
            raise AuthorityError("NATIVE_WAIT_QUESTION_NOT_CURRENT")
        presentation = self.authorize_delegated_answer(c, cp, value)
        if not isinstance(presentation, QuestionPresentation):
            raise AuthorityError("NATIVE_WAIT_DELEGATED_AUTHORITY_INVALID")
        presentation.require_checkpoint(cp)
        if (
            value.presentationDigest != presentation.digest
            or value.actorId != presentation.actorId
            or value.executionSubject != cp.identity.principal_id
            or value.questionDigest != cp.question_digest
            or value.conversationId != cp.identity.conversation_id
        ):
            raise AuthorityError("NATIVE_WAIT_DELEGATED_ANSWER_INVALID")
        if self.clock() >= presentation.expiresAt:
            raise AuthorityError("NATIVE_WAIT_DELEGATION_EXPIRED")
        return self._save_answer(
            c, cp, value.model_dump(mode="json", exclude_none=True), store, head
        )

    def _save_answer(self, c, cp, answer, store, head):
        prior = store.observation(cp.digest, "ANSWER_SAVED")
        if prior:
            if prior != answer:
                raise AuthorityError("NATIVE_ANSWER_CONFLICT")
            return {"accepted": True, "replayed": True}
        if self.clock() >= cp.human_expires_at:
            raise AuthorityError("NATIVE_WAIT_EXPIRED")
        if head["state"] not in {"QUIESCING", "WAITING_FOR_USER"}:
            raise AuthorityError("NATIVE_WAIT_NOT_ACCEPTING_INPUT")
        question = c.execute(
            "SELECT request_digest,result FROM skill_invocation.native_loop_records WHERE namespace=%s "
            "AND security_domain=%s AND skill_invocation_id=%s AND record_key=%s",
            (*store.key, cp.question_key + ":question"),
        ).fetchone()
        if (
            not question
            or question["request_digest"] != cp.question_digest
            or digest(question["result"]) != cp.question_digest
        ):
            raise AuthorityError("NATIVE_WAIT_QUESTION_BINDING_INVALID")
        extra = self._answer_extra(cp, question["result"], answer)
        reply = {
            "question": question["result"]["question"],
            "answer": answer["answer"],
            "questionDigest": cp.question_digest,
            **extra,
        }
        c.execute(
            "INSERT INTO skill_invocation.native_loop_records(namespace,security_domain,skill_invocation_id,record_key,request_digest,result,completed_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,clock_timestamp())",
            (
                *store.key,
                cp.question_key + ":answer",
                cp.question_digest,
                Jsonb(answer),
            ),
        )
        done = c.execute(
            "UPDATE skill_invocation.native_loop_records SET result=%s,completed_at=clock_timestamp() "
            "WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s AND record_key=%s AND request_digest=%s AND result IS NULL RETURNING record_key",
            (Jsonb(reply), *store.key, cp.question_key, cp.input_request_digest),
        ).fetchone()
        if not done:
            raise AuthorityError("NATIVE_WAIT_INPUT_ALREADY_FINISHED")
        store.transition(head, "ANSWER_SAVED", "ANSWER_SAVED", answer)
        return {"accepted": True, "replayed": False}

    @staticmethod
    def _answer_extra(cp, question, answer):
        contract = question.get("answerContract")
        extra = {}
        if contract is not None:
            from .native_question_contracts import validate_meaning

            interpretation = answer.get("verifiedInterpretation")
            if (
                (cp.executor_id, cp.executor_revision)
                != ("native-document-review", "7")
                or not isinstance(interpretation, dict)
                or interpretation.get("schemaVersion")
                != "native-verified-question-answer.v1"
                or interpretation.get("questionDigest") != cp.question_digest
                or interpretation.get("interpretationDigest")
                != digest(
                    {
                        k: v
                        for k, v in interpretation.items()
                        if k != "interpretationDigest"
                    }
                )
            ):
                raise AuthorityError("NATIVE_WAIT_TYPED_ANSWER_REQUIRED")
            validate_meaning(
                {
                    k: interpretation.get(k)
                    for k in ("decision", "candidateId", "questionContractDigest")
                },
                contract,
            )
            extra = {
                "answerContract": contract,
                "verifiedInterpretation": interpretation,
            }
        elif "verifiedInterpretation" in answer:
            raise AuthorityError("NATIVE_WAIT_UNEXPECTED_INTERPRETATION")
        return extra

    def claim_continuation(
        self, c, cp, *, worker_id, startup_record_digest, verify_worker
    ):
        store = self._lock(c, cp, "CONTINUE")
        verify_worker(c, cp, worker_id, startup_record_digest)
        head = store.head()
        if not head or head["checkpoint_digest"] != cp.digest:
            raise AuthorityError("NATIVE_WAIT_QUESTION_NOT_CURRENT")
        answer = store.observation(cp.digest, "ANSWER_SAVED")
        if not answer or not store.observation(cp.digest, "STOP_CONFIRMED"):
            raise AuthorityError("NATIVE_WAIT_NOT_RESUMABLE")
        claim = ContinuationClaim(
            checkpoint_digest=cp.digest,
            answer_digest=canonical_digest(answer),
            fence=token_hex(32),
            worker_id=worker_id,
            startup_record_digest=startup_record_digest,
        )
        return store.claim(head, claim)

    def enter_continuation(
        self, c, cp, claim, *, worker_id, startup_record_digest, verify_worker
    ):
        """One local driver enters; repeated callers observe without a loop run."""
        store = self._lock(c, cp, "CONTINUE_ENTRY")
        if cp.digest != claim.checkpoint_digest or store.checkpoint(cp.digest) != cp:
            raise AuthorityError("NATIVE_WAIT_BINDING_CHANGED")
        verify_worker(c, cp, worker_id, startup_record_digest)
        head = store.require_fence(
            claim, worker_id=worker_id, startup_record_digest=startup_record_digest
        )
        if head["state"] != "CONTINUATION_CLAIMED":
            return False
        store.transition(
            head,
            "ADVANCING",
            "ADVANCING",
            {"claimDigest": canonical_digest(claim.model_dump(mode="json"))},
        )
        return True

    def claim_effect(
        self,
        c,
        cp,
        claim,
        *,
        worker_id,
        startup_record_digest,
        key,
        request_digest,
        verify_worker,
    ):
        """Fence + journal claim are one transaction; replay is observation only.

        The caller dispatches only when newlyClaimed is True AFTER commit. This
        operation does not settle budget, call a provider or finish the root.
        """
        store = self._lock(c, cp, "EFFECT")
        if (
            cp.digest != claim.checkpoint_digest
            or store.checkpoint(claim.checkpoint_digest) != cp
        ):
            raise AuthorityError("NATIVE_WAIT_BINDING_CHANGED")
        verify_worker(c, cp, worker_id, startup_record_digest)
        head = store.require_fence(
            claim, worker_id=worker_id, startup_record_digest=startup_record_digest
        )
        if head["state"] != "ADVANCING":
            raise AuthorityError("NATIVE_WAIT_CONTINUATION_NOT_ENTERED")
        self._effect_key(cp, key)
        from .native_wait_types import EffectReference

        # Reuse the same bounded digest validator without accepting arbitrary SQL
        # keys or a client-selected request identity.
        EffectReference(
            key=key, request_digest=request_digest, result_digest=request_digest
        )
        prior = c.execute(
            "SELECT request_digest,result FROM skill_invocation.native_loop_records "
            "WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s AND record_key=%s",
            (*store.key, key),
        ).fetchone()
        if prior:
            if prior["request_digest"] != request_digest:
                raise AuthorityError("NATIVE_LOOP_JOURNAL_CONFLICT")
            return {"newlyClaimed": False, "record": prior}
        c.execute(
            "INSERT INTO skill_invocation.native_loop_records "
            "(namespace,security_domain,skill_invocation_id,record_key,request_digest) "
            "VALUES(%s,%s,%s,%s,%s)",
            (*store.key, key, request_digest),
        )
        return {"newlyClaimed": True, "record": None}

    @staticmethod
    def _effect_key(cp, key):
        parts = key.removeprefix(cp.root_key + ":").split(":")
        if (
            not key.startswith(cp.root_key + ":")
            or len(parts) not in {2, 3}
            or not parts[0].isdecimal()
            or str(int(parts[0])) != parts[0]
            or not cp.ordinal < int(parts[0]) < cp.maximum_decisions
            or parts[1] not in {"MODEL", "TOOL", "VERIFY"}
            or (
                len(parts) == 3
                and (parts[1] != "MODEL" or parts[2] not in {"receipt", "settlement"})
            )
        ):
            raise AuthorityError("NATIVE_WAIT_EFFECT_KEY_MISMATCH")

    def finish_effect(
        self,
        c,
        cp,
        claim,
        *,
        worker_id,
        startup_record_digest,
        key,
        request_digest,
        result,
        verify_worker,
    ):
        """Persist a receipt under the same live fence, never authorize dispatch."""
        store = self._lock(c, cp, "EFFECT_RECEIPT")
        if cp.digest != claim.checkpoint_digest or store.checkpoint(cp.digest) != cp:
            raise AuthorityError("NATIVE_WAIT_BINDING_CHANGED")
        verify_worker(c, cp, worker_id, startup_record_digest)
        head = store.require_fence(
            claim, worker_id=worker_id, startup_record_digest=startup_record_digest
        )
        if head["state"] != "ADVANCING":
            raise AuthorityError("NATIVE_WAIT_CONTINUATION_NOT_ENTERED")
        self._effect_key(cp, key)
        row = c.execute(
            "SELECT request_digest,result FROM skill_invocation.native_loop_records "
            "WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s AND record_key=%s FOR UPDATE",
            (*store.key, key),
        ).fetchone()
        if not row or row["request_digest"] != request_digest:
            raise AuthorityError("NATIVE_LOOP_JOURNAL_CONFLICT")
        if row["result"] is not None:
            if row["result"] != result:
                raise AuthorityError("NATIVE_LOOP_JOURNAL_CONFLICT")
            return
        c.execute(
            "UPDATE skill_invocation.native_loop_records SET result=%s,completed_at=clock_timestamp() "
            "WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s AND record_key=%s",
            (Jsonb(result), *store.key, key),
        )

    def finish_root(
        self, c, cp, claim, *, worker_id, startup_record_digest, result, verify_worker
    ):
        store = self._lock(c, cp, "TERMINAL_RECEIPT")
        if cp.digest != claim.checkpoint_digest or store.checkpoint(cp.digest) != cp:
            raise AuthorityError("NATIVE_WAIT_BINDING_CHANGED")
        verify_worker(c, cp, worker_id, startup_record_digest)
        head = store.require_fence(
            claim, worker_id=worker_id, startup_record_digest=startup_record_digest
        )
        if head["state"] != "ADVANCING":
            raise AuthorityError("NATIVE_WAIT_CONTINUATION_NOT_ENTERED")
        pending = c.execute(
            "SELECT record_key FROM skill_invocation.native_loop_records "
            "WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s "
            "AND record_key<>%s AND result IS NULL LIMIT 1",
            (*store.key, cp.root_key),
        ).fetchone()
        if pending:
            raise AuthorityError("NATIVE_WAIT_EFFECT_NOT_SETTLED")
        changed = c.execute(
            "UPDATE skill_invocation.native_loop_records SET result=%s,completed_at=clock_timestamp() "
            "WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s "
            "AND record_key=%s AND request_digest=%s AND result IS NULL RETURNING record_key",
            (Jsonb(result), *store.key, cp.root_key, cp.root_digest),
        ).fetchone()
        if not changed:
            raise AuthorityError("NATIVE_WAIT_ROOT_NOT_ACTIVE")
        store.transition(
            head, "COMPLETED", "COMPLETED", {"terminalDigest": digest(result)}
        )

    def next_question(
        self,
        c,
        previous,
        claim,
        checkpoint,
        question,
        *,
        worker_id,
        startup_record_digest,
        verify_worker,
    ):
        """Complete one wait and register the next atomically in the original job."""
        store = self._lock(c, previous, "NEXT_QUESTION")
        if (
            previous.digest != claim.checkpoint_digest
            or store.checkpoint(previous.digest) != previous
        ):
            raise AuthorityError("NATIVE_WAIT_BINDING_CHANGED")
        verify_worker(c, previous, worker_id, startup_record_digest)
        head = store.require_fence(
            claim, worker_id=worker_id, startup_record_digest=startup_record_digest
        )
        immutable = (
            "identity",
            "root_key",
            "root_digest",
            "executor_id",
            "executor_revision",
            "executor_configuration_digest",
            "source_digest",
            "model_profile_digest",
            "scope_evidence_digest",
            "maximum_decisions",
            "authority_expires_at",
        )
        if (
            head["state"] != "ADVANCING"
            or any(getattr(previous, k) != getattr(checkpoint, k) for k in immutable)
            or checkpoint.ordinal <= previous.ordinal
            or checkpoint.remaining_active_milliseconds
            > previous.remaining_active_milliseconds
            or checkpoint.worker_id != worker_id
            or checkpoint.startup_record_digest != startup_record_digest
            or checkpoint.created_at < previous.created_at
        ):
            raise AuthorityError("NATIVE_WAIT_SUCCESSOR_BINDING_INVALID")
        store.transition(
            head, "COMPLETED", "COMPLETED", {"nextCheckpointDigest": checkpoint.digest}
        )
        # register rechecks all settled effects and current owner rows; any failure
        # rolls back COMPLETED as well. No standalone completion-before-register.
        return self.register(c, checkpoint, question)

    def read_continuation(self, c, cp, root):
        """Reconstruct only exact original receipts; no model/tool/terminal writes."""
        from agent_runtime.native_loop_wait import reconstruct_continuation

        store = self._lock(c, cp, "CONTINUE_FRAME")
        if store.checkpoint(cp.digest) != cp or digest(root) != cp.root_digest:
            raise AuthorityError("NATIVE_WAIT_BINDING_CHANGED")
        if (
            root.get("identity") != cp.root_key
            or root.get("limits", {}).get("maximum_decisions") != cp.maximum_decisions
            or root.get("limits", {}).get("total_seconds", 0) * 1000
            < cp.remaining_active_milliseconds
        ):
            raise AuthorityError("NATIVE_WAIT_LIMIT_BINDING_CHANGED")
        head = store.head()
        if not head or head["checkpoint_digest"] != cp.digest:
            raise AuthorityError("NATIVE_WAIT_QUESTION_NOT_CURRENT")
        saved_answer = store.observation(cp.digest, "ANSWER_SAVED")
        if not saved_answer:
            raise AuthorityError("NATIVE_WAIT_ANSWER_REQUIRED")
        rows = c.execute(
            "SELECT record_key,request_digest,result FROM skill_invocation.native_loop_records "
            "WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s",
            cp.identity.skill_key,
        ).fetchall()
        indexed = {row["record_key"]: row for row in rows}
        receipts = {}
        for ref in cp.completed_effects:
            row = indexed.get(ref.key)
            if (
                not row
                or row["request_digest"] != ref.request_digest
                or row["result"] is None
                or digest(row["result"]) != ref.result_digest
            ):
                raise AuthorityError("NATIVE_WAIT_EFFECT_NOT_SETTLED")
            receipts[ref.key] = {
                "requestDigest": ref.request_digest,
                "result": row["result"],
            }
        question = indexed.get(cp.question_key + ":question")
        answer = indexed.get(cp.question_key + ":answer")
        incoming = indexed.get(cp.question_key)
        if (
            not question
            or not answer
            or not incoming
            or question["request_digest"] != cp.question_digest
            or digest(question["result"]) != cp.question_digest
            or answer["request_digest"] != cp.question_digest
            or answer["result"] != saved_answer
            or incoming["request_digest"] != cp.input_request_digest
        ):
            raise AuthorityError("NATIVE_WAIT_ANSWER_BINDING_INVALID")
        expected_reply = {
            "question": question["result"]["question"],
            "answer": saved_answer["answer"],
            "questionDigest": cp.question_digest,
            **self._answer_extra(cp, question["result"], saved_answer),
        }
        if incoming["result"] != expected_reply:
            raise AuthorityError("NATIVE_WAIT_ANSWER_BINDING_INVALID")
        receipts[cp.question_key] = {
            "requestDigest": cp.input_request_digest,
            "result": incoming["result"],
        }
        return reconstruct_continuation(
            root=root,
            checkpoint_digest=cp.digest,
            ordinal=cp.ordinal,
            remaining_active_seconds=cp.remaining_active_milliseconds / 1000,
            receipts=receipts,
        )
