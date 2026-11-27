"""Explicit private two-leaf composition. Loading does not construct owners."""

import hashlib
import importlib
import json
import os
from pathlib import Path
from types import MappingProxyType

from .native_host_policy_set import LeafKind, scope_of
from .native_host_service_config import Configuration
from .native_host_startup import owned_file

ENVIRONMENT_KEYS = frozenset(
    {
        "NATIVE_DISPATCH_DATABASE_URL",
        "NATIVE_DISPATCH_AUTHORITY_CONFIGURATION",
        "NATIVE_DISPATCH_EXECUTION_MIGRATION",
        "NATIVE_DISPATCH_SCHEMA_MIGRATION",
        "NATIVE_DISPATCH_WORKER_ID",
        "NATIVE_DISPATCH_TASK_PREFIX",
        "NATIVE_DISPATCH_POLL_SECONDS",
        "NATIVE_DISPATCH_PREPARED_SKILL",
        "NATIVE_DISPATCH_CONTINUATION_POLICY",
        "NATIVE_BOUND_SERVICE_EXECUTION_POLICY",
        "NATIVE_BOUND_SERVICE_LOCAL_BUDGET_POLICY",
        "OWNED_BUSINESS_ADMISSION_POLICY",
        "OWNED_BUSINESS_RETAINED_HISTORY_POLICIES",
        "OWNED_BUSINESS_ONTOLOGY_CORRECTION_POLICY",
        "NATIVE_LOOP_RUNTIME_FILE",
        "NATIVE_DURABLE_WAIT_CONFIGURATION",
        "PROVIDER_BUDGET_EXTENSION_POLICY",
    }
)
COMMON_PROCESS_KEYS = ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "TZ", "PYTHONPATH")
GLOBAL_FIELDS = (
    "stateDirectory",
    "manifestPath",
    "manifestDigest",
    "maxHosts",
    "maxRestarts",
    "pollSeconds",
    "readinessSeconds",
    "shutdownSeconds",
)
DI_SOURCES = (
    "operator/src/agent_operator/native_host_policy_set.py",
    "operator/src/agent_operator/native_host_policy_set_config.py",
    "operator/src/agent_operator/native_host_policy_set_assembly.py",
    "operator/src/agent_operator/native_dispatch_reconciler.py",
    "console/backend/src/agent_console/prepared_native_composition.py",
    "console/backend/src/agent_console/native_loop_runtime.py",
    "console/backend/src/agent_console/plan_suggestion_runtime.py",
    "console/backend/src/agent_console/owned_business_work_reader.py",
    "console/backend/src/agent_console/owned_business_retained_history.py",
    "console/backend/src/agent_console/ontology_action_correction.py",
    "console/backend/src/agent_console/service_local_budget.py",
)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("HOST_POLICY_SET_DUPLICATE_FIELD")
        result[key] = value
    return result


def document(raw):
    value = json.loads(raw, object_pairs_hook=unique_object)
    if not isinstance(value, dict):
        raise ValueError("HOST_POLICY_SET_OBJECT_REQUIRED")
    return value


