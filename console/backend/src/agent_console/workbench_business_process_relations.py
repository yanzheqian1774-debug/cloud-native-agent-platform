"""Fixed process/capability association commands and exact bidirectional reads."""

import json
from typing import Literal

from psycopg import Error as PostgresError
from pydantic import Field

from .authority_contracts import AuthorityError, ExactGrant
from .business_capability import BusinessCapabilityError
from .business_capability_postgres import PostgresBusinessCapabilityRepository
from .business_process_authorization import require_process_grant
from .business_process_definition import (
    BusinessCapabilityRelation,
    FixedBusinessReference,
)
from .business_process_postgres import BusinessProcessStorageError
from .business_process_relation_withdrawals import BusinessRelationWithdrawalRepository
from .business_process_relations_postgres import BusinessProcessRelationRepository
from .execution_domain import ScopeIdentity
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_bff_schemas import StrictWorkbenchModel
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError

ROOT = PREFIX + "/business-processes/capability-relations"
COLLECTION = ExactGrant("BUSINESS_PROCESS", "LIST", "business-process:collection")


class SaveRelation(StrictWorkbenchModel):
    relation: BusinessCapabilityRelation
    expectedVersion: int = Field(strict=True, ge=0)
    commandId: str = Field(min_length=1, max_length=200)


class WithdrawRelation(StrictWorkbenchModel):
    relationId: str = Field(min_length=1, max_length=200)
    relationRevisionId: str = Field(min_length=1, max_length=200)
    expectedVersion: int = Field(strict=True, ge=1)
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    reason: str = Field(min_length=1, max_length=2000)
    commandId: str = Field(min_length=1, max_length=200)


class ListRelations(StrictWorkbenchModel):
    side: Literal["PROCESS", "CAPABILITY"]
    identity: str = Field(min_length=1, max_length=200)
    revision: str = Field(min_length=1, max_length=200)
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    pageSize: int = Field(default=25, ge=1, le=50)
    cursor: str = Field(default="", max_length=2048)


