from datetime import UTC, datetime, timedelta

import pytest
from agent_console.model_binding_resolution import (
    AuthorizedModelUse,
    ExactModelBinding,
    ExactModelUse,
    ModelBindingResolutionFailure,
    ModelConsumptionScope,
    ModelUseAction,
    ModelUseSubject,
    ResolvedModelBinding,
    resolve_authorized_model_binding,
)
from agent_console.model_governance import (
    ConnectionProfileRevisionIdentity,
    EndpointRevisionIdentity,
    ModelEligibility,
    ModelEligibilityState,
    ModelLifecycleHighWater,
    ModelRevisionIdentity,
    ModelScope,
    ProviderRevisionIdentity,
)

SCOPE = ModelConsumptionScope("tenant-a", "quality")
SUBJECT = ModelUseSubject("employee:17")
BINDING = ExactModelBinding("model:reviewer", "model-revision:7", "a" * 64)
USE = ExactModelUse(
    BINDING,
    ModelUseAction.BIND_MODEL,
    "model:binding:AGENT:agent:17:revision:4:"
    f"{BINDING.resource_id}:{BINDING.revision_id}:{BINDING.digest}",
)
NOW = datetime(2026, 9, 12, 9, tzinfo=UTC)


class RecordingAuthorizer:
    def __init__(self, events, result=True):
        self.events = events
        self.result = result

    def authorize_use(self, scope, subject, use):
        self.events.append(("authorize", scope, subject, use))
        if not self.result:
            return None
        if isinstance(self.result, AuthorizedModelUse):
            return self.result
        return authorization()


class RecordingResolver:
    def __init__(self, events, result=None):
        self.events = events
        self.result = result

    def resolve_exact(self, scope, binding):
        self.events.append(("resolve", scope, binding))
        return self.result or resolution()


def authorization(**changes):
    values = {
        "decision_id": "decision:1",
        "subject": SUBJECT,
        "scope": SCOPE,
        "use": USE,
        "policy_generation": 7,
        "policy_version": "policy:7",
        "issued_at": NOW - timedelta(minutes=1),
        "expires_at": NOW + timedelta(minutes=1),
    }
    values.update(changes)
    return AuthorizedModelUse(**values)


def eligibility(**changes):
    values = {
        "scope": ModelScope(SCOPE.namespace, SCOPE.security_domain),
        "model": ModelRevisionIdentity(
            BINDING.resource_id, BINDING.revision_id, BINDING.digest
        ),
        "state": ModelEligibilityState.PUBLISHED_ENABLED,
        "high_water": ModelLifecycleHighWater(3, "fact:3", "f" * 64),
    }
    values.update(changes)
    return ModelEligibility(**values)


def resolution(**changes):
    values = {
        "scope": SCOPE,
        "binding": BINDING,
        "provider": ProviderRevisionIdentity("provider:1", "revision:1", "b" * 64),
        "endpoint": EndpointRevisionIdentity("endpoint:1", "revision:1", "c" * 64),
        "connection_profile": ConnectionProfileRevisionIdentity(
            "profile:1", "revision:1", "d" * 64
        ),
        "eligibility": eligibility(),
    }
    values.update(changes)
    return ResolvedModelBinding(**values)


def resolve(authorizer, resolver, *, evaluation_time=NOW):
    return resolve_authorized_model_binding(
        SCOPE,
        SUBJECT,
        USE,
        authorizer=authorizer,
        resolver=resolver,
        evaluation_time=evaluation_time,
    )


def test_exact_authorized_binding_returns_secret_free_owner_readback() -> None:
    events = []
    result = resolve(RecordingAuthorizer(events), RecordingResolver(events))

    assert result.binding == BINDING
    assert result.provider.provider_id == "provider:1"
    assert result.eligibility.high_water.ordinal == 3
    assert [event[0] for event in events] == ["authorize", "resolve"]
    assert not hasattr(result, "credentials")


def test_denial_precedes_and_suppresses_protected_lookup() -> None:
    events = []
    with pytest.raises(ModelBindingResolutionFailure, match="MODEL_BINDING_NOT_FOUND"):
        resolve(RecordingAuthorizer(events, False), RecordingResolver(events))
    assert [event[0] for event in events] == ["authorize"]


def test_absent_authority_fails_before_resolver() -> None:
    events = []
    with pytest.raises(
        ModelBindingResolutionFailure, match="MODEL_AUTHORIZATION_UNAVAILABLE"
    ):
        resolve(None, RecordingResolver(events))
    assert events == []


