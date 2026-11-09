"""Bounded Responses SSE decoding; previews never authorize or execute work."""

import contextvars
import json
import time

SINK = contextvars.ContextVar("response_stream_sink", default=None)


def emit(value):
    sink = SINK.get()
    if sink is not None:
        sink(value)


def preview(text):
    """Lex JSON strings, exposing only business field values, never reasoning."""
    values, key, previous, i = [], None, "", 0
    while i < len(text) and len(values) < 12:
        if text[i].isspace():
            i += 1
            continue
        if text[i] != '"':
            previous = text[i]
            i += 1
            continue
        start = i
        i += 1
        while i < len(text):
            if text[i] == "\\":
                i += 2
            elif text[i] == '"':
                i += 1
                break
            else:
                i += 1
        token = text[start:i]
        complete = token.endswith('"') and len(token) > 1
        try:
            value = json.loads(token if complete else token + '"')
        except ValueError:
            # A chunk may end halfway through a unicode escape or escaped quote.
            value = ""
        if (
            previous == ":"
            and key
            in {"title", "description", "clarificationQuestion", "responsibility"}
            and value
        ):
            values.append(value[:2000])
        key = value if previous in {"{", ","} else None
        previous = "string"
    return "\n".join(values)[:6000]


def read_response(response, configuration, progress):
    """Accept exactly one completed response. EOF/deltas alone are UNKNOWN."""
    limit = configuration.maximum_response_bytes
    if not 200 <= response.status < 300 or "text/event-stream" not in (
        response.getheader("content-type") or ""
    ):
        return response.read(limit + 1)
    data, wire, text, count, previous = [], 0, "", 0, None
    started = time.monotonic()
    last_emit = 0.0
    while True:
        line = response.readline(limit + 1)
        wire += len(line)
        if not line or wire > limit * 8 or len(line) > limit:
            raise OSError("RESPONSE_STREAM_INCOMPLETE_OR_OVERSIZED")
        if line.strip():
            if line.startswith(b"data:"):
                data.append(line[5:].strip())
            continue
        if not data:
            continue
        raw = b"\n".join(data)
        data = []
        if raw == b"[DONE]":
            raise OSError("RESPONSE_STREAM_COMPLETION_MISSING")
        event = json.loads(raw)
        if not isinstance(event, dict):
            raise OSError("RESPONSE_STREAM_INVALID")
        count += 1
        kind = event.get("type")
        if count == 1:
            progress(
                {
                    "kind": "stream",
                    "eventCount": count,
                    "characters": 0,
                    "preview": "",
                    "elapsedMs": int((time.monotonic() - started) * 1000),
                }
            )
        if kind == "response.output_text.delta":
            delta = event.get("delta")
            if not isinstance(delta, str):
                raise OSError("RESPONSE_STREAM_INVALID")
            text += delta
            if len(text.encode()) > limit:
                raise OSError("RESPONSE_STREAM_OVERSIZED")
            now = time.monotonic()
            if now - last_emit < 0.1:
                continue
            visible = preview(text)
            if visible != previous or now - last_emit >= 0.5:
                progress(
                    {
                        "kind": "stream",
                        "eventCount": count,
                        "characters": len(text),
                        "preview": visible,
                        "elapsedMs": int((time.monotonic() - started) * 1000),
                    }
                )
                previous = visible
                last_emit = now
        elif kind == "response.completed":
            body = event.get("response")
            if not isinstance(body, dict) or body.get("status") != "completed":
                raise OSError("RESPONSE_STREAM_INVALID_COMPLETION")
            encoded = json.dumps(body, ensure_ascii=False).encode()
            if len(encoded) > limit:
                raise OSError("RESPONSE_STREAM_OVERSIZED")
            progress(
                {
                    "kind": "stream",
                    "eventCount": count,
                    "characters": len(text),
                    "preview": preview(text),
                    "completed": True,
                    "elapsedMs": int((time.monotonic() - started) * 1000),
                }
            )
            return encoded
        elif kind in {"error", "response.failed", "response.incomplete"}:
            raise OSError("RESPONSE_STREAM_INCOMPLETE")
