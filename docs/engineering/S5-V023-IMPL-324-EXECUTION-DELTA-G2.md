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

## D324-6：同案新计划的历史累计次数差异（PROPOSED，未批准、未实施）

用户最新验收要求同一新问题贯通真实理解、目标/标准、计划和实际执行，旧成本Plan只能回归。只读PG核验原planning ledger `ledger:s5-323-real-planning:original-window` 已有19条reservation，原call_cap=8、total_cost_cap_microusd=10000000；理解账本5/12。原19次为既有历史，不能因超过8而删除、重置或套用323连续开发例外。

具体冲突：D324-5要求原上限不变，而新问题尚无正式proposal/Plan；现有正常新建计划依赖governed planning invocation。窄后继入口要求既有同案Plan与来源proposal，不能移用旧成本Plan。预算owner在dispatch时以全部reservation计数，20>8必然拒绝；`migrate_and_configure`拒绝改变原policy，返回PROVIDER_BUDGET_PROFILE_CONFLICT。不是登录、Grant审批或等待时序能解除的问题。

最小建议（等待Human决定）：在原预算owner增加追加式、精确新324 planning对象适用的次数修订记录，保留原policy=8及所有历史，以累计20次为本次有效计数上限，即当前19次之后最多新增1次。仍使用原模型/价格及USD10总额上限，累计全部结算与UNKNOWN预留，任何一项不足即拒绝。记录只适用于实际形成、随后由独立本人签发的本次新planning对象；对象尚未形成时本决定仅授权实施，绝不预签调用。不得令旧323调用继承该次数修订，不改旧guard，不返回可绕过金额上限的continuous-development例外；调用UNKNOWN即停，不能自动追加第二次。

受影响组件：原budget owner的有效次数投影、context精确planning范围及其独立决定绑定、追加持久记录/迁移和读回展示。现有额度/账本不覆盖；旧writer不能误读新增记录，需明确兼容门禁和停writer回退，不删除新旧历史。这是D324-5“原上限不变”的实质增量，G2未接受前不得编码或签发。

替代：①保持全部原限制，则本次新问题只能推进已获准的理解阶段，不能宣称完整同案验收；②另建完整手工规划来源/入口需要新的产品与契约范围，不是现成可用替代，不建议本轮扩展；③复用旧成本Plan冒充本案、清账本或直接更新policy均不采用。建议仅审阅上述1次有界追加；它不改变USD总上限、不替代精确Grant、资源审核、执行准入或Human验收，也不保证一次模型输出必定满足标准。
