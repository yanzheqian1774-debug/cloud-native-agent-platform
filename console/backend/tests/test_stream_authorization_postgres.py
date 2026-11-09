"""Exact ephemeral READ stays live while dispatch owns the governance lock."""

import hashlib
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS

import pytest
from agent_console.authority_configuration import (
    CredentialConfiguration,
    StaticAuthorityGeneration,
    StaticGrant,
)
from agent_console.authority_contracts import (
    AuthenticationSource,
    GrantSource,
    TrustedRequestContext,
)
from agent_console.draft_assistance_authorization import (
    GrantAdministrationDraftAuthorization,
    read_grant,
)
from agent_console.grant_administration_application import GenerationAuthorizationReader
from test_authority_foundation_postgres import (  # noqa: F401
    DATABASE_URL,
    isolated_database,
    repository,
    session,
)

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="isolated PostgreSQL required")


def test_preview_checks_live_grant_without_waiting_for_dispatch_lock(repository):  # noqa: F811
    now = datetime.now(UTC)
    browser = session(now, "preview")
    invocation = NS(invocation_id="preview-exact")
    grant = read_grant(invocation)
    credential = CredentialConfiguration(
        browser.principal.credential_id,
        "7" * 64,
        browser.principal.principal_id,
        browser.principal.scope,
        now + timedelta(days=1),
        GrantSource.BROWSER_BOOTSTRAP,
        (StaticGrant(grant, GrantSource.BROWSER_BOOTSTRAP),),
    )
    generation = StaticAuthorityGeneration(
        1, "a" * 64, "policy-1", "test", (credential,), (), frozenset()
    )
    repository.activate_generation(
        1,
        generation.digest,
        1,
        operator_id="operator:test",
        revoked_credentials=(),
        now=now,
    )
    repository.create_session(browser, hashlib.sha256(b"preview").hexdigest())
    context = TrustedRequestContext(
        browser.principal.principal_id,
        browser.principal.scope,
        browser.session_id,
        AuthenticationSource.BROWSER_SESSION,
        "policy-1",
    )
    reader = GenerationAuthorizationReader(
        generation, repository, repository, recovery_epoch=1
    )
    owner = NS(
        controller=NS(
            protected_request=lambda: nullcontext(generation),
            readiness=NS(recovery_epoch=1),
        ),
        authorization=reader,
    )
    authorization = GrantAdministrationDraftAuthorization(None, owner)
    with repository.pool.connection() as held, held.transaction():
        held.execute("SELECT pg_advisory_xact_lock(3230028)")
        assert authorization.can_read_stream(context, invocation)
        assert not authorization.can_read_stream(context, NS(invocation_id="other"))
    repository.revoke_session(
        browser.session_id, now=now, reason="test", actor_id="operator:test"
    )
    assert not authorization.can_read_stream(context, invocation)
