# S5-V023-IMPL-299 业务问题工作区交互设计

本设计把业务问题作为可恢复、可审批、可追溯的工作单元：用户从左侧问题导航进入，中间区域按 Problem、Criteria、Plan、审批、执行和结果推进，右侧呈现数字员工及相关资源；界面必须明确区分“可选”“已绑定”“实际使用”，以中文和可读时间表达状态，并对刷新恢复、未保存修改及迟到响应给出确定行为。本文仅补充已授权的交互设计，不把设计目标描述为现有实现。

## 1. 边界与状态口径

本文规定信息架构、状态、关键交互、授权边界和依赖接线。它不授权修改公共 CRD、冻结契约、Kubernetes API group、持久化边界或跨域 owner；未知字段、接口和语义统一标记为“待 owner 确认”。

| 标记 | 含义 | 页面处理 |
| --- | --- | --- |
| 设计目标 | 299 期望提供的体验，不代表已有后端支撑 | 可用于实现规格，不得宣称已可用 |
| 已有能力 | 已由源码和测试确认的正式能力 | 仍按其公开/正式端口和授权边界接线 |
| 候选接线 | 有相邻任务产物，但未证明已接入 299 | feature gate 或禁用状态，不模拟成功 |
| 未接线 | 299 无可用连接 | 显示原因并禁用依赖操作 |
| 缺少接口/契约 | 需要新的正式端口、字段、事件或语义 | 待 owner 确认后再实施 |

305 与 310 只按任务提供的固定参考提交评估，分别为 `3abb901f30a57218928990adf4f2ae75ca38829b` 和 `fb5edaf174783f0e997ed912c516644b977e3eb6`；它们不是整体合入授权，也不证明 299 已完成接线。状态时点以这些固定提交为准，当前部署、PR 和 CI 状态不在本文中推断。

## 2. 三栏信息架构

| 区域 | 内容 | 主要操作 | 约束 |
| --- | --- | --- | --- |
| 左栏：问题导航 | 问题列表、搜索、筛选、状态、更新时间、未保存提示 | 新建、切换、筛选、恢复最近访问 | 不承载审批或执行详情 |
| 中栏：工作主区 | Problem、Criteria、Plan、审批、执行、结果及活动时间线 | 编辑、保存、审批、执行、查看和导出 | 唯一主任务流，不成为后端权威 |
| 右栏：参与资源 | 数字员工、工作流、知识、工具及绑定/使用证据 | 查看、绑定、解绑、跳转正式资源入口 | 按授权最小披露，不替代资源管理中心 |

顶部显示问题标题、稳定问题标识、整体状态、owner、最后保存时间和刷新入口。整体状态由服务端阶段状态推导，不能由用户直接修改。所有写命令在对应卡片内反馈；toast 仅作补充。

窄屏时中栏占满宽度，左栏收为“问题”抽屉，右栏收为“参与资源”抽屉或底部面板。状态、主操作和错误不得进入不可见横向滚动区；抽屉关闭后焦点返回触发按钮。

## 3. 阶段状态与交互

正常业务路径为：

`Problem 草稿 → Criteria 就绪 → Plan 就绪 → 待审批 → 已批准 → 执行中 → 结果可用`

这是业务推进路径，不要求底层共用一个状态字段。修改已批准计划会使旧批准失效；重新执行创建新 attempt，不覆盖旧执行与结果。

### 3.1 Problem

内容包括标题、业务描述、背景、owner、范围、排除项、期望时间和服务端版本。状态包括空白、草稿、就绪、已归档；是否存在锁定/删除语义待 owner 确认。

- 保存只修订 Problem，不隐式审批或执行。
- 已有下游产物时修改 Problem，服务端返回受影响阶段，前端不自行猜测。
- owner 变更单独授权，并记录旧/新 owner、操作者和时间。
- 归档不删除历史执行和结果。

### 3.2 Criteria 与 Criteria Set

Criteria Set 是同一 Problem 下的版本化成功标准集合；Criteria 是集合中的稳定条目。每条标准至少表达业务描述、是否必须、验证方式和判定状态，精确字段待 owner 确认。

