"""Private team definitions over existing trusted session/authorization UoW."""

from dataclasses import dataclass

from psycopg import Error as PostgresError
from pydantic import Field

from .authority_contracts import AuthorityError, ExactGrant
from .digital_employee_definition import EmployeeDefinitionError
from .execution_domain import ScopeIdentity
from .team_definition import (
    TeamDefinitionError,
    TeamMember,
    TeamRevision,
    TeamWorkReference,
)
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_bff_schemas import StrictWorkbenchModel, WorkbenchPageQuery
from .workbench_owner_authorization import WorkbenchOwnerError
from .workbench_team_people import candidates, validate_owner
from .workbench_team_work import project_team_work, validate_work_links


class TeamMemberInput(StrictWorkbenchModel):
    employeeDefinitionId: str = Field(min_length=1, max_length=200)
    employeeRevisionId: str = Field(min_length=1, max_length=200)
    employeeDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    responsibility: str = Field(min_length=1, max_length=1000)
    handoff: str = Field(default="", max_length=1000)


class TeamWorkInput(StrictWorkbenchModel):
    workflowRunId: str = Field(min_length=1, max_length=200)
    preparationDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    problemId: str = Field(min_length=1, max_length=200)
    problemRevisionId: str = Field(min_length=1, max_length=200)
    problemDigest: str = Field(pattern=r"^[a-f0-9]{64}$")


class SaveTeamInput(StrictWorkbenchModel):
    teamId: str = Field(min_length=1, max_length=200)
    revisionId: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=120)
    goal: str = Field(min_length=1, max_length=2000)
    ownerId: str = Field(min_length=1, max_length=200)
    members: tuple[TeamMemberInput, ...] = Field(min_length=1, max_length=32)
    predecessorRevisionId: str | None = Field(default=None, max_length=200)
    workLinks: tuple[TeamWorkInput, ...] | None = Field(default=None, max_length=32)
    expectedVersion: int = Field(strict=True, ge=0)
    commandId: str = Field(min_length=1, max_length=200)


@dataclass(frozen=True)
class _Principal:
    principal_id: str
    tenant_id: str
    security_domain: str


def save_grants(context, path, payload, query):
    if payload.get("predecessorRevisionId") is None:
        return (ExactGrant("TEAM", "CREATE", "team:collection"),)
    return (ExactGrant("TEAM", "REVISE", f"team:{payload['teamId']}:aggregate"),)


class TeamTargets:
    def is_known_exact_target(self, context, grant, *, connection=None):
        if grant.owner != "TEAM" or connection is None:
            return False
        if grant.action in {"CREATE", "LIST"}:
            return grant.exact_resource == "team:collection"
        if grant.action not in {"READ", "REVISE"}:
            return False
        table, expression = (
            ("revisions", "'team:' || team_id || ':' || revision_id")
            if grant.action == "READ"
            else ("definitions", "'team:' || team_id || ':aggregate'")
        )
        try:
            return (
                connection.execute(
                    f"SELECT 1 FROM team_definition.{table} WHERE namespace=%s "
                    f"AND security_domain=%s AND {expression}=%s FOR SHARE",
                    (
                        context.scope.tenant_id,
                        context.scope.security_domain,
                        grant.exact_resource,
                    ),
                ).fetchone()
                is not None
            )
        except PostgresError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc


