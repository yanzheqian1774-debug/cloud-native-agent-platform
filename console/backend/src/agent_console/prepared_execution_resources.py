"""Exact current owner readbacks for the bounded synthetic Native execution."""

from .execution_preparation import ExecutionPreparationError
from .resource_use_domain import canonical_digest


def published(connection, scope, kind, ref):
    tables = {
        "SKILL": ("skill_mcp_resource.resources", "resource_id"),
        "KNOWLEDGE": ("knowledge_operation.knowledge", "knowledge_id"),
        "RUNTIME": ("runtime_profile.profiles", "runtime_profile_id"),
    }
    if kind not in tables:
        raise ExecutionPreparationError("PREPARED_RESOURCE_OWNER_NOT_CONFIGURED")
    table, column = tables[kind]
    row = connection.execute(
        f"SELECT record FROM {table} WHERE namespace=%s AND security_domain=%s "
        f"AND {column}=%s"
        + (" AND kind='skill'" if kind == "SKILL" else "")
        + " FOR SHARE",
        (scope.namespace, scope.security_domain, ref.resource_id),
    ).fetchone()
    if row is None:
        raise ExecutionPreparationError("PREPARED_RESOURCE_UNAVAILABLE")
    record = row["record"]
    revision = next(
        (r for r in record.get("revisions", []) if r["revisionId"] == ref.revision_id),
        None,
    )
    if (
        revision is None
        or str(revision.get("digest", "")).removeprefix("sha256:") != ref.digest
        or record.get("publishedRevisionId") != ref.revision_id
        or revision.get("state") != "PUBLISHED"
        or record.get("archived")
        or (kind == "SKILL" and not record.get("enabled"))
    ):
        raise ExecutionPreparationError("PREPARED_RESOURCE_REVISION_UNAVAILABLE")
    return revision["content"]


def validate_resources(connection, scope, preparation, participant):
    skill = published(connection, scope, "SKILL", participant.skill.reference)
    operation = next(
        (
            o
            for o in skill.get("operations", [])
            if o["name"] == participant.skill.operation
        ),
        None,
    )
    if operation is None or (
        operation.get("executorId"),
        operation.get("executorRevision"),
        operation.get("executorConfigurationDigest"),
        canonical_digest(operation.get("inputSchema")),
        canonical_digest(operation.get("outputSchema")),
        operation.get("sideEffectClass"),
    ) != (
        participant.executor_id,
        participant.executor_revision,
        participant.executor_digest,
        participant.skill.input_schema_digest,
        participant.skill.output_schema_digest,
        "READ_ONLY",
    ):
        raise ExecutionPreparationError("PREPARED_SKILL_OPERATION_MISMATCH")
    profile = published(connection, scope, "RUNTIME", participant.profile)
    if profile.get("provider") != "NATIVE_KUBERNETES":
        raise ExecutionPreparationError("PREPARED_NATIVE_PROFILE_REQUIRED")
    published(connection, scope, "KNOWLEDGE", preparation.source_snapshot)
    for resource in participant.resources:
        published(connection, scope, resource.kind, resource.reference)
    return operation


def resource_read_grants(preparation, participant):
    from .authority_contracts import ExactGrant

    return (
        ExactGrant(
            "KNOWLEDGE",
            "READ_RESOURCE",
            "knowledge:prepared-resource:"
            + preparation.source_snapshot.resource_id
            + ":"
            + preparation.source_snapshot.revision_id,
        ),
        ExactGrant(
            "RUNTIME_PROFILE",
            "READ_RESOURCE",
            "runtime-profile:prepared-resource:"
            + participant.profile.resource_id
            + ":"
            + participant.profile.revision_id,
        ),
    )
