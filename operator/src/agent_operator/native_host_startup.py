"""Opt-in startup observation for new managed Native work, not recovery authority."""

import hashlib
import inspect
import json
import os
import stat
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def require(ok):
    if not ok:
        raise ValueError("NATIVE_HOST_STARTUP_PROVENANCE_INVALID")


def owned_file(path):
    path = Path(path)
    require(path.is_absolute() and not path.is_symlink())
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        require(
            stat.S_ISREG(info.st_mode)
            and info.st_uid == os.getuid()
            and stat.S_IMODE(info.st_mode) == 0o600
        )
        return stream.read()


class StartupObservation:
    def __init__(self, configuration, assembly):
        from agent_console.prepared_native_skill import PreparedNativeSkillCaller

        from .native_dispatch_reconciler import ManagedSkillNativeTransport

        self.config_path = Path(configuration)
        self.config_bytes = owned_file(self.config_path)
        self.config = json.loads(self.config_bytes)
        cfg = self.config
        require(
            set(cfg) - {"predecessorRecordPath", "predecessorDigest"}
            == {
                "workerId",
                "namespace",
                "securityDomain",
                "principalId",
                "manifestPath",
                "manifestDigest",
                "recordPath",
                "policyFiles",
                "authorizationResources",
            }
        )
        require(
            all(
                isinstance(cfg[k], str) and cfg[k]
                for k in cfg
                if k not in {"policyFiles", "authorizationResources"}
            )
        )
        require(
            cfg["workerId"]
            == assembly.worker.worker_id
            == os.environ.get("NATIVE_DISPATCH_WORKER_ID")
        )
        require(type(assembly.worker.transport) is ManagedSkillNativeTransport)
        require(type(assembly.worker.transport.caller) is PreparedNativeSkillCaller)
        require(
            os.environ.get("NATIVE_DISPATCH_PREPARED_SKILL") == "registered-readonly-v1"
        )
        manifest_path = Path(cfg["manifestPath"])
        require(
            manifest_path.is_absolute() and manifest_path.resolve() == manifest_path
        )
        manifest_bytes = manifest_path.read_bytes()
        require(hashlib.sha256(manifest_bytes).hexdigest() == cfg["manifestDigest"])
        manifest = json.loads(manifest_bytes)
        root = Path(manifest["source"])
        require(root.is_absolute() and root.resolve() == root)
        hashes = manifest["sourceHashes"]
        require(isinstance(hashes, dict) and 1 <= len(hashes) <= 10000)
        self.files = {str(Path(cfg["manifestPath"])): cfg["manifestDigest"]}
        for relative, expected in hashes.items():
            path = root / relative
            require(
                not Path(relative).is_absolute()
                and path.resolve().is_relative_to(root)
                and path.resolve() == path
            )
            require(hashlib.sha256(path.read_bytes()).hexdigest() == expected)
            self.files[str(path)] = expected
        critical = [
            Path(__file__).resolve(),
            Path(inspect.getfile(ManagedSkillNativeTransport)).resolve(),
            Path(inspect.getfile(PreparedNativeSkillCaller)).resolve(),
            Path(__file__).with_name("native_dispatch_host.py").resolve(),
        ]
        if os.environ.get("NATIVE_BOUND_SERVICE_EXECUTION_POLICY"):
            from agent_console import bound_service_execution

            critical.append(Path(bound_service_execution.__file__).resolve())
        if os.environ.get("NATIVE_BOUND_SERVICE_LOCAL_BUDGET_POLICY"):
            from agent_console import service_local_budget

            critical.append(Path(service_local_budget.__file__).resolve())

        require(all(str(p) in self.files for p in critical))
        require(isinstance(cfg["policyFiles"], dict) and cfg["policyFiles"])
        policies = {}
        for env, expected in cfg["policyFiles"].items():
            require(
                env
                in {
                    "NATIVE_DISPATCH_AUTHORITY_CONFIGURATION",
                    "NATIVE_LOOP_RUNTIME_FILE",
                    "NATIVE_DISPATCH_CONTINUATION_POLICY",
                    "OWNED_BUSINESS_ADMISSION_POLICY",
                    "NATIVE_BOUND_SERVICE_EXECUTION_POLICY",
                    "NATIVE_DURABLE_WAIT_CONFIGURATION",
                    "OWNED_BUSINESS_ONTOLOGY_CORRECTION_POLICY",
                    "PROVIDER_BUDGET_EXTENSION_POLICY",
                    "NATIVE_BOUND_SERVICE_LOCAL_BUDGET_POLICY",
                }
            )
            path = os.environ.get(env, "")
            require(path and hashlib.sha256(owned_file(path)).hexdigest() == expected)
            policies[env] = {"path": path, "digest": expected}
            self.files[path] = expected
            if env == "NATIVE_LOOP_RUNTIME_FILE":
                loop = json.loads(owned_file(path))
                runtime_path = loop["modelRuntimeFile"]
                runtime_digest = loop["modelRuntimeDigest"]
                require(
                    hashlib.sha256(owned_file(runtime_path)).hexdigest()
                    == runtime_digest
                )
                self.files[runtime_path] = runtime_digest
                policies[env]["modelRuntimeDigest"] = runtime_digest
        require("NATIVE_DISPATCH_AUTHORITY_CONFIGURATION" in policies)
        require(
            not os.environ.get("NATIVE_BOUND_SERVICE_LOCAL_BUDGET_POLICY")
            or "NATIVE_BOUND_SERVICE_EXECUTION_POLICY" in policies
        )
        require(
            not (
                "NATIVE_BOUND_SERVICE_EXECUTION_POLICY" in policies
                and "OWNED_BUSINESS_ADMISSION_POLICY" in policies
            )
        )
        require(
            all(
                not os.environ.get(key) or key in policies
                for key in (
                    "NATIVE_LOOP_RUNTIME_FILE",
                    "NATIVE_DISPATCH_CONTINUATION_POLICY",
                    "OWNED_BUSINESS_ADMISSION_POLICY",
                    "NATIVE_BOUND_SERVICE_EXECUTION_POLICY",
                    "NATIVE_DURABLE_WAIT_CONFIGURATION",
                    "OWNED_BUSINESS_ONTOLOGY_CORRECTION_POLICY",
                    "PROVIDER_BUDGET_EXTENSION_POLICY",
                    "NATIVE_BOUND_SERVICE_LOCAL_BUDGET_POLICY",
                )
            )
        )
        require(
            isinstance(cfg["authorizationResources"], list)
            and 1 <= len(cfg["authorizationResources"]) <= 128
            and all(
                isinstance(x, str) and x.startswith("governed-execution:prepared:")
                for x in cfg["authorizationResources"]
            )
        )
        predecessors = []
        if cfg.get("predecessorRecordPath") or cfg.get("predecessorDigest"):
            prior = json.loads(owned_file(cfg["predecessorRecordPath"]))
            old = prior["observation"]
            require(prior["digest"] == cfg["predecessorDigest"] == digest(old))
            require(
                all(
                    old[k] == cfg[k]
                    for k in (
                        "workerId",
                        "namespace",
                        "securityDomain",
                        "principalId",
                        "authorizationResources",
                    )
                )
            )
            predecessors = [prior["digest"], *old.get("predecessorDigests", [])]
            require(
                len(predecessors) <= 32 and len(predecessors) == len(set(predecessors))
            )
            self.files[cfg["predecessorRecordPath"]] = hashlib.sha256(
                owned_file(cfg["predecessorRecordPath"])
            ).hexdigest()
        self.pid = os.getpid()
        self.birth = subprocess.check_output(
            ["ps", "-p", str(self.pid), "-o", "lstart="], text=True
        ).strip()
        require(bool(self.birth))
        active = assembly.authority_repository.active_generation()
        require(active is not None)
        self.record = {
            "schema": "native-host-startup.v1",
            "startupId": str(uuid4()),
            "predecessorDigests": predecessors,
            "workerId": cfg["workerId"],
            "namespace": cfg["namespace"],
            "securityDomain": cfg["securityDomain"],
            "principalId": cfg["principalId"],
            "authorizationResources": cfg["authorizationResources"],
            "pid": self.pid,
            "processBirth": self.birth,
            "observedAt": datetime.now(UTC).isoformat(),
            "installedRevision": manifest["commit"],
            "manifestPath": str(manifest_path),
            "sourceDirectory": str(root),
            "manifestDigest": cfg["manifestDigest"],
            "sourceHashesDigest": digest(hashes),
            "adapterFiles": {
                str(p.relative_to(root)): self.files[str(p)] for p in critical
            },
            "launchDigest": digest(
                {
                    "executable": sys.executable,
                    "module": "agent_operator.native_dispatch_host",
                    "workerId": cfg["workerId"],
                    "preparedMode": os.environ["NATIVE_DISPATCH_PREPARED_SKILL"],
                    "policies": policies,
                }
            ),
            "authorityGeneration": active[0],
            "authorityDigest": active[1],
            "recoveryEpoch": active[2],
        }
        self.record_digest = digest(self.record)
        target = Path(cfg["recordPath"])
        require(target.is_absolute() and target.parent.resolve() == target.parent)
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(
                {"observation": self.record, "digest": self.record_digest},
                stream,
                sort_keys=True,
            )
            stream.flush()
            os.fsync(stream.fileno())
        directory_fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        self.record_bytes = owned_file(target)
        self.env = {
            key: os.environ.get(key)
            for key in (
                *policies,
                "NATIVE_DISPATCH_WORKER_ID",
                "NATIVE_DISPATCH_PREPARED_SKILL",
            )
        }

    def current(self):
        require(
            os.getpid() == self.pid
            and owned_file(self.config_path) == self.config_bytes
        )
        require(owned_file(self.config["recordPath"]) == self.record_bytes)
        require(all(os.environ.get(k) == v for k, v in self.env.items()))
        require(
            all(
                hashlib.sha256(Path(p).read_bytes()).hexdigest() == expected
                for p, expected in self.files.items()
            )
        )
        return {"observation": self.record, "digest": self.record_digest}

    def observe_only_receipt(self, claim):
        """Local process provenance; never an effect/claim/terminal authority fact."""
        value = self.current()
        receipt = {
            "kind": "NATIVE_HOST_OBSERVE_ONLY_CONTINUATION",
            "startupDigest": value["digest"],
            "commandId": str(claim.command.command_id),
            "commandDigest": claim.command.digest,
            "workerId": claim.worker_id,
            "claimGeneration": claim.claim_generation.value,
            "effectInvocationAllowed": False,
        }
        target = Path(
            self.config["recordPath"] + ".observe-" + digest(receipt) + ".json"
        )
        data = json.dumps(receipt, sort_keys=True).encode()
        try:
            fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            require(owned_file(target) == data)
        else:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            directory_fd = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
