# IMPL-324 执行契约集中差异决定包 v1

状态：ACCEPTED_WITH_CONSTRAINTS（本Session Human集中决定），非服务端执行签发；2026-09-21。原323保持CLOSED。

## 已接受方向与本次唯一请求

本Session及附件已经授权：同案成本Plan复用、四阶段六任务、单Run、有限静态DAG、精确资源映射、不强制Workflow编辑器、Native只读优先、合成数据、真实产物和Human结果决定。以上不再请求批准。

本包已获Human接受下列D3具体责任及状态语义，作为324编码的架构依据。不是请求重新理解、重新生成计划或批准相同开发方向；也不代替后续服务端独立准入与页面Human决定。

## 现场依据与冲突

- main `2e8c1fb60a2a8f3aef6d244dced8ea2988e8bcf6`，Registry 323 CLOSED且D3详细契约递延。
- `core/src/agent_core/execution_contract.py` 的ExecutionIdentityAggregate强制WorkflowRun.assignment_id等于aggregate.assignment_id；TaskRun只有workflow_run_id，无Task参与Assignment。Native队列取aggregate.assignment作为授权关联。
- `execution_application.py:start`将task_id纳入Run seed；逐Task调用产生多个Run。`governed_execution.py`只读旧v1/v2执行envelope，不接收workflow_planning的plan.v2/planning.v3。
- 现场PG读回Plan v2摘要`a789015b006cecc053dc5297529edf80fa430411253aa13e869c210292623492`及Approval `6d30f690-d10b-4e6c-afcf-4d8ccea14e4b`与closure一致；Run/TaskRun/Attempt均0。
- 该Plan明确写“本轮只规划与确认，不创建Assignment、Run或TaskRun”，两个required资源selected均null。不得把旧Approval直接当业务执行许可。
- [Architecture Gates](ARCHITECTURE_GATES.md)将Task/Workflow/Runtime生命周期及cross-plane ownership变更列为G2。新root/Task责任和UNKNOWN聚合属于这条规则；仅批准静态DAG方向并未确定以下状态行为。

## D324-1：根与Task参与身份及兼容

建议：保留现有WorkflowRun→root Assignment身份及旧aggregate不变量，在execution owner追加Task参与绑定：exact TaskRun→Task Assignment→Employee Instance→Definition revision/digest，同scope绑定准备快照。root仅协调、无Task资源权限继承；每次Native派发授权以Task参与主体、原用户执行授权、资源owner授权交集为准。旧单Task路径不自动转换；新版本入口显式区分。

单Run唯一键：scope + approved execution-instance identity；该instance精确固定Plan ID/version/digest、Approval、准备快照digest及root Assignment。Start请求幂等键只负责重放；同一instance换key仍同Run，不同内容同key冲突。更换资源/批准不原地改Run，必须在启动前失效重备，启动后走明确后继。

影响：core execution identity的追加绑定契约、execution PG owner、governed start、Native队列/worker授权关联与read model。兼容：保留原ID/摘要/旧API；新增表使用新domain migration及writer版本检查。回退仅兼容reader/停新writer，不还原数据。替代是root代理所有Task权限或逐Task新Run，两者均不满足授权/单Run要求，不推荐。

## D324-2：调度、失败、取消与UNKNOWN状态语义

建议保留operator既有成功依赖ready和失败后裔skip算法；当前批次最多32 Task、128边、32阶段，与已接受planning parser上限一致。超限、循环、自依赖、重复ID、缺依赖和不匹配I/O均在任何Run创建前拒绝。禁止动态增图、条件表达式代码、循环、跨Runtime迁移。

| 持久事实 | 后继Task | 无关分支 | Run及恢复规则 |
| --- | --- | --- | --- |
| 依赖全部成功且产物验证通过 | 可排队，每Attempt仅一个effect owner和managed Skill | 按依赖就绪 | QUEUED不能显示为运行；以worker事实推进 |
| 已知FAILED/TIMED_OUT且已证实停止 | 先进入RETRY_WAIT；明确放弃/耗尽重试后FINAL_FAILED，才传播后裔SKIPPED | 继续已准入的只读分支 | RETRY_WAIT期间Run不终态；所有Task已终结后Run失败，终态不可复活 |
| effect结果UNKNOWN或fence失联 | 不派发依赖任务 | 停止新增派发，已运行继续观测 | RECOVERY_REQUIRED，不自动重试，不作为terminal Business Outcome输入 |
| 用户取消请求已保存 | 不再新增派发，未派发Task记录取消原因 | 向已运行Attempt发有权取消请求 | CANCEL_REQUESTED不等于CANCELLED；无ack保持待确认/UNKNOWN |
| 已保存取消请求且全部运行Attempt停止已确认 | 未运行任务终结并保留原因 | 无新增派发 | 汇聚CANCELLED；部分成功产物仍保留 |
| 全部必需Task成功、产物齐备 | 无 | 无 | 技术SUCCEEDED；终态快照后评价，不能直接关闭Problem |

