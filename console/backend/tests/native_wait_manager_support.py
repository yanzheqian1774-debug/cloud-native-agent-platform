"""Actual HostService and exec isolation; controlled model/Kubernetes ports."""

import json
import os
import subprocess
import sys
import tomllib
import traceback
from pathlib import Path
from types import SimpleNamespace as NS

from agent_operator.native_host_service import HostService
from agent_operator.native_host_service_state import private_directory, read, write
from native_wait_exec_configuration import encode, isolated_dsn


def managed(e, work, native, discovery, directory):
    directory = private_directory(directory)
    e.wait_runtime_expiry = discovery.wait_access.runtime.expiry
    config = NS(
        directory=directory,
        environment=dict(os.environ),
        value=dict(
            maxHosts=1,
            maxRestarts=8,
            pollSeconds=1,
            readinessSeconds=20,
            shutdownSeconds=5,
            manifestPath="/controlled/manifest",
            manifestDigest="a" * 64,
            policyFiles={},
        ),
        verify=lambda: None,
    )
    spawned = []
    events = directory / "maintain-observations.jsonl"
    original_maintain = discovery.maintain
    original_receipt = work._owned_receipt

    def observe_receipt(row, now):
        previous_trace = sys.gettrace()

        def trace_guard(frame, event, arg):
            if event == "exception" and frame.f_code.co_name in {
                "_owned_receipt",
                "authorize_dispatch",
                "derive_work",
                "work",
                "require",
            }:
                kind, error, _ = arg
                with events.open("a") as stream:
                    stream.write(
                        json.dumps(
                            {
                                "guard": frame.f_code.co_name,
                                "exception": kind.__name__,
                                "reason": getattr(error, "reason_code", str(error)),
                            }
                        )
                        + "\n"
                    )
            if (
                event == "return"
                and arg is False
                and frame.f_code.co_name == "authorize_dispatch"
            ):
                local = frame.f_locals
                diagnostic = {
                    "guard": "authorize_dispatch",
                    "returned": False,
                    "hasBoundAttempt": local.get("bound") is not None,
                    "receiptCount": len(local.get("rows", [])),
                    "hasDerivedWork": local.get("work") is not None,
                }
                if local.get("work") is not None:
                    from agent_console.owned_business_resource_adapter import evidence

                    current, receipt = local["work"], local["receipt"]
                    diagnostic.update(
                        evidenceMatches=evidence(current) == receipt["ownedBusiness"],
                        runMatches=receipt["runId"]
                        == str(local["bound"]["workflow_run_id"]),
                        caseMatches=current.businessScope.case == receipt["case"],
                        agentMatches=current.businessScope.nativeAgentName
                        == receipt["nativeAgentName"]
                        == local["command"].agent_name,
                    )
                with events.open("a") as stream:
                    stream.write(json.dumps(diagnostic) + "\n")
            return trace_guard

        try:
            sys.settrace(trace_guard)
            value = original_receipt(row, now)
        finally:
            sys.settrace(previous_trace)
        if not value:
            with events.open("a") as stream:
                stream.write(
                    json.dumps(
                        {
                            "receiptEligible": False,
                            "preparationDigest": row["result"]["preparationDigest"],
                        }
                    )
                    + "\n"
                )
        return value

    work._owned_receipt = observe_receipt

    def observe_maintain(candidate, process_record):
        try:
            value = original_maintain(candidate, process_record)
        except Exception:
            with events.open("a") as stream:
                stream.write(
                    json.dumps(
                        {
                            "preparationDigest": candidate["preparationDigest"],
                            "error": traceback.format_exc(),
                        }
                    )
                    + "\n"
                )
            raise
        if value is None:
            with events.open("a") as stream:
                stream.write(
                    json.dumps(
                        {
                            "preparationDigest": candidate["preparationDigest"],
                            "result": None,
                            "processState": process_record["state"],
                        }
                    )
                    + "\n"
                )
        return value

    discovery.maintain = observe_maintain

    with native.pool.connection() as c:
        _, auth = work.authority_factory(c, NS(principal_id=e.context.principal_id))
    own = e.business_owner.work_reader
    payload = dict(
        database=isolated_dsn(native.pool.conninfo),
        authorityMigration=str(e.repo.migration_path),
        executionMigration=str(native.migration_path),
        context=encode(e.context),
        generation=encode(auth.adapter.authorization.generation),
        ownedGeneration=encode(own.authorization.generation),
        epoch=auth.adapter.controller.readiness.recovery_epoch,
        ownedEpoch=own.recovery_epoch,
        policy=str(e.business_owner.path),
        expiry=e.wait_runtime_expiry.isoformat(),
        directory=str(directory),
        continuationPolicy=work.policy.model_dump(mode="json"),
    )
    config_path = directory / "test-owner-configuration.json"
    write(config_path, payload, exclusive=True)

    def spawn(command, **kwargs):
        assert command[-1] == "agent_operator.native_dispatch_host"
        environment = dict(kwargs["env"])
        startup_path = Path(environment["NATIVE_HOST_STARTUP_CONFIGURATION"])
        cfg = read(startup_path)
        output = directory / (startup_path.stem + "-result.json")
        environment["NATIVE_WAIT_TEST_OUTPUT"] = str(output)
        root = Path(__file__).resolve().parents[3]
        paths = tomllib.loads((root / "pyproject.toml").read_text())["tool"]["pytest"][
            "ini_options"
        ]["pythonpath"]
        environment["PYTHONPATH"] = os.pathsep.join(
            [
                str(Path(__file__).parent.resolve()),
                *(str(root / item) for item in paths),
            ]
        )
        kwargs["env"] = environment
        process = subprocess.Popen(
            [sys.executable, "-m", "native_wait_exec_child", str(config_path)], **kwargs
        )
        spawned.append((process, output, cfg))
        return process

    service = HostService(config, discovery, popen=spawn)
    service.spawned = spawned
    return service
