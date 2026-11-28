"""Real known ZIP code + isolated PostgreSQL Tool claims; no Skill or provider."""

import base64
import hashlib
import io
import json
import os
import threading
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace as NS

import psycopg
import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.execution_domain import ScopeIdentity, record_digest
from agent_console.tool_definition_postgres import PostgresToolDefinitionRepository
from agent_console.tool_lifecycle import ToolCommand, command
from agent_console.tool_source_journal import SourceJournal, check_schema, migrate
from agent_console.tool_source_policy import PrivateSourcePolicy, SourceBinding
from agent_console.tool_source_testing import ToolSourceTesting
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

CODE = (
    b'def main(inputs):\n    return {"total": sum(inputs["values"]), '
    b'"count": len(inputs["values"])}\n'
)
OTHER_CODE = CODE.replace(b'sum(inputs["values"])', b'2 * sum(inputs["values"])')
DENIED_PORTS = {19436, 19761, 29437, 53428, 64335, 64330}


def package(code=CODE, runtime="reviewed-python-function.v1"):
    manifest = {
        "format": "t-manufacturing-tool-plugin/v1",
        "id": "synthetic.sum",
        "version": "1",
        "runtime": runtime,
        "entrypoint": "sum.py",
        "permissions": [],
        "tools": [
            {
                "name": "sum",
                "description": "synthetic only",
                "sideEffect": "read-only",
                "inputSchema": {
                    "type": "object",
                    "required": ["values"],
                    "properties": {
                        "values": {"type": "array", "items": {"type": "number"}}
                    },
                },
                "outputSchema": {
                    "type": "object",
                    "required": ["total", "count"],
                    "properties": {
                        "total": {"type": "number"},
                        "count": {"type": "number"},
                    },
                },
            }
        ],
    }
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for name, content in (
            ("manifest.json", json.dumps(manifest).encode()),
            ("sum.py", code),
        ):
            entry = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            z.writestr(entry, content)
    return out.getvalue()


def source_test_database_url():
    url = os.environ.get("TOOL_SOURCE_TEST_DATABASE_URL") or os.environ.get(
        "AUTHORITY_I1_TEST_DATABASE_URL"
    )
    if not url:
        return None
    info = psycopg.conninfo.conninfo_to_dict(url)
    if (
        info.get("host") != "127.0.0.1"
        or info.get("port") not in {"53439", "53428", "64335"}
        or info.get("hostaddr", "127.0.0.1") != "127.0.0.1"
        or info.get("service")
    ):
        raise ValueError("TOOL_SOURCE_TEST_DATABASE_NOT_ISOLATED")
    return url


@pytest.fixture
def owner():
    url = source_test_database_url()
    if not url:
        pytest.skip("dedicated Tool source PostgreSQL required")
    db = "tool_source_" + uuid.uuid4().hex
    with psycopg.connect(url, autocommit=True) as c:
        c.execute(
            psycopg.sql.SQL("CREATE DATABASE {}").format(psycopg.sql.Identifier(db))
        )
    pool = ConnectionPool(
        psycopg.conninfo.make_conninfo(url, dbname=db),
        kwargs={"row_factory": dict_row},
        open=True,
        min_size=1,
        max_size=8,
    )
    repo = PostgresToolDefinitionRepository(pool)
    repo.migrate(Path(__file__).parents[1] / "migrations/0061_tool_definitions.sql")
    with pool.connection() as c, c.transaction():
        migrate(c)
    yield repo
    pool.close()
    with psycopg.connect(url, autocommit=True) as c:
        c.execute(
            psycopg.sql.SQL("DROP DATABASE {}").format(psycopg.sql.Identifier(db))
        )


class Authority:
    def __init__(self):
        self.denied = set()
        self.calls = []

    def require(self, principal, owner, action, target):
        self.calls.append((owner, action, target))
        assert owner == "TOOL", "foreign owner authority forbidden"
        if action in self.denied:
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")
        return NS(decision_id="decision:synthetic")