合法重试必须重新校验授权与exact资源，使用同Run/TaskRun的新Attempt；旧UNKNOWN没有权威解决事实时禁止重试。取消与自然完成竞争按持久事实/CAS排序，不把晚到ack覆盖已确认完成。stage状态按真实成员聚合，未终结不算完成。

这里“UNKNOWN时暂停无关分支”和“已知失败允许无关分支继续”是本次新增实质选择，旧线性实现未决定，不能由编码者静默确定。

## D324-3：精确映射及Plan后继边界

建议execution owner保存不可变准备映射，资源owner只提供有权精确reader；固定Task operation、Skill executor/revision、MCP tool/schema/trust、Knowledge source revision/snapshot、Employee Definition/Instance/Assignment和Native profile。每Task单managed Skill完成，禁止Native与同步Skill双dispatch；不是自然语言自由调用。

本案例复用Plan v2全部Problem/Criteria、四阶段六Task、依赖、8000预算、排除试验项目及缺口。仅由正常后继流程追加执行就绪语义：替换“本轮只规划”限制为“本次隔离合成资料只读执行”，固定合成数据来源和准备映射；形成可审查diff、同Plan下一revision和新Approval。不得重生成理解/规划，不修改v2或复制旧批准。后继仍由原可信Human在页面确认；开发授权不自动充当此事实。

artifact采用已有PG/Evidence owner：每Task至多16个产物、每产物256KiB、Run合计4MiB，UTF-8 JSON/text，schema版本、摘要、字节数、时间、Plan/Task/Attempt lineage与授权读取。超限不截断后冒充成功；输出缺失/篡改是技术失败，合法缺口报告是成功产物但业务可能不可评估。保留追加历史、不自动删除，不引入对象存储。

最小Context引用同案Problem/Criteria/Plan、纠正、准备快照、Task输入、Attempt及Evidence；不能截断必需schema/约束。展示压缩或省略字段及来源，不建立新的长期记忆owner。Evaluation及Human后继沿ARCH-264，不新增结果权威。

替代：维持Plan v2“只规划”语义，只做准备而无实际执行；不满足附件完整闭环。推荐上述窄后继，不把合成结果当星河客服真实业务结论。

## 不在本次架构确认中的运行签发

接受本包只解除上述编码契约门禁。实现、测试、资源准备及准入预检后再集中提交原主体/独立签发者可操作包，包含实际namespace/security-domain、exact资源digest、有效期、操作白名单、技术上限、撤销与成功标志。当前尚无这些真实准备对象，不能现在伪造签发记录。Human结果决定及merge/close仍分别执行。

## 验证与后续执行

按附件§7全矩阵验证，包括六Task分支、环/超限、重复Start换key、同key冲突、跨scope、资源撤销、crash/fence、UNKNOWN无重发、取消无ack、合法重试、产物篡改、重启和历史摘要。前端按已实读[R30绑定](S5-V023-IMPL-324-DESIGN-BINDING.md)实施；图间导航差异不宣称视觉通过。

## Human集中决定（2026-09-21）

本Session用户明确批准D324-1/2/3作为实施依据，同时要求：

1. 先记录Attempt失败与停止依据；允许重试的Task进入RETRY_WAIT、阻塞其后裔；合法重试生成新Attempt。明确最终失败后才将Task置FINAL_FAILED并传播SKIPPED；全部Task终结后才形成Run终态。已终态Run/Task/Attempt不得静默复活。
2. CANCELLED须同时有持久取消请求与停止确认依据；自然停止不构成取消。
3. 每Task产物数量按全部Attempt历史累计，Run字节按全部Task/Attempt历史累计；锁定同Run预算行原子校验后追加，重放同产物不重计，冲突拒绝；不得删除历史或重置额度。

