# S5-V023-IMPL-310 — 数字员工概况、列表与档案详情交互设计补充

Status: `OPEN / G1 / PARTIAL_DRAFT / BLOCKED_ON_TRUSTED_READ_INTEGRATION`

## 1. 文档范围与依据

本文补充 IMPL-310 的产品交互设计，不改变既有架构、公共契约、产品代码或
IMPL-305 活动路径，也不解除可信读取接线完成前的实现暂停。

- 分支：`codex/s5-v023-impl-310-digital-employee-work-participation`。
- 本轮挂载点：`/Users/tristan/.codex/worktrees/4a88/cloud-native-agent-platform`。
- 产品候选：`4ef9ee40b4fb099d93823e3aa98c801e90c2087c`。
- 候选 tree：`ac9f34bedfb3b2d64364126ed2a52cb2127f1d33`。
- 视觉参考：`3数字员工.png` 中“顶部概况＋左侧列表＋右侧详情”的信息架构。
  图片中的人数、活跃度、增长率、满意度、告警、姓名、负责人和开关均不是
  产品事实或契约依据。
- 接线依赖来源时点：IMPL-305 checkpoint
  `437980f156da16c2879ca88ca7b832c894f61a4f`。该 checkpoint 已完成 Employee
  Definition exact READ 的候选接线，但尚未持久集成，其 DTO 不包含发布状态。
  本文不据此猜测其他读取已完成。

本文使用以下状态：

- `可复用`：候选代码已有交互或私有 owner 事实，但不表示浏览器可信读取已闭合。
- `待 305`：必须复用正式 Workbench BFF、可信 session 和 owner 授权接线。
- `需契约`：当前没有足够的正式字段、LIST、聚合或最小投影；本文只记录需求，
  不授权新增契约。

## 2. 页面信息架构

宽屏页面采用上下两层：顶部为建设概况；下部为左侧可滚动列表与右侧原位更新的
详情。右侧默认打开“员工档案”。

```text
┌──────────────────── 当前授权可见的建设概况 ────────────────────┐
│ 定义数量 │ 已发布 │ 待完善配置 │ 实例/分配/工作状态（待接线） │
└───────────────────────────────────────────────────────────────┘
┌──────────── 数字员工列表 ───────────┬──────── 档案详情 ────────┐
│ 搜索 / 筛选 / 分页                  │ 档案 | 能力 | 工作参与   │
│ 头像  正式名称/缺失提示             │ Runtime | 结果与证据    │
│ 岗位  一句话职责  状态  能力标签     │ 版本与变更             │
│ 当前选中高亮                        │ 身份详情（可展开）       │
└────────────────────────────────────┴─────────────────────────┘
```

概况卡点击只改变列表查询条件，不隐式改变授权范围，也不自动选中一个未获 READ
授权的对象。列表行只来自已获 LIST 授权的最小投影；选中后再对 exact resource
执行独立 READ 授权和读取。

## 3. 顶部建设概况

### 3.1 指标、来源与点击行为

| 指标 | 正式定义与统计范围 | 正式来源 | 点击行为 | 当前能力或缺口 |
| --- | --- | --- | --- | --- |
| 当前授权可见的员工定义数量 | 当前 session、tenant、security domain 与查询条件下，owner 明确允许列出的 Definition 数量 | Employee Definition owner 的授权后 LIST 结果及其可信 `total` 语义 | 清除发布/配置状态筛选，显示同一授权范围内的全部可见定义 | `待 305 / 需契约`。若 owner 只返回当前页且没有可信总数，只显示“本页 N 项”，不得冒充全量 |
| 已发布定义数量 | 上述同一授权集合中，owner 明确标记为已发布的 Definition 数量 | 包含发布状态的最小 LIST 投影或独立授权聚合 | 设置 `publication=PUBLISHED` | `需契约`。305 checkpoint 的 exact READ DTO 不含发布状态，不能用该 DTO统计 |
| 待完善配置 | 同一授权集合中，owner 校验结果明确为 `INCOMPLETE` 的 exact revision 数量 | Employee Definition owner 的版本化配置校验摘要 | 设置 `configuration=INCOMPLETE`，列表显示原因码 | `需契约`。缺少校验摘要时显示“尚不可统计”，不能显示 0 |
| 实例、分配和工作状态 | 当前授权范围内分别由 Instance、Assignment、Execution/Runtime owner 明确汇总的数量 | 各 owner 的授权后 LIST/聚合最小投影 | 进入相应列表筛选；没有列表接点时卡片不可点击并标“待接线” | `待 305 / 需契约`。不得从 Definition 数量、Runtime Profile 或前端缓存推导 |