@pytest.fixture
def rig(owner, tmp_path):
    scope = ScopeIdentity("synthetic-tools", "readonly")
    context = NS(
        scope=NS(tenant_id=scope.namespace, security_domain=scope.security_domain),
        principal_id="human:synthetic",
    )
    authority = Authority()
    approved = {hashlib.sha256(package()).hexdigest(): CODE}
    calls = []
    mode = ["normal"]
    journal = SourceJournal(owner.pool)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            assert self.path == "/v1/read-only/invoke"
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert body["operation"] == "tool-source-test.v1"
            r = body["input"]
            raw = base64.b64decode(r["sourceBase64"], validate=True)
            source_sha = hashlib.sha256(raw).hexdigest()
            assert source_sha == r["sourceDigest"] and source_sha in approved
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                code = z.read(r["entrypoint"])
            assert (
                code == approved[source_sha]
                and hashlib.sha256(code).hexdigest() == r["entrypointDigest"]
            )
            assert (
                r["runtime"] == "reviewed-python-function.v1"
                and r["runtimeRevision"] == "registered-1"
            )
            # Independently observe durable pre-effect claim on another connection.
            with owner.pool.connection() as c:
                assert c.execute(
                    "SELECT count(*) n FROM tool_definition.source_test_facts "
                    "WHERE kind='DISPATCH_CLAIM'"
                ).fetchone()["n"] > len(calls)
            # TEST ONLY: execute only these reviewed exact bytes, with no imports,
            # files, sockets, environment, package installation or dynamic source.
            namespace = {"__builtins__": {"sum": sum, "len": len}}
            exec(compile(code, r["entrypoint"], "exec"), namespace)
            actual = namespace["main"](r["arguments"])
            calls.append(
                {
                    "request": r,
                    "actual": actual,
                    "entrypointBytesDigest": hashlib.sha256(code).hexdigest(),
                }
            )
            if mode[0] == "lost":
                self.close_connection = True
                return
            proof = {
                k: r[k]
                for k in (
                    "toolId",
                    "revisionId",
                    "revisionDigest",
                    "sourceDigest",
                    "entrypoint",
                    "entrypointDigest",
                    "runtime",
                    "runtimeRevision",
                    "operation",
                    "inputDigest",
                )
            }
            if mode[0] == "bad-proof":
                proof["sourceDigest"] = "0" * 64
            envelope = {
                "actual": actual,
                "execution": proof,
                "actualDigest": record_digest(actual),
                "sourceExecuted": True,
            }
            response = {
                "schemaVersion": "read-only-skill-response.v1",
                "invocationId": body["invocationId"],
                "accepted": True,
                "observationId": "local-source:" + str(len(calls)),
                "output": envelope,
            }
            encoded = json.dumps(response).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    assert server.server_port not in DENIED_PORTS
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    path = tmp_path / "source-policy.json"

    def install(raw=None, expected=None):
        raw = raw or package()
        with owner.pool.connection() as c, c.transaction():
            imported = owner.import_drafts(
                c,
                scope,
                "PLUGIN_ZIP",
                raw,
                ["sum"],
                expected or {},
                effects={"sum": "read-only"},
                command_id="import:" + uuid.uuid4().hex,
                actor_id=context.principal_id,
                decision_id="decision:synthetic",
            )
            current = owner.read(c, scope, imported["items"][0]["toolId"])
        return current

    current = install()

    def policy(cur=current, code=CODE, **changes):
        binding = dict(
            namespace=scope.namespace,
            securityDomain=scope.security_domain,
            subject=context.principal_id,
            toolId=cur["toolId"],
            revisionId=cur["revisionId"],
            digest=cur["digest"],
            sourceDigest=cur["sourceDigest"],
            entrypoint="sum.py",
            entrypointDigest=hashlib.sha256(code).hexdigest(),
            runtime="reviewed-python-function.v1",
            runtimeRevision="registered-1",
            endpoint=f"http://127.0.0.1:{server.server_port}",
            expiresAt=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            maximumCalls=20,
            timeoutMs=2000,
            maximumInputBytes=65536,
            maximumOutputBytes=65536,
            syntheticReadOnly=True,
        )
        binding.update(changes)
        path.write_text(
            json.dumps(
                {
                    "schemaVersion": "tool-source-test-policy.v1",
                    "enabled": True,
                    "bindings": [binding],
                }
            )
        )
        path.chmod(0o600)
        return ToolSourceTesting(path, owner)

    testing = policy()

    def run(
        key="test:one",
        values=None,
        expected=None,
        test=testing,
        cur=None,
        **cmd_changes,
    ):
        cur = cur or current
        cmd = dict(
            action="test",
            commandId=key,
            expectedVersion=cur["aggregateVersion"],
            revisionId=cur["revisionId"],
            digest=cur["digest"],
            testName="known sum source",
            input={"values": values or [2, 3]},
            expectedOutput=expected or {"total": 5, "count": 2},
        )
        cmd.update(cmd_changes)
        with owner.pool.connection() as c, c.transaction():
            call = NS(context=context, connection=c, authority=authority)
            return command(
                owner,
                c,
                scope,
                cur["toolId"],
                ToolCommand(**cmd),
                actor_id=context.principal_id,
                decision_id="decision:synthetic",
                run_test=lambda row, command: test.run(call, row, command),
            )

    yield NS(**locals())
    server.shutdown()
    server.server_close()
    thread.join()


