# 本体专项阶段0 — 成果与验收证据

日期：2026-11-04（Asia/Shanghai）。状态：基线与架构设计工程交付完成；G2架构决定PENDING；阶段1—2尚未实施。

## 固定基线

- Parent commit：`9df4c7fe95278fd85246abe3645ae7dfc244b485`。
- Parent tree：`8f9afe54ddcf1558734b1c71ae89782d9ad7509b`。
- 独立分支：`codex/ontology-sales-stages-0-2`。
- 初始工作树干净；1626个追踪文件逐个核对Git对象与实际字节。
- [全量基线清单](baseline-manifest.json)包含摘要、Git blob和父工作区未提交差异清单；未纳入并行P08/P10改动。
- [源码归档说明](source-archive.json)保存固定源码归档摘要；归档随用户交付包提供。
- 代码基线为现有研发候选，不是main或发布状态声明。系统Git启动器的本地许可问题已通过调用现有CommandLineTools Git解决，未更改系统许可或设置。

## 当前测试证据

相关5个测试文件覆盖销售、执行准备/绑定、Skill资源仓储和执行授权。

| 执行 | 结果 | 证据 |
| --- | --- | --- |
| 首次无PG配置 | 47 passed / 7 skipped | [原始日志](baseline-tests.log) |
| 独立PG复核 | 54 passed / 0 skipped / 0 failed，5.71秒 | [最终日志](baseline-tests-postgresql.log) |

[测试摘要](test-summary.json)记录候选、范围和环境。PG测试使用独立、临时postgres:15-alpine容器及tmpfs数据，不访问既有研发数据库；验证后容器已停止并移除。本轮没有模型调用、运行准入、原案例重放、共享迁移、服务重启或业务数据写入。

54项测试只证明本次固定旧基线的相关行为，不证明本体能力已实现。未执行全库make check、前端构建或业务浏览器验收：本阶段仅新增设计和证据文件，阶段1—2实现后按适用门禁执行。

## 可评审成果

- [具体架构方案](../../engineering/ONTOLOGY-SALES-01-ARCHITECTURE-DECISION.md)：当前缺口、推荐方案、领域责任、定义模型、权限、API、运行绑定、兼容、迁移、回退和待决定范围。
- [阶段0—2实施计划](../../exec-plans/active/ONTOLOGY-SALES-STAGES-0-2.md)：依赖、路径、顺序、交付及验收。
- [30项验收案例](../../engineering/ONTOLOGY-SALES-ACCEPTANCE.csv)：S01—S12用于阶段1，S13—S30补齐阶段2；全部标记NOT_RUN，防止把规划冒充验证。
- [分支内Registry登记](../../governance/REGISTRY.md)：独立任务与Human门；尚未提交到durable main。

## 阶段0核对

| 项目 | 状态 |
| --- | --- |
| 独立基线、tree和全文件摘要 | PASS |
| 源码归档完整性 | 见delivery-verification.json；交付前逐文件核对 |
| 并行工作隔离 | PASS；原P08/P10所有权不变 |
| 当前针对性基线测试 | PASS；54/54 |
| 具体设计与验收集 | DELIVERED / PROPOSED |
| 架构Human决定 | PENDING |
| 阶段1本体定义发布 | NOT_STARTED |
| 阶段2本体运行闭环 | NOT_STARTED |
| 合并、发布、生产及真实业务接受 | NOT_GRANTED / NOT_CLAIMED |

下一步需对ONTOLOGY-SALES-01选项B作决定。它明确新增业务语义域、权限操作、版本化绑定与执行准备v2，保留旧v1历史和执行责任；任务的普通研发授权继续有效。

## 后续决定（保留上述阶段0历史快照）

用户2026-11-04明确答复“批准选项B，继续阶段1—2”；见human-decision.json。架构状态ACCEPTED，阶段0最终工程门完成。上述PENDING/NOT_STARTED与NOT_RUN均是提交决定时的历史状态，最新进展以实施计划、运营说明和阶段1—2交付证据为准。
