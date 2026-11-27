"""Controlled empty peer for per-leaf PG tests; not proof of two real owners."""

from types import SimpleNamespace

from agent_operator.native_host_policy_set import (
    DiscoveryLeaf,
    LeafKind,
    PolicySetDiscovery,
)


def routed(real, kind):
    peer_kind = (
        LeafKind.HUMAN_OWNED
        if kind == LeafKind.BOUND_SERVICE
        else LeafKind.BOUND_SERVICE
    )
    peer = SimpleNamespace(
        scope=(*real.scope[:2], "controlled-empty-peer"),
        fingerprint=real.fingerprint,
        service=object() if peer_kind == LeafKind.BOUND_SERVICE else None,
        work=SimpleNamespace(
            owned_business=object() if peer_kind == LeafKind.HUMAN_OWNED else None
        ),
        wait_access=None,
        page=lambda limit: [],
    )
    return PolicySetDiscovery(
        (DiscoveryLeaf(kind, real), DiscoveryLeaf(peer_kind, peer))
    )
