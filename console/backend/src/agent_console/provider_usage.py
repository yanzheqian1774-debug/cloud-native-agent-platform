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


class ProviderUsageGrantTargetValidator:
    """Only canonical, already recorded targets may be requested; never grants."""

    def __init__(self, understanding=None, planning=None):
        self.owners = {"understanding": understanding, "planning": planning}

    def is_known_exact_target(self, context, grant, *, connection=None):
        if connection is None:
            return False
        measurement = grant.owner == "EVIDENCE" and grant.action == "READ_MEASUREMENT"
        if measurement:
            for kind, owner in self.owners.items():
                prefix = f"evidence-reference:provider-usage:{kind}:"
                if grant.exact_resource.startswith(prefix):
                    identity = grant.exact_resource[len(prefix) :]
                    return bool(
                        identity
                        and owner is not None
                        and owner.has_usage_target(
                            connection, context.scope, identity, measurement=True
                        )
                    )
            return False
        prefix = "resource-use:contextual-resource-use:"
        if (grant.owner, grant.action) != (
            "RESOURCE_USE",
            "READ",
        ) or not grant.exact_resource.startswith(prefix):
            return False
        identity = grant.exact_resource[len(prefix) :]
        return bool(identity) and any(
            owner is not None
            and owner.has_usage_target(
                connection, context.scope, identity, measurement=False
            )
            for owner in self.owners.values()
        )
