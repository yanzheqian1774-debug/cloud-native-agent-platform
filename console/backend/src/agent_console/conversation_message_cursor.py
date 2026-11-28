"""Bounded keyset navigation only; a cursor never grants conversation access."""

import base64
import binascii
import json

from .private_conversation import ConversationError


def encode_cursor(scope, ceiling, before, *, inclusive=False):
    raw = json.dumps(
        {
            "v": 1,
            "scope": list(scope),
            "ceiling": ceiling,
            "before": before,
            **({"inclusive": True} if inclusive else {}),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(value, scope):
    if value is None:
        return None
    try:
        if not isinstance(value, str) or not 1 <= len(value) <= 4096:
            raise ValueError
        raw = base64.b64decode(
            value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
        )
        result = json.loads(raw)
        if not isinstance(result, dict) or set(result) not in (
            {"v", "scope", "ceiling", "before"},
            {"v", "scope", "ceiling", "before", "inclusive"},
        ):
            raise ValueError
        if "inclusive" in result and result["inclusive"] is not True:
            raise ValueError
        if (
            type(result["v"]) is not int
            or result["v"] != 1
            or result["scope"] != list(scope)
        ):
            raise ValueError
        for name in ("ceiling", "before"):
            item = result[name]
            if not isinstance(item, list) or len(item) != 2:
                raise ValueError
            if type(item[0]) is not int or not 0 < item[0] <= 9223372036854775807:
                raise ValueError
            if not isinstance(item[1], str) or not 1 <= len(item[1]) <= 200:
                raise ValueError
        if tuple(result["before"]) > tuple(result["ceiling"]):
            raise ValueError
        return result
    except (ValueError, TypeError, KeyError, binascii.Error, UnicodeError) as exc:
        raise ConversationError("CONVERSATION_PAGE_INVALID", 422) from exc
