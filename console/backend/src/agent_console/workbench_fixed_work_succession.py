"""Explicit pre-target successor, same original authoring/conversation transaction."""

from dataclasses import replace

from psycopg.types.json import Jsonb

from . import fixed_work_sources_postgres as sources
from . import fixed_work_succession_postgres as store
from .authority_contracts import AuthenticationSource
from .digital_employee_definition import digest
from .execution_domain import ScopeIdentity
from .fixed_work_authoring import SaveDraft
from .fixed_work_succession import SuccessionCommand, preview, require, successor_ids
from .team_definition_postgres import PostgresTeamDefinitionRepository as Teams
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_fixed_work import grants


class FixedWorkSuccessionOwner:
    def __init__(self, source_owner):
        self.source = source_owner

    def __call__(self, call):
        c, ctx = call.connection, call.context
        scope = ctx.scope.tenant_id, ctx.scope.security_domain
        require(
            ctx.authentication_source is AuthenticationSource.BROWSER_SESSION,
            "BROWSER_REQUIRED",
        )
        store.compatible(c)
        read = call.operation == "READ_FIXED_WORK_SUCCESSION"
        if read:
            prior = c.execute(
                "SELECT * FROM fixed_work_successions.transitions WHERE "
                "namespace=%s AND security_domain=%s "
                "AND subject_id=%s AND command_id=%s",
                (*scope, ctx.principal_id, call.path["command_id"]),
            ).fetchone()
            if not prior:
                # Even absence is revealed only after original authoring READ.
                self.source.authoring(
                    replace(
                        call, operation="READ_FIXED_WORK_DRAFT", payload={}, query={}
                    )
                )
                return {"state": "NOT_RECORDED"}
            body = SuccessionCommand.model_validate(prior["record"]["command"])
        else:
            body = SuccessionCommand.model_validate(call.payload)
        require(
            (body.predecessor.resource_id, body.predecessor.revision_id)
            == (call.path["work_id"], call.path["revision_id"]),
            "PREDECESSOR_CHANGED",
        )
        saved = self.source.authoring(
            replace(call, operation="READ_FIXED_WORK_DRAFT", payload={}, query={})
        )
        require(saved["digest"] == body.predecessor.digest, "WORK_CHANGED")
        handoff = sources.read(
            c,
            scope,
            "handoffs",
            body.predecessor.resource_id,
            body.predecessor.revision_id,
        )
        require(
            handoff is not None and handoff["digest"] == body.predecessorHandoffDigest,
            "HANDOFF_CHANGED",
        )
        conversation = handoff["record"]["conversationId"]
        require(self.source.conversations is not None, "CONVERSATION_UNAVAILABLE")
        chat = self.source.conversations.owned(c, ctx, conversation, lock=True)
        require(
            chat["owner_id"] == ctx.principal_id and chat["archived_at"] is None,
            "CONVERSATION_CHANGED",
        )
        new_path = {
            **call.path,
            "team_id": body.team.resource_id,
            "team_revision_id": body.team.revision_id,
        }
        # Use the same original policy and exact TEAM READ/REVISE authorization;
        # preview checks SAVE too, but never writes a draft or grants permissions.
        from .fixed_work_authoring import AuthoringPolicy
        from .workbench_business_problem import OwnerPrincipal

        policy = AuthoringPolicy.load(self.source.authoring.policy_path)
        for path in (call.path, new_path):
            permit = policy.require(
                ctx,
                path["team_id"],
                path["team_revision_id"],
                "READ" if read else "SAVE",
                self.source.authoring.clock(),
            )
            for g in grants(ctx, path, {}, {}, write=not read):
                call.authority.require(
                    OwnerPrincipal(ctx.principal_id, *scope),
                    g.owner,
                    g.action,
                    g.exact_resource,
                )
        old_team = Teams.read(
            c,
            ScopeIdentity(*scope),
            call.path["team_id"],
            call.path["team_revision_id"],
        )
        new_team = Teams.read(
            c, ScopeIdentity(*scope), body.team.resource_id, body.team.revision_id
        )
        require(new_team.content_digest == body.team.digest, "TEAM_CHANGED")
        require(permit.teamDigest == new_team.content_digest, "POLICY_TEAM_CHANGED")
        current = c.execute(
            "SELECT head_revision_id FROM team_definition.definitions WHERE "
            "namespace=%s AND security_domain=%s "
            "AND team_id=%s FOR SHARE",
            (*scope, body.team.resource_id),
        ).fetchone()
        require(
            read or (current and current["head_revision_id"] == body.team.revision_id),
            "TEAM_HEAD_CHANGED",
        )
        value = preview(
            {"record": saved["draft"], "digest": saved["digest"]},
            handoff,
            old_team,
            new_team,
            ctx.principal_id,
            conversation,
        )
        from .fixed_work_succession_members import changed_references, compositions

        for identity, revision_id, _ in changed_references(value):
            call.authority.require(
                OwnerPrincipal(ctx.principal_id, *scope),
                "EMPLOYEE",
                "READ",
                f"employee:{identity}:{revision_id}",
            )
        value["employeeCompositions"] = compositions(c, scope, value)
        # Original chat lock is held before all original work/command locks.
        store.lock_writes(c, scope)
        c.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,67))",
            (digest(("work", *scope, body.predecessor.resource_id)),),
        )
        prior = c.execute(
            "SELECT * FROM fixed_work_successions.transitions WHERE "
            "namespace=%s AND security_domain=%s "
            "AND subject_id=%s AND command_id=%s",
            (*scope, ctx.principal_id, body.commandId),
        ).fetchone()
        payload = digest(body.model_dump(mode="json"))
        if prior:
            require(prior["payload_digest"] == payload, "COMMAND_CONFLICT")
            checked = store.transition(c, scope, prior["work_id"], prior["revision_id"])
            require(checked == prior, "RECORD_CHANGED")
            return {
                "state": "COMMITTED",
                "record": prior["record"],
                "digest": prior["digest"],
            }
        require(not read, "RECORD_CHANGED")
        store.require_current(c, scope, body.predecessor.resource_id)
        self.source.lock_work(c, scope, body.predecessor)
        self.empty(c, scope, conversation, body.predecessor.resource_id)
        hashed = digest(value)
        if call.operation == "PREVIEW_FIXED_WORK_SUCCESSION":
            require(body.previewDigest is None, "PREVIEW_COMMAND_INVALID")
            return {
                "state": "PREVIEW",
                "preview": value,
                "previewDigest": hashed,
                "executionEnabled": False,
            }
        require(
            call.operation == "COMMIT_FIXED_WORK_SUCCESSION"
            and body.previewDigest == hashed,
            "PREVIEW_CHANGED",
        )
        previous = store.transition(
            c, scope, body.predecessor.resource_id, body.predecessor.revision_id
        )
        logical = (
            previous["logical_work_id"] if previous else body.predecessor.resource_id
        )
        work_id, revision_id = successor_ids(scope, logical, body.commandId)
        data = SaveDraft(
            workId=work_id,
            revisionId=revision_id,
            expectedVersion=0,
            commandId="succession-save:" + digest((logical, body.commandId)),
            **value["preserved"],
        )
        require(
            not c.execute(
                "SELECT 1 FROM fixed_work_authoring.heads WHERE namespace=%s "
                "AND security_domain=%s AND work_id=%s",
                (*scope, work_id),
            ).fetchone(),
            "SUCCESSOR_ID_ALREADY_EXISTS",
        )
        created = self.source.authoring(
            replace(
                call,
                operation="SAVE_FIXED_WORK_DRAFT",
                path=new_path,
                payload=data.model_dump(mode="json"),
                query={},
            )
        )
        work = {
            "resource_id": work_id,
            "revision_id": revision_id,
            "digest": created["digest"],
        }
        h = {
            "schemaVersion": "fixed-work-conversation.v2",
            "work": work,
            "team": created["draft"]["team"],
            "subjectId": ctx.principal_id,
            "conversationId": conversation,
            "commandId": body.commandId,
            "instructionDigest": digest(created["draft"]["instruction"]),
            "mode": "TARGET_REVIEW_ONLY",
            "executionEnabled": False,
            "logicalWorkId": logical,
            "predecessorHandoffDigest": handoff["digest"],
        }
        record = {
            "schemaVersion": "fixed-work-succession.v1",
            "scope": list(scope),
            "logicalWorkId": logical,
            "ordinal": previous["ordinal"] + 1 if previous else 1,
            "subjectId": ctx.principal_id,
            "conversationId": conversation,
            "predecessor": body.predecessor.model_dump(mode="json"),
            "predecessorHandoffDigest": handoff["digest"],
            "predecessorTransitionDigest": previous["digest"] if previous else None,
            "work": work,
            "commandId": body.commandId,
            "payloadDigest": payload,
            "command": body.model_dump(mode="json"),
            "preview": value,
            "previewDigest": hashed,
            "handoff": h,
            "effectivePoint": "BEFORE_FIRST_TARGET_ONLY",
            "executionEnabled": False,
            "recordedAt": self.source.authoring.clock().isoformat(),
        }
        c.execute(
            "INSERT INTO fixed_work_successions.transitions "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *scope,
                logical,
                record["ordinal"],
                ctx.principal_id,
                conversation,
                body.predecessor.resource_id,
                body.predecessor.revision_id,
                work_id,
                revision_id,
                body.commandId,
                payload,
                digest(record),
                Jsonb(record),
            ),
        )
        checked = store.transition(c, scope, work_id, revision_id)
        return {
            "state": "COMMITTED",
            "record": checked["record"],
            "digest": checked["digest"],
        }

    @staticmethod
    def empty(c, scope, conversation, work_id):
        for table in ("messages", "journeys"):
            require(
                not c.execute(
                    "SELECT 1 FROM private_conversation."
                    + table
                    + " WHERE tenant_id=%s AND security_domain=%s AND "
                    "conversation_id=%s LIMIT 1",
                    (*scope, conversation),
                ).fetchone(),
                "CONVERSATION_NOT_EMPTY",
            )
        for table in (
            "fixed_work_sources.bindings",
            "fixed_work_successions.bindings",
            "fixed_work_service.planning_preparations",
            "fixed_work_triggers.receipts",
        ):
            if (
                c.execute("SELECT to_regclass(%s) name", (table,)).fetchone()["name"]
                is not None
            ):
                require(
                    not c.execute(
                        "SELECT 1 FROM "
                        + table
                        + " WHERE namespace=%s AND security_domain=%s AND "
                        "work_id=%s LIMIT 1",
                        (*scope, work_id),
                    ).fetchone(),
                    "ALREADY_BOUND_OR_STARTED",
                )


def operations(source_owner):
    owner = FixedWorkSuccessionOwner(source_owner)
    path = (
        PREFIX + "/teams/{team_id}/revisions/{team_revision_id}/fixed-work-drafts"
        "/{work_id}/revisions/{revision_id}/succession"
    )
    return (
        WorkbenchOperation(
            "PREVIEW_FIXED_WORK_SUCCESSION",
            "POST",
            path + "/preview",
            SuccessionCommand,
            None,
            grants,
            owner,
        ),
        WorkbenchOperation(
            "COMMIT_FIXED_WORK_SUCCESSION",
            "POST",
            path,
            SuccessionCommand,
            None,
            grants,
            owner,
            201,
        ),
        WorkbenchOperation(
            "READ_FIXED_WORK_SUCCESSION",
            "GET",
            path + "/commands/{command_id}",
            None,
            None,
            grants,
            owner,
        ),
    )
