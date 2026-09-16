# ruff: noqa: RUF001
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import Barrier
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import (
    AuthenticationSource,
    AuthorityScope,
    GrantRequestStatus,
    TrustedRequestContext,
)
from agent_console.draft_assistance import (
    AuthorizationState,
    DeterministicSyntheticDraftTransport,
    DraftAssistanceError,
    DraftAssistanceProfileRevision,
    DraftAssistanceService,
    DraftInvocationState,
    DraftResultKind,
    DraftScope,
    InMemoryDraftAssistanceRepository,
    StaticPepperResolver,
)
from agent_console.draft_assistance_authorization import (
    CANCEL,
    DRAFT_OWNER,
    READ,
    REQUEST,
    GrantAdministrationDraftAuthorization,
)
from agent_console.draft_assistance_support import (
    ExactProfileModelResolver,
    InMemoryContextualResourceUseOwner,
    InMemoryDraftEvidenceOwner,
    InMemoryProviderCallBudget,
    OpaqueSyntheticCredentialResolver,
    StaticDraftAuthorization,
)
from agent_console.model_binding_resolution import (
    ExactModelBinding,
    ModelConsumptionScope,
    ResolvedModelBinding,
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

DIGEST = "a" * 64
NOW = datetime(2029, 1, 1, tzinfo=UTC)


class Identities:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self, prefix: str) -> str:
        self.value += 1
        return f"{prefix}:{self.value}"


def context(principal: str = "human:alice") -> TrustedRequestContext:
    return TrustedRequestContext(
        principal,
        AuthorityScope("tenant-a", "quality"),
        "session-1",
        AuthenticationSource.BROWSER_SESSION,
        "policy-1",
    )


def profile() -> DraftAssistanceProfileRevision:
    binding = ExactModelBinding("model-1", "model-revision-1", DIGEST)
    return DraftAssistanceProfileRevision(
        "draft-profile-revision-1",
        DIGEST,
        DraftScope("tenant-a", "quality"),
        binding,
        "provider-1",
        "provider-revision-1",
        DIGEST,
        "endpoint-1",
        "endpoint-revision-1",
        DIGEST,
        "connection-profile-1",
        "connection-profile-revision-1",
        DIGEST,
        "synthetic-draft-transport",
        "v1",
    )


def resolved() -> ResolvedModelBinding:
    return ResolvedModelBinding(
        ModelConsumptionScope("tenant-a", "quality"),
        ExactModelBinding("model-1", "model-revision-1", DIGEST),
        ProviderRevisionIdentity("provider-1", "provider-revision-1", DIGEST),
        EndpointRevisionIdentity("endpoint-1", "endpoint-revision-1", DIGEST),
        ConnectionProfileRevisionIdentity(
            "connection-profile-1", "connection-profile-revision-1", DIGEST
        ),
        ModelEligibility(
            ModelScope("tenant-a", "quality"),
            ModelRevisionIdentity("model-1", "model-revision-1", DIGEST),
            ModelEligibilityState.PUBLISHED_ENABLED,
            ModelLifecycleHighWater(4, "model-fact-4", DIGEST),
        ),
    )


def build(*, authorization_state=AuthorizationState.ALLOWED, now=NOW):
    repository = InMemoryDraftAssistanceRepository()
    authorization = StaticDraftAuthorization(
        state=authorization_state, clock=lambda: now
    )
    credentials = OpaqueSyntheticCredentialResolver()
    transport = DeterministicSyntheticDraftTransport()
    resource_use = InMemoryContextualResourceUseOwner()
    evidence = InMemoryDraftEvidenceOwner()
    service = DraftAssistanceService(
        repository,
        profile(),
        authorization,
        ExactProfileModelResolver(resolved()),
        StaticPepperResolver("pepper:draft", "v1", b"p" * 32),
        credentials,
        transport,
        resource_use,
        evidence,
        InMemoryProviderCallBudget(),
        clock=lambda: now,
        identity_factory=Identities(),
    )
    return service, authorization, credentials, transport, resource_use, evidence


