"""Deterministic untrusted reference generator for bounded planning tests."""

from __future__ import annotations

from collections.abc import Mapping

from agent_console.planning import BusinessQuestion


class SupplierQualityReferenceGenerator:
    """Produce inert supplier-quality candidate data without external calls."""

    generator_id = "reference.supplier-quality"
    generator_version = "v1"

    def generate(self, question: BusinessQuestion) -> Mapping[str, object]:
        return {
            "objective": "Assess the bounded supplier quality question",
            "constraints": [
                "Use only inputs represented by future task requirements",
                "Do not invoke providers, capabilities, knowledge, or runtimes",
            ],
            "success_criteria": [
                "Produce a reviewable supplier quality assessment",
                "Preserve explicit validation limitations",
            ],
            "assumptions": ["Input evidence will be bound by a future package"],
            "uncertainties": ["No knowledge source is selected in Package 1"],
            "tasks": [
                {
                    "id": "collect-quality-inputs",
                    "type": "COLLECT",
                    "purpose": "Represent the required supplier quality inputs",
                    "inputs": [question.request_id],
                    "outputs": ["bounded-quality-input-set"],
                    "dependencies": [],
                    "constraints": ["No live retrieval"],
                    "acceptance_conditions": ["Required input semantics are explicit"],
                    "risk": "LOW",
                    "approval": "HUMAN",
                    "unresolved": [],
                    "ordinal": 0,
                },
                {
                    "id": "analyze-quality-exception",
                    "type": "ANALYZE",
                    "purpose": "Analyze the represented supplier quality exception",
                    "inputs": ["bounded-quality-input-set"],
                    "outputs": ["quality-exception-analysis"],
                    "dependencies": ["collect-quality-inputs"],
                    "constraints": ["No capability or model invocation"],
                    "acceptance_conditions": ["Analysis requirements are reviewable"],
                    "risk": "MEDIUM",
                    "approval": "HUMAN",
                    "unresolved": [],
                    "ordinal": 1,
                },
                {
                    "id": "review-quality-plan",
                    "type": "REVIEW",
                    "purpose": "Review the bounded analysis plan",
                    "inputs": ["quality-exception-analysis"],
                    "outputs": ["reviewed-quality-plan"],
                    "dependencies": ["analyze-quality-exception"],
                    "constraints": ["Human approval remains separate"],
                    "acceptance_conditions": ["Exact candidate digest is presented"],
                    "risk": "MEDIUM",
                    "approval": "HUMAN",
                    "unresolved": [],
                    "ordinal": 2,
                },
            ],
        }
