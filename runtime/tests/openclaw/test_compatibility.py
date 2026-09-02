from agent_runtime.providers.openclaw.compatibility import EXACT_TARGET, validate_target
from agent_runtime.providers.openclaw.models import ExactTarget, ReasonCode


def test_exact_durable_target_is_ready() -> None:
    assert EXACT_TARGET.version == "2026.7.1-2"
    assert EXACT_TARGET.tag_commit == "0790d9f593ad30c940ed93b5872a8cf6d6f3cf8c"
    assert validate_target(EXACT_TARGET) is ReasonCode.EXACT_VERSION_READY


def test_version_and_integrity_mismatch_fail_closed() -> None:
    wrong_version = ExactTarget(
        "2026.7.2", EXACT_TARGET.tag_commit, EXACT_TARGET.package_integrity
    )
    wrong_integrity = ExactTarget(
        EXACT_TARGET.version, EXACT_TARGET.tag_commit, "sha512-not-authorized"
    )
    assert validate_target(wrong_version) is ReasonCode.VERSION_UNSUPPORTED
    assert validate_target(wrong_integrity) is ReasonCode.PACKAGE_INTEGRITY_MISMATCH