def test_governed_synthetic_draft_records_metadata_resource_use_and_evidence() -> None:
    service, authorization, credentials, transport, resource_use, evidence = build()

    result = service.begin(
        context(),
        key="draft-key-1",
        content="降低供应商来料缺陷率，并在季度末前形成可验证的改进结果。",
    )

    assert result.invocation.state is DraftInvocationState.SUCCEEDED
    assert result.invocation.result_kind is DraftResultKind.DRAFT_READY
    assert result.title and result.description
    assert result.synthetic is True
    assert (
        authorization.admission_count
        == credentials.calls
        == transport.dispatch_count
        == 1
    )
    assert result.invocation.resource_use_id in resource_use.records
    assert result.invocation.evidence_id
    assert len(evidence.operations) == 1
    persisted = repr(
        service.repository.get(result.invocation.scope, result.invocation.invocation_id)
    )
    assert "降低供应商" not in persisted
    assert result.description not in persisted


def test_short_input_returns_clarification_and_supplement_creates_new_turn() -> None:
    service, *_ = build()
    first = service.begin(context(), key="draft-key-1", content="质量有问题")
    assert first.invocation.result_kind is DraftResultKind.NEEDS_CLARIFICATION
    assert first.clarification_question

    second = service.begin(
        context(),
        key="draft-key-2",
        content="质量有问题。目标是季度末前把来料缺陷率降到百分之一以内。",
        parent_context_id=first.invocation.context_id,
        parent_turn_id=first.invocation.turn_id,
        expected_parent_version=first.invocation.turn_version,
        predecessor_invocation_id=first.invocation.invocation_id,
    )
    assert second.invocation.context_id == first.invocation.context_id
    assert second.invocation.turn_version == first.invocation.turn_version + 1
    assert second.invocation.predecessor_invocation_id == first.invocation.invocation_id
    assert second.invocation.result_kind is DraftResultKind.DRAFT_READY
    with pytest.raises(DraftAssistanceError, match="DRAFT_TURN_VERSION_CONFLICT"):
        service.begin(
            context(),
            key="draft-key-stale-successor",
            content="另一个基于过期 turn 的补充。",
            parent_context_id=first.invocation.context_id,
            parent_turn_id=first.invocation.turn_id,
            expected_parent_version=first.invocation.turn_version,
            predecessor_invocation_id=first.invocation.invocation_id,
        )


def test_pending_authorization_requires_same_body_resubmission() -> None:
    service, authorization, credentials, transport, *_ = build(
        authorization_state=AuthorizationState.PENDING
    )
    first = service.begin(context(), key="draft-key-1", content="需要进一步说明")
    assert first.invocation.state is DraftInvocationState.AUTHORIZATION_PENDING
    assert credentials.calls == transport.dispatch_count == 0

    authorization.state = AuthorizationState.ALLOWED
    resumed = service.begin(context(), key="draft-key-1", content="需要进一步说明")
    assert resumed.invocation.state is DraftInvocationState.SUCCEEDED
    assert transport.dispatch_count == 1


def test_pending_authorization_rejects_different_body_without_dispatch() -> None:
    service, authorization, credentials, transport, *_ = build(
        authorization_state=AuthorizationState.PENDING
    )
    first = service.begin(
        context(), key="draft-key-pending-different", content="需要进一步说明"
    )
    assert first.invocation.state is DraftInvocationState.AUTHORIZATION_PENDING

    authorization.state = AuthorizationState.ALLOWED
    with pytest.raises(DraftAssistanceError, match="IDEMPOTENCY_PAYLOAD_MISMATCH"):
        service.begin(
            context(),
            key="draft-key-pending-different",
            content="这是不同的正文，不能借原授权调用。",
        )
    assert credentials.calls == transport.dispatch_count == 0


