"""Real two-leaf factory; controlled static-generation input and Kubernetes port.

No factory, repository, current authorizer, WorkReader or bridge is replaced.
The shared fixture's declared current generation is supplied at the loader port;
this does not claim a deployed signed-generation/controller ceremony.
"""

import hashlib
from pathlib import Path

from agent_console.authority_configuration import StaticAuthorityLoader
from agent_console.authority_contracts import ControlState
from agent_console.authority_recovery import HostControlRecord, HostRecoveryControl
from agent_console.governed_execution_ownership import execution_database_fingerprint
from agent_operator import native_dispatch_reconciler
from agent_operator.native_host_policy_set_assembly import PolicySetAssembly
from agent_operator.native_host_policy_set_config import (
    DI_SOURCES,
    PolicySetConfiguration,
)
from agent_operator.native_host_service_state import write


def assemble(tmp_path, monkeypatch, human, service, generation):
    from pending_pipeline_support import FixtureKubernetes

    tmp_path.mkdir()
    root = Path(__file__).resolve().parents[3]
    migrations = root / "console/backend/migrations"
    database_url = human.repository.pool.conninfo
    assert database_url == service.repository.pool.conninfo
    fingerprint = execution_database_fingerprint(database_url)
    control = tmp_path / "control.json"
    HostRecoveryControl(control).replace(
        HostControlRecord(
            1,
            1,
            ControlState.ACTIVE,
            fingerprint,
            generation.generation,
            generation.digest,
            "isolated-owner-test",
        )
    )
    generation_path = tmp_path / "controlled-generation.json"
    write(generation_path, {"fixture": "shared-current-generation-input"})
    original_load = StaticAuthorityLoader.load

    def load(path, *, expected_digest):
        if Path(path) == generation_path:
            assert expected_digest == generation.digest
            return generation
        return original_load(path, expected_digest=expected_digest)

    monkeypatch.setattr(StaticAuthorityLoader, "load", load)
    monkeypatch.setattr(
        native_dispatch_reconciler, "KubernetesNativeTaskPort", FixtureKubernetes
    )
    authority = tmp_path / "authority.json"
    write(
        authority,
        dict(
            schemaVersion="authority-foundation-runtime.v1",
            databaseUrl=database_url,
            migrationPath=str(migrations / "0018_browser_session_grant_authority.sql"),
            generationPath=str(generation_path),
            generationDigest=generation.digest,
            csrfSigningKeyPath=str(tmp_path / "unused-csrf"),
            continuationSigningKeyPath=str(tmp_path / "unused-continuation"),
            recoveryControlPath=str(control),
            databaseFingerprint=fingerprint,
            operatorId="operator:isolated-owner-test",
        ),
    )
    names = (
        set(DI_SOURCES)
        | {
            "operator/src/agent_operator/" + name
            for name in (
                "native_host_service.py",
                "native_host_service_config.py",
                "native_host_service_discovery.py",
                "native_host_service_state.py",
                "native_host_service_child.py",
                "native_dispatch_host.py",
            )
        }
        | {"console/backend/src/agent_console/bound_service_execution.py"}
    )
    manifest = tmp_path / "manifest.json"
    write(
        manifest,
        {
            "source": str(root),
            "sourceHashes": {
                name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                for name in names
            },
        },
    )
    leaves = []
    for kind, work, key, policy_path in (
        (
            "HUMAN_OWNED",
            human,
            "OWNED_BUSINESS_ADMISSION_POLICY",
            human.owned_business.path,
        ),
        (
            "BOUND_SERVICE",
            service,
            "NATIVE_BOUND_SERVICE_EXECUTION_POLICY",
            tmp_path / "bound-policy.json",
        ),
    ):
        if kind == "BOUND_SERVICE":
            write(
                policy_path,
                service.bound_service_execution.registry._policy().model_dump(
                    mode="json"
                ),
            )
        continuation = tmp_path / (kind + "-continuation.json")
        write(continuation, work.policy.model_dump(mode="json"))
        if kind == "HUMAN_OWNED":
            p = human.owned_business.policy
            scope = p.tenantId, p.securityDomain, p.subjectId
        else:
            p = service.bound_service_execution.registry._policy()
            scope = p.tenantId, p.securityDomain, p.subjectId
        env = dict(
            NATIVE_DISPATCH_DATABASE_URL=database_url,
            NATIVE_DISPATCH_AUTHORITY_CONFIGURATION=str(authority),
            NATIVE_DISPATCH_EXECUTION_MIGRATION=str(
                migrations / "0008_execution_runtime_authority.sql"
            ),
            NATIVE_DISPATCH_SCHEMA_MIGRATION=str(
                migrations / "0022_native_execution_dispatch.sql"
            ),
            NATIVE_DISPATCH_WORKER_ID="joint-factory-" + kind,
            NATIVE_DISPATCH_PREPARED_SKILL="registered-readonly-v1",
            NATIVE_DISPATCH_CONTINUATION_POLICY=str(continuation),
        )
        env[key] = str(policy_path)
        config = tmp_path / (kind + "-configuration.json")
        write(
            config,
            dict(
                enabled=True,
                namespace=scope[0],
                securityDomain=scope[1],
                principalId=scope[2],
                stateDirectory=str(tmp_path / "state"),
                manifestPath=str(manifest),
                manifestDigest=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                policyFiles={
                    k: hashlib.sha256(Path(env[k]).read_bytes()).hexdigest()
                    for k in (
                        "NATIVE_DISPATCH_AUTHORITY_CONFIGURATION",
                        "NATIVE_DISPATCH_CONTINUATION_POLICY",
                        key,
                    )
                },
                maxHosts=2,
                maxRestarts=0,
                pollSeconds=1,
                readinessSeconds=2,
                shutdownSeconds=2,
            ),
        )
        env_path = tmp_path / (kind + "-environment.json")
        write(env_path, env)
        leaves.append(
            dict(
                kind=kind,
                configurationPath=str(config),
                configurationDigest=hashlib.sha256(config.read_bytes()).hexdigest(),
                environmentPath=str(env_path),
                environmentDigest=hashlib.sha256(env_path.read_bytes()).hexdigest(),
            )
        )
    path = tmp_path / "policy-set.json"
    write(
        path,
        dict(schema="native-exact-host-policy-set.v1", enabled=True, leaves=leaves),
    )
    return PolicySetAssembly(PolicySetConfiguration(path))