“待完善配置”采用明确、版本化的 owner 校验规则。首版规则至少检查：`role` 长度
合法；`responsibilities` 为 1–32 项且每项合法；members 为 1–128 项；恰好一个
Agent；最多一个 Runtime Profile；`kind + resourceId` 不重复；每个成员均有合法的
exact `resourceId + revisionId + digest`；需要 owner 解析的引用已经核对。只有 owner
返回 `INCOMPLETE` 及原因码时才计数。未运行校验、结果过期、资源不可披露或校验
接口未接通均显示 `UNKNOWN`，不并入“待完善”，也不根据缺少 `VALIDATE` 事实自行
判定。

### 3.2 统计真实性规则

- 发布不等于运行，Definition 数量不等于 Instance 数量。
- 当前页计数、已加载计数和 owner 声明的授权集合总数必须使用不同标签。
- 请求失败、无权读取、接口未接通和真正的零值必须使用不同空态；只有 owner
  明确返回数值 `0` 才显示零。
- 不展示没有正式来源的活跃度、成功率、满意度、安全告警或增长趋势。
- 聚合结果必须带范围说明和 `asOf`；精确时间和时区可展开查看。

## 4. 左侧数字员工列表

### 4.1 行内容及事实来源

| 展示项 | 展示规则 | 来源与缺口 |
| --- | --- | --- |
| 头像或角色图标 | 使用统一插画系统或中性角色图标；替代文本说明“数字员工视觉标识” | 纯视觉标识，不代表真人、在线、健康或权限 |
| 正式名称 | 有正式 Employee 字段时显示；没有时明确显示“未提供正式名称” | 当前 Definition 契约没有 display name；不得复制 Agent name、演示别名、ID 或负责人充当正式名称 |
| 岗位 | 展示 Definition `role`，并标注来源为 Digital Employee Definition | 当前可复用 |
| 一句话职责 | 使用 Employee `responsibilities` 的 owner 提供摘要，或受限显示第一条并标明截断 | 当前有职责列表，但最小 LIST 摘要需要正式投影；不得用 Agent business purpose 静默替代 |
| 发布状态 | 固定文本状态，例如“已发布 / 未发布” | LIST 投影需要发布状态；305 exact READ 候选 DTO 当前不含该字段 |
| 配置校验状态 | `完整 / 待完善 / 未知`，待完善可展开原因码 | 需要版本化 owner 校验摘要；前端不自行猜测 |
| 主要能力标签 | 优先显示已授权最小投影中的成员类型；若显示 Agent capability，必须 exact revision READ 成功并标“来源：Agent” | 配置/绑定不表示实际使用；禁止因已知 ID 绕过披露授权 |
| 更新时间 | 显示本地化易读时间，如“2026-09-10 14:30”，悬停或展开显示 ISO 8601、精确时区和来源 | 当前 Definition DTO 无权威更新时间，缺少时显示“未提供”，不得使用浏览器读取时间代替 |

岗位类别只有在正式 `roleCategory` 或等价 taxonomy 可用时才使用浅蓝、浅紫、浅青、
浅橙进行克制区分。类别未知时使用中性色，不能从岗位文本、Agent 领域或头像颜色
推断分类。

### 4.2 搜索、筛选、分页与选择

- 正式搜索至少覆盖正式名称、岗位和 owner 允许搜索的标识；缺少正式名称时不将
  Agent 名称混入 Employee 搜索语义。
- 筛选包括发布状态、配置校验状态和有正式来源的岗位类别。每个筛选项说明作用于
  当前授权集合还是仅当前页。
- 分页由 owner/BFF 返回稳定游标或页码、页大小及可信 total 语义。仅有当前页时不
  生成虚假的末页或全量数量。
- 查询、筛选、分页、选中的 `employeeDefinitionId + revisionId` 保存在 URL 或页面
  路由状态；滚动位置按查询签名保存在会话级 UI 状态。状态只用于恢复坐标，不是
  认证或事实来源。