本次准许连续实施、必要资源整合、受控验证和页面交付；不再次请求同方向确认。保留Plan v2，通过正常后继流程形成隔离合成资料只读执行修订及可审查差异，不重新生成理解或整套规划。实现与实际入口预检通过后集中提供修订确认及独立准入操作流程，分别保留正式记录。323 CLOSED、旧Approval、七UNKNOWN与账本不变；新首页、平台底座和完整记忆平台不纳入本批。

## 接受决定的实现落点（续接）

0034 添加原 planning owner 的精确引用登记与 Task 参与身份，不复制或覆盖 v2。PreparedNativeCoordinator/SkillCaller 与既有 NativeDispatchWorker 接线，Runtime/Task/Skill 每次派发均再校验当前授权；UNKNOWN 不重发。取消已请求且 effect 尚未获准时形成可核对停止收据，不能仅从 Attempt 集合推断取消；已获 effect 许可而无停止证据仍不能 CANCELLED。0033 的历史累计原子限额由 Skill 终态事务调用，超限回滚不隐藏旧产物。

0035 保存 exact Criteria / artifact / ResourceUse 终态快照、标准评价、Human 确认及 Outcome 后继，幂等命令不重复记录，异议不覆盖原评价。原案例 Human 规划标准无法被合成执行自动判 PASS；此限制在页面、评价和操作包持续披露。服务端独立准入与 Human 记录仍未由开发授权替代。

## D324-4：隔离测试账号与短期会话分离（ACCEPTED）

2026-09-21 用户将测试账号密码登录纳入同一 324 / PR #186，并明确若触及认证架构须先提交最小差异。本节只处理新增认证边界；D324-1/2/3 及其三项约束保持 ACCEPTED，不重新申请模型、费用或执行总体范围。

### 现状与实际阻塞

当前 `StaticGenerationAuthenticator` 对用户提交的完整 bearer 凭据作 SHA-256 比对；`BrowserSessionService` 的会话有效期被该凭据有效期截断。`GenerationAuthorizationReader._current_credential` 在授权时再次要求有效的 generation credential。没有账号、密码哈希、账号停用或密码重置 owner；仅改表单为用户名/密码无法满足用户要求，长期 bearer 包装或自动续期亦不能作为实现。

`ARCHITECTURE_GATES.md` G2 明确列出 **authentication architecture** 并要求批准前停止实施。ARCH-300 文档及 Registry 仍标 PROPOSED，不在本节擅自更改其状态；302 源码、测试及实施文档用于识别当前能力，不据文档标题推定新认证已获批准。

[本次入口诊断](../evidence/s5/v0.2/s5-v023-impl-324/login-diagnosis-v1.json)：运行 generation 4 / recovery epoch 1；当前业务主体新凭据未过期、文件无首尾空白且摘要匹配。真实 HTTPS POST 使用新 nonce 返回 303，Cookie 为 Secure/HttpOnly/SameSite=Strict/__Host-，随后 session GET 200、目标页 200；缺 CSRF 的退出 403，正确 CSRF 退出 204，旧 nonce 重放 401。没有使用审批身份或发送业务命令。

历史失败的原 POST/响应原因未留存：服务 access log 关闭，HTML 登录 handler 将所有 AuthorityError 合并为相同提示，当前浏览器错误日志为空。恢复后诊断前没有 generation 4 新 session。以上不足以判定历史失败发生于过期、nonce、提交内容、Origin 或浏览器 Cookie；禁止把本次成功复现当作历史根因已确认。

### 请求批准的最小增量

