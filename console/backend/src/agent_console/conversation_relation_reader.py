# ruff: noqa: E501 -- Exact scoped owner reads; no resource content is loaded.
"""Build and recheck minimal current-work context using existing owner READ ports."""

import copy
import os

from .authority_contracts import ExactGrant
from .business_problem_authorization import problem_resource
from .conversation_relation_context import sealed_snapshot
from .private_conversation import ConversationError, digest
from .workbench_business_problem import OwnerPrincipal


def _ref(value):
    return (value.get("resource_id"), value.get("revision_id"), value.get("digest"))


def _problem_ref(value):
    return (
        value.get("business_problem_id"),
        value.get("revision_id"),
        value.get("digest"),
    )


def _journal(records, context, conversation, message_id):
    with records.connect() as c:
        owned = records.owned(c, context, conversation)
        if owned["archived_at"]:
            raise ConversationError("CONVERSATION_ARCHIVED")
        from .conversation_goal_selection import selected_journal

        row = selected_journal(c, context, conversation, message_id=message_id)
        return row or {"version": 0, "state": {}}


def reader(application, authorizer, business_problems, actions):
    records = actions.records

    def read(context, conversation, message_id, draft_service):
        question_reader = getattr(
            getattr(application, "state", None), "fixed_question_reader", None
        )
        if question_reader is not None:
            observed_question = question_reader.read(
                context, conversation, message_id=message_id, current=True
            )
            if observed_question is not None:
                return observed_question[1]
        focus_reader = getattr(
            getattr(application, "state", None), "fixed_cycle_focus_reader", None
        )
        focus = (
            focus_reader(context, conversation, message_id=message_id)
            if focus_reader
            else None
        )
        if focus is not None:
            _basis, observed = focus
            return sealed_snapshot(
                conversation,
                message_id,
                None,
                {
                    "goal": "就所选固定工作周期的已保存结果作普通回复, 不改变工作目标或安排",
                    "scope": "仅解释以下当前有权读取的保存观察; 不是新的执行请求",
                    "stage": "FIXED_CYCLE_OBSERVATION",
                    **(
                        {"naturalGoalIntentVersion": "v1"}
                        if os.environ.get("CONVERSATION_GOAL_NATURAL_ENABLED") == "1"
                        else {}
                    ),
                    "currentQuestion": None,
                    "fixedCycleObservation": observed,
                },
            )
        from .conversation_goal_neutral import read as read_neutral

        neutral = read_neutral(records, context, conversation, message_id)
        if neutral is not None:
            return neutral
        journal = _journal(records, context, conversation, message_id)
        state = journal["state"] or {}
        current = {
            "goal": None,
            "scope": None,
            "stage": "NO_ACTIVE_WORK",
            "currentQuestion": None,
        }
        target = None
        problem = state.get("problem")
        if not problem or state.get("phase") in {"UNDERSTAND", "CLARIFY"}:
            raise ConversationError("CONVERSATION_ROUTING_WORK_REQUIRED", 409)
        principal = OwnerPrincipal(
            context.principal_id, context.scope.tenant_id, context.scope.security_domain
        )
        base = {"journalVersion": journal["version"], "journeyKey": state.get("key")}
        if problem:
            identity = problem.get("business_problem_id")
            if not identity:
                raise ConversationError("CONVERSATION_ROUTING_CONTEXT_INVALID", 409)

            def resolve(call):
                records.owned(call.connection, context, conversation)
                link = call.connection.execute(
                    "SELECT target FROM private_conversation.links WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s AND target->>'problemId'=%s",
                    (*records.scope(context), conversation, identity),
                ).fetchall()
                if not any(
                    (
                        r["target"].get("problemId"),
                        r["target"].get("revisionId"),
                        r["target"].get("problemDigest"),
                    )
                    == _problem_ref(problem)
                    for r in link
                ):
                    raise ConversationError("CONVERSATION_ROUTING_CONTEXT_INVALID", 409)
                origins = call.connection.execute(
                    "SELECT r.subject_id,r.record->>'conversation_id' AS conversation_id,r.record->>'first_user_message_id' AS first_user_message_id FROM authorization_admin.context_call_objects o JOIN authorization_admin.context_call_requests r USING(tenant_id,security_domain,context_id) WHERE o.tenant_id=%s AND o.security_domain=%s AND o.owner='BUSINESS_PROBLEM' AND o.resource_id=%s LIMIT 2",
                    (*records.scope(context), identity),
                ).fetchall()
                if len(origins) != 1 or (
                    origins[0]["subject_id"],
                    origins[0]["conversation_id"],
                ) != (context.principal_id, conversation):
                    raise ConversationError("CONVERSATION_ROUTING_CONTEXT_INVALID", 409)
                from .conversation_goal_slots import message_goal

                first_message = origins[0].get("first_user_message_id")
                original_goal = (
                    message_goal(
                        call.connection, records, context, conversation, first_message
                    )
                    if first_message
                    else None
                )
                if original_goal != journal.get("goalId"):
                    raise ConversationError("CONVERSATION_GOAL_ORIGIN_CHANGED", 409)
                owner = copy.copy(business_problems)
                owner.authority = call.authority
                view = owner.read_problem(
                    principal, identity, connection=call.connection
                )
                revision = next(
                    (
                        r
                        for r in view["revisions"]
                        if r["revision_id"] == view["problem"]["current_revision_id"]
                    ),
                    None,
                )
                if revision is None or _problem_ref(revision) != _problem_ref(problem):
                    raise ConversationError("CONVERSATION_ROUTING_CONTEXT_CHANGED", 409)
                return revision

            revision = authorizer.execute(
                context,
                (ExactGrant("BUSINESS_PROBLEM", "READ", problem_resource(identity)),),
                operation="READ_CONVERSATION_ROUTING_CONTEXT",
                payload={},
                path={},
                query={},
                handler=resolve,
            )
            current.update(
                goal=revision["title"],
                scope=revision["description"],
                stage=state.get("phase", "CURRENT_WORK"),
            )
            base["problemId"] = identity
            if state.get("execution"):
                execution_digest = state["execution"]

                def native(call):
                    from .execution_domain import ScopeIdentity
                    from .native_interaction import progress
                    from .prepared_execution_application import (
                        PreparedExecutionApplication,
                    )
                    from .workbench_prepared_execution import candidate

                    p = candidate(
                        call.connection,
                        ScopeIdentity(*records.scope(context)),
                        execution_digest,
                    )
                    if _ref(
                        p.semantics.target.problem.model_dump(mode="json")
                    ) != _problem_ref(problem):
                        raise ConversationError(
                            "CONVERSATION_ROUTING_CONTEXT_INVALID", 409
                        )
                    app = PreparedExecutionApplication(
                        call.connection, principal, call.authority
                    )
                    value = progress(call, app, p)
                    run = call.connection.execute(
                        "SELECT record FROM execution_authority.prepared_run_progress WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s",
                        (*records.scope(context), p.run_id),
                    ).fetchone()
                    if not run:
                        raise ConversationError(
                            "CONVERSATION_ROUTING_CONTEXT_UNAVAILABLE", 503
                        )
                    recorded_state = run["record"].get("state")
                    cancellation = run["record"].get("cancellation_request_id")
                    stage = (
                        "DONE"
                        if recorded_state == "SUCCEEDED"
                        else "CANCEL_REQUESTED"
                        if cancellation and recorded_state == "RUNNING"
                        else recorded_state
                        if recorded_state
                        in {
                            "PENDING",
                            "RUNNING",
                            "FAILED",
                            "CANCELLED",
                            "CANCEL_REQUESTED",
                            "RECOVERY_REQUIRED",
                        }
                        else "UNKNOWN"
                    )
                    running = recorded_state == "RUNNING" and not cancellation
                    return value, running, p.run_id, stage

                progress, running, run_id, effective_stage = authorizer.execute(
                    context,
                    (
                        ExactGrant(
                            "EXECUTION",
                            "READ",
                            "governed-execution:prepared:" + execution_digest,
                        ),
                    ),
                    operation="READ_NATIVE_PROGRESS",
                    payload={},
                    path={"digest": execution_digest},
                    query={},
                    handler=native,
                )
                # The journal is a durable orchestration checkpoint, not the
                # execution lifecycle authority. Never rewrite its old facts.
                current["stage"] = effective_stage
                questions = (
                    [
                        q
                        for q in progress["questions"]
                        if not q["answer"] and not q["expired"]
                    ]
                    if running
                    else []
                )
                if len(questions) > 1:
                    raise ConversationError(
                        "CONVERSATION_ROUTING_QUESTION_AMBIGUOUS", 409
                    )
                if questions:
                    q = questions[0]
                    current["currentQuestion"] = q["question"]
                    if q.get("answerContract") is not None:
                        current["currentQuestionType"] = "NATIVE"
                        from .native_question_contracts import validate_contract

                        current["answerContract"] = validate_contract(
                            q["answerContract"]
                        )
                    target = {
                        **base,
                        "kind": "NATIVE",
                        "invocationId": q["invocationId"],
                        "questionKey": q["questionKey"],
                        "questionDigest": q["questionDigest"],
                        "executionDigest": execution_digest,
                        "runId": run_id,
                        "expiresAt": q["expiresAt"],
                    }
            elif state.get("phase") == "PLANNING_CLARIFY":
                identity = (
                    (state.get("planning") or {})
                    .get("invocation", {})
                    .get("target", {})
                    .get("invocation_id")
                )
                planning_reader = getattr(
                    application.state, "conversation_planning_reader", None
                )
                if not identity or planning_reader is None:
                    raise ConversationError(
                        "CONVERSATION_ROUTING_CONTEXT_UNAVAILABLE", 503
                    )
                planning = planning_reader(context, identity)
                plan_target = planning["invocation"]["target"]
                if _ref(plan_target["problem"]["problem"]) != _problem_ref(problem):
                    raise ConversationError("CONVERSATION_ROUTING_CONTEXT_INVALID", 409)
                result = planning["result"]
                if (
                    result.get("technical_status") != "SUCCEEDED"
                    or result.get("kind") != "NEEDS_CLARIFICATION"
                    or not result.get("questions")
                ):
                    raise ConversationError("CONVERSATION_ROUTING_CONTEXT_CHANGED", 409)
                current["currentQuestion"] = "\n".join(result["questions"])
                target = {
                    **base,
                    "kind": "PLANNING",
                    "invocationId": identity,
                    "questionDigest": digest(result),
                }
        # Persist no raw business text in draft invocation metadata; only target
        # identifiers and a fingerprint. Preserve full owner question, never truncate.
        if any(isinstance(v, str) and len(v) > 4000 for v in current.values()):
            raise ConversationError("CONVERSATION_ROUTING_CONTEXT_TOO_LARGE", 422)
        if (
            _journal(records, context, conversation, message_id)["version"]
            != journal["version"]
        ):
            raise ConversationError("CONVERSATION_ROUTING_CONTEXT_CHANGED", 409)
        snapshot = sealed_snapshot(conversation, message_id, target, current)
        if journal.get("goalId") is not None:
            snapshot["goalId"] = journal["goalId"]
        return snapshot

    def safe_read(context, conversation, message_id, draft_service):
        from psycopg import Error as StorageError

        from .authority_contracts import AuthorityError
        from .draft_assistance import DraftAssistanceError
        from .plan_suggestion_domain import PlanningError
        from .workbench_owner_authorization import WorkbenchOwnerError

        try:
            return read(context, conversation, message_id, draft_service)
        except ConversationError:
            raise
        except (AuthorityError, WorkbenchOwnerError, DraftAssistanceError) as exc:
            raise ConversationError("CONVERSATION_ROUTING_ACCESS_DENIED", 403) from exc
        except (
            StorageError,
            OSError,
            TimeoutError,
            PlanningError,
            ValueError,
            KeyError,
            TypeError,
        ) as exc:
            raise ConversationError(
                "CONVERSATION_ROUTING_CONTEXT_UNAVAILABLE", 503
            ) from exc

    return safe_read
