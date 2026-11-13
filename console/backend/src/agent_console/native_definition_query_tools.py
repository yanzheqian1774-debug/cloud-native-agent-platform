"""Versioned, optional definition lookup over the exact bound document ontology."""

from agent_runtime.native_loop import Tool, digest

from .native_document_rule_tools import NativeDocumentRuleTools


class NativeDefinitionQueryTools(NativeDocumentRuleTools):
    def __init__(self, source, reference, content, binding):
        super().__init__(source, reference, content, binding)
        schema = {
            "type": "object",
            "properties": {"ruleCode": {"type": "string", "maxLength": 64}},
            "required": ["ruleCode"],
            "additionalProperties": False,
        }
        self.tools = (
            *self.tools,
            Tool(
                "query_rule_definition",
                "1",
                digest({"schema": schema, "adapter": "exact-document-rule-query.v1"}),
                (
                    "Read a rule definition and exact sources only when needed. "
                    "Empty ruleCode lists definitions. This is not rule evaluation "
                    "or authorization; review_document evaluates evidence."
                ),
                schema,
                lambda args: self.validate("query_rule_definition", args),
            ),
        )

    def inventory(self):
        value = super().inventory()
        # Do not send every definition and then require a redundant lookup.
        value["rules"] = [{"code": r.code, "name": r.name} for r in self.rules.rules]
        value["definitionQueryAvailable"] = True
        return value

    def validate(self, name, args):
        if name != "query_rule_definition":
            return super().validate(name, args)
        if (
            not isinstance(args, dict)
            or set(args) != {"ruleCode"}
            or not isinstance(args["ruleCode"], str)
            or len(args["ruleCode"]) > 64
        ):
            raise ValueError("DOCUMENT_TOOL_ARGUMENTS")

    def invoke(self, name, args):
        if name != "query_rule_definition":
            return super().invoke(name, args)
        self.validate(name, args)
        rules = [
            r.model_dump(mode="json")
            for r in self.rules.rules
            if not args["ruleCode"] or r.code == args["ruleCode"]
        ]
        return {
            "schemaVersion": "bound-rule-definition-query.v1",
            "state": "FOUND" if rules else "UNKNOWN",
            "ruleBinding": self.binding.model_dump(mode="json"),
            "scope": self.rules.scope,
            "rules": rules,
            "sources": [
                m.model_dump(mode="json")
                for m in self.rules.mappings
                if m.code == self.binding.mapping_code
            ],
            "rulesEvaluated": False,
            "authorizationGranted": False,
        }
