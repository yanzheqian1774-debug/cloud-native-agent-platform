"""D324-4 bounded local accounts owned by Browser Session Authority.

Passwords are independent of bootstrap secrets and Grant lifetimes. Account
locks are taken before session locks; authorization uses the caller's transaction.
"""

import hashlib
import hmac
import secrets
from datetime import timedelta

from .authority_contracts import (
    AuthorityError,
    BrowserSession,
    SessionId,
    SessionSecret,
    VerifiedPrincipal,
)

ADAPTER = "local-test-accounts-v1"
VERSION = 36


def _migration(repository):
    return repository.migration_path.parent / "0036_local_test_accounts.sql"


def schema_record(repository):
    return {
        "version": VERSION,
        "adapter": ADAPTER,
        "checksum": hashlib.sha256(_migration(repository).read_bytes()).hexdigest(),
    }


def verify_schema(repository):
    with repository.connection_scope() as c:
        row = c.execute(
            "SELECT version,adapter,checksum FROM "
            "browser_identity.schema_migrations WHERE version=36"
        ).fetchone()
        if row != schema_record(repository):
            raise AuthorityError("AUTHORITY_SCHEMA_INCOMPATIBLE")


def migrate(repository):
    with repository.connection_scope() as c:
        c.execute("SELECT pg_advisory_xact_lock(3240036)")
        record = schema_record(repository)
        row = c.execute(
            "SELECT version,adapter,checksum FROM "
            "browser_identity.schema_migrations WHERE version=36"
        ).fetchone()
        if row:
            if row != record:
                raise AuthorityError("AUTHORITY_SCHEMA_INCOMPATIBLE")
            return
        c.execute("SET LOCAL lock_timeout='3s'")
        c.execute("SET LOCAL statement_timeout='30s'")
        c.execute(_migration(repository).read_text())
        c.execute(
            "INSERT INTO "
            "browser_identity.schema_migrations(version,adapter,checksum)"
            " VALUES(36,%s,%s)",
            (ADAPTER, record["checksum"]),
        )


def password_hash(password, *, salt=None):
    if not isinstance(password, str) or not 16 <= len(password) <= 256:
        raise AuthorityError("LOCAL_PASSWORD_POLICY")
    salt = salt or secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode(), salt=salt, n=131072, r=8, p=1, maxmem=256 * 1024 * 1024
    )
    return "scrypt-131072-8-1$" + salt.hex() + "$" + derived.hex()


def password_matches(password, encoded):
    try:
        algorithm, salt, expected = encoded.split("$")
        if algorithm != "scrypt-131072-8-1" or len(salt) != 32 or len(expected) != 128:
            return False
        return hmac.compare_digest(
            password_hash(password, salt=bytes.fromhex(salt)), encoded
        )
    except (ValueError, AuthorityError):
        # Keep the expensive verification path for malformed/short input too.
        password_hash("invalid-password-placeholder", salt=b"\x00" * 16)
        return False


def account_binding_current(generation, binding):
    return (
        binding is not None
        and binding.credential_id not in generation.credential_revocation_tombstones
        and binding.grant_source_id not in generation.credential_revocation_tombstones
    )


def current_session_account(c, *, session_id=None, secret_digest=None):
    """Same transaction as the protected owner; locks account before session."""
    if session_id is not None:
        session = c.execute(
            "SELECT session_id,credential_id FROM "
            "browser_identity.sessions WHERE session_id=%s",
            (session_id,),
        ).fetchone()
    else:
        session = c.execute(
            "SELECT session_id,credential_id FROM "
            "browser_identity.sessions WHERE secret_digest=%s",
            (secret_digest,),
        ).fetchone()
    if session is None:
        return False
    if not session["credential_id"].startswith("local-account:"):
        return True
    row = c.execute(
        "SELECT a.status,a.revision,s.account_revision FROM "
        "browser_identity.local_accounts a JOIN "
        "browser_identity.local_account_sessions s "
        "USING(account_id) WHERE s.session_id=%s AND "
        "a.account_id=%s FOR SHARE OF a",
        (session["session_id"], session["credential_id"]),
    ).fetchone()
    return bool(
        row
        and row["status"] == "ENABLED"
        and row["revision"] == row["account_revision"]
    )


