"""Preserve and review current original assets; never initialize or mutate DB."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for part in (
    "core/src",
    "gateway/src",
    "operator/src",
    "runtime/src",
    "console/backend/src",
):
    sys.path.insert(0, str(ROOT / part))
import psycopg  # noqa: E402
from agent_console.acceptance_recovery import (  # noqa: E402
    database_snapshot,
    file_identity,
    verify_files,
)
from agent_console.authority_configuration import (  # noqa: E402
    AuthorityRuntimeConfiguration,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--reviewed-source-digests", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(mode=0o700, exist_ok=False)
    manifest = json.loads(args.original_manifest.read_text())
    reviewed = json.loads(args.reviewed_source_digests.read_text())
    allowed = {
        "console/backend/src/agent_console/acceptance_recovery.py",
        "console/backend/tests/test_workbench_creator_continuation_postgres.py",
        "scripts/acceptance/resume_kimi_acceptance.py",
    }
    for relative in allowed:
        path = ROOT / relative
        old = manifest["files"][str(path)]
        current = file_identity(path)
        baseline = subprocess.check_output(
            ["git", "show", f"HEAD:{relative}"], cwd=ROOT
        )
        if (
            hashlib.sha256(baseline).hexdigest() != old["sha256"]
            or current["sha256"] != reviewed.get(relative)
            or current["mode"] != old["mode"]
            or current["uid"] != old["uid"]
        ):
            raise RuntimeError("UNREVIEWED_SOURCE_DELTA")
        manifest["files"][str(path)] = current
    verify_files(manifest["files"])
    runtime = AuthorityRuntimeConfiguration.from_mapping(
        json.loads(Path(manifest["runtime"]).read_text())
    )
    with psycopg.connect(runtime.database_url, autocommit=True) as connection:
        snapshot = database_snapshot(connection)
    changed = [
        name
        for name, value in snapshot["tables"].items()
        if value != manifest["database"]["tables"].get(name)
    ]
    if snapshot["columnsDigest"] != manifest["database"]["columnsDigest"] or any(
        name
        not in {
            "browser_identity.sessions",
            "browser_identity.login_nonces",
            "authorization_admin.audit_events",
        }
        for name in changed
    ):
        raise RuntimeError("UNEXPECTED_PRESERVATION_DRIFT")
    backup = args.output / "before-create.dump"
    with backup.open("xb") as stream:
        subprocess.run(
            [
                "docker",
                "exec",
                "kimi-real-01a0a96e-postgres",
                "pg_dump",
                "-U",
                "postgres",
                "-d",
                "kimi_acceptance",
                "--format=custom",
                "--serializable-deferrable",
            ],
            stdout=stream,
            check=True,
        )
    with backup.open("rb") as stream:
        subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                "kimi-real-01a0a96e-postgres",
                "pg_restore",
                "--file=/dev/null",
            ],
            stdin=stream,
            stdout=subprocess.DEVNULL,
            check=True,
        )
    (args.output / "old-manifest.json").write_bytes(args.original_manifest.read_bytes())
    manifest["database"] = snapshot
    manifest["dist"] = str(args.dist)
    manifest["restrictedCreate"] = True
    modules = {
        "recovery": ROOT / "console/backend/src/agent_console/acceptance_recovery.py",
        "restrictedCreate": ROOT
        / "console/backend/src/agent_console/acceptance_recovery_create.py",
    }
    manifest["candidate"] = {
        "source": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "tree": subprocess.check_output(
            ["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True
        ).strip(),
        "modules": {
            name: file_identity(path)["sha256"] for name, path in modules.items()
        },
    }
    for path in [
        *modules.values(),
        Path(__file__),
        ROOT / "scripts/acceptance/resume_kimi_acceptance.py",
        *args.dist.rglob("*"),
    ]:
        if path.is_file():
            manifest["files"][str(path)] = file_identity(path)
    destination = args.output / "restricted-create-manifest.json"
    destination.write_text(json.dumps(manifest, indent=2))
    summary = {
        "backupSha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
        "backupBytes": backup.stat().st_size,
        "backupDecoded": True,
        "changedTables": changed,
        "candidate": manifest["candidate"],
        "manifestSha256": file_identity(destination)["sha256"],
    }
    (args.output / "preservation-summary.json").write_text(
        json.dumps(summary, indent=2)
    )
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