def business_process_relation_operations(repository, cursors):
    def scope(call):
        return ScopeIdentity(
            call.context.scope.tenant_id, call.context.scope.security_domain
        )

    def capability_grant(call, action, resource):
        return call.authority.require(
            OwnerPrincipal(
                call.context.principal_id,
                call.context.scope.tenant_id,
                call.context.scope.security_domain,
            ),
            "BUSINESS_CAPABILITY",
            action,
            resource,
        )

    def exact(call, side, reference):
        if side == "PROCESS":
            require_process_grant(
                call,
                ExactGrant(
                    "BUSINESS_PROCESS",
                    "READ",
                    f"business-process:PROCESS:{reference.resource_id}:{reference.revision_id}",
                ),
            )
            value = repository.read(
                call.connection,
                scope(call),
                "PROCESS",
                reference.resource_id,
                reference.revision_id,
            )
            actual_digest = value["digest"]
        else:
            capability_grant(
                call,
                "READ",
                f"business-capability:{reference.resource_id}:{reference.revision_id}",
            )
            value = PostgresBusinessCapabilityRepository.read(
                call.connection,
                scope(call),
                reference.resource_id,
                reference.revision_id,
            )
            actual_digest = value.content_digest
        if actual_digest != reference.digest:
            raise BusinessProcessStorageError("BUSINESS_RELATION_REFERENCE_MISMATCH")
        return value

    def authorize(call, relation, *, write=False):
        decision = None
        if write:
            decision = require_process_grant(
                call,
                ExactGrant(
                    "BUSINESS_PROCESS",
                    "REVISE",
                    f"business-process:{relation.process.resource_id}:aggregate",
                ),
            )
            if relation.relation_type == "DERIVED_FROM_PROCESS":
                capability_grant(
                    call,
                    "REVISE",
                    f"business-capability:{relation.capability.resource_id}:aggregate",
                )
        process = exact(call, "PROCESS", relation.process)
        capability = exact(call, "CAPABILITY", relation.capability)
        return decision, process, capability

    def projected(call, row, *, write=False):
        value = BusinessProcessRelationRepository.decode(row)
        relation = BusinessCapabilityRelation.model_validate(value["record"])
        _, process, capability = authorize(call, relation, write=write)
        value.update(
            processName=process["record"]["content"]["name"],
            capabilityTitle=capability.title,
            activities=[
                {"activityId": item["activity_id"], "name": item["name"]}
                for item in process["record"]["content"]["activities"]
                if item["activity_id"] in relation.activity_ids
            ],
        )
        latest = call.connection.execute(
            "SELECT relation_revision_id FROM business_process.capability_relations "
            "WHERE namespace=%s AND security_domain=%s AND relation_id=%s "
            "ORDER BY relation_version DESC LIMIT 1",
            (scope(call).namespace, scope(call).security_domain, relation.relation_id),
        ).fetchone()
        value["isCurrentRelationRevision"] = (
            latest["relation_revision_id"] == relation.relation_revision_id
        )
        value["withdrawal"] = BusinessRelationWithdrawalRepository.state(
            call.connection, scope(call), relation.relation_id
        )
        return value

    def handle(call):
        current_scope = scope(call)
        key = (current_scope.namespace, current_scope.security_domain)
        try:
            if call.operation in {
                "WITHDRAW_BUSINESS_RELATION",
                "READ_BUSINESS_RELATION_WITHDRAWAL_RECEIPT",
            }:
                if call.operation == "WITHDRAW_BUSINESS_RELATION":
                    command = WithdrawRelation.model_validate(call.payload)
                    relation_id, revision_id = (
                        command.relationId,
                        command.relationRevisionId,
                    )
                    receipt = None
                else:
                    receipt = call.connection.execute(
                        "SELECT * FROM "
                        "business_process.relation_withdrawals WHERE "
                        "namespace=%s AND security_domain=%s AND "
                        "command_id=%s AND actor_id=%s",
                        (*key, call.path["command_id"], call.context.principal_id),
                    ).fetchone()
                    if not receipt:
                        raise WorkbenchOwnerError(
                            "BUSINESS_RELATION_WITHDRAWAL_NOT_FOUND", 404
                        )
                    relation_id, revision_id = (
                        receipt["relation_id"],
                        receipt["relation_revision_id"],
                    )
                row = call.connection.execute(
                    "SELECT * FROM business_process.capability_relations "
                    "WHERE namespace=%s AND security_domain=%s AND "
                    "relation_id=%s AND relation_revision_id=%s",
                    (*key, relation_id, revision_id),
                ).fetchone()
                if not row:
                    raise WorkbenchOwnerError("BUSINESS_RELATION_NOT_FOUND", 404)
                relation = BusinessCapabilityRelation.model_validate(
                    BusinessProcessRelationRepository.decode(row)["record"]
                )
                decision, _, _ = authorize(call, relation, write=True)
                if receipt:
                    return receipt["result"]
                return BusinessRelationWithdrawalRepository.withdraw(
                    call.connection,
                    current_scope,
                    command.model_dump(mode="json"),
                    actor_id=call.context.principal_id,
                    decision_id=decision.decision_id,
                )
            if call.operation == "SAVE_BUSINESS_CAPABILITY_RELATION":
                command = SaveRelation.model_validate(call.payload)
                decision, _, _ = authorize(call, command.relation, write=True)
                return BusinessProcessRelationRepository.save(
                    call.connection,
                    current_scope,
                    command.relation,
                    expected_version=command.expectedVersion,
                    command_id=command.commandId,
                    actor_id=call.context.principal_id,
                    decision_id=decision.decision_id,
                )
            if call.operation in {
                "READ_BUSINESS_RELATION",
                "READ_BUSINESS_RELATION_RECEIPT",
            }:
                receipt = call.operation == "READ_BUSINESS_RELATION_RECEIPT"
                clause = (
                    "command_id=%s AND actor_id=%s"
                    if receipt
                    else "relation_id=%s AND relation_revision_id=%s"
                )
                args = (
                    (call.path["command_id"], call.context.principal_id)
                    if receipt
                    else (call.path["relation_id"], call.path["relation_revision_id"])
                )
                row = call.connection.execute(
                    "SELECT * FROM business_process.capability_relations "
                    "WHERE namespace=%s AND security_domain=%s AND " + clause,
                    (*key, *args),
                ).fetchone()
                if not row:
                    raise WorkbenchOwnerError("BUSINESS_RELATION_NOT_FOUND", 404)
                return projected(call, row, write=receipt)
            query = ListRelations.model_validate(call.query)
            exact(
                call,
                query.side,
                FixedBusinessReference(
                    resource_id=query.identity,
                    revision_id=query.revision,
                    digest=query.digest,
                ),
            )
            route = json.dumps(
                [ROOT, query.side, query.identity, query.revision, query.digest]
            )
            after = (
                cursors.resolve(
                    query.cursor,
                    route=route,
                    context=call.context,
                    page_size=query.pageSize,
                    key_size=2,
                )
                if query.cursor
                else None
            )
            prefix = "process" if query.side == "PROCESS" else "capability"
            parameters = [*key, query.identity, query.revision]
            extra = ""
            if after:
                extra = 'AND (relation_id COLLATE "C",relation_version) > (%s,%s) '
                parameters.extend((after[0], int(after[1])))
            parameters.append(query.pageSize + 1)
            rows = call.connection.execute(
                "SELECT * FROM business_process.capability_relations "
                "WHERE namespace=%s AND security_domain=%s "
                f"AND {prefix}_id=%s AND {prefix}_revision_id=%s "
                + extra
                + 'ORDER BY relation_id COLLATE "C",relation_version LIMIT %s',
                tuple(parameters),
            ).fetchall()
            items = []
            for row in rows[: query.pageSize]:
                try:
                    items.append(projected(call, row))
                except AuthorityError as error:
                    if str(error) != "AUTHORIZATION_NOT_FOUND":
                        raise
            cursor = None
            if len(rows) > query.pageSize:
                last = rows[query.pageSize - 1]
                cursor = cursors.mint(
                    route=route,
                    context=call.context,
                    page_size=query.pageSize,
                    last_key=(last["relation_id"], str(last["relation_version"])),
                )
            return {"items": items, "nextCursor": cursor, "executionAuthorized": False}
        except AuthorityError as error:
            raise WorkbenchOwnerError("BUSINESS_RELATION_NOT_FOUND", 404) from error
        except (BusinessProcessStorageError, BusinessCapabilityError) as error:
            reason = str(error)
            status = (
                503
                if reason.endswith(("CORRUPT", "INCOMPATIBLE"))
                else 404
                if reason.endswith("NOT_FOUND")
                else 409
                if reason.endswith("CONFLICT")
                else 422
            )
            raise WorkbenchOwnerError(reason, status) from error
        except PostgresError as error:
            raise WorkbenchOwnerError("BUSINESS_RELATION_UNAVAILABLE", 503) from error

    def list_grants(context, path, payload, query):
        value = ListRelations.model_validate(query)
        if value.side == "PROCESS":
            return (COLLECTION,)
        return (
            ExactGrant(
                "BUSINESS_CAPABILITY",
                "READ",
                f"business-capability:{value.identity}:{value.revision}",
            ),
        )

    def collection(*_):
        return (COLLECTION,)

    return (
        WorkbenchOperation(
            "WITHDRAW_BUSINESS_RELATION",
            "POST",
            ROOT + "/withdrawals",
            WithdrawRelation,
            None,
            collection,
            handle,
        ),
        WorkbenchOperation(
            "READ_BUSINESS_RELATION_WITHDRAWAL_RECEIPT",
            "GET",
            ROOT + "/withdrawals/{command_id}",
            None,
            None,
            collection,
            handle,
        ),
        WorkbenchOperation(
            "SAVE_BUSINESS_CAPABILITY_RELATION",
            "POST",
            ROOT,
            SaveRelation,
            None,
            collection,
            handle,
        ),
        WorkbenchOperation(
            "LIST_BUSINESS_CAPABILITY_RELATIONS",
            "GET",
            ROOT,
            None,
            ListRelations,
            list_grants,
            handle,
        ),
        WorkbenchOperation(
            "READ_BUSINESS_RELATION_RECEIPT",
            "GET",
            ROOT + "/commands/{command_id}",
            None,
            None,
            collection,
            handle,
        ),
        WorkbenchOperation(
            "READ_BUSINESS_RELATION",
            "GET",
            ROOT + "/{relation_id}/{relation_revision_id}",
            None,
            None,
            collection,
            handle,
        ),
    )
