"""Accepted 323-only append-only continuity. No credential or grant is copied."""

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import AuthorityError


class ContinuityApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    original_digest: str = Field(pattern="^[a-f0-9]{64}$")
    transition_id: str
    transition_digest: str = Field(pattern="^[a-f0-9]{64}$")
    predecessor_digest: str | None = None
    binding_digest: str = Field(pattern="^[a-f0-9]{64}$")
    old_subject_credential_id: str
    old_issuer_credential_id: str
    subject_credential_id: str
    issuer_credential_id: str
    expires_at: datetime
    idempotency_key: str = Field(min_length=1, max_length=200)


def available(c):
    return bool(
        c.execute(
            "SELECT "
            "to_regclass('authorization_admin.task_identity_continuities') AS "
            "name"
        ).fetchone()["name"]
    )


def transition_proof(current, candidate, readiness):
    """Only called by the trusted Foundation controller, never from an HTTP body."""

    def public(credential):
        return {
            "credential_id": str(credential.credential_id),
            "principal_id": str(credential.principal_id),
            "scope": asdict(credential.scope),
            "expires_at": credential.expires_at.isoformat(),
            "grants": [asdict(g.grant) for g in credential.grants],
        }

    old = {str(v.credential_id): v for v in current.credentials}
    new = {str(v.credential_id): v for v in candidate.credentials}
    return {
        "old_generation": current.generation,
        "old_digest": current.digest,
        "generation": candidate.generation,
        "generation_digest": candidate.digest,
        "database_fingerprint": readiness.database_fingerprint,
        "recovery_epoch": readiness.recovery_epoch,
        "policy_unchanged": current.policy_version == candidate.policy_version
        and current.requestability == candidate.requestability,
        "old": {k: public(v) for k, v in old.items()},
        "new": {k: public(v) for k, v in new.items()},
        "preserved": [k for k, v in old.items() if new.get(k) == v],
        "fresh": [
            k
            for k, v in new.items()
            if k not in old
            and all(v.credential_sha256 != o.credential_sha256 for o in old.values())
        ],
        "revoked_credentials": sorted(
            str(k) for k in candidate.credential_revocation_tombstones
        ),
        "revoked_static": [
            {"credential_id": str(k), "grant": asdict(g)}
            for k, g in sorted(candidate.static_grant_revocation_tombstones, key=str)
        ],
    }


