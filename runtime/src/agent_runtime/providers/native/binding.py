"""Deterministic translation from platform intent to Native configuration."""

import re
from collections.abc import Mapping, Sequence

from agent_runtime.providers.native.compatibility import RUNTIME_TARGET
from agent_runtime.providers.native.models import (
    BindingEvidence,
    DesiredRuntimeBinding,
    DiagnosticReason,
    EffectiveRuntimeBinding,
)

SUPPORTED_CONFIGURATION = frozenset(
    {
        "AGENT_DISPLAY_NAME",
        "AGENT_NAME",
        "AGENT_NAMESPACE",
        "AGENT_ROLE",
        "MODEL_NAME",
        "MODEL_PROVIDER",
    }
)
SECRET_MARKERS = frozenset({"apikey", "credential", "password", "secret", "token"})
SECRET_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"),
    re.compile(r"(?i)(?:^|\s)bearer\s+[a-z0-9._~+/=-]{8,}(?:$|\s)"),
    re.compile(
        r"(?i)(?:api[-_ ]?key|credential|password|secret|token)"
        r"\s*[:=]\s*['\"]?[a-z0-9._~+/=-]{8,}"
    ),
    re.compile(r"(?i)(?:^|[^a-z0-9])(?:sk|rk|pk)[-_](?:test[-_])?[a-z0-9]{16,}"),
)


class BindingTranslationError(ValueError):
    def __init__(self, reason: DiagnosticReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


def _is_secret_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", key.casefold())
    return any(marker in normalized for marker in SECRET_MARKERS)


def _is_secret_value(value: str) -> bool:
    """Return whether a string matches a high-confidence secret form."""

    return any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS)


def _contains_secret(value: object, seen: set[int] | None = None) -> bool:
    """Inspect supported containers without converting values to diagnostic text."""

    if isinstance(value, str):
        return _is_secret_value(value)
    if isinstance(value, Mapping):
        seen = set() if seen is None else seen
        identity = id(value)
        if identity in seen:
            return False
        seen.add(identity)
        return any(
            (isinstance(key, str) and _is_secret_key(key))
            or _contains_secret(item, seen)
            for key, item in value.items()
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        seen = set() if seen is None else seen
        identity = id(value)
        if identity in seen:
            return False
        seen.add(identity)
        return any(_contains_secret(item, seen) for item in value)
    return False


def translate_binding(desired: DesiredRuntimeBinding) -> BindingEvidence:
    """Translate without mutating caller-owned binding or configuration."""

    if desired.runtime_target != RUNTIME_TARGET:
        raise BindingTranslationError(
            DiagnosticReason.BINDING_CONFIGURATION_UNSUPPORTED
        )
    if _contains_secret(desired.configuration):
        raise BindingTranslationError(DiagnosticReason.BINDING_SECRET_VALUE_PROHIBITED)
    copied = dict(desired.configuration)
    if not all(isinstance(key, str) for key in copied) or not all(
        isinstance(value, str) for value in copied.values()
    ):
        raise BindingTranslationError(
            DiagnosticReason.BINDING_CONFIGURATION_UNSUPPORTED
        )
    if set(copied) - SUPPORTED_CONFIGURATION:
        raise BindingTranslationError(
            DiagnosticReason.BINDING_CONFIGURATION_UNSUPPORTED
        )
    if copied.get("MODEL_PROVIDER", "mock") != "mock":
        raise BindingTranslationError(
            DiagnosticReason.BINDING_CONFIGURATION_UNSUPPORTED
        )
    effective = {
        "AGENT_NAME": copied.get("AGENT_NAME", "unknown"),
        "AGENT_NAMESPACE": copied.get("AGENT_NAMESPACE", "unknown"),
        "MODEL_NAME": copied.get("MODEL_NAME", "mock-model"),
        "MODEL_PROVIDER": "mock",
    }
    for optional in ("AGENT_DISPLAY_NAME", "AGENT_ROLE"):
        if optional in copied:
            effective[optional] = copied[optional]
    ordered_desired = tuple(sorted(copied.items()))
    return BindingEvidence(
        desired=DesiredRuntimeBinding(
            runtime_target=desired.runtime_target,
            configuration=copied,
        ),
        effective=EffectiveRuntimeBinding(
            runtime_target=RUNTIME_TARGET,
            configuration=tuple(sorted(effective.items())),
        ),
        redacted_desired_configuration=ordered_desired,
    )