1. **身份 owner**：在现有 PostgreSQL 的 Browser Session Authority 内增加隔离测试账号及认证修订，不新增数据库、外部 IdP 或另一身份权威。`demo324` 固定映射 `human:demo323-requester`，`reviewer324` 固定映射 `human:demo323-approver`；scope 固定 `s5-323-demo / isolated-real-demo`。登录表单不能指定 principal、scope、角色或权限。功能显式开启，仅用于已批准本地隔离环境，生产默认关闭。
2. **账号生命周期**：账号在 operator 显式停用/撤销前可用，不依赖数小时更换演示口令；会话仍 idle 30 分钟、absolute 8 小时、nonce 5 分钟、CSRF 10 分钟。不将原 bootstrap 凭据改为永久有效，不自动续签 Grant，不复活 323 委托/连续性。保留旧 bootstrap 兼容路径及旧凭据期限。
3. **密码与管理**：服务端使用带随机 salt 的自适应密码哈希（实现选用 scrypt 并校准成本）；前端、仓库、日志不保存密码。operator 通过受控本机命令提供首次随机密码、停用、不可逆撤销及重置，私有领取文件 0600；无公共注册、找回邮件、SSO 或完整账号管理平台。重置追加密码修订，旧哈希不可再认证；停用/撤销/重置均使旧会话失效，重复 operator 命令幂等并保留审计，撤销不被重置抵消。
4. **统一当前身份校验**：新增账号认证版本绑定，与现有 generation / recovery epoch 一起进入 Browser Session 与 exact authorization 的同事务当前性校验。会话读取、业务 owner、独立准入及 Native dispatch 均使用同一身份有效性规则；不能只在登录检查账号状态。并发停用/重置与业务操作按现有授权事务锁/快照顺序线性化，旧 writer 对新增认证模式 fail closed。旧会话和旧授权证据不改写。
5. **权限边界**：账号只证明原主体。原业务 bootstrap 权限与独立审批人的 exact meta 范围保持，不新增业务权限；静态 tombstone 与动态撤销优先。原三条 PENDING 请求继续按原 ID/version 决定；新 Grant 仍由独立本人签发、保留原有效期规则。会话/账号长期可用不延长 Grant 或执行准入。代理不得登录 reviewer324 代作独立决定。
6. **页面与诊断**：沿用已接受的 IAM01 登录外观及当前 R30 实施基线，只调整账号、密码、显示密码、错误与帮助，并显示当前身份/隔离环境。保留安全 returnTo、Host/Origin、Cookie、CSRF、退出与零自动业务重发。中文外部错误不泄露账号存在性；服务端以 correlation ID 记录受控枚举原因（解析、nonce、密码/停用、Origin、会话、CSRF、跳转），不记录密码、凭据、Cookie、nonce、CSRF 原值或完整请求体。加入持久的有界登录节流及重启后拒绝绕过的验证。

### 影响、兼容与替代

影响 `browser_session_application`、`authority_configuration`、`authority_postgres`、`grant_administration_application`、Workbench BFF/登录页/身份投影、现有 runtime composition 和一条追加迁移。保留 Browser Session Authority 和 Grant Administration Authority 的分工；不修改公开 CRD、Kubernetes API group、业务 Plan/Approval/Run 契约。若实现发现必须修改其他 frozen Contract，另报具体差异，不能由本决定泛化授权。

建议批准上述有界本地账号适配。替代 A：维持 bearer 登录并补诊断，可定位失败但不满足稳定账号要求；替代 B：接入企业 IdP，范围明显超出本批，不推荐。账号绑定、生命周期和所有 current-authorization 路径必须一并实现，不能仅以更换登录表单交付。

### 批准后的验证与续接（尚未实施）

- 迁移升级/摘要/回滚；密码错误、枚举隐藏、节流、停用/撤销/重置、并发当前性和重启持久性；会话过期与 Grant 过期相互独立、跨 scope/自批拒绝。
- 真实入口以 demo324 验证登录、Cookie/CSRF/安全跳转、当前主体/环境、刷新零重发；reviewer324 登录由本人验证，不以 fixture 替代。
- 登录前实读既定 IAM01 图片并补页/摘要绑定；视觉与功能验证分别记录。R33 不替换 R30。
- 正常门禁及原 PR #186 最终候选 CI；一次性交付账号、URL、本机密码领取及必要人工步骤。三条原申请 → 资源/Employee 发布 → 窄后继确认 → 独立执行准入 → 实际 Native → 产物/Criteria → Human 决定 → 持久读回。

**待决定：批准 D324-4 上述六项最小增量作为同一 324 的实施依据。该决定不代替任何业务发布、Plan 确认、执行准入或 Human 结果决定。**

### D324-4 Human 批准（2026-09-21）

用户明确批准上述六项增量，固定 demo324/reviewer324 映射原主体；旧 bootstrap 到期后账号仍可登录，授权依当前账号及有效 Grant，不延长旧凭据/复活委托/隐式续签。密码本机安全生成且正常重启不重建。独立签发仍由本人完成，批准连续实施、门禁、真实验证并回接原主链，非业务审批或完成记录。

