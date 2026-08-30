"""Deterministic untrusted reference generator for bounded planning tests."""

from __future__ import annotations

from collections.abc import Mapping

from agent_console.planning import BusinessQuestion


class SupplierQualityReferenceGenerator:
    """Produce inert supplier-quality candidate data without external calls."""

    generator_id = "reference.supplier-quality"
    generator_version = "v1"

    def generate(self, question: BusinessQuestion) -> Mapping[str, object]:
        is_chinese = question.locale == "zh-cn"

        def localized(chinese: str, english: str) -> str:
            return chinese if is_chinese else english

        objective = (
            f"分析该供应商质量问题并形成可审批、可验证的整改计划: {question.question}"
            if is_chinese
            else (
                "Analyze this supplier-quality problem and create an approvable, "
                f"verifiable corrective plan: {question.question}"
            )
        )
        return {
            "objective": objective,
            "constraints": [
                localized(
                    "仅使用未来任务要求所表达的输入",
                    "Use only inputs represented by future task requirements",
                ),
                localized(
                    "草案阶段不调用提供方、能力、知识或运行环境",
                    "Do not invoke providers, capabilities, knowledge, or runtimes",
                ),
            ],
            "success_criteria": [
                localized(
                    "形成可审查的供应商质量评估",
                    "Produce a reviewable supplier quality assessment",
                ),
                localized(
                    "明确保留验证限制",
                    "Preserve explicit validation limitations",
                ),
            ],
            "assumptions": [
                localized(
                    "提交的问题仅使用经过脱敏的演示数据",
                    "The submitted problem uses sanitized Demo data only",
                )
            ],
            "uncertainties": [
                localized(
                    "初始问题尚未提供已确认的根因",
                    "The initial question does not identify a confirmed root cause",
                )
            ],
            "tasks": [
                {
                    "id": "collect-quality-inputs",
                    "type": "COLLECT",
                    "purpose": localized(
                        "表达所需的供应商质量输入",
                        "Represent the required supplier quality inputs",
                    ),
                    "inputs": [question.request_id],
                    "outputs": ["bounded-quality-input-set"],
                    "dependencies": [],
                    "constraints": [localized("不实时检索", "No live retrieval")],
                    "acceptance_conditions": [
                        localized(
                            "所需输入的业务语义明确",
                            "Required input semantics are explicit",
                        )
                    ],
                    "risk": "LOW",
                    "approval": "HUMAN",
                    "unresolved": [],
                    "ordinal": 0,
                },
                {
                    "id": "analyze-quality-exception",
                    "type": "ANALYZE",
                    "purpose": localized(
                        "分析已表达的供应商质量异常",
                        "Analyze the represented supplier quality exception",
                    ),
                    "inputs": ["bounded-quality-input-set"],
                    "outputs": ["quality-exception-analysis"],
                    "dependencies": ["collect-quality-inputs"],
                    "constraints": [
                        localized(
                            "不调用能力或模型",
                            "No capability or model invocation",
                        )
                    ],
                    "acceptance_conditions": [
                        localized(
                            "分析要求可供审查",
                            "Analysis requirements are reviewable",
                        )
                    ],
                    "risk": "MEDIUM",
                    "approval": "HUMAN",
                    "unresolved": [],
                    "ordinal": 1,
                },
                {
                    "id": "review-quality-plan",
                    "type": "REVIEW",
                    "purpose": localized(
                        "审查有边界的分析计划",
                        "Review the bounded analysis plan",
                    ),
                    "inputs": ["quality-exception-analysis"],
                    "outputs": ["reviewed-quality-plan"],
                    "dependencies": ["analyze-quality-exception"],
                    "constraints": [
                        localized(
                            "人工批准保持为独立步骤",
                            "Human approval remains separate",
                        )
                    ],
                    "acceptance_conditions": [
                        localized(
                            "展示精确的候选计划校验值",
                            "Exact candidate digest is presented",
                        )
                    ],
                    "risk": "MEDIUM",
                    "approval": "HUMAN",
                    "unresolved": [],
                    "ordinal": 2,
                },
            ],
        }
