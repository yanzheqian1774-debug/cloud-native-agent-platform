# ruff: noqa: E501 -- Scoped immutable command SQL.
"""Exact command replay and actor/authority audit for prepared control actions."""

import json

from psycopg.types.json import Jsonb

from .execution_preparation import ExecutionPreparationError
from .execution_preparation_postgres import PreparedExecutionStore
from .resource_use_domain import canonical_digest


def control_command(connection, principal, authority, p, action, payload, execute):
    authorization = authority.require(
        principal, "EXECUTION", action, "governed-execution:prepared:" + p.digest
    )
    key = payload["idempotencyKey"]
    digest = canonical_digest(
        {"preparation": p.digest, "action": action, "payload": payload}
    )
    connection.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        (
            json.dumps(
                [
                    "prepared-control",
                    p.namespace,
                    p.security_domain,
                    principal.principal_id,
                    key,
                ]
            ),
        ),
    )
    prior = connection.execute(
        "SELECT digest,result FROM execution_authority.prepared_control_commands WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND command_key=%s",
        (p.namespace, p.security_domain, principal.principal_id, key),
    ).fetchone()
    if prior:
        if prior["digest"] != digest:
            raise ExecutionPreparationError("CONTROL_COMMAND_REPLAY_CONFLICT")
        return prior["result"]
    PreparedExecutionStore(connection).read(
        p.namespace, p.security_domain, p.run_id, lock=True
    )
    result = execute()
    connection.execute(
        "INSERT INTO execution_authority.prepared_control_commands(namespace,security_domain,actor_id,command_key,workflow_run_id,digest,action,authority_basis,result) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            p.namespace,
            p.security_domain,
            principal.principal_id,
            key,
            p.run_id,
            digest,
            action,
            authorization.decision_id,
            Jsonb(result),
        ),
    )
    return result
