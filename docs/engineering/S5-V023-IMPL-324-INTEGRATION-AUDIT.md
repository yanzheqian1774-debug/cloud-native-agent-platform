# IMPL-324 当前PR整合预检

2026-09-21 fetch后基线`2e8c1fb`。仅只读比对，尚未整合或关闭来源PR。
机器清单见[pr-audit.json](../evidence/s5/v0.2/s5-v023-impl-324/pr-audit.json)，包含每PR原始改动路径、与main字节相同及不同路径。不同不等于独有：后续需按语义审阅，不能凭数量关闭PR。

| PR | 固定HEAD | 当前事实 | 处理顺序与剩余工作 |
| --- | --- | --- | --- |
| 168 | 388b6e3993fcbd41526cb4038cd8974446980ce0 | OPEN Draft，旧检查成功；与main在isolated_browser_harness及其测试冲突 | 第一资源候选；提取exact详情/能力区别和必需目录，保留双方reporter、诊断与清理断言；旧英文复用面板需按本批中文要求审查，不全量冒充R30 |
| 167 | bb1f821ee0c11e525e8634e0cf1e09db799b828d | OPEN Draft，旧检查成功；组合有冲突，无SQL变更 | 第二资源候选；只接所需来源/预览/中文，核对pypdf与锁文件；不扩大全知识改版 |
| 166 | b0f934e7d5e958e5f8303eb194b100e0a4757c6a | OPEN Draft，旧检查成功；组合有冲突 | 保留独立Workflow价值；本次精确映射路线不强制依赖编辑器 |
| 163 | 141a17ecd34ec3b721e1c8a8ae33277c4b454e42 | 19个来源改动路径中10个当前main字节相同，9个不同；0019同摘要 | 逐项审核剩余模型授权/诊断/文档差异后，提议保留或替代关闭；当前不关闭 |
| 164 | 5a32fbb918a3c30ad50141e8bfbe7613673dc412 | 37个来源改动路径中14个相同、23个不同；0020同摘要 | 保留main已加强可信入口，剩余差异需按语义核对，不回退BFF |
| 170 | 020c1d6eae35c47a418d210b5e982e8d54b03889 | 56个来源改动路径中18个相同、38个不同；0020同摘要 | 保留演进后Problem入口；旧UI不直接覆盖成本同案工作台 |
| 169 | 947a4ca25221541d7e2ff54bee5ab0fa11d6d480 | OPEN Draft；5成功/1失败；execution_postgres/operator main/Registry冲突 | 单独保持Native共存及0021 owner迁移；固定版本连接不代表execute |

## 169失败的实际可见诊断

读取GitHub run 34735543441原失败日志：37 selected/executed，36 passed、1 failed；`WAVE_3B_REAL_SERVICE_JOURNEYS`，`BROWSER_TIMEOUT / TIMEOUT`，actionClass UNKNOWN，定位为测试声明第21行，非确切失败断言。保存的摘要不能证明OpenClaw transport失败。

main相对该候选已增加MCP server closeAllConnections、PC/移动视口焦点及延迟读回的精确断言、finally释放。后续组合验证需保留这些改进和来源诊断；没有当前组合重现前，不声称旧失败已经修复或擅自增加timeout。

## 迁移与回退

[逐文件摘要](../evidence/s5/v0.2/s5-v023-impl-324/migration-audit.json)：163的0019与164/170的0020和main完全相同；169的0021尚未在main，不能占用或重编号。168/167/166本次来源改动无SQL。未运行任何升级。
后续按各domain schema_migrations验证版本/checksum/依赖，特别是execution0008、Native dispatch0022及OpenClaw0021并存；不把全目录顺序执行当升级方案。兼容回退保留新事实并停新writer，禁止覆盖原数据库。

当前仅预检，内容整合、差异逐项处置、组合测试和可评审合并顺序仍待完成。旧绿灯不算324候选CI。