def _limit(c, bucket, limit, now):
    row = c.execute(
        "INSERT INTO "
        "browser_identity.local_login_limits(bucket,started_at,attempts)"
        " VALUES(%s,%s,1) ON CONFLICT(bucket) DO UPDATE SET "
        "started_at=CASE WHEN local_login_limits.started_at<=%s "
        "THEN EXCLUDED.started_at ELSE "
        "local_login_limits.started_at END, attempts=CASE WHEN "
        "local_login_limits.started_at<=%s THEN 1 ELSE "
        "local_login_limits.attempts+1 END RETURNING attempts",
        (bucket, now, now - timedelta(minutes=15), now - timedelta(minutes=15)),
    ).fetchone()
    return row["attempts"] <= limit


def login(service, username, password):
    generation = service.authenticator.generation
    binding = next(
        (a for a in generation.local_accounts if a.username == username), None
    )
    now = service.clock()
    result = None
    reason = "ACCOUNT_AUTHENTICATION_FAILED"
    with service.repository.connection_scope() as c:
        active = c.execute(
            "SELECT generation,generation_digest,recovery_epoch "
            "FROM authorization_admin.active_generation WHERE "
            "singleton=true FOR SHARE"
        ).fetchone()
        if active is None or (
            active["generation"],
            active["generation_digest"],
            active["recovery_epoch"],
        ) != (generation.generation, generation.digest, service.recovery_epoch):
            raise AuthorityError("AUTHORITY_RECOVERY_REQUIRED")
        # Bounded buckets: two configured usernames plus one shared unknown bucket.
        global_allowed = _limit(c, "global", 100, now)
        allowed = (
            _limit(c, binding.username if binding else "unknown", 10, now)
            and global_allowed
        )
        row = (
            c.execute(
                "SELECT * FROM browser_identity.local_accounts "
                "WHERE account_id=%s FOR UPDATE",
                (binding.credential_id,),
            ).fetchone()
            if binding
            else None
        )
        encoded = (
            c.execute(
                "SELECT password_hash FROM "
                "browser_identity.local_account_passwords WHERE "
                "account_id=%s AND revision=%s",
                (row["account_id"], row["revision"]),
            ).fetchone()
            if row
            else None
        )
        # Unknown accounts do the same expensive hash without retaining submitted names.
        match = (
            password_matches(password, encoded["password_hash"])
            if encoded
            else password_matches(
                password, "scrypt-131072-8-1$" + "00" * 16 + "$" + "00" * 64
            )
        )
        valid = (
            allowed
            and match
            and row
            and row["status"] == "ENABLED"
            and account_binding_current(generation, binding)
            and (row["principal_id"], row["tenant_id"], row["security_domain"])
            == (
                binding.principal_id,
                binding.scope.tenant_id,
                binding.scope.security_domain,
            )
        )
        if valid:
            expires = now + service.policy.absolute_lifetime
            session = BrowserSession(
                SessionId("session-" + service.token_factory()),
                VerifiedPrincipal(
                    binding.principal_id,
                    binding.scope,
                    binding.credential_id,
                    expires,
                    generation.policy_version,
                ),
                now,
                now,
                min(now + service.policy.idle_lifetime, expires),
                expires,
                service.recovery_epoch,
                generation.generation,
            )
            secret = service.token_factory()
            service.repository._insert_session(c, session, service._digest(secret))
            c.execute(
                "INSERT INTO browser_identity.local_account_sessions VALUES(%s,%s,%s)",
                (session.session_id, binding.credential_id, row["revision"]),
            )
            result = SessionSecret(session.session_id, secret, expires)
            reason = "ACCOUNT_AUTHENTICATED"
        elif not allowed:
            reason = "ACCOUNT_LOGIN_THROTTLED"
        service.repository._audit(
            c,
            event_type="LOCAL_ACCOUNT_LOGIN",
            actor_id=binding.principal_id if binding else "anonymous",
            outcome="COMMITTED" if valid else "DENIED",
            reason=reason,
            occurred_at=now,
            generation=generation.generation,
            recovery_epoch=service.recovery_epoch,
        )
    # Raise after committing failed-attempt counters and redacted audit.
    if result is None:
        error = AuthorityError("AUTHENTICATION_REQUIRED")
        error.diagnostic_reason = reason
        raise error
    return result


