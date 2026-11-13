"""Explicit single-subject Native opt-in; no grants or identity substitution."""

from .development_administrator import PRINCIPAL


def configured_subject(config):
    mode = config.get("authorizationMode", "DEVELOPMENT_ADMIN")
    subject = config.get("subject")
    if mode == "DEVELOPMENT_ADMIN":
        if subject == PRINCIPAL:
            return subject
    elif mode == "EXACT_ORIGINAL_SUBJECT" and (
        isinstance(subject, str)
        and subject.startswith("human:")
        and 6 < len(subject) <= 256
        and subject == subject.strip()
        and not any(character.isspace() for character in subject)
    ):
        return subject
    raise ValueError("NATIVE_LOOP_SUBJECT_CONFIGURATION_INVALID")


def require_original_subject(subject, command):
    if command.principal_id != subject:
        raise ValueError("NATIVE_LOOP_ORIGINAL_SUBJECT_MISMATCH")
