"""Immutable static-authority generation loading and validation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from agent_console.authority_contracts import (
    AuthorityError,
    AuthorityScope,
    CredentialId,
    ExactGrant,
    GrantSource,
)

SCHEMA_VERSION = "static-authority-generation.v1"
RUNTIME_SCHEMA_VERSION = "authority-foundation-runtime.v1"

OWNER_ACTIONS: dict[str, frozenset[str]] = {
    "BUSINESS_PROBLEM": frozenset({"CREATE", "LIST", "READ", "REVISE", "TRANSITION"}),
    "SUCCESS_CRITERION": frozenset({"CREATE", "READ", "REVISE"}),
    "SUCCESS_CRITERIA_SET": frozenset({"CREATE", "READ", "REVISE"}),
    "PLAN": frozenset({"PREPARE", "READ", "APPROVE"}),
    "WORKFLOW": frozenset({"CREATE", "LIST", "READ"}),
    "AGENT": frozenset({"LIST", "READ"}),
    "EMPLOYEE": frozenset({"CREATE", "LIST", "READ"}),
    "INSTANCE": frozenset({"CREATE", "READ"}),
    "ASSIGNMENT": frozenset({"CREATE", "READ"}),
    "EXECUTION": frozenset({"START", "READ"}),
    "SKILL": frozenset({"INVOKE_SKILL", "READ_SKILL_INVOCATION"}),
    "RESOURCE_USE": frozenset({"READ"}),
    "EVIDENCE": frozenset({"READ_REFERENCE"}),
}

OWNER_RESOURCE_PREFIXES = {
    "BUSINESS_PROBLEM": "business-problem:",
    "SUCCESS_CRITERION": "success-criterion:",
    "SUCCESS_CRITERIA_SET": "success-criteria-set:",
    "PLAN": "plan:",
    "WORKFLOW": "workflow:",
    "AGENT": "agent:",
    "EMPLOYEE": "employee:",
    "INSTANCE": "instance:",
    "ASSIGNMENT": "assignment:",
    "EXECUTION": "governed-execution:",
    "SKILL": "skill-invocation:",
    "RESOURCE_USE": "resource-use:",
    "EVIDENCE": "evidence-reference:",
}

META_OWNERS = frozenset({"GRANT_ADMIN", "CONTINUATION_ASSIGNMENT"})
META_ACTIONS = {
    "GRANT_ADMIN": frozenset({"DECIDE", "REVOKE", "INSPECT"}),
    "CONTINUATION_ASSIGNMENT": frozenset({"ASSIGN"}),
}

BROWSER_BOOTSTRAP_GRANTS = frozenset(
    {
        ("BUSINESS_PROBLEM", "CREATE", "business-problem:collection"),
        ("BUSINESS_PROBLEM", "LIST", "business-problem:collection"),
        ("SUCCESS_CRITERION", "CREATE", "success-criterion:collection"),
        ("WORKFLOW", "CREATE", "workflow:collection"),
        ("WORKFLOW", "LIST", "workflow:collection"),
        ("EMPLOYEE", "CREATE", "employee:collection"),
        ("EMPLOYEE", "LIST", "employee:collection"),
        ("INSTANCE", "CREATE", "instance:collection"),
    }
)


@dataclass(frozen=True, slots=True)
class StaticGrant:
    grant: ExactGrant
    source: GrantSource


@dataclass(frozen=True, slots=True)
class CredentialConfiguration:
    credential_id: CredentialId
    credential_sha256: str
    principal_id: str
    scope: AuthorityScope
    expires_at: datetime
    authentication_source: GrantSource
    grants: tuple[StaticGrant, ...]


@dataclass(frozen=True, slots=True)
class RequestabilityRule:
    owner: str
    action: str
    resource_prefix: str
    purpose: str

    def allows(self, grant: ExactGrant) -> bool:
        return (
            grant.owner == self.owner
            and grant.action == self.action
            and grant.exact_resource.startswith(self.resource_prefix)
        )


@dataclass(frozen=True, slots=True)
class StaticAuthorityGeneration:
    generation: int
    digest: str
    policy_version: str
    audit_source: str
    credentials: tuple[CredentialConfiguration, ...]
    requestability: tuple[RequestabilityRule, ...]
    credential_revocation_tombstones: frozenset[CredentialId]
    static_grant_revocation_tombstones: frozenset[tuple[CredentialId, ExactGrant]] = (
        frozenset()
    )

    def credential(self, digest: str) -> CredentialConfiguration | None:
        return next(
            (item for item in self.credentials if item.credential_sha256 == digest),
            None,
        )

    def credential_by_id(
        self, credential_id: CredentialId
    ) -> CredentialConfiguration | None:
        return next(
            (item for item in self.credentials if item.credential_id == credential_id),
            None,
        )


@dataclass(frozen=True, slots=True)
class AuthorityRuntimeConfiguration:
    database_url: str
    migration_path: Path
    generation_path: Path
    generation_digest: str
    csrf_signing_key_path: Path
    continuation_signing_key_path: Path
    recovery_control_path: Path
    database_fingerprint: str
    operator_id: str

    @classmethod
    def from_mapping(
        cls, configuration: Mapping[str, object]
    ) -> AuthorityRuntimeConfiguration:
        required = {
            "schemaVersion",
            "databaseUrl",
            "migrationPath",
            "generationPath",
            "generationDigest",
            "csrfSigningKeyPath",
            "continuationSigningKeyPath",
            "recoveryControlPath",
            "databaseFingerprint",
            "operatorId",
        }
        if set(configuration) != required or (
            configuration.get("schemaVersion") != RUNTIME_SCHEMA_VERSION
        ):
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        values = [configuration[name] for name in required - {"schemaVersion"}]
        if any(not isinstance(value, str) or not value for value in values):
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        digest = str(configuration["generationDigest"])
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        paths = {
            name: Path(str(configuration[name]))
            for name in (
                "generationPath",
                "migrationPath",
                "csrfSigningKeyPath",
                "continuationSigningKeyPath",
                "recoveryControlPath",
            )
        }
        if any(not path.is_absolute() for path in paths.values()):
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        return cls(
            database_url=str(configuration["databaseUrl"]),
            migration_path=paths["migrationPath"],
            generation_path=paths["generationPath"],
            generation_digest=digest,
            csrf_signing_key_path=paths["csrfSigningKeyPath"],
            continuation_signing_key_path=paths["continuationSigningKeyPath"],
            recovery_control_path=paths["recoveryControlPath"],
            database_fingerprint=str(configuration["databaseFingerprint"]),
            operator_id=str(configuration["operatorId"]),
        )

    @staticmethod
    def read_external_key(path: Path) -> bytes:
        try:
            key = path.read_bytes()
        except OSError as exc:
            raise AuthorityError("AUTHORITY_CONFIGURATION_UNAVAILABLE") from exc
        if len(key) < 32:
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        return key


def parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID") from exc
    if parsed.tzinfo is None:
        raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
    return parsed.astimezone(UTC)


def validate_registered_grant(grant: ExactGrant, *, allow_meta: bool) -> None:
    if grant.owner in META_OWNERS:
        if not allow_meta:
            raise AuthorityError("DYNAMIC_META_GRANT_PROHIBITED")
        prefix = (
            "grant-scope:" if grant.owner == "GRANT_ADMIN" else "continuation-scope:"
        )
        if grant.action not in META_ACTIONS[
            grant.owner
        ] or not grant.exact_resource.startswith(prefix):
            raise AuthorityError("UNKNOWN_AUTHORITY_OPERATION")
        return
    if grant.action not in OWNER_ACTIONS.get(grant.owner, frozenset()):
        raise AuthorityError("UNKNOWN_AUTHORITY_OPERATION")
    if not grant.exact_resource.startswith(OWNER_RESOURCE_PREFIXES[grant.owner]):
        raise AuthorityError("INVALID_GRANT_TARGET")


def _exact_grant(value: object, *, allow_meta: bool) -> ExactGrant:
    required = {"owner", "action", "resource"}
    if (
        not isinstance(value, dict)
        or not required <= set(value)
        or not set(value) <= required | {"source", "purpose"}
    ):
        raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
    try:
        grant = ExactGrant(
            owner=str(value["owner"]),
            action=str(value["action"]),
            exact_resource=str(value["resource"]),
        )
    except (KeyError, TypeError) as exc:
        raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID") from exc
    validate_registered_grant(grant, allow_meta=allow_meta)
    return grant


class StaticAuthorityLoader:
    """Load one digest-addressed immutable generation; publication is not activation."""

    @staticmethod
    def load(path: Path, *, expected_digest: str) -> StaticAuthorityGeneration:
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise AuthorityError("AUTHORITY_GENERATION_UNAVAILABLE") from exc
        digest = hashlib.sha256(raw).hexdigest()
        if len(expected_digest) != 64 or digest != expected_digest:
            raise AuthorityError("AUTHORITY_GENERATION_DIGEST_MISMATCH")
        try:
            document = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID") from exc
        return StaticAuthorityLoader._parse(document, digest=digest)

    @staticmethod
    def _parse(document: object, *, digest: str) -> StaticAuthorityGeneration:
        expected_keys = {
            "schemaVersion",
            "generation",
            "policyVersion",
            "auditSource",
            "credentials",
            "requestability",
            "credentialRevocationTombstones",
            "staticGrantRevocationTombstones",
        }
        if (
            not isinstance(document, dict)
            or set(document) != expected_keys
            or document.get("schemaVersion") != SCHEMA_VERSION
        ):
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        try:
            generation = document["generation"]
            policy_version = document["policyVersion"]
            audit_source = document["auditSource"]
            credential_values = document["credentials"]
            requestability_values = document["requestability"]
            tombstone_values = document["credentialRevocationTombstones"]
            grant_tombstone_values = document["staticGrantRevocationTombstones"]
        except KeyError as exc:
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID") from exc
        if (
            not isinstance(generation, int)
            or generation < 1
            or not isinstance(policy_version, str)
            or not policy_version
            or not isinstance(audit_source, str)
            or not audit_source
            or not isinstance(credential_values, list)
            or not isinstance(requestability_values, list)
            or not isinstance(tombstone_values, list)
            or not isinstance(grant_tombstone_values, list)
        ):
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        credentials = tuple(
            StaticAuthorityLoader._credential(value) for value in credential_values
        )
        requestability = tuple(
            StaticAuthorityLoader._requestability(value)
            for value in requestability_values
        )
        if any(not isinstance(value, str) or not value for value in tombstone_values):
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        tombstones = frozenset(CredentialId(value) for value in tombstone_values)
        grant_tombstones = frozenset(
            StaticAuthorityLoader._grant_tombstone(value)
            for value in grant_tombstone_values
        )
        if len(tombstones) != len(tombstone_values):
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        if len(grant_tombstones) != len(grant_tombstone_values):
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        StaticAuthorityLoader._validate_unique(credentials, requestability)
        return StaticAuthorityGeneration(
            generation=generation,
            digest=digest,
            policy_version=policy_version,
            audit_source=audit_source,
            credentials=credentials,
            requestability=requestability,
            credential_revocation_tombstones=tombstones,
            static_grant_revocation_tombstones=grant_tombstones,
        )

    @staticmethod
    def _credential(value: object) -> CredentialConfiguration:
        if not isinstance(value, dict) or set(value) != {
            "credentialId",
            "credentialSha256",
            "principalId",
            "tenantId",
            "securityDomain",
            "expiresAt",
            "authenticationSource",
            "grants",
        }:
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        try:
            credential_id = CredentialId(value["credentialId"])
            credential_sha256 = value["credentialSha256"]
            principal_id = value["principalId"]
            scope = AuthorityScope(value["tenantId"], value["securityDomain"])
            expires_at = parse_timestamp(value["expiresAt"])
            authentication_source = GrantSource(value["authenticationSource"])
            grants = tuple(
                StaticGrant(
                    _exact_grant(item, allow_meta=True),
                    GrantSource(item["source"]),
                )
                for item in value["grants"]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID") from exc
        scalar_values = (
            credential_id,
            credential_sha256,
            principal_id,
            scope.tenant_id,
            scope.security_domain,
        )
        if any(not isinstance(item, str) or not item for item in scalar_values):
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        if len(credential_sha256) != 64 or any(
            char not in "0123456789abcdef" for char in credential_sha256
        ):
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        if any(grant.source is GrantSource.DYNAMIC for grant in grants):
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        if authentication_source in {GrantSource.DYNAMIC, GrantSource.STATIC_META}:
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        if any(
            grant.grant.owner in META_OWNERS
            and grant.source is not GrantSource.STATIC_META
            for grant in grants
        ):
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        if any(
            grant.grant.owner not in META_OWNERS
            and grant.source is not authentication_source
            for grant in grants
        ):
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        if any(
            grant.source is GrantSource.BROWSER_BOOTSTRAP
            and (
                grant.grant.owner,
                grant.grant.action,
                grant.grant.exact_resource,
            )
            not in BROWSER_BOOTSTRAP_GRANTS
            for grant in grants
        ):
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        grant_keys = [
            (item.grant.owner, item.grant.action, item.grant.exact_resource)
            for item in grants
        ]
        if len(set(grant_keys)) != len(grant_keys):
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        return CredentialConfiguration(
            credential_id,
            credential_sha256,
            principal_id,
            scope,
            expires_at,
            authentication_source,
            grants,
        )

    @staticmethod
    def _requestability(value: object) -> RequestabilityRule:
        if not isinstance(value, dict) or set(value) != {
            "owner",
            "action",
            "resourcePrefix",
            "purpose",
        }:
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        owner = value["owner"]
        action = value["action"]
        prefix = value["resourcePrefix"]
        purpose = value["purpose"]
        if (
            not isinstance(owner, str)
            or action not in OWNER_ACTIONS.get(owner, frozenset())
            or not isinstance(prefix, str)
            or prefix != OWNER_RESOURCE_PREFIXES[owner]
            or any(marker in prefix for marker in "*?[]{}()\\")
            or not isinstance(purpose, str)
            or not purpose
        ):
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        return RequestabilityRule(owner, str(action), prefix, purpose)

    @staticmethod
    def _grant_tombstone(value: object) -> tuple[CredentialId, ExactGrant]:
        if not isinstance(value, dict) or set(value) != {
            "credentialId",
            "owner",
            "action",
            "resource",
        }:
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        credential_id = value["credentialId"]
        if not isinstance(credential_id, str) or not credential_id:
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        grant_value = {
            key: item for key, item in value.items() if key != "credentialId"
        }
        return CredentialId(credential_id), _exact_grant(grant_value, allow_meta=True)

    @staticmethod
    def _validate_unique(
        credentials: tuple[CredentialConfiguration, ...],
        requestability: tuple[RequestabilityRule, ...],
    ) -> None:
        credential_ids = [item.credential_id for item in credentials]
        credential_digests = [item.credential_sha256 for item in credentials]
        if len(set(credential_ids)) != len(credential_ids) or len(
            set(credential_digests)
        ) != len(credential_digests):
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        request_keys = [
            (
                rule.purpose,
                rule.owner,
                rule.action,
                rule.resource_prefix,
            )
            for rule in requestability
        ]
        if len(set(request_keys)) != len(request_keys):
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
