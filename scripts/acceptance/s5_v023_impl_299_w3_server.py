#!/usr/bin/env python3
"""Run the IMPL-299 public Workbench against an exclusive PostgreSQL database."""

from __future__ import annotations

import argparse
import hashlib
import os
import stat
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import psycopg
import uvicorn
from agent_console.authority_configuration import (
    CredentialConfiguration,
    RequestabilityRule,
    StaticAuthorityGeneration,
    StaticGrant,
)
from agent_console.authority_contracts import (
    AuthorityScope,
    CredentialId,
    ExactGrant,
    GrantSource,
)
from agent_console.authority_foundation import SignedContinuationOwner
from agent_console.authority_postgres import PostgresAuthorityRepository
from agent_console.browser_session_application import (
    BrowserSessionPolicy,
    BrowserSessionService,
    StaticGenerationAuthenticator,
)
from agent_console.business_plan_postgres import PostgresProblemPlanUnitOfWork
from agent_console.business_problem_application import BusinessProblemApplication
from agent_console.business_problem_continuation import BusinessProblemCreateCoordinator
from agent_console.business_problem_postgres import PostgresBusinessProblemRepository
from agent_console.grant_administration_application import (
    GenerationAuthorizationReader,
    GrantAdministrationService,
)
from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
from agent_console.workbench_business_problem import business_problem_operations
from agent_console.workbench_grant_targets import WorkbenchGrantTargetValidator
from agent_console.workbench_owner_authorization import WorkbenchOwnerAuthorization


class Controller:
    def __init__(self, generation: StaticAuthorityGeneration) -> None:
        self.generation = generation
        self.readiness = SimpleNamespace(recovery_epoch=1)

    @contextmanager
    def protected_request(self):
        yield self.generation


def generation(alice_secret: str, bob_secret: str) -> StaticAuthorityGeneration:
    now = datetime.now(UTC)
    scope = AuthorityScope("tenant-impl299", "business-workbench")
    browser = GrantSource.BROWSER_BOOTSTRAP
    meta = GrantSource.STATIC_META
    return StaticAuthorityGeneration(
        generation=1,
        digest="9" * 64,
        policy_version="impl299-w3-live-v1",
        audit_source="S5-V023-IMPL-299-W3-LIVE",
        credentials=(
            CredentialConfiguration(
                CredentialId("impl299-alice"),
                hashlib.sha256(alice_secret.encode()).hexdigest(),
                "human:impl299-applicant",
                scope,
                now + timedelta(hours=2),
                browser,
                (
                    StaticGrant(
                        ExactGrant(
                            "BUSINESS_PROBLEM",
                            "CREATE",
                            "business-problem:collection",
                        ),
                        browser,
                    ),
                    StaticGrant(
                        ExactGrant(
                            "BUSINESS_PROBLEM", "LIST", "business-problem:collection"
                        ),
                        browser,
                    ),
                ),
            ),
            CredentialConfiguration(
                CredentialId("impl299-bob"),
                hashlib.sha256(bob_secret.encode()).hexdigest(),
                "human:impl299-independent-admin",
                scope,
                now + timedelta(hours=2),
                browser,
                (
                    StaticGrant(
                        ExactGrant(
                            "GRANT_ADMIN",
                            "DECIDE",
                            "grant-scope:tenant-impl299:business-workbench",
                        ),
                        meta,
                    ),
                    StaticGrant(
                        ExactGrant(
                            "GRANT_ADMIN",
                            "INSPECT",
                            "grant-scope:tenant-impl299:business-workbench",
                        ),
                        meta,
                    ),
                ),
            ),
        ),
        requestability=(
            RequestabilityRule(
                "BUSINESS_PROBLEM", "READ", "business-problem:", "CONTINUE_PROBLEM_READ"
            ),
            *tuple(
                RequestabilityRule(owner, action, prefix, "WORKBENCH_SUCCESS_CRITERIA")
                for owner, prefix, actions in (
                    (
                        "SUCCESS_CRITERION",
                        "success-criterion:",
                        ("CREATE", "READ", "REVISE"),
                    ),
                    (
                        "SUCCESS_CRITERIA_SET",
                        "success-criteria-set:",
                        ("CREATE", "READ", "REVISE"),
                    ),
                )
                for action in actions
            ),
        ),
        credential_revocation_tombstones=frozenset(),
    )


