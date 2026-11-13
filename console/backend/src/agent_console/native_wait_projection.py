"""Same exact-progress READ projection; never authority to resume a wait."""

import json
from datetime import UTC, datetime
from typing import get_args

from .authority_contracts import AuthorityError
from .native_wait_types import WaitCheckpoint, WaitState


def read_waits(connection, preparation):
    # Caller has already passed native_interaction.records' complete exact READ
    # contract. Do not add execution checks or a GET-side grant/write here.
    if not connection.execute(
        "SELECT to_regclass('skill_invocation.native_wait_heads') present"
    ).fetchone()["present"]:
        return None
    rows = connection.execute(
        "SELECT h.state,h.checkpoint_digest,cp.record,i.skill_invocation_id,"
        "i.attempt_id,n.principal_id,n.command_id,"
        "EXISTS(SELECT 1 FROM skill_invocation.native_wait_observations o "
        "WHERE o.namespace=h.namespace AND o.security_domain=h.security_domain "
        "AND o.skill_invocation_id=h.skill_invocation_id "
        "AND o.checkpoint_digest=h.checkpoint_digest "
        "AND o.kind='ANSWER_SAVED') answered,"
        "EXISTS(SELECT 1 FROM skill_invocation.native_wait_observations o "
        "WHERE o.namespace=h.namespace AND o.security_domain=h.security_domain "
        "AND o.skill_invocation_id=h.skill_invocation_id "
        "AND o.checkpoint_digest=h.checkpoint_digest "
        "AND o.kind='STOP_CONFIRMED') stopped "
        "FROM skill_invocation.invocations i "
        "JOIN skill_invocation.native_wait_heads h "
        "USING(namespace,security_domain,skill_invocation_id) "
        "JOIN skill_invocation.native_wait_checkpoints cp "
        "USING(namespace,security_domain,skill_invocation_id,checkpoint_digest) "
        "JOIN execution_authority.native_dispatch_commands n "
        "USING(namespace,security_domain,attempt_id) "
        "WHERE i.namespace=%s AND i.security_domain=%s AND i.workflow_run_id=%s "
        "ORDER BY i.skill_invocation_id LIMIT 33",
        (preparation.namespace, preparation.security_domain, preparation.run_id),
    ).fetchall()
    if len(rows) > 32:
        raise AuthorityError("NATIVE_WAIT_PROJECTION_INCOMPLETE")
    result = []
    for row in rows:
        cp = WaitCheckpoint.model_validate_json(json.dumps(row["record"]))
        identity = cp.identity
        if (
            cp.digest != row["checkpoint_digest"]
            or identity.namespace != preparation.namespace
            or identity.security_domain != preparation.security_domain
            or identity.preparation_digest != preparation.digest
            or identity.workflow_run_id != preparation.run_id
            or identity.skill_invocation_id != row["skill_invocation_id"]
            or identity.attempt_id != str(row["attempt_id"])
            or identity.command_id != str(row["command_id"])
            or identity.principal_id != row["principal_id"]
            or cp.source_digest != preparation.source_snapshot.digest
        ):
            raise AuthorityError("NATIVE_WAIT_PROJECTION_BINDING_INVALID")
        state = row["state"]
        if state not in get_args(WaitState):
            raise AuthorityError("NATIVE_WAIT_PROJECTION_STATE_INVALID")
        now = datetime.now(UTC)
        if state != "COMPLETED" and now >= cp.authority_expires_at:
            state = "BLOCKED"
        elif (
            state != "COMPLETED" and not row["answered"] and now >= cp.human_expires_at
        ):
            state = "EXPIRED"
        # Observations only; neither branch mutates the persisted head or grants.
        result.append(
            dict(
                invocationId=identity.skill_invocation_id,
                questionKey=cp.question_key,
                questionDigest=cp.question_digest,
                state=state,
                humanExpiresAt=cp.human_expires_at.isoformat(),
                answerSaved=row["answered"],
                stopConfirmed=row["stopped"],
            )
        )
    return result
