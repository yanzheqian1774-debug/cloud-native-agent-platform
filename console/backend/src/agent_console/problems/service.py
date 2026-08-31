# ruff: noqa: E501, RUF001
"""Process-local v0.2.1 Problem and immutable plan authority.

Model and vector-index adapters propose or derive data only. This module owns
Problem, plan-revision, approval, citation, and event identities.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from agent_console.agent_definition_repository import DefinitionScope
from agent_console.problems.providers import (
    ProblemPlanningError,
    embedding_provider_from_environment,
    planning_provider_from_environment,
)

SUPPLIER_QUALITY = (
    "某供应商近期交付质量持续下降，请分析原因，制定整改计划，"
    "并在审批后执行和验证改善效果。"
)


@dataclass(frozen=True, slots=True)
class TrustedPrincipal:
    tenant_id: str
    security_domain: str
    principal_id: str


def _digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class QdrantVectorIndexPort:
    def __init__(self) -> None:
        self.base_url = os.getenv("S5_IMPL_041_QDRANT_URL", "http://127.0.0.1:6333")
        self.collection = "s5_impl_041_supplier_quality"

    def rebuild(self, chunks: list[dict[str, Any]], vectors: list[list[float]]) -> str:
        if not vectors:
            raise ProblemPlanningError("EMPTY_INDEX_MANIFEST", 503)
        httpx.delete(f"{self.base_url}/collections/{self.collection}", timeout=10)
        created = httpx.put(
            f"{self.base_url}/collections/{self.collection}",
            json={"vectors": {"size": len(vectors[0]), "distance": "Cosine"}},
            timeout=30,
        )
        created.raise_for_status()
        points = [
            {
                "id": index + 1,
                "vector": vector,
                "payload": {
                    "chunk_id": chunk["chunkId"],
                    "chunk_digest": chunk["chunkDigest"],
                    "document_revision_id": chunk["documentRevisionId"],
                },
            }
            for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
        ]
        indexed = httpx.put(
            f"{self.base_url}/collections/{self.collection}/points",
            params={"wait": "true"},
            json={"points": points},
            timeout=30,
        )
        indexed.raise_for_status()
        return _digest([item["payload"] for item in points])

    def query(self, vector: list[float], limit: int) -> list[dict[str, Any]]:
        response = httpx.post(
            f"{self.base_url}/collections/{self.collection}/points/query",
            json={"query": vector, "limit": limit, "with_payload": True},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["result"]["points"]


class ProblemPlanningService:
    """Single-process preview authority with truthful restart-loss semantics."""

    def __init__(
        self,
        planning_provider: Any | None = None,
        vector_index: Any | None = None,
        embedding_provider: Any | None = None,
        agent_definitions: Callable[[DefinitionScope], list[dict[str, Any]]]
        | None = None,
    ) -> None:
        self.planning_provider = (
            planning_provider or planning_provider_from_environment()
        )
        self.embedding_provider = (
            embedding_provider
            or planning_provider
            or embedding_provider_from_environment()
        )
        self.vector_index = vector_index or QdrantVectorIndexPort()
        self.agent_definitions = agent_definitions or (lambda scope: [])
        self._lock = threading.Lock()
        self._problems: dict[str, dict[str, Any]] = {}
        self._analysis_streams: dict[str, dict[str, Any]] = {}
        self._completed_mutations: set[tuple[str, str, str]] = set()
        self._authority_epoch = f"process-local:{uuid.uuid4()}"
        self._chunks = self._seed_chunks()

    def _analysis_event(
        self,
        stream: dict[str, Any],
        event_type: str,
        stage: str,
        status: str,
        classification: str,
        payload: dict[str, Any],
        *,
        terminal: bool = False,
    ) -> dict[str, Any]:
        previous = stream["events"][-1] if stream["events"] else None
        event = {
            "schemaVersion": "problem-analysis-event.v1",
            "streamId": stream["streamId"],
            "eventId": f"analysis-event:{uuid.uuid4()}",
            "sequence": len(stream["events"]) + 1,
            "occurredAt": _now(),
            "eventType": event_type,
            "stage": stage,
            "status": status,
            "classification": classification,
            "terminal": terminal,
            "previousEventDigest": previous["eventDigest"] if previous else "GENESIS",
            "correlationId": stream["streamId"],
            "causationId": previous["eventId"] if previous else stream["streamId"],
            "actor": "problem-planning-service",
            "payload": payload,
        }
        event["eventDigest"] = _digest(event)
        stream["events"].append(event)
        return event

    def begin_analysis(
        self, command: dict[str, Any], principal: TrustedPrincipal
    ) -> Iterator[dict[str, Any]]:
        description = str(command.get("description", "")).strip()
        if not description:
            raise ProblemPlanningError("PROBLEM_DESCRIPTION_INVALID")
        stream_id = f"problem-analysis:{uuid.uuid4()}"
        stream = {
            "streamId": stream_id,
            "command": json.loads(json.dumps(command)),
            "principal": principal,
            "events": [],
            "state": "WAITING_FOR_HUMAN",
            "resultProblemId": None,
        }
        self._analysis_streams[stream_id] = stream
        initial = [
            (
                "PROBLEM_SUBMITTED",
                "SUBMISSION",
                "问题已提交",
                {"description": description},
            ),
            (
                "BUSINESS_INTENT_IDENTIFIED",
                "INTERPRETATION",
                "正在识别业务意图",
                {
                    "businessIntent": "分析供应商质量下降并形成可审核整改计划",
                    "state": "AI_SUGGESTION",
                },
            ),
            (
                "BUSINESS_ENTITIES_EXTRACTED",
                "INTERPRETATION",
                "正在提取业务对象",
                {
                    "entities": ["供应商", "交付批次", "质量缺陷", "整改计划"],
                    "state": "AI_SUGGESTION",
                },
            ),
            (
                "SCOPE_CONSTRAINTS_IDENTIFIED",
                "INTERPRETATION",
                "正在识别范围与约束",
                {
                    "scope": "近期供应商交付质量",
                    "constraints": [
                        "仅使用授权知识",
                        "需要人工审批",
                        "当前版本暂不执行",
                    ],
                    "state": "AI_SUGGESTION",
                },
            ),
            (
                "MISSING_INFORMATION_CHECKED",
                "CLARIFICATION",
                "正在检查缺失信息",
                {
                    "missingInformation": [
                        "确认供应商范围",
                        "确认时间范围",
                        "确认改善指标",
                    ],
                    "state": "WAITING_CONFIRMATION",
                },
            ),
            (
                "CLARIFICATION_REQUESTED",
                "CLARIFICATION",
                "需要人工补充信息",
                {
                    "questions": [
                        "是否限定当前受控供应商？",
                        "是否采用最近三个月交付批次？",
                        "是否以连续三批缺陷率低于百分之一为指标？",
                    ],
                    "state": "WAITING_FOR_HUMAN",
                },
            ),
        ]
        for event_type, stage, activity, payload in initial:
            yield self._analysis_event(
                stream, event_type, stage, activity, "PARTIAL", payload
            )

    def resume_analysis(
        self,
        stream_id: str,
        response: dict[str, Any],
        principal: TrustedPrincipal,
    ) -> Iterator[dict[str, Any]]:
        stream = self._analysis_streams.get(stream_id)
        if stream is None:
            raise ProblemPlanningError("ANALYSIS_STREAM_UNAVAILABLE_AFTER_RESTART", 404)
        original: TrustedPrincipal = stream["principal"]
        if original != principal:
            raise ProblemPlanningError("ANALYSIS_STREAM_NOT_FOUND", 404)
        if stream["state"] != "WAITING_FOR_HUMAN":
            raise ProblemPlanningError("ANALYSIS_STREAM_ALREADY_RESUMED", 409)
        stream["state"] = "RUNNING"
        yield self._analysis_event(
            stream,
            "CLARIFICATION_SUBMITTED",
            "CLARIFICATION",
            "已提交补充信息",
            "FORMAL",
            {"response": response, "state": "FORMAL_RECORD"},
        )
        yield self._analysis_event(
            stream,
            "KNOWLEDGE_RETRIEVAL_STARTED",
            "KNOWLEDGE",
            "正在检索授权知识",
            "PARTIAL",
            {"authorizationFilter": "APPLIED", "state": "GENERATING"},
        )
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.create, stream["command"], principal)
            heartbeat = 0
            while not future.done():
                heartbeat += 1
                yield self._analysis_event(
                    stream,
                    "CONTROLLED_MODEL_WORKING",
                    "INTERPRETATION",
                    "正在形成初步问题判断",
                    "PARTIAL",
                    {
                        "operation": "controlled structured planning",
                        "elapsedSeconds": heartbeat,
                        "state": "GENERATING",
                    },
                )
                time.sleep(1)
            try:
                problem = future.result()
            except Exception as exc:
                stream["state"] = "FAILED"
                yield self._analysis_event(
                    stream,
                    "ANALYSIS_FAILED",
                    "TERMINAL",
                    "生成失败",
                    "FORMAL",
                    {
                        "reasonCode": "CONTROLLED_PROVIDER_UNAVAILABLE",
                        "state": "FAILED",
                    },
                    terminal=True,
                )
                raise exc
        problem["clarificationAttempts"].append(
            {
                "streamId": stream_id,
                "response": response,
                "submittedAt": _now(),
                "state": "FORMAL_RECORD",
            }
        )
        problem["interpretations"].append(
            {
                **problem["interpretations"][-1],
                "revision": 2,
                "supplierScope": str(response.get("supplierScope", "当前受控供应商")),
                "timeRange": str(response.get("timeRange", "最近三个月交付批次")),
                "improvementIndicator": str(
                    response.get("improvementIndicator", "连续三批缺陷率低于百分之一")
                ),
                "createdAt": _now(),
                "source": "HUMAN_CLARIFICATION",
            }
        )
        artifacts = [
            (
                "KNOWLEDGE_RETRIEVAL_COMPLETED",
                "KNOWLEDGE",
                "已发现相关知识依据",
                {
                    "sources": [
                        {
                            "title": item["documentTitle"],
                            "excerpt": item["excerpt"],
                            "citationId": item["citationId"],
                            "selectionState": "SELECTED",
                            "expectedInfluence": item["selectionReason"],
                        }
                        for item in problem["knowledge"]["citations"]
                    ]
                },
            ),
            (
                "INITIAL_FINDING_PROPOSED",
                "INTERPRETATION",
                "正在形成初步问题判断",
                {
                    "supportedFindings": [problem["planRevisions"][-1]["summary"]],
                    "uncertainty": "需要 Human 核验业务范围与任务语义",
                    "limitations": problem["planRevisions"][-1]["limitations"],
                },
            ),
            (
                "BLUEPRINT_SEARCHED",
                "BLUEPRINT",
                "正在搜索解决方案蓝图",
                {
                    "candidates": [
                        item
                        for item in problem["blueprints"]
                        if item.get("blueprintId")
                    ]
                },
            ),
        ]
        revision = problem["planRevisions"][-1]
        for index, task in enumerate(revision["tasks"]):
            artifacts.append(
                (
                    "TASK_PROPOSED",
                    "TASKS",
                    "正在拆解任务",
                    {
                        "task": {
                            "taskId": task["taskId"],
                            "displayCode": task["displayCode"],
                            "name": task["name"],
                            "state": "AI_SUGGESTION",
                        },
                        "ordinal": index + 1,
                    },
                )
            )
            artifacts.append(
                (
                    "TASK_DEPENDENCY_PROPOSED",
                    "TASKS",
                    "正在建立任务依赖",
                    {
                        "taskId": task["taskId"],
                        "dependencies": task["dependencies"],
                        "state": "AI_SUGGESTION",
                    },
                )
            )
            artifacts.append(
                (
                    "RESOURCE_MATCH_PROPOSED",
                    "RESOURCES",
                    "正在匹配数字员工、Agent、Skill、MCP、知识和运行环境",
                    {
                        "taskId": task["taskId"],
                        "agentRevision": task["agentRevision"],
                        "skillRevisions": task["skillRevisions"],
                        "mcpOperations": task["mcpRevisions"],
                        "knowledgeSnapshot": task["knowledgeSnapshotId"],
                        "runtimeRequirements": task["runtimeRequirements"],
                        "explanation": "授权过滤后与任务角色和质量分析能力匹配",
                        "state": "SYSTEM_VALIDATED",
                    },
                )
            )
        artifacts.extend(
            [
                (
                    "CAPABILITY_GAP_IDENTIFIED",
                    "GAPS",
                    "正在识别能力缺口",
                    {"gaps": revision["capabilityGaps"], "state": "SYSTEM_VALIDATED"},
                ),
                (
                    "PLAN_REVISION_ASSEMBLED",
                    "PLAN",
                    "正在生成计划修订版本",
                    {
                        "planRevisionId": revision["planRevisionId"],
                        "canonicalDigest": revision["canonicalDigest"],
                        "state": "FORMAL_RECORD",
                    },
                ),
                (
                    "SCHEMA_VALIDATION_COMPLETED",
                    "VALIDATION",
                    "正在进行结构校验",
                    {"result": "PASS", "state": "SYSTEM_VALIDATED"},
                ),
                (
                    "RULE_VALIDATION_COMPLETED",
                    "VALIDATION",
                    "正在进行规则校验",
                    {
                        "result": revision["provenance"]["ruleValidation"],
                        "authorizationValidation": "PASS",
                        "state": "SYSTEM_VALIDATED",
                    },
                ),
                (
                    "PLAN_READY_FOR_HUMAN_REVIEW",
                    "REVIEW",
                    "计划已准备好，等待人工审核",
                    {
                        "problemId": problem["problemId"],
                        "planRevisionId": revision["planRevisionId"],
                        "canonicalDigest": revision["canonicalDigest"],
                        "state": "FORMAL_RECORD",
                    },
                ),
            ]
        )
        for index, (event_type, stage, activity, payload) in enumerate(artifacts):
            yield self._analysis_event(
                stream,
                event_type,
                stage,
                activity,
                "FORMAL"
                if payload.get("state") in {"FORMAL_RECORD", "SYSTEM_VALIDATED"}
                else "PARTIAL",
                payload,
                terminal=index == len(artifacts) - 1,
            )
        stream["state"] = "COMPLETED"
        stream["resultProblemId"] = problem["problemId"]

    def replay_analysis(
        self, stream_id: str, last_event_id: str | None, principal: TrustedPrincipal
    ) -> list[dict[str, Any]]:
        stream = self._analysis_streams.get(stream_id)
        if stream is None:
            raise ProblemPlanningError("ANALYSIS_STREAM_UNAVAILABLE_AFTER_RESTART", 404)
        if stream["principal"] != principal:
            raise ProblemPlanningError("ANALYSIS_STREAM_NOT_FOUND", 404)
        events = stream["events"]
        if last_event_id is None:
            return events
        indexes = [
            index
            for index, item in enumerate(events)
            if item["eventId"] == last_event_id
        ]
        if not indexes:
            raise ProblemPlanningError("ANALYSIS_RESUME_UNAVAILABLE", 409)
        return events[indexes[0] + 1 :]

    @staticmethod
    def _seed_chunks() -> list[dict[str, Any]]:
        documents = [
            (
                "docrev:supplier-quality:baseline:v1",
                "基础供应商质量程序要求按批次核对来料不合格、过程缺陷与客户退货，并由质量经理复核。",
                "基础供应商质量程序",
            ),
            (
                "docrev:supplier-quality:8d:v2",
                "八维整改程序要求在二十四小时内完成围堵并由供应商质量负责人承担纠正措施；根因必须通过数据复现验证，效果验证要求连续三批缺陷率低于百分之一。若重复缺陷或逾期，必须升级质量经理审批。证据必须包括围堵记录、根因验证报告、措施责任确认、三批效果数据和审批记录。",
                "八维整改程序",
            ),
        ]
        return [
            {
                "chunkId": f"chunk:supplier-quality:{index + 1}",
                "documentRevisionId": revision,
                "chunkDigest": _digest(text),
                "excerpt": text,
                "ordinal": 1,
                "documentTitle": title,
                "documentVersion": revision.rsplit(":", 1)[-1],
            }
            for index, (revision, text, title) in enumerate(documents)
        ]

    @staticmethod
    def _scope(problem: dict[str, Any], principal: TrustedPrincipal) -> None:
        if (
            problem["tenantId"] != principal.tenant_id
            or problem["securityDomain"] != principal.security_domain
        ):
            raise ProblemPlanningError("PROBLEM_NOT_FOUND", 404)

    def _events(
        self, problem_id: str, attempt_id: str, types: list[str]
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        previous = "GENESIS"
        for sequence, event_type in enumerate(types, 1):
            body = {
                "streamId": f"planning-stream:{problem_id}",
                "problemId": problem_id,
                "attemptId": attempt_id,
                "authorityEpoch": self._authority_epoch,
                "sequence": sequence,
                "eventType": event_type,
                "previousEventDigest": previous,
                "classification": "PARTIAL"
                if event_type.endswith("DELTA")
                else "AUTHORITATIVE",
                "correlationId": attempt_id,
                "causationId": events[-1]["eventId"] if events else problem_id,
                "occurredAt": _now(),
            }
            body["eventId"] = f"event:{_digest(body)[7:31]}"
            body["eventDigest"] = _digest(body)
            previous = body["eventDigest"]
            events.append(body)
        return events

    @staticmethod
    def _display_code(prefix: str, ordinal: int, revision: int | None = None) -> str:
        base = f"{prefix}-{ordinal:04d}"
        return f"{base}-R{revision:02d}" if revision is not None else base

    def _append_event(
        self,
        problem: dict[str, Any],
        event_type: str,
        *,
        evidence_id: str | None = None,
    ) -> None:
        previous = problem["events"][-1]
        body = {
            "streamId": previous["streamId"],
            "problemId": problem["problemId"],
            "attemptId": previous["attemptId"],
            "authorityEpoch": self._authority_epoch,
            "sequence": previous["sequence"] + 1,
            "eventType": event_type,
            "previousEventDigest": previous["eventDigest"],
            "classification": "AUTHORITATIVE",
            "correlationId": previous["correlationId"],
            "causationId": previous["eventId"],
            "occurredAt": _now(),
        }
        if evidence_id:
            body["evidenceId"] = evidence_id
        body["eventId"] = f"event:{_digest(body)[7:31]}"
        body["eventDigest"] = _digest(body)
        problem["events"].append(body)

    @staticmethod
    def _validate_dag(tasks: list[dict[str, Any]]) -> None:
        ids = {item["taskId"] for item in tasks}
        if len(ids) != len(tasks):
            raise ProblemPlanningError("DUPLICATE_TASK_REFERENCE")
        if any(dep not in ids for item in tasks for dep in item["dependencies"]):
            raise ProblemPlanningError("MISSING_TASK_REFERENCE")
        visiting: set[str] = set()
        visited: set[str] = set()
        by_id = {item["taskId"]: item for item in tasks}

        def visit(task_id: str) -> None:
            if task_id in visiting:
                raise ProblemPlanningError("TASK_DAG_CYCLE")
            if task_id in visited:
                return
            visiting.add(task_id)
            for dependency in by_id[task_id]["dependencies"]:
                visit(dependency)
            visiting.remove(task_id)
            visited.add(task_id)

        for task_id in ids:
            visit(task_id)

    def create(
        self, command: dict[str, Any], principal: TrustedPrincipal
    ) -> dict[str, Any]:
        started = time.perf_counter()
        timings: dict[str, int] = {"problemAcceptanceMs": 0}
        description = str(command.get("description", "")).strip()
        if not description or len(description) > 2000:
            raise ProblemPlanningError("PROBLEM_DESCRIPTION_INVALID")
        include_new = bool(command.get("includeNewKnowledge", False))
        authorized = self._chunks if include_new else self._chunks[:1]
        accepted = time.perf_counter()
        timings["problemAcceptanceMs"] = round((accepted - started) * 1000)
        retrieval_started = time.perf_counter()
        vectors = self.embedding_provider.embed(
            [item["excerpt"] for item in authorized]
        )
        manifest = self.vector_index.rebuild(authorized, vectors)
        query_vector = self.embedding_provider.embed([description])[0]
        dense = self.vector_index.query(query_vector, 8)
        dense_by_chunk = {item["payload"]["chunk_id"]: item for item in dense}
        terms = set(description.replace("，", " ").replace("。", " ").split())
        ranked = []
        for chunk in authorized:
            lexical = sum(1 for term in terms if term and term in chunk["excerpt"])
            dense_item = dense_by_chunk.get(chunk["chunkId"], {"score": 0.0})
            ranked.append(
                (float(dense_item["score"]) * 0.65 + lexical * 0.35, lexical, chunk)
            )
        ranked.sort(key=lambda item: (-item[0], item[2]["chunkId"]))
        context = [item[2] for item in ranked]
        timings["retrievalMs"] = round((time.perf_counter() - retrieval_started) * 1000)
        model_started = time.perf_counter()
        proposal = self.planning_provider.propose(description, context)
        timings["controlledModelPlanningMs"] = round(
            (time.perf_counter() - model_started) * 1000
        )
        validation_started = time.perf_counter()
        # Deterministic rules own the executable boundary and exact DAG.
        task_specs = [
            ("collect", "收集并核验质量事实", [], "quality-analyst"),
            ("analyze", "验证质量下降根因", ["collect"], "quality-analyst"),
            ("plan", "形成供应商整改计划", ["analyze"], "supplier-quality-lead"),
        ]
        if include_new:
            task_specs.insert(
                2,
                (
                    "contain",
                    "制定围堵与八维纠正措施",
                    ["analyze"],
                    "supplier-quality-lead",
                ),
            )
            task_specs[-1] = (
                "plan",
                "形成含效果验证门槛的整改计划",
                ["validate"],
                "supplier-quality-lead",
            )
            task_specs.insert(
                3,
                (
                    "validate",
                    "验证三批改善效果并触发升级判断",
                    ["contain"],
                    "quality-analyst",
                ),
            )
        problem_id = f"problem:{uuid.uuid4()}"
        attempt_id = f"attempt:{uuid.uuid4()}"
        citations = [
            {
                "citationId": f"citation:{item['chunkId']}",
                **item,
                "denseRank": next(
                    (
                        i + 1
                        for i, point in enumerate(dense)
                        if point["payload"]["chunk_id"] == item["chunkId"]
                    ),
                    None,
                ),
                "denseScore": dense_by_chunk.get(item["chunkId"], {}).get("score"),
                "lexicalScore": lexical,
                "influence": "INFLUENCED_PLAN",
                "selectionReason": (
                    "新增授权程序直接规定围堵、责任、阈值、升级、审批和证据要求。"
                    if item["documentRevisionId"].endswith("8d:v2")
                    else "基础程序支持质量事实核对与根因判断。"
                ),
                "affectedTasks": (
                    ["contain", "validate", "plan"]
                    if item["documentRevisionId"].endswith("8d:v2")
                    else ["collect", "analyze"]
                ),
            }
            for _, lexical, item in ranked
        ]
        tasks = [
            {
                "taskId": f"task:{problem_id.split(':', 1)[1]}:{key}",
                "name": title,
                "description": title,
                "revision": 1,
                "lifecycle": "PLANNED",
                "provenance": "MODEL_PROPOSED_RULE_VALIDATED",
                "authorizationState": "VISIBLE_AND_MATCHABLE",
                "dependencies": [
                    f"task:{problem_id.split(':', 1)[1]}:{dep}" for dep in deps
                ],
                "role": role,
                "agentRevision": f"agent-definition:{role}:v1",
                "skillRevisions": ["skill:quality-analysis:v1"],
                "mcpRevisions": ["mcp:quality-records:operation:read:v1"],
                "knowledgeSnapshotId": f"index-snapshot:{manifest[7:23]}",
                "runtimeRequirements": ["runtime:native:planning-only:v1"],
                "inputs": [
                    "authorized-problem-revision",
                    "authorized-knowledge-snapshot",
                ],
                "outputs": ["reviewable-plan-artifact"],
                "approvalRequirements": (
                    ["supplier-quality-manager", "quality-manager-escalation"]
                    if include_new and key in {"contain", "validate", "plan"}
                    else ["supplier-quality-manager"]
                ),
                "expectedEvidence": (
                    [
                        "围堵记录",
                        "根因验证报告",
                        "措施责任确认",
                        "连续三批效果数据",
                        "审批记录",
                    ]
                    if include_new and key in {"contain", "validate", "plan"}
                    else ["质量事实记录", "根因分析报告"]
                ),
                "validationCriteria": (
                    [
                        "二十四小时内完成围堵",
                        "根因可通过数据复现",
                        "连续三批缺陷率低于百分之一",
                        "重复缺陷或逾期必须升级",
                        "当前版本暂不执行",
                    ]
                    if include_new and key in {"contain", "validate", "plan"}
                    else ["来源可追溯", "根因有证据", "当前版本暂不执行"]
                ),
                "displayCode": self._display_code("TSK", index + 1),
                "candidateMatches": {
                    "digitalEmployees": [f"digital-employee:{role}:v1"],
                    "agentRevisions": [f"agent-definition:{role}:v1"],
                    "skillRevisions": ["skill:quality-analysis:v1"],
                    "mcpOperations": ["mcp:quality-records:operation:read:v1"],
                    "knowledgeSnapshots": [f"index-snapshot:{manifest[7:23]}"],
                    "runtimeRequirements": ["runtime:native:planning-only:v1"],
                },
            }
            for index, (key, title, deps, role) in enumerate(task_specs)
        ]
        plan_body = {
            "problemRevision": 1,
            "interpretationRevision": 1,
            "classification": proposal["classification"],
            "summary": proposal["summary"],
            "tasks": tasks,
            "capabilityGaps": [
                {
                    "state": "GAP",
                    "description": "尚无已发布并获准匹配的供应商质量分析 Agent Definition。",
                    "missingCapability": "supplier-quality-analysis",
                    "impact": "计划缺少可复用的 Agent Definition。",
                    "recommendedAction": "在 Agent Workbench 创建、审核并发布适用定义。",
                    "targetVersion": "v0.2.2",
                },
                {
                    "state": "PARTIALLY_SUPPORTED",
                    "description": (
                        "已规划围堵、升级与效果阈值，但实际执行和效果采集属于后续版本。"
                        if include_new
                        else "执行与效果验证属于后续版本；当前只完成分析和计划审批。"
                    ),
                    "missingCapability": "受控派发、运行与效果证据采集",
                    "impact": "计划可以审核和批准，但不能派发或执行。",
                    "recommendedAction": (
                        "需要人工确认当前计划；建议在 v0.2.2 发布资源，"
                        "并在 v0.2.3 配置运行环境。"
                    ),
                    "targetVersion": "v0.2.2 / v0.2.3",
                },
            ],
            "limitations": [
                "PROCESS_LOCAL_TECHNICAL_PREVIEW",
                "NO_EXECUTION",
                "NO_AGENT_OR_RUNTIME_INSTANCE",
            ],
            "provenance": {
                "provider": self.planning_provider.provider_id,
                "model": self.planning_provider.model,
                "promptTemplateRevision": "supplier-quality-planning.zh-CN.v1",
                "inputDigest": _digest(description),
                "outputDigest": _digest(proposal),
                "schemaValidation": "PASS",
                "ruleValidation": "PASS_WITH_EXECUTION_BOUNDARY_ENFORCED",
            },
        }
        revision_id = f"plan-revision:{uuid.uuid4()}:1"
        revision_created = _now()
        revision = {
            "planId": f"plan:{problem_id.split(':', 1)[1]}",
            "planRevisionId": revision_id,
            "revision": 1,
            "status": "PLAN_REVIEW",
            "approvalState": "PENDING",
            "createdAt": revision_created,
            "updatedAt": revision_created,
            "knowledgeSnapshotId": f"index-snapshot:{manifest[7:23]}",
            "capabilityGapCount": len(plan_body["capabilityGaps"]),
            "displayCode": self._display_code("PLN", 1, 1),
            **plan_body,
        }
        revision["canonicalDigest"] = _digest(revision)
        now = _now()
        timings["schemaAndRuleValidationMs"] = round(
            (time.perf_counter() - validation_started) * 1000
        )
        record = {
            "problemId": problem_id,
            "name": str(command.get("name") or "供应商质量下降分析与整改"),
            "description": description,
            "tenantId": principal.tenant_id,
            "securityDomain": principal.security_domain,
            "principalId": principal.principal_id,
            "revision": 1,
            "status": "PLAN_REVIEW",
            "provenance": "HUMAN_SUBMITTED",
            "createdAt": now,
            "updatedAt": now,
            "displayCode": self._display_code("PRB", len(self._problems) + 1),
            "planningAttempts": [
                {
                    "attemptId": attempt_id,
                    "displayCode": self._display_code("ATT", 1),
                    "state": "COMPLETED",
                    "createdAt": now,
                    "knowledgeMode": "EXPANDED" if include_new else "BASELINE",
                }
            ],
            "interpretations": [
                {
                    "revision": 1,
                    "supplierScope": "当前供应商",
                    "timeRange": "近期交付批次",
                    "improvementIndicator": "缺陷率下降并持续稳定",
                    "summary": proposal["summary"],
                    "createdAt": now,
                    "source": "CONTROLLED_MODEL_PROPOSAL",
                }
            ],
            "humanDecisions": [],
            "clarificationAttempts": [],
            "knowledge": {
                "knowledgeBaseId": "knowledge-base:supplier-quality",
                "indexSnapshotId": f"index-snapshot:{manifest[7:23]}",
                "indexManifestDigest": manifest,
                "retrievalState": "RETRIEVED" if citations else "EMPTY",
                "citations": citations,
                "selectedCitationIds": [item["citationId"] for item in citations],
            },
            "blueprints": [
                {
                    "blueprintId": "solution-blueprint:supplier-quality:v1",
                    "name": "供应商质量整改解决方案蓝图",
                    "purpose": "复用质量分析与整改审核能力，形成可追溯的待审核计划。",
                    "state": "PARTIALLY_SUPPORTED",
                    "visibleReusableComponents": [
                        "quality-analyst",
                        "supplier-quality-lead",
                    ],
                    "matchedAgents": sorted({task["agentRevision"] for task in tasks}),
                    "matchedSkills": sorted(
                        {item for task in tasks for item in task["skillRevisions"]}
                    ),
                    "matchedMcpOperations": sorted(
                        {item for task in tasks for item in task["mcpRevisions"]}
                    ),
                    "matchedKnowledge": [f"index-snapshot:{manifest[7:23]}"],
                    "runtimeRequirements": ["runtime:native:planning-only:v1"],
                    "authorizationPrerequisites": ["supplier-quality-manager"],
                    "supportReason": (
                        "分析、检索、资源匹配和审批可用；派发与执行当前不可用。"
                    ),
                    "planImpact": f"生成 {len(tasks)} 个任务并绑定精确资源修订版本。",
                    "recommendedAction": (
                        "可直接复用当前分析资源；需要人工确认计划；"
                        "后续版本补充执行能力。"
                    ),
                    "targetVersion": "v0.2.2 / v0.2.3",
                },
                {
                    "state": "UNAVAILABLE_OR_DENIED",
                    "description": (
                        "该资源当前不可使用，或你没有查看权限。为保护权限边界，"
                        "系统不会披露资源身份和数量。"
                    ),
                },
            ],
            "planRevisions": [revision],
            "currentPlanRevisionId": revision_id,
            "approval": None,
            "selectedBlueprintId": "solution-blueprint:supplier-quality:v1",
            "timings": timings,
        }
        record["events"] = self._events(
            problem_id,
            attempt_id,
            [
                "PROBLEM_ACCEPTED",
                "INTERPRETATION_STARTED",
                "INTERPRETATION_DELTA",
                "INTERPRETATION_PROPOSED",
                "KNOWLEDGE_RETRIEVAL_STARTED",
                "KNOWLEDGE_HIT",
                "BLUEPRINT_SEARCH_STARTED",
                "BLUEPRINT_CANDIDATE",
                "TASK_DAG_PROPOSED",
                "PLAN_REVISION_PROPOSED",
                "SCHEMA_VALIDATION_COMPLETED",
                "RULE_VALIDATION_COMPLETED",
                "PLAN_READY_FOR_HUMAN_REVIEW",
                "STREAM_COMPLETED",
            ],
        )
        with self._lock:
            self._problems[problem_id] = record
        timings["comparisonAssemblyMs"] = round(
            (time.perf_counter() - validation_started) * 1000
        )
        timings["totalMs"] = round((time.perf_counter() - started) * 1000)
        return record

    def get(self, problem_id: str, principal: TrustedPrincipal) -> dict[str, Any]:
        problem = self._problems.get(problem_id)
        if problem is None:
            raise ProblemPlanningError("PREVIEW_STATE_UNAVAILABLE_AFTER_RESTART", 404)
        self._scope(problem, principal)
        return problem

    def rematch(self, problem_id: str, principal: TrustedPrincipal) -> dict[str, Any]:
        problem = self.get(problem_id, principal)
        current = problem["planRevisions"][-1]
        eligible = self.agent_definitions(
            DefinitionScope(principal.tenant_id, principal.security_domain)
        )
        candidates = []
        for item in eligible:
            revision = item["revision"]
            if "supplier-quality-analysis" in revision["content"]["capabilities"]:
                candidates.append((item["definition"]["definitionId"], revision))
        gap = next(
            (
                item
                for item in current["capabilityGaps"]
                if item["missingCapability"] == "supplier-quality-analysis"
            ),
            None,
        )
        if gap is not None and candidates:
            definition_id, revision = sorted(
                candidates, key=lambda value: (value[0], value[1]["revisionId"])
            )[0]
            gap.update(
                {
                    "state": "MATCHED",
                    "description": "已由受治理的已发布 Agent Definition 满足。",
                    "matchedDefinitionId": definition_id,
                    "matchedRevisionId": revision["revisionId"],
                    "matchedDigest": revision["digest"],
                    "executionAuthority": "NOT_GRANTED",
                }
            )
        current["capabilityGapCount"] = sum(
            1 for item in current["capabilityGaps"] if item["state"] != "MATCHED"
        )
        problem["updatedAt"] = _now()
        return problem

    def intervene(
        self, problem_id: str, command: dict[str, Any], principal: TrustedPrincipal
    ) -> dict[str, Any]:
        mutation_key = (problem_id, "INTERVENTION", _digest(command))
        with self._lock:
            if mutation_key in self._completed_mutations:
                return self.get(problem_id, principal)
            result = self._intervene_once(problem_id, command, principal)
            self._completed_mutations.add(mutation_key)
            return result

    def _intervene_once(
        self, problem_id: str, command: dict[str, Any], principal: TrustedPrincipal
    ) -> dict[str, Any]:
        problem = self.get(problem_id, principal)
        current = problem["planRevisions"][-1]
        if command.get("predecessorDigest") != current["canonicalDigest"]:
            raise ProblemPlanningError("STALE_OR_SUPERSEDED_PLAN", 409)
        if problem["approval"] is not None:
            raise ProblemPlanningError("PLAN_ALREADY_APPROVED", 409)
        kind = str(command.get("kind", ""))
        reason = str(command.get("reason", "")).strip()
        if not reason:
            raise ProblemPlanningError("HUMAN_REASON_REQUIRED")
        supported = {
            "CLARIFICATION",
            "INTERPRETATION",
            "KNOWLEDGE",
            "BLUEPRINT",
            "TASK",
            "RESOURCE_MATCH",
            "CAPABILITY_GAP",
        }
        if kind not in supported:
            raise ProblemPlanningError("INTERVENTION_KIND_UNSUPPORTED")
        successor = json.loads(json.dumps(current))
        before: list[dict[str, Any]] = []
        event_types: list[str] = []
        payload = command.get("payload") or {}
        if not isinstance(payload, dict):
            raise ProblemPlanningError("INTERVENTION_PAYLOAD_INVALID")
        if kind in {"CLARIFICATION", "INTERPRETATION"}:
            previous = problem["interpretations"][-1]
            interpretation = {
                **previous,
                **{key: str(value) for key, value in payload.items()},
            }
            interpretation["revision"] = previous["revision"] + 1
            interpretation["createdAt"] = _now()
            interpretation["source"] = "HUMAN_CORRECTED"
            problem["interpretations"].append(interpretation)
            before.append(
                {"field": "interpretation", "previous": previous, "new": interpretation}
            )
            event_types = ["CLARIFICATION_SUBMITTED", "INTERPRETATION_CORRECTED"]
        elif kind == "KNOWLEDGE":
            visible = {item["citationId"] for item in problem["knowledge"]["citations"]}
            selected = list(dict.fromkeys(payload.get("selectedCitationIds", [])))
            if not selected or any(item not in visible for item in selected):
                raise ProblemPlanningError("KNOWLEDGE_SELECTION_NOT_AUTHORIZED")
            old = problem["knowledge"]["selectedCitationIds"]
            problem["knowledge"]["selectedCitationIds"] = selected
            before.append(
                {"field": "selectedCitationIds", "previous": old, "new": selected}
            )
            event_types = ["KNOWLEDGE_SOURCE_SELECTED"]
            if set(old) - set(selected):
                event_types.append("KNOWLEDGE_SOURCE_EXCLUDED")
        elif kind == "BLUEPRINT":
            selected = payload.get("blueprintId")
            visible = {
                item.get("blueprintId")
                for item in problem["blueprints"]
                if item.get("blueprintId")
            }
            if selected is not None and selected not in visible:
                raise ProblemPlanningError("BLUEPRINT_SELECTION_NOT_AUTHORIZED")
            old = problem.get("selectedBlueprintId")
            problem["selectedBlueprintId"] = selected
            before.append(
                {"field": "selectedBlueprintId", "previous": old, "new": selected}
            )
            event_types = ["BLUEPRINT_SELECTED"]
        elif kind == "TASK":
            task_id = str(payload.get("taskId", ""))
            task = next(
                (item for item in successor["tasks"] if item["taskId"] == task_id), None
            )
            if task is None:
                raise ProblemPlanningError("TASK_NOT_FOUND", 404)
            allowed = {
                "name",
                "description",
                "dependencies",
                "outputs",
                "validationCriteria",
            }
            changes = payload.get("changes") or {}
            if (
                not isinstance(changes, dict)
                or not changes
                or any(key not in allowed for key in changes)
            ):
                raise ProblemPlanningError("TASK_CHANGE_NOT_ALLOWED")
            for field, value in changes.items():
                before.append(
                    {
                        "field": f"task.{task_id}.{field}",
                        "previous": task[field],
                        "new": value,
                    }
                )
                task[field] = value
            task["revision"] += 1
            self._validate_dag(successor["tasks"])
            event_types = ["TASK_UPDATED_BY_HUMAN"]
            if "dependencies" in changes:
                event_types.append("DEPENDENCY_UPDATED_BY_HUMAN")
        elif kind == "RESOURCE_MATCH":
            task_id = str(payload.get("taskId", ""))
            task = next(
                (item for item in successor["tasks"] if item["taskId"] == task_id), None
            )
            if task is None:
                raise ProblemPlanningError("TASK_NOT_FOUND", 404)
            agent = payload.get("agentRevision")
            if agent not in task["candidateMatches"]["agentRevisions"]:
                raise ProblemPlanningError("RESOURCE_MATCH_NOT_AUTHORIZED")
            before.append(
                {
                    "field": f"task.{task_id}.agentRevision",
                    "previous": task["agentRevision"],
                    "new": agent,
                }
            )
            task["agentRevision"] = agent
            event_types = ["RESOURCE_MATCH_SELECTED"]
        else:
            gap_index = int(payload.get("gapIndex", 0))
            if gap_index < 0 or gap_index >= len(successor["capabilityGaps"]):
                raise ProblemPlanningError("CAPABILITY_GAP_NOT_FOUND", 404)
            disposition = str(payload.get("disposition", ""))
            allowed = {
                "USE_EXISTING",
                "ADJUST_TASK",
                "ACCEPT_LIMITATION",
                "FOLLOW_UP_PROPOSAL",
                "REPLAN",
            }
            if disposition not in allowed:
                raise ProblemPlanningError("CAPABILITY_GAP_DISPOSITION_INVALID")
            gap = successor["capabilityGaps"][gap_index]
            before.append(
                {
                    "field": f"capabilityGap.{gap_index}.disposition",
                    "previous": gap.get("disposition"),
                    "new": disposition,
                }
            )
            gap["disposition"] = disposition
            gap["responsibleRole"] = str(
                payload.get("responsibleRole") or "supplier-quality-manager"
            )
            gap["executionConsequence"] = "当前版本暂不执行；决定仅影响待审核计划。"
            event_types = [
                "REPLAN_REQUESTED"
                if disposition == "REPLAN"
                else "CAPABILITY_GAP_ACCEPTED"
            ]
        successor["revision"] += 1
        successor["planRevisionId"] = (
            f"{current['planId']}:revision:{successor['revision']}"
        )
        successor["displayCode"] = self._display_code("PLN", 1, successor["revision"])
        successor["predecessorRevisionId"] = current["planRevisionId"]
        successor["status"] = "PLAN_REVIEW"
        successor["approvalState"] = "PENDING"
        successor["createdAt"] = _now()
        successor["updatedAt"] = successor["createdAt"]
        evidence_id = f"evidence:{uuid.uuid4()}"
        successor["humanChangeSet"] = {
            "evidenceId": evidence_id,
            "kind": kind,
            "reason": reason,
            "changes": before,
            "affectedTaskIds": sorted(
                {
                    item["field"].split(".")[1]
                    for item in before
                    if item["field"].startswith("task.")
                }
            ),
            "previousRevisionId": current["planRevisionId"],
        }
        successor.pop("canonicalDigest", None)
        successor["canonicalDigest"] = _digest(successor)
        problem["planRevisions"].append(successor)
        problem["currentPlanRevisionId"] = successor["planRevisionId"]
        problem["updatedAt"] = successor["updatedAt"]
        problem["humanDecisions"].append(
            {
                **successor["humanChangeSet"],
                "planRevisionId": successor["planRevisionId"],
                "canonicalDigest": successor["canonicalDigest"],
            }
        )
        for event_type in [*event_types, "PLAN_REVISION_CREATED"]:
            self._append_event(problem, event_type, evidence_id=evidence_id)
        return problem

    def list(self, principal: TrustedPrincipal) -> list[dict[str, Any]]:
        return [
            item
            for item in self._problems.values()
            if item["tenantId"] == principal.tenant_id
            and item["securityDomain"] == principal.security_domain
        ]

    def correct(
        self, problem_id: str, command: dict[str, Any], principal: TrustedPrincipal
    ) -> dict[str, Any]:
        mutation_key = (problem_id, "CORRECTION", _digest(command))
        with self._lock:
            if mutation_key in self._completed_mutations:
                return self.get(problem_id, principal)
            result = self._correct_once(problem_id, command, principal)
            self._completed_mutations.add(mutation_key)
            return result

    def _correct_once(
        self, problem_id: str, command: dict[str, Any], principal: TrustedPrincipal
    ) -> dict[str, Any]:
        problem = self.get(problem_id, principal)
        current = problem["planRevisions"][-1]
        if command.get("predecessorDigest") != current["canonicalDigest"]:
            raise ProblemPlanningError("STALE_OR_SUPERSEDED_PLAN", 409)
        successor = json.loads(json.dumps(current))
        successor["revision"] += 1
        successor["planRevisionId"] = (
            f"{current['planId']}:revision:{successor['revision']}"
        )
        successor["predecessorRevisionId"] = current["planRevisionId"]
        successor["summary"] = str(command.get("summary") or successor["summary"])
        successor["status"] = "PLAN_REVIEW"
        successor["approvalState"] = "PENDING"
        successor["createdAt"] = _now()
        successor["updatedAt"] = successor["createdAt"]
        successor["correction"] = {
            "reason": command.get("reason"),
            "beforeDigest": current["canonicalDigest"],
        }
        successor.pop("canonicalDigest", None)
        successor["canonicalDigest"] = _digest(successor)
        problem["planRevisions"].append(successor)
        problem["currentPlanRevisionId"] = successor["planRevisionId"]
        problem["updatedAt"] = _now()
        return problem

    def approve(
        self, problem_id: str, command: dict[str, Any], principal: TrustedPrincipal
    ) -> dict[str, Any]:
        problem = self.get(problem_id, principal)
        current = problem["planRevisions"][-1]
        if problem["approval"] is not None:
            raise ProblemPlanningError("PLAN_ALREADY_APPROVED", 409)
        if (
            command.get("planRevisionId") != current["planRevisionId"]
            or command.get("canonicalDigest") != current["canonicalDigest"]
        ):
            raise ProblemPlanningError("STALE_OR_SUPERSEDED_PLAN", 409)
        approval_id = f"approval:{uuid.uuid4()}"
        problem["approval"] = {
            "approvalId": approval_id,
            "planRevisionId": current["planRevisionId"],
            "canonicalDigest": current["canonicalDigest"],
            "principalId": principal.principal_id,
            "approvedAt": _now(),
            "state": "APPROVED",
            "evidence": {
                "evidenceId": f"evidence:{uuid.uuid4()}",
                "type": "HUMAN_PLAN_APPROVAL",
                "planRevisionId": current["planRevisionId"],
                "canonicalDigest": current["canonicalDigest"],
            },
        }
        current["status"] = "APPROVED_AWAITING_DISPATCH"
        current["approvalState"] = "APPROVED"
        current["updatedAt"] = problem["approval"]["approvedAt"]
        problem["status"] = "APPROVED_AWAITING_DISPATCH"
        problem["dispatchBoundary"] = {
            "state": "INERT",
            "resourceReadiness": "PARTIAL",
            "unresolvedGaps": current["capabilityGaps"],
            "prerequisites": [
                "v0.2.2 resource publication",
                "v0.2.3 runtime and execution authority",
            ],
            "reason": "v0.2.1 ends at exact-plan approval; execution is unavailable.",
        }
        self._append_event(
            problem,
            "PLAN_APPROVED",
            evidence_id=problem["approval"]["evidence"]["evidenceId"],
        )
        return problem