def build(
    database_url: str,
    alice_secret: str,
    bob_secret: str,
    *,
    allowed_host: str = "127.0.0.1:18299",
    allowed_origin: str = "https://console.example",
):
    migrations = Path(__file__).parents[2] / "console" / "backend" / "migrations"
    with psycopg.connect(database_url) as connection:
        for version in range(1, 13):
            connection.execute(
                next(migrations.glob(f"{version:04d}_*.sql")).read_text()
            )
    problems = PostgresBusinessProblemRepository(
        database_url,
        migration_path=migrations / "0013_business_problem_authority.sql",
        creator_receipt_migration_path=migrations
        / "0020_business_problem_creator_receipt.sql",
        timeout=30,
    )
    problems.migrate()
    authority = PostgresAuthorityRepository(
        database_url,
        migration_path=migrations / "0018_browser_session_grant_authority.sql",
        timeout=30,
    )
    authority.migrate()
    fixed = generation(alice_secret, bob_secret)
    authority.activate_generation(
        fixed.generation,
        fixed.digest,
        1,
        operator_id="operator:impl299-live",
        revoked_credentials=(),
        now=datetime.now(UTC),
    )
    sessions = BrowserSessionService(
        authority,
        StaticGenerationAuthenticator(fixed, source=GrantSource.BROWSER_BOOTSTRAP),
        BrowserSessionPolicy(
            login_nonce_lifetime=timedelta(minutes=5),
            idle_lifetime=timedelta(minutes=30),
            absolute_lifetime=timedelta(hours=2),
            csrf_lifetime=timedelta(minutes=10),
        ),
        csrf_signing_key=b"impl299-live-csrf-key-material-32",
        recovery_epoch=1,
    )
    reader = GenerationAuthorizationReader(
        fixed, authority, authority, recovery_epoch=1
    )
    grants = GrantAdministrationService(
        authority,
        reader,
        fixed,
        continuation_owner=SignedContinuationOwner(b"impl299-live-continuation-key-32"),
        target_validator=WorkbenchGrantTargetValidator(problems),
        recovery_epoch=1,
    )
    owner = BusinessProblemApplication(
        PostgresProblemPlanUnitOfWork(problems, object()),
        None,
        object(),
        object(),
        object(),
    )
    application = create_workbench_bff(
        sessions,
        WorkbenchOwnerAuthorization(Controller(fixed), authority, reader),  # type: ignore[arg-type]
        WorkbenchBffPolicy(allowed_host, allowed_origin),
        operations=business_problem_operations(
            owner,
            BusinessProblemCreateCoordinator(
                grants,
                clock=grants.clock,
                identity_factory=grants.identity_factory,
            ),
        ),
        grant_administration=grants,
    )
    return application, authority, problems


def main() -> None:
    parser = argparse.ArgumentParser()
    database = parser.add_mutually_exclusive_group(required=True)
    database.add_argument("--database-url")
    database.add_argument("--database-url-file", type=Path)
    database.add_argument("--database-url-env", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=18299, type=int)
    parser.add_argument("--allowed-host", default="127.0.0.1:18299")
    parser.add_argument("--allowed-origin", default="https://console.example")
    args = parser.parse_args()
    if args.database_url_file is not None:
        if stat.S_IMODE(args.database_url_file.stat().st_mode) != 0o600:
            parser.error("database URL file mode must be 0600")
        args.database_url = args.database_url_file.read_text(encoding="utf-8").strip()
    elif args.database_url_env:
        args.database_url = os.environ["IMPL299_DATABASE_URL"]
    alice = os.environ["IMPL299_ALICE_CREDENTIAL"]
    bob = os.environ["IMPL299_BOB_CREDENTIAL"]
    application, authority, problems = build(
        args.database_url,
        alice,
        bob,
        allowed_host=args.allowed_host,
        allowed_origin=args.allowed_origin,
    )
    try:
        uvicorn.run(application, host=args.host, port=args.port, log_level="warning")
    finally:
        authority.close()
        problems.pool.close()


if __name__ == "__main__":
    main()
