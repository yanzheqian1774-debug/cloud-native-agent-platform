"""Allowlisted Responses metering; total tokens already include cached/reasoning."""

import re

from .business_problem_domain import canonical_digest
from .draft_assistance import ObservationState, ProviderObservation


def _identity(value):
    return (
        value
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9._:-]{1,200}", value)
        else None
    )


def _count(value):
    return value if type(value) is int and 0 <= value <= 1_000_000_000 else None


def measurement(response, correlation, invocation_id, latency, configuration):
    response = response if isinstance(response, dict) else {}
    raw = response.get("usage")
    raw = raw if isinstance(raw, dict) else {}
    usage = {
        key: _count(raw.get(key))
        for key in ("input_tokens", "output_tokens", "total_tokens")
    }
    for parent, child in (
        ("input_tokens_details", "cached_tokens"),
        ("output_tokens_details", "reasoning_tokens"),
    ):
        detail = raw.get(parent)
        usage[child] = _count(detail.get(child)) if isinstance(detail, dict) else None
    i, o, c, r, total = (
        usage[k]
        for k in (
            "input_tokens",
            "output_tokens",
            "cached_tokens",
            "reasoning_tokens",
            "total_tokens",
        )
    )
    reliable = (
        i is not None
        and o is not None
        and i > 0
        and (c is None or c <= i)
        and (r is None or r <= o)
        and (total is None or total == i + o)
        and i <= configuration.maximum_input_tokens
        and o <= configuration.maximum_output_tokens
        and response.get("model") == configuration.native_model_id
        and response.get("status") in {"completed", "incomplete", "failed"}
    )
    # Missing optional fields are distinct from malformed supplied fields.
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        if key in raw and _count(raw[key]) is None:
            reliable = False
    for parent, child in (
        ("input_tokens_details", "cached_tokens"),
        ("output_tokens_details", "reasoning_tokens"),
    ):
        if parent in raw and (
            not isinstance(raw[parent], dict)
            or (child in raw[parent] and _count(raw[parent][child]) is None)
        ):
            reliable = False
    return {
        "local_request_id": invocation_id,
        "provider_request_id": _identity(correlation)
        if correlation != f"http-200-{invocation_id}"
        and not correlation.startswith("http-")
        else None,
        "provider_response_id": _identity(response.get("id")),
        "configured_model": configuration.native_model_id,
        "returned_model": _identity(response.get("model")),
        "provider_status": response.get("status")
        if response.get("status")
        in {"completed", "incomplete", "failed", "queued", "in_progress"}
        else "UNKNOWN",
        "usage": usage,
        "settleable": reliable,
        "metering": "OPENAI_RESPONSES_V1_TOTALS_INCLUDE_DETAILS",
        "latency_ms": latency,
    }


def settle(budget, invocation_id, receipt):
    """Recover from the immutable receipt, never from another provider dispatch."""
    m = receipt.get("measurement", {})
    if not m.get("settleable"):
        return {"status": "PENDING_RECONCILIATION", "reservation_retained": True}
    usage = m["usage"]
    observation = ProviderObservation(
        "planning-usage:" + canonical_digest(m),
        ObservationState.UNKNOWN,
        reason_code="USAGE_ONLY_NOT_BUSINESS_STATUS",
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
    )
    return budget.settle(invocation_id, receipt["reservation_id"], observation)
