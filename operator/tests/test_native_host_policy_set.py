from types import SimpleNamespace

import pytest
from agent_operator.native_host_policy_set import (
    DiscoveryLeaf,
    LeafKind,
    PolicySetDiscovery,
)


class ControlledDiscovery:
    def __init__(self, actor, *, service=False):
        self.scope = ("ns", "domain", actor)
        self.fingerprint = "same-database"
        self.service = object() if service else None
        self.work = SimpleNamespace(owned_business=None if service else object())
        self.calls = []
        self.failure = False
        self.item = dict(
            namespace="ns",
            securityDomain="domain",
            principalId=actor,
            preparationDigest=actor + "-prep",
            runId=actor + "-run",
        )
        self.observation = self.item

    def page(self, limit):
        self.calls.append(("page", limit))
        if self.failure:
            raise ValueError("controlled unavailable")
        return [self.item]

    def current(self, candidate):
        self.calls.append(("current", candidate))
        if self.failure:
            raise ValueError("controlled revoked")
        return self.observation

    def maintain(self, candidate, record):
        self.calls.append(("maintain", candidate, record))
        return self.observation

    def stopped(self, *args):
        self.calls.append(("stopped", *args))
        return "original-owner-receipt"


def pair():
    human = ControlledDiscovery("human")
    service = ControlledDiscovery("service", service=True)
    leaves = (
        DiscoveryLeaf(LeafKind.HUMAN_OWNED, human),
        DiscoveryLeaf(LeafKind.BOUND_SERVICE, service),
    )
    return human, service, leaves


def test_two_actor_pages_fair_and_current_rechecks_original_owner():
    human, service, leaves = pair()
    router = PolicySetDiscovery(leaves)
    assert router.page() == [human.item, service.item]
    assert router.page() == [service.item, human.item]
    assert router.current(human.item) == human.item
    assert human.calls[-1] == ("current", human.item)
    assert not any(call[0] == "current" for call in service.calls)
    assert router.page_errors == ()


def test_ambiguous_unknown_wrong_kind_and_database_rejected():
    human, service, leaves = pair()
    service.scope = human.scope
    with pytest.raises(ValueError, match="AMBIGUOUS"):
        PolicySetDiscovery(leaves)
    human, service, leaves = pair()
    service.fingerprint = "other-database"
    with pytest.raises(ValueError, match="DATABASE"):
        PolicySetDiscovery(leaves)
    human, service, leaves = pair()
    service.service = None
    with pytest.raises(ValueError, match="OWNER_KIND"):
        PolicySetDiscovery(leaves)
    human, service, leaves = pair()
    router = PolicySetDiscovery(leaves)
    with pytest.raises(ValueError, match="NO_MATCH"):
        router.current({**human.item, "principalId": "unknown"})
    assert human.calls == service.calls == []


def test_unavailable_or_missing_service_never_falls_back_to_human():
    human, service, leaves = pair()
    router = PolicySetDiscovery(leaves)
    service.failure = True
    assert router.page() == [human.item]
    assert router.page_errors == (("BOUND_SERVICE", "OBSERVATION_UNAVAILABLE"),)
    before = list(human.calls)
    with pytest.raises(ValueError, match="revoked"):
        router.current(service.item)
    assert human.calls == before
    service.failure = False
    service.observation = (
        None  # Includes UNKNOWN/ineligible original-owner observation.
    )
    assert router.current(service.item) is None
    assert human.calls == before
    service.observation = human.item
    with pytest.raises(ValueError, match="SCOPE_CHANGED"):
        router.current(service.item)


def test_wait_callbacks_keep_original_leaf_and_identity_after_page_rotation():
    human, service, leaves = pair()
    router = PolicySetDiscovery(leaves)
    callback = object()
    router.observe_stopped = callback
    assert human.observe_stopped is service.observe_stopped is callback
    router.page()
    router.page()
    record, startup, receipt, verify = ({"pid": 7}, {}, {}, object())
    assert router.maintain(service.item, record) == service.item
    assert router.stopped(service.item, record, startup, receipt, verify) == (
        "original-owner-receipt"
    )
    assert service.calls[-1] == (
        "stopped",
        service.item,
        record,
        startup,
        receipt,
        verify,
    )
    assert not any(call[0] in {"maintain", "stopped"} for call in human.calls)


