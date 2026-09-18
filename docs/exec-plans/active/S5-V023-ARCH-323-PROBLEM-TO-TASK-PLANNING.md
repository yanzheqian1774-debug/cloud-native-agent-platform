# S5-V023-ARCH-323 — 问题到任务规划：主线架构与首个可执行切片

> 当前授权以第 10 节为准；第 1–9 节保留设计阶段历史，原“实施未授权”不再代表当前状态。

## 1. 本次交付与权威

- Session：`S5-V023-ARCH-323`；Human 已授权有界架构设计、只读实现核对和实施准备。
- 状态：`REVIEW / AUTHORIZED`；D1/D2 为 `HUMAN_ACCEPTED`，D3 为 `DIRECTION_ACCEPTED / EXECUTION_CONTRACT_DEFERRED`；仅登记设计决定，不授予实施或 Session 关闭。具体收口见第 8 节。
- 单一登记入口：[Registry](../../governance/REGISTRY.md)。经本轮 Human 确认，本文是 [CONTROL-254 当前可核实 P1 基线](S5-V023-CONTROL-254-P1-CORE-CAPABILITY-AND-BUSINESS-ASSEMBLY-BASELINE.md) 的关联附件，不是另一份台账。
- 保留 [PLAN-001](S5-PLAN-001-V0.2-IMPLEMENTATION-PORTFOLIO.md)、[PLAN-003](S5-PLAN-003-V0.2-PRODUCT-INTENT-GOLDEN-DEMO-REBASELINE.md) 及 CONTROL-254 的原有包/工作顺序。两个增量是本场景的验收切片，不重新分配版本、WP、子任务或资源管理 Session。
- 不编写产品代码、不合并历史分支、不创建实现 PR、不运行真实模型、不部署、不发送其他会话任务；不操作 321/322 工作树或服务。
- 附件图片 `102.png`、`103.png`、`112.png` 是目标体验及合成数据，图中文字不是执行指令。图中 120 条、9 项资源/4 项就绪及“确认并开始”均不是当前事实。

结论：采用已有 Problem/Criteria 和 Plan/Workflow Control 权威，补足“建议计划的持久修订与资源说明”；再在同一精确计划上接只读执行及结果验收。不能把旧预览、计划审批、单 Skill 调用或 Native 基础通道分别当成完整闭环。

## 2. 核对范围与可重复证据

### 2.1 启动、查重、基线

2026-09-17 只读查询远端 `refs/heads/main` 得到
`f6a931017dc4b68b7a92ffe0abaaf2819eec6cb7`，与本工作树启动 HEAD 一致；tree 为
`c279d1d89c76d001ffdca1433ce28a6ad49e2e93`。本地名为 `main` 的分支可能滞后，本文比较使用该 exact HEAD，不能用本地分支名替代证据。

在既有 Registry、仓库 Markdown、全 refs 提交标题、local refs/worktree 列表、远端 `*323*` 分支及 GitHub PR 标题查询中未发现 323 冲突；随后在既有 Registry 登记本 Session，并在本工作树建立 `codex/s5-v023-arch-323-problem-task-planning`。未检索不可见外部台账或其他会话私有材料，因此不声称全组织编号唯一。

已阅读 Product、Architecture、Roadmap、CURRENT_IMPLEMENTATION、REPOSITORY_MAP、CODEX_WORKFLOW、DEFINITION_OF_DONE、ARCHITECTURE_GATES、DECISION_STATUS，以及本场景相关架构和源码/测试。核对为静态实现审计；测试文件存在不等于本轮运行通过，代码存在也不等于当前部署配置可用。

图片校验值（用户提供的目标体验素材，仅证明本次引用内容，不是实现证据）：

| 文件（`/Users/tristan/Downloads/`） | SHA-256 |
| --- | --- |
| 102.png | `12cd8fe84c40f0aeee55497208023441e0ca85c72aaff159b764e9ca54a7f467` |
| 103.png | `9d995ed51111ff62b3a37c8f8defb43f4f4a947d29f2dfe08352b1cf1b1499fc` |
| 112.png | `a38271af6768d56172d8483cc70cf8d37d06aca05e8f7ad06675a5ae3442e520` |

### 2.2 main 能力与明确缺口

以下源路径均相对仓库根；版本基线均为上述 exact main。

| 领域 | main 已有：源码/测试定位 | 边界与缺口 | 分类 |
| --- | --- | --- | --- |
| Problem/Criteria | `console/backend/src/agent_console/business_problem_domain.py`：BusinessProblemRevision、SuccessCriterionRevision、SuccessCriteriaSetRevision、PlanProblemBinding；`business_problem_application.py`；`business_problem_postgres.py`；migration `0013` | 精确修订、digest、CAS、授权、标准集合、计划绑定已有。不能把用户聊天文本或旧预览 ID 自动当成这些对象 | CURRENT 基础 |
| 持久计划入口 | `business_problem_schemas.py` PreparePlan/DecidePlan；`business_problem_application.py` prepare/approve/read_plan；`business_plan_postgres.py`；`workflow_control_domain.py` PlanRecord；`test_business_problem_api_postgres.py` 的 prepare/approve/restart/replay 与错误资源测试 | 从已有 Workflow Definition 转换显式计划；要求一个 Employee Definition/Instance/Assignment；不是任意模型建议计划；approve 不调用 start | CURRENT 基础，新增计划路径缺失 |
| 旧规划体验 | `problems/service.py:ProblemPlanningService`、`problems/ProblemPlanningPage.tsx`、`test_problem_planning_v021.py` | `_problems`/streams 为进程内 dict；已有模型/知识驱动预览、任务展示、修订和审批体验，但重启丢失且不执行。不得作为持久主线或复制其 authority | CURRENT 预览 |
| 确定性规划/角色匹配 | `planning.py` PlanningEngine、TaskRequirement、拓扑/循环校验、精确批准与 successor；`matching.py` RoleRequirement/ROLE_GAP；`test_planning.py`、`test_matching.py` | 可复用解析、稳定排序和匹配原则；`planning_generator.py` 是 supplier-quality reference generator。未建立本采购案例的持久建议计划/跨种类资源可用性快照 | CURRENT 内部基础 |
| 模型接入 | `model_governance.py`、`model_binding_resolution.py`、`model_governance_postgres.py`、migration `0019`；`draft_assistance.py`、migration `0023/0024` | 精确 model binding 及 pre-Problem draft assistance 已有。后者绑定 draft context/turn，不能悄悄改为 confirmed-Problem plan generation，不能虚构 Attempt | CURRENT；规划调用语义待决定 |
| Workflow | `workflow_definition_schemas.py` WorkflowTask/WorkflowContent；`workflow_definition_service.py`、`workflow_definition_postgres.py`；`workflow_control_application.py` 及测试 | 有 taskId、dependsOn、I/O 字符串、资源 refs、Skill operation binding、retry/timeout/failure policy。`workflow_definition_resolver.py:resolve_workflow_reference` 当前只解析 RUNTIME_PROFILE/SKILL，其余 kind 返回 False；schema 可表达 MCP/Knowledge 不代表发布校验可支持。无页面阶段分组和逐阶段数字员工字段；普通 I/O 字符串不等于可执行产物映射 | CURRENT 定义/控制基础 |
| 数字员工 | `digital_employee_definition.py`、`digital_employee_application.py`、`digital_employee_postgres.py`、migration `0014`；`test_digital_employee_application.py` | Definition/Instance/Assignment、exact composition、发布/实例化分离已有；一个已发布员工引用多个资源不表示这些资源归其所有。当前 Plan 入口和 Run 的单 Assignment 形态不能直接表达多员工 Task 路由 | CURRENT；多员工路由缺失 |
| Skill/MCP | `skill_mcp_service.py`/`skill_mcp_transport.py` 管理与发现；`skill_invocation_application.py`/`skill_executor.py`/`governed_execution.py`；migration `0016/0017`；`test_governed_execution_api_postgres.py` | 托管 READ_ONLY HTTP Skill、persist-before-effect、replay、unknown 恢复基础已有；管理 MCP discovery/test 不等于本场景 Attempt-bound 采购查询。没有核实到采购专用发布资源、真实端点授权和数据 | CURRENT 基础；场景资源明确未获证明 |
| Knowledge | `knowledge_lifecycle_service.py`、`knowledge_attempt_retrieval.py`、`knowledge_citations.py`、`knowledge_postgres.py`、`knowledge_qdrant.py`；对应 retrieval/restart/authorization 测试 | 已有文本生命周期、派生向量索引、exact snapshot、引用及 Attempt 绑定。采购日期口径知识是否存在/发布/可读未知；本案例不强制检索，不把常识当知识引用 | CURRENT；业务知识待准备 |
| 执行与 Native | `execution_application.py` start/retry；`native_dispatch_application.py` queue；`operator/src/agent_operator/native_dispatch_reconciler.py`；migration `0022`；`test_native_dispatch_application.py` | 有 durable queue、claim/fencing、Kubernetes/Native 通道和 technical completion。当前 start 的 Run identity seed 含 task_id：逐 task 调用会产生不同 Run，不能冒充一个多阶段 Run。既有 `operator/src/agent_operator/workflow_controller.py` 已有 Kubernetes Workflow 依赖就绪/跳过调度，`execution_coordinator.py` 已有单 Task Native/Capability 协调；缺的是与本产品 Plan/Assignment/PG Evidence 链接通的同 Run 编排，不是重写通用调度器 | CURRENT 基础；产品同 Run 接线缺失 |
| Evidence/Outcome | `resource_use_application.py`/`resource_use_postgres.py`；`execution_application.py` completion；`workflow_control_application.py` terminal outcome 保护 | 已有实际使用、调用和技术完成事实。ARCH-264 的完整 SuccessCriteriaEvaluationService/Human Confirmation/业务 Outcome 主链未在本次定向源码核对中发现；Knowledge Evaluation 不是业务标准评估 | CURRENT 技术基础；业务验收仅设计 |
| 浏览器可信入口 | `workbench_business_problem.py`、`workbench_bff.py`、`workbench_owner_authorization.py`、`business_problem_continuation.py` | 复用 trusted session、CSRF、exact grant、owner adapter、事务及 creator continuation。不得绕回开发默认身份，也不扩造 IAM | CURRENT |

### 2.3 未合并候选及已选择接收的历史成果

远端分支 SHA 与 GitHub PR head 在本轮核对一致。下表通过 `git show <sha>:<path>`、相对 exact main 的差异及源码读取判断；未 checkout、merge 或运行候选环境。历史验收记录仅归属于原候选，不作为本轮测试结果。

| 成果 / exact candidate | 当前载体 | 源码核对与可复用范围 | 不可推导的能力 |
| --- | --- | --- | --- |
| 308 `141a17ecd34ec3b721e1c8a8ae33277c4b454e42` | PR #163 OPEN | main 中 `model_governance.py`、`model_binding_resolution.py`、`model_governance_postgres.py` 三个 blob 与候选逐一相同；319 已定向接收所需基础。先复用 main，不再整体导入 308 | PR 未合并不代表符号未实现；基础模型绑定不表示规划用途和采购场景已授权 |
| 311 `b0f934e7d5e958e5f8303eb194b100e0a4757c6a` | PR #166 OPEN | `WorkflowRevisionDesigner.tsx`、`workflowDesignerModel.ts`、Canvas/NodeForm：依赖图、节点表单、按 taskId 编辑、后端 DTO 保存读回；`workflow-visual-designer.spec.ts`。main 没有这组新增设计器 | 不含新 backend、执行、阶段状态或多员工权威；布局拖动不是依赖修改。可选复用 UI，不阻塞增量一的计划卡片 |
| 312 `bb1f821ee0c11e525e8634e0cf1e09db799b828d` | PR #167 OPEN | `knowledge_document_parser.py` 与 Knowledge Workbench：有界 PDF/DOCX 文本预览、真实位置/来源、现有发布检索；新增 parser 不在 main | 非采购订单数据适配器，不保存原始二进制，不是原文件存储/QA 完整生命周期；本案例可不用该新增解析器 |
| 313 `388b6e3993fcbd41526cb4038cd8974446980ce0` | PR #168 OPEN | `CapabilityCenterDirectory.tsx` 读取既有 list 数据、详情及 Skill/MCP 复用操作 UI，源码变更为 frontend。可复用目录/详情导航与 exact revision 展示 | 没有新增规划资源解析器或 Attempt MCP 执行；管理测试不授予执行权限。原候选还明确记录可信 ingress 接线债务，集成时重新核对 |
| 314 `947a4ca25221541d7e2ff54bee5ab0fa11d6d480` | PR #169 OPEN | `production_transport.py`、`binding_observer.py`、`openclaw_binding_application.py`、migration `0021`：预检、持久 binding 及只读恢复观察 | `execute/observe_execution` 明确 EXECUTION_UNSUPPORTED，start/stop/replace 仍 lifecycle unsupported；不能选作本例执行路线，也不能把后续 recovery batch 漏判为完全没有实现 |
| 315/316/317 | PR #171/#172/#173 MERGED，合并落点 `6f3e174087c5132b2fc5c5d1e20492fdc2b68ddc` | Native handoff、可信 preparation/employee 组合已经在 main，按当前源码复用 | Registry 的历史 Draft 状态未同步；本轮只在 323 记录差异，不改历史 Session，不因合并宣称业务到 Native 的全链完成 |
| 319/320 | main 含 #179/#180 的成果，当前 HEAD 是 #180 merge | `draft_assistance.py`、Kimi 适配/截止时间/恢复基础及主问题入口可定向复用 | 不读取或修改 321/322 候选，不假设其 UI/Problem 能力已进入 main；增量一从已提交 exact Problem 开始 |

历史实现不重开、不整体合并。后续如选择接收候选，只在新的获授权实施边界内以精确来源和文件级 diff 审查接收；不能覆盖 main 的后续 BFF、授权或恢复修改。

## 3. 核心对象和边界

架构依据：ARCH-011（建议、Task/匹配与确定性校验）、ARCH-018（domain-owned PostgreSQL）、ARCH-019（执行层次）、ARCH-208（Plan/批准/更正）、ARCH-258（Problem/Criteria）、ARCH-259（MCP trust）、ARCH-263（Skill slot）、ARCH-264（结果验收）、ARCH-266（实际资源使用）、ARCH-300（可信入口）及 IMPL-276 composition addendum。这些权威继续有效；D1/D2 已由本 Session Human 接受；D3 方向已接受，执行细节留在增量二前收口（第 8 节）。

```text
BusinessProblemRevision + SuccessCriteriaSetRevision
                    │ exact IDs / digests
                    ▼
PlanProposalRevision ─── Validation / ResourceResolutionSnapshot
                    │ one exact Human plan confirmation
                    ▼
PlanRecord + ApprovalDecision（确认计划，不启动）
                    │ authorized execution admission, recheck resources
                    ▼
Workflow Run → Task Run → Attempt → Placement / Runtime / Agent Instance
                    │                   └→ Resource Invocation / Resource Use
                    ▼
terminal Run + Evidence snapshot → Criteria Evaluation → Human Confirmation
                                                   → successor Business Outcome
```

`PlanProposalRevision`、`ResourceResolutionSnapshot`、阶段分组/分工和 admission 等新增名称属于本轮内部设计名称：D1/D2 按 Human 决定收口，execution admission 细节仍待增量二前收口；均不代表现有接口、CRD 或已实现 public Contract。

| 对象 | Owner / 核心绑定 | 不变式 |
| --- | --- | --- |
| Problem / Criteria | 既有 Product domain；Problem revision/digest；独立 Criteria Set revision/digest；有序 Criterion revisions | 不使用 latest；标准包含规则、evaluator version、Evidence requirements。改变目标/范围/标准创建 successor，旧批准不适用新内容 |
| 建议与 Plan | 现有 planning/Workflow Control owner 边界；proposal stable ID + revision + digest + predecessor；正式 PlanRecord 继续拥有批准/执行关联 | 存规范化的有限业务计划内容；模型 raw prompt/response 不持久化。proposal 不能假扮已批准 Plan；同一建议确认后有明确 Plan linkage，不复制另一套权威 |
| 阶段与 Task | proposed 阶段展示分组，成员是 exact taskId；TaskRequirement/Workflow task 保留不可变语义 | 阶段不是 Kubernetes Task，也不是 Attempt；第一例只用线性依赖。重排/删依赖/I/O/资源改变语义需 successor；显示折叠/布局不产生修订 |
| 分工 | 计划里 role requirement → exact Employee Definition revision；执行前另解析 Instance 与 Assignment | 职责不是资源所有权。采购分析员可复用在读取和报告两个阶段；数据校验员独立职责。没有实际 Definition 就显示角色缺口，不能用名字制造员工实例 |
| Skill/MCP/Knowledge/Workflow | 各资源自身 domain；独立维护、验证、发布；计划仅保存引用及使用目的 | 多阶段/多员工可以引用同一 revision；不自动复制、归属员工或自动生产资源。员工 composition 是引用关系；Skill executor 内部调用 MCP 也需单独记录实际来源与调用链 |
| 实例与执行 | Execution owner，遵守 Assignment → Run → Task Run → Attempt → Placement 的既有身份 | 实例和 Placement 不在模型建议时创建；Plan approval ≠ Instance readiness ≠ execution start。多员工 Task binding 方向已接受，详细执行关系仅在增量二前收口；增量一不创建或改写 Run/Assignment |
| Evidence / Evaluation / Confirmation | Execution facts；ARCH-264 evaluator、Human governance、Product Outcome 分别负责 | 配置/匹配/就绪不等于调用；技术成功不等于解决。只有 exact terminal Run 能形成业务 Outcome；Human 不同意则不标记已解决 |

### 3.0 D1 已接受方案：唯一权威、确认与兼容边界