- 选中行保持边框、背景和 `aria-current`/等价语义；键盘可移动焦点和打开详情。
- 列表刷新后若选中项不再可见，不保留旧详情，显示统一的“资源不可用或当前访问
  未获授权”，不泄露是被删除、越权还是撤权。

## 5. 右侧档案详情

详情顶部显示视觉头像、正式名称或缺失提示、岗位、发布/配置状态及来源摘要。默认
打开“员工档案”。技术 ID、revision 和 digest 收入可展开的“身份详情”，但所有
请求仍携带并核对完整 exact identity；隐藏技术字段不能降低精确读回要求。

| 分区 | 内容与来源边界 | 当前可复用 | 待接线或新增缺口 |
| --- | --- | --- | --- |
| 员工档案 | Employee Definition 自身的岗位、职责、用途、适用范围和版本；Agent 提供的名称、标题、目的和职责必须单独标注来源 | exact Definition 的 `role`、`responsibilities`、身份、发布/匹配事实展示及 Employee/Agent 来源分隔 | `待 305` 的 Definition exact READ；正式名称、用途、适用范围等 `需契约`。不能把 Agent 或 HR 身份互相复制 |
| 能力配置 | Agent、Skill、MCP、Knowledge、Workflow、Model 的精确关联，逐项显示 owner、ID、revision、digest、配置状态 | Definition members 中 Agent、Skill、MCP、Knowledge、Workflow、Runtime Profile 的 exact tuple 和 configured/bound 语义 | Agent 必须改为 exact revision 最小披露；各成员详情需独立授权读取。当前无直接 Model member，Model 关联 `需契约`，不得从 Runtime Profile 猜测 |
| 工作参与 | Instance、Assignment、当前工作与执行状态，清楚分隔 configured、bound、assigned、placed、executed、terminal | 已知 ID 下的 Instance、Assignment、Placement 精确读取交互、父链/身份校验、迟到响应隔离 | `待 305`；当前没有 Instance/Assignment/Placement LIST，也没有完整当前工作/历史聚合 |
| Runtime | Runtime Profile 配置、Instance 绑定、Placement、启动状态和健康观察分别展示 | Runtime Profile 精确成员引用、Placement 的 Runtime Instance 引用与有限 observation | Runtime 启动、健康与通用执行读取需正式 owner 接点。Runtime Profile 不证明实例在线，未观测必须为 `UNKNOWN/UNAVAILABLE` |
| 结果与证据 | 实际使用、执行结果、Business Outcome 和 Evidence 分开显示，并逐项标注 owner 与授权状态 | 当前 Placement 投影能明确保持 execution/outcome 不可用 | 正式执行/Resource Use/Evidence reference 读取待接线；Evidence 内容需要独立 exact READ。执行成功不得推导 Business Outcome 完成 |
| 版本与变更 | exact revision、前驱、发布及决策事实、变更时间线 | 当前 exact revision、predecessor、facts 可展示 | revision LIST/history、变更摘要、权威更新时间及 actor 最小投影 `需契约`；不能用当前 aggregate 或前端 diff 冒充完整审计记录 |

每个事实组在标题旁显示来源，例如“来源：Digital Employee Definition”“来源：
Agent Definition exact revision”“来源：Placement owner”。一个分区发生拒绝或不可用
时，仅清空该来源的数据，不用其他对象的缓存填补。

## 6. 视觉与操作体验

### 6.1 视觉语义

- 头像或插画保持统一构图、尺寸和背景；可按正式岗位类别使用浅色区分，但不表达
  性别、真人身份、在线、健康、风险或权限。
- 状态颜色采用固定语义：蓝色为信息/已配置，绿色为明确成功或有效，橙色为待处理，
  红色为失败/拒绝，灰色为未知/未接通/停用。颜色必须同时配文字和图标，不能作为
  唯一信号。
- “已发布”“可匹配”“已分配”“已放置”“执行中”“已完成”“已停用”是不同事实，
  不共享一个模糊的绿色“启用中”。
- 中文标签优先，必要技术术语保留英文括注。时间默认按用户界面时区显示，并允许
  查看原始 ISO 时间、时区和 owner `asOf`。

