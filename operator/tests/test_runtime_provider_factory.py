import pytest
from agent_operator.runtime_provider_factory import (
    REGISTRATIONS,
    RuntimeProviderFactory,
    RuntimeProviderFactoryError,
    RuntimeProviderKind,
)


class Adapter:
    def __init__(self, kind):
        self.provider_kind = kind


def test_factory_requires_one_explicit_known_provider() -> None:
    factory = RuntimeProviderFactory(
        native=Adapter(RuntimeProviderKind.NATIVE),
        openclaw=Adapter(RuntimeProviderKind.OPENCLAW),
    )
    assert factory.create(("native",)).provider_kind is RuntimeProviderKind.NATIVE
    assert factory.create(("openclaw",)).provider_kind is RuntimeProviderKind.OPENCLAW
    for configured, code in (
        ((), "RUNTIME_PROVIDER_MISSING"),
        (("native", "openclaw"), "RUNTIME_PROVIDER_AMBIGUOUS"),
        (("mock",), "RUNTIME_PROVIDER_UNKNOWN"),
    ):
        with pytest.raises(RuntimeProviderFactoryError, match=code):
            factory.create(configured)


def test_registration_descriptor_is_deterministic_and_track_270_ready() -> None:
    assert RuntimeProviderFactory.registrations() is REGISTRATIONS
    assert tuple(item.provider for item in REGISTRATIONS) == (
        RuntimeProviderKind.NATIVE,
        RuntimeProviderKind.OPENCLAW,
    )
    assert REGISTRATIONS[1].exact_version == "2026.7.1-2"


def test_factory_rejects_missing_or_conflicting_registration() -> None:
    with pytest.raises(RuntimeProviderFactoryError, match="NOT_REGISTERED"):
        RuntimeProviderFactory().create(("native",))
    with pytest.raises(RuntimeProviderFactoryError, match="REGISTRATION_CONFLICT"):
        RuntimeProviderFactory(native=Adapter(RuntimeProviderKind.OPENCLAW)).create(
            ("native",)
        )