def result(response):
    return response["testResult"]


def test_real_zip_entrypoint_independent_actual_and_input_changes(rig):
    a = result(rig.run())
    b = result(rig.run("test:two", [4, 8], {"total": 999, "count": 2}))
    assert a["status"] == "PASSED" and a["actual"] == {"total": 5, "count": 2}
    assert b["status"] == "FAILED" and b["actual"] == {"total": 12, "count": 2}
    assert all(r["actualExecution"] and r["toolSourceInvoked"] for r in (a, b))
    assert a["sourceExecution"]["entrypointDigest"] == hashlib.sha256(CODE).hexdigest()
    assert len(rig.calls) == 2 and all(
        owner == "TOOL" for owner, *_ in rig.authority.calls
    )
    evidence = os.environ.get("TOOL_SOURCE_EVIDENCE")
    if evidence:
        Path(evidence).write_text(
            json.dumps(
                {
                    "verificationLevel": a["verificationLevel"],
                    "actualSourceCalls": rig.calls,
                    "results": [a, b],
                    "paidCalls": 0,
                },
                indent=2,
            )
        )


def test_same_key_replay_and_new_owner_recovery_no_extra_call(rig):
    first = rig.run()
    assert rig.run()["replayed"] and len(rig.calls) == 1
    restarted = ToolSourceTesting(rig.path, rig.owner)
    assert result(rig.run(test=restarted)) == result(first)
    with rig.owner.pool.connection() as c:
        call = NS(context=rig.context, connection=c, authority=rig.authority)
        assert restarted.receipt(call, "test:one")["items"][0]["testResult"] == result(
            first
        )


@pytest.mark.parametrize("mode", ["lost", "bad-proof"])
def test_unknown_retained_and_original_key_never_redispatches(rig, mode):
    rig.mode[0] = mode
    a = result(rig.run())
    assert a["status"] == "UNKNOWN" and a["actual"] is None
    assert result(rig.run()) == a and len(rig.calls) == 1
    restarted = ToolSourceTesting(rig.path, rig.owner)
    with rig.owner.pool.connection() as c:
        saved = restarted.receipt(
            NS(context=rig.context, connection=c, authority=rig.authority), "test:one"
        )
    assert saved["items"][0]["testResult"]["status"] == "UNKNOWN"


def test_pending_claim_restart_is_unknown_not_replayed(rig):
    # Simulate a process lost after durable claim but before any terminal write.
    rig.journal.claim(
        rig.context,
        "orphan",
        "binding",
        {
            "toolId": rig.current["toolId"],
            "revisionId": rig.current["revisionId"],
            "digest": rig.current["digest"],
            "sourceDigest": rig.current["sourceDigest"],
        },
        20,
    )
    with rig.owner.pool.connection() as c:
        receipt = rig.testing.receipt(
            NS(context=rig.context, connection=c, authority=rig.authority), "orphan"
        )
    assert receipt["items"][0]["testResult"]["status"] == "UNKNOWN" and not rig.calls


@pytest.mark.parametrize("action", ["READ", "TEST"])
def test_tool_own_current_authority_denial_never_calls(rig, action):
    rig.authority.denied.add(action)
    if action == "READ":
        # BFF would also deny; testing adapter itself must independently deny.
        pass
    a = result(rig.run())
    assert a["status"] == "NOT_EXECUTED" and not rig.calls


