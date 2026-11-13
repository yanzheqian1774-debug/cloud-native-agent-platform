"""Offline exact-host service configuration; no database/process/model operations."""

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from .native_host_service_state import private_directory, write
from .native_host_startup import owned_file


def prepare(manifest_path, state_directory, output, *, enabled=False, max_hosts=2):
    from agent_console.owned_business_policy import OwnedBusinessPolicy

    policy = OwnedBusinessPolicy.load(os.environ["OWNED_BUSINESS_ADMISSION_POLICY"])
    if not policy.enabled or policy.expiresAt <= datetime.now(UTC):
        raise ValueError("HOST_SERVICE_CURRENT_OWNED_POLICY_REQUIRED")
    manifest_path = Path(manifest_path)
    state_directory, output = Path(state_directory), Path(output)
    if any(
        not p.is_absolute() or p.resolve() != p
        for p in (manifest_path, state_directory, output)
    ):
        raise ValueError("HOST_SERVICE_ABSOLUTE_OWNED_PATH_REQUIRED")
    if type(max_hosts) is not int or not 1 <= max_hosts <= 8:
        raise ValueError("HOST_SERVICE_CAPACITY_INVALID")
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    root = Path(manifest["source"])
    if not root.is_absolute() or root.resolve() != root:
        raise ValueError("HOST_SERVICE_MANIFEST_INVALID")
    for name, expected in manifest["sourceHashes"].items():
        path = root / name
        if (
            path.resolve() != path
            or not path.is_relative_to(root)
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            raise ValueError("HOST_SERVICE_MANIFEST_INVALID")
    required = (
        "NATIVE_DISPATCH_AUTHORITY_CONFIGURATION",
        "NATIVE_DISPATCH_CONTINUATION_POLICY",
        "OWNED_BUSINESS_ADMISSION_POLICY",
    )
    names = (
        *required,
        *(
            name
            for name in (
                "NATIVE_LOOP_RUNTIME_FILE",
                "NATIVE_DURABLE_WAIT_CONFIGURATION",
            )
            if os.environ.get(name)
        ),
    )
    files = {
        name: hashlib.sha256(owned_file(os.environ[name])).hexdigest() for name in names
    }
    value = {
        "enabled": enabled,
        "namespace": policy.tenantId,
        "securityDomain": policy.securityDomain,
        "principalId": policy.subjectId,
        "stateDirectory": str(state_directory),
        "manifestPath": str(manifest_path),
        "manifestDigest": hashlib.sha256(raw).hexdigest(),
        "policyFiles": files,
        "maxHosts": max_hosts,
        "pollSeconds": 2,
        "readinessSeconds": 20,
        "shutdownSeconds": 30,
        "maxRestarts": 4,
    }
    private_directory(output.parent)
    write(output, value, exclusive=True)
    return {
        "configurationPath": str(output),
        "enabled": enabled,
        "manifestDigest": value["manifestDigest"],
        "policyDigest": policy.digest,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--state-directory", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--enabled", action="store_true")
    parser.add_argument("--max-hosts", type=int, default=2)
    args = parser.parse_args()
    print(
        json.dumps(
            prepare(
                args.manifest,
                args.state_directory,
                args.output,
                enabled=args.enabled,
                max_hosts=args.max_hosts,
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
