# ruff: noqa: E501 -- Scoped immutable owner SQL.
"""Transactional reference owner, not installed by any runtime or HTTP route yet.

The caller supplies a current owner authorization/read callback inside its existing
transaction. That callback must verify exact READ authority and return only current
saved source/question/retention/budget evidence. No client authorization flag is
accepted. This adapter neither starts a model nor writes a business object.
"""

from psycopg.types.json import Jsonb

from .draft_assistance import DraftScope
from .draft_assistance_postgres import PostgresDraftAssistanceRepository
from .understanding_result_adoption import reference, require


def installed(connection):
    return (
        connection.execute(
            "SELECT to_regclass('draft_assistance.result_adoptions') AS name"
        ).fetchone()["name"]
        is not None
    )


def lock_context(connection, scope, identity):
    row = connection.execute(
        "SELECT initiating_principal_id FROM draft_assistance.contexts WHERE namespace=%s AND security_domain=%s AND context_id=%s FOR UPDATE",
        (scope.namespace, scope.security_domain, identity),
    ).fetchone()
    require(row is not None, "ORIGINAL_NOT_FOUND")
    return row


def require_unconsumed_parent(connection, candidate):
    """Called under the same context lock by the normal draft claim adapter."""
    if installed(connection):
        row = connection.execute(
            "SELECT 1 FROM draft_assistance.result_adoptions WHERE namespace=%s AND security_domain=%s AND original_invocation_id=%s",
            (
                candidate.scope.namespace,
                candidate.scope.security_domain,
                candidate.predecessor_invocation_id,
            ),
        ).fetchone()
        require(row is None, "PARENT_ALREADY_CONSUMED")


def require_unconsumed_question(connection, candidate):
    """Prevent a fresh route call consuming a question already adopted elsewhere."""
    target = (candidate.conversation_context or {}).get("target") or {}
    if target.get("kind") != "UNDERSTANDING" or not installed(connection):
        return
    owner = lock_context(connection, candidate.scope, target.get("contextId", ""))
    require(
        owner["initiating_principal_id"] == candidate.initiating_principal_id,
        "SUBJECT_MISMATCH",
    )
    row = connection.execute(
        "SELECT 1 FROM draft_assistance.result_adoptions WHERE namespace=%s "
        "AND security_domain=%s AND original_invocation_id=%s",
        (
            candidate.scope.namespace,
            candidate.scope.security_domain,
            target.get("invocationId", ""),
        ),
    ).fetchone()
    require(row is None, "PARENT_ALREADY_CONSUMED")


def adopt(connection, context, target, result_id, request_key, verify):
    """Append once. All effects roll back with the caller's owner transaction."""
    require(installed(connection), "UNAVAILABLE")
    require(0 < len(request_key) <= 128, "KEY_INVALID")
    scope = DraftScope.from_context(context)
    require(context.principal_id == target.subject_id, "SUBJECT_MISMATCH")
    owner = lock_context(connection, scope, target.original_context_id)
    require(owner["initiating_principal_id"] == target.subject_id, "SUBJECT_MISMATCH")
    for identity in sorted({target.original_invocation_id, result_id}):
        row = connection.execute(
            "SELECT initiating_principal_id FROM draft_assistance.invocations WHERE namespace=%s AND security_domain=%s AND invocation_id=%s FOR UPDATE",
            (scope.namespace, scope.security_domain, identity),
        ).fetchone()
        require(
            row is not None and row["initiating_principal_id"] == target.subject_id,
            "RESULT_NOT_FOUND",
        )
    original = PostgresDraftAssistanceRepository._latest(
        connection, scope, target.original_invocation_id
    )
    result = PostgresDraftAssistanceRepository._latest(connection, scope, result_id)
    head_id = connection.execute(
        "SELECT i.invocation_id FROM draft_assistance.invocations i JOIN draft_assistance.turns t USING(namespace,security_domain,context_id,turn_id) WHERE i.namespace=%s AND i.security_domain=%s AND i.context_id=%s ORDER BY t.ordinal DESC LIMIT 1",
        (scope.namespace, scope.security_domain, target.original_context_id),
    ).fetchone()
    head = PostgresDraftAssistanceRepository._latest(
        connection, scope, head_id["invocation_id"]
    )
    # Revalidate actual authority/retention even for an idempotent readback.
    evidence = verify(connection, context, target, original, result)
    record = reference(target, original, head, result, **evidence)
    prior = connection.execute(
        "SELECT record,request_key FROM draft_assistance.result_adoptions WHERE namespace=%s AND security_domain=%s AND original_invocation_id=%s",
        (scope.namespace, scope.security_domain, original.invocation_id),
    ).fetchone()
    if prior:
        require(prior == {"record": record, "request_key": request_key}, "CONFLICT")
        return prior["record"]
    connection.execute(
        "INSERT INTO draft_assistance.result_adoptions(namespace,security_domain,original_invocation_id,result_invocation_id,subject_id,conversation_id,message_id,request_key,record_digest,record) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            scope.namespace,
            scope.security_domain,
            original.invocation_id,
            result.invocation_id,
            target.subject_id,
            target.conversation_id,
            target.message_id,
            request_key,
            record["digest"],
            Jsonb(record),
        ),
    )
    return record