def test_exact_source_change_requires_new_allowlist_and_runs_new_code(rig):
    newraw = package(OTHER_CODE)
    new = rig.install(newraw, {"sum": 1})
    denied = result(rig.run(cur=new))
    assert denied["status"] == "NOT_EXECUTED" and not rig.calls
    rig.approved[hashlib.sha256(newraw).hexdigest()] = OTHER_CODE
    newtest = rig.policy(new, OTHER_CODE)
    accepted = result(
        rig.run(
            "test:new-source", cur=new, test=newtest, expected={"total": 10, "count": 2}
        )
    )
    assert accepted["status"] == "PASSED" and accepted["actual"]["total"] == 10
    assert accepted["sourceExecution"]["sourceDigest"] != rig.current["sourceDigest"]


@pytest.mark.parametrize(
    "change", ["digest", "sourceDigest", "entrypointDigest", "runtimeRevision"]
)
def test_mismatched_exact_source_or_runtime_is_never_claimed_as_success(rig, change):
    value = "wrong-runtime" if change == "runtimeRevision" else "0" * 64
    test = rig.policy(**{change: value})
    a = result(rig.run(test=test))
    assert a["status"] in {"NOT_EXECUTED", "UNKNOWN"} and a["actual"] is None
    if change != "runtimeRevision":
        assert not rig.calls


def test_private_policy_changed_and_expired_denied(rig):
    rig.path.write_text(rig.path.read_text() + " ")
    assert result(rig.run())["status"] == "NOT_EXECUTED"
    expired = rig.policy(
        expiresAt=(datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    )
    assert (
        result(rig.run("expired", test=expired))["status"] == "NOT_EXECUTED"
        and not rig.calls
    )


def test_call_cap_shared_across_keys_concurrent_claims(rig):
    test = rig.policy(maximumCalls=1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(
            pool.map(lambda k: result(rig.run(k, test=test)), ["cap:1", "cap:2"])
        )
    assert sorted(r["status"] for r in rows) == ["NOT_EXECUTED", "PASSED"]
    assert len(rig.calls) == 1


def test_schema_marker_missing_fails_closed(owner):
    with owner.pool.connection() as c, c.transaction():
        c.execute("DELETE FROM tool_definition.schema_migrations WHERE version=81")
        with pytest.raises(ValueError, match="SCHEMA_INCOMPATIBLE"):
            check_schema(c)


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://127.0.0.1:1@evil.example",
        "http://localhost:1",
        "http://127.0.0.1:1/path",
        "http://127.0.0.1:1?x=1",
        "https://127.0.0.1:1",
    ],
)
def test_endpoint_not_free_external_or_path(rig, endpoint):
    binding = rig.testing.policy.policy.bindings[0].model_dump()
    with pytest.raises(ValueError):
        SourceBinding(**(binding | {"endpoint": endpoint}))


def test_policy_world_readable_refused(rig):
    rig.path.chmod(0o644)
    with pytest.raises(ValueError, match="PRIVATE_POLICY"):
        PrivateSourcePolicy(rig.path)


def test_actual_effect_then_terminal_write_lost_original_key_recovers_unknown(
    rig, monkeypatch
):
    def lost(*_args):
        raise RuntimeError("synthetic terminal transaction lost")

    monkeypatch.setattr(rig.testing.journal, "finish", lost)
    with pytest.raises(RuntimeError, match="terminal transaction"):
        rig.run()
    assert len(rig.calls) == 1
    restarted = ToolSourceTesting(rig.path, rig.owner)
    # The normal lifecycle transaction rolled back; independent claim survived.
    recovered = result(rig.run(test=restarted))
    assert recovered["status"] == "UNKNOWN" and len(rig.calls) == 1


def test_conflicting_same_key_never_dispatches_again(rig):
    rig.run()
    from agent_console.tool_definition_postgres import ToolStorageError

    with pytest.raises(ToolStorageError, match="COMMAND_CONFLICT"):
        rig.run(values=[6, 9])
    assert len(rig.calls) == 1


def test_concurrent_same_claim_and_distinct_payload_are_fail_closed(rig):
    def claim(_):
        return rig.journal.claim(
            rig.context, "claim:concurrent", "same-binding", {"synthetic": True}, 1
        )[0]

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(claim, range(2))) == [False, True]
    with pytest.raises(ValueError, match="COMMAND_CONFLICT"):
        rig.journal.claim(
            rig.context, "claim:concurrent", "other-binding", {"synthetic": False}, 20
        )
    assert not rig.calls