状态包括草稿、校验中、就绪、需修改、已失效。支持新增、修订、排序和移除；移除已被 Plan 引用的 Criteria 必须提示影响。保存与“检查完整性”分离，机器不可验证的标准显示“人工确认”。Plan 和结果引用精确 Criteria Set 版本，旧版本继续可读。

### 3.3 Plan

内容包括目标摘要、步骤、每步 owner/数字员工、输入输出、资源绑定、风险、预计时间，以及工作流精确引用。状态包括未准备、准备中、草稿、就绪、待审批、已批准、已驳回、已失效。

- “准备 Plan”是显式命令；在途时冻结其输入基线，不先清空现有草稿。
- 提交审批冻结不可变 Plan 版本，并展示 Criteria Set 版本、资源绑定和高风险权限摘要。
- 已批准后影响执行语义的修改创建新版本，旧批准不继承。
- 若工作流设计器有正式接点，仅提供版本化只读预览及受权深链接，不在 299 内建立第二工作流权威。

### 3.4 审批

内容包括提交人、提交时间、Plan 版本、策略摘要、审批主体、决定、意见和审计入口。状态包括未提交、待审批、已批准、已驳回、已撤回、已失效；多级和代理审批语义待 owner 确认。

- 批准/驳回仅对精确授权身份显示，服务端在命令时再次授权。
- 代理审批同时记录实际 actor 与被代理身份。
- 迟到决定不得覆盖已经形成的权威决定；界面读回最新审批并解释冲突。

### 3.5 执行

内容包括 execution/attempt 标识、精确 Plan 与 Criteria Set 版本、发起人、时间、步骤、进度、数字员工参与记录和结构化错误。状态包括未开始、排队中、执行中、等待输入、取消中、已取消、成功、失败、状态未知。

- 只允许对有效且已批准的 Plan 发起执行。
- 启动使用客户端幂等键，双击、刷新或网络超时不产生重复执行。
- 取消是请求：先显示“取消中”，以服务端终态收敛。
- 传输中断显示“状态未知，正在重新连接”，不直接标为失败。
- 重试创建新 attempt 并保留与旧 attempt 的关系；断点恢复待 runtime owner 确认。

### 3.6 结果

结果关联唯一 execution attempt，包含摘要、Criteria 逐项判定、产物、证据来源、实际使用资源、生成时间和限制。状态包括尚无结果、生成中、部分结果、结果可用、结果失败、已过时。

- Criteria 判定区分通过、未通过、无法判定；无法判定不计为通过。
- 部分结果列出已完成和缺失部分。
- 新结果不覆盖历史；旧结果标明基于旧版本。
- 导出重新授权，只包含当前主体有权读取的字段和证据。

## 4. 资源关系

| 关系 | 定义 | 是否证明执行参与 |
| --- | --- | --- |
| 可选 | 当前身份在当前 scope 中有权发现并考虑的资源 | 否 |
| 已绑定 | 精确资源版本已加入 Problem 或 Plan 版本 | 否，只证明计划关系 |
| 实际使用 | 某 execution attempt 的可信记录证明资源被调用、读取或参与步骤 | 是，仅限该 attempt 与证据范围 |

三种关系用独立分区和文字标签表达，不能压缩成一个勾选状态。已批准 Plan 的资源版本不得静默漂移；版本不可用时阻断执行或重新审批，规则待 owner 确认。

数字员工同时是可发现资源与业务参与主体，但不等于 runtime、model 或 service account。310 仅是参与关系/归因的候选接线，不能据此推断 Problem、Criteria、Plan 或执行端口存在。知识和工具只有运行时可信 usage record 才能标记“实际使用”。

## 5. 身份、授权与最小披露

读取和每个写命令都由服务端基于 session、subject、scope、resource、action 和对象版本重新授权。按钮隐藏只是体验优化，不是安全边界。

必须区分：

- human actor：实际发出命令的人；
- on-behalf-of identity：被代理身份（如有）；
- digital employee：业务参与主体；
- runtime/service identity：工作负载执行身份；
- approver identity：作出决定的主体。

