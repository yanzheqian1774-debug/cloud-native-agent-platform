"""Private opt-in process-service configuration, without execution authority."""

import hashlib
import json
import os
from pathlib import Path

from .native_host_service_state import private_directory
from .native_host_startup import owned_file


class Configuration:
    def __init__(self, path):
        self.path = str(Path(path))
        self.raw = owned_file(path)
        self.value = json.loads(self.raw)
        value = self.value
        expected = {
            "enabled",
            "namespace",
            "securityDomain",
            "principalId",
            "stateDirectory",
            "manifestPath",
            "manifestDigest",
            "policyFiles",
            "maxHosts",
            "pollSeconds",
            "readinessSeconds",
            "shutdownSeconds",
            "maxRestarts",
        }
        if set(value) != expected or value["enabled"] is not True:
            raise ValueError("HOST_SERVICE_CONFIGURATION_DISABLED_OR_INVALID")
        for key in (
            "namespace",
            "securityDomain",
            "principalId",
            "manifestPath",
            "manifestDigest",
            "stateDirectory",
        ):
            if not isinstance(value[key], str) or not value[key]:
                raise ValueError("HOST_SERVICE_CONFIGURATION_INVALID")
        for key, minimum, maximum in (
            ("maxHosts", 1, 8),
            ("pollSeconds", 1, 60),
            ("readinessSeconds", 1, 25),
            ("shutdownSeconds", 1, 60),
            ("maxRestarts", 0, 16),
        ):
            if type(value[key]) is not int or not minimum <= value[key] <= maximum:
                raise ValueError("HOST_SERVICE_CONFIGURATION_INVALID")
        self.directory = private_directory(value["stateDirectory"])
        manifest_path = Path(value["manifestPath"])
        if not manifest_path.is_absolute() or manifest_path.resolve() != manifest_path:
            raise ValueError("HOST_SERVICE_MANIFEST_INVALID")
        manifest_raw = manifest_path.read_bytes()
        if hashlib.sha256(manifest_raw).hexdigest() != value["manifestDigest"]:
            raise ValueError("HOST_SERVICE_MANIFEST_INVALID")
        manifest = json.loads(manifest_raw)
        root = Path(manifest["source"])
        loaded = Path(__file__).resolve()
        if (
            not loaded.is_relative_to(root)
            or manifest["sourceHashes"].get(str(loaded.relative_to(root)))
            != hashlib.sha256(loaded.read_bytes()).hexdigest()
        ):
            raise ValueError("HOST_SERVICE_INSTALLED_SOURCE_REQUIRED")
        critical = (
            "native_host_service.py",
            "native_host_service_config.py",
            "native_host_service_discovery.py",
            "native_host_service_state.py",
            "native_host_service_child.py",
            "native_dispatch_host.py",
        )
        for name in critical:
            relative = str(loaded.with_name(name).relative_to(root))
            if relative not in manifest["sourceHashes"]:
                raise ValueError("HOST_SERVICE_INSTALLED_SOURCE_REQUIRED")
        self.files = {str(manifest_path): value["manifestDigest"]}
        for relative, expected_digest in manifest["sourceHashes"].items():
            p = root / relative
            if (
                Path(relative).is_absolute()
                or p.resolve() != p
                or not p.is_relative_to(root)
            ):
                raise ValueError("HOST_SERVICE_MANIFEST_INVALID")
            self.files[str(p)] = expected_digest
        required = {
            "NATIVE_DISPATCH_AUTHORITY_CONFIGURATION",
            "NATIVE_DISPATCH_CONTINUATION_POLICY",
            "OWNED_BUSINESS_ADMISSION_POLICY",
        }
        allowed = required | {
            "NATIVE_LOOP_RUNTIME_FILE",
            "NATIVE_DURABLE_WAIT_CONFIGURATION",
            "OWNED_BUSINESS_ONTOLOGY_CORRECTION_POLICY",
            "PROVIDER_BUDGET_EXTENSION_POLICY",
        }
        if (
            not isinstance(value["policyFiles"], dict)
            or not required <= set(value["policyFiles"]) <= allowed
        ):
            raise ValueError("HOST_SERVICE_POLICY_BINDING_REQUIRED")
        self.environment = dict(os.environ)
        if (
            self.environment.get("NATIVE_DISPATCH_PREPARED_SKILL")
            != "registered-readonly-v1"
        ):
            raise ValueError("HOST_SERVICE_READONLY_MODE_REQUIRED")
        if any(
            self.environment.get(k) and k not in value["policyFiles"] for k in allowed
        ):
            raise ValueError("HOST_SERVICE_POLICY_BINDING_REQUIRED")
        for name, expected_digest in value["policyFiles"].items():
            file_path = self.environment.get(name, "")
            if hashlib.sha256(owned_file(file_path)).hexdigest() != expected_digest:
                raise ValueError("HOST_SERVICE_POLICY_CHANGED")
            self.files[file_path] = expected_digest
            if name == "NATIVE_LOOP_RUNTIME_FILE":
                model = json.loads(owned_file(file_path))
                self.files[model["modelRuntimeFile"]] = model["modelRuntimeDigest"]
        if any(
            name in self.environment
            for name in (
                "NATIVE_HOST_SERVICE_LOCK_FD",
                "NATIVE_HOST_SERVICE_READY_FD",
                "NATIVE_HOST_SERVICE_CONTROL_FD",
                "NATIVE_HOST_STARTUP_CONFIGURATION",
            )
        ):
            raise ValueError("HOST_SERVICE_NESTED_LAUNCH_REJECTED")
        self.verify()

    def verify(self):
        if owned_file(self.path) != self.raw or any(
            hashlib.sha256(Path(p).read_bytes()).hexdigest() != h
            for p, h in self.files.items()
        ):
            raise ValueError("HOST_SERVICE_PINNED_SOURCE_CHANGED")
        if any(
            os.environ.get(name) != self.environment.get(name)
            for name in self.value["policyFiles"]
        ):
            raise ValueError("HOST_SERVICE_ENVIRONMENT_CHANGED")
