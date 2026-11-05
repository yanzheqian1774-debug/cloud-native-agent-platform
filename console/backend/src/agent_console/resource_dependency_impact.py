# ruff: noqa: E501, RUF001 -- Exact owner SQL and Chinese visibility notes.
"""Bounded permission-filtered projections of existing exact definition references."""

from .authority_contracts import AuthorityError
from .plan_suggestion_domain import ExactReference
from .planning_candidates import OWNERS, require_read
from .workbench_business_problem import OwnerPrincipal


def references(value):
    """Only typed reference shapes; never substring/name similarity as dependency."""
    result = []

    def visit(item):
        if isinstance(item, dict):
            for a, b, d in [
                ("resource_id", "revision_id", "digest"),
                ("resourceId", "revisionId", "digest"),
                ("skillId", "skillRevisionId", "skillDigest"),
            ]:
                if isinstance(item.get(a), str) and isinstance(item.get(b), str):
                    result.append(
                        {
                            "identity": item[a],
                            "revision": item[b],
                            "digest": item.get(d),
                            "kind": item.get("kind"),
                        }
                    )
                    break
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return result


def structural(content, kind):
    if kind == "AGENT":
        return content.get("bindings", {})
    if kind == "WORKFLOW":
        return {
            "runtimeProfile": content.get("runtimeProfile"),
            "tasks": [
                {
                    "references": task.get("references", []),
                    "skillOperationBindings": task.get("skillOperationBindings", []),
                }
                for task in content.get("tasks", [])
            ],
        }
    # Examples, schemas, arbitrary data/documents and prose are never dependencies.
    return {}


