"""Signed, scope-bound keyset cursors for trusted Workbench LIST operations."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass

from agent_console.authority_contracts import TrustedRequestContext
from agent_console.workbench_owner_authorization import WorkbenchOwnerError

_CURSOR_VERSION = "workbench-keyset-cursor.v1"
_SIGNING_DOMAIN = b"workbench-keyset-cursor.v1\x00"


@dataclass(frozen=True, slots=True)
class WorkbenchCursorCodec:
    signing_key: bytes

    def __post_init__(self) -> None:
        if len(self.signing_key) < 32:
            raise ValueError("AUTHORITY_CONFIGURATION_INVALID")

    def mint(
        self,
        *,
        route: str,
        context: TrustedRequestContext,
        page_size: int,
        last_key: tuple[str, ...],
    ) -> str:
        payload = {
            "schemaVersion": _CURSOR_VERSION,
            "route": route,
            "tenantId": context.scope.tenant_id,
            "securityDomain": context.scope.security_domain,
            "pageSize": page_size,
            "lastKey": list(last_key),
        }
        encoded = base64.urlsafe_b64encode(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).rstrip(b"=")
        signature = hmac.new(
            self.signing_key, _SIGNING_DOMAIN + encoded, hashlib.sha256
        ).hexdigest()
        return f"{encoded.decode()}.{signature}"

    def resolve(
        self,
        token: str,
        *,
        route: str,
        context: TrustedRequestContext,
        page_size: int,
        key_size: int,
    ) -> tuple[str, ...]:
        try:
            if not token or len(token) > 2048:
                raise ValueError
            encoded, signature = token.split(".", 1)
            expected = hmac.new(
                self.signing_key,
                _SIGNING_DOMAIN + encoded.encode(),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError
            padding = "=" * (-len(encoded) % 4)
            payload = json.loads(base64.urlsafe_b64decode(encoded + padding))
            if set(payload) != {
                "schemaVersion",
                "route",
                "tenantId",
                "securityDomain",
                "pageSize",
                "lastKey",
            }:
                raise ValueError
            last_key = payload["lastKey"]
            if (
                payload["schemaVersion"] != _CURSOR_VERSION
                or payload["route"] != route
                or payload["tenantId"] != context.scope.tenant_id
                or payload["securityDomain"] != context.scope.security_domain
                or payload["pageSize"] != page_size
                or not isinstance(last_key, list)
                or len(last_key) != key_size
                or any(
                    not isinstance(value, str) or not value or len(value) > 240
                    for value in last_key
                )
            ):
                raise ValueError
            return tuple(last_key)
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise WorkbenchOwnerError("REQUEST_INVALID", 422) from exc
