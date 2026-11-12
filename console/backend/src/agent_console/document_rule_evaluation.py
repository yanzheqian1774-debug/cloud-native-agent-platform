"""Finite document checks with exact rules/source digests and line evidence."""

import json
import re

from .native_document_tools import validate_source
from .ontology_domain import DocumentRulesContent, OntologyError
from .resource_use_domain import canonical_digest

UNKNOWN_MARKERS = ("待确认", "待补充", "未明确", "unknown", "todo", "tbd")


def evaluate_document_rules(content: DocumentRulesContent, source: dict) -> dict:
    docs = validate_source(source)
    if canonical_digest(source) != content.mappings[0].source_digest:
        raise OntologyError("ONTOLOGY_SOURCE_DIGEST_MISMATCH")
    if not any(d["role"] == "POLICY" and d["scope"] == content.scope for d in docs):
        raise OntologyError("DOCUMENT_RULE_SCOPE_UNAVAILABLE")
    submission = next(d for d in docs if d["role"] == "SUBMISSION")
    blocks = []
    current = None
    for line, text in enumerate(submission["text"].splitlines(), 1):
        heading = re.fullmatch(r"##\s+(.+?)\s*", text)
        if heading:
            current = {"title": heading[1], "line": line, "text": text, "body": []}
            blocks.append(current)
        elif current is not None:
            current["body"].append({"line": line, "text": text})

    def evidence(line):
        return {
            "documentId": submission["id"],
            "line": line["line"],
            "text": line["text"],
        }

    findings = []
    for rule in content.rules:
        matches = [b for b in blocks if b["title"] == rule.section]
        status, citations, values = "MISSING", [], []
        if len(matches) > 1:
            status, citations = "CONFLICT", [evidence(b) for b in matches]
        elif matches:
            block = matches[0]
            citations = [evidence(block)]
            if rule.kind == "REQUIRED_SECTION":
                lines = [line for line in block["body"] if line["text"].strip()]
                status = "UNKNOWN" if not lines else "SATISFIED"
                unknown = [
                    line
                    for line in lines
                    if any(m in line["text"].casefold() for m in UNKNOWN_MARKERS)
                ]
                if unknown:
                    status = "UNKNOWN"
                citations += [evidence(line) for line in (unknown or lines[:1])]
            else:
                pattern = re.compile(
                    r"^\s*" + re.escape(rule.field) + r"\s*[:\uFF1A]\s*(.*?)\s*$"
                )
                fields = [
                    (line, pattern.fullmatch(line["text"])) for line in block["body"]
                ]
                fields = [(line, match[1]) for line, match in fields if match]
                if fields:
                    citations += [evidence(line) for line, _ in fields]
                    values = list(dict.fromkeys(value for _, value in fields))
                    known = [
                        value
                        for value in values
                        if value
                        and not any(m in value.casefold() for m in UNKNOWN_MARKERS)
                    ]
                    status = (
                        "CONFLICT"
                        if len(known) > 1
                        else "UNKNOWN"
                        if len(known) != len(values)
                        else "SATISFIED"
                    )
        findings.append(
            {
                "ruleCode": rule.code,
                "ruleName": rule.name,
                "kind": rule.kind,
                "section": rule.section,
                "field": rule.field,
                "status": status,
                "evidence": citations,
                "observedValues": values,
                "absenceCheckedAgainst": canonical_digest(submission)
                if status == "MISSING"
                else None,
            }
        )
    result = {
        "schemaVersion": "document-rule-result.v1",
        "scope": content.scope,
        "rulesDigest": canonical_digest(content.model_dump(mode="json")),
        "sourceDigest": canonical_digest(source),
        "documentId": submission["id"],
        "documentDigest": canonical_digest(submission),
        "documentTitle": submission["title"],
        "findings": findings,
        "businessConclusion": "UNDETERMINED",
        "limitations": [
            "SYNTHETIC_ONLY",
            "EXPLICIT_SECTION_AND_LINE_LABELS_ONLY",
            "SATISFIED_IS_RULE_MATCH_NOT_BUSINESS_CORRECTNESS",
        ],
    }

    if len(json.dumps(result, ensure_ascii=False).encode()) > 128 * 1024:
        raise OntologyError("DOCUMENT_RULE_RESULT_TOO_LARGE")
    return result
