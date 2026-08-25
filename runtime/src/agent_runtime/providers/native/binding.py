"""Deterministic translation from platform intent to Native configuration."""

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
SECRET_MARKERS = ("api_key", "credential", "password", "secret", "token")


class BindingTranslationError(ValueError):
    def __init__(self, reason: DiagnosticReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


def _is_secret_key(key: str) -> bool:
    normalized = key.casefold()
    return any(marker in normalized for marker in SECRET_MARKERS)


def translate_binding(desired: DesiredRuntimeBinding) -> BindingEvidence:
    """Translate without mutating caller-owned binding or configuration."""

    if desired.runtime_target != RUNTIME_TARGET:
        raise BindingTranslationError(
            DiagnosticReason.BINDING_CONFIGURATION_UNSUPPORTED
        )
    copied = dict(desired.configuration)
    if any(_is_secret_key(key) for key in copied):
        raise BindingTranslationError(DiagnosticReason.BINDING_SECRET_VALUE_PROHIBITED)
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