无法从正式契约获得精确身份时标为“待 owner 确认”，不得用展示名、身份 header 或客户端声明替代可信身份。

最小披露规则：无发现权不透露对象存在性；有列表无详情权只返回允许摘要；有执行权不等于有密钥读取权；有结果权不等于有全部证据权。错误不回显密钥、提示词、工具参数、内部端点、堆栈、策略规则或其他 scope 标识，只提供可关联追踪编号。

## 6. 保存、刷新与迟到响应

页面区分服务端已保存状态、本地未保存修改和命令处理中状态。只有服务端确认后才移除“未保存”标识；审批决定与执行开始不得乐观标为成功。

刷新恢复顺序：

1. 按稳定 problem 标识读取权威快照。
2. 恢复服务端在途命令、审批和执行状态。
3. 若有本地草稿，比较其基准版本与服务端版本。
4. 基准一致时允许恢复或丢弃，不自动提交。
5. 基准不一致时保留用户输入并进入冲突视图；合并契约待 owner 确认。

离开当前问题时若有修改，提供“保存并离开”“不保存离开”“继续编辑”。条件写携带 CAS/版本标识；冲突时保留本地输入，不提供无契约的“一键覆盖”。审批、执行和资源解绑永不自动合并。

每个请求关联 problem、对象版本、命令/请求标识和当前视图实例。切换问题后到达的响应只能更新原问题缓存；旧保存响应不得覆盖更新版本；超时命令使用同一幂等键查询或重试；已推进阶段不被迟到响应回退。

## 7. 中文、时间与可访问性

- 默认使用“成功标准”“计划”“待审批”“数字员工”“实际使用”等业务中文，首次可附英文术语。
- 按钮使用动作与对象，如“保存成功标准”“提交计划审批”“取消本次执行”。
- 当天显示“今天 14:32”，昨日显示“昨天 09:05”，更早显示完整年月日和时间；相对时间只作辅助，并提供绝对时间与时区。
- 客户端时钟不决定审批或事件顺序，使用服务端权威时间/序列。
- 当前阶段不能只靠颜色表达；状态变化以文字和可访问通知呈现，错误后焦点回到卡片错误摘要。

## 8. 操作、owner、正式接点与缺口

下表描述所需能力，不发明 URL、schema 或 action 名称。正式端口必须由当前源码/测试确认。

| 操作 | 正式能力要求 | owner/候选依赖 | 授权要求 | 当前结论 |
| --- | --- | --- | --- | --- |
| 创建/读取/修订 Problem | 稳定 identity、scope、revision/CAS、影响信息 | 现有 Problem owner；305 可作可信 BFF 候选 | create/read/revise 等价正式 action | 待源码核验 |
| 创建/读取/修订 Criteria Set | 精确 problem/revision 绑定、Criteria 稳定标识、CAS | 现有 Criteria owner；305 可聚合 | 对精确 problem scope 授权 | 待源码核验 |
| prepare/read Plan | 冻结输入、命令状态、精确版本与资源引用 | 现有 Plan owner；305 可聚合 | prepare/read 正式 action | 待源码核验 |
| approve Plan | 不可变版本、精确 approver、决定冲突 | 审批 owner 待确认 | 服务端决定时授权 | 待源码核验，不从 310 推断 |
| 恢复 session | 可信 session 与 subject、scope、允许动作 | 305 候选 | 不接受客户端身份覆盖 | 待源码核验 |
| 资源发现/绑定 | action/resource/scope 与精确 revision | 资源 owner 待确认 | discover/use/bind 分层授权 | 缺口或候选接线，待核验 |
| 数字员工参与 | 参与主体及 attribution/usage record | 310 固定参考提交 | 参与和证据读取分层授权 | 候选接线，不扩张业务操作端口 |
| 执行/结果 | approved Plan → attempt → evidence/outcome | runtime/result owner 待确认 | execute/cancel/read/export 分层授权 | 本轮后续义务，不由首批闭环伪造 |

## 9. 后续实现验收

