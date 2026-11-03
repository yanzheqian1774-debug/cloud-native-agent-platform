# ruff: noqa: RUF001 -- Chinese user-visible report.
"""Bounded deterministic Skill for the approved isolated synthetic cost case.

No network, model, billing connector, configuration write, or enterprise source.
"""

from decimal import Decimal, InvalidOperation

from .resource_use_domain import canonical_digest
from .skill_executor import SkillExecutorFailure, SkillExecutorResult
from .skill_invocation_domain import ExecutorRevision

OPERATIONS = (
    "READ_DATA",
    "VALIDATE_DATA",
    "SUMMARIZE",
    "ANALYZE_DATA",
    "RECOMMEND",
    "RENDER_REPORT",
)
CONFIGURATION = {
    "schemaVersion": "synthetic-cost-skill.v1",
    "operations": list(OPERATIONS),
    "project": "星河客服",
    "includeTrial": False,
    "currency": "CNY",
    "budget": "8000.00",
    "categories": ["MODEL_API", "COMPUTE"],
    "maxRows": 128,
    "realBusinessConclusion": False,
}


def fail(code):
    raise SkillExecutorFailure(code, outcome_unknown=False)


class SyntheticCostSkillExecutor:
    revision = ExecutorRevision(
        "synthetic-cost-readonly", "1", canonical_digest(CONFIGURATION)
    )

    def invoke(self, invocation_id, operation, inputs, timeout_ms):
        try:
            return self._compute(invocation_id, operation, inputs)
        except SkillExecutorFailure:
            raise
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise SkillExecutorFailure(
                "SYNTHETIC_INPUT_INVALID", outcome_unknown=False
            ) from exc

    def _compute(self, invocation_id, operation, inputs):
        if operation not in OPERATIONS or inputs.get("synthetic") is not True:
            fail("SYNTHETIC_COST_BOUNDARY_REQUIRED")
        dependencies = inputs.get("dependencies", {})
        result = {
            "schemaVersion": "synthetic-cost-output.v1",
            "synthetic": True,
            "operation": operation,
            "sourceSnapshot": inputs["sourceSnapshot"],
            "limitations": [
                "SYNTHETIC_ONLY",
                "NOT_ENTERPRISE_BILLING",
                "REAL_SAVINGS_UNVERIFIED",
            ],
        }
        if operation == "READ_DATA":
            source = inputs.get("source")
            if (
                not isinstance(source, dict)
                or source.get("schemaVersion") != "synthetic-cost-source.v1"
                or source.get("synthetic") is not True
            ):
                fail("SYNTHETIC_SOURCE_REQUIRED")
            rows = source.get("rows")
            if (
                not isinstance(rows, list)
                or not 1 <= len(rows) <= CONFIGURATION["maxRows"]
            ):
                fail("SYNTHETIC_SOURCE_ROWS_INVALID")
            result.update(
                rows=rows,
                periods=source["periods"],
                sourceDigest=canonical_digest(source),
                gaps=source.get("gaps", []),
            )
        elif operation == "VALIDATE_DATA":
            source = self.dependency(dependencies, "READ_DATA")
            valid, excluded, invalid = [], [], []
            seen = set()
            for row in source["rows"]:
                if not isinstance(row, dict):
                    fail("SYNTHETIC_SOURCE_ROW_INVALID")
                identity = row.get("id")
                if not isinstance(identity, str) or not identity or identity in seen:
                    fail("SYNTHETIC_SOURCE_DUPLICATE_OR_MISSING_ID")
                seen.add(identity)
                if (
                    row.get("project") != CONFIGURATION["project"]
                    or row.get("trial") is not False
                    or row.get("category") not in CONFIGURATION["categories"]
                ):
                    excluded.append(identity)
                    continue
                try:
                    if not isinstance(row["amount"], str) or len(row["amount"]) > 20:
                        raise ValueError("bounded decimal string required")
                    amount = Decimal(row["amount"])
                    good = (
                        amount.is_finite()
                        and 0 <= amount <= Decimal("1000000000")
                        and row["currency"] == "CNY"
                        and row["period"] in source["periods"]
                    )
                except (InvalidOperation, KeyError, TypeError, ValueError):
                    good = False
                if not good:
                    invalid.append(identity)
                else:
                    valid.append(
                        {**row, "amount": str(amount.quantize(Decimal("0.01")))}
                    )
            result.update(
                rows=valid,
                excludedIds=excluded,
                invalidIds=invalid,
                periods=source["periods"],
                gaps=source["gaps"],
            )
            if invalid:
                result["limitations"].append("INVALID_ROWS_EXCLUDED")
        elif operation == "SUMMARIZE":
            source = self.dependency(dependencies, "VALIDATE_DATA")
            totals = {}
            for row in source["rows"]:
                period = totals.setdefault(row["period"], {})
                period[row["category"]] = str(
                    Decimal(period.get(row["category"], "0")) + Decimal(row["amount"])
                )
            result.update(
                totals=totals,
                periods=source["periods"],
                gaps=source["gaps"],
                excludedIds=source["excludedIds"],
                invalidIds=source["invalidIds"],
            )
        elif operation == "ANALYZE_DATA":
            summary = self.dependency(dependencies, "SUMMARIZE")
            validated = self.dependency(dependencies, "VALIDATE_DATA")
            result.update(
                totals=summary["totals"],
                periods=summary["periods"],
                budgetCny=CONFIGURATION["budget"],
                comparableMonths=False,
                gaps=summary["gaps"],
                excludedIds=validated["excludedIds"],
                invalidIds=validated["invalidIds"],
            )
            result["limitations"].extend(
                ["PARTIAL_MONTH_NOT_FULL_MONTH", "CAUSAL_ATTRIBUTION_INSUFFICIENT"]
            )
        elif operation == "RECOMMEND":
            analysis = self.dependency(dependencies, "ANALYZE_DATA")
            result.update(
                analysis=analysis,
                recommendations=[
                    {"action": "补齐同口径整月账单及用量证据", "executed": False},
                    {
                        "action": "核对模型调用单价与资源分摊后再评估优化",
                        "executed": False,
                    },
                ],
                verifiedSavingsCny=None,
            )
        else:
            recommendations = self.dependency(dependencies, "RECOMMEND")
            analysis = recommendations["analysis"]
            result.update(
                title="星河客服成本分析 · 隔离合成资料",
                analysis=analysis,
                recommendations=recommendations["recommendations"],
                verifiedSavingsCny=None,
                businessConclusion="UNDETERMINED",
                report="本报告使用隔离合成资料。预算基线为人民币8000元，排除试验项目；"
                "9月1日至20日不能直接与10月整月等同比较。真实费用、原因及节约效果仍需正式证据与人工决定。",
            )
        return SkillExecutorResult(
            True, result, "synthetic-computation:" + invocation_id
        )

    @staticmethod
    def dependency(dependencies, operation):
        matches = [
            value
            for value in dependencies.values()
            if value.get("operation") == operation and value.get("synthetic") is True
        ]
        if len(matches) != 1:
            fail("SYNTHETIC_DEPENDENCY_MISMATCH")
        return matches[0]