建议采用 versioned typed Plan envelope：保持现有 explicit-plan v1 的非空 Workflow/Instance/Assignment 前置条件及历史读取完全不变；新增 planning v2 的 typed records 由同一 Workflow Control owner 管理，不把新字段塞入旧接口任意 JSON，不改变旧记录身份。

| 记录 | 最小字段与关系 | 写入条件 |
| --- | --- | --- |
| ProposalRevision | scope、proposalId/revision/digest、predecessor、exact Problem/CriteriaSet、stage/task requirements、role requirements、selected exact refs 或 unresolved requirement、I/O contracts、边界、generator invocation reference | 服务端通过结构和支持集合校验后保存；即使资源未齐仍为不可执行建议 |
| Plan v2 semantic revision | planId/version/digest、source proposal revision/digest、同一份被确认的规范化语义内容、predecessor、validation snapshot reference | 与 exact ApprovalDecision 在同一 owner transaction 建关联；resource readiness 是另一个维度，不能把未齐计划标 execution-eligible |
| ResourceResolutionSnapshot | exact proposal/Plan、按 requirement 的 authorized owner facts、checkedAt/high-water、reason classifications | 可重新查询并追加；原来选定资源的版本不随查询变更，历史 snapshot 不修改 |
| ExecutionAdmission | exact approved Plan/digest、exact published Workflow/Task mapping、selected Instance/Assignment/Placement references、fresh eligibility/authorization basis、idempotent Run link | **仅增量二**；所有 required exact refs 齐备并校验，不能承载任意模型脚本。对已确认语义的确定性物化不新设用户决定；更改资源选择、职责、数据范围或规则则回到 successor/确认 |

建议计划 PR1 以 `P1/C1 → [S1:{T1}, S2:{T2a,T2b}, S3:{T3a,T3b}]` 固定语义；每个 Task 以 stable taskId 引用第 4 节职责、I/O、资源需求。确认产生 `Plan v2/ApprovalDecision`，执行尚为“未开始”。如果当时只有缺口，没有 exact 资源选择，后续补选会形成新的可执行语义 revision，确认前清楚展示差异；不会把原来“确认待准备”解释成允许任意替换资源。该额外确认仅因批准内容改变发生，不是每次健康刷新或准备项更新都确认。

Human 已接受本方案，未选择“资源齐备后才确认”的缩减路线。下列规则是该决定的实施准备细化，不授予本轮编码或迁移：

- **唯一写入权威**：现有 planning owner 产生不可变 ProposalRevision；Workflow Control owner 独占正式 Plan revision、ApprovalDecision 和 proposal→Plan 确认关联。Problem/Criteria 与资源仍由原 domain 独占。前端、模型、资源目录及 invocation 都不能写 Plan approval；proposal 的状态只投影正式确认关联，不另存一套可独立批准的真假值。
- **唯一语义关系**：每个正式 Plan revision 精确引用一个 source ProposalRevision/digest；一个 scoped proposal revision 最多产生一个确认后的 Plan revision。proposal 中的内容是建议来源，Plan 的规范化确认快照是后续业务批准的唯一依据，两者通过 schema version、source digest 和 canonical semantic digest 证明内容一致。Plan digest 包含 exact Problem/Criteria、阶段/Task、职责、已选资源或明确缺口、I/O 和边界；ApprovalDecision 只绑定该 Plan ID/version/digest。proposal 不能替代正式 Plan，旧建议或模型结果不能覆盖它。
- **原子确认**：服务端先验证 trusted actor/owner grants，再在同一 PostgreSQL owner UoW 内核对 expected proposal/Problem/Criteria 版本、校验结果及精确源 digest；一次性保存 Plan revision、ApprovalDecision、确认关联、CAS 更新与幂等结果。全部提交后才返回“计划已确认”。任一失败全量 rollback，不得出现有批准无计划、有计划无确认关联的半成品。不同 key 并发确认同一 proposal 由唯一约束收敛至原关联；同 key/同 payload 返回原结果，异 payload fail closed。无跨 provider 调用的数据库事务。
- **修订**：语义调整新建 ProposalRevision，保留 predecessor；确认后创建同一稳定 Plan ID 的下一不可变 revision、对应新 ApprovalDecision 和 successor link。旧 revision/批准保留，仅通过追加关联标识当前有效链头；不把旧批准复制到新 digest。首次确认竞争、successor CAS 冲突返回稳定冲突并读回，不自动以新版本重试。纯健康 observation、展开/折叠和只读刷新不触发语义修订或新确认。
- **兼容**：explicit-plan v1 的 PreparePlan/DecidePlan、非空 Workflow/Instance/Assignment、授权、失败码和历史读取保持原样；planning v2 用显式版本化 typed reader/writer 和适配入口。先部署兼容 reader，再启用新 writer；不得将 v2 缺口转换成 v1 虚拟 ID、nullable 占位或执行资格。旧 reader 不静默按 v1 解释 v2；回滚停新 writer并保留新记录，不能删历史。迁移编号和具体私有路由在后续单一 G1 实施计划查重固定，不重新分配产品版本。
- **资格分离**：允许 required 资源缺失时确认正式待准备计划；“已确认”仅指语义批准。增量一根本不创建 Run/Attempt/Assignment/Placement，不把这种计划投到现有 execution start；执行资格与 D3 详细契约留在增量二。


### 3.1 每阶段引用的最小内部契约（提案）

每个 Task 声明 `taskId`、职责/输入/输出、依赖 task IDs、成功标准 IDs、只读边界及可执行单元；每个资源使用声明：

- `kind + resourceId + revisionId + digest`；`purpose`；required/optional；`operation` 或 tool identity/schema digest（适用时）。
- `inputContractRef`/`outputContractRef` 和 I/O mapping：固定参数、前驱产物 ID/字段/版本；类型不匹配、未产出字段、循环/悬空依赖均拒绝。
- Skill：operation + executor revision/config digest + READ_ONLY class；Workflow：revision/digest、taskId、Runtime Profile exact ref；MCP：endpoint revision、tool discovery snapshot、tool/schema digest、connection/trust/credential-reference 验证；Knowledge：document revision、published/index snapshot、引用用途及 citation identity。
- 对不存在的资源，只保存 `requirementId`、kind、需求和缺口原因；不创建假的 resource ID/revision/digest。可选无引用必须明确 `NOT_REQUIRED` 和原因。
- ResourceResolutionSnapshot：由服务器从授权后的 owner ports 查询，带 snapshot ID/digest、checkedAt、源版本/high-water、适用 scope、原因分类。名称命中只能候选；发布资格、精确 revision、schema、trust/connection、授权及运行兼容性分项核实。
- 计划语义 digest 绑定选定 exact refs、I/O、职责、目标、只读边界；即时健康等 observation 通过独立 snapshot 关联，健康刷新不修改 Plan 内容。执行前再次检查，旧快照不授予未来可用性。

建议 UI 状态 `MATCHED / MISSING / UNAVAILABLE / NOT_VERIFIED / NOT_REQUIRED` 为**派生说明**，不是新增资源生命周期。授权失败使用受控的“不允许访问或不可用”，不得借缺口信息泄露资源是否存在。未查询实时目录时只能 NOT_VERIFIED，不能计为就绪。

### 3.2 确认、调整与持久读回

1. 输入为已确认的 exact Problem/Criteria；缺必需业务参数时集中补问，已回答的不重复问。
2. 模型仅输出受限结构建议；系统按大小/schema/支持集合/依赖/类型/资源/版本/授权/只读边界校验。模型的“资源已就绪”字段不采信；不执行模型提供的任意 URL、脚本或工具指令。
3. 建议、有限澄清结果、校验和资源缺口应可持久读回；本轮建议最多 32 Task/128 dependency、沿用规划 parser 的输入界限，再以持久契约测试固定。
4. 一次关键确认汇总目标、标准、计划、职责、资源状态、边界和缺口。增量一文案“确认计划”，响应必须给 exact Plan identity/version/digest/approval，刷新从服务器 GET；不得进入“执行中”。
5. required 资源缺失可以保存建议并按已接受 D1 确认待准备计划；它不具备 execution admission 资格。不能向现有 PreparePlan 填虚拟 Instance/Assignment 绕过校验。
6. 目标、范围、日期口径、资源语义版本、输入快照或重要执行边界变更产生 successor 并重新确认；仅刷新状态/布局/可见信息不新增确认。失效批准保留历史，不静默套到 successor。
7. 请求带 expected version 与 scoped idempotency key；同 key 同 payload 返回同一结果，异 payload 冲突。提交成功但响应丢失时读回/重放原命令，不重新生成计划。
8. 同一计划资源全部就绪后，增量二独立“开始只读执行”命令保留必要执行授权；一个已披露明确含执行的动作可以承载所需授权校验，不再叠加纯形式确认框。本例不在确认计划后自动启动，也不在资源恢复时偷偷启动。

### 3.3 接口关系及建议修改位置

既有 BFF `PREFIX` 以 `workbench_bff.py` 为准，下表用相对后缀，避免与 internal Bearer URL 混用。

| 操作 | 既有权威入口 / 新增提案 | 提交与读回 / 边界 |
| --- | --- | --- |
| 问题/标准读写 | BFF `/problems/{id}`、`/success-criteria`、`/problems/{id}/criteria-sets`；owner 内部 `/api/internal/v0.2.3/business-problems/...` | 复用 owner authorization、revision/digest、集合成员独立 READ |
| 建议/必要补问 | **拟新增** planning owner application 的 propose/clarify/read；不复用 pre-Problem target identity | 绑定 exact Problem/Criteria 和 proposal revision；Model Governance 解析模型，schema/rule validator 决定结果；D2 先行 |
| 资源解析 | **拟新增** bounded resolver/read snapshot；复用 `matching.py` 和资源 owner ports | 授权先于 list/lookup/count；只返回可见资源；补齐当前 Workflow resolver 不支持的 MCP/Knowledge owner resolution，不能只扩大 schema 枚举；不调用 MCP 业务查询来证明“匹配” |
| 保存/确认计划 | 已有 BFF `/problems/{id}/plans`、`/plans/{id}?version=N`、`/plans/{id}/approvals`；新路径遵循 D1 | 旧 PreparePlan/DecidePlan 保持兼容；additive typed repository/UoW，proposal 与 Plan linkage 原子提交 |
| 改计划 | 复用 `workflow_control_application.py` CORRECT_PLAN 思路及 immutable predecessor；新 proposal successor 读回 | 不盲调用要求现有暂停 Run 的 APPROVE_AND_CONTINUE 来确认尚未执行计划 |
| 执行 admission/状态 | 内部 `/api/internal/v0.2.3/executions` 现为单 READ_ONLY Skill；拟补可信 BFF 与同 Run coordinator | 身份、授权、资源 fresh check → durable intent → actual effect；Native queue 只是 QUEUED，不是 RUNNING |
| 产物与验收 | 复用 Execution Evidence/Resource Use readers；拟补 ARCH-264 typed evaluation/confirmation/outcome service/API | 终态与 exact Evidence snapshot 校验；不使用 Knowledge Evaluation 冒名替代 |

## 4. 首个完整计划样例：整理延期采购订单清单

这是**设计样例，尚不可执行**。符号 P1/C1/PR1、R1 等只为本文交叉引用，不是假造的数据库 ID 或 digest。真实实例化必须由后端返回精确身份；所有采购专用资源当前标记 NOT_VERIFIED，未证明的不能发布为 MATCHABLE。

### 4.1 业务输入与统计口径

- Problem P1：整理所有供应商尚未完成的采购订单明细，输出延期清单、供应商摘要和数据异常说明；不修改订单，不催交，不发通知。
- 样例判定日 `2026-09-17`，业务时区 `Asia/Shanghai`；`asOf=2026-09-17T10:00:00+08:00` 是期望快照时间，实际读取后必须记录 source snapshot ID/version、extractedAt、sourceAsOf、scope/filter digest、schema version、内容 digest、分页完整性。实际快照偏差影响结论时补问/新修订，不谎称在 10:00 已读取。
- 数据粒度：`sourceSystem + companyId + purchaseOrderId + lineId + scheduleLineId`（无分期时明示不适用）。同一订单多明细不误计多个订单。输入至少有 supplierId、status、promisedDate、outstandingQuantity、unit、sourceRowRef/sourceRevision；来源只提供 ordered/delivered/cancelled 数量时，必须固定 `outstanding=ordered-delivered-cancelled`、精度与单位口径再计算。
- 范围：所有授权范围内供应商、未关闭/未取消且 outstanding > 0 的 schedule line。无法访问全部供应商时不能标“所有供应商”；应说明实际覆盖范围，目标变化需确认。
- 延期：可解析的 promisedDate（业务日期）严格早于 2026-09-17 且 outstanding > 0；当天到期不算延期，日历天 `asOfDate-promisedDate` 为延期天数。时间戳先按源 schema 的时区规则转业务日期；不猜测不明时区。
- 汇总：按 supplierId 分组；输出延期 schedule-line 数、去重订单数、按单位分组的未交数量、最大延期天数。不跨单位累加，不引入币种/金额口径；供应商名缺失保留 ID，禁止按近似名称合并。
- Knowledge 非强制：默认采用本次已确认 Criteria 规则；若企业要求采购政策作依据，须增加 exact published Knowledge revision/snapshot，不把模型回忆当作规则来源。

### 4.2 角色和资源清单

| 符号 | 需求 / 所有者 | 本例用途与输入→输出 | 当前状态 / 准备或替代 |
| --- | --- | --- | --- |
| E1 | 数字员工：采购分析员；Employee domain | 读取 S1、汇总 S3；共享同一 Definition revision，可按获批路由复用 Instance | NOT_VERIFIED；查已发布职责覆盖，不能因角色名字相同就选中 |
| E2 | 数字员工：数据校验员；Employee domain | 校验与延期判断 S2 | NOT_VERIFIED；独立职责。缺失时报告；仅在 E1 的真实发布职责覆盖且 Human 接受分工变化后可复用 E1，不假扮两个员工 |
| R1 | MCP 采购快照只读查询；MCP domain | scope/asOf/page token → complete immutable order snapshot manifest + bounded rows | NOT_VERIFIED；需真实 endpoint/trust/tool/schema/只读授权。替代：用户提供带来源和摘要的冻结导出快照；这是输入路线变化，要披露并确认，不自动生成 MCP |
| R2 | Skill 日期与数据校验；Skill domain | R1 snapshot → valid rows + exceptions + row trace map | NOT_VERIFIED；需受治理 deterministic operation/executor/schema；复用已存在等价资源优先 |
| R3 | Skill 延期计算；Skill domain | valid rows + exact criteria → delayed/not-delayed partitions + counts | NOT_VERIFIED；计算口径在 Criteria，不由模型临场决定 |
| R4 | Skill 供应商汇总；Skill domain | delayed rows → supplier summary | NOT_VERIFIED；不同单位分桶，订单 distinct 规则固定 |
| R5 | Skill 报告生成；Skill domain | partitions + exceptions + summary + manifest → bounded structured report + references | NOT_VERIFIED；先用确定性 renderer，报告文字不能新增事实；大文件存储/原始文件管理不在本切片 |
| R6 | Workflow Definition + Native Runtime Profile；各自 owner | T1→T2a→T2b→T3a→T3b 的 exact definition / runtime 约束 | NOT_VERIFIED 场景配置；Native 基础已有，不意味着当前资源配置就绪；不依赖 314 |
| K0 | Knowledge（可选） | 企业采购日期政策→有来源的口径解释 | NOT_REQUIRED；仅在业务政策要求时纳入，revision 和 index snapshot 必须固定 |
| H1 | Human 结果验收者 | terminal Run + Evaluation/Evidence →确认或不通过 | 沿用现有授权机制；不是数字员工实例 |

“供应商协同员”和“供应商档案查询”为图 112 的可选后续增强，本例不纳入 required 集合、不分配任务、不阻塞只读清单。资源去重按 kind+ID+revision+digest，不能因两阶段引用同一 Skill 计两项就绪资源。

### 4.3 阶段、依赖与产物

一个页面阶段可含多个 Task，每个 Attempt 仍至多一个托管 Skill。下面 Task 分解是实施提案；现有 single-task start 不能直接执行整张表。

| 页面阶段 / 执行 Task | 责任角色 | 依赖 / 资源 | 输入→交付物 | 阶段完成条件 |
| --- | --- | --- | --- | --- |
| S1 读取快照 / T1 read-snapshot | E1 | 起点；R1、R6 | 固定范围/asOf → A1 snapshot manifest、bounded rows、读取 Evidence | 分页完备、授权范围明确、schema/digest/来源可读回；只获取了部分分页则不能算完成 |
| S2 校验 / T2a validate | E2 | T1；R2、R6 | A1 → A2 valid rows / exceptions / lineage | 每个源行可追踪；日期/数量/状态/主键异常分类；保留所有排除依据 |
| S2 延期识别 / T2b classify | E2 | T2a；R3、R6 | A2 + C1 → A3 delayed/not-delayed/unknown partitions | 严格日期边界、数量口径正确，异常不混入“未延期” |
| S3 供应商汇总 / T3a aggregate | E1 | T2b；R4、R6 | A3 → A4 supplier summary | 明细与摘要 reconciliation 一致；数量按单位分组 |
| S3 汇总报告 / T3b render-report | E1 | T3a，引用 A1/A2/A3；R5、R6 | A1–A4 → A5 清单、摘要、异常、覆盖和限制 | 报告各数字关联到源行集与算法/Criteria 版本，报告 digest 固定 |
| S4 验收 / 非新的 execution Task | H1，系统 evaluator | exact terminal Run + A1–A5 + C1 + Evidence snapshot | Evaluation → Human decision → Business Outcome | 满足下列 Criteria 且 Human 确认；无需为验收再创建空 Attempt |

T1 的 MCP invocation 需补正式 Attempt-bound 适配；不把管理测试调用当 T1。若采用已有 Skill executor 作查询 adapter，必须明确它调用 R1 的关系及 MCP 实际使用证据，不能绕过 MCP trust/credential authority。无可核实适配时本路线 BLOCKED_RESOURCE，不自动换源。