def test_absent_resolver_is_checked_only_after_authorization() -> None:
    events = []
    with pytest.raises(
        ModelBindingResolutionFailure, match="MODEL_RESOLVER_UNAVAILABLE"
    ):
        resolve(RecordingAuthorizer(events), None)
    assert [event[0] for event in events] == ["authorize"]


@pytest.mark.parametrize(
    "current,reason",
    [
        (
            authorization(scope=ModelConsumptionScope("tenant-b", "quality")),
            "MODEL_AUTHORIZATION_INVALID",
        ),
        (
            authorization(subject=ModelUseSubject("employee:other")),
            "MODEL_AUTHORIZATION_INVALID",
        ),
        (
            authorization(
                use=ExactModelUse(
                    (
                        other_binding := ExactModelBinding(
                            "model:other", BINDING.revision_id, BINDING.digest
                        )
                    ),
                    ModelUseAction.BIND_MODEL,
                    "model:binding:AGENT:agent:17:revision:4:"
                    f"{other_binding.resource_id}:{other_binding.revision_id}:"
                    f"{other_binding.digest}",
                )
            ),
            "MODEL_AUTHORIZATION_INVALID",
        ),
        (
            authorization(expires_at=NOW),
            "MODEL_AUTHORIZATION_INVALID",
        ),
    ],
)
def test_authorization_binds_complete_current_use(current, reason) -> None:
    events = []
    with pytest.raises(ModelBindingResolutionFailure, match=reason):
        resolve(RecordingAuthorizer(events, current), RecordingResolver(events))
    assert [event[0] for event in events] == ["authorize"]


@pytest.mark.parametrize(
    "resolved,reason",
    [
        (
            resolution(scope=ModelConsumptionScope("tenant-b", "quality")),
            "MODEL_SCOPE_MISMATCH",
        ),
        (
            resolution(
                binding=ExactModelBinding(
                    "model:other", BINDING.revision_id, BINDING.digest
                )
            ),
            "MODEL_IDENTITY_MISMATCH",
        ),
        (
            resolution(
                binding=ExactModelBinding(
                    BINDING.resource_id, "model-revision:8", BINDING.digest
                )
            ),
            "MODEL_REVISION_MISMATCH",
        ),
        (
            resolution(
                binding=ExactModelBinding(
                    BINDING.resource_id, BINDING.revision_id, "e" * 64
                )
            ),
            "MODEL_DIGEST_MISMATCH",
        ),
        (
            resolution(
                eligibility=eligibility(
                    model=ModelRevisionIdentity(
                        BINDING.resource_id, "model-revision:8", BINDING.digest
                    )
                )
            ),
            "MODEL_ELIGIBILITY_MISMATCH",
        ),
        (
            resolution(
                eligibility=eligibility(state=ModelEligibilityState.PUBLISHED_DISABLED)
            ),
            "MODEL_INELIGIBLE",
        ),
    ],
)
def test_owner_readback_must_match_exact_binding_and_eligibility(
    resolved, reason
) -> None:
    events = []
    with pytest.raises(ModelBindingResolutionFailure, match=reason):
        resolve(RecordingAuthorizer(events), RecordingResolver(events, resolved))
    assert [event[0] for event in events] == ["authorize", "resolve"]


def test_not_found_does_not_default_to_an_available_model() -> None:
    events = []

    class MissingResolver(RecordingResolver):
        def resolve_exact(self, scope, binding):
            self.events.append(("resolve", scope, binding))
            return None

    with pytest.raises(ModelBindingResolutionFailure, match="MODEL_BINDING_NOT_FOUND"):
        resolve(RecordingAuthorizer(events), MissingResolver(events))
    assert events[1][2] == BINDING


@pytest.mark.parametrize(
    "binding,reason",
    [
        (("", "model-revision:7", "a" * 64), "MODEL_IDENTITY_REQUIRED"),
        (("model:reviewer", "", "a" * 64), "MODEL_REVISION_REQUIRED"),
        (("model:reviewer", "model-revision:7", "latest"), "MODEL_DIGEST_REQUIRED"),
    ],
)
def test_binding_requires_exact_identity_revision_and_digest(binding, reason) -> None:
    with pytest.raises(ModelBindingResolutionFailure, match=reason):
        ExactModelBinding(*binding)


def test_use_target_cannot_authorize_a_different_model_suffix() -> None:
    with pytest.raises(
        ModelBindingResolutionFailure, match="MODEL_AUTHORIZATION_INVALID"
    ):
        ExactModelUse(
            BINDING,
            ModelUseAction.BIND_MODEL,
            "model:binding:AGENT:agent:17:revision:4:"
            f"model:other:{BINDING.revision_id}:{BINDING.digest}",
        )
