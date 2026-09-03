#!/usr/bin/env python3
# ruff: noqa: E501, RUF001
"""Idempotently assemble the bounded v0.2.2 Public Preview template.

This client uses only existing lifecycle HTTP APIs. It creates definitions and
an indexed Knowledge Pack; it never creates an Instance, Assignment, Run,
Attempt, Placement, or runtime process.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

PREFIX = "PV103 · "
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "X-Tenant-ID": "tenant-a",
    "X-Security-Domain": "supplier-quality-preview",
    "X-Principal-ID": "human:public-preview-owner",
}


@dataclass
class Client:
    base_url: str

    def request(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> Any:
        request = urllib.request.Request(
            self.base_url.rstrip("/") + path,
            data=None if body is None else json.dumps(body).encode(),
            headers=HEADERS,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(
                f"{method} {path} failed ({exc.code}): {detail}"
            ) from exc
        return None if not payload else json.loads(payload)


def current_revision(record: dict[str, Any]) -> dict[str, Any]:
    revision_id = record.get("publishedRevisionId") or record.get(
        "currentDraftRevisionId"
    )
    return next(
        item for item in record["revisions"] if item["revisionId"] == revision_id
    )


def existing(
    client: Client, path: str, name: str, envelope: str | None = None
) -> dict[str, Any] | None:
    values = client.request("GET", path)
    for value in values:
        record = value.get(envelope, value) if envelope else value
        if record.get("name") == name:
            return record
    return None


def publish_reviewed(
    client: Client, root: str, record: dict[str, Any], id_key: str, envelope: str
) -> dict[str, Any]:
    if record.get("publishedRevisionId"):
        return record
    identity = record[id_key]
    if record["lifecycleState"] == "DRAFT":
        record = client.request(
            "POST",
            f"{root}/{urllib.parse.quote(identity, safe='')}/validation",
            {"expectedVersion": record["aggregateVersion"]},
        )[envelope]
    revision = current_revision(record)
    if record["lifecycleState"] == "VALIDATED":
        record = client.request(
            "POST",
            f"{root}/{urllib.parse.quote(identity, safe='')}/reviews",
            {
                "expectedVersion": record["aggregateVersion"],
                "digest": revision["digest"],
                "decision": "APPROVE",
                "reason": "Bounded sanitized Public Preview fixture",
            },
        )[envelope]
    revision = current_revision(record)
    review_id = record.get("reviews", [{}])[-1].get("reviewId")
    body = {"expectedVersion": record["aggregateVersion"], "digest": revision["digest"]}
    if review_id:
        body["reviewId"] = review_id
    return client.request(
        "POST", f"{root}/{urllib.parse.quote(identity, safe='')}/publications", body
    )[envelope]


def ensure_simple(
    client: Client, kind: str, name: str, content: dict[str, Any]
) -> dict[str, Any]:
    root = f"/api/internal/v0.2.2/resources/{kind}"
    record = existing(client, root, name)
    if record is None:
        record = client.request("POST", root, {"name": name, "content": content})[
            "resource"
        ]
    return publish_reviewed(client, root, record, "resourceId", "resource")


@contextlib.contextmanager
def local_mcp_fixture():
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            message = json.loads(self.rfile.read(length) or b"{}")
            if message.get("method") == "notifications/initialized":
                self.send_response(202)
                self.end_headers()
                return
            result = {
                "initialize": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "serverInfo": {"name": "pv103-local-read-only", "version": "1"},
                },
                "tools/list": {
                    "tools": [
                        {
                            "name": "read_quality_records",
                            "description": "Read sanitized Preview quality facts",
                            "inputSchema": {"type": "object"},
                        }
                    ]
                },
                "resources/list": {"resources": []},
                "prompts/list": {"prompts": []},
            }.get(message.get("method"), {})
            payload = json.dumps(
                {"jsonrpc": "2.0", "id": message.get("id"), "result": result}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Mcp-Session-Id", "pv103-bounded-fixture")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def govern_mcp_tool(
    client: Client, record: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    selections = record.get("toolSelections", [])
    if selections:
        return record, selections[-1]["snapshotId"]
    with local_mcp_fixture():
        value = client.request(
            "POST",
            f"/api/internal/v0.2.2/resources/mcp/{urllib.parse.quote(record['resourceId'], safe='')}/discovery",
            {"expectedVersion": record["aggregateVersion"], "timeoutSeconds": 3},
        )
    record = value["resource"]
    snapshot_id = record["discoverySnapshots"][-1]["snapshotId"]
    value = client.request(
        "POST",
        f"/api/internal/v0.2.2/resources/mcp/{urllib.parse.quote(record['resourceId'], safe='')}/tool-selections",
        {
            "expectedVersion": record["aggregateVersion"],
            "snapshotId": snapshot_id,
            "toolNames": ["read_quality_records"],
            "reason": "PV103 approved bounded read-only fixture",
        },
    )
    return value["resource"], snapshot_id


def bootstrap(client: Client) -> dict[str, Any]:
    skill = ensure_simple(
        client,
        "skill",
        PREFIX + "供应商质量分析 Skill",
        {
            "description": "分析脱敏供应商质量事实",
            "capabilities": ["supplier-quality.analysis"],
            "instructions": "仅分析获批的脱敏输入，不执行外部写操作。",
            "sideEffect": "NONE",
            "idempotency": "IDEMPOTENT",
        },
    )
    mcp = ensure_simple(
        client,
        "mcp",
        PREFIX + "本地只读质量 MCP",
        {
            "description": "仅用于本地 Preview 的受限只读 MCP fixture",
            "capabilities": ["supplier-quality.read"],
            "endpoint": "http://127.0.0.1:8765/mcp",
            "permissions": ["quality:read"],
            "sideEffect": "NONE",
            "idempotency": "IDEMPOTENT",
        },
    )
    mcp, mcp_snapshot_id = govern_mcp_tool(client, mcp)

    knowledge_root = "/api/internal/v0.2.2/knowledge"
    knowledge = existing(client, knowledge_root, PREFIX + "供应商质量知识包")
    if knowledge is None:
        knowledge = client.request(
            "POST",
            knowledge_root,
            {
                "name": PREFIX + "供应商质量知识包",
                "source": {
                    "sourceId": "preview:pv103:source",
                    "documentId": "preview:pv103:procedure",
                    "kind": "TEXT",
                    "provenance": "human-approved:sanitized-public-preview",
                    "content": "供应商质量异常应先核验脱敏事实，再形成待人工审批的整改计划。",
                },
            },
        )["knowledge"]
    knowledge = publish_reviewed(
        client, knowledge_root, knowledge, "knowledgeId", "knowledge"
    )
    if not knowledge.get("activeIndexSnapshotId"):
        knowledge = client.request(
            "POST",
            f"{knowledge_root}/{urllib.parse.quote(knowledge['knowledgeId'], safe='')}/ingestion",
            {"expectedVersion": knowledge["aggregateVersion"]},
        )["knowledge"]
    if knowledge.get("lifecycleState") != "AVAILABLE":
        raise RuntimeError(
            "Knowledge ingestion did not produce an AVAILABLE indexed snapshot"
        )

    runtime_root = "/api/internal/v0.2.2/runtime-profiles"
    runtime = existing(
        client, runtime_root, PREFIX + "声明式 Runtime Profile", "profile"
    )
    if runtime is None:
        runtime = client.request(
            "POST",
            runtime_root,
            {
                "name": PREFIX + "声明式 Runtime Profile",
                "content": {
                    "provider": "NATIVE_KUBERNETES",
                    "resources": {
                        "cpuRequest": "250m",
                        "cpuLimit": "500m",
                        "memoryRequest": "256Mi",
                        "memoryLimit": "1Gi",
                    },
                    "isolation": "NAMESPACE",
                    "stateMode": "STATELESS",
                    "sessionAffinity": "NONE",
                    "secretReferences": [],
                    "openClawPackageRef": None,
                },
            },
        )["profile"]
    runtime = publish_reviewed(
        client, runtime_root, runtime, "runtimeProfileId", "profile"
    )

    def ref(record: dict[str, Any], id_key: str, kind: str) -> dict[str, str]:
        revision = current_revision(record)
        return {
            "kind": kind,
            "resourceId": record[id_key],
            "revisionId": revision["revisionId"],
        }

    workflow_root = "/api/internal/v0.2.2/workflow-definitions"
    workflow = existing(
        client,
        workflow_root,
        PREFIX + "质量分析 Workflow Definition",
        "definition",
    )
    workflow_content = {
        "description": "只定义受治理的 Preview 工作流，不创建 Workflow Run。",
        "tasks": [
            {
                "taskId": "analyze-sanitized-quality",
                "name": "分析脱敏质量事实",
                "inputs": ["sanitized-quality-facts"],
                "outputs": ["reviewable-analysis"],
                "capabilityRequirements": ["supplier-quality.analysis"],
                "references": [],
                "retryLimit": 0,
                "timeoutSeconds": 300,
                "failurePolicy": "FAIL_WORKFLOW",
            }
        ],
        "inputs": ["sanitized-quality-facts"],
        "outputs": ["reviewable-analysis"],
        "runtimeProfile": ref(runtime, "runtimeProfileId", "RUNTIME_PROFILE"),
    }
    if workflow is None:
        workflow = client.request(
            "POST",
            workflow_root,
            {
                "name": PREFIX + "质量分析 Workflow Definition",
                "content": workflow_content,
            },
        )["definition"]
    elif workflow["lifecycleState"] == "DRAFT":
        workflow = client.request(
            "PUT",
            f"{workflow_root}/{urllib.parse.quote(workflow['workflowDefinitionId'], safe='')}/draft",
            {
                "expectedVersion": workflow["aggregateVersion"],
                "content": workflow_content,
            },
        )["definition"]
    workflow = publish_reviewed(
        client, workflow_root, workflow, "workflowDefinitionId", "definition"
    )

    def exact(record: dict[str, Any], id_key: str) -> dict[str, str]:
        revision = current_revision(record)
        return {
            "resourceId": record[id_key],
            "revisionId": revision["revisionId"],
            "digest": revision["digest"].removeprefix("sha256:"),
        }

    agent_root = "/api/internal/v0.2.2/agent-definitions"
    agent = existing(client, agent_root, PREFIX + "供应商质量分析数字员工")
    agent_content = {
        "title": "供应商质量分析员",
        "duties": ["核验脱敏质量事实", "形成可供人工审核的分析"],
        "capabilities": ["supplier-quality.analysis"],
        "businessPurpose": "帮助质量负责人理解异常并准备受治理的后续计划。",
        "bindings": {
            "skills": [exact(skill, "resourceId")],
            "mcpTools": [
                {
                    **exact(mcp, "resourceId"),
                    "toolName": "read_quality_records",
                    "snapshotId": mcp_snapshot_id,
                }
            ],
            "knowledge": [
                {
                    **exact(knowledge, "knowledgeId"),
                    "snapshotId": knowledge["activeIndexSnapshotId"],
                }
            ],
            "workflow": {"kind": "workflow", **exact(workflow, "workflowDefinitionId")},
            "runtimeProfile": {
                "kind": "runtime-profile",
                **exact(runtime, "runtimeProfileId"),
            },
        },
    }
    if agent is None:
        agent = client.request(
            "POST",
            agent_root,
            {"name": PREFIX + "供应商质量分析数字员工", "content": agent_content},
        )["definition"]
    elif agent["lifecycleState"] == "DRAFT":
        agent = client.request(
            "PUT",
            f"{agent_root}/{urllib.parse.quote(agent['definitionId'], safe='')}/draft",
            {"expectedVersion": agent["aggregateVersion"], "content": agent_content},
        )["definition"]
    agent = publish_reviewed(client, agent_root, agent, "definitionId", "definition")

    templates = client.request(
        "GET", "/api/internal/v0.2.2/product/digital-employee-templates"
    )
    template = next(
        (
            item
            for item in templates
            if item["agentDefinition"]["identity"] == agent["definitionId"]
        ),
        None,
    )
    if template is None:
        raise RuntimeError(
            "Published Agent Definition was not readable as a Digital Employee template"
        )
    return {
        "owner": HEADERS["X-Principal-ID"],
        "resources": {
            "agent": agent["definitionId"],
            "skill": skill["resourceId"],
            "mcp": mcp["resourceId"],
            "knowledge": knowledge["knowledgeId"],
            "workflow": workflow["workflowDefinitionId"],
            "runtimeProfile": runtime["runtimeProfileId"],
        },
        "template": template,
        "prohibitedLifecycleCreated": False,
    }


def cleanup(client: Client) -> dict[str, Any]:
    actions: list[str] = []
    for kind in ("skill", "mcp"):
        for record in client.request("GET", f"/api/internal/v0.2.2/resources/{kind}"):
            if (
                record.get("name", "").startswith(PREFIX)
                and record.get("lifecycleState") != "DEPRECATED"
            ):
                client.request(
                    "POST",
                    f"/api/internal/v0.2.2/resources/{kind}/{urllib.parse.quote(record['resourceId'], safe='')}/deprecate",
                    {
                        "expectedVersion": record["aggregateVersion"],
                        "reason": "PV103 deterministic cleanup",
                    },
                )
                actions.append(record["resourceId"])
    return {
        "cleanup": "DEPRECATED_REVERSIBLY_WHERE_SUPPORTED",
        "resources": actions,
        "historyDeleted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    client = Client(args.base_url)
    print(
        json.dumps(
            cleanup(client) if args.cleanup else bootstrap(client),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