## D324-5：新问题的独立准入与原预算连续性（ACCEPTED，实施中）

2026-09-22 用户补充要求全新供应商问题真实 AI 入口。第一处已复现失败是运行装配缺少 Draft Assistance 路由，HTTP 405；不是模型超时或账号错误。补齐明确的未配置错误、诊断、页面恢复和正常接口装配不改变权限。但直接启用原模型 runtime 不能完成新问题真实调用：原 understanding ledger 精确绑定唯一 323 delegation，该 delegation 已于 2026-09-20 18:34:34.697Z 到期；`guard_budget` 会按原任务校验 context/UNKNOWN/当前准入。原 `TaskDelegationService.approve` 还按 bootstrap credential 到期限制新决定，无法把稳定账号等同于长期授权。不得删除 ledger 关联或复活 323。

### 最小建议决定

1. 为本次 324 的新合成问题增加独立、追加式的 **context 调用准入记录**，由独立 Human 签发，绑定实际生成 context、原业务主体、当前账号修订、scope、精确 profile/model/adapter 摘要、允许阶段、有效期和幂等键。无 wildcard context；账号启用只是身份前置，不能自动签发。
2. 复用原模型与价格、原预算 owner 和已批准上限。新记录指向原 ledger，原所有调用次数、结算及未结算最坏预留参与同一原子额度计算；不新建空账本规避额度，不释放七 UNKNOWN / USD 4.816896。新准入不得引用 323 已有 context/调用/Plan，不修改旧 delegation 的期限、状态或权限。
3. `dispatch_guard` 明确区分：323 调用仍严格走原 delegation/UNKNOWN 规则；新 324 context 只有精确独立准入且当前账号与 Grant 均有效才可调用。新 context 一旦 UNKNOWN/未结算即阻断其后继，禁止自动重发；不得把 323 的例外名单继承给新 context。原 UNKNOWN 保留占额，不等于已解决。
4. 新 context 和 invocation 由正常入口生成，先形成待准入状态，再集中呈现独立签发；不预造 ID。只覆盖理解/补问/草稿及原确认流程，不因此授予 Native、资源发布或业务结果确认。只在需要规划时另用同一正式准入机制的精确 planning 范围，不重跑旧成本规划。

影响：原 authorization/budget owner 的追加记录和准入选择，账号当前性校验，以及页面准入状态。G2 原因：改变模型调用授权/委托及账本准入选择，超出 D324-4 登录机制。兼容：旧记录及 old guard 不变，新 writer/schema 显式版本校验；回退停新 writer，保留新旧全部记录。无新数据库、IdP、CRD 或全平台账号系统。

替代 A：保持真实 AI 不可用，只修诊断和手工入口，不能满足全新问题真实 AI 验收。替代 B：复活 323/解除原 guard/新建空 ledger，违反历史及预算边界，不采用。推荐上述有界追加机制；若原批准额度已不足，明确拒绝，不能隐式增加预算。

待 Human 决定仅是上述新 context 准入机制，不重新申请既有模型、价格或总体费用上限；批准该机制也不替代实际独立签发。D324-1/2/3/4 继续有效。原资源—Native 主链不依赖此模型机制，可在原三条申请决定后继续。

### D324-5 Human 决定追加（2026-09-22）

用户对原决定包的精确答复为：“批准 D324-5 的有界追加机制”。上述四项机制及边界正式接受；D324-1/2/3/4 继续有效。此记录是架构决定，不是具体 context 的调用准入、资源发布或 Native 执行批准。实际对象形成后仍由独立本人签发；原账本、上限、历史、UNKNOWN 及 323 guard 不变。

## D324-6：同案新计划的历史累计次数差异（ACCEPTED；实施状态 Partial）

用户最新验收要求同一新问题贯通真实理解、目标/标准、计划和实际执行，旧成本Plan只能回归。只读PG核验原planning ledger `ledger:s5-323-real-planning:original-window` 已有19条reservation，原call_cap=8、total_cost_cap_microusd=10000000；理解账本5/12。原19次为既有历史，不能因超过8而删除、重置或套用323连续开发例外。

具体冲突：D324-5要求原上限不变，而新问题尚无正式proposal/Plan；现有正常新建计划依赖governed planning invocation。窄后继入口要求既有同案Plan与来源proposal，不能移用旧成本Plan。预算owner在dispatch时以全部reservation计数，20>8必然拒绝；`migrate_and_configure`拒绝改变原policy，返回PROVIDER_BUDGET_PROFILE_CONFLICT。不是登录、Grant审批或等待时序能解除的问题。