首个闭环必须证明：从真实前端创建业务问题，经正式后端 owner 持久化后读回同一 identity；在同一 scope 内修订 Criteria Set，CAS 冲突失败关闭；刷新后仍读取同一 problem identity、revision 与 Criteria Set，而非重新创建或从 mock 恢复。

后续仍需独立完成 Plan prepare/read/approve、资源绑定、执行、进度、Evidence-backed 结果、纠正、Outcome 和反馈。候选依赖未接线时必须保持显式缺口，不得以静态数据、私有 API 或身份 header 回退替代。

## 10. 2026-09-12 恢复实施接点表

来源时点：299 实际基线 `91928f285160f74927a7dbd3a905b5bdaa7bbf6f`；可信浏览器依赖核对到用户固定参考 305 `3abb901f30a57218928990adf4f2ae75ca38829b`，首批业务子集取自其祖先 `8ce7b39`；310 固定参考 `fb5edaf174783f0e997ed912c516644b977e3eb6` 只用于确认边界，未引入。

| 能力 | 已有正式 owner 端口 | 浏览器接点 | 前端调用位置 | 缺口 | 定向验证 |
| --- | --- | --- | --- | --- | --- |
| Problem 创建 | `POST /api/internal/v0.2.3/business-problems`；`BUSINESS_PROBLEM CREATE + READ business-problem:collection` | 305 已接受 `POST /api/workbench/v1/problems`，可信 session + CSRF，同授权事务调用 owner | `businessWorkspace.ts:createBusinessProblem`；`ProblemWorkspacePage:create` | 新 identity 的后续精确 grant/continuation 尚无已注册浏览器管理端口，真实环境需预置精确 grant 或 owner 后续契约 | BFF route/边界单测；owner caller-owned connection 单测；前端 source/build |
| Problem 权威读回 | `GET /api/internal/v0.2.3/business-problems/{id}`；返回 aggregate、revisions、lifecycle | `GET /api/workbench/v1/problems/{id}`；精确 `READ business-problem:{id}` | `readBusinessProblem`；URL `?problem=` 刷新恢复 | 无精确 READ grant 时 fail closed；不回退私有 header API | 读取同一 problem/revision/digest/aggregate version；刷新 source 断言 |
| Problem 修订 | `POST .../{id}/revisions`；predecessor revision + aggregate CAS + idempotency | `POST /api/workbench/v1/problems/{id}/revisions`；精确 REVISE + READ | `reviseBusinessProblem`；`saveProblem` | ownerId 变更仍需独立产品授权语义；本批保持现 owner | CAS、重复键与迟到响应隔离单测/源检查 |
| Criterion 创建/修订 | `POST /api/internal/v0.2.3/success-criteria`；criterion 自身 revision/CAS | `POST /api/workbench/v1/success-criteria`；collection CREATE 或 exact REVISE，并读 predecessor | `writeCriterion`；`saveCriterion` | 正式 schema 是类型化 measurement，不存在自由文本 displayName；首批使用 `HUMAN_EVALUATED/rubric` | strict schema、同事务 owner、幂等键复用 |
| Criteria Set 创建/修订 | `POST .../business-problems/{id}/criteria-sets`；绑定 problem revision 和有序 criterion revisions，使用 problem aggregate CAS | `POST /api/workbench/v1/problems/{id}/criteria-sets`；set + Problem + member revision 精确授权 | `writeCriteriaSet`；`saveCriterion` 第二步 | Criterion 与 Criteria Set 没有单一原子浏览器命令；set 失败时 criterion revision 可能已存在，UI 不宣称完成并以原幂等键重试 | CAS 冲突、owner scope、刷新后 set/member 精确身份 |
| Criteria 读回 | 私有 owner 有 set 列表和 problem criterion 列表 | `GET .../{id}/criteria-sets` 与 `GET .../{id}/criteria` | `loadWorkspace` 并行权威读 | member READ grant 由 owner 发现后检查；无权时不部分泄露 | BFF 最小披露与页面 identity 展示 |
| Plan prepare/read/approve | 当前 owner 三个正式端口均已存在，要求精确 Problem/Criteria/Workflow/Employee/Instance/Assignment 引用 | 305 已注册对应 Workbench routes | 本批只显示“尚未接线” | 前端资源选择、精确引用采集、审批词汇和真实浏览器验收未完成 | 后续单独纵向切片，不由首批测试代替 |
| Session、action、resource、scope | 305 的 `TrustedRequestContext` 由 HttpOnly cookie 构造；拒绝 Authorization、principal、tenant、domain 等身份 header | `/login`、`/session`、rotate/logout；Host/Origin/CSRF；精确 `owner/action/resource` | `readWorkbenchSession`；所有写请求仅带 CSRF | grant request/decision/revoke/continuation 浏览器端口尚未正式注册 | session、CSRF、untrusted-header、Host/Origin、错误最小披露单测 |
| 错误语义 | owner 将 not-found 隐藏为统一 Problem not found；冲突 409；存储/兼容问题 503 | BFF 返回 `{reasonCode, requestId}`，无内部细节 | `WorkbenchRequestError` 与卡片内错误 | 字段级错误、冲突差异和本地合并契约缺失 | source、API 单测和真实服务响应分层记录 |

