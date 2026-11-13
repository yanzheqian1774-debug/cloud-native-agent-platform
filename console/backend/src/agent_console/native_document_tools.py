"""Read-only Markdown evidence tools, independent of tabular diagnostics."""

import re

from agent_runtime.native_loop import Tool, digest, snapshot


def validate_source(source):
    if (
        source.get("schemaVersion") != "document-review-source.v1"
        or source.get("synthetic") is not True
    ):
        raise ValueError("DOCUMENT_SYNTHETIC_SOURCE_REQUIRED")
    docs = source.get("documents")
    if not isinstance(docs, list) or not 2 <= len(docs) <= 12:
        raise ValueError("DOCUMENT_BOUNDS")
    if len({d.get("id") for d in docs}) != len(docs):
        raise ValueError("DOCUMENT_IDENTITIES")
    total = 0
    for d in docs:
        if not all(
            isinstance(d.get(k), str) and d[k].strip() for k in ("id", "title", "text")
        ) or d.get("role") not in {"SUBMISSION", "POLICY"}:
            raise ValueError("DOCUMENT_FORMAT")
        if d["role"] == "POLICY" and (
            not isinstance(d.get("scope"), str)
            or not d["scope"].strip()
            or not sections(d["text"])
        ):
            raise ValueError("DOCUMENT_POLICY_REQUIRED")
        total += len(d["text"])
    if total > 20000 or sum(d["role"] == "SUBMISSION" for d in docs) != 1:
        raise ValueError("DOCUMENT_BOUNDS")
    scopes = [d["scope"] for d in docs if d["role"] == "POLICY"]
    if len(set(scopes)) != len(scopes) or source.get("confirmedScope") not in [
        None,
        *scopes,
    ]:
        raise ValueError("DOCUMENT_SCOPE_INVALID")
    return docs


def sections(text):
    result = {}
    current = None
    for line, value in enumerate(text.splitlines(), 1):
        match = re.fullmatch(r"##\s+(.+?)\s*", value)
        if match:
            current = match[1]
            if current in result:
                raise ValueError("DOCUMENT_DUPLICATE_SECTION")
            result[current] = {"line": line, "heading": value, "body": []}
        elif current:
            result[current]["body"].append({"line": line, "text": value})
    return result


def review(source, document_id, policy_id):
    docs = {d["id"]: d for d in validate_source(source)}
    document, policy = docs[document_id], docs[policy_id]
    if document["role"] != "SUBMISSION" or policy["role"] != "POLICY":
        raise ValueError("DOCUMENT_ROLE_MISMATCH")
    submitted, required = sections(document["text"]), sections(policy["text"])
    findings = []
    for title, p in required.items():
        item = submitted.get(title)
        content = "\n".join(x["text"] for x in item["body"]).strip() if item else ""
        status = (
            "MISSING"
            if item is None
            else "INCOMPLETE"
            if not content
            or any(x in content.casefold() for x in ["todo", "tbd", "待补充", "待确认"])
            else "PRESENT_NOT_VALIDATED"
        )
        findings.append(
            {
                "section": title,
                "status": status,
                "requirement": {
                    "documentId": policy_id,
                    "line": p["line"],
                    "text": p["heading"],
                    "body": p["body"],
                },
                "evidence": None
                if item is None
                else {"documentId": document_id, **item},
                "absenceCheckedAgainst": digest(document) if item is None else None,
            }
        )
    return {
        "scope": policy["scope"],
        "documentId": document_id,
        "policyId": policy_id,
        "documentDigest": digest(document),
        "policyDigest": digest(policy),
        "findings": findings,
        "missingSections": [x["section"] for x in findings if x["status"] == "MISSING"],
        "incompleteSections": [
            x["section"] for x in findings if x["status"] == "INCOMPLETE"
        ],
        "businessConclusion": "UNDETERMINED",
        "limitation": (
            "Section completeness only; present text is not technica"
            "l correctness or deployment authorization."
        ),
    }