最小建议（等待Human决定）：在原预算owner增加追加式、精确新324 planning对象适用的次数修订记录，保留原policy=8及所有历史，以累计20次为本次有效计数上限，即当前19次之后最多新增1次。仍使用原模型/价格及USD10总额上限，累计全部结算与UNKNOWN预留，任何一项不足即拒绝。记录只适用于实际形成、随后由独立本人签发的本次新planning对象；对象尚未形成时本决定仅授权实施，绝不预签调用。不得令旧323调用继承该次数修订，不改旧guard，不返回可绕过金额上限的continuous-development例外；调用UNKNOWN即停，不能自动追加第二次。

受影响组件：原budget owner的有效次数投影、context精确planning范围及其独立决定绑定、追加持久记录/迁移和读回展示。现有额度/账本不覆盖；旧writer不能误读新增记录，需明确兼容门禁和停writer回退，不删除新旧历史。这是D324-5“原上限不变”的实质增量，G2未接受前不得编码或签发。

替代：①保持全部原限制，则本次新问题只能推进已获准的理解阶段，不能宣称完整同案验收；②另建完整手工规划来源/入口需要新的产品与契约范围，不是现成可用替代，不建议本轮扩展；③复用旧成本Plan冒充本案、清账本或直接更新policy均不采用。建议仅审阅上述1次有界追加；它不改变USD总上限、不替代精确Grant、资源审核、执行准入或Human验收，也不保证一次模型输出必定满足标准。

### D324-6 Human 决定追加（2026-09-22，ACCEPTED）

用户对上述精确差异明确答复：“批准 D324-6 有界追加一次”。保留前述 PROPOSED 文本作为申请历史，本追加将决定状态改为 ACCEPTED、实现状态为待实施。仅本次实际新324规划对象可经独立本人签发使用累计20次上限；原policy=8、USD10上限、全部历史结算与UNKNOWN预留及323 guard不变。不得自动增加第二次；本决定不是具体调用准入。

## D324-7 — 任务授权、正式对象来源与配置修订衔接（ACCEPTED；实施状态 Partial）

本节取代此前D324-7候选正文；旧候选由Git历史保留。D324-1至6继续有效。2026-09-22 用户在原324会话分别批准决定A和决定B；批准记录见本节末尾。架构接受不等于实际对象签发或实施完成。

### 事实、冲突与目标

本案是固定快照/判定日期的合成供应商交付及时性分析。真实理解已成功，Problem/Criteria与资源/Employee正式发布记录保留。2026-09-22北京时间16:18:33规划调用f078a876-eef8-4cb5-ae69-83bf6cfccd42无响应头/结果/usage，在WAIT_HEADERS约30.735秒失败，终态UNKNOWN，新增USD0.688128预留；原七UNKNOWN/USD4.816896及全部历史保持。累计20次，D6一次已消耗；金额累计USD5.956372/10为当前账本快照，不保证未来仍有同等余额。

实际装配读取5/30/60秒配置。stage脚本为重现旧delegation摘要，把原独立timeout revision的55秒改回previous_read_seconds=30。离线transport测试证实30或55会按配置传递；不能宣称worker读到了55、不能仅延长期限解决未知供应商行为。Kimi公开Responses文档声明store=false/background=false；公开索引未找到单条结果/用量检索契约，无response id，供应商后台/支持方能否追溯尚未知。无记录不证明未处理或零费用。

Employee精确READ返回404：账号ENABLED/revision1，human:demo323-requester与s5-323-demo/isolated-real-demo匹配；精确修订及CREATE/VALIDATE/APPROVE/PUBLISH事实完整。两条READ Grant过期，最近于2026-09-22 08:42:38.489UTC失效。与此前已修复的SQL版本投影遗漏区分；不重新发布、不换主体绕过拒绝。

当前逐对象Grant/context准入不支持明确任务范围内的正式owner后继衔接；无模型隔离Native规格也不能冒充governed planning invocation。改变授权适用规则和新增可信计划来源属于G2，需本决定；纯交付Skill/边界适配继续按既有实施授权完成。

### 决定A：有界机制调整（不增加模型次数或金额）