### 6.2 选择、加载和反馈

- 列表选择后在原位更新右侧详情，保留列表筛选、分页和滚动位置。
- 每次选择生成新的读取世代并取消可取消的旧请求；旧请求即使迟到也不得覆盖当前
  员工。各详情分区可独立显示骨架、成功、未知、拒绝或重试状态。
- 当前详情为只读时可直接切换。未来出现未保存编辑时，切换员工、筛选导致当前项
  消失、关闭抽屉或离开路由前必须提示“保存 / 放弃 / 留在当前页”，不得静默丢失。
- 401/403/404 对普通用户采用不泄露存在性的统一文案；409 exact tuple/digest 不匹配
  清空详情并要求权威刷新；5xx/网络错误保留可重试提示但不保留过期敏感内容。
- 空态区分“授权集合确实为空”“当前筛选无匹配”“尚未接线”“未知”“读取失败”。

### 6.3 窄屏

- 窄屏先显示概况和列表；选择后进入独立详情路由或全高抽屉，并提供明确返回列表
  操作。返回时恢复查询、筛选、分页和滚动位置。
- 不把列表与全部详情栏目横向挤压；详情标签可横向滚动或收纳为分区菜单。
- 技术身份、长 digest、错误码和能力标签允许换行/复制，不造成页面横向溢出。

### 6.4 独立操作

发布、停用、撤销匹配/权限、停止 Instance 必须设计为不同的 owner 命令，分别显示
影响范围、前置条件、确认文案和权威读回。不能以一个开关混合这些操作，也不能因
列表行隐藏按钮而认为用户无权调用。本文不新增或启用任何写操作。

## 7. 接口与授权映射

所有浏览器读取均复用 IMPL-305 的正式 Workbench BFF。BFF 从可信 session 派生
principal、tenant 和 security domain，在查找或披露数据前执行当前授权，并通过正式
owner port 返回最小响应。客户端不得生成或覆盖身份 header。scope 过滤、对象关联、
页面隐藏、已知 ID 和无法猜测的 URL 都不能替代 exact-resource 授权。

### 7.1 页面读取

