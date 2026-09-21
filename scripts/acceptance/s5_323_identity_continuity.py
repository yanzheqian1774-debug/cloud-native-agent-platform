"""Human-operated 323 continuity activation; --check is read-only, no provider IO.

The manifest is host-owned, candidate-bound and contains paths, never credentials.
Controlled rehearsals must use a separate DB/port and cannot target the original.
"""

import argparse
import copy
import fcntl
import hashlib
import json
import os
import re
import secrets
import signal
import ssl
import stat
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import psycopg
from psycopg.rows import dict_row


def require(condition, code):
    if not condition:
        raise RuntimeError(code)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, default=str)
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o600)


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def checked(response, expected=200):
    media = response.headers.get("content-type", "").split(";")[0]
    meta = {
        "path": urlsplit(str(response.url)).path,
        "status": response.status_code,
        "contentType": media,
        "redirect": response.is_redirect,
        "bytes": len(response.content),
    }
    require(
        response.status_code == expected and not response.is_redirect,
        "HTTP_STATUS " + json.dumps(meta),
    )
    require(media == "application/json", "HTTP_CONTENT_TYPE " + json.dumps(meta))
    try:
        value = response.json()
    except ValueError:
        raise RuntimeError("HTTP_JSON_INVALID " + json.dumps(meta)) from None
    require(isinstance(value, dict), "HTTP_OBJECT_REQUIRED")
    return value