A1–A5 是拟议的有界产物类型：Execution domain 保存允许的有限结构内容/摘要、digest 和 source refs；精确 schema/大小限制需在实施计划固定并测试。Evidence 只保存脱敏、bounded 事实与授权引用，不存原始 provider payload 或整份敏感采购数据。超界需报告 UNSUPPORTED/输入范围调整，不能静默截断或引入 blob 服务。

### 4.4 标准 C1、异常与可演算样例

Criteria Set C1 包含以下不可变 criterion revisions（evaluator 为本例确定性 v1 实现提案）：

| Criterion | 度量/验收 | 所需证据 |
| --- | --- | --- |
| C1a 输入覆盖 | schema、source refs、分页/范围完整性可证；每个输入记录可追溯 | A1、source acquisition Evidence |
| C1b 分类守恒 | 输入行 = 重复被排除行 + 范围外行 + 异常行 + 可判定行；可判定行 = 延期 + 未延期，各分组不重叠 | A2/A3、row mapping、rule version |
| C1c 延期准确 | 所有延期行 promisedDate < asOfDate 且 outstanding > 0；临界日不算；缺日期不推测 | A3 与 C1 digest |
| C1d 汇总一致 | supplier 分组总行数等于延期行数；distinct 订单和 unit 桶规则可复算 | A3/A4 |
| C1e 报告与边界 | A5 同时有清单、摘要、异常/局限及来源；无订单写入或通知调用 | A5、actual Resource Use/Evidence snapshot |
| C1f Human 验收 | 人工基于 exact Evaluation/Evidence 判断交付是否满足目标；不同意不能解决问题 | append-only Human Confirmation |

缺失/无效承诺日期列入 `UNKNOWN_DATE`，不算延期也不算未延期；负数、非数值、单位不明列为 `INVALID_QUANTITY`；主键缺失/相同 key 不同内容为 `SOURCE_CONFLICT`。完全相同 key+revision+digest 的重复记录可确定性去重，并记录重复数；冲突记录隔离，不擅自挑“最新”。缺 supplier 名称但有 ID 可继续；缺 supplier ID 的记录归异常分区，报告另列未归属数据，不计入正常供应商汇总。名称缺失但 ID 存在只是非阻断 warning，不再重复计入异常分区。正常记录可以完成分析，结论必须带不完整性；异常影响目标达成时 C1a/C1f 不得自动通过。

以 5 个**合成**不同明细验证预期（单位均 EA、未关闭；日期为空时记异常）：

| 行 | 供应商 / 订单 | promisedDate | outstanding | 预期 |
| --- | --- | --- | --- | --- |
| L1 | A / PO1 | 2026-09-15 | 4 | 延期 2 天 |
| L2 | A / PO1 | 2026-09-17 | 3 | 未延期，当天到期 |
| L3 | B / PO2 | 缺失 | 2 | UNKNOWN_DATE |
| L4 | B / PO3 | 2026-09-16 | 0 | 范围外（已无未交数量） |
| L5 | A / PO4 | 2026-09-10 | 1 | 延期 7 天 |

预期报告：延期 2 条、2 个不同订单，供应商 A 共 5 EA、最大延期 7 天；未延期 1 条；异常 1 条；范围外 1 条；`5=0+1+1+3` 且 `3=2+1`。这些不是执行结果，仅作为未来 deterministic test 的 oracle。

### 4.5 失败、无数据与恢复入口

| 情况 | 真实状态/展示 | 恢复入口 |
| --- | --- | --- |
| 没有授权可见资源或目录不可读 | 不泄露存在性；NOT_VERIFIED/不可用，不能伪造 MISSING 细节 | 资源详情/现有授权管理入口；刷新解析，只重读不自动执行 |
| required 资源确实缺失/未发布/过期 | 待准备；execution admission 阻塞 | 同一计划资源缺口列表，提出复用/准备事项；不自动生产发布 |
| 完整读取成功且 0 行 | 技术读取成功、空清单及 0 统计（有来源）；不是调用失败 | 可以继续报告和验收；不得把连接失败当 0 行 |
| 部分分页、日期冲突、数据质量不足 | 报告覆盖/异常；受影响标准 UNKNOWN 或 NOT_SATISFIED | 查看来源与异常清单；修订输入/口径时生成 successor 并确认 |
| dispatch 前失败 | 执行未开始/已知失败；无调用事实 | 修复资源或配置后按现有授权重试；内容变更重新确认 |
| dispatch 后断线/超时/重启且终态不可证 | OUTCOME_UNKNOWN / RECOVERY_REQUIRED，后继依赖不推进 | 只读重新观察原 invocation；不盲目重发；授权 retry 建 successor Attempt |
| 已知 Task 失败 | stage failed，依赖未满足；无整个 Run 成功 | 显示失败阶段/原因，允许现有授权的 retry；不吞掉失败来生成完整报告 |
| 请求暂停后续任务 | 请求状态与实际应用状态分开；已发请求不保证立刻停止 | 复用 intervention exact target；只在 coordinator 有持久 fence/ack 时开放按钮 |
| 报告产生但无 terminal Run / Evidence 缺失 | 等待证据/不可验收；不得确认解决 | 重读/reconcile 原事实，保留不确定性 |
| 用户不认可结果 | 不通过或未解决；保存理由和 exact reviewed snapshot | 必要 correction → successor Plan/Run；不改历史产物或确认 |

## 5. 增量一：可持久读回的建议计划

**验收出口**：PC 用户从 exact Problem/Criteria 得到真实建议，理解阶段、职责、资源和缺口，必要补问后一次确认计划；刷新及服务重启能读回相同计划修订和批准。全程没有执行启动。

| 实施项 | 拟修改路径（均非本轮修改） | 依赖与验收 |
| --- | --- | --- |
| I1.1 建议 revision / 校验 / 资源 snapshot | `planning.py` 周边新增 typed domain/application/repository；`business_problem_application.py` / `workflow_control_*` owner seams；新 additive migration，编号实施时查重 | D1；旧 PreparePlan 兼容；Problem/Criteria exact binding；缺口可存，proposal 与 Plan 不混同；revision immutable |
| I1.2 模型生成与必要澄清 | 新 plan-suggestion invocation adapter，复用 `model_binding_resolution.py`、authority ports 与受限 provider adapter | D2；真实模型只在另行授权的验证阶段使用；错误输出/timeout 不产生 approved Plan；不复制 DraftAssistanceInvocation identity |
| I1.3 阶段资源解析与职责匹配 | `matching.py`、`workflow_definition_resolver.py`、各 owner 的 read/eligibility port、typed resolution snapshot | auth-before-lookup；版本/schema/trust/availability 独立核实；多阶段共用资源一次解析，仍保存每次用途；不新建资源 |
| I1.4 确认与后继修订 | `business_plan_postgres.py`、`business_problem_schemas.py`、`workbench_business_problem.py` 的 additive operations | atomic linkage/approval/CAS/idempotency；提交后 GET；故障重放不双写；旧接口保持原语义 |
| I1.5 PC 计划卡片与读回 | `console/frontend/src/problems/ProblemWorkspacePage.tsx` 周边、对应 API client；复用已定型组件 | 模型输出/资源缺失/必要补问/待确认/已确认/冲突/刷新失败完整状态；确认按钮焦点 Enter 可用，输入框 Enter 不触发确认 |

前置：D1/D2 的本次已接受决定、真实已提交 Problem/Criteria、授权及模型配置、task-path ownership（实施启动时核对 321/322 已集成基线/共享 UI），无需等 311—314 全部合并。资源未齐可展示建议，但不得谎称可执行。

测试边界：parser 恶意/超大/unknown field、依赖环/悬空/I/O 类型错误、资源版本错误/撤权、模型声称就绪无效、重复提交/CAS/事务 rollback、旧接口回归；真实 PostgreSQL + trusted BFF + 浏览器的确认/刷新/服务重启 readback。测试替身只能验证结构与 UI；“AI 建议接通”最终需另行获授权的真实模型证据，不能用 fixture 宣称完成。本轮不运行它。

## 6. 增量二：同一计划只读执行和结果验收

**验收出口**：同一 exact approved Plan 派生一个可追踪的 Workflow Run，阶段按真实 Task facts 更新；清单/摘要/异常/证据可读回；系统完成标准评估，Human 确认业务结果。它依赖增量一，增量一不依赖执行完成。

| 实施项 | 拟修改路径 | 依赖与验收 |
| --- | --- | --- |
| I2.1 同 Run 多 Task admission/coordinator | `execution_application.py`、`execution_repository.py`/`execution_postgres.py`、`governed_execution.py`、`workflow_control_application.py` 周边 bounded coordinator | D3；复用当前生命周期/单 Skill slot，不逐 Task start 新 Run；持久依赖 readiness、I/O artifact binding、Task Assignment、进度 read model；复用现有 Kubernetes Workflow ready/skip 算法与协调 port，接通产品链，不另造通用调度器；只支持本例线性链 |
| I2.2 真实只读输入与算法资源 | `skill_invocation_*`/`skill_executor.py`、`skill_mcp_*` 和授权配置接线；采购 R1–R5 已有资源优先 | R1–R6 的 exact eligible published configuration；必要新资源另经既有管理流程准备，323 不授权自动创建；MCP trust 与 invocation Evidence 必须真实 |
| I2.3 既有执行通道接入 | `native_dispatch_application.py`、operator Native worker、Placement、governed Skill adapters | 不重写 Runtime、不使用 314 充当已支持执行；明确每个 Task 的 effect owner，不能 Native 与 synchronous Skill 重复 dispatch 同一 operation |
| I2.4 有界产物和阶段状态 | `execution_*` / `resource_use_*` typed record/read model；frontend Problem task/result components | 来源、digest、task/attempt/plan lineage；stage 成功需其全部 required Task 成功；按页面 3 阶段统计，技术视图显示 5 Task，验收另列；不显示合成进度 |
| I2.5 标准评估/验收 | 新 ARCH-264 evaluation/confirmation/outcome typed services/repos/API，复用既有 Evidence readers/UoW | terminal Run gate、exact C1/Evidence snapshot；UNKNOWN 与 NOT_MEASURABLE 不填 0；Human disagreement 保留；确认 actor 从 trusted context 来 |
| I2.6 恢复/干预/刷新 | existing retry/intervention/dispatch observation + coordinator readback | crash 后恢复原 Run/Task，不重发 unknown；只读 retry 新 Attempt；暂停请求与 ack 分离；刷新不触发动作 |

测试边界：R1–R5 deterministic oracle（第 4.4 节）和异常矩阵；真实授权只读 source+Skill/必要 Native 路线；依赖拒绝、跨员工/跨 scope 错绑、资源撤权零 effect、并发 start 单 Run、单 slot、结果未知不重发、late observation 不污染 successor、报告 reconciliation、未终态不可验收、Human 否决、重启读回。真实数据连接和真实业务用例验收不能由管理测试替代。

下游代码实施适用 `make check`，frontend 改动还需 `npm run lint`/`npm run build`、真实服务 browser acceptance；数据库/Native/MCP 集成单独列执行与跳过，不沿用历史测试数。323 本轮只做文档验证和受控纯函数测试，不启动服务验证场景可用性。

### 6.1 工作量区间与估算假设

单位为单工程师净人日，含实现、针对性测试、集成修正和文档；不含等待 Human/数据/权限、跨分支合并等待、真实端点审批、生产运维。不是 Session 分配或交付承诺。

| 增量 | 内部分解估算 | 合计 |
| --- | --- | --- |
| 增量一 | typed proposal/持久及确认 3–5；模型用途接线/校验 2–4；资源解析 2–4；PC/读回 2–3；集成验收 2–3 | 11–19 人日 |
| 增量二 | 同 Run/Task 分工/coordinator 4–7；输入及 deterministic resource 接线 3–6；产物/评估/Human confirmation 4–7；PC 进度恢复及端到端 3–5 | 14–25 人日 |

假设：沿用 PostgreSQL/Native/现有 auth；最多 5 execution Tasks、2 职责、线性链；1 套数据 schema、1 个只读来源；报告有界、不引入文件服务；不做动态 DAG/循环/通用资源工厂；D1/D2 已接受，D3 详细契约仅在增量二实施前落定；目标部署可获得 main 已有基础。新采购 connector 或 R2–R5 全部缺失时，另加约 3–8 人日准备/验证（或重新估算），不隐含在“目录已有”里。选择新的存储设施或通用多员工编排须另 G2，以上估算失效；只采用单角色折中也不能声称完整效果图目标已完成。

## 7. 效果图映射（PC 优先）

| 页面动作/状态 | 权威对象或接口 | 现有实现 | 缺口 | 验收出口 |
| --- | --- | --- | --- | --- |
| 102 目标与完成标准 | BusinessProblemRevision/CriteriaSet/criterion read | main 有 exact 对象/接口 | 与新建议 Plan 卡片绑定 | I1：刷新同 revision，切换问题不串状态 |
| 102 AI 整理方案 | Plan proposal + Model invocation + validator | 旧进程内预览、pre-Problem assistance、model binding 基础 | confirmed Problem 的规划用途和持久 proposal | I1：真建议有调用 provenance，invalid 不伪造方案 |
| 102 三阶段、员工和资源标签 | TaskRequirement + stage group + role/resource snapshot | Workflow task/refs 与独立员工/资源已有 | stage/职责映射、可用性解析 | I1：点开 exact 来源/版本/用途/缺口；不是文案硬编码 |
| 102 执行边界 | exact plan constraints + admission policy | Skill READ_ONLY、既有 grants | 将只读/不改订单/不通知贯穿 source 和 task | I1 展示、I2 拒绝越界且零 effect |
| 102 确认并开始 | ApprovalDecision；独立 execution admission | 现有 approve 不 start | 改成增量一“确认计划”；I2 接实际 start | approval readback 不进入执行中；start 有 Run/dispatch 事实才推进 |
| 102 调整方案/自然语言缩小供应商 | successor Problem/Criteria/Plan revision | correction foundation | bounded suggestion revision UI/API | 只在目标/范围/边界改变时重新确认；旧 history 可查 |
| 103 执行中、1/3、当前日期校验 | Workflow/Task/Attempt facts + stage reducer | 单 Task/Attempt 和 Native facts 已有 | 同 Run coordinator、3 stage/5 Task 的真实统计 | I2：未提交或仅排队不冒充运行；分母固定为本计划阶段 |
| 103 任务依赖、资源用途展开 | exact Workflow task + resolution + actual Resource Use | Workflow refs/Skill binding 和 resource use 基础 | 配置与实际调用统一但分列展示 | I2：看到 selected/invoked 区别和真正 invocation |
| 103 产物与证据、方案版本 | Plan history + bounded artifacts + Evidence reader | history/Evidence 基础 | A1–A5 lineage/结果界面/ARCH-264 接线 | I2：来源追溯、terminal gate、验收与技术成功分离 |
| 103 推进记录 | append-only facts 的 authorized projection | execution/control facts | stage facts read model | I2：按 source sequence/time 展示，重连不补虚假历史 |
| 103 新对话、返回原对话 | 问题/计划稳定路由；conversation 仅上下文 | workspace/问题读取基础 | 执行页导航与后台连续性验证 | 新对话不取消已有 Run；返回读回真实状态，无额外确认 |
| 103 干预/暂停后续 | InterventionRequest→APPLIED/OBSERVED | 控制应用已有闭合命令 | coordinator fence/可信 UI 入口 | I2：未接通时明示不可用；请求不等于立即取消 |
| 112 资源准备统计 | bounded authorized ResourceResolutionSnapshot | 资源目录/各域状态已有；313 是候选体验 | 计划去重、required/optional、blocked-by projection | I1：不复制 9/4/5；未查询为未知，未授权不泄露数量 |
| 112 查看资源详情 | 各 resource owner exact read | main Workbench、311/312/313 可选增强 | 从计划回到 exact revision 的导航 | I1：共享资源只算一次，多处用途可见 |
| 112 确认延期口径 | Criteria revision + successor Plan | Criteria 基础已有 | 必要补问 UI | I1：口径已有不再确认；改变则更新 exact digest |
| 112 协同员职责、其他准备事项 | optional requirement/gap + 人工准备说明 | 无本场景准备工作权威 | 无需新建任务工厂；先给说明/详情入口 | optional 不阻塞，未指定负责人如实显示，不分配新 Session |
| 112 就绪后继续/组合验证 | fresh admission check + same Plan readback | 基础校验存在 | 同 Run coordinator/explicit start | I2：本例等待显式开始；资源恢复不自动调用；语义资源替换需 successor |

## 8. Human 决定登记与剩余边界

本次 continuation 的 Human 原始决定：“D1采用推荐的typed、不可变建议修订与计划确认关联方案”；“D2采用confirmed-Problem的plan-suggestion调用用途”；“D3接受同一Run下Task级多员工绑定的方向，详细执行契约留在增量二实施前收口，不阻塞增量一”。Provenance：`HUMAN_CONFIRMED / CURRENT_SESSION`；登记为本工作树文档，非 main 集成或实施完成证据。

| 决策 | 登记状态 | 已接受边界 | 后续 gate |
| --- | --- | --- | --- |
| D1 | `ACCEPTED` | typed 不可变建议修订；正式 Plan/批准唯一确认关联；资源缺口可表示并确认待准备计划；第 3.0 节固定原子确认、successor、v1 兼容 | 无新增 D1 架构选择阻塞增量一；产品编码/迁移需另行明确授权 |
| D2 | `ACCEPTED` | confirmed-Problem plan-suggestion 用途；精确非 Attempt identity；复用 Model Governance、现有授权、Contextual Resource Use/Evidence owner；第 8.1 节细化 | 不授权本轮真实模型调用；后续调用前须有该用途有效授权及配置，非新建审批体系 |
| D3 | `DIRECTION_ACCEPTED / EXECUTION_CONTRACT_DEFERRED` | 同一 Run 下 Task 级多员工绑定；资源独立维护；每 Attempt 单 managed Skill；不以多个 Run 或展示角色伪装 | 增量二实施前收口根 Assignment/Task Assignment 验证、Run terminal、依赖/I/O、retry/pause fencing、历史兼容；不阻塞增量一 |

