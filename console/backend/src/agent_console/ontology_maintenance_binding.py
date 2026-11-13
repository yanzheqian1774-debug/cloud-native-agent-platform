# ruff: noqa: E501 -- Exact scoped SQL and immutable admission facts.
"""Owner-side managed-command binding, including old HTTP routes and replay."""

from datetime import UTC, datetime

from .ontology_domain import OntologyError
from .resource_use_domain import canonical_digest

SCHEMA = "ontology-maintenance-admission.v1"
PREFIX = "ontology-maintenance:"
REQUEST_PREFIX = "ontology-managed:"
REVISION_PREFIX = "managed-"


def command_key(key):
    return PREFIX + canonical_digest(key)


def verify_managed_command(call, identity, action, command):
    managed_request = command.request_key.startswith(REQUEST_PREFIX)
    if not managed_request and action not in {"CREATE", "REVISE"}:
        return
    c = call.connection
    exists = c.execute(
        "SELECT to_regclass('execution_authority.prepared_resource_commands') AS name"
    ).fetchone()
    if not exists or not exists["name"]:
        return
    scope = (call.context.scope.tenant_id, call.context.scope.security_domain)
    if managed_request:
        row = c.execute(
            "SELECT result FROM execution_authority.prepared_resource_commands WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND command_key=%s",
            (
                *scope,
                call.context.principal_id,
                PREFIX + command.request_key.removeprefix(REQUEST_PREFIX),
            ),
        ).fetchone()
    if not managed_request or row is None:
        if action not in {"CREATE", "REVISE"}:
            return
        # Look up the actual immutable admission, not a reserved revision name.
        # This protects managed grants with a substituted request key without
        # changing the legacy contract's unrestricted revision identifier field.
        row = c.execute(
            "SELECT result FROM execution_authority.prepared_resource_commands WHERE namespace=%s AND security_domain=%s AND result->>'schemaVersion'=%s AND result->>'ontologyId'=%s AND result->'ownerCommand'->>'revision_id'=%s AND result->>'action' IN ('CREATE','REVISE') LIMIT 1",
            (*scope, SCHEMA, identity, command.revision_id),
        ).fetchone()
        if row is None:
            return
    record = row["result"] if row else None
    if (
        not record
        or record.get("schemaVersion") != SCHEMA
        or (
            record.get("ontologyId") != identity
            or record.get("action") != action
            or record.get("actor") != call.context.principal_id
            or record.get("scope") != list(scope)
            or record.get("ownerCommand") != command.model_dump(mode="json")
        )
    ):
        raise OntologyError("ONTOLOGY_MANAGEMENT_BINDING_MISMATCH")
    if record.get("generation") != call.policy_generation:
        raise OntologyError("ONTOLOGY_MANAGEMENT_GENERATION_CHANGED")
    # DB current time, not client time; current grant is independently required
    # by the owner before this check and includes revocation/recovery epoch.
    now = c.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
    expiry = datetime.fromisoformat(record["expiresAt"])
    if expiry.tzinfo is None or expiry <= now.astimezone(UTC):
        raise OntologyError("ONTOLOGY_MANAGEMENT_EXPIRED")
