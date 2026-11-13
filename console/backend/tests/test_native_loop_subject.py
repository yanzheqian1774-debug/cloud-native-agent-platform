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


@pytest.mark.parametrize("credential", [None, "", "*", "bad credential"])
def test_service_mode_requires_explicit_credential_binding(credential):
    with pytest.raises(ValueError, match="SERVICE_CREDENTIAL_REQUIRED"):
        configured_subject(
            dict(
                authorizationMode="EXACT_SERVICE_SUBJECT",
                subject="service:fixed-work",
                serviceCredentialId=credential,
            )
        )


def test_service_is_exact_identity_and_never_browser_impersonation():
    subject = configured_subject(
        dict(
            authorizationMode="EXACT_SERVICE_SUBJECT",
            subject="service:fixed-work",
            serviceCredentialId="credential:service-one",
        )
    )
    command = NS(
        principal_id=subject,
        credential_id="credential:service-one",
        authentication_source="SERVICE_CREDENTIAL",
    )
    require_original_subject(
        subject, command, service_credential_id="credential:service-one"
    )
    for changes in [
        dict(credential_id="other"),
        dict(authentication_source="BROWSER_SESSION"),
        dict(principal_id="human:ordinary"),
    ]:
        changed = NS(**(vars(command) | changes))
        with pytest.raises(ValueError):
            require_original_subject(
                subject, changed, service_credential_id="credential:service-one"
            )
    with pytest.raises(ValueError, match="SERVICE_CREDENTIAL_MISMATCH"):
        require_original_subject(subject, command)


def test_service_runtime_rejects_browser_before_owner_or_model_access():
    from agent_console.native_loop_runtime import COMMAND, NativeLoopRuntime

    runtime = NativeLoopRuntime.__new__(NativeLoopRuntime)
    runtime.subject = "service:fixed-work"
    runtime.service_credential_id = "credential:service-one"
    token = COMMAND.set(
        NS(
            principal_id=runtime.subject,
            credential_id=runtime.service_credential_id,
            authentication_source="BROWSER_SESSION",
        )
    )
    try:
        with pytest.raises(ValueError, match="SERVICE_CREDENTIAL_MISMATCH"):
            runtime.run("invocation", {}, 1000)
    finally:
        COMMAND.reset(token)