def test_replay_requires_read_before_payload_comparison() -> None:
    service, authorization, *_ = build()
    service.begin(context(), key="draft-key-read-first", content="需要进一步说明")
    authorization.readable = False

    with pytest.raises(DraftAssistanceError, match="DRAFT_ASSISTANCE_NOT_FOUND"):
        service.begin(
            context(), key="draft-key-read-first", content="同一个 key 的不同正文"
        )


def test_denial_and_revocation_before_admission_make_zero_provider_calls() -> None:
    service, _, credentials, transport, *_ = build(
        authorization_state=AuthorizationState.DENIED
    )
    denied = service.begin(context(), key="draft-key-1", content="拒绝的请求")
    assert denied.invocation.state is DraftInvocationState.REJECTED
    assert credentials.calls == transport.dispatch_count == 0

    service, authorization, credentials, transport, *_ = build()
    authorization.admitted = False
    with pytest.raises(DraftAssistanceError, match="DISPATCH_ADMISSION_DENIED"):
        service.begin(context(), key="draft-key-2", content="撤权竞争中的请求")
    assert credentials.calls == transport.dispatch_count == 0


def test_same_key_concurrency_dispatches_once_and_payload_conflict_fails_closed() -> (
    None
):
    service, _, _, transport, *_ = build()

    def invoke():
        return service.begin(
            context(),
            key="draft-key-concurrent",
            content="季度末前将供应商缺陷率降低到百分之一以内。",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(lambda _: invoke(), range(2)))
    assert results[0].invocation.invocation_id == results[1].invocation.invocation_id
    assert transport.dispatch_count == 1

    with pytest.raises(DraftAssistanceError, match="IDEMPOTENCY_PAYLOAD_MISMATCH"):
        service.begin(
            context(), key="draft-key-concurrent", content="同一个 key 的不同正文"
        )


def test_unknown_never_redispatches_and_explicit_successor_is_isolated() -> None:
    service, *_prefix, transport, _, _ = build()
    first = service.begin(
        context(), key="draft-key-unknown", content="[UNKNOWN] 模拟传输歧义"
    )
    assert first.invocation.state is DraftInvocationState.OUTCOME_UNKNOWN
    replay = service.begin(
        context(), key="draft-key-unknown", content="[UNKNOWN] 模拟传输歧义"
    )
    assert replay.invocation.invocation_id == first.invocation.invocation_id
    assert transport.dispatch_count == 1

    successor = service.begin(
        context(),
        key="draft-key-successor",
        content="显式 successor：季度末前将缺陷率降低到百分之一以内。",
        parent_context_id=first.invocation.context_id,
        parent_turn_id=first.invocation.turn_id,
        expected_parent_version=first.invocation.turn_version,
        predecessor_invocation_id=first.invocation.invocation_id,
    )
    assert successor.invocation.invocation_id != first.invocation.invocation_id
    assert (
        successor.invocation.predecessor_invocation_id == first.invocation.invocation_id
    )
    assert transport.dispatch_count == 2


def test_expired_or_unavailable_pepper_blocks_replay() -> None:
    service, *_ = build(now=NOW)
    first = service.begin(context(), key="draft-key-1", content="需要进一步说明")
    service.peppers = StaticPepperResolver("pepper:draft", "v2", b"q" * 32)
    with pytest.raises(DraftAssistanceError, match="IDEMPOTENCY_REPLAY_UNVERIFIABLE"):
        service.begin(context(), key="draft-key-1", content="需要进一步说明")

    service.clock = lambda: NOW + timedelta(days=2)
    with pytest.raises(DraftAssistanceError, match="IDEMPOTENCY_REPLAY_WINDOW_EXPIRED"):
        service.begin(context(), key="draft-key-1", content="需要进一步说明")
    assert first.invocation.commitment not in repr(
        next(iter(service.evidence.operations.values()))
    )