def test_startup_composes_once_and_service_lookup_returns_exact_original_objects(
    monkeypatch,
):
    from agent_operator import native_dispatch_reconciler as builder
    from agent_operator import native_host_policy_set_assembly as module

    human, service, _ = pair()
    policy = SimpleNamespace(
        tenantId="ns",
        securityDomain="domain",
        subjectId="service",
        credentialId="credential",
        digest="policy",
    )
    bridge = SimpleNamespace(registry=SimpleNamespace(_policy=lambda: policy))
    runtime = SimpleNamespace(
        subject="service",
        service_credential_id="credential",
        bound_service_execution=bridge,
    )
    work = SimpleNamespace(bound_service_execution=bridge)
    closed, constructed = [], []
    owners = [
        SimpleNamespace(close=lambda: closed.append("human")),
        SimpleNamespace(
            worker=SimpleNamespace(
                repository=SimpleNamespace(work=work),
                transport=SimpleNamespace(caller=SimpleNamespace(runtime=runtime)),
            ),
            execution_repository=object(),
            close=lambda: closed.append("service"),
        ),
    ]
    configs = {
        human.scope: (
            LeafKind.HUMAN_OWNED,
            SimpleNamespace(environment={"leaf": "human"}),
        ),
        service.scope: (
            LeafKind.BOUND_SERVICE,
            SimpleNamespace(environment={"leaf": "service"}),
        ),
    }

    def build(*, environment):
        constructed.append(environment["leaf"])
        return owners[len(constructed) - 1]

    monkeypatch.setattr(builder, "build_native_dispatch_from_environment", build)
    monkeypatch.setattr(
        module,
        "Discovery",
        lambda assembly, scope, fp: human if scope == human.scope else service,
    )
    combined = module.PolicySetAssembly(
        SimpleNamespace(
            leaves=configs, fingerprint="same-database", verify=lambda: None
        )
    )
    exact = combined.service_leaf(
        service.scope, credential_id="credential", policy_digest="policy"
    )
    assert exact.assembly is owners[1]
    assert exact.runtime is runtime and exact.work is work
    assert constructed == ["human", "service"]
    for scope, cred, digest in (
        (human.scope, "credential", "policy"),
        (service.scope, "other", "policy"),
        (service.scope, "credential", "other"),
    ):
        with pytest.raises(ValueError, match="LEAF_MISMATCH"):
            combined.service_leaf(scope, credential_id=cred, policy_digest=digest)
    assert constructed == ["human", "service"]
    combined.close()
    combined.close()
    assert closed == ["service", "human"]
    with pytest.raises(ValueError, match="ASSEMBLY_CLOSED"):
        combined.service_leaf(
            service.scope, credential_id="credential", policy_digest="policy"
        )


def test_partial_factory_failure_closes_all_previously_constructed_owners(monkeypatch):
    from agent_operator import native_dispatch_reconciler as builder
    from agent_operator import native_host_policy_set_assembly as module

    human, service, _ = pair()
    closed, calls = [], []
    first = SimpleNamespace(close=lambda: closed.append("human"))

    def build(*, environment):
        calls.append(environment)
        if len(calls) == 2:
            raise ValueError("controlled-second-factory-failed")
        return first

    monkeypatch.setattr(builder, "build_native_dispatch_from_environment", build)
    monkeypatch.setattr(module, "Discovery", lambda *args: human)
    configs = {
        human.scope: (LeafKind.HUMAN_OWNED, SimpleNamespace(environment={})),
        service.scope: (LeafKind.BOUND_SERVICE, SimpleNamespace(environment={})),
    }
    with pytest.raises(ValueError, match="second-factory-failed"):
        module.PolicySetAssembly(
            SimpleNamespace(
                leaves=configs, fingerprint="same-database", verify=lambda: None
            )
        )
    assert closed == ["human"]
