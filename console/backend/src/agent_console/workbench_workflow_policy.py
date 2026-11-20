"""Default-off D12 publication, original authorized UoW and immutable command store."""

from typing import Literal

from psycopg import Error as PostgresError
from psycopg.types.json import Jsonb
from pydantic import Field

from .authority_contracts import ExactGrant
from .development_administrator import for_call
from .resource_policy_contract import DevelopmentAdministratorReview
from .resource_use_domain import canonical_digest
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_bff_schemas import StrictWorkbenchModel
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError
from .workbench_prepared_resources import bind_service
from .workflow_authoring_references import WorkflowReferenceChecker
from .workflow_definition_repository import WorkflowDefinitionRepositoryError
from .workflow_definition_service import WorkflowDefinitionFailure


class PolicyPublicationCommand(StrictWorkbenchModel):
    action: Literal["policy-publish"]
    commandKey: str = Field(min_length=1, max_length=200)
    workflowId: str = Field(min_length=1, max_length=200)
    expectedVersion: int = Field(strict=True, ge=1)
    digest: str = Field(pattern=r"^(?:sha256:)?[a-f0-9]{64}$")


class PolicyReceiptQuery(StrictWorkbenchModel):
    workflowId: str = Field(min_length=1, max_length=200)


def capability(call, enabled):
    return bool(enabled and for_call(call))


class WorkflowPolicyPublication:
    def __init__(self, service, services):
        self.service = service
        self.references = WorkflowReferenceChecker(services)

    def __call__(self, call):
        try:
            return self.handle(call)
        except WorkflowDefinitionFailure as exc:
            raise WorkbenchOwnerError(exc.reason, exc.status) from exc
        except (WorkflowDefinitionRepositoryError, PostgresError) as exc:
            raise WorkbenchOwnerError(
                "WORKFLOW_POLICY_PUBLICATION_UNAVAILABLE", 503
            ) from exc

    def handle(self, call):
        if call.operation not in {
            "PUBLISH_WORKFLOW_POLICY",
            "READ_WORKFLOW_POLICY_PUBLICATION",
        }:
            raise WorkbenchOwnerError("WORKFLOW_POLICY_OPERATION_UNSUPPORTED", 403)
        if not for_call(call):
            raise WorkbenchOwnerError("DEVELOPMENT_ADMINISTRATOR_REQUIRED", 403)
        read = call.operation == "READ_WORKFLOW_POLICY_PUBLICATION"
        command = (
            None if read else PolicyPublicationCommand.model_validate(call.payload)
        )
        identity = call.query["workflowId"] if read else command.workflowId
        key = call.path["command_key"] if read else command.commandKey
        ctx, c = call.context, call.connection
        principal = OwnerPrincipal(
            ctx.principal_id, ctx.scope.tenant_id, ctx.scope.security_domain
        )
        call.authority.require(
            principal, "WORKFLOW", "REVIEW_PUBLISH", "workflow:aggregate:" + identity
        )
        scope_key = (
            ctx.scope.tenant_id,
            ctx.scope.security_domain,
            ctx.principal_id,
            "workflow-policy-publication:" + key,
        )
        c.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (canonical_digest(scope_key),),
        )
        row = c.execute(
            "SELECT digest,result FROM execution_authority.prepared_resource_commands "
            "WHERE namespace=%s AND security_domain=%s "
            "AND actor_id=%s AND command_key=%s",
            scope_key,
        ).fetchone()
        payload_digest = (
            None if read else canonical_digest(command.model_dump(mode="json"))
        )
        if read and row is None:
            raise WorkbenchOwnerError("WORKFLOW_COMMAND_NOT_FOUND", 404)
        if row and (
            row["result"]["workflowId"] != identity
            or (not read and row["digest"] != payload_digest)
        ):
            raise WorkbenchOwnerError("WORKFLOW_COMMAND_CONFLICT", 409)
        service = bind_service(self.service, c)
        scope = service.scope(ctx.scope.tenant_id, ctx.scope.security_domain)
        record = service.repository.get(scope, identity)
        revision_id = (
            row["result"]["revisionId"] if row else record["currentDraftRevisionId"]
        )
        revision = next(
            (r for r in record["revisions"] if r["revisionId"] == revision_id), None
        )
        if revision is None:
            raise WorkbenchOwnerError("WORKFLOW_POLICY_TARGET_CHANGED", 409)
        call.authority.require(
            principal, "WORKFLOW", "READ", f"workflow:{identity}:{revision_id}"
        )
        service.reference_resolver = lambda _, ref: self.references(call, ref, True)
        # Before replay too: a saved publication never restores revoked references.
        service._validate_content(scope, revision["content"], resolve=True)
        if row:
            if (
                revision["state"] != "PUBLISHED"
                or revision["digest"] != row["result"]["digest"]
                or revision.get("publicationBasis") != row["result"]["policyReview"]
            ):
                raise WorkbenchOwnerError("WORKFLOW_POLICY_TARGET_CHANGED", 409)
            return {**row["result"], "replayed": True}
        proof = DevelopmentAdministratorReview(
            ctx.principal_id, call.policy_generation, payload_digest
        )
        reviewed = service.review_policy(
            scope,
            identity,
            ctx.principal_id,
            command.expectedVersion,
            command.digest,
            proof,
        )
        review = reviewed["policyReviews"][-1]
        published = service.publish_policy(
            scope,
            identity,
            ctx.principal_id,
            reviewed["aggregateVersion"],
            command.digest,
            review["reviewId"],
            proof,
        )
        result = {
            "schemaVersion": "workflow-policy-publication-receipt.v1",
            "commandKey": key,
            "action": "policy-publish",
            "workflowId": identity,
            "revisionId": revision_id,
            "digest": command.digest,
            "aggregateVersion": published["aggregateVersion"],
            "policyReview": review,
            "executionAuthorized": False,
            "replayed": False,
        }
        c.execute(
            "INSERT INTO execution_authority.prepared_resource_commands "
            "(namespace,security_domain,actor_id,command_key,digest,result) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (*scope_key, payload_digest, Jsonb(result)),
        )
        return result


def policy_publication_operations(service, services, *, enabled=False):
    if not enabled:
        return ()
    owner = WorkflowPolicyPublication(service, services)

    def grants(_ctx, _path, body, query):
        identity = body.get("workflowId") or query["workflowId"]
        return (
            ExactGrant("WORKFLOW", "REVIEW_PUBLISH", "workflow:aggregate:" + identity),
        )

    return (
        WorkbenchOperation(
            "PUBLISH_WORKFLOW_POLICY",
            "POST",
            PREFIX + "/workflows/policy-publications",
            PolicyPublicationCommand,
            None,
            grants,
            owner,
        ),
        WorkbenchOperation(
            "READ_WORKFLOW_POLICY_PUBLICATION",
            "GET",
            PREFIX + "/workflows/policy-publications/{command_key}",
            None,
            PolicyReceiptQuery,
            grants,
            owner,
        ),
    )
