"""Deterministic translation from platform intent to Native configuration."""

import re
from collections.abc import Mapping, Sequence
from enum import Enum

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
    re.compile(
        r"(?i)(?:^|\s)bearer\s+"
        r"(?=[a-z0-9._~+/=-]*[0-9._~+/=-])[a-z0-9._~+/=-]{8,}(?:$|\s)"
    ),
    re.compile(
        r"(?i)(?:api[-_ ]?key|credential|password|secret|token)"
        r"\s*[:=]\s*['\"]?[a-z0-9._~+/=-]{8,}"
    ),
    re.compile(r"(?i)(?:^|[^a-z0-9])(?:sk|rk|pk)[-_](?:test[-_])?[a-z0-9]{16,}"),
)
MAX_CONFIGURATION_DEPTH = 32
MAX_CONFIGURATION_NODES = 4096
MAX_CONFIGURATION_STRING_LENGTH = 65_536
MAX_CONFIGURATION_TOTAL_CHARACTERS = 262_144


class _SecretScanResult(Enum):
    CLEAN = "clean"
    SECRET = "secret"
    UNSUPPORTED = "unsupported"


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


def _scan_secret_boundary(value: object) -> _SecretScanResult:
    """Inspect bounded containers without repr or recursive Python calls."""

    stack = [(value, 0)]
    seen: set[int] = set()
    nodes = 0
    total_characters = 0
    unsupported = False

    try:
        while stack:
            item, depth = stack.pop()
            nodes += 1
            if nodes > MAX_CONFIGURATION_NODES:
                return _SecretScanResult.UNSUPPORTED
            if isinstance(item, str):
                total_characters += len(item)
                if (
                    len(item) > MAX_CONFIGURATION_STRING_LENGTH
                    or total_characters > MAX_CONFIGURATION_TOTAL_CHARACTERS
                ):
                    return _SecretScanResult.UNSUPPORTED
                if _is_secret_value(item):
                    return _SecretScanResult.SECRET
                continue
            if isinstance(item, Mapping):
                identity = id(item)
                if identity in seen or depth >= MAX_CONFIGURATION_DEPTH:
                    unsupported = True
                    continue
                seen.add(identity)
                for key, nested in item.items():
                    if not isinstance(key, str):
                        unsupported = True
                    else:
                        total_characters += len(key)
                        if (
                            len(key) > MAX_CONFIGURATION_STRING_LENGTH
                            or total_characters > MAX_CONFIGURATION_TOTAL_CHARACTERS
                        ):
                            return _SecretScanResult.UNSUPPORTED
                        if _is_secret_key(key):
                            return _SecretScanResult.SECRET
                    stack.append((nested, depth + 1))
                    if len(stack) + nodes > MAX_CONFIGURATION_NODES:
                        return _SecretScanResult.UNSUPPORTED
                continue
            if isinstance(item, Sequence) and not isinstance(
                item, (str, bytes, bytearray)
            ):
                identity = id(item)
                if identity in seen or depth >= MAX_CONFIGURATION_DEPTH:
                    unsupported = True
                    continue
                seen.add(identity)
                for nested in item:
                    stack.append((nested, depth + 1))
                    if len(stack) + nodes > MAX_CONFIGURATION_NODES:
                        return _SecretScanResult.UNSUPPORTED
                continue
            unsupported = True
    except Exception:
        return _SecretScanResult.UNSUPPORTED

    if unsupported:
        return _SecretScanResult.UNSUPPORTED
    return _SecretScanResult.CLEAN


def translate_binding(desired: DesiredRuntimeBinding) -> BindingEvidence:
    """Translate without mutating caller-owned binding or configuration."""

    if desired.runtime_target != RUNTIME_TARGET:
        raise BindingTranslationError(
            DiagnosticReason.BINDING_CONFIGURATION_UNSUPPORTED
        )
    scan = _scan_secret_boundary(desired.configuration)
    if scan is _SecretScanResult.SECRET:
        raise BindingTranslationError(DiagnosticReason.BINDING_SECRET_VALUE_PROHIBITED)
    if scan is _SecretScanResult.UNSUPPORTED:
        raise BindingTranslationError(
            DiagnosticReason.BINDING_CONFIGURATION_UNSUPPORTED
        )
    try:
        copied = dict(desired.configuration)
    except Exception:
        raise BindingTranslationError(
            DiagnosticReason.BINDING_CONFIGURATION_UNSUPPORTED
        ) from None
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
