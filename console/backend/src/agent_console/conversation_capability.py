# ruff: noqa: RUF001 -- Business-facing Chinese capability explanations.
"""Evidence-bounded analysis offer; not an oracle for arbitrary user intent."""


def describe(source, observed):
    operations = {op["operation"] for op in observed.get("operations", [])}
    uncertain = observed.get("state") in {
        "READ_UNAVAILABLE",
        "UNVERIFIED",
        "NOT_CONFIGURED",
    }
    missing = (
        []
        if uncertain
        else sorted({"READ_DATA", "ANALYZE_DATA", "RENDER_REPORT"} - operations)
    )
    schema = source["schemaVersion"]
    if schema == "document-review-source.v1":
        label = source.get("title", "文档检查资料")
        criteria = [
            "读取已确认的原文并保留行号依据。",
            "执行中发现规范范围不明确时，在本会话追问并沿用回答继续。",
            "按所选规范核对缺失章节与待补充内容；章节存在不代表技术正确或获准上线。",
        ]
    elif schema == "tabular-diagnostic-source.v1":
        mapping = source["mapping"]
        label = source.get("title", "指标诊断资料")
        criteria = [
            f"按资料中声明的 {mapping['upperBound']} 上限检查 "
            f"{mapping['value']}，只识别严格大于上限的记录。",
            f"按 {'、'.join(mapping['dimensions'])} 分别汇总，"
            f"{mapping['unit']} 不同的记录分开统计。",
            "提供异常记录、原始行和计算依据；缺失或无效值列为资料缺口，不按零处理。",
            "说明观察到的异常与未经验证的原因，不能将统计相关性当作原因证明。",
        ]
    elif schema == "sales-diagnostic-source.v1":
        label = "销售测试资料"
        criteria = [
            "按已确认期间与资料既有口径分析，币种分别核算。",
            "展示汇总、变化和异常明细，并提供可复算的来源依据。",
            "区分数据观察与原因推测，不声称经营改善。",
        ]
    else:
        label = "交付测试资料"
        criteria = [
            "按资料声明的评估日期与交付口径识别异常。",
            "展示供应商与订单明细、来源依据和无法确认的原因。",
        ]
    return {
        "label": label,
        "assessment": {
            "state": (
                "READ_UNAVAILABLE"
                if observed.get("state") == "READ_UNAVAILABLE"
                else "UNVERIFIED"
            )
            if uncertain
            else "MISSING_TOOLS"
            if missing
            else "BOUNDED_ANALYSIS_AVAILABLE",
            "missingOperations": missing,
            "basis": "AUTHORIZED_PUBLISHED_SOURCE_AND_OBSERVED_MEMBER_CONTRACTS",
            "executionReady": False,
            "goalCoverage": "REQUIRES_QUESTION_SPECIFIC_PLANNING",
            "limitations": [
                "仅使用所选测试资料",
                "只读分析，不执行外部业务操作",
                *(
                    []
                    if schema == "document-review-source.v1"
                    else ["原因与改善效果需要进一步证据"]
                ),
            ],
        },
        "completionCriteria": criteria,
    }
