"""Minimal, independently authorized contextual usage disclosure (no dispatch)."""

from .authority_contracts import AuthorityError


def grants(kind, invocation_id):
    return (
        (
            "RESOURCE_USE",
            "READ",
            f"resource-use:contextual-resource-use:{invocation_id}",
        ),
        (
            "EVIDENCE",
            "READ_MEASUREMENT",
            f"evidence-reference:provider-usage:{kind}:{invocation_id}",
        ),
    )


def authorize(require, kind, invocation_id):
    for owner, action, resource in grants(kind, invocation_id):
        require(owner, action, resource)


def unavailable():
    return AuthorityError("PROVIDER_USAGE_NOT_FOUND")


def projection(measurement, pricing, reservation_id, settlement, *, local_cleanup=None):
    # The inputs are owner-produced allowlisted facts, never raw provider bodies.
    return {
        "schemaVersion": "provider-usage-read.v1",
        "measurement": measurement,
        "pricing": pricing,
        "reservationId": reservation_id,
        "settlement": settlement,
        "localCleanup": local_cleanup,
        "remoteCancellation": "NOT_PROVEN",
        "providerInvoice": "NOT_VERIFIED",
    }