1. **基础访问与职责**：固定账号仍映射原主体和scope，不新造主体。基础角色只提供导航、本人任务/申请的必要元数据；业务正文、资源及模型/执行效应仍要求当前有效授权。审批角色只读取待审精确对象和必要脱敏依据，不获得业务全局LIST、业务代办或自批权。角色分配和权限调整仍由正式管理owner记录，不硬编码账号特权。

2. **不可变任务授权修订**：由独立本人签发，精确绑定S5-V023-IMPL-324、主体及账号revision、tenant/security-domain、根Problem/context、允许阶段和动作、固定合成数据/判定日期、精确资源及模型profile/configuration revision、原预算owner、累计次数/金额上限、notBefore/expiresAt及恢复条件。范围仅本案交付及时性和明确独立的Native合成能力验证，不含成本分析、生产数据或外部写入。新修订追加并引用前任，不覆盖旧Grant/approval/ledger。

3. **有效期与撤销**：每个签发窗口最长8小时，起止时间在实际签发时展示；任务生命周期不自动延长授权。登录/刷新/密码重置不续签。到期、撤销、账号停用或账号revision变化立即阻止新调用、新Attempt及其他受控效应；未完成对象保留。已派发工作继续按原状态机收集停止/完成证据，不因授权失效自动记CANCELLED或释放UNKNOWN预留。系统owner保存终态/审计证据不构成新的用户效应授权。续期是追加正式决定，可只更新时间、不要求重复业务发布或目标确认。

4. **后继对象衔接**：正式owner在创建事务中记录root、parent、精确revision/digest、scope、subject、origin和创建动作；仅同根、同主体/scope、允许phase/type且未扩大边界的后继可由策略生成逐次授权决定，无需Human逐ID办理技术Grant。客户端taskId/URL/名称不能证明血缘。旧对象仅经显式可审计关联纳入，不通过相同namespace猜测继承。新turn不复制旧invocation签名；新模型调用获得新的正式准入决定并占用剩余额度。原context的UNKNOWN阻断传播，除非独立任务授权修订明确批准该UNKNOWN的精确后继恢复；原终态不复活。

5. **保留必须的业务决定**：目标/标准、Plan确认、资源审核发布、独立实际Run准入、Human成果接受按现行职责保留独立记录。已有有效发布/确认只读复用；任务授权只授予办理资格，不自动表示这些决定完成。独立Run准入必须等实际Plan/Preparation/Run身份可核验后签发。授权窗口内的派生Task/Attempt仍按批准Run和重试上限核验，无需逐技术ID人工签名，但不能新增未批准任务或重试额度。

6. **资源及效应前校验**：每次新效应原子核验账号、任务授权revision、当前时间/撤销、正式血缘、精确资源修订/发布状态、Skill操作Schema及执行身份、预算和UNKNOWN限制。源快照、判定日期、模型、执行器或任务语义变化超出已批准集合时拒绝并提出差异；不能静默替换成“最新”资源。并发预算和产物限额沿用原owner，累计重试及全部历史；不得新建空账本。

7. **配置版本连续性**：新增显式配置修订，候选connect5/read55/total60秒、worker清理2秒；绑定profile/model/adapter及完整配置摘要和来源。加载器必须核验已签发revision与实际值一致，不允许为匹配旧摘要静默降回30秒或沿用旧路径；不一致在派发前拒绝并提供诊断。保留30秒配置及原调用证据，旧323 guard仍用原规则。离线验证配置解析、传递及外层期限后，实际任务授权单独绑定候选。55秒不保证成功，也不增加次数。

8. **隔离Native正式计划来源**：只为本次已要求的独立合成能力验证增加明确的HUMAN_SYNTHETIC_VALIDATION来源；由正常计划owner保存待确认proposal，附合成来源、任务映射、标准及摘要，invocation关联为空且不得伪造模型调用。与真实AI来源可区分，不能回填为本案AI规划或覆盖原Plan。经本人正常Plan确认、资源审核/绑定和独立执行准入后，使用同一Preparation/Run/Task/Native/产物/评价契约。隔离scope与原案例分开，不复制Approval或Grant。该来源不开放任意手工计划平台、不改变真实AI本案验收口径。

