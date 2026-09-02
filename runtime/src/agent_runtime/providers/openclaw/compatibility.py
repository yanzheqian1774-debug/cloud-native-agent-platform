"""Exact OpenClaw target selected by S5-SPIKE-005 RTM02."""

from agent_runtime.providers.openclaw.models import ExactTarget, ReasonCode

EXACT_TARGET = ExactTarget(
    version="2026.7.1-2",
    tag_commit="0790d9f593ad30c940ed93b5872a8cf6d6f3cf8c",
    package_integrity=(
        "sha512-ycF3yPcbjN6bUPeaUx6Mh6vze1hQWoD3CT/wWcmD7a8xaHHHRUaAlaq+"
        "lFxMHf1ssEgODVAwjlzYqp2twkYZ7g=="
    ),
)


def validate_target(observed: ExactTarget) -> ReasonCode:
    if (
        observed.version != EXACT_TARGET.version
        or observed.tag_commit != EXACT_TARGET.tag_commit
    ):
        return ReasonCode.VERSION_UNSUPPORTED
    if observed.package_integrity != EXACT_TARGET.package_integrity:
        return ReasonCode.PACKAGE_INTEGRITY_MISMATCH
    return ReasonCode.EXACT_VERSION_READY
