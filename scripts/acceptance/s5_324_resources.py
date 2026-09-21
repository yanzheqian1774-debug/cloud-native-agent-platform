"""Prepare only the four necessary resource drafts through their existing owners.

Defaults to read-only inventory. --prepare appends drafts as an engineering actor;
it never reviews, publishes, grants, confirms a plan, or starts execution.
"""

import argparse
import hashlib
import json
from contextlib import ExitStack
from pathlib import Path

import psycopg
from agent_console.agent_definition_postgres import PostgresAgentDefinitionRepository
from agent_console.agent_definition_service import AgentDefinitionService
from agent_console.agent_definition_service import _content as normalize_agent_content
from agent_console.knowledge_lifecycle_service import KnowledgeLifecycleService
from agent_console.knowledge_postgres import PostgresKnowledgeRepository
from agent_console.persistence_bootstrap import migration_recorded
from agent_console.prepared_resource_bundle import resource_content
from agent_console.runtime_profile_postgres import PostgresRuntimeProfileRepository
from agent_console.runtime_profile_service import RuntimeProfileService
from agent_console.skill_mcp_postgres import PostgresSkillMcpRepository
from agent_console.skill_mcp_service import SkillMcpService
from agent_console.workbench_prepared_resources import TABLES, bind_service, reference
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
ACTOR = "agent:s5-324-resource-preparer"
NAMES = {
    "skill": "S5-324 隔离合成成本只读技能",
    "runtime": "S5-324 Native 隔离只读运行配置",
    "knowledge": "S5-324 明确标注的合成成本资料",
    "agent": "S5-324 合成成本核验职责",
}
OWNERS = (
    (
        "skill",
        PostgresSkillMcpRepository,
        SkillMcpService,
        "0002_skill_mcp_lifecycle.sql",
    ),
    (
        "runtime",
        PostgresRuntimeProfileRepository,
        RuntimeProfileService,
        "0007_workflow_runtime_profiles.sql",
    ),
    (
        "knowledge",
        PostgresKnowledgeRepository,
        KnowledgeLifecycleService,
        "0003_knowledge_operations.sql",
    ),
    (
        "agent",
        PostgresAgentDefinitionRepository,
        AgentDefinitionService,
        "0001_agent_definition_lifecycle.sql",
    ),
)


def prepare(connection, services, namespace, security_domain, *, write=False):
    content = resource_content()
    if write:
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"S5-V023-IMPL-324:resources:{namespace}:{security_domain}",),
        )
    result = []
    for kind, service in services.items():
        service = bind_service(service, connection)
        scope = service.scope(namespace, security_domain)
        table, _ = TABLES[kind]
        found = connection.execute(
            f"SELECT record FROM {table} WHERE namespace=%s AND security_domain=%s "
            "AND record->>'name'=%s" + (" AND kind='skill'" if kind == "skill" else ""),
            (namespace, security_domain, NAMES[kind]),
        ).fetchall()
        if len(found) > 1:
            raise ValueError("RESOURCE_DRAFT_AMBIGUOUS")
        record = found[0]["record"] if found else None
        if record is None and write:
            args = (scope, "skill", ACTOR) if kind == "skill" else (scope, ACTOR)
            record = service.create(*args, NAMES[kind], content[kind])
            if kind == "knowledge":
                record = record["knowledge"]
        if record is None:
            result.append({"kind": kind, "state": "MISSING"})
            continue
        selected = record.get("currentDraftRevisionId") or record.get(
            "publishedRevisionId"
        )
        revision = next(
            (r for r in record["revisions"] if r["revisionId"] == selected), None
        )
        if revision is None:
            raise ValueError("RESOURCE_DRAFT_CHANGED_REQUIRES_REVIEW")
        if kind == "knowledge":
            actual = revision["content"]["documents"][0]["contentDigest"]
            expected = hashlib.sha256(content[kind]["content"].encode()).hexdigest()
        else:
            actual, expected = revision["content"], content[kind]
            if kind == "agent":
                expected = normalize_agent_content(expected)
        if actual != expected:
            raise ValueError("RESOURCE_DRAFT_CONTENT_CONFLICT")
        identity = record[
            {
                "skill": "resourceId",
                "runtime": "runtimeProfileId",
                "knowledge": "knowledgeId",
                "agent": "definitionId",
            }[kind]
        ]
        result.append(
            {
                "kind": kind,
                "identity": identity,
                "revisionId": revision["revisionId"],
                "digest": revision["digest"],
                "state": revision["state"],
                "aggregateVersion": record["aggregateVersion"],
                "target": reference(kind, identity, revision["revisionId"]),
                "queryReference": "|".join((kind, identity, revision["revisionId"])),
            }
        )
    return {
        "session": "S5-V023-IMPL-324",
        "namespace": namespace,
        "securityDomain": security_domain,
        "resources": result,
        "publishedByThisCommand": False,
        "executionStarted": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    runtime = json.loads(args.runtime_file.read_text())
    database_url = runtime["databaseUrl"]
    with ExitStack() as stack:
        services = {}
        for kind, repository, service, migration in OWNERS:
            repo = repository(
                database_url,
                migration_path=ROOT / "console/backend/migrations" / migration,
            )
            stack.callback(repo.pool.close)
            if (
                args.prepare
                and kind == "knowledge"
                and not migration_recorded(repo, "knowledge_operation", 1)
            ):
                repo.migrate()  # normal owner activation, no invented ledger checksum
            repo.compatibility()
            services[kind] = service(repo)
        with psycopg.connect(database_url, row_factory=dict_row) as connection:
            if not args.prepare:
                connection.execute("SET TRANSACTION READ ONLY")
            result = prepare(
                connection,
                services,
                "s5-323-demo",
                "isolated-real-demo",
                write=args.prepare,
            )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "states": [r["state"] for r in result["resources"]],
            }
        )
    )


if __name__ == "__main__":
    main()