def read_chain(connection, context, result_id, authorize_read):
    """Read exact adopted ancestry; returns evidence, never business permission.

    Callers must separately validate the root business policy and both active
    configurations before issuing any business/planning grants. This owner does
    not infer that a general context is business-authorized.
    """
    from .draft_assistance import DraftInvocationState
    from .draft_assistance_postgres import _invocation
    from .private_conversation import digest

    if not installed(connection):
        return ()
    scope = DraftScope.from_context(context)
    chain, seen = [], set()
    conversation, expected_result_source = None, None
    for _ in range(16):
        require(result_id not in seen, "LINEAGE_CYCLE")
        seen.add(result_id)
        row = connection.execute(
            "SELECT record,record_digest FROM draft_assistance.result_adoptions WHERE namespace=%s AND security_domain=%s AND result_invocation_id=%s AND subject_id=%s",
            (scope.namespace, scope.security_domain, result_id, context.principal_id),
        ).fetchone()
        if row is None:
            return tuple(chain)
        record = row["record"]
        require(
            digest({k: v for k, v in record.items() if k != "digest"})
            == record.get("digest")
            == row["record_digest"],
            "REFERENCE_CORRUPT",
        )
        target, actual = record["target"], record["actualResult"]
        require(
            record["scope"] == [scope.namespace, scope.security_domain]
            and target["subject_id"] == context.principal_id
            and actual["invocationId"] == result_id,
            "SUBJECT_MISMATCH",
        )
        if conversation is None:
            conversation = target["conversation_id"]
        result_source = record["resultSourceDigest"]
        require(
            target["conversation_id"] == conversation
            and (
                expected_result_source is None
                or result_source == expected_result_source
            ),
            "SOURCE_CHANGED",
        )
        exact = connection.execute(
            "SELECT record FROM draft_assistance.invocation_versions WHERE namespace=%s AND security_domain=%s AND invocation_id=%s AND aggregate_version=%s",
            (
                scope.namespace,
                scope.security_domain,
                result_id,
                actual["aggregateVersion"],
            ),
        ).fetchone()
        require(exact is not None, "RESULT_NOT_FOUND")
        saved = _invocation(exact["record"])
        current = PostgresDraftAssistanceRepository._latest(
            connection, scope, result_id
        )
        original = PostgresDraftAssistanceRepository._latest(
            connection, scope, target["original_invocation_id"]
        )
        require(current is not None and original is not None, "RESULT_NOT_FOUND")
        authorize_read(connection, context, original, current)
        fields = (
            "context_id",
            "turn_id",
            "turn_version",
            "scope",
            "initiating_principal_id",
            "commitment",
            "profile_revision_id",
            "input_source",
            "conversation_context",
            "conversation_route",
            "result_kind",
            "terminal_observation_id",
        )
        require(
            current.state is DraftInvocationState.SUCCEEDED
            and saved.state is DraftInvocationState.SUCCEEDED
            and all(getattr(current, k) == getattr(saved, k) for k in fields)
            and current.context_id == actual["contextId"]
            and current.turn_id == actual["turnId"]
            and current.terminal_observation_id == actual["terminalObservationId"]
            and current.result_kind.value == actual["resultKind"]
            and current.commitment == record["resultCommitment"]
            and current.profile_revision_id == record["resultProfileRevision"]
            and digest(current.input_source) == result_source
            and original.state is DraftInvocationState.SUCCEEDED
            and original.aggregate_version == target["original_aggregate_version"]
            and digest(original.input_source) == target["source_digest"]
            and original.context_id == target["original_context_id"]
            and original.turn_id == target["original_turn_id"]
            and original.turn_version == target["original_turn_version"]
            and original.initiating_principal_id == context.principal_id
            and original.scope == scope,
            "REFERENCE_CHANGED",
        )
        transition = record.get("sourceTransition")
        require(
            (
                transition == "UNCHANGED"
                and current.input_source == original.input_source
            )
            or (
                transition == "EXPLICIT_AUTHORIZED_SUPPLEMENT"
                and original.input_source is None
                and original.result_kind.value in {"NEEDS_DATA", "DRAFT_READY"}
                and isinstance(current.input_source, dict)
                and bool(current.input_source)
            ),
            "SOURCE_CHANGED",
        )
        expected_result_source = target["source_digest"]
        chain.append(record)
        result_id = original.invocation_id
    require(False, "LINEAGE_TOO_DEEP")


def migrate(repository):
    """Optional local extension ledger; never raise the frozen draft schema version."""
    from hashlib import sha256
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[2]
        / "migrations/0065_understanding_result_adoption.sql"
    )
    checksum = sha256(path.read_bytes()).hexdigest()
    with repository.connection_scope() as connection:
        connection.execute("SELECT pg_advisory_xact_lock(3230065)")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS draft_assistance.adoption_schema_migrations "
            "(version integer PRIMARY KEY,checksum text NOT NULL,"
            "applied_at timestamptz NOT NULL DEFAULT clock_timestamp())"
        )
        rows = connection.execute(
            "SELECT version,checksum FROM draft_assistance.adoption_schema_migrations"
        ).fetchall()
        if rows:
            require(
                rows == [{"version": 65, "checksum": checksum}], "SCHEMA_INCOMPATIBLE"
            )
            return
        connection.execute(path.read_text())
        connection.execute(
            "INSERT INTO draft_assistance.adoption_schema_migrations(version,checksum) VALUES(65,%s)",
            (checksum,),
        )
