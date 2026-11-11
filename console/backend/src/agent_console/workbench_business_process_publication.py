"""Business publication endpoints; no workflow execution or resource mutation."""

from psycopg import Error as PostgresError
from pydantic import Field

from .authority_contracts import AuthorityError, ExactGrant
from .business_process_authorization import require_process_grant
from .business_process_postgres import BusinessProcessStorageError
from .business_process_publication_postgres import BusinessProcessPublicationRepository
from .execution_domain import ScopeIdentity, record_digest
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_bff_schemas import StrictWorkbenchModel
from .workbench_owner_authorization import WorkbenchOwnerError

ROOT = PREFIX + "/business-processes"
OWNER = "BUSINESS_PROCESS"
COLLECTION = "business-process:collection"


class PublishBusinessProcess(StrictWorkbenchModel):
    objectId: str = Field(min_length=1, max_length=200)
    revisionId: str = Field(min_length=1, max_length=200)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    expectedVersion: int = Field(strict=True, ge=1)
    commandId: str = Field(min_length=1, max_length=200)


def publication_state(call, repository, identity, selected_revision=None):
    scope = ScopeIdentity(
        call.context.scope.tenant_id, call.context.scope.security_domain
    )
    publications = BusinessProcessPublicationRepository(repository.pool)
    call.connection.execute(
        "SELECT pg_advisory_xact_lock_shared(hashtextextended(%s,56))",
        (
            record_digest(
                {"namespace": scope.namespace, "domain": scope.security_domain}
            ),
        ),
    )

    def authorized(revision=None):
        value = repository.read(call.connection, scope, "PROCESS", identity, revision)
        require_process_grant(
            call,
            ExactGrant(
                OWNER,
                "READ",
                f"business-process:PROCESS:{identity}:{value['revisionId']}",
            ),
        )
        return value

    selected = authorized(selected_revision)
    old_publication = call.connection.execute(
        "SELECT result FROM business_process.publications WHERE namespace=%s "
        "AND security_domain=%s AND object_id=%s AND revision_id=%s",
        (scope.namespace, scope.security_domain, identity, selected["revisionId"]),
    ).fetchone()
    try:
        current = authorized()
        published = publications.latest(call.connection, scope, identity)
        if published:
            value = authorized(published["revisionId"])
            if value["digest"] != published["digest"]:
                raise BusinessProcessStorageError("BUSINESS_PROCESS_RECORD_CORRUPT")
    except AuthorityError as error:
        if str(error) != "AUTHORIZATION_NOT_FOUND":
            raise
        # A readable historical version remains readable without exposing current refs.
        return {
            "objectId": identity,
            "published": None,
            "draft": None,
            "currentStateAvailable": False,
            "selectedState": "PUBLISHED_VERSION"
            if old_publication
            else "DRAFT_VERSION",
            "executionAuthorized": False,
        }
    has_draft = published is None or published["revisionId"] != current["revisionId"]
    selected_state = (
        "CURRENT_PUBLISHED"
        if published and selected["revisionId"] == published["revisionId"]
        else "MODIFICATION_DRAFT"
        if has_draft and selected["revisionId"] == current["revisionId"]
        else "HISTORICAL_PUBLISHED"
        if old_publication
        else "HISTORICAL_DRAFT"
    )
    return {
        "objectId": identity,
        "published": published,
        "draft": {
            "revisionId": current["revisionId"],
            "digest": current["digest"],
            "aggregateVersion": current["aggregateVersion"],
        }
        if has_draft
        else None,
        "currentStateAvailable": True,
        "selectedState": selected_state,
        "executionAuthorized": False,
    }


def business_process_publication_operations(repository, references=None):
    publications = BusinessProcessPublicationRepository(repository.pool)

    def read(call, scope, kind, identity, revision_id=None):
        value = repository.read(call.connection, scope, kind, identity, revision_id)
        require_process_grant(
            call,
            ExactGrant(
                OWNER,
                "READ",
                f"business-process:{kind}:{identity}:{value['revisionId']}",
            ),
        )
        return value

    def handle(call):
        scope = ScopeIdentity(
            call.context.scope.tenant_id, call.context.scope.security_domain
        )
        try:
            if call.operation == "READ_BUSINESS_PROCESS_PUBLICATION_RECEIPT":
                return publications.receipt(
                    call.connection,
                    scope,
                    call.path["command_id"],
                    call.context.principal_id,
                )
            if call.operation == "READ_BUSINESS_PROCESS_PUBLICATION_STATE":
                return publication_state(call, repository, call.path["process_id"])
            command = PublishBusinessProcess.model_validate(call.payload)
            value = read(call, scope, "PROCESS", command.objectId, command.revisionId)
            reference = value["record"]["architectureReference"]
            read(call, scope, "ARCHITECTURE", "architecture", reference["revisionId"])
            decision = require_process_grant(
                call, ExactGrant(OWNER, "PUBLISH", COLLECTION)
            )
            return publications.publish(
                call.connection,
                scope,
                command.objectId,
                revision_id=command.revisionId,
                revision_digest=command.digest,
                expected_version=command.expectedVersion,
                command_id=command.commandId,
                actor_id=call.context.principal_id,
                decision_id=decision.decision_id,
                validate_references=(
                    lambda content: references.validate(
                        call, content, require_published=True
                    )
                )
                if references is not None
                else None,
            )
        except AuthorityError as error:
            raise WorkbenchOwnerError("BUSINESS_PROCESS_NOT_FOUND", 404) from error
        except BusinessProcessStorageError as error:
            reason = str(error)
            status = (
                404
                if reason.endswith("NOT_FOUND")
                else 409
                if reason.endswith("CONFLICT")
                else 422
            )
            if reason.endswith("CORRUPT") or reason.endswith("INCOMPATIBLE"):
                status = 503
            raise WorkbenchOwnerError(reason, status) from error
        except PostgresError as error:
            raise WorkbenchOwnerError("BUSINESS_PROCESS_UNAVAILABLE", 503) from error

    def publish_grants(*_):
        return (ExactGrant(OWNER, "PUBLISH", COLLECTION),)

    def list_grants(*_):
        return (ExactGrant(OWNER, "LIST", COLLECTION),)

    return (
        WorkbenchOperation(
            "PUBLISH_BUSINESS_PROCESS",
            "POST",
            ROOT + "/publications",
            PublishBusinessProcess,
            None,
            publish_grants,
            handle,
        ),
        WorkbenchOperation(
            "READ_BUSINESS_PROCESS_PUBLICATION_RECEIPT",
            "GET",
            ROOT + "/publications/{command_id}",
            None,
            None,
            publish_grants,
            handle,
        ),
        WorkbenchOperation(
            "READ_BUSINESS_PROCESS_PUBLICATION_STATE",
            "GET",
            ROOT + "/{process_id}/publication-state",
            None,
            None,
            list_grants,
            handle,
        ),
    )