class NativeDocumentTools:
    def __init__(self, source, reference):
        self.source, self.reference = snapshot(source), snapshot(reference)
        self.documents = {d["id"]: d for d in validate_source(source)}
        self.confirmed_scope = source.get("confirmedScope")
        self.reviewed = None
        self.tools = tuple(
            self._tool(n)
            for n in [
                "list_documents",
                "read_document",
                "search_documents",
                "review_document",
                "build_report",
            ]
        )
        self.answer_schema = {
            "type": "object",
            "properties": {
                "reportDigest": {"type": "string"},
                "scope": {"type": "string"},
                "missingSections": {"type": "array", "items": {"type": "string"}},
                "incompleteSections": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "reportDigest",
                "scope",
                "missingSections",
                "incompleteSections",
            ],
            "additionalProperties": False,
        }

    def _tool(self, name):
        properties = {}
        if name == "read_document":
            properties = {"id": {"type": "string", "enum": list(self.documents)}}
        elif name == "search_documents":
            properties = {"query": {"type": "string", "minLength": 1, "maxLength": 100}}
        elif name == "review_document":
            properties = {
                "documentId": {
                    "type": "string",
                    "enum": [
                        d["id"]
                        for d in self.documents.values()
                        if d["role"] == "SUBMISSION"
                    ],
                },
                "policyId": {
                    "type": "string",
                    "enum": [
                        d["id"]
                        for d in self.documents.values()
                        if d["role"] == "POLICY"
                    ],
                },
            }
        schema = {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }
        descriptions = {
            "list_documents": (
                "List document roles and policy scopes; scope must come "
                "from user, never infer it."
            ),
            "read_document": "Read exact Markdown lines with citations.",
            "search_documents": "Find literal text with document and line references.",
            "review_document": (
                "Check submission sections against the policy for the US"
                "ER-confirmed scope. Ask a clarification first when scop"
                "e is unconfirmed."
            ),
            "build_report": (
                "Create cited completeness report from actual review. FI"
                "NISH must copy its completionAnswer exactly."
            ),
        }
        return Tool(
            name,
            "1",
            digest(
                {
                    "name": name,
                    "schema": schema,
                    "implementation": "markdown-section-review.v1",
                }
            ),
            descriptions[name],
            schema,
            lambda args: self.validate(name, args),
        )

    def validate(self, name, args):
        expected = {
            "read_document": {"id"},
            "search_documents": {"query"},
            "review_document": {"documentId", "policyId"},
        }.get(name, set())
        if set(args) != expected or any(
            not isinstance(v, str) or not v.strip() for v in args.values()
        ):
            raise ValueError("DOCUMENT_TOOL_ARGUMENTS")
        if name == "read_document" and args["id"] not in self.documents:
            raise ValueError("DOCUMENT_NOT_FOUND")
        if name == "search_documents" and len(args["query"]) > 100:
            raise ValueError("DOCUMENT_QUERY_BOUNDS")
        if name == "review_document" and any(
            args[k] not in self.documents for k in expected
        ):
            raise ValueError("DOCUMENT_NOT_FOUND")

    def apply_confirmed_scope(self, evidence):
        """Owner-projected original intent, not a synthetic native answer."""
        scope = evidence["scope"] if evidence is not None else None
        if scope is not None and scope not in {
            d["scope"] for d in self.documents.values() if d["role"] == "POLICY"
        }:
            raise ValueError("DOCUMENT_CONFIRMED_SCOPE_UNAVAILABLE")
        self.confirmed_scope = scope

    def question_contracts(self):
        from .native_question_contracts import scope_contracts

        return scope_contracts(self)

    def resolve_question_contract(self, contract_id):
        from .native_question_contracts import resolve_contract

        return resolve_contract(self, contract_id)

    def record_typed_answer(self, contract, verified_interpretation):
        from .native_question_contracts import consume_interpretation

        consume_interpretation(self, contract, verified_interpretation)

    def record_answer(self, answer, *, question=None):
        from .native_scope_answer import confirmed_answer_scope

        self.confirmed_scope = confirmed_answer_scope(
            answer,
            [d["scope"] for d in self.documents.values() if d["role"] == "POLICY"],
            question=question,
            previous=self.confirmed_scope,
            policy_labels=[
                (d["scope"], label)
                for d in self.documents.values()
                if d["role"] == "POLICY"
                for label in (d["title"], d["text"].splitlines()[0].lstrip("# "))
            ],
        )

    def inventory(self):
        """Already-loaded source metadata; not evidence of reading document lines."""
        return {
            "sourceSnapshot": self.reference,
            "sourceDigest": digest(self.source),
            "confirmedScope": self.confirmed_scope,
            "documents": [
                {k: d.get(k) for k in ["id", "title", "role", "scope"]}
                for d in self.documents.values()
            ],
        }

    def invoke(self, name, args):
        self.validate(name, args)
        provenance = {
            "sourceSnapshot": self.reference,
            "sourceDigest": digest(self.source),
        }
        if name == "list_documents":
            return self.inventory()
        if name == "read_document":
            d = self.documents[args["id"]]
            return {
                **provenance,
                "documentId": d["id"],
                "documentDigest": digest(d),
                "lines": [
                    {"line": i, "text": t}
                    for i, t in enumerate(d["text"].splitlines(), 1)
                ],
            }
        if name == "search_documents":
            return {
                **provenance,
                "matches": [
                    {"documentId": d["id"], "line": i, "text": t}
                    for d in self.documents.values()
                    for i, t in enumerate(d["text"].splitlines(), 1)
                    if args["query"].casefold() in t.casefold()
                ][:30],
            }
        if name == "review_document":
            policy = self.documents[args["policyId"]]
            if not self.confirmed_scope or policy.get("scope") != self.confirmed_scope:
                return {
                    "state": "NEEDS_CLARIFICATION",
                    "reason": "USER_POLICY_SCOPE_REQUIRED",
                    "availableScopes": [
                        d["scope"]
                        for d in self.documents.values()
                        if d["role"] == "POLICY"
                    ],
                }
            self.reviewed = review(self.source, args["documentId"], args["policyId"])
            return {**provenance, **self.reviewed}
        if not self.reviewed:
            return {"state": "REVIEW_REQUIRED"}
        result = {**provenance, **self.reviewed}
        result["reportDigest"] = digest(result)
        result["completionAnswer"] = {
            k: result[k]
            for k in ["reportDigest", "scope", "missingSections", "incompleteSections"]
        }
        return result

    def verify(self, context, answer):
        reports = [
            o["output"]
            for o in context["observations"]
            if o["kind"] == "TOOL_RESULT" and o["tool"] == "build_report"
        ]
        if not self.reviewed or not reports:
            return {"passed": False, "missing": ["CITED_REVIEW_REQUIRED"]}
        expected = self.invoke("build_report", {})
        reads = {
            o["arguments"]["id"]
            for o in context["observations"]
            if o["kind"] == "TOOL_RESULT" and o["tool"] == "read_document"
        }
        if not {expected["documentId"], expected["policyId"]} <= reads:
            return {"passed": False, "missing": ["READ_SELECTED_DOCUMENTS"]}
        return {
            "passed": reports[-1] == expected
            and answer == expected["completionAnswer"]
            and expected["scope"] == self.confirmed_scope,
            "businessAcceptance": False,
        }
