"""Explicit single-subject Native opt-in; no grants or identity substitution."""

from .development_administrator import PRINCIPAL


def configured_subject(config):
    mode = config.get("authorizationMode", "DEVELOPMENT_ADMIN")
    subject = config.get("subject")
    if mode == "DEVELOPMENT_ADMIN":
        if subject == PRINCIPAL:
            return subject
    elif (
        mode == "EXACT_ORIGINAL_SUBJECT"
        and (
            isinstance(subject, str)
            and subject.startswith("human:")
            and 6 < len(subject) <= 256
            and subject == subject.strip()
            and not any(character.isspace() for character in subject)
        )
    ) or (
        mode == "EXACT_SERVICE_SUBJECT"
        and (
            isinstance(subject, str)
            and subject.startswith("service:")
            and 8 < len(subject) <= 256
            and subject == subject.strip()
            and not any(character.isspace() for character in subject)
            and configured_service_credential(config) is not None
        )
    ):
        return subject
    raise ValueError("NATIVE_LOOP_SUBJECT_CONFIGURATION_INVALID")


def configured_service_credential(config):
    if config.get("authorizationMode") != "EXACT_SERVICE_SUBJECT":
        return None
    credential = config.get("serviceCredentialId")
    if (
        not isinstance(credential, str)
        or not 1 <= len(credential) <= 256
        or any(character.isspace() for character in credential)
        or credential == "*"
    ):
        raise ValueError("NATIVE_LOOP_SERVICE_CREDENTIAL_REQUIRED")
    return credential


def require_original_subject(subject, command, *, service_credential_id=None):
    if command.principal_id != subject:
        raise ValueError("NATIVE_LOOP_ORIGINAL_SUBJECT_MISMATCH")
    if subject.startswith("service:") and (
        service_credential_id is None
        or getattr(command, "credential_id", None) != service_credential_id
        or getattr(command, "authentication_source", None) != "SERVICE_CREDENTIAL"
    ):
        raise ValueError("NATIVE_LOOP_SERVICE_CREDENTIAL_MISMATCH")