D3 的详细推荐仍是保留一个 Run 根 Assignment 并添加 Task 参与绑定，但**根 Assignment 的确切职责/约束尚未作为完整执行契约接受**。增量一只保存职责要求和经验证的 Definition 引用，不创建或执行这些实例关系。ARCH-264 的 terminal Run/Human result confirmation 继续有效，不再另问是否由模型判定成功。

### 8.1 D2 精确调用、结果和 Resource Use 归属

用途固定 `CONFIRMED_PROBLEM_PLAN_SUGGESTION`，只读已授权的确认问题/标准及可见资源描述，输出计划建议/必要补问；不执行计划、不管理资源、不修改 Problem/Criteria。新增的是现有治理中的受限用途及 typed target，不是独立审批层。

| 项目 | 本用途的精确契约 |
| --- | --- |
| Invocation owner | Planning application 拥有 plan-suggestion invocation metadata、调用状态和结果关联；Model Governance 仍独占模型/版本/binding/eligibility，Execution domain 仍独占 canonical Resource Use；各 Evidence writer 保持原 owner |
| 服务端身份 | scoped opaque invocationId、suggestionContextId、requestRevision、可选 predecessorInvocationId；请求前分配，客户端不得传入 authority IDs。Context 指向 exact confirmed Problem revision/digest、CriteriaSet revision/digest、有序标准成员和 expected aggregate versions；并绑定 source proposal revision/digest（首次不存在时用明确的 FIRST_PROPOSAL target variant，不伪造 proposal/Plan ID） |
| Target snapshot | schemaVersion + purpose + scope + invocation/context/request revision + exact Problem/Criteria + request variant/source proposal + resolved resource snapshot ID/digest + input commitment + output schema/policy version；规范化计算 target digest，身份和快照持久化后才允许调用。资源目录不可读时不生成虚假 snapshot |
| 模型绑定 | exact Model/Provider/Endpoint/Profile revisions/digests、adapter revision、授权 decision/credential identity、policy generation 与请求预算；Model Governance 从 server-owned profile 解析，不由模型/浏览器选择未经授权 endpoint。复用已有治理的授权先于 lookup/disclosure、dispatch 前检查、persist-before-effect 和未知结果不重发规则 |
| 结果 | Invocation 技术结果与计划语义结果分离。技术成功只能说明返回被接收；有界解析器/validator 产生 NEEDS_CLARIFICATION、VALID_SUGGESTION、INVALID/UNSUPPORTED 等结果分类。VALID_SUGGESTION 精确关联其 output semantic digest、validator version/report 及由 planning owner 保存的 ProposalRevision；不能自动确认 Plan。补问回答形成新 request revision/invocation，不改原调用记录；late result 只能归原 target，问题已变更则不自动接纳 |
| Resource Use / Evidence | 通过既有非 Attempt contextual Resource Use 模式登记 exact plan-suggestion invocation/snapshot target，使用 typed context variant，不套用 pre-Problem draft target、不伪造 Attempt，也不将旧 Attempt 字段 nullable 化。Execution owner 写 Resource Use state/计量，Planning 仅请求登记和保存链接；Evidence 保存 exact invocation/target/model/result digest、bounded/redacted 状态和来源。不生成 workflow execution Evidence 来证明规划调用 |
| 保留与恢复 | 原始 prompt/provider response、secret/private message 不落库；仅保留治理允许的 metadata/commitment 与 D1 所需规范化有限业务建议，后者归 Proposal owner。相同 scoped idempotency key+payload 返回原 invocation；不同 payload 拒绝。dispatch 后结果不确定保持 OUTCOME_UNKNOWN，只观察/读取，不能为补 Resource Use/Evidence 再调模型；附属事实登记失败显示待补记，未补齐不宣称完整调用证据 |
| 授权与确认 | 沿用现有 trusted context、exact grants、用途策略和预算；计划确认复用 D1 的一次关键确认。调用授权不是 Plan 批准，Plan 批准也不授予模型或执行权限；不新建人工模型审批页，不让用户对每个阶段/资源重复审批 |

以上 typed 字段用于限定 D2 接受用途的实现，具体类名/私有路由/迁移序号由后续单任务 G1 计划确定；不放宽 ARCH-318 既有 pre-Problem 路线。

### 8.2 增量一单一可执行任务描述（实施待授权）

**任务名称**：已确认问题到三阶段五任务建议计划——资源说明、一次确认与持久读回。属于原计划既有版本/顺序的增量一，不新编 Session/WP；一个后续获授权任务承接，不拆数字员工/Skill/MCP/Knowledge 模块会话。

**修改范围**：第 5 节 I1.1–I1.5 的 typed proposal/Plan confirmation repository 与 UoW、confirmed-Problem invocation adapter及既有 contextual Resource Use 接缝、只读资源解析、可信 BFF/API client、PC 计划卡片、针对性测试和文档。未来新增 persistence 仅为现有 PostgreSQL 内有界 additive schema；版本化 reader/writer 和迁移须在获授权实施时做。不要实现 Run coordinator、Task 实例路由、MCP 业务调用、Skill 执行器新业务资源、资源生产发布、结果业务验收或修改 operator/runtime。

**前置依赖**：D1/D2 已满足；取得明确实施授权、固定届时 main 与共享路径 ownership、现有可信身份/数据库测试环境、exact confirmed Problem/Criteria、下表最小输入，以及 plan-suggestion 用途的精确模型配置/调用授权。D3 细节、采购真实执行资源齐套、311–314 合并、外部 WP 定位均不作为增量一设计/编码的新增阻塞项；未获真实模型调用授权时，只完成不含调用的实现/测试，最终真实 AI 接通验收仍待该证据。

**验收出口**（均为同一个采购案例）：

1. 页面固定展示三阶段五个唯一 Task：S1/T1 读取快照；S2/T2a 校验、T2b 延期识别；S3/T3a 汇总、T3b 报告。DAG 为 T1→T2a→T2b→T3a→T3b；执行尚未发生，A1–A5 只显示预期交付物，不显示样例数据为实际产物。此分解作为本例服务端场景约束，不能在 UI 丢弃/添加模型任务来凑五个；不合约的建议由 validator 拒绝/要求修订。
2. 每 Task 绑定职责要求、I/O 和依赖；角色可复用，资源独立引用；缺失资源保留 requirement 而非假的 ID。至少覆盖一条 real-owner 精确引用读回和一条 required 缺口路径，以及未知/拒绝/版本不符/optional 不阻塞路径；测试数据可预置于专属验证环境并明确标识，不能冒称真实企业目录。
3. 必要业务参数未确定时集中补问；已确定时直接显示建议。服务器验证模型结构/依赖/资源，不相信“已就绪”文本。一次“确认计划”原子返回 Plan revision/digest、source proposal 和 ApprovalDecision；资源未齐显示“已确认，待准备；未开始执行”。
4. 浏览器刷新及服务重启读回同一 identity/digest/approval/linkage；重复确认、不同 key 竞争、冲突 CAS、故障 rollback、响应丢失重放、新 revision/旧 history、跨 scope 不泄露、旧 v1 API 行为均有测试。
5. 确认及资源刷新前后 Run/Task Run/Attempt/Assignment/Placement/业务资源创建或发布为零，业务 MCP/Skill/Native dispatch 为零；模型调用仅发生于明确获授权的 plan-suggestion 请求，不因确认、刷新或补记事实再次调用。
6. 独立记录真实 PostgreSQL/BFF/browser 证据；真实模型的 exact purpose/target/binding、结果关联、Resource Use/Evidence 齐备才可称 AI 接通。fixture/controlled provider 验证标明 TEST，不替代真实模型验收。适用 `make check`、frontend lint/build、专属环境集成和 PC browser 验收，实际通过/跳过分别记录。

**工作量**：沿用 11–19 净人日（typed 持久/确认 3–5，调用/校验 2–4，资源解析 2–4，PC/读回 2–3，集成 2–3），包含本次 D1/D2 细化；假设现有治理/PG 接缝可用、一个受限模型 profile、三阶段五 Task、有限输入和目录。等待授权/配置及外部服务故障不计；增量二资源新建的 3–8 人日不转嫁到增量一。若需改变 accepted authority 或新基础设施，再报告 G2，不默增范围。

**剩余必要决定**：增量一没有未决 D1/D2 架构选择；实施及真实模型调用权限尚未授予。数据路线/业务口径/模型 profile 等按下表核实配置，不新建架构审批体系。D3 细节只阻塞增量二。外部 WP 原文件/版本/里程碑引用继续待核对，不影响本任务描述，也不改变计划顺序和版本归属。

### 8.3 场景数据/资源最小准备及可接受替代

| 准备项 | 增量一最小要求 | 可接受替代 / 不可宣称 | 增量二才必需 |
| --- | --- | --- | --- |
| 已确认问题与标准 | 后端持久 exact Problem/Criteria；第 4.1 节日期、时区、授权范围、粒度、数量/去重、异常规则有明确值；三阶段五 Task 的 schema/I/O oracle | 演示可用脱敏/合成业务输入，但明确标识；缺真实口径先补问，不用模型猜。原例日期仅为样例，不默认当新运行日 | 实际执行日期、范围与 exact Plan 一致 |
| 订单样本 | 第 4.4 节五行合成样本、source schema/字段说明及预期分区，另列空数据/重复/冲突/单位异常 oracle；用于规划/测试输入说明，不要求读取真实订单 | 无业务数据也可规划和确认待准备计划；不得显示“已读取订单”或 A1–A5 实际产物。输入里不塞整份敏感采购数据给模型 | 真实可追溯冻结 snapshot、授权、完整分页/范围、digest、source revision/asOf |
| 数据取得路线 | 在计划中选定“采购只读 MCP 快照”需求并如实标缺口 | 可选“Human 提供冻结导出快照”：附来源系统、导出时点、筛选范围、schema/digest/行引用、完整性说明；改变路线须在确认前披露，已确认后走 successor。文件上传/文件存储能力不存在时只记录待准备输入要求，不造已上传状态 | 实际导出/只读 endpoint/tool、受治理 adapter与 Evidence；不将文件替代包装为已接通 MCP |
| 员工/Skill/MCP/Workflow | E1/E2 职责要求，R1–R6 operation/schema/用途与所需版本说明；能授权读取的 published exact refs 才匹配，其他为缺口/未知 | 两职责可以引用同一已发布且职责覆盖的员工，但明确展示复用，不造第二个员工；未找到等价 Skill 时保留 requirement，不自动生成发布；测试目录标明测试来源 | published bindings、Instance/Assignment/Placement 与 D3 执行契约全部满足 |
| Knowledge | 本例默认 NOT_REQUIRED，Criteria 为日期规则权威 | 企业政策必须引用时提供 exact published document/index snapshot；未具备则缺口，不以模型记忆替代，也不要求先完成 312 文档上传 | 若为 required，真实检索/引用权限与 trace |
| 模型与治理 | 已配置、获授权的 plan-suggestion profile及 exact Model/Provider/Endpoint/adapter binding、scope、预算、用途策略；secret 仅外部引用 | controlled provider可先验证持久/校验/界面，明确 TEST；未授权真实调用则 AI 接通验收待证，不假报成功 | 不要求为了确定性订单分析再额外调用模型 |
| 验证环境 | 独立 PG、trusted BFF/browser 和授权测试资料；当前 main/共享路径归属明确 | 资源缺口不要求另开模块会话；本 Session 不修改或启动 321/322 服务 | 独立只读业务资源和执行环境 |

## 9. 缺项、验收记录与交付边界

集中缺项（不再重复全项目发现）：

1. **外部主计划映射待核对**：此前使用 WP 编号的交付主计划本轮未在仓库定位到，原文件路径/版本、相关 WP/里程碑引用及与本附件的对应关系尚待核对。Human 已同意关联当前可核实的 CONTROL-254，并引用 PLAN-001/003；这不表示 CONTROL-254 替代外部主计划。保持既有任务顺序、版本和里程碑；不新编 WP、不猜映射、不重建台账，不扩为全局文档一致性任务。
2. 未提供真实采购 source schema、分页/快照保证、可读取的 endpoint/tool revision、数据样本及授权；因此本例口径和资源匹配为 proposed，不声称零延期或任何数量事实。
3. E1/E2、R1–R6 的真实发布 ID/revision/digest 与运行适配配置未核实；代码审计不能代替目录实例可用性验证。可选 K0 是否必需取决于业务政策。
4. D1/D2 已接受，D3 方向已接受、详细执行契约仅在增量二实施前收口；本轮不再要求重复裁决。现有 Frozen Contract/API group/Kubernetes source of truth 不改；若实施细化发现必须突破，按 G2 停止报告，不将本设计当授权豁免。
5. 321/322 可能继续改变主入口和共享 UI；后续实施启动只需复核届时 main 与精确 ownership 差异，不使用其环境验证 323。

### 9.1 首轮验证记录（本次文档收口未重跑产品测试）

- `uv run --frozen pytest -q console/backend/tests/test_planning.py console/backend/tests/test_matching.py console/backend/tests/test_business_problem_domain.py console/backend/tests/test_workflow_control_domain.py`：**56 passed in 4.15s**。只验证已有确定性 domain/规划/匹配契约，没有调用真实模型、数据库或运行服务。
- `git diff --check`：通过；相对本次基线只修改本附件、CONTROL-254 关联章节及 Registry 单条登记。
- 附件相对 Markdown 链接、本次引用的完整源码路径与候选对象检查通过；采购样例的日期、分区和汇总已用独立算式复核。
- 未运行 `make check`、frontend lint/build、PostgreSQL/browser/Native/MCP 实验：本轮没有产品代码变更，且不操作其他任务环境。本结果不是实施验收，也没有借用历史 CI 计数。

文档交付完成不表示资源就绪、增量实现、P1 接受或 Session CLOSED；不提交实现 PR，不自动进入下一增量。

### 9.2 本次决定收口验证

仅更新原附件、第 8 节决定记录、既有 Registry 的 323 行以及 CONTROL-254 的关联说明。检查 Markdown 链接、状态一致性、修改路径与 `git diff --check`；不新增 Session/WP/台账，不执行产品编码、迁移、真实模型或实现 PR。首轮 56 项测试是首轮历史结果，不作为本次重新运行结果。设计决定已登记；Session 保持 REVIEW，不自动 CLOSED，也不授予实施权限。


## 10. 增量一 G1 与恢复检查点（2026-09-17）

Human 已明确授权原 323 增量一产品实现、独立环境迁移、验证、正常提交与 non-force push、唯一 Draft PR；停在 Human 接受/合并前。真实模型、正式迁移、部署、业务执行仍关闭。D1/D2 沿用接受结果；D3 详细契约不阻塞本轮。

### 10.1 已核验恢复点与唯一 writer

- 原载体 `01a0af15-ada4-7a92-b68a-252e871b2aa7` 状态 systemError，最后一条 commit 命令 completed / exit 0，hooks pytest Passed；最后提交 `f1a1822fa97c47bc2fb2b51b8d0ea3bf1957855a`。没有重复运行该提交。
- 原工作树 `/Users/tristan/.codex/worktrees/b923/cloud-native-agent-platform` 保持原分支；恢复时 tracked/untracked status 均空。未 reset、clean、覆盖；未发现遗留 git/test/server 实施进程。本恢复载体是唯一 323 writer。
- 实时远端 main `f6a931017dc4b68b7a92ffe0abaaf2819eec6cb7`；321 `97b8603e8a8507eea719099e465e559b81240925`；322 `e5fa882a0b18dfbf3465cc6fb17a663f83228db7`。323 尚无远端分支或 PR。
- 322 最近回执保持 e5fa882、视觉接受身份 79f62d0，不新增实施或同步；当前载体 idle。独立后端先行，共享 UI 接入前再核验 exact 文件差异与 writer。父 PR 不擅自合并；323 依赖将按实际接收内容记录。
- 设计已提交；G1/实现尚未开始是本次恢复起点。历史测试不计入新候选结果。

### 10.2 实施顺序、接口与兼容

1. planning v2 typed domain：exact Problem/Criteria、不可变 proposal、阶段/Task/资源需求、服务端结构及采购案例约束校验；规范化 digest，不保留 raw provider 内容。
2. Workflow Control owner 的 additive PostgreSQL v2 repository/UoW：建议、正式 Plan revision、ApprovalDecision 与确认关联；唯一约束、幂等、CAS、原子 rollback、successor/history。旧 v1 不改，不伪造 Workflow/Instance/Assignment。
3. confirmed-Problem plan-suggestion application：既有授权、模型 binding/budget 与 contextual Resource Use/Evidence 接缝；typed 非 Attempt target；persist-before-effect、UNKNOWN 不重发、有限补问与有效/无效结果分类。只用 controlled provider 验证。
4. 授权后的资源 owner 精确读回与独立快照；required/optional、未知/不可读/版本不符不误标就绪；不生产发布资源，不执行 MCP/Skill。
5. 可信 BFF 与独立 PC 规划区域：当前问题补问、三阶段五任务、用途/缺口、一次确认、刷新/重启/history。确认不启动执行，缺资源明确“计划已确认，资源待准备，尚未开始执行”。
6. 独立 PostgreSQL/BFF/browser 验证；make check、frontend lint/build、定向集成与截图；review diff/status 后正常提交、推送唯一 Draft PR。