def project(call, kind, record):
    c = call.connection
    p = OwnerPrincipal(
        call.context.principal_id,
        call.context.scope.tenant_id,
        call.context.scope.security_domain,
    )
    current = next(
        x
        for x in record["revisions"]
        if x["revisionId"]
        == (record["currentDraftRevisionId"] or record["publishedRevisionId"])
    )
    identity = record["resourceId"]
    nodes = []
    limits = []
    for owner_kind in ("AGENT", "SKILL", "MCP", "KNOWLEDGE", "RUNTIME", "WORKFLOW"):
        table, col, _, _ = OWNERS[owner_kind]
        if not c.execute("SELECT to_regclass(%s) value", (table,)).fetchone()["value"]:
            limits.append(owner_kind + "_OWNER_UNAVAILABLE")
            continue
        rows = c.execute(
            f"SELECT {col} identity,t.record,r FROM {table} t CROSS JOIN LATERAL jsonb_array_elements(t.record->'revisions') r WHERE namespace=%s AND security_domain=%s"
            + (" AND kind=%s" if owner_kind in {"SKILL", "MCP"} else "")
            + f" ORDER BY {col},r->>'revisionId' LIMIT 501",
            (
                p.tenant_id,
                p.security_domain,
                *([owner_kind.lower()] if owner_kind in {"SKILL", "MCP"} else []),
            ),
        ).fetchall()
        if len(rows) > 500:
            limits.append(owner_kind + "_SCAN_LIMIT")
        for row in rows[:500]:
            ref = ExactReference(
                resource_id=row["identity"],
                revision_id=row["r"]["revisionId"],
                digest=row["r"]["digest"].removeprefix("sha256:"),
            )
            try:
                require_read(call.authority, p, owner_kind, ref)
            except AuthorityError:
                continue
            nodes.append(
                {
                    "kind": owner_kind,
                    "identity": ref.resource_id,
                    "revision": ref.revision_id,
                    "digest": ref.digest,
                    "name": row["record"]["name"],
                    "state": row["r"]["state"],
                    "references": references(
                        structural(row["r"]["content"], owner_kind)
                    ),
                }
            )
    if c.execute(
        "SELECT to_regclass('digital_employee_definition.revisions') value"
    ).fetchone()["value"]:
        rows = c.execute(
            "SELECT definition_id,revision_id,digest,record FROM digital_employee_definition.revisions WHERE namespace=%s AND security_domain=%s ORDER BY definition_id,revision_id LIMIT 501",
            (p.tenant_id, p.security_domain),
        ).fetchall()
        if len(rows) > 500:
            limits.append("EMPLOYEE_SCAN_LIMIT")
        for row in rows[:500]:
            ref = ExactReference(
                resource_id=row["definition_id"],
                revision_id=row["revision_id"],
                digest=row["digest"],
            )
            try:
                require_read(call.authority, p, "EMPLOYEE", ref)
            except AuthorityError:
                continue
            nodes.append(
                {
                    "kind": "EMPLOYEE",
                    "identity": ref.resource_id,
                    "revision": ref.revision_id,
                    "digest": ref.digest,
                    "name": row["record"]["role"],
                    "state": "SAVED_REVISION",
                    "references": references(row["record"].get("members", [])),
                }
            )
    else:
        limits.append("EMPLOYEE_OWNER_UNAVAILABLE")
    # Plans remain their own owner. Only authorized exact Plan revisions enter graph.
    rows = c.execute(
        "SELECT plan_id,version,record FROM workflow_planning.plans WHERE namespace=%s AND security_domain=%s ORDER BY plan_id,version LIMIT 501",
        (p.tenant_id, p.security_domain),
    ).fetchall()
    if len(rows) > 500:
        limits.append("PLAN_SCAN_LIMIT")
    for row in rows[:500]:
        try:
            call.authority.require(p, "PLAN", "READ", "plan:v2:" + row["plan_id"])
        except AuthorityError:
            continue
        value = row["record"]
        nodes.append(
            {
                "kind": "PLAN",
                "identity": row["plan_id"],
                "revision": str(row["version"]),
                "name": value.get("title")
                or value.get("semantics", {}).get("objective")
                or "已确认方案",
                "state": "CONFIRMED",
                "references": references(
                    value.get("semantics", {}).get("requirements", [])
                ),
            }
        )
    if c.execute(
        "SELECT to_regclass('execution_authority.run_preparations') value"
    ).fetchone()["value"]:
        rows = c.execute(
            "SELECT p.workflow_run_id,p.digest,p.record,g.record->>'state' state FROM execution_authority.run_preparations p LEFT JOIN execution_authority.prepared_run_progress g USING(namespace,security_domain,workflow_run_id) WHERE p.namespace=%s AND p.security_domain=%s ORDER BY p.workflow_run_id LIMIT 501",
            (p.tenant_id, p.security_domain),
        ).fetchall()
        if len(rows) > 500:
            limits.append("RUN_SCAN_LIMIT")
        for row in rows[:500]:
            try:
                call.authority.require(
                    p,
                    "EXECUTION",
                    "READ",
                    "governed-execution:prepared:" + row["digest"],
                )
            except AuthorityError:
                continue
            nodes.append(
                {
                    "kind": "RUN",
                    "identity": row["workflow_run_id"],
                    "revision": row["digest"],
                    "name": "已准备执行",
                    "state": row["state"] or "PREPARED_NOT_CALLED",
                    "references": references(row["record"].get("participants", [])),
                }
            )
    target_kind = kind.upper()
    frontier = {
        (identity, current["revisionId"]): {
            "distance": 0,
            "targetRevision": current["revisionId"],
            "versionRelation": "CURRENT_VERSION",
        }
    }
    # All actual pinned revisions of this resource family are distinct roots.
    for revision in record["revisions"]:
        frontier[(identity, revision["revisionId"])] = {
            "distance": 0,
            "targetRevision": revision["revisionId"],
            "versionRelation": "CURRENT_VERSION"
            if revision["revisionId"] == current["revisionId"]
            else "OTHER_VERSION",
        }
    incoming = []
    seen = set()
    for _ in range(6):
        added = False
        for node in nodes:
            key = (node["identity"], node["revision"])
            if key in seen or node["identity"] == identity:
                continue
            matches = [
                (r, frontier[(r["identity"], r["revision"])])
                for r in node["references"]
                if (r["identity"], r["revision"]) in frontier
            ]
            if not matches:
                continue
            link, parent = min(matches, key=lambda x: x[1]["distance"])
            if parent["distance"] >= 6:
                continue
            entry = {
                k: node[k] for k in ["kind", "identity", "revision", "name", "state"]
            }
            entry.update(
                distance=parent["distance"] + 1,
                targetRevision=parent["targetRevision"],
                versionRelation=parent["versionRelation"],
                via={"identity": link["identity"], "revision": link["revision"]},
                automaticUpgrade=False,
            )
            if parent["distance"] == 0:
                expected = next(
                    x["digest"].removeprefix("sha256:")
                    for x in record["revisions"]
                    if x["revisionId"] == link["revision"]
                )
                if (
                    link.get("digest")
                    and link["digest"].removeprefix("sha256:") != expected
                ):
                    entry["versionRelation"] = "DIGEST_MISMATCH"
            frontier[key] = {
                "distance": entry["distance"],
                "targetRevision": entry["targetRevision"],
                "versionRelation": entry["versionRelation"],
            }
            seen.add(key)
            incoming.append(entry)
            added = True
        if not added:
            break
    outgoing = []
    for ref in references(current["content"]):
        child = next(
            (
                n
                for n in nodes
                if n["identity"] == ref["identity"] and n["revision"] == ref["revision"]
            ),
            None,
        )
        outgoing.append(
            {
                **ref,
                "readable": child is not None,
                "name": child["name"] if child else None,
            }
        )
    declarations = [
        x for x in current["content"].get("dependencies", []) if isinstance(x, str)
    ]
    return {
        "outgoing": outgoing,
        "unresolvedDeclarations": declarations,
        "incoming": incoming,
        "visibility": "AUTHORIZED_OWNER_REVISIONS_ONLY",
        "complete": False,
        "limitations": [
            "权限范围内的可读定义；不可见定义不计数",
            "未解析的字符串声明不推断为版本依赖",
            "最多六层关联；不自动升级、改派或重跑",
            *limits,
        ],
        "coveredOwners": [
            "AGENT",
            "SKILL",
            "MCP",
            "KNOWLEDGE",
            "RUNTIME",
            "WORKFLOW",
            "EMPLOYEE",
            "PLAN",
            "RUN",
        ],
        "targetKind": target_kind,
    }
