"""Real existing owned owner -> bounded discovery, never launch/invoke a host."""

# ruff: noqa: F401,F811 -- Reuse the same real isolated consumer owner fixture.
from types import SimpleNamespace

from agent_operator.native_host_service_discovery import Discovery
from test_owned_business_consumer_chain import (
    adopted,
    cleanup_consumer_resources,
    env,
    ordinary,
    owned_created,
    owned_ready,
    pytestmark,
    routed,
    setup,
)
from test_owned_business_consumer_chain import (
    test_same_owned_problem_confirms_prepares_and_worker_reads as exercise,
)


def test_actual_owned_receipt_discovery_and_scope_are_read_only(
    owned_created, tmp_path, request, monkeypatch
):
    e = owned_created

    def observe(work, repository, receipt, ready):
        assembly = SimpleNamespace(
            worker=SimpleNamespace(repository=SimpleNamespace(work=work)),
            execution_repository=repository,
        )
        scope = (
            e.context.scope.tenant_id,
            e.context.scope.security_domain,
            e.context.principal_id,
        )
        discovery = Discovery(assembly, scope, "isolated")
        with e.repo.connection_scope() as c:
            before = c.execute(
                "SELECT count(*) n FROM execution_authority.native_dispatch_facts"
            ).fetchone()["n"]
        first = discovery.page()
        assert len(first) == 1
        item = first[0]
        assert (
            item["resource"]
            == "governed-execution:prepared:" + receipt["preparationDigest"]
        )
        assert discovery.current(item) == item
        assert item["existingWorkers"] == []
        assert Discovery(assembly, (*scope[:2], "other"), "isolated").page() == []
        assert Discovery(assembly, ("other", *scope[1:]), "isolated").page() == []
        # The exact-host narrowing also scopes ready-driver and terminal-review reads.
        work.exact_host_scope = (*scope, ("governed-execution:prepared:other",))
        assert work.dispatches() == ()
        work.exact_host_scope = (*scope, (item["resource"],))
        assert work.dispatches() == ((scope[0], scope[1], item["resource"]),)
        work.exact_host_scope = None
        with e.repo.connection_scope() as c:
            assert (
                c.execute(
                    "SELECT count(*) n FROM execution_authority.native_dispatch_facts"
                ).fetchone()["n"]
                == before
            )
        # Existing exercise then records actual admission revocation and checks
        # dispatch eligibility becomes empty; this observer never writes authority.
        # Actual owner SQL source binding, independently of caller identity.
        # Permission enforcement remains native_interaction.records (tested before
        # this optional helper); this check is not an admin-login acceptance claim.
        import json
        import time

        from agent_console.native_host_process_projection import process_projection
        from agent_operator.native_host_startup import digest

        directory = tmp_path / "host-view"
        directory.mkdir(mode=0o700)
        monkeypatch.setenv("NATIVE_EXACT_HOST_SERVICE_STATUS_DIRECTORY", str(directory))
        identity = [*scope, receipt["preparationDigest"]]
        view = directory / ("view-" + digest(identity) + ".json")
        view.write_text(
            json.dumps(
                {
                    "schema": "native-exact-host-view.v1",
                    "identity": identity,
                    "runId": receipt["runId"],
                    "observedAt": time.time(),
                    "validForSeconds": 30,
                    "state": "READY",
                    "reasonCode": None,
                }
            )
        )
        view.chmod(0o600)
        prepared = SimpleNamespace(
            namespace=scope[0],
            security_domain=scope[1],
            digest=receipt["preparationDigest"],
            run_id=receipt["runId"],
        )
        with e.repo.connection_scope() as c:
            reader = SimpleNamespace(
                connection=c,
                context=SimpleNamespace(principal_id="different-authorized-reader"),
            )
            assert process_projection(reader, prepared)["state"] == "READY"
            prepared.run_id = "wrong-run"
            assert process_projection(reader, prepared)["state"] == "UNKNOWN"
            prepared.run_id = receipt["runId"]
            prepared.security_domain = "wrong-domain"
            assert process_projection(reader, prepared)["state"] == "UNKNOWN"
        e.host_discovery = discovery
        e.host_candidate = item

    e.consumer_execution_observer = observe

    def revoked():
        assert e.host_discovery.current(e.host_candidate) is None

    e.consumer_after_revoke = revoked
    exercise(e, tmp_path, request)
