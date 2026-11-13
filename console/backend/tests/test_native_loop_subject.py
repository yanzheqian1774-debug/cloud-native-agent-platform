"""Legacy administrator admission remains closed without explicit opt-in."""

from types import SimpleNamespace as NS

import pytest
from agent_console.development_administrator import PRINCIPAL
from agent_console.native_loop_subject import (
    configured_subject,
    require_original_subject,
)


def test_legacy_subject_is_unchanged():
    assert configured_subject({"subject": PRINCIPAL}) == PRINCIPAL
    with pytest.raises(ValueError):
        configured_subject({"subject": "human:ordinary"})


@pytest.mark.parametrize(
    "subject",
    [None, "", "human:", " human:ordinary", "human:a b", "service:worker", "*"],
)
def test_opt_in_rejects_invalid_subjects(subject):
    with pytest.raises(ValueError):
        configured_subject(
            {"authorizationMode": "EXACT_ORIGINAL_SUBJECT", "subject": subject}
        )


def test_opt_in_keeps_one_exact_subject():
    subject = configured_subject(
        {"authorizationMode": "EXACT_ORIGINAL_SUBJECT", "subject": "human:ordinary"}
    )
    require_original_subject(subject, NS(principal_id="human:ordinary"))
    for other in [PRINCIPAL, "human:other"]:
        with pytest.raises(ValueError, match="ORIGINAL_SUBJECT_MISMATCH"):
            require_original_subject(subject, NS(principal_id=other))


def test_unknown_mode_fails_closed():
    with pytest.raises(ValueError):
        configured_subject({"authorizationMode": "ALL_USERS", "subject": PRINCIPAL})


def test_runtime_rejects_other_subject_before_owner_or_model_access():
    from agent_console.native_loop_runtime import COMMAND, NativeLoopRuntime

    runtime = NativeLoopRuntime.__new__(NativeLoopRuntime)
    runtime.subject = "human:ordinary"
    token = COMMAND.set(NS(principal_id=PRINCIPAL))
    try:
        with pytest.raises(ValueError, match="ORIGINAL_SUBJECT_MISMATCH"):
            runtime.run("invocation", {}, 1000)
    finally:
        COMMAND.reset(token)
