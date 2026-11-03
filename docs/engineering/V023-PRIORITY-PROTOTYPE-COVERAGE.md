# v0.2.3 优先原型页与交付案例对照

核对范围为资源管理 PC 清单中的 9 / 72 页。代码基线为 PR #186 的 db7ad2d8。以下记录可复用的代码与尚需验证的业务操作，未逐页进行真实服务视觉验收。

| 原型 | 实际入口与代码（相对 console/frontend/src） | 已有实现 | 下一项可验收结果 |
|---|---|---|---|
| D04 能力装配 | /digital-employees · digital-employees/EmployeeDefinitionAssembly.tsx | 员工定义与能力成员装配 | 交付案例中逐项对齐阶段、用途、精确版本与缺口 |
| D09 实例分工 | /digital-employees · digital-employees/DigitalEmployeesPage.tsx | 按坐标读取实例、分工和已绑定定义 | 验证同案任务分工及有效期、结束分工影响 |
| D10 任务参与 | /digital-employees · digital-employees/EmployeeWorkParticipation.tsx | 展示 Assignment 和 Placement，页面标明执行、证据和结果未接通 | 从员工进入同案任务并回到原问题 |
| S04 输入输出 | /skills · resources/CapabilityResourceDetails.tsx | 展示操作和资源级输入输出 Schema、类型、必填、说明 | 验证从任务打开的修订与计划引用一致，再核对缺失日期样本 |
| S11 使用追溯 | /skills · resources/SkillWorkbenchPage.tsx、CapabilityResourceDetails.tsx | 已记录的关系、来源修订及摘要 | 将计划声明与真实调用分开呈现，关联同案 Attempt 和产物 |
| W05 节点资源 | /workflow-definitions · workflows/WorkflowSkillOperationBindingEditor.tsx | 精确 Skill 操作、执行器、输入输出及副作用策略绑定 | 按节点核对员工、知识、Skill、多种资源缺口 |
| W11 关联计划 | /work/planning/:proposalId · planning/PlanningPage.tsx | 从计划读取任务、资源需求、计划版本与确认记录 | 验证从 Workflow 特定版本反查同案已确认计划，再返回原问题 |
| W12 运行详情 | /work?problem=…&execution=… · problems/PreparedExecutionPanel.tsx | 有运行、产物、标准评价和人工决定界面 | 取得交付案例真实 Run、Attempt 和产物，按原标准读回结果 |
| A11 实例关联任务 | /agents · resources/AgentTechnicalProjection.tsx；员工任务参与页另有 Placement 坐标 | 定义身份及不可变修订可见；员工页可读取实例放置关联 | 建立 Agent 实例到 Problem、Plan、Run、Task、Attempt 的同案查询 |

本批用户路径从首页“继续已有业务问题”进入可信工作台的问题列表，按当前权限选择案例；在已有计划的任务内打开对应资源需求并返回原问题。资源详情显示计划所引用的信息，实际资源调用需要独立证据。供应商案例真实规划结果、执行授权、Run 和结果验收仍待获得。
