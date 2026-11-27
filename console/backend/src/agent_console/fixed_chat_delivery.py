# ruff: noqa: E501 -- Explicit bounded same-connection owner queries.
"""Original-chat event projection. No journal mutation or execution commands."""

from .authority_contracts import ExactGrant
from .digital_employee_definition import digest
from .execution_preparation_postgres import PreparedExecutionStore
from .fixed_chat_facts import binding_facts, event_facts, planning_facts, require
from .fixed_work_authoring_postgres import read as read_work


class FixedChatDelivery:
    def __init__(self, policy, records, automation, cursors):
        self.policy, self.records = policy, records
        self.automation, self.cursors = automation, cursors

    def binding(self, call, conversation):
        permit = self.policy.require(
            call.context, conversation, self.automation.grants.clock()
        )
        owned = self.records.owned(
            call.connection, call.context, conversation, lock=True
        )
        require(
            owned["owner_id"] == call.context.principal_id
            and owned["archived_at"] is None
        )
        scope = permit.tenantId, permit.securityDomain
        from .fixed_work_sources_postgres import read

        rows = [
            read(
                call.connection,
                scope,
                table,
                permit.work.resource_id,
                permit.work.revision_id,
            )
            for table in ("bindings", "handoffs")
        ]
        saved = read_work(
            call.connection, scope, permit.work.resource_id, permit.work.revision_id
        )
        bound = binding_facts(*rows, saved, permit)
        from .fixed_chat_provenance import require_retained

        require_retained(call.connection, call.context, bound)
        return permit, bound, saved

    def event(self, call, permit, bound, saved, row):
        admission = call.connection.execute(
            "SELECT * FROM fixed_work_service.planning_preparations WHERE namespace=%s "
            "AND security_domain=%s AND work_id=%s AND event_id=%s",
            (
                permit.tenantId,
                permit.securityDomain,
                permit.work.resource_id,
                row["event_id"],
            ),
        ).fetchone()
        prepared, progress = PreparedExecutionStore(call.connection).read(
            permit.tenantId, permit.securityDomain, row["workflow_run_id"]
        )
        discovery = planning_facts(admission, bound, saved, permit)
        value = event_facts(row, admission, bound, saved, prepared, permit)
        value.update(phase="EXECUTION", discoveryDigest=discovery["discoveryDigest"])
        # Prove the original continuation receipt, not just an index pointing at a Run.
        require(row["start_command_key"].endswith(":start"))
        original = call.connection.execute(
            "SELECT result FROM execution_authority.prepared_resource_commands "
            "WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND command_key=%s",
            (
                permit.tenantId,
                permit.securityDomain,
                row["actor_id"],
                row["start_command_key"][:-6],
            ),
        ).fetchone()
        require(original is not None)
        receipt = original["result"]
        require(
            receipt["subject"] == row["actor_id"]
            and receipt["preparationDigest"] == prepared.digest
            and receipt["runId"] == row["workflow_run_id"]
            and receipt["executionStarted"] is True
            and row["payload_digest"]
            == digest(
                dict(
                    work=permit.work.model_dump(mode="json"),
                    event=row["event_id"],
                    plan=receipt["sourcePlanDigest"],
                )
            )
            and row["start_command_key"]
            == "readonly-continuation:" + receipt["sourcePlanDigest"] + ":start"
        )
        readable = call.authority.current_action_grants(
            (
                ExactGrant(
                    "EXECUTION",
                    "READ",
                    "governed-execution:prepared:" + prepared.digest,
                ),
            )
        ) == (True,)
        from .fixed_chat_read_access import members_for, target_digest

        value["readTargetDigest"] = target_digest(
            members_for(call, prepared, self.automation.grants.target_validator)
        )
        value.update(
            readState="READABLE" if readable else "READ_REQUIRED",
            execution={
                "state": progress.state,
                "version": progress.version,
            }
            if readable
            else None,
        )
        return value, prepared

    def selected(self, call, conversation, event_id, receipt_digest):
        permit, bound, saved = self.binding(call, conversation)
        rows = call.connection.execute(
            "SELECT * FROM fixed_work_triggers.receipts WHERE namespace=%s AND security_domain=%s "
            "AND work_id=%s AND revision_id=%s AND work_digest=%s AND event_id=%s",
            (
                permit.tenantId,
                permit.securityDomain,
                permit.work.resource_id,
                permit.work.revision_id,
                permit.work.digest,
                event_id,
            ),
        ).fetchall()
        require(len(rows) == 1)
        event, prepared = self.event(call, permit, bound, saved, rows[0])
        require(event["receiptDigest"] == receipt_digest)
        return permit, bound, event, prepared

    def read(self, call, conversation, cursor=None):
        owned = self.records.owned(
            call.connection, call.context, conversation, lock=True
        )
        require(
            owned["owner_id"] == call.context.principal_id
            and owned["archived_at"] is None
        )
        from .fixed_work_sources_postgres import conversation_binding

        found = conversation_binding(
            call.connection,
            (call.context.scope.tenant_id, call.context.scope.security_domain),
            conversation,
        )
        if found is None:
            return dict(
                conversationId=conversation,
                state="NO_BOUND_WORK",
                items=[],
                hasMore=False,
                nextCursor=None,
                partial=False,
                answerDelegation="UNAVAILABLE",
            )
        permit, bound, saved = self.binding(call, conversation)
        route = "FIXED_CHAT:" + digest(
            [conversation, permit.bindingDigest, self.policy.model_dump(mode="json")]
        )
        after = None
        if cursor:
            after = self.cursors.resolve(
                cursor, route=route, context=call.context, page_size=20, key_size=2
            )
        params = [
            permit.tenantId,
            permit.securityDomain,
            permit.work.resource_id,
            permit.work.revision_id,
        ]
        suffix = ""
        if after:
            suffix = " AND ((policy->'eventWindows'->event_id->>0)::timestamptz,event_id)<(%s::timestamptz,%s)"
            params.extend(after)
        rows = call.connection.execute(
            "SELECT * FROM fixed_work_service.planning_preparations WHERE namespace=%s AND security_domain=%s "
            "AND work_id=%s AND revision_id=%s"
            + suffix
            + " ORDER BY (policy->'eventWindows'->event_id->>0)::timestamptz DESC,event_id DESC LIMIT 21",
            tuple(params),
        ).fetchall()
        items = []
        for admission in rows[:20]:
            pending = planning_facts(admission, bound, saved, permit)
            receipts = call.connection.execute(
                "SELECT * FROM fixed_work_triggers.receipts WHERE namespace=%s AND security_domain=%s "
                "AND work_id=%s AND revision_id=%s AND event_id=%s",
                (
                    permit.tenantId,
                    permit.securityDomain,
                    permit.work.resource_id,
                    permit.work.revision_id,
                    admission["event_id"],
                ),
            ).fetchall()
            require(len(receipts) <= 1)
            if receipts:
                items.append(self.event(call, permit, bound, saved, receipts[0])[0])
            else:
                invocation = call.connection.execute(
                    "SELECT i.record,i.actor_id,r.record result FROM workflow_planning.invocations i "
                    "LEFT JOIN workflow_planning.invocation_results r USING(namespace,security_domain,invocation_id) "
                    "WHERE namespace=%s AND security_domain=%s AND invocation_id=%s",
                    (
                        permit.tenantId,
                        permit.securityDomain,
                        admission["invocation_id"],
                    ),
                ).fetchone()
                if invocation:
                    require(
                        invocation["record"] == admission["record"]
                        and invocation["actor_id"] == admission["subject_id"]
                    )
                result = invocation["result"] if invocation else None
                pending["planningState"] = (
                    "PREPARED"
                    if result
                    and result.get("technical_status") == "SUCCEEDED"
                    and result.get("kind") == "VALID_SUGGESTION"
                    else "REQUIRES_REVIEW"
                    if result or not invocation
                    else "RECORDED"
                )
                items.append(pending)
        more = len(rows) > 20
        next_cursor = (
            self.cursors.mint(
                route=route,
                context=call.context,
                page_size=20,
                last_key=(items[19]["scheduledAt"], items[19]["eventId"]),
            )
            if more
            else None
        )
        return dict(
            conversationId=conversation,
            state="BOUND",
            bindingDigest=permit.bindingDigest,
            work=permit.work.model_dump(mode="json"),
            problem=bound["target"]["problem"],
            inputSource=bound["inputSource"],
            trigger=saved["record"]["trigger"],
            workTitle=saved["record"]["title"],
            items=items,
            hasMore=more,
            nextCursor=next_cursor,
            partial=False,
            answerDelegation="UNAVAILABLE",
        )
