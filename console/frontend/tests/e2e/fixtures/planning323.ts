import type {Semantics} from "../../../src/planning/api";

// Synthetic procurement semantics from the 323 controlled fixture; no execution facts.
export const procurement: Semantics = {
  "schema_version": "planning.v2",
  "scenario": "OVERDUE_PURCHASE_ORDERS",
  "target": {
    "problem": {
      "resource_id": "problem:323-purchase",
      "revision_id": "problem:323-purchase:1",
      "digest": "0462cf1884a2b506d24b4e20df22cebb1099a6328bfac69df16896dda14e5cf0"
    },
    "criteria": {
      "resource_id": "problem:323-purchase",
      "revision_id": "criteria:323:1",
      "digest": "7ae766b4b2e58a2b91d2671ac92f65b956d8ca53fc88e94cec62ffcd9d0df9ab"
    },
    "criterion_revision_ids": [
      "criterion:323-report:1"
    ],
    "expected_problem_version": 3
  },
  "title": "整理延期采购订单清单",
  "business_rules": [
    "2026-09-17 / Asia/Shanghai, 承诺日期严格早于判定日",
    "仅授权范围未关闭未取消且未交量大于零的明细",
    "按来源、公司、订单、明细、分期去重; 冲突与缺日期单列",
    "按供应商和单位汇总, 不跨单位相加"
  ],
  "boundaries": [
    "只读, 不修改订单, 不催交, 不发通知"
  ],
  "effect": "READ_ONLY",
  "stages": [
    {
      "stage_id": "S1",
      "title": "读取快照",
      "task_ids": [
        "T1"
      ]
    },
    {
      "stage_id": "S2",
      "title": "校验与延期识别",
      "task_ids": [
        "T2a",
        "T2b"
      ]
    },
    {
      "stage_id": "S3",
      "title": "汇总与报告",
      "task_ids": [
        "T3a",
        "T3b"
      ]
    }
  ],
  "tasks": [
    {
      "task_id": "T1",
      "title": "读取快照",
      "responsibility": "采购分析与报告",
      "employee_requirement_id": "employee",
      "depends_on": [],
      "inputs": [
        "冻结订单快照"
      ],
      "outputs": [
        "A1"
      ],
      "requirement_ids": [
        "snapshot"
      ],
      "criterion_revision_ids": [
        "criterion:323-report:1"
      ]
    },
    {
      "task_id": "T2a",
      "title": "校验数据",
      "responsibility": "校验与延期识别",
      "employee_requirement_id": "validator",
      "depends_on": [
        "T1"
      ],
      "inputs": [
        "A1"
      ],
      "outputs": [
        "A2"
      ],
      "requirement_ids": [
        "dates"
      ],
      "criterion_revision_ids": [
        "criterion:323-report:1"
      ]
    },
    {
      "task_id": "T2b",
      "title": "识别延期",
      "responsibility": "校验与延期识别",
      "employee_requirement_id": "validator",
      "depends_on": [
        "T2a"
      ],
      "inputs": [
        "A2"
      ],
      "outputs": [
        "A3"
      ],
      "requirement_ids": [
        "overdue"
      ],
      "criterion_revision_ids": [
        "criterion:323-report:1"
      ]
    },
    {
      "task_id": "T3a",
      "title": "供应商汇总",
      "responsibility": "采购分析与报告",
      "employee_requirement_id": "employee",
      "depends_on": [
        "T2b"
      ],
      "inputs": [
        "A3"
      ],
      "outputs": [
        "A4"
      ],
      "requirement_ids": [
        "summary"
      ],
      "criterion_revision_ids": [
        "criterion:323-report:1"
      ]
    },
    {
      "task_id": "T3b",
      "title": "生成报告",
      "responsibility": "采购分析与报告",
      "employee_requirement_id": "employee",
      "depends_on": [
        "T3a"
      ],
      "inputs": [
        "A4"
      ],
      "outputs": [
        "A5"
      ],
      "requirement_ids": [
        "report"
      ],
      "criterion_revision_ids": [
        "criterion:323-report:1"
      ]
    }
  ],
  "requirements": [
    {
      "requirement_id": "employee",
      "kind": "EMPLOYEE",
      "name": "采购分析员",
      "purpose": "承担采购分析与报告职责",
      "required": true,
      "selected": {
        "resource_id": "employee:323-purchase",
        "revision_id": "employee:323-purchase:1",
        "digest": "031597ef12e5e26c67d02a2367b8b8c972fa0a24ff437da1f0f44cbdda752c0d"
      },
      "operation": null,
      "preparation": "真实owner中的已发布测试数字员工, 非企业生产目录"
    },
    {
      "requirement_id": "snapshot",
      "kind": "MCP",
      "name": "采购快照",
      "purpose": "提供授权范围内冻结采购数据",
      "required": true,
      "selected": null,
      "operation": null,
      "preparation": "准备只读采购接口或披露冻结导出替代路线"
    },
    {
      "requirement_id": "validator",
      "kind": "EMPLOYEE",
      "name": "数据校验员",
      "purpose": "校验日期、异常和延期口径",
      "required": true,
      "selected": null,
      "operation": null,
      "preparation": "职责需求待准备, 不创建员工实例"
    },
    {
      "requirement_id": "dates",
      "kind": "SKILL",
      "name": "日期校验",
      "purpose": "检查缺失日期与来源冲突",
      "required": true,
      "selected": null,
      "operation": null,
      "preparation": "尚未选择精确发布版本"
    },
    {
      "requirement_id": "overdue",
      "kind": "SKILL",
      "name": "延期计算",
      "purpose": "按承诺日期与未交数量判断延期",
      "required": true,
      "selected": null,
      "operation": null,
      "preparation": "尚未选择精确发布版本"
    },
    {
      "requirement_id": "summary",
      "kind": "SKILL",
      "name": "供应商汇总",
      "purpose": "按供应商及数量单位汇总",
      "required": true,
      "selected": null,
      "operation": null,
      "preparation": "尚未选择精确发布版本"
    },
    {
      "requirement_id": "report",
      "kind": "SKILL",
      "name": "报告生成",
      "purpose": "整理清单、摘要与异常说明",
      "required": true,
      "selected": null,
      "operation": null,
      "preparation": "尚未选择精确发布版本"
    },
    {
      "requirement_id": "knowledge",
      "kind": "KNOWLEDGE",
      "name": "采购政策",
      "purpose": "可选补充依据",
      "required": false,
      "selected": null,
      "operation": null,
      "preparation": "本例以已确认标准为准"
    }
  ]
};
