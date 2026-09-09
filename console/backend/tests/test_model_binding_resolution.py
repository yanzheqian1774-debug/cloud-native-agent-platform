import pytest
from agent_console.model_binding_resolution import (
    AuthorizedModelUse,
    ExactModelBinding,
    ModelBindingResolutionFailure,
    ModelConsumptionScope,
    ModelUseSubject,
    ResolvedModelBinding,
    resolve_authorized_model_binding,
)

SCOPE = ModelConsumptionScope("tenant-a", "quality")
SUBJECT = ModelUseSubject("employee:17")
BINDING = ExactModelBinding("model:reviewer", "model-revision:7", "a" * 64)


class RecordingAuthorizer:
    def __init__(self, events, result=True):
        self.events = events
        self.result = result

    def authorize_use(self, scope, subject, binding):
        self.events.append(("authorize", scope, subject, binding))
        if not self.result:
            return None
        if isinstance(self.result, AuthorizedModelUse):
            return self.result
        return AuthorizedModelUse("decision:1", subject, scope, binding)


class RecordingResolver:
    def __init__(self, events, result=None):
        self.events = events
        self.result = result

    def resolve_exact(self, scope, binding):
        self.events.append(("resolve", scope, binding))
        return self.result or resolution()


def resolution(**changes):
    values = {
        "scope": SCOPE,
        "binding": BINDING,
        "provider_reference": "provider:approved",
        "connection_profile_reference": "connection-profile:eu-1",
        "published": True,
        "enabled": True,
        "configuration_available": True,
    }
    values.update(changes)
    return ResolvedModelBinding(**values)


def resolve(authorizer, resolver):
    return resolve_authorized_model_binding(
        SCOPE,
        SUBJECT,
        BINDING,
        authorizer=authorizer,
        resolver=resolver,
    )


def test_exact_authorized_binding_returns_secret_free_owner_readback() -> None:
    events = []

    result = resolve(RecordingAuthorizer(events), RecordingResolver(events))

    assert result.binding == BINDING
    assert result.provider_reference == "provider:approved"
    assert result.connection_profile_reference == "connection-profile:eu-1"
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
    "authorization,reason",
    [
        (
            AuthorizedModelUse(
                "decision:1",
                SUBJECT,
                ModelConsumptionScope("tenant-b", "quality"),
                BINDING,
            ),
            "MODEL_AUTHORIZATION_INVALID",
        ),
        (
            AuthorizedModelUse(
                "decision:1",
                ModelUseSubject("employee:other"),
                SCOPE,
                BINDING,
            ),
            "MODEL_AUTHORIZATION_INVALID",
        ),
        (
            AuthorizedModelUse(
                "decision:1",
                SUBJECT,
                SCOPE,
                ExactModelBinding("model:other", "model-revision:7", "a" * 64),
            ),
            "MODEL_AUTHORIZATION_INVALID",
        ),
    ],
)
def test_authorization_must_bind_subject_scope_and_exact_model(
    authorization, reason
) -> None:
    events = []

    with pytest.raises(ModelBindingResolutionFailure, match=reason):
        resolve(RecordingAuthorizer(events, authorization), RecordingResolver(events))

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
                binding=ExactModelBinding("model:other", "model-revision:7", "a" * 64)
            ),
            "MODEL_IDENTITY_MISMATCH",
        ),
        (
            resolution(
                binding=ExactModelBinding(
                    "model:reviewer", "model-revision:8", "a" * 64
                )
            ),
            "MODEL_REVISION_MISMATCH",
        ),
        (
            resolution(
                binding=ExactModelBinding(
                    "model:reviewer", "model-revision:7", "b" * 64
                )
            ),
            "MODEL_DIGEST_MISMATCH",
        ),
        (resolution(published=False), "MODEL_UNPUBLISHED"),
        (resolution(enabled=False), "MODEL_DISABLED"),
        (
            resolution(configuration_available=False),
            "MODEL_CONFIGURATION_UNAVAILABLE",
        ),
    ],
)
def test_owner_readback_must_match_exact_binding_and_consumption_state(
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