class Activation:
    def __init__(self, manifest_path):
        self.path = Path(manifest_path).resolve()
        self.m = read(self.path)
        self.root = Path(self.m["root"])
        self.out = Path(self.m["output"])
        self.runtime = read(self.m["oldRuntime"])
        self.db = self.runtime["databaseUrl"]
        self.url = self.m["url"]
        for part in (
            "console/backend/src",
            "core/src",
            "runtime/src",
            "operator/src",
            "conformance_harness/src",
            "gateway/src",
            "experiments/s5-spike-005-runtime-target-manifest",
            "experiments/s5-spike-007-capability-rest-fixtures",
        ):
            sys.path.insert(0, str(self.root / part))

    def connection(self):
        return psycopg.connect(self.db, row_factory=dict_row)

    def facts(self):
        with self.connection() as c:
            c.execute("SET TRANSACTION READ ONLY")
            return {
                table: hashlib.sha256(
                    json.dumps(
                        c.execute(
                            "SELECT to_jsonb(t) AS value FROM "
                            + table
                            + " t ORDER BY to_jsonb(t)::text"
                        ).fetchall(),
                        sort_keys=True,
                        default=str,
                    ).encode()
                ).hexdigest()
                for table in self.m["protectedTables"]
            }

    def check(self):
        m = self.m
        require(
            not self.path.is_symlink()
            and self.path.stat().st_uid == os.geteuid()
            and stat.S_IMODE(self.path.stat().st_mode) == 0o600,
            "MANIFEST_OWNERSHIP",
        )
        require(os.geteuid() == m["uid"], "OPERATOR_UID_MISMATCH")
        parsed = urlsplit(self.db)
        controlled = m.get("controlled", False)
        require(
            (parsed.hostname, parsed.port)
            == ("127.0.0.1", 64332 if controlled else 64330),
            "DATABASE_BOUNDARY",
        )
        require(
            urlsplit(self.url).hostname == "127.0.0.1"
            and urlsplit(self.url).port == (19438 if controlled else 19436),
            "SERVICE_BOUNDARY",
        )
        require(not controlled or "controlled" in str(self.out), "TEST_OUTPUT_BOUNDARY")
        require(m["task"] == "S5-V023-ARCH-323", "TASK_BOUNDARY")
        for path, digest in m["files"].items():
            require(
                sha(path) == digest, "ENTRY_OR_CONFIGURATION_CHANGED " + Path(path).name
            )
        if not controlled:
            candidate_sha = subprocess.check_output(
                ["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True
            ).strip()
            require(candidate_sha == m["source"], "CANDIDATE_CHANGED")
            require(
                not subprocess.check_output(
                    ["git", "-C", str(self.root), "status", "--porcelain"], text=True
                ).strip(),
                "CANDIDATE_DIRTY",
            )
            gates = read(m["gates"])
            require(
                gates["source"] == candidate_sha
                and gates["passed"]
                and gates["draft"]
                and gates["state"] == "OPEN",
                "CANDIDATE_GATE",
            )
        for name in ("oldRuntime", "certificate", "key"):
            p = Path(m[name])
            require(
                p.is_file() and not p.is_symlink() and p.stat().st_uid == os.geteuid(),
                "HOST_FILE_OWNERSHIP",
            )
        from agent_console.authority_configuration import StaticAuthorityLoader

        original = StaticAuthorityLoader.load(
            Path(self.runtime["generationPath"]),
            expected_digest=self.runtime["generationDigest"],
        )
        for role in ("subject", "issuer"):
            identity = m[role + "Credential"]
            credential = original.credential_by_id(identity)
            require(
                credential is not None
                and credential.principal_id == m[role]
                and identity not in original.credential_revocation_tombstones,
                "ORIGINAL_CREDENTIAL_REVOKED_OR_MISMATCH",
            )
            require(
                not any(
                    cid == identity
                    for cid, _ in original.static_grant_revocation_tombstones
                ),
                "ORIGINAL_STATIC_PERMISSION_REVOKED",
            )
        require(self.facts() == m["protected"], "PROTECTED_HISTORY_CHANGED")
        with self.connection() as c:
            c.execute("SET TRANSACTION READ ONLY")
            row = c.execute(
                "SELECT d.*,x.revoked FROM authorization_admin.task_delegations d "
                "JOIN authorization_admin.task_delegation_control x "
                "USING(delegation_id) WHERE delegation_id=%s",
                (m["delegation"],),
            ).fetchone()
            require(
                row
                and not row["revoked"]
                and row["task_id"] == m["task"]
                and row["subject_id"] == m["subject"]
                and row["issuer_id"] == m["issuer"],
                "DELEGATION_BOUNDARY",
            )
            for table in ("task_delegation_revocations", "task_development_stops"):
                require(
                    not c.execute(
                        "SELECT 1 FROM authorization_admin."
                        + table
                        + " WHERE delegation_id=%s",
                        (m["delegation"],),
                    ).fetchone(),
                    "REVOKED_OR_STOPPED",
                )
            unknown = c.execute(
                "SELECT record FROM workflow_planning.invocation_results "
                "WHERE record->>'technical_status'='OUTCOME_UNKNOWN'"
            ).fetchall()
            require(len(unknown) == m["unknownCount"], "UNKNOWN_COUNT_CHANGED")
            receipts = c.execute(
                "SELECT p.record FROM workflow_planning.provider_receipts p JOIN "
                "workflow_planning.invocation_results r USING(invocation_id) "
                "WHERE r.record->>'technical_status'='OUTCOME_UNKNOWN'"
            ).fetchall()
            require(
                all(
                    x["record"]["deadline"]["reaped"]
                    and not alive(x["record"]["deadline"]["worker_pid"])
                    for x in receipts
                ),
                "OLD_WORKER_NOT_REAPED",
            )
        return {
            "candidate": m["source"],
            "protected": True,
            "providerDispatches": 0,
            "controlled": controlled,
        }

    def receipt(self, name, value):
        path = self.out / (name + ".json")
        if not path.exists():
            write(path, value)
        return read(path)

    def credentials(self):
        """Operator-only append; old credential files and hashes remain untouched."""
        path = self.out / "generation.next.json"
        if path.exists():
            require(
                (self.out / "credentials-complete.json").exists(),
                "PARTIAL_CREDENTIAL_CREATION_INSPECT",
            )
            return
        old = read(self.runtime["generationPath"])
        new = copy.deepcopy(old)
        new["generation"] += 1
        expiry = datetime.now(UTC) + timedelta(hours=8)
        for role in ("subject", "issuer"):
            previous = next(
                c
                for c in old["credentials"]
                if c["credentialId"] == self.m[role + "Credential"]
            )
            require(previous["principalId"] == self.m[role], "ORIGINAL_IDENTITY")
            secret = secrets.token_urlsafe(48)
            target = self.out / (role + ".credential")
            with target.open("x") as f:
                f.write(secret)
                f.flush()
                os.fsync(f.fileno())
            target.chmod(0o600)
            extra = copy.deepcopy(previous)
            extra.update(
                credentialId=previous["credentialId"] + ":continuity-v1",
                credentialSha256=hashlib.sha256(secret.encode()).hexdigest(),
                expiresAt=expiry.isoformat(),
            )
            new["credentials"].append(extra)
        write(path, new)
        runtime = {
            **self.runtime,
            "generationPath": str(path),
            "generationDigest": sha(path),
            "migrationPath": str(
                self.root
                / "console/backend/migrations/0018_browser_session_grant_authority.sql"
            ),
        }
        write(self.out / "runtime.next.json", runtime)
        self.receipt(
            "credentials-complete",
            {
                "expiresAt": expiry,
                "generation": new["generation"],
                "oldFilesUnchanged": True,
            },
        )

    def stop_and_migrate(self):
        before = self.out / "backup.dump"
        if not (self.out / "backup-complete.json").exists():
            require(not before.exists(), "INCOMPLETE_BACKUP_INSPECT")
            with before.open("xb") as f:
                subprocess.run(
                    [
                        "docker",
                        "exec",
                        self.m["container"],
                        "pg_dump",
                        "-U",
                        "postgres",
                        "-Fc",
                        urlsplit(self.db).path[1:],
                    ],
                    stdout=f,
                    check=True,
                )
            self.receipt("backup-complete", {"sha256": sha(before)})
        else:
            require(
                sha(before) == read(self.out / "backup-complete.json")["sha256"],
                "BACKUP_CHANGED",
            )
        if not (self.out / "old-stopped.json").exists():
            pid = self.m["oldPid"]
            if alive(pid):
                command = subprocess.check_output(
                    ["ps", "-p", str(pid), "-o", "command="], text=True
                ).strip()
                require(command == self.m["oldCommand"], "OLD_PID_REUSED")
                os.kill(pid, signal.SIGTERM)
                end = time.monotonic() + 15
                while alive(pid) and time.monotonic() < end:
                    time.sleep(0.1)
                require(not alive(pid), "OLD_WRITER_NOT_REAPED")
            self.receipt("old-stopped", {"pid": pid, "locallyReaped": True})
        from types import SimpleNamespace

        from agent_console.authority_postgres import PostgresAuthorityRepository
        from agent_console.task_delegation import TaskDelegationService

        repository = PostgresAuthorityRepository(
            self.db,
            migration_path=self.root
            / "console/backend/migrations/0018_browser_session_grant_authority.sql",
        )
        try:
            # migrate verifies existing checksums and only applies the absent extension.
            service = TaskDelegationService.__new__(TaskDelegationService)
            service.repository = repository
            service.grants = SimpleNamespace(repository=repository)
            service.migrate()
            repository.verify_existing_schema()
        finally:
            repository.close()
        self.receipt("migration-complete", {"version": 32})

    def activate_generation(self):
        from agent_console.authority_configuration import StaticAuthorityLoader
        from agent_console.authority_foundation import (
            ActivationBarrier,
            AuthorityGenerationController,
            AuthorityReadiness,
        )
        from agent_console.authority_postgres import PostgresAuthorityRepository
        from agent_console.authority_recovery import HostRecoveryControl

        runtime = read(self.out / "runtime.next.json")
        candidate = StaticAuthorityLoader.load(
            Path(runtime["generationPath"]), expected_digest=runtime["generationDigest"]
        )
        old = StaticAuthorityLoader.load(
            Path(self.runtime["generationPath"]),
            expected_digest=self.runtime["generationDigest"],
        )
        repository = PostgresAuthorityRepository(
            self.db, migration_path=Path(runtime["migrationPath"])
        )
        try:
            state = repository.active_generation()
            require(
                state[:2]
                in (
                    (old.generation, old.digest),
                    (candidate.generation, candidate.digest),
                ),
                "UNEXPECTED_ACTIVE_GENERATION",
            )
            control = HostRecoveryControl(Path(runtime["recoveryControlPath"]))
            current = candidate if state[0] == candidate.generation else old
            controller = AuthorityGenerationController(
                ActivationBarrier(current),
                repository,
                control,
                AuthorityReadiness(
                    current.generation,
                    current.digest,
                    state[2],
                    runtime["databaseFingerprint"],
                ),
            )
            controller.activate(
                candidate,
                control_epoch=control.read().control_epoch + 1,
                operator_id=runtime["operatorId"],
                now=datetime.now(UTC),
            )
            self.receipt(
                "generation-active",
                {"generation": candidate.generation, "transitionRecorded": True},
            )
        finally:
            repository.close()

    def client(self):
        return httpx.Client(
            base_url=self.url,
            trust_env=False,
            follow_redirects=False,
            verify=ssl.create_default_context(cafile=self.m["certificate"]),
            timeout=5,
        )

    def start(self):
        state = self.out / "service-started.json"
        if state.exists():
            pid = read(state)["pid"]
            require(alive(pid), "RECORDED_SERVICE_EXITED_INSPECT_BEFORE_RESTART")
            command = subprocess.check_output(
                ["ps", "-p", str(pid), "-o", "command="], text=True
            )
            require(
                str(self.path) in command and "--serve" in command,
                "RECORDED_SERVICE_PID_REUSED",
            )
        else:
            listeners = subprocess.run(
                ["lsof", "-t", "-iTCP:" + str(urlsplit(self.url).port), "-sTCP:LISTEN"],
                capture_output=True,
                text=True,
            )
            require(not listeners.stdout.strip(), "SERVICE_PORT_OCCUPIED")
            with (self.out / "service.log").open("xb") as log:
                proc = subprocess.Popen(
                    [sys.executable, __file__, str(self.path), "--serve"],
                    cwd=self.root,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            pid = proc.pid
            self.receipt("service-started", {"pid": pid, "source": self.m["source"]})
        deadline = time.monotonic() + 45
        last = "NOT_READY"
        with self.client() as client:
            while time.monotonic() < deadline:
                require(alive(pid), "SERVICE_EXITED_INSPECT_SERVICE_LOG")
                try:
                    response = client.get(
                        "/healthz",
                        timeout=min(2, max(0.001, deadline - time.monotonic())),
                    )
                    if checked(response) == {"status": "ok"}:
                        checked(client.get("/api/workbench/v1/session"), expected=401)
                        self.receipt(
                            "service-ready",
                            {"pid": pid, "authenticationRequired": True},
                        )
                        return
                except (httpx.HTTPError, RuntimeError) as e:
                    last = (
                        type(e).__name__ if isinstance(e, httpx.HTTPError) else str(e)
                    )
                time.sleep(0.2)
        raise RuntimeError("READINESS_DEADLINE " + last)

    def sign(self):
        """Only invoked after Human's typed operator/independent-issuer action."""
        prefix = (
            "/api/workbench/v1/authorization/task-delegations/" + self.m["delegation"]
        )
        with self.client() as client:
            page = client.get("/api/workbench/v1/login")
            require(
                page.status_code == 200
                and "text/html" in page.headers.get("content-type", ""),
                "LOGIN_ENTRY_INVALID",
            )
            nonce = re.search(r'name="loginNonce" value="([^"]+)"', page.text)
            require(nonce, "LOGIN_NONCE_MISSING")
            response = client.post(
                "/api/workbench/v1/session",
                data={
                    "loginNonce": nonce.group(1),
                    "bootstrapCredential": (self.out / "issuer.credential").read_text(),
                },
                headers={"origin": self.url},
            )
            require(response.status_code == 303, "INDEPENDENT_LOGIN_REJECTED")
            session = checked(client.get("/api/workbench/v1/session"))
            require(
                session["principal"]["principalId"] == self.m["issuer"],
                "ISSUER_MISMATCH",
            )
            client.headers.update(
                {"origin": self.url, "x-csrf-token": session["csrfToken"]}
            )
            configuration = checked(
                client.get(
                    "/api/workbench/v1/authorization/task-delegations/configuration"
                )
            )
            require(
                configuration["configurations"] == self.m["configurations"],
                "LOADED_LIMITS_CHANGED",
            )
            info = checked(client.get(prefix + "/identity-continuity/preflight"))
            payload_path = self.out / "signature-payload.json"
            if not payload_path.exists():
                require(info["predecessor"] is None, "UNEXPECTED_CONTINUITY_INSPECT")
                payload = {
                    "original_digest": info["original_digest"],
                    "transition_id": info["transition"]["transition_id"],
                    "transition_digest": info["transition"]["digest"],
                    "binding_digest": info["binding_digest"],
                    "predecessor_digest": None,
                    "expires_at": read(self.out / "credentials-complete.json")[
                        "expiresAt"
                    ],
                    "idempotency_key": "323-continuity-v1-activation",
                }
                for role in ("subject", "issuer"):
                    payload["old_" + role + "_credential_id"] = self.m[
                        role + "Credential"
                    ]
                    payload[role + "_credential_id"] = (
                        self.m[role + "Credential"] + ":continuity-v1"
                    )
                write(payload_path, payload)
            payload = read(payload_path)
            prior = info["predecessor"]
            if prior is None:
                # Never resend after an uncertain response: persistent preflight first.
                checked(client.post(prefix + "/identity-continuity", json=payload))
                prior = checked(client.get(prefix + "/identity-continuity/preflight"))[
                    "predecessor"
                ]
            from agent_console.task_delegation import digest
            from agent_console.task_identity_continuity import ContinuityApproval

            canonical = ContinuityApproval.model_validate(payload).model_dump(
                mode="json"
            )
            require(
                prior and prior["payload_digest"] == digest(canonical),
                "SIGNATURE_READBACK_MISMATCH",
            )
            self.receipt(
                "signature-confirmed",
                {
                    "continuityId": prior["continuity_id"],
                    "digest": prior["digest"],
                    "issuer": prior["issuer_id"],
                },
            )
            checked(client.get(prefix))
            from agent_console.task_delegation import active

            with self.connection() as c:
                effective, _ = active(c, self.m["delegation"])
                require(
                    effective["_continuity"]["continuity_id"] == prior["continuity_id"],
                    "CONTINUITY_NOT_EFFECTIVE",
                )

    def serve(self):
        for key in (
            "AGENT_DEFINITION_DATABASE_URL",
            "EXECUTION_DATABASE_URL",
            "WORKFLOW_RUNTIME_DATABASE_URL",
            "KNOWLEDGE_DATABASE_URL",
            "SKILL_MCP_DATABASE_URL",
        ):
            os.environ[key] = self.db
        os.environ.update(
            WORKBENCH_AUTHORITY_RUNTIME_FILE=str(self.out / "runtime.next.json"),
            WORKBENCH_ALLOWED_HOST=urlsplit(self.url).netloc,
            WORKBENCH_ALLOWED_ORIGIN=self.url,
            DRAFT_ASSISTANCE_RUNTIME_FILE=self.m["understanding"],
            PLANNING_RUNTIME_FILE=self.m["planning"],
            PLANNING_V2_ENABLED="true",
        )
        import uvicorn
        from agent_console.app import get_workbench_app
        from fastapi.responses import FileResponse
        from fastapi.staticfiles import StaticFiles

        app = get_workbench_app()
        dist = Path(self.m["dist"])
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}")
        def frontend(path: str):
            return FileResponse(dist / "index.html")

        self.receipt(
            "running-source",
            {
                "source": self.m["source"],
                "pid": os.getpid(),
                "planningPolicy": "planning-suggestion.zh-CN.v1",
                "understandingPolicyUnchanged": True,
            },
        )
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=urlsplit(self.url).port,
            ssl_certfile=self.m["certificate"],
            ssl_keyfile=self.m["key"],
            access_log=False,
        )

    def run(self, *, check_only=False):
        state = self.check()
        if check_only:
            print(json.dumps(state, ensure_ascii=False))
            return
        require(
            sys.stdin.isatty() or self.m.get("controlled", False),
            "HUMAN_TERMINAL_REQUIRED",
        )
        print("323原主体身份恢复与独立连续性签发; 不调用模型、不执行业务。")
        require(
            input("输入 ACTIVATE_323_CONTINUITY_V1: ").strip()
            == "ACTIVATE_323_CONTINUITY_V1",
            "HUMAN_ACTION_NOT_ENTERED",
        )
        with (self.out / "activation.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.check()
            self.credentials()
            self.stop_and_migrate()
            self.activate_generation()
            self.start()
            self.sign()
            require(self.facts() == self.m["protected"], "PROTECTED_HISTORY_CHANGED")
            self.receipt("activation-complete", {**state, "at": datetime.now(UTC)})
            print("IDENTITY_CONTINUITY_323_ACTIVE")


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    activation = Activation(args.manifest)
    try:
        if args.serve:
            activation.serve()
        else:
            activation.run(check_only=args.check)
    except Exception as e:
        # No traceback/request body/credential in shared receipts.
        code = str(e) if isinstance(e, RuntimeError) else type(e).__name__
        print("ACTIVATION_STOPPED " + code)
        if not args.check and not args.serve:
            write(
                activation.out
                / (
                    "failure-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f") + ".json"
                ),
                {"stage": code, "providerDispatches": 0},
            )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