def test_append_only_claim_and_result_cannot_be_mutated(rig):
    rig.run()
    for table in ("source_test_requests", "source_test_facts"):
        with (
            rig.owner.pool.connection() as c,
            c.transaction(),
            pytest.raises(psycopg.errors.RaiseException, match="APPEND_ONLY"),
        ):
            c.execute(
                psycopg.sql.SQL("DELETE FROM tool_definition.{}").format(
                    psycopg.sql.Identifier(table)
                )
            )


@pytest.mark.parametrize("damage", ["checksum", "adapter", "trigger"])
def test_wrong_schema_marker_and_missing_trigger_reject(rig, damage):
    with rig.owner.pool.connection() as c, c.transaction():
        if damage == "trigger":
            c.execute(
                "DROP TRIGGER source_test_facts_immutable "
                "ON tool_definition.source_test_facts"
            )
        else:
            c.execute(
                psycopg.sql.SQL(
                    "UPDATE tool_definition.schema_migrations SET {}='bad' "
                    "WHERE version=81"
                ).format(psycopg.sql.Identifier(damage))
            )
        with pytest.raises(ValueError, match="SCHEMA_INCOMPATIBLE"):
            check_schema(c)
    # Restore marker through outer rollback is intentionally not automatic here:
    # this fixture DB is disposable and never shared with any other case.


def test_source_input_limit_denied_before_claim(rig):
    test = rig.policy(maximumInputBytes=5)
    assert result(rig.run(test=test))["status"] == "NOT_EXECUTED" and not rig.calls


def test_unknown_runtime_policy_is_rejected(rig):
    binding = rig.testing.policy.policy.bindings[0].model_dump()
    with pytest.raises(ValueError):
        SourceBinding(**(binding | {"runtime": "arbitrary-host-python"}))


def test_bounded_response_stream_never_accepts_large_or_late_bytes():
    import httpx
    from agent_console.tool_source_runtime import BoundedStream

    with pytest.raises(ValueError, match="RESPONSE_LIMIT"):
        list(BoundedStream(httpx.ByteStream(b"too large"), 3, float("inf")))
    with pytest.raises(ValueError, match="RESPONSE_LIMIT"):
        list(BoundedStream(httpx.ByteStream(b"ok"), 100, 0))


def test_original_import_receipt_route_recovers_committed_orphan(rig):
    from agent_console.workbench_tool_definitions import tool_definition_operations

    saved = {
        "toolId": rig.current["toolId"],
        "revisionId": rig.current["revisionId"],
        "digest": rig.current["digest"],
        "sourceDigest": rig.current["sourceDigest"],
    }
    rig.journal.claim(rig.context, "route:orphan", "binding", saved, 20)
    operations = tool_definition_operations(rig.owner, None, source_testing=rig.testing)
    route = next(o for o in operations if o.name == "READ_TOOL_IMPORT_RECEIPT")
    with rig.owner.pool.connection() as c, c.transaction():
        call = NS(
            operation="READ_TOOL_IMPORT_RECEIPT",
            context=rig.context,
            connection=c,
            authority=rig.authority,
            path={"command_id": "route:orphan"},
        )
        response = route.handler(call)
    assert response["testResult"]["status"] == "UNKNOWN" and not rig.calls


def test_cross_subject_claim_key_cannot_be_borrowed(rig):
    rig.journal.claim(rig.context, "global:key", "binding", {"synthetic": True}, 20)
    other = NS(scope=rig.context.scope, principal_id="human:other")
    with pytest.raises(psycopg.errors.UniqueViolation):
        rig.journal.claim(other, "global:key", "other-binding", {"synthetic": True}, 20)
    assert rig.journal.read(other, "global:key") is None and not rig.calls


def test_exact_zip_manifest_unknown_runtime_never_dispatches(rig):
    unknown = rig.install(package(runtime="unknown-runtime"), {"sum": 1})
    test = rig.policy(unknown)
    assert result(rig.run(cur=unknown, test=test))["status"] == "NOT_EXECUTED"
    assert not rig.calls