def test_cancel_reject_and_problem_link_do_not_claim_business_success() -> None:
    service, *_ = build()
    result = service.begin(
        context(),
        key="draft-key-1",
        content="季度末前将供应商缺陷率降低到百分之一以内。",
    )
    linked = service.link_problem(
        context(),
        result.invocation.invocation_id,
        problem_id="problem-1",
        problem_revision_id="problem-revision-1",
        problem_digest=DIGEST,
    )
    assert linked.invocation.problem_id == "problem-1"
    assert linked.invocation.state is DraftInvocationState.SUCCEEDED

    rejected = service.reject(context(), result.invocation.invocation_id)
    assert rejected.invocation.state is DraftInvocationState.REJECTED_BY_USER
    assert rejected.invocation.problem_id == "problem-1"

    service, *_ = build()
    unknown = service.begin(
        context(), key="draft-key-cancel", content="[UNKNOWN] 模拟取消"
    )
    cancelled = service.cancel(context(), unknown.invocation.invocation_id)
    assert cancelled.invocation.state is DraftInvocationState.CANCELLATION_CONFIRMED

    service, *_ = build()
    succeeded = service.begin(
        context(), key="draft-key-cancel-conflict", content="完整的结构化问题描述"
    )
    with pytest.raises(DraftAssistanceError, match="DRAFT_STATE_CONFLICT"):
        service.cancel(context(), succeeded.invocation.invocation_id)


def test_dispatch_cas_has_one_transport_winner_under_same_key_race() -> None:
    service, authorization, credentials, transport, *_ = build()
    gate = Barrier(2)
    original = authorization.validate_current_and_admit

    def admit(*args):
        value = original(*args)
        gate.wait(timeout=2)
        return value

    authorization.validate_current_and_admit = admit

    def invoke():
        return service.begin(
            context(),
            key="draft-key-cas-race",
            content="季度末前将供应商缺陷率降低到百分之一以内。",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(lambda _: invoke(), range(2)))
    assert {item.invocation.invocation_id for item in results} == {
        results[0].invocation.invocation_id
    }
    assert credentials.calls == transport.dispatch_count == 1


def test_credential_failure_occurs_after_dispatch_fence_and_before_transport() -> None:
    service, authorization, credentials, transport, *_ = build()

    def unavailable(*_args):
        credentials.calls += 1
        raise DraftAssistanceError("CREDENTIAL_RESOLUTION_FAILED")

    credentials.resolve = unavailable
    with pytest.raises(DraftAssistanceError, match="CREDENTIAL_RESOLUTION_FAILED"):
        service.begin(
            context(),
            key="draft-key-credential-failure",
            content="季度末前将供应商缺陷率降低到百分之一以内。",
        )
    restored = service.repository.get_by_key(
        DraftScope.from_context(context()),
        "human:alice",
        "draft-key-credential-failure",
    )
    assert restored is not None
    assert restored.state is DraftInvocationState.FAILED_PRE_DISPATCH
    assert restored.admission_id is not None
    assert restored.dispatch_fence is not None
    assert restored.budget_reservation_id is not None
    assert authorization.admission_count == credentials.calls == 1
    assert transport.dispatch_count == 0


def test_evidence_repair_replays_owner_write_without_provider_dispatch() -> None:
    service, _, _, transport, _, evidence = build()
    original = evidence.append
    attempts = 0

    def flaky(*args):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise DraftAssistanceError("EVIDENCE_STORAGE_UNAVAILABLE")
        return original(*args)

    evidence.append = flaky
    first = service.begin(
        context(),
        key="draft-key-evidence-repair",
        content="季度末前将供应商缺陷率降低到百分之一以内。",
    )
    assert first.invocation.owner_write_reason_code == "EVIDENCE_APPEND_PENDING"
    assert first.invocation.reason_code is None
    observe_calls = 0
    original_observe = transport.observe

    def observe(correlation):
        nonlocal observe_calls
        observe_calls += 1
        return original_observe(correlation)

    transport.observe = observe
    repaired = service.observe(context(), first.invocation.invocation_id)
    assert repaired.invocation.evidence_id
    assert repaired.invocation.reason_code is None
    assert transport.dispatch_count == 1
    assert observe_calls == 0
    assert attempts == 2