| 用户动作 | 正式 owner/API | 精确请求身份 | 最小响应 | 授权要求 | 当前能力或缺口 |
| --- | --- | --- | --- | --- | --- |
| 加载概况、搜索、筛选、分页 | Employee Definition owner 的正式 LIST/aggregate，经 305 BFF | session 派生 scope + collection query/cursor | 列表行所需字段、范围、cursor/page size、可信 total 或明确“仅本页”、`asOf`；聚合不返回完整对象 | 当前 collection `LIST`，先授权后查询/披露 | 当前私有 LIST 可供 owner 设计参考；可信 BFF LIST 与最小投影 `待 305 / 需契约` |
| 点击 Definition 行、恢复深链 | Employee Definition exact READ，经 305 BFF | `employeeDefinitionId + employeeDefinitionRevisionId`；响应核对 digest | 单一 exact revision 的 Employee-owned 档案、精确成员引用及允许披露的状态 | 当前 exact Definition `READ`；授权先于存在性披露 | 305 checkpoint `437980f...` 已有候选接线但未持久集成；其 DTO 不含发布状态 |
| 展示 Agent 名称、目的、职责和能力 | Agent Definition owner 的 exact revision READ，经同一 BFF | `agentDefinitionId + revisionId + digest` | 单一 revision 的获准展示字段，不含其他 revisions、draft 或 aggregate history | 当前 exact Agent revision `READ`；读取后再次核对 ID/revision/digest | 当前页面读取包含全部 revisions 的 Agent aggregate 并由前端筛选，违反最小披露；授权映射仍是提案，不记为完成 |
| 展开 Skill/MCP/Knowledge/Workflow/Model 详情 | 各资源正式 owner 的 exact READ，经同一 BFF | member `kind + resourceId + revisionId + digest`；Model 使用其正式身份（待契约） | 当前分区所需的单一 exact revision 摘要 | 每个资源分别执行当前 exact `READ`，不能继承 Definition READ | Definition 可显示 exact 引用；资源详情读取分别待接线。Model 直接关联当前缺失 |
| 查看 Instance 或从已知 ID 恢复 | Digital Employee Instance owner exact READ，经 305 BFF | `instanceId`，响应中的 Definition `id + revision + digest` 必须与 exact Definition 读回一致 | 单一 Instance 的 lifecycle、owner/organization、Definition 引用及明确可披露的 execution/health 状态 | 当前 exact Instance `READ`；owner 验证 Definition 父链，关联检查不代替授权 | 私有 exact read 与 identity-chain 校验可复用；可信读取 `待 305` |
| 查看 Assignment | Assignment owner exact READ，经 305 BFF | `instanceId + assignmentId` | 单一 Assignment 的 lifecycle、business role、有效期和最小 binding 状态 | 当前 exact Assignment `READ`；owner 验证其父 Instance，并对所需父事实执行相应当前授权 | 私有 exact read 和 Instance/Assignment 响应隔离可复用；可信读取 `待 305` |
| 查看 Placement/当前工作关联 | Placement owner exact READ，经 305 BFF | `instanceId + assignmentId + placementId + attemptId + agentInstanceId` | 单一 Placement 的 request、decision、Runtime reference、policy、compatibility、limitation 和获准 observation；无 Evidence 内容 | 当前 exact Placement `READ`，并在同一可信上下文核对 Placement→request→attempt/agent 与父链；所需父事实独立授权 | 私有 exact read、父链校验和虚假链接移除结论可复用；可信读取 `待 305` |
| 查看 Runtime 配置、启动或健康 | Runtime Profile/Runtime/Observation 正式 owner，经 305 BFF | exact Runtime Profile revision、Runtime Instance 与 observation identity | 配置、绑定、启动事实、最新获准观察及 `asOf/freshness`，各自注明来源 | 各资源当前 exact `READ`；不能因 Placement 或 Definition 可读自动继承 | 配置引用与部分 Placement 事实可复用；正式启动/健康读取接点未确认完成 |
| 查看实际使用、执行结果或工作历史 | Governed Execution/Resource Use owner，经 305 BFF | exact assignment/attempt/execution/resource-use identity | 单次执行或分页历史的最小摘要、状态来源与 `asOf` | 相应 exact `READ` 或独立历史 `LIST`；先授权后披露 | 当前没有完整投影，按已知报告保持未接线 |
| 打开 Evidence | Evidence owner，经 305 BFF | exact Evidence reference/identity；不得仅凭 Placement/Execution ID 拼接 | 获准的 Evidence 元数据；内容或 dereference 使用独立最小响应 | Evidence metadata/content 各自当前 exact `READ`，不能继承执行或 Placement 权限 | Placement 当前无 Evidence reference；正式读取保持未接线 |
| 查看版本与变更 | Employee Definition owner 的 revision LIST 与 exact READ | Definition ID + cursor；选择后为 exact revision ID/digest | 最小 revision 摘要列表；选择后单一 revision 和允许披露的变更事实 | collection/revision `LIST` 与每个 exact revision `READ` 分开 | 当前只有 exact revision 和局部决策 facts，完整 history/list `需契约` |

### 7.2 LIST 与完整 READ 的边界

- LIST 授权只允许返回该集合的最小行投影，例如正式名称（若有）、岗位摘要、发布/
  校验状态、允许披露的能力标签、更新时间、exact selection identity 和分页信息。
- LIST 不自动授予任一行的完整对象 READ；服务端不得先装载完整对象再依赖前端隐藏。
- 点击行、深链恢复、详情预取和展开来源对象均重新执行当前 exact READ。
- 若概况需要独立 aggregate，aggregate 权限及响应投影单独定义，不能用浏览器遍历完整
  对象计算。只有当前页数据时必须标“本页”。
- 授权拒绝、撤权和资源不存在采用受控最小错误；缓存数据在 current check 失败后立即
  清除。已知 ID、父子关联或同一 scope 不能放宽授权。

### 7.3 写操作边界

现有创建 Definition、验证、人工批准、发布、创建 Instance 和创建 Assignment 的
交互不因本文获得可信浏览器写权限。后续若接线，每个命令均需要正式 owner、严格
请求 DTO、独立 action grant、CSRF/Origin/Host/session 检查、幂等/CAS 语义和权威
读回。停用 Definition、撤销匹配或权限、停止 Instance 必须保持为不同命令。

## 8. 复用、依赖与新增契约清单

