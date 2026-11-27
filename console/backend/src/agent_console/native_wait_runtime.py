"""Private live-loop checkpoint adapter; all authority comes from existing owners."""

from contextvars import ContextVar
from datetime import UTC, datetime, timedelta

from agent_runtime.native_loop import digest
from agent_runtime.native_loop_wait import LoopWaiting

from .authority_contracts import AuthorityError
from .native_host_provenance import lock_identity, require_claim
from .native_wait_owner import NativeWaitOwner
from .native_wait_types import EffectReference, WaitCheckpoint, WaitIdentity

# Set only around the actual managed transport call by NativeDispatchWorker.
# A request body or process environment cannot select this command/startup pair.
HOST_CLAIM = ContextVar("native_wait_host_claim", default=None)
CONTINUATION = ContextVar("native_wait_continuation", default=None)


class NativeWaitRuntimeSession:
    def __init__(
        self,
        *,
        runtime,
        command,
        context,
        preparation,
        task_id,
        invocation_id,
        executor,
        scope_evidence,
        current_authority,
    ):
        live = HOST_CLAIM.get()
        if not live or live[0].command != command or live[1] is None:
            raise AuthorityError("NATIVE_WAIT_EXACT_HOST_REQUIRED")
        self.claim, self.startup = live
        self.runtime, self.command, self.context = runtime, command, context
        self.preparation, self.task_id = preparation, task_id
        self.invocation_id, self.executor = invocation_id, executor
        self.scope_evidence = scope_evidence
        self.current_authority = current_authority
        self.continuation = CONTINUATION.get()
        self.owner = NativeWaitOwner(self.authorize, runtime.skill_repository)

    def binding(self, c):
        if self.command.principal_id.startswith("service:"):
            reader = getattr(self.runtime, "bound_service_execution", None)
            if reader is None:
                raise AuthorityError("NATIVE_WAIT_SERVICE_BINDING_REQUIRED")
            return reader.read(c, self.context, self.command, self.preparation)
        if self.runtime.owned_business is None:
            raise AuthorityError("NATIVE_WAIT_OWNED_BUSINESS_REQUIRED")
        bound = self.runtime.owned_business.work(
            c,
            self.context,
            self.preparation.semantics.target.problem,
        )
        if bound.scope.source != self.preparation.source_snapshot:
            raise AuthorityError("NATIVE_WAIT_SOURCE_BINDING_CHANGED")
        return bound

    def verify_worker(self, c, cp, worker_id, startup_record_digest):
        if (
            worker_id != self.claim.worker_id
            or startup_record_digest != self.startup["digest"]
        ):
            raise AuthorityError("NATIVE_WAIT_WORKER_BINDING_CHANGED")
        lock_identity(c, self.startup, self.claim.worker_id)
        require_claim(c, self.claim, self.startup, observe_only=True)

    def authorize(self, c, cp, operation):
        # Worker identity lock precedes command/Skill/progress locks. All current
        # grant/source/admission checks use this same transaction, not a new pool.
        self.verify_worker(c, cp, self.claim.worker_id, self.startup["digest"])
        if not self.current_authority(c):
            raise AuthorityError("NATIVE_WAIT_CURRENT_AUTHORITY_REQUIRED")
        bound = self.binding(c)
        expected = self.identity(c, bound)
        if (
            cp.identity != expected
            or cp.maximum_decisions != self.runtime.config["maximumDecisions"]
            or (cp.executor_id, cp.executor_revision, cp.executor_configuration_digest)
            != (
                self.executor.executor_id,
                self.executor.executor_revision,
                self.executor.configuration_digest,
            )
            or cp.source_digest != self.preparation.source_snapshot.digest
            or cp.model_profile_digest != self.runtime.config["modelRuntimeDigest"]
            or cp.scope_evidence_digest != digest(self.scope_evidence)
            or cp.authority_expires_at > self.authority_expiry(c, bound)
        ):
            raise AuthorityError("NATIVE_WAIT_RUNTIME_BINDING_CHANGED")

    def identity(self, c, bound):
        from .bound_service_execution import BoundServiceExecution

        if isinstance(bound, BoundServiceExecution):
            if bound.execution_subject != self.command.principal_id:
                raise AuthorityError("NATIVE_WAIT_SERVICE_BINDING_CHANGED")
            return WaitIdentity(
                namespace=self.command.scope.namespace,
                security_domain=self.command.scope.security_domain,
                preparation_digest=self.preparation.digest,
                workflow_run_id=self.preparation.run_id,
                task_id=self.task_id,
                attempt_id=str(self.command.attempt_id),
                command_id=str(self.command.command_id),
                skill_invocation_id=self.invocation_id,
                principal_id=self.command.principal_id,
                conversation_id=bound.conversation_id,
            )
        row = c.execute(
            "SELECT record FROM authorization_admin.owned_business_admissions "
            "WHERE tenant_id=%s AND security_domain=%s AND admission_id=%s "
            "AND record_digest=%s",
            (
                bound.tenant_id,
                bound.security_domain,
                bound.admission_id,
                bound.record_digest,
            ),
        ).fetchone()
        if not row or row["record"]["subject"] != self.command.principal_id:
            raise AuthorityError("NATIVE_WAIT_ORIGINAL_CONVERSATION_REQUIRED")
        return WaitIdentity(
            namespace=self.command.scope.namespace,
            security_domain=self.command.scope.security_domain,
            preparation_digest=self.preparation.digest,
            workflow_run_id=self.preparation.run_id,
            task_id=self.task_id,
            attempt_id=str(self.command.attempt_id),
            command_id=str(self.command.command_id),
            skill_invocation_id=self.invocation_id,
            principal_id=self.command.principal_id,
            conversation_id=row["record"]["conversationId"],
        )

    def authority_expiry(self, c, bound):
        from .provider_budget_allowance import require

        limits = [bound.expires_at, self.runtime.expiry]
        credential = self.runtime.generation.credential_by_id(
            self.command.credential_id
        )
        if credential is not None:
            limits.append(credential.expires_at)
        allowance = require(c, self.runtime.model.budget)
        if allowance is not None:
            limits.append(allowance.expiresAt)
        return min(limits)

    def defer_input(self, question, *, key, remaining_seconds, frame):
        with self.runtime.pool.connection() as c, c.transaction():
            self.verify_worker(c, None, self.claim.worker_id, self.startup["digest"])
            bound = self.binding(c)
            identity = self.identity(c, bound)
            now = datetime.now(UTC)
            authority_expiry = self.authority_expiry(c, bound)
            expiry = min(
                authority_expiry,
                now
                + timedelta(seconds=self.runtime.durable_wait.maximumHumanWaitSeconds),
            )
            payload = {
                "kind": "NATIVE_QUESTION",
                "question": question,
                "questionKey": key,
                "principal": identity.principal_id,
                "workflowRunId": identity.workflow_run_id,
                "expiresAt": expiry.isoformat(),
            }
            contract = frame.get("answerContract")
            if contract is not None:
                if not getattr(self.runtime.durable_wait, "typedQuestions", False):
                    raise AuthorityError("NATIVE_WAIT_TYPED_QUESTION_NOT_ENABLED")
                from .native_question_contracts import validate_contract

                payload["answerContract"] = validate_contract(contract)
            action = frame["trace"][-1]["decision"]
            if action.get("question") != question:
                raise AuthorityError("NATIVE_WAIT_QUESTION_BINDING_CHANGED")
            rows = c.execute(
                "SELECT record_key,request_digest,result "
                "FROM skill_invocation.native_loop_records "
                "WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s",
                identity.skill_key,
            ).fetchall()
            refs = tuple(
                EffectReference(
                    key=r["record_key"],
                    request_digest=r["request_digest"],
                    result_digest=digest(r["result"]),
                )
                for r in rows
                if r["record_key"].endswith((":MODEL", ":TOOL", ":INPUT", ":VERIFY"))
            )
            cp = WaitCheckpoint(
                identity=identity,
                ordinal=frame["ordinal"],
                root_key=frame["root"]["identity"],
                root_digest=frame["rootDigest"],
                input_request_digest=digest(action),
                question_key=key,
                question_digest=digest(payload),
                worker_id=self.claim.worker_id,
                startup_record_digest=self.startup["digest"],
                executor_id=self.executor.executor_id,
                executor_revision=self.executor.executor_revision,
                executor_configuration_digest=self.executor.configuration_digest,
                source_digest=self.preparation.source_snapshot.digest,
                model_profile_digest=self.runtime.config["modelRuntimeDigest"],
                scope_evidence_digest=digest(self.scope_evidence),
                completed_effects=refs,
                remaining_active_milliseconds=int(remaining_seconds * 1000),
                maximum_decisions=frame["root"]["limits"]["maximum_decisions"],
                created_at=now,
                human_expires_at=expiry,
                authority_expires_at=authority_expiry,
            )
            if self.continuation is None:
                receipt = self.owner.register(c, cp, payload)
            else:
                previous, claim = self.continuation
                receipt = self.owner.next_question(
                    c,
                    previous,
                    claim,
                    cp,
                    payload,
                    worker_id=self.claim.worker_id,
                    startup_record_digest=self.startup["digest"],
                    verify_worker=self.verify_worker,
                )
            self.waiting = receipt
        return LoopWaiting(self.invocation_id, receipt.checkpoint_digest)

    def acquire(self):
        if self.continuation is None:
            return True
        cp, existing = self.continuation
        if existing is not None:
            raise AuthorityError("NATIVE_WAIT_CALLER_CLAIM_NOT_ACCEPTED")
        with self.runtime.pool.connection() as c, c.transaction():
            result = self.owner.claim_continuation(
                c,
                cp,
                worker_id=self.claim.worker_id,
                startup_record_digest=self.startup["digest"],
                verify_worker=self.verify_worker,
            )
        self.continuation = (cp, result.claim)
        return result.newly_claimed

    def terminal(self, root):
        if self.continuation is None:
            return None
        cp, _ = self.continuation
        from .native_wait_store import NativeWaitStore

        with self.runtime.pool.connection() as c, c.transaction():
            self.authorize(c, cp, "TERMINAL_READ")
            store = NativeWaitStore(c, cp.identity)
            head = store.head()
            if not head or head["checkpoint_digest"] != cp.digest:
                raise AuthorityError("NATIVE_WAIT_BINDING_CHANGED")
            if head["state"] != "COMPLETED":
                return None
            record = c.execute(
                "SELECT request_digest,result "
                "FROM skill_invocation.native_loop_records "
                "WHERE namespace=%s AND security_domain=%s "
                "AND skill_invocation_id=%s AND record_key=%s",
                (*cp.identity.skill_key, cp.root_key),
            ).fetchone()
            completed = store.observation(cp.digest, "COMPLETED")
            if (
                digest(root) != cp.root_digest
                or not record
                or record["request_digest"] != cp.root_digest
                or not record["result"]
                or record["result"].get("status") not in {"SUCCEEDED", "STOPPED"}
                or completed != {"terminalDigest": digest(record["result"])}
            ):
                raise AuthorityError("NATIVE_WAIT_TERMINAL_RECEIPT_REQUIRED")
            return record["result"]

    def frame(self, root):
        if self.continuation is None:
            return None
        cp, _claim = self.continuation
        with self.runtime.pool.connection() as c, c.transaction():
            return self.owner.read_continuation(c, cp, root)

    def enter(self, frame, root):
        cp, claim = self.continuation
        if frame.checkpoint_digest != cp.digest or frame.root_digest != digest(root):
            raise AuthorityError("NATIVE_WAIT_BINDING_CHANGED")
        with self.runtime.pool.connection() as c, c.transaction():
            actual = self.owner.read_continuation(c, cp, root)
            if actual != frame:
                raise AuthorityError("NATIVE_WAIT_FRAME_CHANGED")
            return self.owner.enter_continuation(
                c,
                cp,
                claim,
                worker_id=self.claim.worker_id,
                startup_record_digest=self.startup["digest"],
                verify_worker=self.verify_worker,
            )

    def claim_effect(self, key, commitment):
        cp, claim = self.continuation
        with self.runtime.pool.connection() as c, c.transaction():
            result = self.owner.claim_effect(
                c,
                cp,
                claim,
                worker_id=self.claim.worker_id,
                startup_record_digest=self.startup["digest"],
                key=key,
                request_digest=commitment,
                verify_worker=self.verify_worker,
            )
        if result["newlyClaimed"]:
            return None
        row = result["record"]
        return {"requestDigest": row["request_digest"], "result": row["result"]}

    def finish_effect(self, key, commitment, result):
        cp, claim = self.continuation
        with self.runtime.pool.connection() as c, c.transaction():
            args = dict(
                worker_id=self.claim.worker_id,
                startup_record_digest=self.startup["digest"],
                result=result,
                verify_worker=self.verify_worker,
            )
            if key == cp.root_key and commitment == cp.root_digest:
                self.owner.finish_root(c, cp, claim, **args)
            else:
                self.owner.finish_effect(
                    c, cp, claim, key=key, request_digest=commitment, **args
                )

    def restore_library(self, library, frame):
        """Only replay verified local state; never re-invoke a prior tool/model."""
        from .native_scope_answer import record_bound_answer

        for item in frame.observations:
            if item["kind"] == "USER_ANSWER":
                if "answerContract" in item:
                    if not getattr(self.runtime.durable_wait, "typedQuestions", False):
                        raise AuthorityError("NATIVE_WAIT_TYPED_QUESTION_NOT_ENABLED")
                    from .native_question_contracts import consume_interpretation

                    consume_interpretation(
                        library, item["answerContract"], item["verifiedInterpretation"]
                    )
                elif not getattr(self.runtime.durable_wait, "typedQuestions", False):
                    record_bound_answer(library, item["question"], item)
                # A v7 generic clarification remains model context, never a
                # replacement for a verified scope-confirmation contract.
            elif item["kind"] == "TOOL_RESULT" and item["tool"] == "review_document":
                output = item["output"]
                if output.get("sourceDigest") != digest(library.source):
                    raise AuthorityError("NATIVE_WAIT_TOOL_SOURCE_CHANGED")
                library.reviewed = {
                    k: v
                    for k, v in output.items()
                    if k not in {"sourceSnapshot", "sourceDigest"}
                }


class ContinuationJournal:
    """Same Skill journal, with current exact continuation fence on every write."""

    def __init__(self, session):
        self.session = session

    def claim(self, key, request_digest):
        return self.session.claim_effect(key, request_digest)

    def finish(self, key, request_digest, result):
        return self.session.finish_effect(key, request_digest, result)