def test_resource_use_admission_failure_is_terminal_and_zero_provider_calls() -> None:
    service, _, credentials, transport, resource_use, _ = build()

    def unavailable(*_args):
        raise DraftAssistanceError("RESOURCE_USE_STORAGE_UNAVAILABLE")

    resource_use.record_requested = unavailable
    with pytest.raises(DraftAssistanceError, match="RESOURCE_USE_ADMISSION_FAILED"):
        service.begin(
            context(), key="draft-key-resource-use", content="完整的结构化问题描述"
        )
    restored = service.repository.get_by_key(
        DraftScope.from_context(context()), "human:alice", "draft-key-resource-use"
    )
    assert restored is not None
    assert restored.state is DraftInvocationState.FAILED_PRE_DISPATCH
    assert credentials.calls == transport.dispatch_count == 0


def test_owner_repair_preserves_provider_reason_code() -> None:
    service, _, _, transport, resource_use, _ = build()
    original = resource_use.record_observation
    attempts = 0

    def flaky(*args):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise DraftAssistanceError("RESOURCE_USE_STORAGE_UNAVAILABLE")
        return original(*args)

    resource_use.record_observation = flaky
    first = service.begin(
        context(), key="draft-key-unknown-repair", content="[UNKNOWN] 模拟传输歧义"
    )
    assert first.invocation.reason_code == "TRANSPORT_AMBIGUOUS"
    assert first.invocation.owner_write_reason_code == "RESOURCE_USE_COMPLETION_PENDING"
    observe_calls = 0
    original_transport_observe = transport.observe

    def observe(correlation):
        nonlocal observe_calls
        observe_calls += 1
        return original_transport_observe(correlation)

    transport.observe = observe
    repaired = service.observe(context(), first.invocation.invocation_id)
    assert repaired.invocation.reason_code == "TRANSPORT_AMBIGUOUS"
    assert repaired.invocation.owner_write_reason_code is None
    assert transport.dispatch_count == 1
    assert observe_calls == 0


def test_problem_provenance_link_failure_retries_only_link() -> None:
    service, *_prefix, transport, _, _ = build()
    result = service.begin(
        context(),
        key="draft-key-link-repair",
        content="季度末前将供应商缺陷率降低到百分之一以内。",
    )
    original_compare_and_set = service.repository.compare_and_set
    failures = 0

    def fail_link_once(expected_version, replacement):
        nonlocal failures
        if replacement.problem_id and failures == 0:
            failures += 1
            raise DraftAssistanceError("DRAFT_STORAGE_UNAVAILABLE")
        return original_compare_and_set(expected_version, replacement)

    service.repository.compare_and_set = fail_link_once
    with pytest.raises(DraftAssistanceError, match="DRAFT_STORAGE_UNAVAILABLE"):
        service.link_problem(
            context(),
            result.invocation.invocation_id,
            problem_id="problem-already-created",
            problem_revision_id="problem-revision-1",
            problem_digest=DIGEST,
        )
    linked = service.link_problem(
        context(),
        result.invocation.invocation_id,
        problem_id="problem-already-created",
        problem_revision_id="problem-revision-1",
        problem_digest=DIGEST,
    )
    assert linked.invocation.problem_id == "problem-already-created"
    assert transport.dispatch_count == 1


