"""Private, bounded non-2xx metadata; never a raw-body logging facility."""

from __future__ import annotations

import base64
import json
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import quote

FIELD_LIMIT = 512
ERROR_IDENTIFIERS = frozenset(
    {
        "content_filter",
        "invalid_request_error",
        "invalid_authentication_error",
        "incorrect_api_key_error",
        "permission_denied_error",
        "resource_not_found_error",
        "engine_overloaded_error",
        "exceeded_current_quota_error",
        "rate_limit_reached_error",
        "rate_limit_exceeded",
        "insufficient_quota",
        "client_closed_request",
        "server_error",
        "unexpected_output",
        "server_unavailable",
    }
)
SAFE_MESSAGES = frozenset(
    {
        "The engine is currently overloaded, please try again later",
        "The request was rejected because it was considered high risk",
        "Invalid Authentication",
        "Incorrect API key provided",
        "The API you are accessing is not open",
        "Your IP is not allowed to access this organization",
        "Input token length too long",
    }
)


def _field(value, *, secret, allowed):
    result = {
        "value": None,
        "missing": value is None,
        "discarded": False,
        "truncated": False,
    }
    if value is None:
        return result
    if not isinstance(value, str):
        result["discarded"] = True
        return result
    result["truncated"] = len(value) > FIELD_LIMIT
    # Check BEFORE truncation/normalization. Unknown free text cannot be proven
    # safe and is discarded, including encoded credentials and prompt echoes.
    secret_forms = (
        (
            secret,
            quote(secret, safe=""),
            secret.encode().hex(),
            base64.b64encode(secret.encode()).decode(),
            base64.urlsafe_b64encode(secret.encode()).decode().rstrip("="),
        )
        if secret
        else ()
    )
    if (
        len(value) > FIELD_LIMIT
        or any(form in value for form in secret_forms)
        or not allowed(value)
    ):
        result["discarded"] = True
    else:
        result["value"] = value
    return result


def _request_id(value):
    # Provider-generated opaque IDs only, never arbitrary printable strings.
    return bool(
        re.fullmatch(
            r"(?:[0-9a-fA-F]{24,64}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}"
            r"|req[_-][A-Za-z0-9_-]{8,96})",
            value,
        )
    ) and not re.search(r"(?i)bearer|secret|sk[-_]|api[-_]?key", value)


def _retry_after(value):
    if re.fullmatch(r"[0-9]{1,8}", value):
        return True
    if not re.fullmatch(
        r"[A-Za-z]{3}, [0-9]{2} [A-Za-z]{3} [0-9]{4} "
        r"[0-9]{2}:[0-9]{2}:[0-9]{2} GMT",
        value,
    ):
        return False
    try:
        return parsedate_to_datetime(value).utcoffset().total_seconds() == 0
    except (ValueError, TypeError, AttributeError):
        return False


def non2xx_diagnostic(
    *, status, host, path, latency_ms, headers, body, maximum_body_bytes, secret
):
    """Only callers' allowlisted headers are inspected; no raw input retained."""
    request_id = _field(headers.get("x-request-id"), secret=secret, allowed=_request_id)
    retry = _field(headers.get("retry-after"), secret=secret, allowed=_retry_after)
    truncated = len(body) > maximum_body_bytes
    parse_failed = False
    error = {}
    if not truncated:
        try:
            document = json.loads(body)
            if not isinstance(document, dict) or not isinstance(
                document.get("error"), dict
            ):
                parse_failed = True
            else:
                error = document["error"]
        except (ValueError, UnicodeError, RecursionError):
            parse_failed = True
    return {
        "http_status": status,
        "received_at_utc": datetime.now(UTC).isoformat(),
        "host": host,
        "path": path,
        "latency_ms": latency_ms,
        "provider_request_id": request_id,
        "provider_request_id_header": "x-request-id" if request_id["value"] else None,
        "retry_after": retry,
        "error": {
            key: _field(
                error.get(key),
                secret=secret,
                allowed=(
                    SAFE_MESSAGES if key == "message" else ERROR_IDENTIFIERS
                ).__contains__,
            )
            for key in ("type", "code", "message")
        },
        "body_missing": not body,
        "body_truncated": truncated,
        "parse_failed": parse_failed,
    }