class TeamOwner:
    def __init__(self, repository, employees, cursors):
        self.repository, self.employees, self.cursors = repository, employees, cursors

    @staticmethod
    def _actions(call, value, head):
        from .workbench_management_actions import projection

        return projection(
            call,
            {
                "REVISE": (
                    ExactGrant("TEAM", "REVISE", f"team:{value.team_id}:aggregate"),
                    value.revision_id == head["head_revision_id"],
                ),
                "SELECT_OWNER": (ExactGrant("TEAM", "CREATE", "team:collection"), True),
            },
            target={
                "teamId": value.team_id,
                "revisionId": value.revision_id,
                "digest": value.content_digest,
                "aggregateVersion": head["aggregate_version"],
            },
        )

    def __call__(self, call):
        scope = ScopeIdentity(
            call.context.scope.tenant_id, call.context.scope.security_domain
        )
        principal = _Principal(
            call.context.principal_id, scope.namespace, scope.security_domain
        )
        try:
            if call.operation == "READ_TEAM_CAPABILITIES":
                from .workbench_management_actions import collection_projection

                return collection_projection(call, "TEAM")
            if call.operation == "SAVE_TEAM_REVISION":
                data = SaveTeamInput.model_validate(call.payload)
                revision = TeamRevision(
                    scope,
                    data.teamId,
                    data.revisionId,
                    data.title,
                    data.goal,
                    data.ownerId,
                    tuple(
                        TeamMember(
                            m.employeeDefinitionId,
                            m.employeeRevisionId,
                            m.employeeDigest,
                            m.responsibility,
                            m.handoff,
                        )
                        for m in data.members
                    ),
                    data.predecessorRevisionId,
                    tuple(
                        TeamWorkReference(
                            link.workflowRunId,
                            link.preparationDigest,
                            link.problemId,
                            link.problemRevisionId,
                            link.problemDigest,
                        )
                        for link in data.workLinks
                    )
                    if data.workLinks is not None
                    else None,
                )
                grant = save_grants(call.context, call.path, call.payload, call.query)[
                    0
                ]
                decision = call.authority.require(
                    principal, grant.owner, grant.action, grant.exact_resource
                )
                # Recheck every exact employee before even an idempotent replay.
                for member in revision.members:
                    call.authority.require(
                        principal,
                        "EMPLOYEE",
                        "READ",
                        f"employee:{member.employee_definition_id}:{member.employee_revision_id}",
                    )
                    value = self.employees.read_revision_for_workbench(
                        call.connection,
                        scope,
                        member.employee_definition_id,
                        member.employee_revision_id,
                        authorized=True,
                    )
                    if value["digest"] != member.employee_digest:
                        raise TeamDefinitionError("TEAM_MEMBER_VERSION_MISMATCH")
                previous = (
                    self.repository.read(
                        call.connection, scope, data.teamId, data.predecessorRevisionId
                    )
                    if data.predecessorRevisionId is not None
                    else None
                )
                validate_owner(
                    call, data.ownerId, previous.owner_id if previous else None
                )
                validate_work_links(call, principal, revision.work_links)
                result = self.repository.save(
                    call.connection,
                    revision,
                    expected_version=data.expectedVersion,
                    command_id=data.commandId,
                    actor_id=call.context.principal_id,
                    decision_id=decision.decision_id,
                )
                return {
                    **result,
                    "teamId": revision.team_id,
                    "digest": revision.content_digest,
                }
            if call.operation == "READ_TEAM_WORK":
                revision = self.repository.read(
                    call.connection,
                    scope,
                    call.path["team_id"],
                    call.path["revision_id"],
                )
                return {
                    "teamId": revision.team_id,
                    "revisionId": revision.revision_id,
                    "teamDigest": revision.content_digest,
                    **project_team_work(call, revision),
                }
            if call.operation == "READ_TEAM_REVISION":
                head = call.connection.execute(
                    "SELECT head_revision_id,aggregate_version "
                    "FROM team_definition.definitions WHERE namespace=%s "
                    "AND security_domain=%s AND team_id=%s FOR SHARE",
                    (scope.namespace, scope.security_domain, call.path["team_id"]),
                ).fetchone()
                if head is None:
                    raise TeamDefinitionError("TEAM_NOT_FOUND")
                value = self.repository.read(
                    call.connection,
                    scope,
                    call.path["team_id"],
                    call.path["revision_id"],
                )
                return {
                    "revision": value.canonical_record(),
                    "digest": value.content_digest,
                    "aggregateVersion": head["aggregate_version"],
                    "headRevisionId": head["head_revision_id"],
                    "maintenanceActions": self._actions(call, value, head),
                }
            if call.operation == "LIST_TEAM_OWNER_CANDIDATES":
                return {"items": candidates(call), "authorityGranted": False}
            if call.operation == "LIST_TEAMS":
                return self._list(call, scope)
            raise WorkbenchOwnerError("WORKBENCH_OPERATION_INVALID", 500)
        except TeamDefinitionError as exc:
            code = str(exc)
            status = (
                404
                if code == "TEAM_NOT_FOUND"
                else 503
                if code == "TEAM_RECORD_CORRUPT"
                else 409
                if code
                in {
                    "TEAM_VERSION_CONFLICT",
                    "TEAM_COMMAND_CONFLICT",
                    "TEAM_REVISION_EXISTS",
                    "TEAM_MEMBER_VERSION_MISMATCH",
                }
                else 422
            )
            raise WorkbenchOwnerError(code, status) from exc
        except EmployeeDefinitionError as exc:
            raise WorkbenchOwnerError("TEAM_MEMBER_UNAVAILABLE", 409) from exc
        except PostgresError as exc:
            raise WorkbenchOwnerError("TEAM_STORAGE_UNAVAILABLE", 503) from exc

    def _list(self, call, scope):
        size = call.query["pageSize"]
        after = ""
        if call.query.get("cursor"):
            after = self.cursors.resolve(
                call.query["cursor"],
                route="TEAM_LIST",
                context=call.context,
                page_size=size,
                key_size=1,
            )[0]
        rows = call.connection.execute(
            "SELECT team_id,head_revision_id,aggregate_version "
            "FROM team_definition.definitions "
            'WHERE namespace=%s AND security_domain=%s AND team_id COLLATE "C">%s '
            'ORDER BY team_id COLLATE "C" LIMIT %s',
            (scope.namespace, scope.security_domain, after, size + 1),
        ).fetchall()
        items = []
        for row in rows[:size]:
            revision = self.repository.read(
                call.connection, scope, row["team_id"], row["head_revision_id"]
            )
            # Collection grant exposes summaries, not member duties or employee content.
            items.append(
                {
                    "teamId": revision.team_id,
                    "revisionId": revision.revision_id,
                    "title": revision.title,
                    "ownerId": revision.owner_id,
                    "memberCount": len(revision.members),
                    "digest": revision.content_digest,
                    "aggregateVersion": row["aggregate_version"],
                }
            )
        return {
            "items": items,
            "nextCursor": self.cursors.mint(
                route="TEAM_LIST",
                context=call.context,
                page_size=size,
                last_key=(rows[size - 1]["team_id"],),
            )
            if len(rows) > size
            else None,
        }