def test_cancel_request_late_result_updates_only_original_not_successor() -> None:
    service, *_prefix, transport, _, _ = build()
    original = service.begin(
        context(), key="draft-key-cancel-late", content="[UNKNOWN] 模拟取消后晚到"
    )
    correlation = original.invocation.provider_correlation
    assert correlation

    transport.cancel = lambda value: type(transport.observations[correlation])(
        "cancel-not-confirmed",
        transport.observations[correlation].state,
        correlation=value,
        reason_code="PROVIDER_CANCELLATION_UNSUPPORTED_FOREGROUND",
    )
    requested = service.cancel(context(), original.invocation.invocation_id)
    assert requested.invocation.state is DraftInvocationState.CANCELLATION_REQUESTED
    successor = service.begin(
        context(),
        key="draft-key-cancel-late-successor",
        content="季度末前将供应商缺陷率降低到百分之一以内。",
        parent_context_id=original.invocation.context_id,
        parent_turn_id=original.invocation.turn_id,
        expected_parent_version=original.invocation.turn_version,
        predecessor_invocation_id=original.invocation.invocation_id,
    )
    transport.observations[correlation] = type(transport.observations[correlation])(
        "late-after-cancel",
        transport.observations[successor.invocation.provider_correlation].state,
        correlation=correlation,
        result_kind=DraftResultKind.DRAFT_READY,
        title="原调用晚到结果",
        description="该结果只能归属原调用。",
    )
    observed = service.observe(context(), original.invocation.invocation_id)
    persisted_successor = service.read(context(), successor.invocation.invocation_id)
    assert observed.invocation.state is DraftInvocationState.SUCCEEDED
    assert (
        persisted_successor.invocation.invocation_id
        == successor.invocation.invocation_id
    )
    assert persisted_successor.invocation.last_observation_id != "late-after-cancel"


def test_late_result_updates_original_and_never_successor() -> None:
    service, *_prefix, transport, _, _ = build()
    original = service.begin(
        context(), key="draft-key-late", content="[UNKNOWN] 模拟晚到结果"
    )
    successor = service.begin(
        context(),
        key="draft-key-late-successor",
        content="季度末前将供应商缺陷率降低到百分之一以内。",
        parent_context_id=original.invocation.context_id,
        parent_turn_id=original.invocation.turn_id,
        expected_parent_version=original.invocation.turn_version,
        predecessor_invocation_id=original.invocation.invocation_id,
    )
    correlation = original.invocation.provider_correlation
    assert correlation
    transport.observations[correlation] = type(transport.observations[correlation])(
        "late-success",
        transport.observations[successor.invocation.provider_correlation].state,
        correlation=correlation,
        result_kind=DraftResultKind.DRAFT_READY,
        title="晚到的原调用草稿",
        description="只归属于原调用。",
    )
    observed = service.observe(context(), original.invocation.invocation_id)
    persisted_successor = service.read(context(), successor.invocation.invocation_id)
    assert observed.invocation.state is DraftInvocationState.SUCCEEDED
    assert persisted_successor.invocation.problem_id is None
    assert (
        persisted_successor.invocation.invocation_id
        == successor.invocation.invocation_id
    )


def test_formal_authorization_bootstrap_requests_exact_read_and_cancel_grants() -> None:
    service, *_ = build(authorization_state=AuthorizationState.PENDING)
    invocation = service.begin(
        context(), key="formal-authorization-key", content="需要进一步说明"
    ).invocation
    invocation = replace(invocation, authorization=None)

    class Grants:
        def __init__(self):
            self.commands = []
            self.authorization = SimpleNamespace(
                authorize_current=lambda *_args, **_kwargs: None
            )

        def submit_request(self, _context, command):
            self.commands.append(command)
            return SimpleNamespace(
                request_id=f"request-{len(self.commands)}", aggregate_version=1
            )

        def inspect_request(self, _context, request_id):
            return SimpleNamespace(
                request_id=request_id,
                status=GrantRequestStatus.APPROVED,
                aggregate_version=2,
            )

    grants = Grants()
    adapter = GrantAdministrationDraftAuthorization(
        grants,
        SimpleNamespace(),
        clock=lambda: NOW,
    )
    pending = adapter.resolve(context(), invocation)
    requested = grants.commands[0].requested_grants
    assert [(item.owner, item.action) for item in requested] == [
        (DRAFT_OWNER, REQUEST),
        (DRAFT_OWNER, READ),
        (DRAFT_OWNER, CANCEL),
    ]
    assert {item.exact_resource for item in requested[1:]} == {
        f"draft-assistance:invocation:{invocation.invocation_id}"
    }
    assert pending.model_authorization_request_id is None
