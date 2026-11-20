"""Exact human conversation provenance; no model, execution or permission issuance."""

import json
from dataclasses import replace

from pydantic import Field

from . import fixed_work_sources_postgres as store
from .authority_contracts import AuthenticationSource
from .business_problem_domain import canonical_bytes, canonical_digest
from .context_call_admission import request_row
from .digital_employee_definition import digest
from .fixed_work_authoring import AuthoringPolicy
from .plan_suggestion_application import PlanningApplication
from .plan_suggestion_domain import ExactReference
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_bff_schemas import StrictWorkbenchModel
from .workbench_business_problem import OwnerPrincipal
from .workbench_fixed_work import grants


class SourceCommand(StrictWorkbenchModel):
    conversationId: str = Field(min_length=1, max_length=200)
    workDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    commandId: str = Field(min_length=1, max_length=200)
    previewDigest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class FixedWorkSourceOwner:
    def __init__(self, authoring, owned_business, problems):
        self.authoring, self.owned, self.problems = authoring, owned_business, problems
        self.conversations = (
            None  # assigned from the existing composed conversation owner
        )

    def __call__(self, call):
        operation = call.operation
        store.require(
            operation
            in {
                "PREPARE_FIXED_WORK_CONVERSATION",
                "READ_FIXED_WORK_SOURCE",
                "BIND_FIXED_WORK_SOURCE",
            },
            "OPERATION_UNSUPPORTED",
        )
        write = operation in {
            "PREPARE_FIXED_WORK_CONVERSATION",
            "BIND_FIXED_WORK_SOURCE",
        }
        ctx, c = call.context, call.connection
        store.require(
            ctx.authentication_source is AuthenticationSource.BROWSER_SESSION,
            "BROWSER_REQUIRED",
        )
        store.require(self.conversations is not None, "CONVERSATION_UNAVAILABLE")
        scope = ctx.scope.tenant_id, ctx.scope.security_domain
        saved = self.authoring(
            replace(call, operation="READ_FIXED_WORK_DRAFT", payload={}, query={})
        )
        work = ExactReference(
            resource_id=saved["draft"]["workId"],
            revision_id=saved["draft"]["revisionId"],
            digest=saved["digest"],
        )
        if write:
            p = AuthoringPolicy.load(self.authoring.policy_path)
            p.require(
                ctx,
                call.path["team_id"],
                call.path["team_revision_id"],
                "SAVE",
                self.authoring.clock(),
            )
            for g in grants(ctx, call.path, {}, {}, write=True):
                call.authority.require(
                    OwnerPrincipal(ctx.principal_id, *scope),
                    g.owner,
                    g.action,
                    g.exact_resource,
                )
        body = SourceCommand.model_validate(call.payload) if write else None
        handoff = store.read(c, scope, "handoffs", work.resource_id, work.revision_id)
        conversation = (
            body.conversationId
            if body
            else (handoff or {}).get("record", {}).get("conversationId")
        )
        if conversation is None:
            return {
                "state": "NO_CONVERSATION",
                "work": work.model_dump(),
                "executionEnabled": False,
            }
        # Existing conversation lock precedes context/admission and work locks.
        conv = self.conversations.owned(c, ctx, conversation, lock=True)
        store.require(
            conv["owner_id"] == ctx.principal_id and conv["archived_at"] is None,
            "CONVERSATION_CHANGED",
        )
        journal = c.execute(
            "SELECT version,state FROM private_conversation.journeys WHERE "
            "tenant_id=%s AND security_domain=%s AND conversation_id=%s FOR "
            "SHARE",
            (*scope, conversation),
        ).fetchone()
        state = journal["state"] if journal else {}
        handoff = store.read(c, scope, "handoffs", work.resource_id, work.revision_id)
        if body:
            store.require(body.workDigest == work.digest, "WORK_CHANGED")
        if operation == "PREPARE_FIXED_WORK_CONVERSATION":
            store.require(
                len(saved["draft"]["instruction"]) <= 2048, "INSTRUCTION_TOO_LONG"
            )
            self.lock_work(c, scope, work)
            handoff = store.read(
                c, scope, "handoffs", work.resource_id, work.revision_id
            )
            value = {
                "schemaVersion": "fixed-work-conversation.v1",
                "work": work.model_dump(),
                "team": saved["draft"]["team"],
                "subjectId": ctx.principal_id,
                "conversationId": conversation,
                "commandId": body.commandId,
                "instructionDigest": digest(saved["draft"]["instruction"]),
                "mode": "TARGET_REVIEW_ONLY",
                "executionEnabled": False,
            }
            if handoff:
                store.require(handoff["record"] == value, "CONFLICT")
                return handoff
            store.require(
                not state
                and not c.execute(
                    "SELECT 1 FROM private_conversation.messages WHERE tenant_id=%s "
                    "AND security_domain=%s AND conversation_id=%s LIMIT 1",
                    (*scope, conversation),
                ).fetchone(),
                "CONVERSATION_NOT_EMPTY",
            )
            store.require(body.previewDigest is None, "COMMAND_INVALID")
            return store.append(c, scope, "handoffs", value)
        store.require(
            handoff is not None
            and handoff["record"]["subjectId"] == ctx.principal_id
            and handoff["record"]["conversationId"] == conversation
            and handoff["record"]["work"] == work.model_dump()
            and handoff["record"]["instructionDigest"]
            == digest(saved["draft"]["instruction"]),
            "HANDOFF_CHANGED",
        )
        if not state.get("problem"):
            store.require(not body, "TARGET_NOT_READY")
            return {
                "state": "AWAITING_CONFIRMED_TARGET",
                "work": work.model_dump(),
                "handoff": handoff,
                "executionEnabled": False,
            }
        provenance = self.confirmed(call, saved, state, conversation)
        self.lock_work(c, scope, work)
        preview = {
            "work": work.model_dump(),
            "team": saved["draft"]["team"],
            "subjectId": ctx.principal_id,
            "conversationId": conversation,
            "handoffDigest": handoff["digest"],
            **provenance,
        }
        bound = store.read(c, scope, "bindings", work.resource_id, work.revision_id)
        if operation == "BIND_FIXED_WORK_SOURCE":
            store.require(
                body.previewDigest == canonical_digest(preview), "PREVIEW_CHANGED"
            )
            value = {
                "schemaVersion": "fixed-work-confirmed-source.v1",
                **preview,
                "commandId": body.commandId,
                "executionEnabled": False,
            }
            bound = store.append(c, scope, "bindings", value)
        if bound:
            store.require(
                {k: bound["record"].get(k) for k in preview} == preview,
                "BOUND_TARGET_CHANGED",
            )
        return {
            "state": "BOUND" if bound else "READY_TO_CONFIRM",
            "preview": preview,
            "previewDigest": canonical_digest(preview),
            "binding": bound,
            "executionEnabled": False,
            "readiness": {
                name: "NOT_EVALUATED"
                for name in (
                    "SERVICE_ADMISSION",
                    "CURRENT_SERVICE_AUTHORITY",
                    "BOUNDED_EVENT_WINDOWS",
                    "CYCLE_HOST",
                )
            },
        }

    @staticmethod
    def lock_work(c, scope, work):
        # Original conversation/context admission locks precede the authoring work lock.
        c.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,67))",
            (digest(("work", *scope, work.resource_id)),),
        )
        head = c.execute(
            "SELECT head_revision_id FROM fixed_work_authoring.heads WHERE "
            "namespace=%s AND security_domain=%s AND work_id=%s",
            (*scope, work.resource_id),
        ).fetchone()
        store.require(
            head and head["head_revision_id"] == work.revision_id, "WORK_CHANGED"
        )

    def confirmed(self, call, saved, state, conversation):
        c, ctx = call.connection, call.context
        scope = ctx.scope.tenant_id, ctx.scope.security_domain
        problem = state["problem"]
        ref = ExactReference(
            resource_id=problem["business_problem_id"],
            revision_id=problem["revision_id"],
            digest=problem["digest"],
        )
        # Existing adopted source only; the journal is not approval.
        binding = self.owned.work(c, ctx, ref)
        rows = c.execute(
            "SELECT context_id,invocation_id FROM "
            "authorization_admin.context_call_objects WHERE tenant_id=%s AND "
            "security_domain=%s AND owner='BUSINESS_PROBLEM' AND "
            "resource_id=%s",
            (*scope, ref.resource_id),
        ).fetchall()
        store.require(len(rows) == 1, "UNDERSTANDING_AMBIGUOUS")
        source, _, _, _, value, ancestry = self.owned._source_evidence(
            c, ctx, rows[0]["invocation_id"]
        )
        store.require(
            source["record"].get("conversation_id") == conversation
            and value.context_id == rows[0]["context_id"]
            and value.state == "SUCCEEDED"
            and value.result_kind == "DRAFT_READY",
            "UNDERSTANDING_CHANGED",
        )
        origin_context = (
            ancestry[-1]["target"]["original_context_id"]
            if ancestry
            else value.context_id
        )
        origin = request_row(c, origin_context)
        store.require(
            origin is not None
            and origin["record"].get("conversation_id") == conversation
            and origin["record"].get("first_user_message_id")
            == state.get("userMessageId"),
            "ORIGINAL_MESSAGE_CHANGED",
        )
        store.require(
            self.owned.root.experience.conversation_scope(
                c, ctx, conversation, state["userMessageId"]
            ),
            "ORIGINAL_MESSAGE_CHANGED",
        )
        msg = c.execute(
            "SELECT author_id,content FROM private_conversation.messages WHERE "
            "tenant_id=%s AND security_domain=%s AND conversation_id=%s AND "
            "message_id=%s",
            (*scope, conversation, state.get("userMessageId")),
        ).fetchone()
        store.require(
            msg
            and msg["author_id"] == ctx.principal_id
            and msg["content"] == saved["draft"]["instruction"]
            and state.get("question") == msg["content"],
            "INSTRUCTION_CHANGED",
        )
        principal = OwnerPrincipal(ctx.principal_id, *scope)
        call.authority.require(
            principal, "BUSINESS_PROBLEM", "READ", "business-problem:" + ref.resource_id
        )
        actual = PlanningApplication(None, self.problems, call.authority).current_input(
            principal, ref.resource_id, c
        )
        store.require(actual["target"]["problem"] == ref.model_dump(), "TARGET_CHANGED")
        for criterion in actual["target"]["criterion_revision_ids"]:
            tied = c.execute(
                "SELECT 1 FROM authorization_admin.context_call_objects "
                "WHERE tenant_id=%s AND security_domain=%s AND context_id=%s "
                "AND owner='SUCCESS_CRITERION' AND resource_id=%s",
                (*scope, rows[0]["context_id"], criterion),
            ).fetchone()
            store.require(tied is not None, "CRITERION_SOURCE_CHANGED")
        source_input = value.input_source
        store.require(
            source_input
            and source_input["source"] == binding.scope.source.model_dump()
            and source_input["sourceContentDigest"]
            == binding.scope.sourceContentDigest,
            "INPUT_CHANGED",
        )
        return {
            "originalMessageId": state["userMessageId"],
            "originalContextId": origin_context,
            "instructionDigest": digest(msg["content"]),
            "understanding": {
                "invocationId": value.invocation_id,
                "aggregateVersion": value.aggregate_version,
                "contextId": value.context_id,
            },
            "admission": {"id": binding.admission_id, "digest": binding.record_digest},
            "inputSource": source_input,
            "target": actual["target"],
            "title": actual["title"],
            "description": actual["description"],
            "criteria": json.loads(canonical_bytes(actual["criteria"])),
        }


def source_operations(owner, *, enabled=False):
    if not enabled:
        return ()
    path = (
        PREFIX + "/teams/{team_id}/revisions/{team_revision_id}/fixed-work-drafts/"
        "{work_id}/revisions/{revision_id}"
    )
    return tuple(
        WorkbenchOperation(
            name,
            method,
            path + suffix,
            SourceCommand if method == "POST" else None,
            None,
            lambda c, p, b, q, write=method == "POST": grants(c, p, b, q, write=write),
            owner,
        )
        for name, method, suffix in (
            ("PREPARE_FIXED_WORK_CONVERSATION", "POST", "/conversation"),
            ("READ_FIXED_WORK_SOURCE", "GET", "/source"),
            ("BIND_FIXED_WORK_SOURCE", "POST", "/source"),
        )
    )
