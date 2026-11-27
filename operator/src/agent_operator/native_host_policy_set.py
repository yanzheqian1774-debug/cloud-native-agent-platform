"""Internal, unmounted routing primitive for two original exact-host discoveries.

Scope selects a leaf, never authorizes a preparation. Original Discovery owners
remain responsible for all receipt, credential, source and current-grant checks.
No environment, assembly, process, database or authority mutation occurs here.
"""

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class LeafKind(StrEnum):
    HUMAN_OWNED = "HUMAN_OWNED"
    BOUND_SERVICE = "BOUND_SERVICE"


def scope_of(candidate):
    scope = tuple(
        candidate.get(key) for key in ("namespace", "securityDomain", "principalId")
    )
    if any(not isinstance(value, str) or not value for value in scope):
        raise ValueError("HOST_POLICY_SET_SCOPE_INVALID")
    return scope


@dataclass(frozen=True)
class DiscoveryLeaf:
    kind: LeafKind
    discovery: object


class PolicySetDiscovery:
    """DI adapter; not an enabled CLI or an alternative admission owner."""

    def __init__(self, leaves):
        leaves = tuple(leaves)
        if len(leaves) != 2 or {leaf.kind for leaf in leaves} != set(LeafKind):
            raise ValueError("HOST_POLICY_SET_TWO_TYPED_LEAVES_REQUIRED")
        scopes = [tuple(leaf.discovery.scope) for leaf in leaves]
        if len(set(scopes)) != len(scopes):
            raise ValueError("HOST_POLICY_SET_AMBIGUOUS_SCOPE")
        fingerprints = {leaf.discovery.fingerprint for leaf in leaves}
        if len(fingerprints) != 1 or not next(iter(fingerprints)):
            raise ValueError("HOST_POLICY_SET_DATABASE_MISMATCH")
        for leaf, scope in zip(leaves, scopes, strict=True):
            scope_of(
                dict(
                    zip(
                        ("namespace", "securityDomain", "principalId"),
                        scope,
                        strict=True,
                    )
                )
            )
            service = leaf.discovery.service is not None
            if service != (leaf.kind == LeafKind.BOUND_SERVICE):
                raise ValueError("HOST_POLICY_SET_OWNER_KIND_MISMATCH")
            if not service and leaf.discovery.work.owned_business is None:
                raise ValueError("HOST_POLICY_SET_HUMAN_OWNER_REQUIRED")
        self.leaves = leaves
        self._by_scope = MappingProxyType(dict(zip(scopes, leaves, strict=True)))
        self.fingerprint = next(iter(fingerprints))
        self._offset = 0
        self.page_errors = ()
        self._observe_stopped = None

    @property
    def observe_stopped(self):
        return self._observe_stopped

    @observe_stopped.setter
    def observe_stopped(self, callback):
        self._observe_stopped = callback
        for leaf in self.leaves:
            leaf.discovery.observe_stopped = callback

    def leaf(self, candidate):
        leaf = self._by_scope.get(scope_of(candidate))
        if leaf is None:
            raise ValueError("HOST_POLICY_SET_NO_MATCH")
        return leaf

    def _checked(self, leaf, observed):
        if observed is not None and self.leaf(observed) is not leaf:
            raise ValueError("HOST_POLICY_SET_OBSERVATION_SCOPE_CHANGED")
        return observed

    def page(self, limit=32):
        if type(limit) is not int or not 1 <= limit <= 32:
            raise ValueError("HOST_POLICY_SET_PAGE_BOUND_INVALID")
        ordered = self.leaves[self._offset :] + self.leaves[: self._offset]
        self._offset = (self._offset + 1) % len(self.leaves)
        pages, errors = [], []
        for index, leaf in enumerate(ordered):
            count = limit // 2 + (index < limit % 2)
            if not count:
                pages.append([])
                continue
            try:
                page = list(leaf.discovery.page(count))
                if len(page) > count:
                    raise ValueError("HOST_POLICY_SET_PAGE_OVERFLOW")
                for item in page:
                    if item is None or self.leaf(item) is not leaf:
                        raise ValueError("HOST_POLICY_SET_OBSERVATION_SCOPE_CHANGED")
                pages.append(page)
            except Exception:
                # One unavailable owner must not borrow the other owner or stop
                # discovering its unrelated work. No raw exception is projected.
                errors.append((leaf.kind.value, "OBSERVATION_UNAVAILABLE"))
                pages.append([])
        self.page_errors = tuple(errors)
        result = []
        for index in range(max(map(len, pages), default=0)):
            for page in pages:
                if index < len(page):
                    result.append(page[index])
        return result

    def current(self, candidate):
        leaf = self.leaf(candidate)
        return self._checked(leaf, leaf.discovery.current(candidate))

    def maintain(self, candidate, process_record):
        leaf = self.leaf(candidate)
        return self._checked(leaf, leaf.discovery.maintain(candidate, process_record))

    def wait_access_for(self, candidate):
        return self.leaf(candidate).discovery.wait_access

    def stopped(
        self, candidate, process_record, startup_record, exit_receipt, verify_exit
    ):
        return self.leaf(candidate).discovery.stopped(
            candidate, process_record, startup_record, exit_receipt, verify_exit
        )
