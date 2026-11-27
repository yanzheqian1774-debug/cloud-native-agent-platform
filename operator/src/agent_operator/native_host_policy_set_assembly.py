"""Startup-only composition of original owners; no tick or identity fabrication.

Original constructors can migrate/configure their repositories. This is NOT a
read-only preflight and must never be invoked lazily from a request handler.
"""

from dataclasses import dataclass
from types import MappingProxyType

from .native_host_policy_set import DiscoveryLeaf, LeafKind, PolicySetDiscovery
from .native_host_service_discovery import Discovery


@dataclass(frozen=True)
class LeafAssembly:
    kind: LeafKind
    configuration: object
    assembly: object
    discovery: Discovery

    @property
    def work(self):
        return self.assembly.worker.repository.work

    @property
    def runtime(self):
        caller = self.assembly.worker.transport.caller
        return getattr(caller, "runtime", None)

    @property
    def execution_repository(self):
        return self.assembly.execution_repository


def close_all(assemblies):
    failures = []
    for assembly in reversed(assemblies):
        try:
            assembly.close()
        except Exception as error:
            failures.append(error)
    if failures:
        raise failures[0]


class PolicySetAssembly:
    def __init__(self, configuration):
        from .native_dispatch_reconciler import build_native_dispatch_from_environment

        self.configuration = configuration
        self._closed = False
        entries, owners = {}, []
        try:
            configuration.verify()
            for scope, (kind, config) in configuration.leaves.items():
                assembly = build_native_dispatch_from_environment(
                    environment=config.environment
                )
                if assembly is None:
                    raise ValueError("HOST_SERVICE_ASSEMBLY_REQUIRED")
                owners.append(assembly)
                discovery = Discovery(assembly, scope, configuration.fingerprint)
                entries[scope] = LeafAssembly(kind, config, assembly, discovery)
            configuration.verify()
            self.discovery = PolicySetDiscovery(
                DiscoveryLeaf(entry.kind, entry.discovery) for entry in entries.values()
            )
        except BaseException as error:
            try:
                close_all(owners)
            except Exception as close_error:
                raise error from close_error
            raise
        self.leaves = MappingProxyType(entries)
        self._owners = tuple(owners)

    def service_leaf(self, scope, *, credential_id, policy_digest):
        """Select original objects, without granting command authorization."""
        if self._closed:
            raise ValueError("HOST_POLICY_SET_ASSEMBLY_CLOSED")
        self.configuration.verify()
        leaf = self.leaves.get(tuple(scope))
        if leaf is None or leaf.kind != LeafKind.BOUND_SERVICE:
            raise ValueError("HOST_POLICY_SET_SERVICE_LEAF_MISMATCH")
        bridge = leaf.work.bound_service_execution
        policy = bridge.registry._policy()
        runtime = leaf.runtime
        if (
            (policy.tenantId, policy.securityDomain, policy.subjectId) != tuple(scope)
            or policy.credentialId != credential_id
            or policy.digest != policy_digest
            or runtime is None
            or (runtime.subject, runtime.service_credential_id)
            != (policy.subjectId, policy.credentialId)
            or runtime.bound_service_execution is not bridge
        ):
            raise ValueError("HOST_POLICY_SET_SERVICE_LEAF_MISMATCH")
        return leaf

    def close(self):
        if not self._closed:
            self._closed = True
            close_all(self._owners)
