from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from agent_console.authority_configuration import (
    AuthorityRuntimeConfiguration,
    StaticAuthorityLoader,
    validate_registered_grant,
)
from agent_console.authority_contracts import AuthorityError, ExactGrant, GrantSource
from agent_console.authority_foundation import GovernedExecutionAuthenticatorAdapter


def generation_document() -> dict[str, object]:
    return {
        "schemaVersion": "static-authority-generation.v1",
        "generation": 1,
        "policyVersion": "policy-v1",
        "auditSource": "deployment-test",
        "credentials": [
            {
                "credentialId": "credential-alice",
                "credentialSha256": "a" * 64,
                "principalId": "human:alice",
                "tenantId": "tenant-a",
                "securityDomain": "quality",
                "expiresAt": "2030-01-01T00:00:00Z",
                "authenticationSource": "BROWSER_BOOTSTRAP",
                "grants": [
                    {
                        "owner": "BUSINESS_PROBLEM",
                        "action": "CREATE",
                        "resource": "business-problem:collection",
                        "source": "BROWSER_BOOTSTRAP",
                    }
                ],
            }
        ],
        "requestability": [
            {
                "owner": "BUSINESS_PROBLEM",
                "action": "READ",
                "resourcePrefix": "business-problem:",
                "purpose": "CONTINUE_PROBLEM_PLAN",
            }
        ],
        "credentialRevocationTombstones": [],
        "staticGrantRevocationTombstones": [],
    }


def write_generation(path: Path, document: object) -> str:
    raw = json.dumps(document, sort_keys=True).encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def test_generation_loader_pins_digest_and_closed_sources(tmp_path: Path) -> None:
    path = tmp_path / "generation-1.json"
    digest = write_generation(path, generation_document())

    generation = StaticAuthorityLoader.load(path, expected_digest=digest)

    assert generation.generation == 1
    assert (
        generation.credentials[0].authentication_source is GrantSource.BROWSER_BOOTSTRAP
    )
    assert generation.digest == digest


def test_generation_loader_rejects_digest_mismatch_and_wildcard(tmp_path: Path) -> None:
    path = tmp_path / "generation-1.json"
    document = generation_document()
    digest = write_generation(path, document)
    with pytest.raises(AuthorityError, match="AUTHORITY_GENERATION_DIGEST_MISMATCH"):
        StaticAuthorityLoader.load(path, expected_digest="0" * 64)

    document["requestability"][0]["resourcePrefix"] = "business-problem:*"  # type: ignore[index]
    digest = write_generation(path, document)
    with pytest.raises(AuthorityError, match="AUTHORITY_CONFIGURATION_INVALID"):
        StaticAuthorityLoader.load(path, expected_digest=digest)


def test_runtime_configuration_has_no_secret_or_privileged_defaults(
    tmp_path: Path,
) -> None:
    configuration = {
        "schemaVersion": "authority-foundation-runtime.v1",
        "databaseUrl": "postgresql://authority-test",
        "migrationPath": str(tmp_path / "0018.sql"),
        "generationPath": str(tmp_path / "generation.json"),
        "generationDigest": "b" * 64,
        "csrfSigningKeyPath": str(tmp_path / "csrf.key"),
        "continuationSigningKeyPath": str(tmp_path / "continuation.key"),
        "recoveryControlPath": str(tmp_path / "recovery.json"),
        "databaseFingerprint": "authority-test-database",
        "operatorId": "operator:test",
    }
    parsed = AuthorityRuntimeConfiguration.from_mapping(configuration)
    assert parsed.operator_id == "operator:test"

    missing_operator = dict(configuration)
    del missing_operator["operatorId"]
    with pytest.raises(AuthorityError, match="AUTHORITY_CONFIGURATION_INVALID"):
        AuthorityRuntimeConfiguration.from_mapping(missing_operator)

    with pytest.raises(AuthorityError, match="AUTHORITY_CONFIGURATION_UNAVAILABLE"):
        AuthorityRuntimeConfiguration.read_external_key(tmp_path / "missing.key")


def test_existing_service_bearer_verifier_is_preserved_behind_typed_port() -> None:
    now = datetime(2029, 1, 1, tzinfo=UTC)

    class ExistingAuthority:
        policy_version = "existing-policy"

        def authenticate(self, authorization: str) -> object:
            assert authorization == "Bearer service-secret"
            return SimpleNamespace(
                principal_id="service:runner",
                tenant_id="tenant-a",
                security_domain="quality",
                credential_id="service-credential",
                expires_at=now + timedelta(hours=1),
            )

    principal = GovernedExecutionAuthenticatorAdapter(ExistingAuthority()).authenticate(
        "service-secret", now=now
    )
    assert principal.principal_id == "service:runner"
    assert principal.policy_version == "existing-policy"


def test_agent_exact_read_and_list_are_registered_without_lifecycle_actions() -> None:
    for grant in (
        ExactGrant(
            "AGENT",
            "READ",
            "agent:agent-definition:quality:agent-revision:v1",
        ),
        ExactGrant("AGENT", "LIST", "agent:collection"),
    ):
        validate_registered_grant(grant, allow_meta=False)

    for action in ("CREATE", "PUBLISH"):
        with pytest.raises(AuthorityError, match="UNKNOWN_AUTHORITY_OPERATION"):
            validate_registered_grant(
                ExactGrant("AGENT", action, "agent:collection"), allow_meta=False
            )


def test_placement_exact_read_is_registered_without_other_actions() -> None:
    validate_registered_grant(
        ExactGrant("PLACEMENT", "READ", "placement:placement:quality"),
        allow_meta=False,
    )
    for action in ("CREATE", "LIST"):
        with pytest.raises(AuthorityError, match="UNKNOWN_AUTHORITY_OPERATION"):
            validate_registered_grant(
                ExactGrant("PLACEMENT", action, "placement:collection"),
                allow_meta=False,
            )
