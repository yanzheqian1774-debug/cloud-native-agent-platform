"""Explicit D324-4 operator provisioning; never called by server startup.

Stage a successor immutable generation, then migrate/activate via existing
Authority controller with the old writer stopped. Account commands are separate.
Passwords only exist in owner-only local files, never in command arguments/logs.
"""

import argparse
import hashlib
import json
import os
import secrets
import stat
from datetime import UTC, datetime
from pathlib import Path

from agent_console.authority_configuration import StaticAuthorityLoader
from agent_console.authority_postgres import PostgresAuthorityRepository
from agent_console.local_accounts import migrate, operate


def write_once(path, value):
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("IMMUTABLE_ACCOUNT_CANDIDATE_CONFLICT")
    else:
        with path.open("xb") as f:
            f.write(raw)
    return hashlib.sha256(raw).hexdigest()


def stage(source, output):
    runtime = json.loads(source.read_text())
    current = json.loads(Path(runtime["generationPath"]).read_text())
    StaticAuthorityLoader.load(
        Path(runtime["generationPath"]), expected_digest=runtime["generationDigest"]
    )
    if current.get("localAccounts"):
        raise ValueError("ACCOUNTS_ALREADY_CONFIGURED")
    candidate = {
        **current,
        "generation": current["generation"] + 1,
        "auditSource": "S5-V023-IMPL-324:D324-4-local-accounts",
        "localAccounts": [
            {
                "username": username,
                "grantSourceCredentialId": "credential:324:" + role + ":recovery-v1",
            }
            for username, role in [
                ("demo324", "requester"),
                ("reviewer324", "approver"),
            ]
        ],
    }
    migration = (
        Path(__file__).resolve().parents[2]
        / "console/backend/migrations/0018_browser_session_grant_authority.sql"
    )
    if migration.read_bytes() != Path(runtime["migrationPath"]).read_bytes():
        raise ValueError("BASE_AUTHORITY_MIGRATION_CONFLICT")
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    digest = write_once(output / "generation.json", candidate)
    StaticAuthorityLoader.load(output / "generation.json", expected_digest=digest)
    write_once(output / "source-runtime.json", runtime)
    write_once(
        output / "runtime.json",
        {
            **runtime,
            "migrationPath": str(migration),
            "generationPath": str(output / "generation.json"),
            "generationDigest": digest,
            "operatorId": "operator:s5-324-local-accounts",
        },
    )
    return {
        "generation": candidate["generation"],
        "digest": digest,
        "oldCredentialsUnchanged": True,
        "businessGrantsCreated": 0,
    }


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=["stage", "migrate", "CREATE", "RESET", "DISABLE", "ENABLE", "REVOKE"],
    )
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--username", choices=["demo324", "reviewer324"])
    parser.add_argument("--password-file", type=Path)
    parser.add_argument("--command-id")
    args = parser.parse_args()
    if args.action == "stage":
        if args.output is None:
            parser.error("--output required")
        print(json.dumps(stage(args.runtime, args.output)))
        return
    runtime = json.loads(args.runtime.read_text())
    generation = StaticAuthorityLoader.load(
        Path(runtime["generationPath"]), expected_digest=runtime["generationDigest"]
    )
    repo = PostgresAuthorityRepository(
        runtime["databaseUrl"], migration_path=Path(runtime["migrationPath"])
    )
    try:
        if args.action == "migrate":
            migrate(repo)
            print(json.dumps({"migration": 36, "accountsCreated": 0}))
            return
        if not args.username or not args.command_id:
            parser.error("--username and --command-id required")
        if repo.active_generation()[:2] != (generation.generation, generation.digest):
            raise ValueError("AUTHORITY_RECOVERY_REQUIRED")
        binding = next(
            a for a in generation.local_accounts if a.username == args.username
        )
        password = None
        if args.action in {"CREATE", "RESET"}:
            if args.password_file is None:
                parser.error("--password-file required")
            path = args.password_file
            if not path.exists():
                with path.open("x") as f:
                    f.write(secrets.token_urlsafe(24))
            if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) != 0o600:
                raise ValueError("PASSWORD_FILE_MUST_BE_PRIVATE")
            password = path.read_text()
        revision = operate(
            repo,
            binding,
            action=args.action,
            command_id=args.command_id,
            operator_id=runtime["operatorId"],
            now=datetime.now(UTC),
            password=password,
        )
        print(
            json.dumps(
                {
                    "username": args.username,
                    "action": args.action,
                    "revision": revision,
                    "businessGrantsCreated": 0,
                }
            )
        )
    finally:
        repo.close()


if __name__ == "__main__":
    main()
