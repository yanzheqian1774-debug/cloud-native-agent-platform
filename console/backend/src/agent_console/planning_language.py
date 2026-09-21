"""Finite business-field language gate, never a universal semantic evaluator."""

import re

from .business_problem_domain import canonical_digest


# Only business prose is inspected. IDs, operation enums, I/O keys, exact owner
# metadata and user-authored input are deliberately outside this projection.
def issues(document):
    fields = []
    for index, value in enumerate(document.get("questions", [])):
        fields.append((["questions", index], value))
    plan = document.get("semantics") or {}
    fields.append((["semantics", "title"], plan.get("title", "")))
    for name in ("business_rules", "boundaries"):
        fields.extend(
            (["semantics", name, i], v) for i, v in enumerate(plan.get(name, []))
        )
    for collection, names in (
        ("stages", ("title",)),
        ("tasks", ("title", "responsibility")),
        ("requirements", ("name", "purpose", "preparation")),
    ):
        for i, item in enumerate(plan.get(collection, [])):
            fields.extend(
                (["semantics", collection, i, name], item.get(name, ""))
                for name in names
            )
    for i, task in enumerate(plan.get("tasks", [])):
        for name in ("inputs", "outputs"):
            for j, text in enumerate(task.get(name, [])):
                # A short graph key is an identity, not business prose.
                if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:-]{0,63}", text):
                    fields.append((["semantics", "tasks", i, name, j], text))
    result = []
    for path, text in fields:
        if not text:
            continue
        prose = re.sub(r"https?://\S+|`[^`]*`", "", text)
        chinese = len(re.findall(r"[\u3400-\u9fff]", prose))
        english = re.findall(r"[A-Za-z]{2,}", prose)
        ordinary = [
            w
            for w in english
            if w
            not in {
                "API",
                "MCP",
                "JSON",
                "SQL",
                "CPU",
                "GPU",
                "RMB",
                "USD",
                "Kimi",
                "Token",
                "tokens",
            }
        ]
        if (chinese == 0 and ordinary) or (
            len(ordinary) >= 5 and len(ordinary) * 2 > chinese
        ):
            result.append(
                {"path": path, "type": "language", "rule": "BUSINESS_CHINESE_REQUIRED"}
            )
    return result[:16]


def report(document):
    found = issues(document)
    return {
        "phase": "BUSINESS_LANGUAGE",
        "error_count": len(found),
        "issues": found,
        "fingerprint": canonical_digest(found),
        "rule_version": "business-zh.v1",
    }