### 10.1 首批实现边界

本批前端只使用 `/api/workbench/v1`：读取可信 session、创建 Problem、按返回 identity 权威读回、修订 Problem、创建或修订一个 `HUMAN_EVALUATED` Criterion、创建或修订 Criteria Set，并从 URL 中的精确 problem identity 刷新恢复。请求不发送身份 header；所有写操作冻结 UI、携带 CSRF、CAS 和按 payload 保留的幂等键，切换问题通过请求 epoch 隔离迟到响应。

后端复用现有 Problem/Criteria/PostgreSQL owner，仅加入 305 已接受的 browser session、精确 grant 与 caller-owned transaction 适配。没有建立新的 Problem/Criteria 权威，也没有引入 310、执行或结果能力。

### 10.2 尚未关闭的正式义务

- 新建对象后自动获得精确 Problem/Criteria Set/member grants 的正式 continuation 流程仍缺少已注册浏览器端口；未预置 grant 的环境会安全失败。
- Criterion 与 Criteria Set 是两个正式命令，不保证跨 owner 命令原子化；首步成功、第二步失败会保留未绑定 Criterion revision。
- Plan prepare/read/approve 虽有 305 正式路由，前端尚未收集并验证所需 Workflow、Employee、Instance 与 Assignment 精确引用。
- 执行、Resource Use、Evidence 和 Outcome 没有 305 公共 Workbench owner 端口，本批保持未接线。
- 305 dual-listener/deployment isolation 尚未并入 299；源码测试不能替代真实服务和可信浏览器证据。

## 11. 本批分层验证记录

验证时点：2026-09-12（Asia/Shanghai）。

| 层级 | 已执行 | 结果 | 证明范围 |
| --- | --- | --- | --- |
| Source / mock | 定向 Ruff lint/format；authority、session、BFF、owner adapter、299 frontend source tests | Ruff 通过；首批 pytest 25 passed，追加 app/frontend 回归 8 passed；共有一个既有 Starlette/httpx 弃用警告 | strict schema、session/CSRF/Host/Origin/身份 header 拒绝、caller-owned connection、前端端口/CAS/刷新标记和现有 app 回归 |
| Frontend 静态产物 | `npm run lint`、`npm run build`（先按 lockfile 执行 `npm ci`） | lint 通过；TypeScript 与 Vite production build 通过 | 新 API 类型、React 页面和生产构建可编译；不证明后端或浏览器交互 |
| 真实服务 | 未执行 | `NOT_EVIDENCED` | 本批未启动 PostgreSQL、私有 owner、公有 BFF 或反向代理 |
| 可信浏览器 | 未执行 | `NOT_EVIDENCED` | 未建立真实 HttpOnly session、预置精确 grants 或执行真实浏览器 create/read/revise/refresh |

因此本批可声明“首批正式接线源码已实现并通过定向 source/build 验证”，不能声明真实服务闭环、可信浏览器接受、完整 299、I2/I3、部署或发布完成。