### 8.1 已有实现可直接复用的交互

- 现有 Definition 主从选择、关键词和生命周期筛选的交互骨架。
- URL 中保存 exact Definition/Instance/Assignment/Placement 坐标并权威读回。
- Employee 与 Agent 事实来源分隔、exact member tuple、configured/bound/assigned/
  placed/executed/terminal 语义分隔。
- Instance→Definition exact tuple、Instance/Assignment 隔离、Placement 父链与
  request/attempt/agent 校验，以及迟到响应世代隔离/请求取消。
- 统一受控错误、空态和既有窄屏样式可作为实现起点。

这些内容仍位于私有接口或 mocked 交互边界内，“可复用”不表示真实浏览器授权通过。

### 8.2 等待 IMPL-305 的接点

- Employee Definition exact READ 候选的持久集成；发布状态不得从当前 DTO 猜测。
- Employee Definition LIST/最小投影，以及适用时的授权后 aggregate。
- Agent exact revision READ 的 owner/BFF/授权映射；当前仅为提案。
- Instance、Assignment、Placement exact READ 及其父链和当前授权闭环。
- Runtime/Observation、Execution/Resource Use 和 Evidence reference/content 的正式
  owner 接点；按已知报告保持未完成，不能从 305 的 Definition 候选接线外推。

### 8.3 需要正式字段、列表、聚合或契约

- Employee 正式 display name、用途、适用范围、岗位类别 taxonomy，以及必要时的
  正式 owner/organization 展示字段；不得从 Agent 静默复制。
- Definition 最小 LIST DTO：发布状态、版本化配置校验摘要、权威更新时间、最小能力
  标签、稳定分页与 total 语义。
- 不暴露全部 revisions 的 Agent exact revision 最小 DTO。
- Instance、Assignment、Placement/current-work 的授权 LIST 或聚合投影。
- Model 的正式关联身份；Runtime 启动/健康观察；执行、Resource Use、Business
  Outcome 与 Evidence 的独立引用和最小读取契约。
- Definition revision history/change summary 的授权列表与 exact revision 读取。

以上均是后续契约候选，不由本设计文档批准公共 API、CRD 或权限模型变更。

## 9. 后续真实用户旅程验证清单

- 可信登录/session 派生 scope 和 principal；浏览器身份 header 被拒绝或忽略。
- 不同 principal 的 Definition LIST、概况数量和分页只包含各自获准的最小投影。
- 只有当前页时明确标“本页”，无数据、未知、拒绝和未接通均不显示为零。
- LIST 可见但 exact READ 未授权时，点击/深链不泄露完整对象或其存在性。
- Definition 与 Agent 均读取 exact revision；Agent 响应不包含其他 revisions。
- 快速切换、返回列表、刷新和慢响应不会把前一个员工的数据写入当前详情。
- Instance→Definition、Assignment→Instance、Placement→request→attempt/agent 任一
  身份不匹配时 fail closed，且关系成立仍需当前授权。
- Runtime Profile 绑定不显示“在线”；无 observation 时健康保持未知。
- 执行成功不显示 Business Outcome 完成；Evidence reference 不自动开放内容。
- 搜索、筛选、分页、选中和滚动在返回列表时恢复；390 px 等窄屏无横向挤压。
- 中文时间可读且可查看精确时区；头像和颜色不传达真人、在线或授权语义。
- 发布、停用、撤权和停止 Instance 为独立操作，撤权后详情缓存立即清除。

mocked Playwright 只能证明交互；真实 PostgreSQL Identity Chain 测试只能证明其覆盖的
服务端身份链。两者都不能替代通过正式 BFF、current authorization 和真实 owner 的
浏览器用户旅程。

## 10. 完成与后续边界

本文完成只表示交互设计补充可供审查，不表示功能完成或 Human 接受。PR #165 保持
Draft，IMPL-310 与本 Session 保持 `OPEN`，产品实现继续
`PARTIAL_DRAFT / BLOCKED_ON_TRUSTED_READ_INTEGRATION`。不转 Ready、不 merge、
不 deploy，也不修改 IMPL-305 活动路径。

数字员工、Runtime、工作历史、运营和 Evidence 的原交付义务全部保留；M1/M2/M3、
P1/P2/P3 范围不变，中间演示不构成验收。
