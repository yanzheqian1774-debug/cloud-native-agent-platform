"""Exact published-rule adapter for the existing governed document loop."""

from dataclasses import replace

from agent_runtime.native_loop import digest

from .document_rule_evaluation import evaluate_document_rules
from .native_document_tools import NativeDocumentTools
from .ontology_domain import DocumentRulesContent
from .ontology_execution import DocumentSemanticsBinding


class NativeDocumentRuleTools(NativeDocumentTools):
    def __init__(self, source, reference, content, binding):
        if not isinstance(source, dict):
            raise ValueError("DOCUMENT_RULE_SOURCE_REQUIRED")
        self.rules = DocumentRulesContent.model_validate(content)
        self.binding = DocumentSemanticsBinding.model_validate(binding)
        mapping = self.rules.mappings[0]
        if (
            self.binding.source.model_dump(mode="json") != reference
            or mapping.source != self.binding.source
            or mapping.code != self.binding.mapping_code
            or self.rules.scope != self.binding.scope
        ):
            raise ValueError("DOCUMENT_RULE_BINDING_MISMATCH")
        evaluate_document_rules(self.rules, source)
        super().__init__(source, reference)

    def _tool(self, name):
        original = super()._tool(name)
        if name not in {"review_document", "build_report"}:
            return original
        return replace(
            original,
            revision="2",
            digest=digest(
                {"base": original.digest, "adapter": "published-document-rules.v1"}
            ),
            description=original.description
            + (
                " Apply only the pinned published rules; preserve missing, "
                "unknown and conflict outcomes."
            ),
        )

    def inventory(self):
        return {
            **super().inventory(),
            "ruleBinding": self.binding.model_dump(mode="json"),
            "rules": [r.model_dump(mode="json") for r in self.rules.rules],
        }

    def invoke(self, name, args):
        if name != "review_document":
            return super().invoke(name, args)
        self.validate(name, args)
        document = self.documents[args["documentId"]]
        policy = self.documents[args["policyId"]]
        if document["role"] != "SUBMISSION" or policy["role"] != "POLICY":
            raise ValueError("DOCUMENT_ROLE_MISMATCH")
        if not self.confirmed_scope:
            return {
                "state": "NEEDS_CLARIFICATION",
                "reason": "USER_POLICY_SCOPE_REQUIRED",
                "availableScopes": [self.binding.scope],
            }
        if (
            self.confirmed_scope != self.binding.scope
            or policy["scope"] != self.binding.scope
        ):
            raise ValueError("DOCUMENT_RULE_SCOPE_MISMATCH")
        result = evaluate_document_rules(self.rules, self.source)
        self.reviewed = {
            "scope": self.binding.scope,
            "documentId": document["id"],
            "policyId": policy["id"],
            "ruleBinding": self.binding.model_dump(mode="json"),
            "ruleResult": result,
            "missingSections": [
                f["section"] for f in result["findings"] if f["status"] == "MISSING"
            ],
            "incompleteSections": [
                f["section"]
                for f in result["findings"]
                if f["status"] in {"UNKNOWN", "CONFLICT"}
            ],
        }
        return {
            "sourceSnapshot": self.reference,
            "sourceDigest": digest(self.source),
            **self.reviewed,
        }