def record_transition(c, proof, row, *, operator_id, now):
    from .task_delegation import digest

    if not available(c):
        return
    if (
        row is None
        or any(row[k] != proof[k] for k in ("recovery_epoch",))
        or row["generation"] != proof["old_generation"]
        or row["generation_digest"] != proof["old_digest"]
    ):
        raise AuthorityError("TASK_CONTINUITY_TRANSITION_INVALID")
    identity = "identity-transition-" + uuid4().hex
    c.execute(
        (
            "INSERT INTO authorization_admin.task_identity_transitions "
            "(transition_id,old_generation,generation,recovery_epoch,old_digest,generation_digest,operator_id,database_fingerprint,record,digest,created_at)"
            " VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        ),
        (
            identity,
            proof["old_generation"],
            proof["generation"],
            proof["recovery_epoch"],
            proof["old_digest"],
            proof["generation_digest"],
            operator_id,
            proof["database_fingerprint"],
            Jsonb(proof),
            digest(proof),
            now,
        ),
    )


def latest(c, identity):
    if not available(c):
        return None
    return c.execute(
        (
            "SELECT * FROM authorization_admin.task_identity_continuities "
            "WHERE delegation_id=%s ORDER BY ordinal DESC LIMIT 1"
        ),
        (identity,),
    ).fetchone()


def binding(c, row):
    from .task_cases import cases
    from .task_delegation import digest
    from .task_development import revision
    from .task_timeout_revision import current

    return digest(
        {
            "delegation": row["digest"],
            "cases": cases(c, row["delegation_id"]),
            "development": revision(c, row["delegation_id"]),
            "timeout": current(c, row["delegation_id"]),
            "ledgers": c.execute(
                (
                    "SELECT tenant_id,security_domain,ledger_id,purpose FROM "
                    "authorization_admin.task_delegation_ledgers WHERE "
                    "delegation_id=%s ORDER BY purpose"
                ),
                (row["delegation_id"],),
            ).fetchall(),
        }
    )


def effective(c, row, generation, now):
    result = latest(c, row["delegation_id"])
    if result is None:
        return None
    transition = c.execute(
        (
            "SELECT * FROM authorization_admin.task_identity_transitions WHERE"
            " transition_id=%s"
        ),
        (result["transition_id"],),
    ).fetchone()
    if (
        result["generation"] != generation["generation"]
        or result["recovery_epoch"] != generation["recovery_epoch"]
        or now >= result["expires_at"]
        or transition["generation_digest"] != generation["generation_digest"]
        or c.execute(
            (
                "SELECT 1 FROM "
                "authorization_admin.task_identity_continuity_revocations WHERE "
                "continuity_id=%s"
            ),
            (result["continuity_id"],),
        ).fetchone()
        or result["record"]["binding_digest"] != binding(c, row)
    ):
        raise AuthorityError("TASK_CONTINUITY_INACTIVE")
    return result


def _row(c, identity, context):
    row = c.execute(
        (
            "SELECT d.*,control.revoked FROM "
            "authorization_admin.task_delegations d JOIN "
            "authorization_admin.task_delegation_control control "
            "USING(delegation_id) WHERE delegation_id=%s FOR UPDATE OF "
            "d,control"
        ),
        (identity,),
    ).fetchone()
    if (
        row is None
        or row["task_id"] != "S5-V023-ARCH-323"
        or (row["tenant_id"], row["security_domain"])
        != (context.scope.tenant_id, context.scope.security_domain)
    ):
        raise AuthorityError("TASK_DELEGATION_NOT_FOUND")
    from .task_development import revision, stopped

    if (
        row["revoked"]
        or stopped(c, identity)
        or not revision(c, identity)
        or c.execute(
            (
                "SELECT 1 FROM authorization_admin.task_delegation_revocations "
                "WHERE delegation_id=%s"
            ),
            (identity,),
        ).fetchone()
    ):
        raise AuthorityError("TASK_DELEGATION_INACTIVE")
    if context.principal_id == row["subject_id"]:
        raise AuthorityError("GRANT_SELF_APPROVAL_PROHIBITED")
    if context.principal_id != row["issuer_id"]:
        raise AuthorityError("TASK_CONTINUITY_ISSUER_INVALID")
    return row


def preflight(service, context, identity):
    service._admin(context)
    with service.repository.connection_scope() as c:
        c.execute("SELECT pg_advisory_xact_lock(3230028)")
        service._admin(context, c)
        row = _row(c, identity, context)
        t = c.execute(
            (
                "SELECT * FROM authorization_admin.task_identity_transitions WHERE"
                " generation=%s"
            ),
            (service.grants.generation.generation,),
        ).fetchone()
        return {
            "original_digest": row["digest"],
            "binding_digest": binding(c, row),
            "predecessor": latest(c, identity),
            "transition": t,
        }


def approve(service, context, identity, spec):
    from .task_delegation import digest
    from .task_timeout_revision import effective_limits

    service._admin(context)
    payload = spec.model_dump(mode="json")
    with service.repository.connection_scope() as c:
        c.execute("SELECT pg_advisory_xact_lock(3230028)")
        service._admin(context, c)
        row = _row(c, identity, context)
        generation = c.execute(
            "SELECT * FROM authorization_admin.active_generation WHERE "
            "singleton=true FOR SHARE"
        ).fetchone()
        now = c.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        prior = c.execute(
            (
                "SELECT * FROM authorization_admin.task_identity_continuities "
                "WHERE delegation_id=%s AND generation=%s AND idempotency_key=%s"
            ),
            (identity, generation["generation"], spec.idempotency_key),
        ).fetchone()
        if prior:
            if prior["payload_digest"] != digest(payload):
                raise AuthorityError("IDEMPOTENCY_PAYLOAD_CONFLICT")
            return prior
        predecessor = latest(c, identity)
        if (predecessor["digest"] if predecessor else None) != spec.predecessor_digest:
            raise AuthorityError("TASK_CONTINUITY_PREDECESSOR_CONFLICT")
        t = c.execute(
            (
                "SELECT * FROM authorization_admin.task_identity_transitions WHERE"
                " transition_id=%s"
            ),
            (spec.transition_id,),
        ).fetchone()
        if (
            not t
            or t["digest"] != spec.transition_digest
            or t["generation"] != generation["generation"]
            or t["generation_digest"] != generation["generation_digest"]
            or t["recovery_epoch"] != row["recovery_epoch"]
            or generation["recovery_epoch"] != row["recovery_epoch"]
        ):
            raise AuthorityError("TASK_CONTINUITY_TRANSITION_INVALID")
        proof = t["record"]
        origin = predecessor["generation"] if predecessor else row["generation"]
        if origin != t["old_generation"] and not (
            predecessor
            and predecessor["generation"] == t["generation"]
            and predecessor["transition_id"] == t["transition_id"]
        ):
            raise AuthorityError("TASK_CONTINUITY_TRANSITION_INVALID")
        if (
            not proof["policy_unchanged"]
            or spec.original_digest != row["digest"]
            or spec.binding_digest != binding(c, row)
            or any(
                effective_limits(c, row, k) != service.configurations[k]
                for k in ("understanding", "planning")
            )
        ):
            raise AuthorityError("TASK_CONTINUITY_BINDING_INVALID")
        current_credential = service.repository._current_credential_id(
            c,
            context,
            now=now,
            recovery_epoch=generation["recovery_epoch"],
            lock_session=True,
        )
        if current_credential != spec.issuer_credential_id:
            raise AuthorityError("TASK_CONTINUITY_ISSUER_INVALID")
        for role in ("subject", "issuer"):
            old_id = getattr(spec, "old_" + role + "_credential_id")
            new_id = getattr(spec, role + "_credential_id")
            old = proof["old"].get(old_id)
            new = proof["new"].get(new_id)
            if (
                not old
                or not new
                or old_id not in proof["preserved"]
                or new_id not in proof["fresh"]
                or old_id in proof["revoked_credentials"]
                or new_id in proof["revoked_credentials"]
                or old["principal_id"] != row[role + "_id"]
                or new["principal_id"] != row[role + "_id"]
                or old["scope"] != new["scope"]
                or old["scope"]
                != {
                    "tenant_id": row["tenant_id"],
                    "security_domain": row["security_domain"],
                }
                or any(g not in old["grants"] for g in new["grants"])
            ):
                raise AuthorityError("TASK_CONTINUITY_IDENTITY_INVALID")
            if any(
                v["credential_id"] in (old_id, new_id) and v["grant"] in new["grants"]
                for v in proof["revoked_static"]
            ):
                raise AuthorityError("TASK_CONTINUITY_REVOKED_PERMISSION")
            if spec.expires_at.utcoffset() != timedelta(
                0
            ) or not now < spec.expires_at <= min(
                now + timedelta(hours=8), datetime.fromisoformat(new["expires_at"])
            ):
                raise AuthorityError("TASK_CONTINUITY_EXPIRY_INVALID")
        if (
            predecessor
            and c.execute(
                (
                    "SELECT 1 FROM "
                    "authorization_admin.task_identity_continuity_revocations WHERE "
                    "continuity_id=%s"
                ),
                (predecessor["continuity_id"],),
            ).fetchone()
        ):
            raise AuthorityError("TASK_CONTINUITY_REVOKED")
        cid = "task-continuity-" + uuid4().hex
        record = {
            **payload,
            "subject_id": row["subject_id"],
            "issuer_id": row["issuer_id"],
            "generation": generation["generation"],
            "recovery_epoch": row["recovery_epoch"],
            "created_at": now.isoformat(),
        }
        c.execute(
            (
                "INSERT INTO "
                "authorization_admin.task_identity_continuities(continuity_id,delegation_id,predecessor_id,ordinal,transition_id,generation,recovery_epoch,issuer_id,subject_id,subject_credential_id,issuer_credential_id,idempotency_key,payload_digest,record,digest,created_at,expires_at)"
                " VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
            ),
            (
                cid,
                identity,
                predecessor["continuity_id"] if predecessor else None,
                predecessor["ordinal"] + 1 if predecessor else 1,
                t["transition_id"],
                generation["generation"],
                row["recovery_epoch"],
                row["issuer_id"],
                row["subject_id"],
                spec.subject_credential_id,
                spec.issuer_credential_id,
                spec.idempotency_key,
                digest(payload),
                Jsonb(record),
                digest(record),
                now,
                spec.expires_at,
            ),
        )
        service.repository._audit(
            c,
            event_type="TASK_IDENTITY_CONTINUITY_APPROVED",
            actor_id=context.principal_id,
            outcome="APPROVED",
            reason="APPEND_ONLY_323_CONTINUITY",
            occurred_at=now,
            scope=context.scope,
            subject_id=cid,
            generation=generation["generation"],
            recovery_epoch=row["recovery_epoch"],
        )
        return latest(c, identity)


def revoke(service, context, identity, continuity_id):
    service._admin(context)
    with service.repository.connection_scope() as c:
        c.execute("SELECT pg_advisory_xact_lock(3230028)")
        service._admin(context, c)
        _row(c, identity, context)
        result = latest(c, identity)
        if not result or result["continuity_id"] != continuity_id:
            raise AuthorityError("TASK_CONTINUITY_NOT_FOUND")
        c.execute(
            (
                "INSERT INTO "
                "authorization_admin.task_identity_continuity_revocations(continuity_id,actor_id)"
                " VALUES(%s,%s) ON CONFLICT DO NOTHING"
            ),
            (continuity_id, context.principal_id),
        )
        service.repository._audit(
            c,
            event_type="TASK_IDENTITY_CONTINUITY_REVOKED",
            actor_id=context.principal_id,
            outcome="REVOKED",
            reason="INDEPENDENT_ISSUER",
            occurred_at=datetime.now(UTC),
            scope=context.scope,
            subject_id=continuity_id,
            recovery_epoch=result["recovery_epoch"],
        )
        return {"revoked": True, "continuity_id": continuity_id}


def require_unrevoked_member(c, row, member):
    """A new task grant cannot erase a revoked old exact grant."""
    if latest(c, row["delegation_id"]) is None:
        return
    denied = c.execute(
        (
            "SELECT 1 FROM authorization_admin.grants g JOIN "
            "authorization_admin.grant_revocation_facts r USING(grant_id) "
            "WHERE g.subject_principal_id=%s AND g.tenant_id=%s AND "
            "g.security_domain=%s AND g.owner=%s AND g.action=%s AND "
            "g.exact_resource=%s"
        ),
        (
            row["subject_id"],
            row["tenant_id"],
            row["security_domain"],
            member.owner,
            member.action,
            member.exact_resource,
        ),
    ).fetchone()
    if denied:
        raise AuthorityError("TASK_CONTINUITY_REVOKED_PERMISSION")