def team_operations(repository, employees, cursors):
    handler = TeamOwner(repository, employees, cursors)
    return (
        WorkbenchOperation(
            "READ_TEAM_CAPABILITIES",
            "GET",
            PREFIX + "/teams/capabilities",
            None,
            None,
            lambda *_: (),
            handler,
        ),
        WorkbenchOperation(
            "LIST_TEAM_OWNER_CANDIDATES",
            "GET",
            PREFIX + "/teams/owner-candidates",
            None,
            None,
            lambda *_: (ExactGrant("TEAM", "CREATE", "team:collection"),),
            handler,
        ),
        WorkbenchOperation(
            "LIST_TEAMS",
            "GET",
            PREFIX + "/teams",
            None,
            WorkbenchPageQuery,
            lambda *_: (ExactGrant("TEAM", "LIST", "team:collection"),),
            handler,
        ),
        WorkbenchOperation(
            "SAVE_TEAM_REVISION",
            "POST",
            PREFIX + "/teams",
            SaveTeamInput,
            None,
            save_grants,
            handler,
            201,
        ),
        WorkbenchOperation(
            "READ_TEAM_WORK",
            "GET",
            PREFIX + "/teams/{team_id}/revisions/{revision_id}/work",
            None,
            None,
            lambda _c, p, _v, _q: (
                ExactGrant("TEAM", "READ", f"team:{p['team_id']}:{p['revision_id']}"),
            ),
            handler,
        ),
        WorkbenchOperation(
            "READ_TEAM_REVISION",
            "GET",
            PREFIX + "/teams/{team_id}/revisions/{revision_id}",
            None,
            None,
            lambda _c, p, _v, _q: (
                ExactGrant("TEAM", "READ", f"team:{p['team_id']}:{p['revision_id']}"),
            ),
            handler,
        ),
    )