def test_registered_local_execution_ignores_environment_proxy(rig, monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("NO_PROXY", "")
    assert result(rig.run())["status"] == "PASSED" and len(rig.calls) == 1


def test_migration_autocommit_rejected_before_any_ddl(owner):
    with owner.pool.connection() as c:
        c.autocommit = True
        with pytest.raises(ValueError, match="MIGRATION_TRANSACTION_REQUIRED"):
            migrate(c)
        c.autocommit = False


def test_source_output_size_failure_retains_hash_not_oversize_payload(rig):
    test = rig.policy(maximumOutputBytes=1)
    observed = result(rig.run(test=test))
    assert observed["status"] == "FAILED" and observed["actual"] is None
    assert observed["actualExecution"] and observed["sourceExecution"]["actualDigest"]
    assert len(rig.calls) == 1


def test_source_result_committed_outer_tool_receipt_lost_get_keeps_exact_old_actual(
    rig,
):
    from agent_console.workbench_tool_definitions import tool_definition_operations

    cmd = ToolCommand(
        action="test",
        commandId="result:outer-lost",
        expectedVersion=rig.current["aggregateVersion"],
        revisionId=rig.current["revisionId"],
        digest=rig.current["digest"],
        testName="outer receipt failure",
        input={"values": [2, 3]},
        expectedOutput={"total": 5, "count": 2},
    )
    with (
        pytest.raises(RuntimeError, match="outer receipt lost"),
        rig.owner.pool.connection() as c,
        c.transaction(),
    ):
        call = NS(context=rig.context, connection=c, authority=rig.authority)

        def executed(current, command):
            observed = rig.testing.run(call, current, command)
            assert observed["status"] == "PASSED"
            raise RuntimeError("synthetic outer receipt lost")

        command(
            rig.owner,
            c,
            rig.scope,
            rig.current["toolId"],
            cmd,
            actor_id=rig.context.principal_id,
            decision_id="decision:synthetic",
            run_test=executed,
        )
    assert len(rig.calls) == 1
    newer = rig.install(package(OTHER_CODE), {"sum": 1})
    rig.authority.denied.add("TEST")
    restarted = ToolSourceTesting(rig.path, rig.owner)
    route = next(
        o
        for o in tool_definition_operations(rig.owner, None, source_testing=restarted)
        if o.name == "READ_TOOL_IMPORT_RECEIPT"
    )
    with rig.owner.pool.connection() as c, c.transaction():
        before = c.execute(
            "SELECT count(*) n FROM tool_definition.receipts"
        ).fetchone()["n"]
        response = route.handler(
            NS(
                operation="READ_TOOL_IMPORT_RECEIPT",
                context=rig.context,
                connection=c,
                authority=rig.authority,
                path={"command_id": cmd.commandId},
            )
        )
        after = c.execute("SELECT count(*) n FROM tool_definition.receipts").fetchone()[
            "n"
        ]
        latest = rig.owner.read(c, rig.scope, newer["toolId"])
    assert before == after
    assert response["items"][0]["aggregateVersion"] == cmd.expectedVersion
    assert response["testCase"]["input"] == {"values": [2, 3]}
    assert response["testResult"]["status"] == "PASSED"
    assert response["testResult"]["actual"] == {"total": 5, "count": 2}
    assert response["items"][0]["revisionId"] == rig.current["revisionId"]
    assert latest["revisionId"] == newer["revisionId"] != rig.current["revisionId"]
    assert len(rig.calls) == 1


def test_source_test_fixture_rejects_production_url_without_connecting(monkeypatch):
    production = "postgresql://synthetic@127.0.0.1:64330/not-a-test"
    isolated = "postgresql://synthetic@127.0.0.1:53439/postgres"
    monkeypatch.setenv("TOOL_SOURCE_TEST_DATABASE_URL", production)
    monkeypatch.setenv("AUTHORITY_I1_TEST_DATABASE_URL", isolated)
    with pytest.raises(ValueError, match="DATABASE_NOT_ISOLATED"):
        source_test_database_url()
    monkeypatch.delenv("TOOL_SOURCE_TEST_DATABASE_URL")
    monkeypatch.setenv("AUTHORITY_I1_TEST_DATABASE_URL", production)
    with pytest.raises(ValueError, match="DATABASE_NOT_ISOLATED"):
        source_test_database_url()