def operate(
    repository, binding, *, action, command_id, operator_id, now, password=None
):
    """Explicit operator command. Passwords are not generated on service startup."""
    if (
        action not in {"CREATE", "RESET", "DISABLE", "ENABLE", "REVOKE"}
        or not command_id
        or not operator_id.startswith("operator:")
    ):
        raise AuthorityError("LOCAL_ACCOUNT_COMMAND_INVALID")
    encoded = password_hash(password) if action in {"CREATE", "RESET"} else None
    with repository.connection_scope() as c:
        c.execute("SELECT pg_advisory_xact_lock(3240036)")
        replay = c.execute(
            "SELECT * FROM browser_identity.local_account_commands WHERE command_id=%s",
            (command_id,),
        ).fetchone()
        if replay:
            if (replay["account_id"], replay["action"], replay["operator_id"]) != (
                binding.credential_id,
                action,
                operator_id,
            ):
                raise AuthorityError("IDEMPOTENCY_PAYLOAD_CONFLICT")
            if encoded:
                old = c.execute(
                    "SELECT password_hash FROM "
                    "browser_identity.local_account_passwords "
                    "WHERE account_id=%s AND revision=%s",
                    (binding.credential_id, replay["revision"]),
                ).fetchone()
                if old is None or not password_matches(password, old["password_hash"]):
                    raise AuthorityError("IDEMPOTENCY_PAYLOAD_CONFLICT")
            return replay["revision"]
        row = c.execute(
            "SELECT * FROM browser_identity.local_accounts WHERE "
            "account_id=%s FOR UPDATE",
            (binding.credential_id,),
        ).fetchone()
        if action == "CREATE":
            if row:
                raise AuthorityError("LOCAL_ACCOUNT_ALREADY_EXISTS")
            revision = 1
            c.execute(
                "INSERT INTO browser_identity.local_accounts "
                "VALUES(%s,%s,%s,%s,%s,'ENABLED',1,%s)",
                (
                    binding.credential_id,
                    binding.username,
                    binding.principal_id,
                    binding.scope.tenant_id,
                    binding.scope.security_domain,
                    now,
                ),
            )
        else:
            if row is None or row["status"] == "REVOKED":
                raise AuthorityError("LOCAL_ACCOUNT_UNAVAILABLE")
            revision = row["revision"] + 1
            status = {
                "ENABLE": "ENABLED",
                "DISABLE": "DISABLED",
                "REVOKE": "REVOKED",
            }.get(action, row["status"])
            c.execute(
                "UPDATE browser_identity.local_accounts SET "
                "status=%s,revision=%s WHERE account_id=%s",
                (status, revision, binding.credential_id),
            )
            if encoded is None:
                old = c.execute(
                    "SELECT password_hash FROM "
                    "browser_identity.local_account_passwords "
                    "WHERE account_id=%s AND revision=%s",
                    (binding.credential_id, row["revision"]),
                ).fetchone()
                encoded = old["password_hash"]
        c.execute(
            "INSERT INTO browser_identity.local_account_passwords VALUES(%s,%s,%s,%s)",
            (binding.credential_id, revision, encoded, now),
        )
        c.execute(
            "INSERT INTO browser_identity.local_account_commands "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (command_id, binding.credential_id, action, revision, operator_id, now),
        )
        repository._audit(
            c,
            event_type="LOCAL_ACCOUNT_" + action,
            actor_id=operator_id,
            outcome="COMMITTED",
            reason=action,
            occurred_at=now,
            scope=binding.scope,
            subject_id=binding.credential_id,
        )
        return revision