9. **恢复交互**：查询状态、补交正文、显式发起调用分开；登录返回保留精确对象，查询/刷新/恢复不派发。正文不可恢复时保留旧摘要与对象，走标注来源的正式关联后继。操作清单展示已完成/到期/缺口及影响；并发版本由服务端获取。批准后返回精确事项，不进入审批人无权读取的业务列表。

10. **验收与兼容**：验证owner血缘伪造/跨scope/越phase/过期/撤销/账号修订/配置漂移/并发额度/UNKNOWN后继拒绝及幂等；验证正式合成来源不产生provider记录，不能冒充AI来源，确认前不创建Run。使用现有PostgreSQL追加表/字段与显式迁移，无新数据库或CRD。旧323、D1–D6记录不回写；新writer版本不兼容时启动失败，回退停止新writer/入口而保留所有数据，不删除新记录。实施过程中若发现冻结契约额外冲突，集中报告具体差异，不能泛化此决定。

**决定A的批准含义**：允许实现上述有界机制及55秒配置候选衔接，不签发任何实际任务授权、模型调用、资源发布、Plan、Run或成果接受，也不增加额度。

### 决定B：最多一次新的规划额度（独立于决定A）

在原planning预算owner上追加适用于本次324真实供应商交付问题的精确次数修订：当前累计20后最多再新增1次，累计上限21；原policy=8保留，USD10总上限和模型/价格不变，原七UNKNOWN与本次UNKNOWN等所有预留/结算累计。不得补回已消耗D6次数，不得自动修正调用或再次增加额度。

新调用必须是与上述UNKNOWN明确关联的正式后继，保留恢复理由、正文/输入摘要、原Problem/Criteria/已发布资源关联及新配置revision。对象形成并完成入口/离线预检后，由独立本人签发实际准入；本决定不是该签名。实际派发时重新原子检查剩余次数和金额，任何不足拒绝。若新调用再次UNKNOWN或失败，保留结果和预留，不自动再发；后续另报证据。

拒绝B不影响A机制和隔离Native准备；批准B不绕过A尚未落地的配置/授权机制，也不授权代理代签。若供应商结果可正式核实，则先按既有证据/结算机制处理，不以B为理由无条件再发。

### 影响、替代与建议

影响：task/context authorization、正式owner血缘、budget guard、runtime configuration选择、计划来源投影与验证、BFF操作清单和Native效应前检查。保留现有每对象精确机制作为兼容路径，但不能默认复活它或把过期Grant延长。完整企业IAM、外部Runtime、协同中心、全局菜单及记忆平台不在范围。

替代一：保持D5/D6逐对象机制和20次上限，则可以继续已授权工程，但无法完成新的真实规划，隔离手工规格也不能被当作正式计划。替代二：扩大全局权限、直接写Approval、复制成本Plan或新开账本，违反职责/历史边界，不采用。建议分别审定A与B；批准后先落实拒绝测试和入口预检，再集中展示已形成对象的独立本人步骤。

### D324-7 正式决定登记（2026-09-22）

- **D324-7-A / ACCEPTED**：Human明确批准有界机制调整，实施状态Partial。
- **D324-7-B / ACCEPTED**：Human明确批准最多新增一次规划额度，累计上限21；实施状态Partial，已有额度守卫与追加表，尚无实际调用准入。
- 真实案例与隔离Native验证各自绑定精确根对象和scope；任何派生授权不得跨scope自动继承。隔离验证不复制原案例授权。
- 统一计算：原policy.call_cap=8不可变；历史追加是适用对象的累计上限修订，不是可相加的独立额度。D6累计上限20，D7-B仅精确后继累计上限21；有效上限按适用正式修订选择，不能计算8+20+21。调用数来自原ledger全部reservation（含失败/UNKNOWN），不重置；新reservation与限额检查同一事务。所有实际派发入口共同执行guard，未纳入D7的323路径保持原规则。
- 金额统一为原ledger全部settlement实际金额加未结算reservation最坏金额；任何调用不得突破USD10。UNKNOWN不释放；幂等重放不新计额。
- 实际派发前比较签发configuration revision/digest与运行值；connect5/read55受total60绝对期限约束，不将5+55重新叠加为额外预算；worker总期限到达停止，清理2秒是停止确认宽限，不是额外供应商读取时间。清理失败保留UNKNOWN并阻止后续派发。
- 本批准不代替实际任务授权、模型准入、Plan确认、独立Run准入及成果接受；不重新发布、不复活旧授权、不自动重试。