class PolicySetConfiguration:
    def __init__(self, path, *, environment=None):
        from agent_console.governed_execution_ownership import (
            execution_database_fingerprint,
        )

        ambient = dict(os.environ if environment is None else environment)
        self.path = str(Path(path))
        self.raw = owned_file(path)
        value = document(self.raw)
        if (
            set(value) != {"schema", "enabled", "leaves"}
            or value["schema"] != "native-exact-host-policy-set.v1"
            or value["enabled"] is not True
            or not isinstance(value["leaves"], list)
            or len(value["leaves"]) != 2
        ):
            raise ValueError("HOST_POLICY_SET_DISABLED_OR_INVALID")
        self.files = {self.path: hashlib.sha256(self.raw).hexdigest()}
        self.ca_files = {}
        configs, kinds, fingerprints = {}, set(), set()
        common = {k: ambient[k] for k in COMMON_PROCESS_KEYS if k in ambient}
        for leaf in value["leaves"]:
            if not isinstance(leaf, dict) or set(leaf) != {
                "kind",
                "configurationPath",
                "configurationDigest",
                "environmentPath",
                "environmentDigest",
            }:
                raise ValueError("HOST_POLICY_SET_LEAF_INVALID")
            kind = LeafKind(leaf["kind"])
            if kind in kinds:
                raise ValueError("HOST_POLICY_SET_DUPLICATE_KIND")
            kinds.add(kind)
            raw = {}
            for prefix in ("configuration", "environment"):
                file_path = leaf[prefix + "Path"]
                data = owned_file(file_path)
                actual = hashlib.sha256(data).hexdigest()
                if actual != leaf[prefix + "Digest"]:
                    raise ValueError("HOST_POLICY_SET_PIN_CHANGED")
                self.files[file_path] = actual
                raw[prefix] = document(data)
            selected = raw["environment"]
            if (
                not set(selected) <= ENVIRONMENT_KEYS
                or any(not isinstance(v, str) or not v for v in selected.values())
                or not selected.get("NATIVE_DISPATCH_DATABASE_URL")
            ):
                raise ValueError("HOST_POLICY_SET_ENVIRONMENT_INVALID")
            service = bool(selected.get("NATIVE_BOUND_SERVICE_EXECUTION_POLICY"))
            human = bool(selected.get("OWNED_BUSINESS_ADMISSION_POLICY"))
            if service == human or service != (kind == LeafKind.BOUND_SERVICE):
                raise ValueError("HOST_POLICY_SET_OWNER_KIND_MISMATCH")
            cfg = Configuration(
                leaf["configurationPath"], environment={**common, **selected}
            )
            scope = scope_of(cfg.value)
            if scope in configs:
                raise ValueError("HOST_POLICY_SET_AMBIGUOUS_SCOPE")
            configs[scope] = (kind, cfg)
            fingerprints.add(
                execution_database_fingerprint(selected["NATIVE_DISPATCH_DATABASE_URL"])
            )
        if len(fingerprints) != 1:
            raise ValueError("HOST_POLICY_SET_DATABASE_MISMATCH")
        self.fingerprint = next(iter(fingerprints))
        self.leaves = MappingProxyType(configs)
        first, second = [cfg for _, cfg in configs.values()]
        if any(first.value[k] != second.value[k] for k in GLOBAL_FIELDS):
            raise ValueError("HOST_POLICY_SET_GLOBAL_CONFIGURATION_MISMATCH")
        self.value, self.directory = first.value, first.directory
        manifest = document(owned_file(first.value["manifestPath"]))
        if not set(DI_SOURCES) <= set(manifest["sourceHashes"]):
            raise ValueError("HOST_POLICY_SET_DI_SOURCE_PINS_REQUIRED")
        # Pin the actually imported DI modules as well as files on disk. A
        # hostile/accidental PYTHONPATH must not pair this loader with other code.
        root = Path(manifest["source"])
        for relative in DI_SOURCES:
            module_name = relative.split("/src/", 1)[1][:-3].replace("/", ".")
            loaded = importlib.import_module(module_name)
            if Path(loaded.__file__).resolve() != root / relative:
                raise ValueError("HOST_POLICY_SET_SOURCE_ROOT_MISMATCH")
        for _, cfg in self.leaves.values():
            loop_path = cfg.environment.get("NATIVE_LOOP_RUNTIME_FILE")
            if loop_path:
                loop = document(owned_file(loop_path))
                runtime = document(owned_file(loop["modelRuntimeFile"]))
                tls = runtime.get("tls")
                if not isinstance(tls, dict) or set(tls) != {"caFile"}:
                    raise ValueError("HOST_POLICY_SET_TLS_CONFIGURATION_REQUIRED")
                if tls["caFile"] is not None:
                    ca = Path(tls["caFile"])
                    if not ca.is_absolute() or ca.resolve() != ca or not ca.is_file():
                        raise ValueError("HOST_POLICY_SET_TLS_CA_INVALID")
                    self.ca_files[str(ca)] = hashlib.sha256(ca.read_bytes()).hexdigest()
        self.verify()

    def for_candidate(self, candidate):
        selected = self.leaves.get(scope_of(candidate))
        if selected is None:
            raise ValueError("HOST_POLICY_SET_NO_MATCH")
        selected[1].verify()
        return selected[1]

    def verify(self):
        if any(
            hashlib.sha256(owned_file(p)).hexdigest() != h
            for p, h in self.files.items()
        ):
            raise ValueError("HOST_POLICY_SET_PIN_CHANGED")
        if any(
            Path(p).resolve() != Path(p)
            or hashlib.sha256(Path(p).read_bytes()).hexdigest() != h
            for p, h in self.ca_files.items()
        ):
            raise ValueError("HOST_POLICY_SET_TLS_CA_CHANGED")
        for _, cfg in self.leaves.values():
            cfg.verify()
