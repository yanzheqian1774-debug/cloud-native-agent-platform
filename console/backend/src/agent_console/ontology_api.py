"""Session/CSRF/exact-grant protected BFF operations; no identity headers."""

from .authority_contracts import AuthorityError, ExactGrant
from .execution_preparation import ExecutionPreparationError
from .ontology_domain import OntologyCommand, OntologyError
from .ontology_service import OntologyService, resource
from .plan_suggestion_domain import PlanningError
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_owner_authorization import WorkbenchOwnerError


def operations(planning=None):
    result = []
    path = PREFIX + "/business-ontologies/{identity}"
    if planning is not None:
        from .ontology_planning import OntologyDraftCommand, prepare

        def draft_grants(context, path, payload, query):
            binding = payload["draft"]["business_semantics"]["ontology"]
            return (
                ExactGrant(
                    "BUSINESS_ONTOLOGY",
                    "USE",
                    resource(path["identity"], binding["revision_id"]),
                ),
            )

        def draft(call):
            try:
                return prepare(call, planning)
            except (OntologyError, PlanningError, ValueError) as exc:
                raise WorkbenchOwnerError(str(exc), 409) from exc

        result.append(
            WorkbenchOperation(
                "PREPARE_ONTOLOGY_EXECUTION_DRAFT",
                "POST",
                path + "/execution-drafts",
                OntologyDraftCommand,
                None,
                draft_grants,
                draft,
            )
        )

    def list_grants(context, path, payload, query):
        return (
            ExactGrant("BUSINESS_ONTOLOGY", "LIST", "business-ontology:collection"),
        )

    def directory(call):
        service = OntologyService(call)
        rows = call.connection.execute(
            "SELECT r.ontology_id,r.revision_id,r.digest,r.content->>'name' A"
            "S name,d.version,COALESCE((SELECT f.action FROM "
            "business_ontology.lifecycle_facts f WHERE f.namespace=r.namespace "
            "AND f.security_domain=r.security_domain AND f.ontology_id=r.ontology_id "
            "AND f.revision_id=r.revision_id ORDER BY f.ordinal DESC LIMIT 1),"
            "'DRAFT') AS state "
            "FROM business_ontology.revisions r JOIN business_ontology.definitions d "
            "USING(namespace,security_domain,ontology_id) "
            "WHERE r.namespace=%s AND r.security_domain=%s ORDER BY r.ontolog"
            "y_id,r.revision_id LIMIT 200",
            service.scope,
        ).fetchall()
        visible = []
        for row in rows:
            try:
                call.authority.require(
                    service.principal,
                    "BUSINESS_ONTOLOGY",
                    "READ",
                    resource(row["ontology_id"], row["revision_id"]),
                )
            except AuthorityError:
                continue
            visible.append(row)
        return {"items": visible, "limitations": ["BOUNDED_200_ROWS"]}

    result.append(
        WorkbenchOperation(
            "LIST_BUSINESS_ONTOLOGY",
            "GET",
            PREFIX + "/business-ontologies",
            None,
            None,
            list_grants,
            directory,
        )
    )

    def runs(call):
        service = OntologyService(call)
        present = call.connection.execute(
            "SELECT to_regclass('execution_authority.prepared_candidates') AS name"
        ).fetchone()
        if not present["name"]:
            return {"items": []}
        rows = call.connection.execute(
            "SELECT digest,plan_id,plan_version,record FROM "
            "execution_authority.prepared_candidates "
            "WHERE namespace=%s AND security_domain=%s "
            "AND record->'business_semantics'->'ontology'->>'resource_id'=%s "
            "AND record->'business_semantics'->'ontology'->>'revision_id'=%s "
            "ORDER BY digest LIMIT 100",
            (*service.scope, call.path["identity"], call.path["revision"]),
        ).fetchall()
        visible = []
        for row in rows:
            try:
                call.authority.require(
                    service.principal, "PLAN", "READ", "plan:v2:" + row["plan_id"]
                )
                call.authority.require(
                    service.principal,
                    "EXECUTION",
                    "READ",
                    "governed-execution:prepared:" + row["digest"],
                )
            except AuthorityError:
                continue
            visible.append(
                {
                    "digest": row["digest"],
                    "plan_id": row["plan_id"],
                    "plan_version": row["plan_version"],
                }
            )
        return {"items": visible}

    def read_grants(context, path, payload, query):
        return (
            ExactGrant(
                "BUSINESS_ONTOLOGY",
                "READ",
                resource(path["identity"], path["revision"]),
            ),
        )

    def read(call):
        try:
            service = OntologyService(call)
            return service.repo.read(
                service.scope, call.path["identity"], call.path["revision"]
            )
        except OntologyError as exc:
            raise WorkbenchOwnerError(str(exc), 404) from exc

    result.append(
        WorkbenchOperation(
            "READ_BUSINESS_ONTOLOGY",
            "GET",
            path + "/revisions/{revision}",
            None,
            None,
            read_grants,
            read,
        )
    )
    result.append(
        WorkbenchOperation(
            "READ_ONTOLOGY_RUNS",
            "GET",
            path + "/revisions/{revision}/sales-runs",
            None,
            None,
            read_grants,
            runs,
        )
    )
    for action in (
        "CREATE",
        "REVISE",
        "VALIDATE",
        "TEST",
        "REVIEW",
        "PUBLISH",
        "DEPRECATE",
    ):

        def grants(context, path, payload, query, action=action):
            return (
                ExactGrant(
                    "BUSINESS_ONTOLOGY",
                    action,
                    resource(path["identity"], payload["revision_id"]),
                ),
            )

        def handle(call, action=action):
            try:
                return OntologyService(call).handle(
                    action, call.path["identity"], call.payload
                )
            except (OntologyError, ExecutionPreparationError) as exc:
                raise WorkbenchOwnerError(str(exc), 409) from exc

        result.append(
            WorkbenchOperation(
                "ONTOLOGY_" + action,
                "POST",
                path + "/" + action.lower(),
                OntologyCommand,
                None,
                grants,
                handle,
            )
        )
    return tuple(result)
