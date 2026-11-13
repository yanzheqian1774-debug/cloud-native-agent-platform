"""Fixed-work configuration only, behind exact team and authoring policy gates."""

from psycopg import Error as PostgresError
from psycopg.errors import UniqueViolation
from pydantic import Field

from . import fixed_work_authoring_postgres as store
from .authority_contracts import ExactGrant
from .digital_employee_definition import digest
from .execution_domain import ScopeIdentity
from .fixed_work_authoring import AuthoringPolicy, SaveDraft
from .team_definition import TeamDefinitionError
from .team_definition_postgres import PostgresTeamDefinitionRepository
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_bff_schemas import WorkbenchPageQuery
from .workbench_owner_authorization import WorkbenchOwnerError
from .workbench_team import _Principal


class FixedWorkPageQuery(WorkbenchPageQuery):
    pageSize: int = Field(default=25, ge=1, le=50)


def grants(_context, path, _payload, _query, *, write=False):
    result = [
        ExactGrant("TEAM", "READ", f"team:{path['team_id']}:{path['team_revision_id']}")
    ]
    if write:
        result.append(ExactGrant("TEAM", "REVISE", f"team:{path['team_id']}:aggregate"))
    return tuple(result)


class FixedWorkAuthoringOwner:
    def __init__(self, policy_path, clock, cursors=None):
        self.policy_path, self.clock = policy_path, clock
        self.cursors = cursors

    def __call__(self, call):
        write = call.operation == "SAVE_FIXED_WORK_DRAFT"
        if call.operation not in {
            "SAVE_FIXED_WORK_DRAFT",
            "READ_FIXED_WORK_DRAFT",
            "LIST_FIXED_WORK_DRAFTS",
        }:
            raise WorkbenchOwnerError("FIXED_WORK_OPERATION_UNSUPPORTED", 404)
        context, c = call.context, call.connection
        scope = (context.scope.tenant_id, context.scope.security_domain)
        principal = _Principal(context.principal_id, *scope)
        policy = AuthoringPolicy.load(self.policy_path)
        permit = policy.require(
            context,
            call.path["team_id"],
            call.path["team_revision_id"],
            "SAVE" if write else "READ",
            self.clock(),
        )
        decisions = [
            call.authority.require(principal, g.owner, g.action, g.exact_resource)
            for g in grants(context, call.path, {}, {}, write=write)
        ]
        try:
            team = PostgresTeamDefinitionRepository.read(
                c, ScopeIdentity(*scope), permit.teamId, permit.teamRevisionId
            )
            if team.content_digest != permit.teamDigest:
                raise WorkbenchOwnerError("FIXED_WORK_TEAM_BINDING_CONFLICT", 409)
            team_ref = {
                "teamId": team.team_id,
                "revisionId": team.revision_id,
                "digest": team.content_digest,
            }
            if call.operation == "LIST_FIXED_WORK_DRAFTS":
                can_save = (
                    "SAVE" in permit.operations
                    and call.authority.current_action_grants(
                        (
                            ExactGrant(
                                "TEAM", "REVISE", f"team:{permit.teamId}:aggregate"
                            ),
                        )
                    )
                    == (True,)
                )
                if self.cursors is None:
                    raise WorkbenchOwnerError("FIXED_WORK_DIRECTORY_UNAVAILABLE", 503)
                route = "FIXED_WORK:" + digest(
                    {
                        "subject": context.principal_id,
                        "team": team_ref,
                        "policy": policy.model_dump(mode="json"),
                    }
                )
                size = call.query["pageSize"]
                after = ""
                if call.query.get("cursor"):
                    after = self.cursors.resolve(
                        call.query["cursor"],
                        route=route,
                        context=context,
                        page_size=size,
                        key_size=1,
                    )[0]
                rows = c.execute(
                    "SELECT work_id,head_revision_id FROM fixed_work_authoring.heads "
                    "WHERE namespace=%s AND security_domain=%s AND team_id=%s "
                    "AND team_revision_id=%s AND team_digest=%s "
                    'AND work_id COLLATE "C">%s ORDER BY work_id COLLATE "C" LIMIT %s',
                    (
                        *scope,
                        permit.teamId,
                        permit.teamRevisionId,
                        permit.teamDigest,
                        after,
                        size + 1,
                    ),
                ).fetchall()
                items = []
                for row in rows[:size]:
                    value = store.read(
                        c, scope, row["work_id"], row["head_revision_id"]
                    )
                    items.append({"draft": value["record"], "digest": value["digest"]})
                return {
                    "items": items,
                    "team": team_ref,
                    "nextCursor": self.cursors.mint(
                        route=route,
                        context=context,
                        page_size=size,
                        last_key=(rows[size - 1]["work_id"],),
                    )
                    if len(rows) > size
                    else None,
                    "configurationCanSave": can_save,
                    "executionEnabled": False,
                    "authorityGranted": False,
                    "triggerCreated": False,
                }
            if write:
                data = SaveDraft.model_validate(call.payload)
                row, version = store.save(
                    c,
                    scope,
                    context.principal_id,
                    data,
                    team_ref,
                    digest(policy.model_dump(mode="json")),
                    decisions[-1].decision_id,
                    self.clock(),
                )
            else:
                row = store.read(
                    c, scope, call.path["work_id"], call.path["revision_id"]
                )
                version = row["record"]["aggregateVersion"]
            if (row["team_id"], row["team_revision_id"], row["team_digest"]) != (
                permit.teamId,
                permit.teamRevisionId,
                permit.teamDigest,
            ):
                raise WorkbenchOwnerError("FIXED_WORK_DRAFT_NOT_FOUND", 404)
            return {
                "draft": row["record"],
                "digest": row["digest"],
                "aggregateVersion": version,
                "executionEnabled": False,
                "authorityGranted": False,
                "triggerCreated": False,
                "validation": "CONFIGURATION_STRUCTURE_ONLY",
            }
        except TeamDefinitionError as exc:
            raise WorkbenchOwnerError("FIXED_WORK_TEAM_NOT_FOUND", 404) from exc
        except UniqueViolation as exc:
            raise WorkbenchOwnerError("FIXED_WORK_REVISION_CONFLICT", 409) from exc
        except PostgresError as exc:
            raise WorkbenchOwnerError("FIXED_WORK_STORAGE_UNAVAILABLE", 503) from exc


def fixed_work_operations(policy_path, clock, cursors=None):
    owner = FixedWorkAuthoringOwner(policy_path, clock, cursors)
    path = PREFIX + "/teams/{team_id}/revisions/{team_revision_id}/fixed-work-drafts"
    return (
        WorkbenchOperation(
            "LIST_FIXED_WORK_DRAFTS",
            "GET",
            path,
            None,
            FixedWorkPageQuery,
            grants,
            owner,
        ),
        WorkbenchOperation(
            "SAVE_FIXED_WORK_DRAFT",
            "POST",
            path,
            SaveDraft,
            None,
            lambda c, p, v, q: grants(c, p, v, q, write=True),
            owner,
            201,
        ),
        WorkbenchOperation(
            "READ_FIXED_WORK_DRAFT",
            "GET",
            path + "/{work_id}/revisions/{revision_id}",
            None,
            None,
            grants,
            owner,
        ),
    )
