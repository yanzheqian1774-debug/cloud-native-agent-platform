"""Known waiting acknowledgement under the existing Skill/ResourceUse owners."""

from dataclasses import replace
from types import SimpleNamespace

from .execution_domain import ScopeIdentity
from .resource_use_domain import ResourceUseFactKind, reduce_resource_use
from .skill_invocation_domain import (
    InvocationFactKind,
    InvocationState,
    SkillInvocationError,
)


def record_running(repository, connection, checkpoint, now):
    """Called after checkpoint insertion, in the same locked owner transaction."""
    identity = checkpoint.identity
    scope = ScopeIdentity(identity.namespace, identity.security_domain)
    snapshot = repository._snapshot(connection, scope, identity.skill_invocation_id)
    if snapshot is None:
        raise SkillInvocationError("NATIVE_WAIT_SKILL_NOT_FOUND")
    if snapshot.state is InvocationState.RUNNING:
        return snapshot
    if snapshot.state is not InvocationState.DISPATCH_RECORDED:
        raise SkillInvocationError("NATIVE_WAIT_SKILL_NOT_DISPATCHED")
    stored = connection.execute(
        "SELECT record FROM skill_invocation.native_wait_checkpoints WHERE "
        "namespace=%s AND security_domain=%s AND skill_invocation_id=%s "
        "AND checkpoint_digest=%s",
        (*identity.skill_key, checkpoint.digest),
    ).fetchone()
    if not stored or stored["record"] != checkpoint.model_dump(mode="json"):
        raise SkillInvocationError("NATIVE_WAIT_COMMITTED_CHECKPOINT_REQUIRED")
    # This is a local adapter to fact constructors, not a fabricated Request or
    # identity/authority. Every value derives from the already locked owner rows.
    reference = SimpleNamespace(
        scope=scope,
        invocation_id=snapshot.invocation_id,
        resource_use=SimpleNamespace(resource_use_id=snapshot.resource_use_id),
    )
    kinds = (
        InvocationFactKind.INVOCATION_ACCEPTED,
        InvocationFactKind.INVOCATION_RUNNING,
    )
    facts = tuple(
        repository._fact(
            reference,
            kind,
            "native-wait-owner",
            checkpoint.digest + ":" + kind.value,
            checkpoint.digest,
            now,
        )
        for kind in kinds
    )
    repository._insert_invocation_facts(
        connection, reference, facts, snapshot.high_water
    )
    resources = repository.resource_use
    water = connection.execute(
        "SELECT high_water,version FROM resource_use.high_waters WHERE namespace=%s "
        "AND security_domain=%s AND resource_use_id=%s FOR UPDATE",
        (identity.namespace, identity.security_domain, snapshot.resource_use_id),
    ).fetchone()
    if not water:
        raise SkillInvocationError("SKILL_RESOURCE_USE_NOT_FOUND")
    use_facts = tuple(
        repository._resource_fact(
            reference,
            kind,
            "native-wait-owner",
            checkpoint.digest + ":" + kind.value,
            checkpoint.digest,
            now,
        )
        for kind in (ResourceUseFactKind.ACCEPTED, ResourceUseFactKind.RUNNING)
    )
    resources._insert_facts(connection, scope, use_facts, water["high_water"])
    high_water = water["high_water"] + len(use_facts)
    projection = reduce_resource_use(
        snapshot.resource_use_id,
        resources._facts(connection, scope, snapshot.resource_use_id),
        resources._measurements(connection, scope, snapshot.resource_use_id),
        high_water=high_water,
    )
    changed = connection.execute(
        "UPDATE resource_use.high_waters SET high_water=%s,version=version+1 WHERE "
        "namespace=%s AND security_domain=%s AND resource_use_id=%s AND version=%s",
        (
            high_water,
            identity.namespace,
            identity.security_domain,
            snapshot.resource_use_id,
            water["version"],
        ),
    )
    if changed.rowcount != 1:
        raise SkillInvocationError("SKILL_RESOURCE_USE_CAS_MISMATCH")
    resources._insert_snapshot(connection, scope, projection)
    running = replace(
        snapshot,
        state=InvocationState.RUNNING,
        high_water=snapshot.high_water + len(facts),
        fact_kinds=(*snapshot.fact_kinds, *kinds),
    )
    repository._upsert_projection(connection, scope, running, now)
    return running


def waiting_receipt(repository, request, executor, *, pause_only=False):
    """Positive readback only; never turns an arbitrary RUNNING job into a wait."""
    if not getattr(executor, "accepts_durable_wait", False):
        return None
    from .native_wait_store import NativeWaitStore
    from .native_wait_types import SkillJobWaiting, WaitIdentity

    with repository.pool.connection() as c:
        if not c.execute(
            "SELECT to_regclass('skill_invocation.native_wait_heads') AS t"
        ).fetchone()["t"]:
            return None
        row = c.execute(
            "SELECT h.checkpoint_digest,h.state AS wait_state,c.record,p.state "
            "FROM skill_invocation.native_wait_heads h "
            "JOIN skill_invocation.native_wait_checkpoints c "
            "USING(namespace,security_domain,skill_invocation_id,checkpoint_digest) "
            "JOIN skill_invocation.projections p "
            "USING(namespace,security_domain,skill_invocation_id) "
            "WHERE h.namespace=%s AND h.security_domain=%s "
            "AND h.skill_invocation_id=%s",
            (
                request.scope.namespace,
                request.scope.security_domain,
                request.invocation_id,
            ),
        ).fetchone()
        if not row:
            return None
        if pause_only and row["wait_state"] not in {
            "QUIESCING",
            "WAITING_FOR_USER",
            "ANSWER_SAVED",
        }:
            return None
        identity = WaitIdentity.model_validate(row["record"]["identity"])
        cp = NativeWaitStore(c, identity).checkpoint(row["checkpoint_digest"])
        if (
            row["state"] != "RUNNING"
            or identity.skill_invocation_id != request.invocation_id
            or identity.attempt_id != request.attempt_id
            or (cp.executor_id, cp.executor_revision, cp.executor_configuration_digest)
            != (
                request.executor.executor_id,
                request.executor.executor_revision,
                request.executor.configuration_digest,
            )
        ):
            raise SkillInvocationError("NATIVE_WAIT_SKILL_RECEIPT_MISMATCH")
        return SkillJobWaiting(identity=identity, checkpoint_digest=cp.digest)


def accepted_job(repository, request, inputs):
    """Read original immutable dispatch; this path never calls prepare_dispatch."""
    from .resource_use_domain import canonical_digest, canonical_record

    with repository.pool.connection() as c:
        row = c.execute(
            "SELECT exact_snapshot,created_at FROM skill_invocation.invocations "
            "WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s",
            (
                request.scope.namespace,
                request.scope.security_domain,
                request.invocation_id,
            ),
        ).fetchone()
        expected = {
            "schemaVersion": "skill-invocation-execution-snapshot.v1",
            "request": canonical_record(request),
            "inputDigest": canonical_digest(inputs),
            "payloadDigest": request.payload_digest(inputs),
        }
        if not row or row["exact_snapshot"] != expected:
            raise SkillInvocationError("NATIVE_WAIT_ORIGINAL_JOB_CHANGED")
        snapshot = repository._snapshot(c, request.scope, request.invocation_id)
        if snapshot is None:
            raise SkillInvocationError("NATIVE_WAIT_SKILL_NOT_FOUND")
        return snapshot, row["created_at"]
