"""324 local composition: requestability successor, no grants or Human decisions.

Uses the existing authority controller; credentials, expirations, static grants,
323 delegations and UNKNOWN reservations are never changed. Model runtime is
loaded only through explicit D324-5 configuration; this never issues admission.
Serve only after stopping the old same-database writer.
"""

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from agent_console.authority_configuration import StaticAuthorityLoader

ROOT = Path(__file__).resolve().parents[2]


def write_once(path, value):
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("IMMUTABLE_RUNTIME_CANDIDATE_CONFLICT")
    else:
        path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def stage(source_path, output):
    source = json.loads(source_path.read_text())
    current = json.loads(Path(source["generationPath"]).read_text())
    StaticAuthorityLoader.load(
        Path(source["generationPath"]), expected_digest=source["generationDigest"]
    )
    candidate = json.loads(json.dumps(current))
    candidate["generation"] += 1
    candidate["auditSource"] = "S5-V023-IMPL-324:bounded-owner-requestability"
    from agent_console.authority_configuration import OWNER_RESOURCE_PREFIXES

    groups = {
        "S5_324_RESOURCE_REVIEW": {
            "SKILL": ["READ_RESOURCE", "REVIEW_PUBLISH_RESOURCE"],
            "AGENT": ["READ_RESOURCE", "REVIEW_PUBLISH_RESOURCE"],
            "KNOWLEDGE": ["READ_RESOURCE", "REVIEW_PUBLISH_RESOURCE"],
            "RUNTIME_PROFILE": ["READ_RESOURCE", "REVIEW_PUBLISH_RESOURCE"],
        },
        "WORKBENCH_EMPLOYEE_LIFECYCLE": {
            "EMPLOYEE": ["CREATE", "LIST", "READ", "VALIDATE", "APPROVE", "PUBLISH"],
            "AGENT": ["READ"],
            "INSTANCE": ["CREATE", "READ"],
            "ASSIGNMENT": ["CREATE", "READ"],
            "SKILL": ["READ_RESOURCE"],
            "KNOWLEDGE": ["READ_RESOURCE"],
            "RUNTIME_PROFILE": ["READ_RESOURCE"],
        },
        "S5_324_NATIVE_READONLY": {
            "EXECUTION": ["START", "READ", "CANCEL", "RETRY"],
            "SKILL": ["INVOKE_SKILL", "READ_RESOURCE"],
            "KNOWLEDGE": ["READ_RESOURCE"],
            "RUNTIME_PROFILE": ["READ_RESOURCE"],
            "EMPLOYEE": ["READ"],
            "PLAN": ["READ", "PREPARE", "APPROVE"],
            "BUSINESS_PROBLEM": ["READ"],
            "SUCCESS_CRITERION": ["READ"],
            "SUCCESS_CRITERIA_SET": ["READ"],
            "RESOURCE_USE": ["READ"],
            "EVIDENCE": ["READ_REFERENCE"],
            "EVALUATION": ["EVALUATE", "READ"],
            "HUMAN_CONFIRMATION": ["CONFIRM", "READ"],
        },
    }
    for purpose, owners in groups.items():
        for owner, actions in owners.items():
            for action in actions:
                rule = {
                    "owner": owner,
                    "action": action,
                    "resourcePrefix": OWNER_RESOURCE_PREFIXES[owner],
                    "purpose": purpose,
                }
                if rule not in candidate["requestability"]:
                    candidate["requestability"].append(rule)
    output.mkdir(parents=True, exist_ok=True)
    generation = output / "generation.json"
    digest = write_once(generation, candidate)
    StaticAuthorityLoader.load(generation, expected_digest=digest)
    runtime = {
        **source,
        "generationPath": str(generation),
        "generationDigest": digest,
        "operatorId": "operator:s5-324-local-composition",
    }
    write_once(output / "runtime.json", runtime)
    write_once(output / "source-runtime.json", source)
    return {
        "generation": candidate["generation"],
        "digest": digest,
        "credentialsUnchanged": candidate["credentials"] == current["credentials"],
        "grantsCreated": 0,
        "providerDispatches": 0,
    }