私有版本化路由和迁移编号在源码查重后固定；reader 先于 writer 启用，回退关闭 v2 writer、保留历史。风险集中在原子确认、跨 scope 授权、不可变 digest、owner 解析和治理调用副作用；测试覆盖并发不同 key、同 key 异 payload、响应丢失重放、故障回滚、successor CAS、跨 scope、刷新零执行/模型调用及 v1 回归。

### 10.3 视觉与后继

102/103/112 是本轮直接权威素材；此前简称 02/03/11 按用户说明分别对应目标/方案连续呈现、阶段任务用途、多资源缺口总览，即 102/103/112，不推断为另三个文件。322 截图仅供现状与回归。采购代表页面先浏览器核对再复用其他状态；局部布局包含在原 11–19 净人日估算，非工期承诺。

增量一阶段验收后，后继统一问题提出、AI 补问、用户纠正、确认创建、读回与规划确认的 PC 视觉：布局、信息层级、卡片、留白、导航及右侧摘要。此项另行估算及授权，不新开 Session、不重开已关闭任务，不提前实施。“323 规划功能完成”与“整条演示链视觉达标”分别记录。

### 10.4 实施检查点：独立后端首段（未交付）

已新增 `plan_suggestion_domain.py`、`plan_suggestion_postgres.py`、`plan_suggestion_application.py`、`plan_suggestion_resources.py` 及 additive `0025_plan_suggestion.sql`。当前仅为未接入生产入口的后端首段：typed 不可变语义、采购三阶段五 Task 结构、same-owner 原子 Plan/Approval/source、幂等/CAS/history、Problem/Criteria owner 精确校验与资源状态解析。未声称完整增量一完成。

独立容器 `s5-v023-arch-323-pg`（postgres:15），仅监听 `127.0.0.1:25432`，数据库 `planning323`，合成测试环境 localhost trust，无企业凭据。各 PG 测试创建独立临时数据库并在结束清理自身临时库；保留容器与主测试库。未操作其他任务环境。

实际执行 `PLANNING323_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:25432/planning323 uv run pytest -q console/backend/tests/test_plan_suggestion_v2.py`：**9 passed in 2.58s**。覆盖真实 Problem/Criteria owner、拒绝未授权/陈旧目标、确认响应丢失后历史重放、不同 key 并发收敛、key 冲突、rollback、successor、history、跨 scope 及资源 UNKNOWN/optional。新文件 Ruff check/format 已通过。尚未运行全量 make check、frontend、browser；新候选 CI 尚无。

下一未完成步骤：完成 invocation 的 D2 typed target、persist-before-effect、现有 model binding/budget 与 contextual Resource Use/Evidence owner 接线；资源 real-owner 精确读回补验；可信 BFF/生产 composition 与 102/103/112 PC 页面；独立服务重启/browser、全量门禁、正常 push/唯一 Draft PR。后端首段的测试通过不能替代这些步骤。

### 10.5 接线中的检查点

首段提交实际成功：`42f0021`，正常 Ruff/format/pytest hooks Passed。之后新增 D2 typed target/output、Planning invocation claim/result、`0026` additive contextual kind/Evidence variant、受控 provider service、可信 BFF read/history/confirm/resource refresh，以及独立 `frontend/src/planning/` 组件。当前生成服务尚未完成生产 composition、前端生成入口和端到端接线，不作为功能已完成。

实际 PG + controlled-provider 定向结果：13 passed in 3.70s；四路径为 VALID_SUGGESTION / NEEDS_CLARIFICATION / INVALID / OUTCOME_UNKNOWN，重放 provider call count 保持1，真实provider关闭。真实 Problem owner 校验与此前事务测试继续通过。资源 owner 精确实例、真实BFF/browser/restart仍待验证。

前端首次 lint/build 因 node_modules 不存在无法运行；随后在原323工作树 `npm ci` 成功（锁文件未改），lint 0 errors / 1 React cleanup warning，build通过；cleanup warning随后修复，待下一轮重验。当前页面尚未加入主路由，因此该 build 不是页面浏览器证明。

共享UI ownership复核：321恢复载体和322恢复载体均idle，322最新回执明确停止视觉实施。原323是本工作树唯一writer。下一步在原分支接收 exact 321 `97b8603` 与322 `e5fa882` 的依赖，保留main恢复/焦点保护，解决本地文件级差异；不合并父PR、不修改其工作树/环境。完成接收后再接入主路由并记录组合source/tree及适用新测试。

### 10.6 再恢复检查点（2026-09-17 21:26 +08:00）

旧恢复载体 `01a0af54-6e6e-7bd1-932f-3527d9e1ce18` 为 systemError，最后只读命令 exit 0；此前 HTTPS 启动 exit 1（DRAFT_PROFILE_INVALID），未留下 server/test/hook writer。原 b923 分支 HEAD `cccf1519c0b678415c87b9fcd17090817213f9a5` / tree `f199062a108e51a311a72895ae61014570c50826`，321/322 本地接收完成，不重复 merge。Registry 321/322/323 各一行，保留父状态。

原7项 tracked修改、5项untracked文件已保全到专属验收目录 `recovery-20260917-212650`（binary patch及untracked tar）；原日志、证书、独立PG及全部数据保留。当前载体为唯一323 writer。提交/hooks时禁止并发写入。下一步恢复已部分seed的专属browser库，不删除或重新生产已有资源；解除错误复用draft composition造成的启动故障，再完成治理/BFF/owner/browser与最终门禁。历史1906通过不计为后续改动验证。

### 10.7 组合接线及独立验收（2026-09-17）

已完成可信 planning-input / invocation BFF 路由、生产 composition 的显式 `PlanningInvocationDependencies` 接缝、前端主路由与必要补问入口。默认无 provider；部署必须显式提供 profile、当前精确授权、Model owner resolver、budget、commitment key 与受控 provider。`PLANNING_V2_ENABLED` 单独只开启版本化读/确认/资源操作，不偷偷启用真实模型。专属 HTTPS 环境实际复用该 invocation composition、真实 Model owner、动态 exact grants、Postgres budget、canonical contextual Resource Use 与 Model Evidence。

独立环境：原PG容器与 `planning323` 保留；`planning323_browser` 中断时已部分seed的 Problem/Criteria/Employee/Model 全部读回恢复，未删除、重建、覆盖。修复了测试启动器错误复用 draft profile、同generation重复激活和授权窗口不合规；321环境/账本/凭据/调度未操作。专属 `https://127.0.0.1:19324`，外部验收资产 `/Users/tristan/Documents/s5-v023-arch-323-acceptance`，其中凭据与私钥不入库。

实际验证：

- `make check`：1916 passed / 201 skipped / 1 upstream deprecation warning（80.39s）；跳过项为未配置其他专属PG/Qdrant/Linux环境，不称全外部矩阵通过。之后补充输入总字节边界的定向 invocation 测试：7 passed（3.41s）；最终提交 hooks 仍须正常运行。
- 真实owner与新planning PG定向测试合计覆盖17项：结构/采购DAG、事务rollback、并发不同key确认、CAS/history、真实Problem/Criteria陈旧校验、exact Employee读取、拒绝/错误摘要/required/optional、受控结果分类、治理拒绝/预算失败零dispatch、输入预算及未知不重发。
- 旧v1真实HTTP/PG回归：3 passed / 1 deselected（13.22s），覆盖事务rollback、版本/CAS/独立grant、错误精确资源与改变标准拒绝确认；未运行其业务执行测试。
- frontend lint/build通过，保留bundle >500kB提示；W2A/W3组合回归19 passed（15.2s）。该mock回归中部分criteria请求落到未运行的8000代理，断言全部通过；不将其当真实后端证明。
- 首轮真实HTTPS/PG PC浏览器1 passed：必要补问、刷新补问、三阶段五任务、资源刷新、一次确认、再刷新/history一致。独立进程重启后浏览器1 passed：Plan/Approval/source history严格相等。资源状态为8需求、1匹配、6必要缺口、1可选，不使用设计图9/4数值冒充事实。
- `s5_v023_arch_323_readback.py`实际PASS：CSRF拒绝、重复确认、资源刷新、未知ID拒绝、历史不变；全部资源/执行owner及invocation/Model Use/Evidence/budget计数前后不变，2条受控调用均关联canonical Use/Evidence。没有模型重放、Run/TaskRun/Attempt/Assignment/Placement或业务资源生产/发布。无真实模型调用。

视觉依据为102/103/112：PC左侧目标与三阶段五任务，任务可展开查看职责/依赖/I/O/资源用途；右侧边界/资源计数/版本；确认紧接方案，缺口详情随后。首轮全展开过长已改为任务摘要，重启截图已检查。保留当前父级shell；全链路视觉统一仍属10.3后继，不称整链视觉验收完成。原始截图、browser receipt、side-effects receipt及日志位于专属验收目录，最终source/tree和截图/构建摘要绑定在该目录manifest。

限制：资源仅对已配置Employee reader作真实exact匹配；未配置的Skill/MCP/Knowledge/Workflow reader明确UNKNOWN，未选required为MISSING。模型仍为CONTROLLED_TEST_PROVIDER、业务资源为测试owner资料；真实AI接通/质量、企业采购资源齐套、D3执行与Human接受/merge均未授予。仅在既有323项交付一个Draft PR；Registry中321/322行已与接收候选逐字比对一致。

最终PC浏览器补验：2 passed（2.5s），包含重启后精确history读回、网络响应丢失后刷新仍复用opaque idempotency key；URL不保存回答正文。frontend最新构建为 `index-CnQjc8aV.js` / `index-CXGJAZF9.css`。提交前停止323验收服务并冻结工作树，仅正常hooks可写格式；不绕过hooks。

### 10.8 唯一Draft交付检查点

实现已正常提交并non-force推送：source `b9d2068f554f8e34ba24d6fb1f494bd773faf53c`，tree `b9d240dc664acd4ad60b720d8bfdfe2c7980e3ca`。提交Ruff/format/pytest hooks全部Passed，提交后工作树干净；无后台writer，未绕过hooks。正常hooks包含最新输入边界及全部17项planning测试（设置专属PG变量）。提交后非变更Ruff check/format-check通过。