def activate(output):
    from agent_console.authority_foundation import (
        ActivationBarrier,
        AuthorityGenerationController,
        AuthorityReadiness,
    )
    from agent_console.authority_postgres import PostgresAuthorityRepository
    from agent_console.authority_recovery import HostRecoveryControl

    source = json.loads((output / "source-runtime.json").read_text())
    runtime = json.loads((output / "runtime.json").read_text())
    old = StaticAuthorityLoader.load(
        Path(source["generationPath"]), expected_digest=source["generationDigest"]
    )
    candidate = StaticAuthorityLoader.load(
        Path(runtime["generationPath"]), expected_digest=runtime["generationDigest"]
    )
    repo = PostgresAuthorityRepository(
        runtime["databaseUrl"], migration_path=Path(runtime["migrationPath"])
    )
    try:
        state = repo.active_generation()
        if state is None or state[:2] not in (
            (old.generation, old.digest),
            (candidate.generation, candidate.digest),
        ):
            raise ValueError("UNEXPECTED_ACTIVE_GENERATION")
        control = HostRecoveryControl(Path(runtime["recoveryControlPath"]))
        current = candidate if state[0] == candidate.generation else old
        controller = AuthorityGenerationController(
            ActivationBarrier(current),
            repo,
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
        return {
            "generation": candidate.generation,
            "digest": candidate.digest,
            "grantsCreated": 0,
            "credentialsRenewed": 0,
        }
    finally:
        repo.close()


def serve(output, tls_manifest, origin):
    runtime = json.loads((output / "runtime.json").read_text())
    manifest = json.loads(tls_manifest.read_text())
    for key in (
        "AGENT_DEFINITION_DATABASE_URL",
        "EXECUTION_DATABASE_URL",
        "WORKFLOW_RUNTIME_DATABASE_URL",
        "SKILL_MCP_DATABASE_URL",
    ):
        os.environ[key] = runtime["databaseUrl"]
    for key in (
        "DRAFT_ASSISTANCE_RUNTIME_FILE",
        "PLANNING_RUNTIME_FILE",
        "KNOWLEDGE_DATABASE_URL",
        "AGENT_EXECUTION_EVIDENCE_DB",
    ):
        os.environ.pop(key, None)
    os.environ.pop("CONTEXT_CALL_ADMISSION_ENABLED", None)
    model_manifest = output / "context-call-runtime.json"
    if model_manifest.is_file():
        model_runtime = json.loads(model_manifest.read_text())
        if model_runtime.get("contextCallAdmission") != "D324-5":
            raise ValueError("D324_5_RUNTIME_CONFIGURATION_INVALID")
        for key, field in (
            ("DRAFT_ASSISTANCE_RUNTIME_FILE", "draftAssistanceRuntimeFile"),
            ("PLANNING_RUNTIME_FILE", "planningRuntimeFile"),
        ):
            path = Path(model_runtime[field])
            if not path.is_file():
                raise ValueError("D324_5_RUNTIME_CONFIGURATION_MISSING")
            os.environ[key] = str(path)
        os.environ["CONTEXT_CALL_ADMISSION_ENABLED"] = "true"
    os.environ.update(
        WORKBENCH_AUTHORITY_RUNTIME_FILE=str(output / "runtime.json"),
        WORKBENCH_ALLOWED_HOST=urlsplit(origin).netloc,
        WORKBENCH_ALLOWED_ORIGIN=origin,
        PLANNING_V2_ENABLED="true",
        PREPARED_EXECUTION_ENABLED="true",
    )
    import uvicorn
    from agent_console.app import get_workbench_app
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    app = get_workbench_app()
    dist = ROOT / "console/frontend/dist"
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}")
    def frontend(path: str):
        if path.startswith("api/"):
            from fastapi import HTTPException

            raise HTTPException(404)
        return FileResponse(dist / "index.html")

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=urlsplit(origin).port,
        ssl_certfile=manifest["certificate"],
        ssl_keyfile=manifest["key"],
        access_log=False,
    )


def main():
    os.umask(0o077)
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["stage", "activate", "serve"])
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--source-runtime", type=Path)
    p.add_argument("--tls-manifest", type=Path)
    p.add_argument("--origin", default="https://127.0.0.1:19436")
    args = p.parse_args()
    if args.action == "stage":
        print(json.dumps(stage(args.source_runtime, args.output)))
    elif args.action == "activate":
        print(json.dumps(activate(args.output)))
    else:
        serve(args.output, args.tls_manifest, args.origin)


if __name__ == "__main__":
    main()