唯一Draft PR：[183](https://github.com/yanzheqian1774-debug/cloud-native-agent-platform/pull/183)，base main。父PR状态未改。提交后使用该source重启专属服务，HTTPS只读/确认重放/资源刷新与副作用检查再次PASS，2条controlled调用的Use/Evidence关联不变。随后停止验收server，保留PG、runtime和全部数据；重启命令见测试启动器。最终截图/构建摘要/source/tree在既有验收目录 `capture-manifest.json`，没有将凭据或私钥入库。

本条及Registry状态是交付登记增量，不改变上述实现候选。登记时12项远端CI正在运行，终态以PR exact head checks为准；不把pending写为通过。本Session停在Human接受与合并前，仍OPEN。

### 10.9 PC视觉统一实施授权与计划（2026-09-17）

Human已授权在原323、原分支及唯一Draft PR #183继续视觉实施，替代10.3的“未授权”状态。功能检查点2b8e66f350ac91be83f8c8ac4263692a1d17ce07/tree b7ef029e188c7eef96eabadf84519c3ef57e4766及原review证据保留。当前恢复载体为唯一323 writer；321 idle、322 notLoaded，均不操作其环境或共享文件。原b923工作树干净，无其他323实施writer。

有界G1计划：先用既有323合成采购案例完成目标/计划同屏及实际PC截图，展示后继续推广；提取共享页头/步骤/卡片/时间格式与局部视觉tokens，覆盖问题提出、补问、纠正、确认创建、正式读回、规划补问、三阶段五任务、资源缺口、计划确认和历史。导航仅调整呈现，路由保持可达；业务名称从已有任务/资源语义派生，未知项明确标识，不改持久化数据。技术ID/digest进入展开详情，测试来源保持显式。

边界：只修改frontend展示与针对性测试；保留授权、请求key、UNKNOWN、身份切换/迟到响应和焦点防护。无模型链路/后端存储/执行/资源生产能力变更。102/103/112及原整套效果图为目标，322截图只作回归参考。代表页在1500×1050检查同屏，1366×768检查滚动/可达性；输入、折叠、确认及历史以浏览器交互回归和323独立controlled-provider环境验证，不使用321诊断环境或真实模型。

门禁：frontend lint/build，问题理解/确认/身份保护及规划针对性Playwright回归，make check，正常提交hooks；新提交推送后记录exact source/tree、截图hash、12项CI实际checkout身份。历史验证不冒充新结果。保持Draft，等待Human视觉验收，不Ready/merge/部署/关闭Session。

### 10.10 PC视觉统一交付（2026-09-18）

按10.9授权完成前端呈现：问题提出/补问/纠正/确认创建/正式读回与规划入口使用同一蓝白外框、标题、步骤条、卡片、按钮和右侧摘要。PC次级导航折叠分组，既有全部路由保留；视觉shell精确限定 `/work` 与其子路由，不影响 `/workflow-definitions`。身份读取、焦点、异步恢复、授权/幂等/UNKNOWN与确认函数未修改。

规划默认展示三阶段五任务的职责、数字员工、资源摘要；展开显示Skill/MCP用途和状态，依赖使用任务名称，A类产物标识映射为生产任务的业务结果名称，原标识保留在详情。资源按kind分组，统计为已匹配+必要缺口+可选未匹配的完整分解，匹配不冒充执行就绪。批准、精确资源修订和digest折叠；程序生成的时间统一北京时间中文显示，业务原文不改写。1500×1050默认目标/任务/确认同屏，1366×768实际滚动可达；移动端保留摘要抽屉、焦点与原文读回。

可选构建参数 `VITE_ACCEPTANCE_LABEL` 仅显示测试来源文字，不选择provider或改变API。验收构建显式标记323合成采购案例；未设置时不显示测试条。前段截图为UI_API_FIXTURE，覆盖合成补问、自然纠正、一次确认和授权后读回；不冒充模型质量或真实Problem持久化新旅程。规划部分继续复用323原真实HTTPS/PG记录：历史补问、同一建议修订和确认关联。确认按钮单次写入由UI fixture验证；真实后端确认重放、CSRF、owner、历史及副作用由独立HTTPS检查验证，不制造第二套正式业务数据。无真实模型调用、无321诊断环境操作。

新验证（旧2b8e66f检查点结果未计入）：

- frontend lint与TypeScript/Vite build通过，保留原bundle >500kB提示。
- 问题理解/视觉/规划交互：39 passed（25.2s）。包含原34项回归及5项323同案例、两PC尺寸、历史/UNKNOWN、导航边界检查。
- W2A/W3及Evidence焦点：21 passed（23.8s）。按已授权的技术详情折叠更新测试，增加“默认隐藏→显式展开→原值可读”断言，保留精确授权/迟到响应/滚动/焦点/移动端检查。部分原mock criteria请求仍记录8000代理未运行，断言通过，不计真实后端证据。
- `PLANNING323_TEST_DATABASE_URL=.../planning323 make check`：1917 passed / 201 skipped / 1 warning（88.25s），skips为未配置的其他外部环境；323专属PG属于本地证据。
- 真实HTTPS确认重放/CSRF/owner/history PASS；业务与执行计数不变，原2条受控调用关联Use/Evidence，无新增模型调用。

同案例改造前对照从旧固定source的只读archive构建，未新建分支/worktree/Session；index.html、icons.svg、favicon.svg、JS/CSS五个构建文件逐一与原manifest SHA-256相同。旧源/树、review六图及manifest保留。新UI fixture截图与真实PG截图分别记录，参考101/102/103/112为目标，322仅回归。资产目录仍为原验收根下 `visual/`，其中对照入口 `index.html`、新候选身份/截图/build哈希 `visual-capture-manifest.json`、CI回执和checkout审计跟随本次推送登记，不回填到旧通过记录。

本次是原323视觉增量，唯一PR仍#183 Draft；正常hooks提交后非force推送，最终source/tree及CI实际checkout以既有PR和外部manifest为准。无D3执行、资源生产、Ready/merge/部署/关闭。完成实施和工程验证后返回Human视觉验收，不自行宣称Human已接受。


### 10.11 PC视觉恢复与最终收口（2026-09-18）

旧writer `01a0afb7-b849-7953-a598-f27b2712733d` 为 systemError；原视觉提交及non-force push均已成功，复用 `a5afecc4b3c393ade3afa6fa32dca1aeccd3207d` / tree `cfa148c82737e11d41dd3ad4c378a118dedcd9bd`。原b923工作树、分支、暂存区及历史证据完整，接管时干净，无未完成git/hook进程。只保留原323验收服务与baseline预览，不操作321环境；当前恢复载体为唯一writer。

该视觉候选CI实测10成功、2失败，两项均因299静态测试仍要求已替换的旧文案，未进入后续浏览器阶段。恢复仅更新两处静态边界断言，分别检查单独发起/确认规划且不执行、禁用辅助时不自动调用模型或资源、确认前不创建问题/执行/准备资源；未删除或跳过测试，未改产品源码。相关两文件17项通过，Ruff检查通过。既有make check默认testpaths不包括console/frontend/tests，因此1917通过不能替代这些静态检查。

额外执行整个frontend Python目录曾得到96通过/2失败：一项为上述同源旧文案，已修复；另一项test_s5_impl_274_wave1::test_digital_employee_keeps_core_concepts_separate要求旧数字员工页面字面量。已逐字验证该测试及产品文件与保留基线2b8e66f相同，旧源同样不含Agent Definition，登记为既有范围外测试债务，不修改、不隐藏，也不声称整个目录通过。

39项交互、21项工作区、1917项make check及HTTPS/PG副作用证据复用10.10原日志；本轮产品源码未变。以最终前端source重建到验收目录recovery-build，五个文件与原dist逐字一致，不覆盖原构建或截图。最终source/tree（包含此次测试与登记变更）、最新CI终态及实际checkout关系在原visual/visual-capture-manifest.json、visual/ci-checkout-audit.json与唯一Draft PR #183登记；不沿用旧12成功，也不把旧失败候选改写为成功。

对照入口visual/index.html保留11组前/后/效果图，UI_API_FIXTURE与HTTPS_REAL_PG_EXISTING_RECORDS分别标记，非真实模型完整旅程。102目标/任务/确认同屏、步骤条和蓝白层级已落实；103任务职责/依赖业务名称、资源用途已落实，但执行状态仍未实现；112已按资源种类分组并保留真实1匹配/6必要缺口/1可选，未照搬9/4/5。机器人形象、导航编排、目标标签化、资源表密度及后续生产/责任分配操作与效果图仍有差别，交Human验收决定，不追加润色。

保持原Session OPEN / HUMAN_REVIEW_PENDING、唯一#183 Draft。旧2b8e66f及全部历史证据保留；真实模型关闭，不启动增量二，不改变父PR，不Ready、merge、部署或关闭。


### 10.12 Human前段接受与来源标识核对（2026-09-18）

Human有界接受前段布局改善；全链路最终视觉验收待规划截图审阅，Session仍OPEN、唯一#183仍Draft。前段证据必须分组：s5-321-understanding/V322为供应商质量（来料改善）UI fixture；s5-323-visual同案例测试为采购UI fixture；真实HTTPS/PG规划为既有采购计划历史。共享采购标签曾错误覆盖供应商质量截图，旧图保留为历史且明确其标签错误，不宣称同一案例端到端或真实模型旅程。后续fixture构建使用不指定业务案例的通用UI模拟标签，案例从各测试输入/回执识别；规划独立标记采购历史读回。

共享导航“v0.3 能力建设中”起自71937ef（253中文产品体验），指向/dashboard#planned，属于历史规划入口，不是本次版本归属。只将导航文案改为“查看规划能力”，保留链接、键盘焦点、授权、确认、UNKNOWN及模型输出真实性，不修改ROADMAP或首页能力定义，不增加视觉润色。

保留f65aeb1/tree 9f6311f对应的现有规划同屏、任务展开、资源缺口三图。新候选只改变上述导航文本；新增截图仅在323独立服务读回同一既有采购记录，不创建业务数据、不调用模型。新source/tree、构建hash、逐图候选身份及新候选CI在原visual manifest与PR登记，旧截图不得重标为新候选原始截图。

本轮实际验证：frontend lint/build通过；39项交互通过（26.9s）；make check 1917 passed / 201 skipped / 1 warning（92.31s）。新规划截图只读原Plan/history，history与原回执相等；116张表中，登录session/nonce各增加2，authorization_admin.audit_events增加2（均为SESSION_CREATED/COMMITTED/AUTHENTICATED），其余113张表计数不变；业务/模型/执行计数未变。历史补问invocation读回返回AUTHORIZATION_NOT_FOUND，未修改授权或重发调用，沿用旧候选补问图并单独标注，不把它算为新候选补验通过。最终以所请求的目标/任务/确认同屏、任务用途展开、资源缺口三图交Human审阅。

### 10.13 Human有边界视觉接受登记（2026-09-18）

本节依据Human本轮明确决定，更新10.11/10.12中仍待采购规划视觉审阅的状态，不改写历史记录。原文：

> 接受当前固定候选的采购规划主体及本增量有边界视觉表达；
> 当前候选历史补问缺图延期补证，不以旧图或 fixture 替代；
> 已确认态引导文案作为非阻断后续项。
> 此次不授予全链路业务验收、Ready、合并、部署或 Session 关闭，
> 保持 Draft／OPEN。

接受仅绑定产品Source `9b5b342245b8c6d56ee77d66bf80d8a134f02bfa` / Tree `31d0ecd4dc063c739813ad7703724cdb37a9a681`。本轮开始只读核对本地HEAD/tree、干净工作树、唯一#183 head均相符，PR OPEN/Draft；该候选12项CI均SUCCESS。原CI checkout与tree关系保留在外部`visual/ci-checkout-audit.json`，不挪用于后继治理提交。前段布局既有Human有边界接受继续保留；采购规划主体及本增量视觉表达现为Human有边界接受，绝不是全链路业务验收通过。

当前候选采购历史必要补问截图仍缺失，既有`AUTHORIZATION_NOT_FOUND`事实保留：延期补证，未永久豁免。本轮不重试/绕过，不用旧候选图、供应商质量fixture或独立采购fixture替代。已确认态仍显示“先核对目标与方案，再确认计划”是非阻断后续项；建议后续统一改为“计划已确认，可查看任务、资源缺口与历史；执行尚未开始。”本轮不修改产品代码。

证据继续使用原验收目录`/Users/tristan/Documents/s5-v023-arch-323-acceptance/visual/`的`visual-capture-manifest.json`、`control-continuation-screenshot-matrix.json`、`label-real/02-goal-and-plan.png`至`07-scroll-1366.png`。A供应商质量UI fixture、B独立采购UI fixture、C采购HTTPS/PG受控provider既有历史互不拼接为同案真实模型旅程。`control-continuation-receipt.md`是派生回执，其旧“等待Human决定”由本节决定取代，不构成新权威台账。

本轮仅更新本计划及Registry的323登记。治理提交及其新Tree、更新后PR HEAD另由原PR和派生续接回执登记；不得声称治理Tree仍等于上述被接受产品Tree。产品接受不自动扩展到新产品变更。保留旧功能候选`2b8e66f350ac91be83f8c8ac4263692a1d17ce07`及全部历史证据。Ready/merge/deploy/Session close仍NOT_GRANTED，Session OPEN。

### 10.14 本轮收口核对

| 分类 | 事实与依据 | 对收口的实际影响 |
| --- | --- | --- |
| 已实现 | 10.7–10.12：增量一受控建议/必要补问、exact Problem/Criteria绑定、不可变proposal、资源缺口、原子Plan/Approval/source确认、刷新/重启读回、PC统一及来源标识 | 工程实现已交付；不能据此宣称真实模型稳定或执行完成 |
| 已有验证 | 10.10–10.12：lint/build、39项交互、21项工作区历史回归、1917 passed/201 skipped/1 warning、HTTPS/PG历史与副作用回执；9b候选12项CI成功 | 本轮复用，非本轮重跑；后继治理CI单独关联 |
| Human已接受 | 10.12前段布局；10.13采购规划主体及当前增量有边界视觉表达 | 本增量视觉决定已完成，不重复要求同一决定 |
| 非阻断后续 | 已确认态引导文案；10.11既有274字面量测试债务；未获新增润色授权 | 不阻断本次有边界视觉接受；保留责任与后续处理 |
| 延期补证 | 当前候选C来源历史补问缺图，AUTHORIZATION_NOT_FOUND | 已获明确延期，不再作为要求重作视觉决定的理由；未永久豁免，后续补证需有效读权限与约定候选 |
| 实现验收尚缺 | 第5节明确“真实AI建议接通”需另行授权真实模型证据；本轮11节查出正式规划provider接线缺口、真实质量NOT_MEASURED | 阻断无约束的真实AI接通/完整增量一验收声明，不能用fixture顶替；后续须授权补齐或明确有界验收处置 |
| 增量二前置 | 第6节及D3：同Run多Task契约、真实资源、执行/结果验收接线未完成 | 不追溯阻断已接受的增量一视觉；阻断启动/宣称增量二闭环 |
| 任务关闭与发布 | 全链路业务验收、Ready、合并、部署、关闭均未授予；相应DoD/集成门禁须届时核对 | 本轮无自动关闭条件；Human后续分别决定实现验收边界、延期补证归属、集成与关闭，不捆绑为视觉再验收 |

## 11. 真实AI主线只读核对与后续建议（2026-09-18，PROPOSED非实施授权）

### 11.1 核对基线与直接结论

以下基于10.13固定产品source，读取当前源代码及既有证据；未启动服务、读取凭据、调用模型、创建数据、派发任务或重新运行质量评测。源路径相对仓库根；后端缩写B=`console/backend/src/agent_console/`，前端F=`console/frontend/src/`。测试存在不等于本轮执行，静态接线存在不等于部署已配置。

- **不能确认真实AI已稳定提问/理解/拆解。** 理解与补问已有真实provider适配能力、v2提示策略及校验；321既有Q01–Q16质量仍NOT_MEASURED。规划调用框架存在，但当前正式启动未注入具体provider，323运行证据仅CONTROLLED_TEST_PROVIDER。
- **当前323没有完成实际任务分配。** 模型/受控provider给出Task、角色要求及可选Definition引用；owner验证不等于绑定员工Instance/Task Assignment。D3接线尚待实施。
- **模型接入分段成立。** `/work`草稿理解可由运行profile接OpenAI/Kimi；当前部署是否配置/可用本轮未读取运行配置，不作肯定。planning-v2的正式`app.py`仅传`planning_v2_enabled`，未传`planning_invocations`；仓库具体`PlanningInvocationDependencies(...)`构造只见323验收服务器。不能声称当前产品完整模型主线已接通。
- **已有同案证据到受控采购规划确认及持久历史读回。** 前段供应商质量/独立采购fixture不能与C历史拼接。真实模型从问题到计划的同案证据、该计划到执行和业务结果验收都未建立。平台另有执行基础，不能写成“全平台没有执行实现”。

### 11.2 逐段实现、接线与证据矩阵

| 环节／产品入口或接口 | 核心文件及函数 | 输入→输出 | 当前主线接线与实现分类 | 模型／确定性责任、数据来源 | 持久化／权限／生命周期 | 既有证据与断点／补齐 |
| --- | --- | --- | --- | --- | --- | --- |
| 问题输入 `/work` | F`problems/ProblemWorkspacePage.tsx`，`beginDraftAssistance`调用 | 用户原文/纠正消息→版本化当前会话输入 | 已接入；`VITE_PROBLEM_DRAFT_ASSISTANCE=enabled`控制辅助入口 | 人工原文；禁用时人工草稿，不是假模型fallback | session/CSRF、上下文epoch/迟到响应隔离；未确认不建Problem | 321及323交互fixture覆盖；非真实语义证据 |
| 模型调用 `POST /api/workbench/v1/draft-assistance/invocations` | B`app.py`启动组合、`draft_assistance_bootstrap.build_draft_assistance_composition`、`DraftAssistanceService.begin` | content+exact profile/binding→Invocation/result | 真实adapter已实现且有条件接入正式启动；部署实配未知 | OpenAI/Kimi或显式synthetic transport；结果不得静默换mock | scoped grant、exact model binding、预算、幂等、PG调用元数据及Use/Evidence | 319/320 HTTPS mock、321验证；未找到已完成当前真实质量运行凭据，不推定不存在其他外部运行 |
| 必要补问/理解 | B`draft_assistance_policy.policy_for/validate_result`；OpenAI/Kimi transport prepare/send | 用户消息→NEEDS_CLARIFICATION或DRAFT_READY+understanding | 草稿路径已接；真实稳定性未验证 | v2提示要求只问1–2必要问题、保留未知/冲突/纠正；结构与引用规则确定性校验，不能保证模型语义 | invocation/turn lineage；补充产生受控后继，不自动创建业务对象 | 321 Q01–Q16未测；当前历史C补问读回权限拒绝不重试 |
| 纠正与确认创建 | F`ProblemWorkspacePage.tsx` create/update流程；B`business_problem_application.py` | 最新用户确认草稿→正式Problem revision | 已实现/当前入口已接；已有独立受控后端创建读回证据 | 模型建议不具有确认权；用户编辑与确认决定正式输入 | 一次显式确认、幂等、trusted actor；创建与独立READ授权分开 | 321既有真实PG+HTTPS但provider为fixture；与323 C不是同案完整旅程 |
| 目标/完成标准 | F`ProblemWorkspacePage.tsx` `saveCriterion`；B`plan_suggestion_application.current_input/validate_target` | 正式Problem+Criterion/CriteriaSet→exact planning target | 人工标准路径已接；非模型自动发布标准 | 规则取当前ACTIVE Problem、最新标准集与digest；Human确认标准 | 独立Criteria权限、revision/CAS、stale target拒绝 | 323 target/stale确认测试；正式新问题到ACTIVE/标准授权前置需在同案验证中覆盖，不能假定一步自动完成 |
| 规划必要补问与拆解 `planning-v2/invocations` | F`planning/PlanningEntry.tsx` `generate`；B`PlanningSuggestionService.begin/read`、`plan_suggestion_api.install_planning_invocations` | target+answers+predecessor→questions/typed proposal | 框架与UI已实现；正式app缺provider注入；验收server已接受控provider | provider提建议；`PlanningProviderResult`及`PlanSemantics.validate_graph`验证exact target、引用、无环、采购三阶段五Task线性依赖；非真实模型生成证据 | PREPARE/INVOKE_MODEL、预算、claim幂等、不可变revision；真实开关默认false | `test_plan_suggestion_invocation.py`、`test_plan_suggestion_v2.py`、323受控PG历史；补真实planning adapter/profile/prompt/调用组合及质量验证 |
| 数字员工/能力匹配 `planning-v2/{id}/resources` | B`PlanningResourceResolver.resolve`、`EmployeePlanningReader.observe`、`digital_employee_definition_postgres.read_for_plan` | requirement.selected→owner observation/snapshot | Employee reader已接；其余kind无reader为UNKNOWN；不是Task分配 | 受控provider/未来模型可提精确引用；owner检查scope/READ/已发布revision/digest；`PublishedRoleMatcher.match`另有实现，未由323resolver调用 | 不写Instance/Assignment；缺失MISSING、不可读UNREADABLE、不可用UNAVAILABLE/UNKNOWN分开 | owner测试和真实1匹配/6必要缺口/1可选；不证明能力覆盖、运行可用性、Skill/MCP授权齐套；补owner eligibility及D3绑定 |
| 计划确认 `planning-v2/{id}/confirm` | F`planning/PlanningPage.tsx`；B`PlanningApplication.confirm`、`plan_suggestion_postgres.confirmation` | exactproposal/digest+expectedversion+key→Plan/Approval/source | 已接入且有受控HTTPS/PG验收证据 | 规则原子确认；不自动调用模型、不执行；资源有缺口仍允许保存计划 | APPROVE、trusted actor、CAS/幂等、事务rollback、immutable history | 并发重放/rollback/CSRF/owner/刷新重启证据；缺口不在确认时强制齐套是设计，不能宣称ready |
| 执行派发 `/api/internal/v0.2.3/executions` | B`GovernedExecutionApplication.start`、`ExecutionApplicationService.start`、`native_dispatch_application.py` | exactapprovedplan+Assignment/Instance/Skill binding→Run/Task/Attempt/dispatch | 平台实现已有；未接323planning-v2；同Run多员工协调未完成 | 规则鉴权/批准/operation校验，Skill/Native负责effect；模型不直接派发 | START及INVOKE_SKILL、scope/exact绑定、单slot、unknown不重发 | 310/316/317与execution/Skill测试为基础证据，非323五Task真实运行；start identity seed含task_id，不能逐Task重复start冒充同Run |
| 状态/结果/Evidence读回 | B`GovernedExecutionApplication.read`、`execution_application` outcome/completion record、resource_use；F`evidence/EvidenceCenterPage.tsx` | exactRun/Task/Attempt→观测/Use/Evidence | 平台读回基础已实现；323展示execution_status=NOT_STARTED，未接五Task进度 | 来自owner执行事实，不能从Plan/资源声明生成成功 | 独立READ、append-only证据、attempt lineage、未知保留 | 平台测试/历史非本案；补stage聚合、任务产物I/O及重启reconciliation |
| 业务结果验收 | F`outcomes/OutcomeCenterPage.tsx`；ARCH-264契约 | terminalRun+Criteria/Evidence→Evaluation→HumanConfirmation→Outcome | 当前页面明确NOT_CONNECTED、旧v0.2.1上下文；323主线未实现闭环 | 系统评估与Human业务确认分离；技术completion不是解决问题 | terminal gate、exact evidence、Human actor及否决历史待接线 | 原增量二I2.5明确需新增typed services/repos/API；不能以旧outcome或批准代替 |

完整源文件是实现依据。正式构造搜索覆盖仓库Python源/测试，`PlanningInvocationDependencies`只在323 browser server实例化；它不是可用真实provider的隐式默认值。旧`problems/ProblemPlanningPage.tsx`的v0.2.1“实时AI辅助”独立入口也不能替代当前`/work`接线证明。

### 11.3 模型调用与分配专项约束

配置引用已存在：`DRAFT_ASSISTANCE_RUNTIME_FILE`指定运行profile，内含provider/model/endpoint/connection/adapter/schema及credential引用；`VITE_PROBLEM_DRAFT_ASSISTANCE`控制前端；`PLANNING_V2_ENABLED`只启用规划owner操作。未读取secret/令牌值，未核实当前运行文件内容。真实adapter准备请求时绑定v1/v2策略、structured schema、输入/token上限；321前端不是单纯美化，它传递版本化用户事实及纠正，后端v2理解策略已存在；323后续PC视觉改动本身没有新增模型接线。

Draft transport有connect/read/total timeout、响应体上限及错误/UNKNOWN处理，Kimi还有受监督worker期限/回收实现；320历史A05接受记录仍有未证义务，321后继deadline测试/修复记录并存，不能以旧登记断言当前代码无监督，也不能以一次mock测试证明真实provider全链期限可靠。后续真实调用授权应明确采用的adapter候选和期限证据。服务保留幂等claim、预算reservation及上下文Use/Evidence；未知不自动重发，显式恢复/后继有独立语义。synthetic与LOCAL_HTTPS_MOCK有标签；未见“真实失败就以mock成功顶替”的合法路径。

Planning profile与provider协议已存在，但没有具体真实transport配置/提示词组合落地；`provider.suggest`为同步注入接口，服务捕获TimeoutError/ConnectionError并记OUTCOME_UNKNOWN。没有由该接口框架自行提供的完整网络deadline/retry guarantee；具体transport、输入输出语义与审计还需补齐，不能把draft transport直接等同planning已接。真实开关false；本轮未改变。

AI/受控provider提出的是建议与角色要求，可携带候选Definition引用；资源owner确认引用事实，Human批准计划。只有未来经D3校验的Instance/Task Assignment与运行准入才构成实际分配。当前Employee read_for_plan只保证授权、scope、published和digest，不等于PublishedRoleMatcher能力覆盖或Instance可用性。必要资源缺口应阻断未来执行准入；当前323没有执行按钮/派发路径，允许确认待准备计划并不绕过执行门禁。

稳定性证据分类：信息充分、信息缺失、歧义/冲突、用户纠正已有321策略与模拟交互；权限不足已有授权拒绝/身份隔离测试；资源不足已有323owner/缺口测试。以上均不能升级为真实模型语义稳定性验收。后续建议固定模型/profile/prompt/schema、预先标注的六类用例及多轮纠正样本，分离结构合法率、事实/数字/时间保真、重复补问/遗漏率、纠正保留率、任务依赖与资源幻觉、人工修改量；固定预算与重复次数、逐例保存可披露结果和exact调用证据，报告分母/失败/未知，不只展示成功样例。321 Q01–Q16可复用为草稿质量基线；规划补充同案任务与资源oracle。阈值、样本量及调用预算待Human接受，本轮无新增评测。

### 11.4 增量二最小方案（PROPOSED）

原定义是第6节“同一计划只读执行和结果验收”，含I2.1–I2.6；D3是第3节中同Run多Task/多员工契约的方向，详细契约延期至增量二实施前。延期原因是增量一只需要建议、Definition引用和确认，不需要实例分工/执行；D3的root/Task Assignment、terminal聚合、I/O、retry/pause fencing需先定型。D3不是另一个已完成实现，也不等同全部增量二；本轮没有启动或实施授权。

建议按以下依赖顺序，不改变v0.2现有归属或重开CLOSED架构任务：

1. **先补真实提问/拆解接线，作为增量一真实AI接通缺口。** 复用319/321 draft profile/adapter/策略、323typed proposal与调用审计；补正式planning provider/配置组合、版本化规划提示与输出校验，固定同一个Problem/Criteria。Human先给精确provider/model/endpoint/profile、用途、数据范围、credential受控引用、预算/时间窗和调用授权，再开展同案真实质量验证。此项不能藏进“已完成视觉”的结论，也不通过另一个fixture补齐。
2. **确认D3并补任务分配。** Human接受有界root/Task Assignment契约；复用published employee/Agent/Skill/MCP/Workflow owner与matcher，将角色要求落到最多2类职责的实际实例、精确能力和有效分工，验证发布、权限、capability/schema、trust/availability；资源不足允许计划待准备，执行fail-closed。业务确认、资源发布、实例创建、分工与启动各自独立授权。
3. **场景与边界。** 延期采购订单分析：一个只读订单来源/固定schema，三阶段五Task（快照→日期校验→延期计算→供应商汇总→清单），最多两职责、线性链。起点是同案已批准exactPlan且资源就绪；终点是一个terminalRun、可读清单/异常/来源证据、Criteria评估及Human确认/否决。前段真实问题理解作为前置同案证据串联。范围外：订单写回/通知、动态DAG/循环、通用调度/资源工厂、全部72页、生产发布。
4. **执行接线。** 复用Execution身份、single Skill slot、Native handoff/Placement、授权、Postgres及已有operator readiness算法；补同Run coordinator、持久依赖与artifact I/O、每Task effect owner，禁止Native和同步Skill双派发。不能对五Task各调用旧start生成五Run。
5. **结果与恢复。** I2.4聚合真实Task事实和有界产物；I2.5按ARCH-264实现terminalRun→Evaluation→HumanConfirmation→Outcome；I2.6重启读回、retry新Attempt、未知不重发、pause request/ack分离。执行和结果验收本来就在增量二，不另假定范围外。
6. **同案验收。** 逐段绑定Problem/Criteria/Invocation/Proposal/Approval/Assignment/Run/Task/Attempt/ResourceUse/Evidence/Outcome精确ID与digest；真实授权只读来源、真实模型、真实Skill分别证明，不相互替代。五Task产物对第4.4节R1–R5 oracle；正常、缺失日期、权限拒绝/撤权、资源不足、timeout/unknown、并发start、故障恢复、Human否决都有独立期望。刷新和重启不新增effect。真实模型质量另按11.3测量，工程用例通过不是质量稳定证据。
7. **必要授权与门禁。** 先恢复届时main/现有集成状态与共享路径ownership；Human明确D3接受、增量二G1实施范围、必要资源准备归属、模型调用包、只读数据/执行与验收授权，再按既有治理流程安排实施。没有任何新Task编号在此自动创建；不授予Ready/merge/deploy。若需要改变Accepted架构或增加基础设施，走G2，不能在323悄然扩大。

### 11.5 72页管理设计与主线依赖（PROPOSED）

已找到本地完整设计包`/Users/tristan/Downloads/Resource-Management-PC-72-Pages/`：72张`pages/*.png`、`PAGE-CONTRACT.md`、`coverage.csv`、`IMAGE-MANIFEST.json`、`IMPLEMENTATION-ORDER.md`及`index.html`。已读取页面契约/目录/实施建议；这是2026-09-18目标设计与合成数据，页面编号不是Session编号，不代表功能已实现或获授权。仓库依据为CONTROL-254的Complete Product page inventory（数字员工、Skill、MCP、Knowledge、Workflow等）及PLAN-003模型候选/确定性权威边界；PLAN-001/003早期CURRENT段不是当前源码替代。

A=主线必需的能力切片（不要求先完成整页），B=可并行的非阻断管理体验，C=后续完整管理能力。下面是现有文件/契约层核对，不声称72页逐控件验收。

| 模块／设计依据 | 已有实现与前后端契约 | A 首批依赖／缺口 | B 可并行 | C 后续完整能力 |
| --- | --- | --- | --- | --- |
| 数字员工 D01–D12；重点D04/D07–D11 | F`digital-employees/DigitalEmployeesPage.tsx`、B`digital_employee_*`、`workbench_employee.py`；Definition/Instance/Assignment与授权有现有owner | P0：D04精确能力版本与缺口、D08/09实例和有效Task分工、D11真实Placement；补323到D3映射，不把role卡当Assignment | P1：D05验证呈现、D06版本差异/引用影响、D10任务返回入口 | P2：完整AI创建向导、部门管理与D12批量生命周期；不自动生产员工 |
| Skill S01–S12；重点S03–S09/S11 | F`resources/SkillWorkbenchPage.tsx`；B`skill_mcp_*`、`skill_invocation_*`、`skill_executor.py`，定义/生命周期与调用owner分离 | P0：采购R2–R5真实规则、schema、eligible exactrevision与只读执行、S11实际Evidence；具体采购资源是否齐备未证，当前有缺口 | P1：S07/08测试用例/失败呈现与S10差异；发布门禁必须有，完整UI可后补 | P2：批量导入/克隆/导出、完整AI辅助生产；图中测试通过不是真实发布事实 |
| MCP M01–M12；重点M03/04/07/08/11/12 | F`resources/McpWorkbenchPage.tsx`复用ResourceWorkbench；B`skill_mcp_*`与endpoint/trust相关owner；连接/发现/选择和调用独立 | P0：一个真实只读订单tool，受控credential引用、trust/schema/授权与exact选择、unknown诊断/Evidence；planning owner reader尚未接 | P1：M09诊断/发现差异/引用影响视图 | P2：M05 Resources/M06 Prompts完整发现管理及多connector；不得因Tools已有就宣称两类也完成 |
| Knowledge K01–K12；重点K08/09/10/11 | F`resources/KnowledgeWorkbenchPage.tsx`、B`knowledge_*`；源/revision/索引/检索能力，页面明确workbench retrieval非Attempt Evidence | 场景实际引用Knowledge时为P0：精确已发布source/index、授权检索与可追溯citation；若原采购方案无必需Knowledge则不额外阻塞（需Human确认资源范围） | P1：K08/09来源定位、K10差异与引用；已有检索不代表该Task采用 | P2：K03–K07完整PDF/DOCX解析/预览、批量任务、企业连接器与清理策略；保留后续完整性要求 |
| Workflow W01–W12；重点W04–W06/W08/W09/W11/W12 | F`workflows/WorkflowWorkbenchPage.tsx`/Builder，B`workflow_definition_*`/`workflow_control_*`；现有定义、binding与批准基础 | P0：exactPlan绑定、五Task依赖/I/O、D3准入、同Run事实、恢复/干预与结果；当前323确认不派发 | P1：W03编辑体验、W10版本对比/引用影响 | P2：W07通用条件分支/汇合及完整模板/AI定义管理；本切片仍线性 |
| 技术Agent A01–A12；重点A04–A11 | F`resources/AgentWorkbenchPage.tsx`/AgentBuilder及RuntimeProfileWorkbench；B`agent_definition_*`、model governance、Native/Placement；定义/资源精确binding已有 | P0：所选路线确需的模型profile/运行profile、Agent/员工/Assignment关联和真实观测；模型adapter与Agent配置不可混为一项 | P1：A07验证报告、A08版本影响、A11关联任务与A12unknown诊断可见性 | P2：全套AI定义生产、批量实例控制与完整运维；不能承诺暂停能撤销已发请求 |

优先级按真实主线依赖，不按72图顺序机械开工；A中能力有现成合格owner时复用，只补真实接线/证据，不重复造后台。每次后续实施须引用页面ID、tab、状态转换、exact对象、授权和契约；完整创建/编辑/测试/发布/生命周期仍留在后续规划，不因本次最小闭环删除。

## 12. 正式规划接线增量（2026-09-18，Human授权G1）

本轮Human授权原323/原分支/唯一Draft #183补正式provider接线、必要配置/前端/测试、隔离受控验证及D3草案；正常提交/non-force push。基线1132b641445a4c2286c4d21e90d3ea0e597bf9c1/tree92041a19c99f95afd8664cda4a8504be48a7e767与PR一致、工作树干净。原9b产品视觉接受不自动扩展至新行为。禁止外部真实模型/付费、生产/321/共享环境改动、实际实例/派发/资源生产、增量二执行及Outcome实现、Ready/merge/deploy/close。历史AUTHORIZATION_NOT_FOUND不重试，文案不顺改。

实施映射：复用PlanningSuggestionService及现有typed Proposal/target/授权/幂等/PG原子确认；复用Responses连接配置、exact Model治理、凭据resolver、预算owner；增加明确PLANNING_RUNTIME_FILE、规划purpose的版本化prompt/schema和Responses输出投影，在app正式组合注入。测试provider仅由测试依赖替换，正式配置缺失/禁用/失败均fail-closed，无fixture fallback。保留unknown资源；补问与纠正始终使用最新exact Problem/Criteria，旧target拒绝。复用预算基础且规划使用独立ledger/profile，不能消耗draft授权。

验证：正式app组合入口受控装配（无网络外呼）覆盖配置/未配置、完整/补问/后继、过期target、非法结构/依赖/引用、权限/UNKNOWN/错误/超时及幂等；复用并按变更范围执行现有规划PG确认零执行回归；make check及正常hooks，前端若改则lint/build/针对交互；新CI逐候选登记。真实质量保持NOT_MEASURED。D3及真实调用包另列PROPOSED，不实施执行。

### 12.1 正式调用路径与配置边界

`app._configure_workbench`读取显式`PLANNING_RUNTIME_FILE`，仅在`PLANNING_V2_ENABLED=true`时装配；`build_planning_runtime`→`PlanningInvocationDependencies.bind`→`install_planning_invocations`→`PlanningSuggestionService.begin`→`PlanningResponsesProvider`→既有`OpenAIResponsesDraftTransport.exchange`。网络交换从既有adapter提取复用，草稿dispatch保留原策略/解释语义；本轮正式规划支持`OPENAI_RESPONSES_V1`协议，不自动认定任意兼容endpoint或Kimi已验证。未选实际供应商/模型。Kimi draft adapter仍是问题理解路径，不自动当作规划adapter。

`planning-runtime.v1`复用现有runtime配置字段（scope、profile/model/provider/endpoint/connection精确revision/digest、Responses地址、nativeModelId、限额、credential引用/file、TLS、预算和commitment pepper引用）；规划另要求`outputSchemaVersion=plan-suggestion-output.v1`、`targetFormatVersion=plan-suggestion-target.v1`、`policyDigest`匹配`plan_suggestion_policy.POLICY_DIGEST`、adapter revision v1、显式boolean `realCallsEnabled`。配置样例见同目录`S5-V023-ARCH-323-PLANNING-RUNTIME.example.json`，全部身份/地址/价格为占位，realCallsEnabled=false，不能直接作为调用授权或生产配置。Planning与Draft必须使用各自profile/ledger及purpose精确grant。真实endpoint与Model owner中的native model/connection/限额逐项匹配后才能调用；没有发布资源reader时prepare snapshot为空，不生成假目录快照，后续owner刷新维持UNKNOWN。

本轮复用PostgresProviderCallBudget，每次按包含完整prompt/schema的输入字节保守上界及最大输出预留；规划暂不基于provider usage释放预留，仍报告NOT_COLLECTED，不把缺失usage记零。该ledger不是供应商账户级账单硬上限。当前共享Responses网络交换保留既有connect/read/total配置及歧义失败边界；并不宣称具备Kimi监督worker的全阶段硬墙钟回收保证，真实调用包必须接受或先补齐此限制。无自动重试，无fixture fallback。

诊断记录保留purpose、exact target/profile/model/provider引用、配置model名称、transport class、policy版本/digest、output契约及调用id；不新增正文/credential/原始response日志。错误只保存固定reason code；网络歧义OUTCOME_UNKNOWN、provider拒绝FAILED、业务结构非法INVALID，均不产生批准/执行。当前上下文及授权在dispatch前复核，完成时再次校验target；晚到过期结果不得写成新proposal。补问传上轮问题和累计回答，source successor传经授权的旧proposal与当前exact target；旧Problem/Criteria不继续作为当前规划输入。

### 12.2 真实调用授权包（PROPOSED／本轮不执行）

| 条件 | 具体提案与状态 |
| --- | --- |
| Provider/model | 已有可复用协议：OPENAI_RESPONSES_V1；本轮规划适配支持此路径。实际provider、nativeModelId、Model/provider/endpoint/connection精确revision/digest、adapter资格及有效价格均未给定，不自行选定付费模型。既有Kimi问题理解配置不推定规划兼容；若选择Kimi须先补对应规划适配与受控验证。 |
| 配置与权限 | 显式PLANNING_RUNTIME_FILE、独立planning profile及ledger、精确PLAN PREPARE/READ与MODEL_GOVERNANCE INVOKE_MODEL（purpose plan-suggestion）、Problem/Criteria独立READ；credential仅由既有resolver按引用在获授权调用时解析。本轮不读取真实配置/凭据。Human需确认身份、用途及授权到期；缺任一项保持关闭。 |
| 隔离 | 后续独立323模型验收进程、loopback端口及专属测试DB/认证配置/日志目录；不挂321或生产目录，不复用旧采购历史作为新数据。当前接线测试容器s5-v023-arch-323-wiring-pg只含测试fixture，不自动转作真实调用环境。 |
| 数据 | 建议只用人工可审阅的合成采购Problem/Criteria、日期/数量/单位/公司范围和假资源标识，不用生产订单、企业正文或个人信息。prompt/schema及所有上下文共同计入输入上限。任务计划不读订单、不调用资源。 |
| 案例 | 信息充分：保留全部事实且合理拆解；缺信息：只问必要问题并保留未知；歧义冲突：指出冲突，不擅选；纠正：新exact版本和否定事实生效；资源不足：提出需求但不编造引用/ready；权限不足：前置确定性拒绝且provider dispatch=0，不请模型判断权限。每类至少2个固定场景。 |
| 分级证据 | 单次smoke只证明一次接通：一个合法结构、exact lineage、真实Use/Evidence、无effect。质量阶段：六类案例逐例按事实/补问/纠正/任务依赖/资源幻觉rubric打分，所有权威/副作用硬边界须100%满足，建议语义case通过率至少90%，不通过项保留。稳定阶段：同10个可调用case各重复3次，分别报告成功率、类别一致性、补问差异、延迟及失败/未知；建议至少27/30通过且无越权/假引用/未经确认执行，不承诺零错误。阈值由Human接受。 |
| 次数/token/费用 | 建议分阶段单独放行：smoke最多1次/$1；质量最多20次（10个可调用case，各最多2轮）/$4；稳定最多60次（10case×3次×最多2轮）/$12。权限不足case不分配模型调用。单次完整输入保守上界32768 tokens、最大输出4096；合计最多81次、输入2654208/output331776 tokens、总$17，仅为待批准上限而非预计花费。实际价格未确定前无法配置可信预算，不执行；保守预留可能更早耗尽。原321预算不能挪用。 |
| 停止条件 | 任一权限/版本/秘密泄露/外部effect违规立即停止；UNKNOWN不自动重发；达到任一call/token/cost限额、grant失效或连续2次provider技术失败停止；结构/语义失败保留结果，不用mock补齐。若全阶段硬timeout是Human前置条件，先补其实现/受控证据，不直接开展真实调用。 |
| 窗口 | 建议Human批准后另定一个明确起止、最长8小时窗口，并让exact grants到期同步；分别批准下一阶段，不默认串行消费全部预算。本轮没有生效窗口。 |
| 持久化/清理 | 需Human明确允许测试记录写入：专属DB中的合成Problem/Criteria、model配置元数据/授权、planning invocation/proposal、contextual Use/Evidence、预算预留；计划确认测试若批准则增加Plan/Approval/source。无Assignment/Run/业务订单。证据导出脱敏manifest与逐例评分，建议保留14天或至Human审阅完成后另行批准清理；不自动删旧历史，不清理321。 |
| 已具备/待决定 | 已有治理/结构/调用基础与受控接线测试；待决定具体模型及精确配置、兼容性、费用、数据、隔离环境、记录写入/保留、时间窗、质量阈值、timeout限制和各阶段调用授权。服务可配置不等于已获调用许可。 |

### 12.3 本轮验证及门禁记录

- 正式app→真实Workbench组合→Planning服务→Responses网络边界替身：最初13项通过，加入当前Problem/Criteria纠正后继、CSRF和配置策略拒绝后为16项；与真实独立PG runtime/预算测试合跑17 passed（4.87s）。网络/认证与部分owner为显式测试依赖，不能冒充真实模型或生产部署。
- 规划typed/owner/invocation/确认PG回归、原Responses adapter和Workbench组合回归：49 passed（145.14s，包含当时13项新装配测试）；原子确认重放、rollback、缺口及无执行边界保留。新PG预算测试验证正式runtime初始化、scope适配、重复预留同结果、超限拒绝、零provider dispatch。
- frontend lint PASS；交互配置自动执行TypeScript/Vite build PASS（既有bundle提示），41 passed（35.3s，包含2项新错误/多轮回答用例）。测试preview只在323专用端口19329，未使用321运行环境。新图是测试产物，原视觉接受仍绑定9b；不重标旧图。
- 两次make check的Ruff/format PASS，但pytest门禁失败，日志均保留：首轮1929 passed/201 skipped/2 failed；第二轮1932 passed/201 skipped/2 failed。首轮Kimi stalled-send提前CONNECT_DEADLINE、validation-race无请求到达；第二轮stalled-headers提前CONNECT_DEADLINE、parent-channel-loss接收超时。相关Kimi代码和测试与基线逐字未变；原因UNKNOWN，不能仅凭主机负载归因。首轮两个失败单独复核2 passed（4.60s），不将其替代全量门禁。
- 所有数据库测试位于新建`session=S5-V023-ARCH-323`、`purpose=isolated-wiring-test`的`s5-v023-arch-323-wiring-pg`（postgres:15，loopback随机端口59407）；fixture使用临时数据库并按既有测试teardown清理，仅测试数据。未操作原采购历史、321、生产或共享配置。
- 正常提交hook及新候选CI终态继续记录在原PR与外部`visual/wiring-*`回执，不跳过/弱化Kimi门禁；若hook拒绝则保留工作树、报告未提交/未推送，不宣称全部门禁通过。真实模型质量仍NOT_MEASURED，无外部/付费调用、任务执行或资源生产。

本轮最终门禁终态：第二轮两项失败单独复核2 passed（6.48s）；正常提交hook的Ruff/format PASS，但pytest仍1932 passed/201 skipped/2 failed（176.94s），失败为Kimi stalled-send及stalled-headers的提前CONNECT_DEADLINE。提交exit1，未生成新commit，未push，没有本轮新候选CI。停止重复运行，15文件保留暂存区；本地HEAD/远端PR仍1132b641445a4c2286c4d21e90d3ea0e597bf9c1/tree92041a19c99f95afd8664cda4a8504be48a7e767。可复核暂存Tree、patch/hash和失败日志在原external续接回执记录，不把暂存Tree当已提交Source。本轮受控正式接线验证完成，但整体交付状态COMMIT_GATE_BLOCKED；需先对既有Kimi期限门禁的环境/启动时序作有界诊断或取得其维护授权，不降低期限、不跳过测试、不操作321环境。

### 12.4 Kimi期限门禁诊断与最小修复（后续Human授权）

Human随后授权本地有界诊断、必要最小修复、正常验证/提交/普通推送及原Draft PR更新。本节接续12.3失败检查点，不删除其日志或把历史失败改写为通过；不改变320既有期限契约，不授权真实调用或D3执行。

- 起点实核：HEAD `1132b641445a4c2286c4d21e90d3ea0e597bf9c1`、提交Tree `92041a19c99f95afd8664cda4a8504be48a7e767`、15文件暂存Tree `712a7b25399d9987676a7d207212e34d57fb5ac1`完全吻合；PR同HEAD、OPEN/Draft；无旧commit/hook/pytest writer。原patch、截图及日志全部保留，无reset/clean/rebase。
- 契约：connect和total均在spawn前起算，connect包含启动至TLS完成；total覆盖全部阶段及父进程校验，边界相等时total优先，均不重置。独立1s清理预算仍fail closed。旧hook失败的send/headers只有IPC阶段，分别约1.008/1.004s即CONNECT_DEADLINE且worker已回收，不能证明进入了send/headers；该分类符合契约。
- 有证据的测试设计缺陷：spawn目标定义在整个测试模块中，child反序列化时重导入pytest及数据库/模型装配等非必要依赖，占用1s连接预算。一次全量时间线诊断1922 passed/213 skipped（未启用规划PG），实际到达send/headers时均按total终止。再以固定1.1s child装配模块导入延迟作有界对照：HEAD原测试两例均复现IPC/CONNECT_DEADLINE；相同延迟下轻量spawn目标两例及启动停滞回归3 passed。诊断脚本/时间线/前后日志保存在既有`visual/deadline-*`证据包；人为延迟不是历史主机负载测量。
- 最小修复仅限Kimi两个测试文件：`kimi_deadline_test_workers.py`搬迁既有fault targets，避免child导入整个测试模块；原六阶段增加精确failure_stage断言；新增启动停滞应为IPC/CONNECT的用例；HTTPS fixture停止等待并join非daemon handler，避免延迟线程跨fixture观察共享类状态。没有更改产品期限实现、数值、错误码、断言预期或provider fallback。
- 归因边界：原失败的直接条件是连接预算在目标阶段建立前耗尽；导入耦合通过受控注入复现。fixture未join是确切隔离缺陷，但没有证据证明它触发了历史IPC失败。未记录当时的调度/IO压力，不能把环境负载写成已确证根因。Kimi自行执行_dispatch_once/监督器，只从OpenAI模块取schema常量；新增planning分支的policy导入仅在planning=True时发生，不改Kimi默认profile路径。未发现本轮正式接线改变期限分类的间接回归，仍不声称穷尽所有主机时序因素。
- 验证：原Kimi套件49 passed（49.81s，JUnit属性格式警告），全部六阶段及三类local HTTPS的reaped/期限指标保留。修复后首次make check为1934 passed/201 skipped、1个新增测试配置错误（read>total）；更正该新用例read=1后，最终完整`make check`：Ruff/format PASS，1935 passed/201 skipped/1 warning（112.66s）。原send/headers、parent-channel-loss、validation-race、相邻回收及所有正式接线测试均包含在全量门禁内。不是单独通过替代全量，也不是重复运行同一失败候选碰运气。
- 正常commit hook和新候选CI必须继续按实际结果记录于原PR及`visual/deadline-delivery-receipt.json`、`deadline-ci-checkout-audit.json`，不使用旧候选12项CI替代。最终Source/Tree在提交后登记外部回执，避免提交自引用；本次新增测试文件使总交付变为17文件，不丢弃原15文件实现。
- 本轮仅重启并使用独立`s5-v023-arch-323-wiring-pg`，loopback随机端口50993，测试临时数据库正常teardown；原采购历史/321/生产均未访问。原frontend lint/build/41交互通过证据复用，Kimi修复未改前端；不是本轮重新运行。
- **正式规划Responses限制**：规划仍调用OpenAI exchange，未进入Kimi进程监督器。受控装配、非法输出/timeout到UNKNOWN和确认不执行已验证；socket connect/read timeout、连接后remaining检查及finally-close不等于全阶段绝对硬期限或1s kill/reap。本次没有证明规划DNS/send/慢滴流/父进程校验及回收硬界，也未验证真实模型质量/稳定性；如该保证是实际调用前置条件，需另行授权最小实现及故障注入验证。不得移植Kimi通过结果冒充规划保证。

补充CI终态与受控修复：首次正常提交/普通推送产生Source `19b8dee2fcbd7c4f50e9d089599cca366795ec44` / Tree `623398504d616ac82b1fe5e2cb1558bd1845c70b`，hook三项PASS；CI为11 SUCCESS/1 FAILURE。5项实际checkout该Source，7项checkout合并候选`a50a77a1140adae6dc2958a9cd934147a9dd6197`，Tree均为6233985；Kimi mock与Quality Gates均成功。唯一失败是本次新增规划错误态UI fixture用未编码`failed:323`匹配实际GET的`failed%3A323`，读回落到空result；此前本地断言可能在读回前通过。新增明确等待该GET并reload可确定复现失败，随后仅修fixture解码路径，保留等待/刷新断言，增加至少两次读回及唯一POST断言；没有产品行为修改、扩大超时或重跑失败CI碰运气。后继候选的本地前端lint/build/完整41交互、正常hook及新CI结果分别登记`deadline-frontend-lint-final.log`、`deadline-interaction-final.log`、`deadline-followup-hooks.log`与外部最终回执；首候选CI日志及checkout审计另存`deadline-first-candidate-*`，不覆盖为成功。后继Source/Tree随测试/治理文件变化，产品实现仍与19b8dee相同。

原产品视觉接受仍仅绑定9b5b342/31d0ecd；本次正式接线形成新产品候选，不自动继承新增行为接受。D3保持第13节PROPOSED，历史补问缺图延期、AUTHORIZATION_NOT_FOUND及确认态文案非阻断项不变。停止位置仍为正式接线受控验证完成、真实调用待授权、D3草案待审阅；Draft/Session OPEN。

## 13. D3详细执行契约草案（PROPOSED，待Human审阅；本轮不实现）

本节仅细化第6节增量二，依赖现有ARCH-019/208/258/259/263/264/266及D1/D2。既有架构决定：Execution层次与owner、exact批准、MCP trust/credential、单Skill slot、UNKNOWN不盲重发、terminalRun作为业务验收根；不重开CLOSED架构。以下同Run协调/Task Assignment/I/O细则是建议，尚未获批准，不能从“D3方向接受”推导实施许可。

### 13.1 来源、任务与角色

推荐一个已获授权的只读采购tool，固定公司/采购组织/日期范围、asOf日期及时区、字段白名单、最大行数与分页完整性。只允许读取订单号/明细/供应商标识/承诺日期/未交数量/单位/状态及来源revision；不读联系人、账户或其他生产敏感字段。实际endpoint/tool/revision/digest与范围尚待Human提供和授权；无合格MCP时BLOCKED_RESOURCE。冻结导出是原第4节允许的候选替代路线，但变更输入来源必须显式披露并确认，不静默切换。

| 阶段／Task | 名称／依赖 | 精确输入→不可变产物 | 推荐职责 |
| --- | --- | --- | --- |
| S1 / T1 | 读取快照；无前置 | 授权scope/asOf/schema、分页约束→A1 manifest、bounded rows、完整性/来源digest、MCP读取Evidence | E1采购分析员 |
| S2 / T2a | 校验数据；T1 | A1→A2有效行、缺失/冲突/重复/范围外分类、逐行lineage与规则版本 | E2数据核验员 |
| S2 / T2b | 识别延期；T2a | A2+exact Criteria→A3延期/未延期/UNKNOWN分区；promisedDate严格早于asOf且未交量>0，同日不延期 | E2数据核验员 |
| S3 / T3a | 供应商汇总；T2b | A3→A4 supplier分组，按unit分桶、行数及distinct订单可复算，不跨单位相加 | E1采购分析员 |
| S3 / T3b | 生成报告；T3a | A1–A4+Criteria/Evidence snapshot→A5清单/摘要/异常/局限/来源及digest；不生成无证据结论 | E1采购分析员 |

最多两职责。Definition表示已发布业务职责和精确能力引用；Instance是实际受管理员工；Task Assignment是该Instance对某个批准Task的scope/有效期/责任绑定。建议root Assignment归E1作为此计划协调责任，Task级分别引用E1/E2实例；root不赋予跨实例代执行权，E2任务必须独立验证其合法Assignment。该root/Task关系扩展是D3待Human明确接受项；不以复制五个旧start调用生成五Run代替。

### 13.2 准入、身份与生命周期

- **资源准入**：Employee/Agent/Skill/MCP/Workflow精确revision+digest、published/non-revoked、能力覆盖/schema兼容、scope/READ/INVOKE、MCP trust/tool selection、credential受控引用、实例/Assignment有效及所选Runtime readiness均分别核实；未知/缺失必要项拒绝启动。资源健康观测不改批准语义；更换资源/职责/I/O则生成successor Plan并重新批准。
- **Plan→Run**：同一scope、exactPlan revision/digest、Approval及显式start request key形成唯一admission记录，关联root及五Task Assignment、资源快照、Criteria。重放同key同payload返回原Run；不同payload冲突。批准不创建Assignment/Run/Attempt/Placement。Human准备实例/分工与显式启动分别授权；本轮不执行任何一步。
- **Task/Attempt**：复用Execution owner合法状态，不从UI自造终态；协调read model区分依赖等待、准入阻塞、运行中、成功、失败、未知和未执行。Attempt成功必须有匹配task/plan/attempt、schema/digest的产物及真实completion；只创建了invocation不算成功。每Task同时最多一个活动Attempt/Skill slot；依赖完成且输入artifact绑定精确后才可派发。
- **重试/幂等**：start/admission与每Task dispatch claim持久化；known failure允许经授权的只读retry，创建新Attempt并引用前一Attempt，不改历史。UNKNOWN先observe/reconcile原调用，禁止自动重复effect。late observation仅落原Attempt，不能污染后继。网络请求状态与业务完成状态分别记录。
- **I/O与报告**：A1–A5均有sourceTask/Attempt/Plan、schema/version/digest、输入artifact引用及来源证据；有界PG记录复用现有设施，不新增文件服务。每阶段成功要求全部required Task成功，不能用已生成报告遮盖前序异常/缺失。超过行数/产物上限明确失败/需缩小范围，不截断后宣称完整。
- **失败/超时/干预**：已知失败停止依赖后续；缺权限/资源为阻塞，不能由模型自批；未知保持待核实。暂停为request，协调持久fence/ack后才宣称停止后续admission，不能撤销已发请求。恢复复用原Run/Task和claim；Human纠正业务语义走successor Plan/Run，技术只读重试走新Attempt。
- **只读边界**：禁止采购写回、更新订单、发邮件/催交/通知、发布资源、创建生产实例、任意shell或网络fallback；Task只能调用批准operation。Native与同步Skill不得拥有同一次effect的双dispatch；T1通过Skill封装MCP时仍须记录实际MCP invocation/Evidence并保留trust authority。

### 13.3 Evidence、终态与业务验收

Execution owner持有Run/Task/Attempt与completion，MCP/Skill等owner提供可验证调用事实，canonical Resource Use/Evidence按ARCH-266关联实际使用，不拿resource声明充调用；Frontend仅投影。读回须独立权限、scope、exact identity，并披露未知/过期，不补造缺失证据。

推荐Run终态：required Task均得到确定终态或经明确终止处置且不存在未决effect；仍有OUTCOME_UNKNOWN时不伪称成功terminal。具体失败/取消聚合映射复用届时Execution合法枚举，D3实施前接受精确转换表。技术成功要求五Task成功、产物链完整；业务目标是否达成另按第4.4节C1a–C1f判断。

terminalRun后，按ARCH-264依次产生不可变Criteria Evaluation（exact criteria/evidence snapshot）、append-only Human确认或否决及后继Outcome；UNKNOWN/NOT_MEASURABLE不得填零。Human可以否决技术成功的报告并记录原因；未确认不自动标问题解决。验收不新增空执行Task/Attempt。相关typed service/repository/API/产品投影属于原I2.5后续实现，本轮仅提案。

### 13.4 待实现、验收与Human选择

| 类别 | 本轮建议 |
| --- | --- |
| 可复用 | 323 proposal/Plan/Approval、模型治理、published resource owners/matcher、Execution身份与幂等、Skill slot、MCP/Native、Placement、Use/Evidence与独立READ、PG事务 |
| 需补齐 | D3 root/Task Assignment与同Run admission/coordinator、Task输入输出绑定、真实采购R1–R5、exact资源eligibility、五Task进度/故障恢复、ARCH-264 Evaluation/Confirmation/Outcome；真实资源是否齐套仍未证 |
| 必验 | 正常五Task同Run；并发start单Run；缺权限/撤权/缺资源零effect；跨scope/错误版本/过期Assignment拒绝；日期边界/缺日期/重复/单位oracle；分页不完整拒绝；known failure新Attempt；timeout/UNKNOWN不重发；重启/late observation不污染；pause request/ack；未terminal不可验收；Human否决；独立授权读回 |
| Human需明确 | 单MCP或冻结导出路线、数据scope/asOf/行数上限；E1/E2实际职责与root/Task Assignment推荐结构；exact资源及effect owner路线；故障/取消终态与暂停语义；D3契约接受及后续G1实施/测试执行授权。若涉及既有Accepted Contract不兼容变更，先G2，不自行修改 |
| 推荐下一切片 | 先审定D3并做无effect的exact资源/Task Assignment admission与同Run身份验证，再单独授权只读五Task执行与恢复，最后I2.5结果验收；不要先实现72页再补主线，也不以单任务跑通代替五Task闭环 |

### 13.5 最小页面衔接

本轮仅规划入口的调用/失败/补问上下文衔接。后续D3最小依赖：A04模型配置引用与诊断（不展示秘密）；D08/D09实例与分工；D04/S04/S09/M03/M04/M07/M11精确资源/契约/发布/授权；W09/W11准入与关联计划；W12/A11/A12任务/Attempt/UNKNOWN与证据；业务Outcome的Criteria Evaluation和Human确认/否决。已有owner能力优先复用，完整管理仍按11.5后续规划。首页H01–H07当前323工作区未收到可核实图集/契约，登记“设计资料待同步”，未审图、不阻断后端接线；本轮不实现首页或72页。
