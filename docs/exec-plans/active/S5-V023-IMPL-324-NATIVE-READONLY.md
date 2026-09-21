# S5-V023-IMPL-324 同案资源准备、Native只读执行与结果验收

状态：ACTIVE / AUTHORIZED；v0.2.3；2026-09-21。

## 来源与登记

用户明确要求核验324后登记并执行[附件完整范围](../../engineering/S5-V023-IMPL-324-TASK-SOURCE.md)。附件SHA-256：`2343e2b1f70dc46698101f1dab79f486aa6c2039ae0e42030f85e5e575592ca6`。
现场fetch完成，origin/main与起点均为`2e8c1fb60a2a8f3aef6d244dced8ea2988e8bcf6`；远端Registry无324。干净独立工作树3096，新分支`codex/s5-v023-impl-324-native-readonly`。
323保持CLOSED，原计划§26/§28及交接证据不覆盖。成本Problem `59a1d736-96d5-5060-8ae3-293d82b4b74b`、Plan `5ad74afd-a6bf-4b04-b395-34d18d01c3b6` v2、Approval `6d30f690-d10b-4e6c-afcf-4d8ccea14e4b`为复用目标；现场PG核验未完成，不重复理解/规划/确认。

## G1实施计划

1. 比对现有owner、D3与附件已接受方向，固化有限静态DAG、精确映射、产物与状态表。仅未覆盖实质G2语义集中呈交。
2. 按需整合168/167；审计166/163/164/170残余；修复169既有失败并保留OpenClaw执行后续切片。共享harness/迁移由本任务单writer维护。
3. execution/governed_execution/Native/Skill owner接通单Run六Task、准备快照和派发前再校验；不引入平行执行器或账本。
4. Evidence/Criteria/Outcome owner实现有界产物、不可评估及Human追加决定；最小Context从持久事实重建。
5. 前端修改前实读R30图片与交互契约，记录路由/页ID/文件/SHA256/状态；验证同视口中文、长内容、缩放、滚动与键盘。
6. 完成隔离合成数据与执行准入预检，一次提交确需独立主体的激活包；激活后实际Native执行和持久读回，Human决定不代签。
7. 正常提交推送及候选CI；最终合并/关闭按仓库Human门禁。

## 验证、兼容与风险

执行附件§7完整测试矩阵；相关代码测试和make check，前端另lint/build。保留旧Plan/Approval、七UNKNOWN和原账本；历史值来自交付证据，未现场读回不称PG验证。旧方案不自动转换，保留采购旧契约负例；迁移按domain ledger校验，回退禁止旧writer和覆盖历史。

## 当前检查点

完成附件/main/编号核验与分支登记。governed_execution仅接受employee-execution-plan.v1/v2，v3多Task映射不能直接调用旧start作为预检。R30目录已找到，VERSION/CATALOG标R30、待视觉审阅；逐图绑定待完成。产品实现、数据库/身份核验、受控测试、实际执行、CI和Human结果决定均未完成。

## 后续范围

附件§9沿323 §26 A/B/C权威入口追踪：OpenClaw执行、Hermes/Fleet、个人助手、自适应循环、多会话、分层记忆、大规模资源选择、完整组织预算运营、公共UI规范不混入本批验收。

## 2026-09-21 现场核验与集中门禁

已在原PG只读事务中读回workflow_planning的成本v1/v2及Approval，v2摘要与closure一致；旧execution_authority.plans无此Plan是owner差异，不是Plan丢失。Run/TaskRun/Attempt均0。七未结预留共USD4.816896，17条结算recorded cost USD0.582440（沿历史估算口径，非供应商账单）；未释放或改写。主体grant时间窗计数已读，尚不等于完整执行准入。

[R30逐图绑定](../../engineering/S5-V023-IMPL-324-DESIGN-BINDING.md)已完成14页实读与manifest摘要核验；未前端实施/视觉验收。[七PR预检](../../engineering/S5-V023-IMPL-324-INTEGRATION-AUDIT.md)已读取当前HEAD/检查、merge-tree冲突、逐路径字节对照及迁移摘要；残余语义处置与整合未完成。

[G2集中差异包](../../engineering/S5-V023-IMPL-324-EXECUTION-DELTA-G2.md)为PROPOSED：root/Task权限责任、新Run状态传播、保留v2且正常后继确认“只规划”到隔离合成只读执行。Human问题已发送，未收到决定。仅受影响执行身份/生命周期编码停在G2，未伪造接受或服务端签发。

截至此检查点仍未产品编码、创建执行对象、调用模型、迁移、推送/PR/CI、实际Native或Human结果决定；完整任务未完成。

提交钩子首次pytest：2097通过、331跳过、1失败（父通道丢失worker退出测试）；未改代码的单测复现1通过/2.44s，尚不据此宣称全门禁通过。失败保留，完整提交门禁待重试。

## 当前执行检查点：Human集中决定已接受

2026-09-21用户批准D324-1/2/3并追加重试等待→最终失败→后裔SKIPPED→Run终态顺序、取消请求+停止确认、跨重试历史的原子产物限额三项约束，已登记原决定包。先前PROPOSED/等待决定为历史检查点，当前编码门禁已解除。
163544f提交钩子完整重跑通过，Ruff lint/format检查通过；首次失败保留。实施继续，不重跑理解/规划、不重置旧账本，不扩首页/平台底座/完整记忆平台。

## 实施检查点：状态、产物与窄后继基础层

已实现接受的重试/最终失败/后裔传播规则、取消请求与停止确认分离、UNKNOWN禁止新增派发、终态不复活。0033追加准备/进度/事件/产物表，引用现有canonical身份；Run锁下原子检查全部Task/Attempt历史，单Task16项/单项256KiB/Run4MiB，历史不可覆盖或删除。独立PG并发、重试、重连、CAS、重放和迁移摘要漂移测试通过。此层尚未接入canonical多Task准入或Native worker，不宣称执行就绪。

新增窄后继提案入口 `/api/workbench/v1/planning-v2/{proposal_id}/execution-revision`，要求现有PLAN READ/PREPARE exact授权；保持Problem/Criteria、Task/DAG/阶段、预算规则、缺口和policy，只变更已批准的执行边界与exact选择。通过原追加确认机制另生Approval，准备本身不确认、不准入、不启动。确定性修订标记 `execution-revision:`，不是模型调用记录；原案例尚未调用该入口。

[本检查点证据](../../evidence/s5/v0.2/s5-v023-impl-324/implementation-checkpoint.json)：相关39项含真实PG通过、无跳过。make check首次2113通过/334跳过/1失败，既有Kimi send deadline单项未改代码复现通过；全门禁不因单项通过而标绿。仅使用新建324测试容器，未修改323数据库或运行原接管脚本。

下一实施步骤仍为canonical planning-owner引用与Task参与身份接线、Native唯一Skill effect owner、资源整合及实际页面。未完成入口预检，不提前发出Human准入包；尚无实际Native/产物/评价/Human决定或交付完成声明。

### 资源页局部与检查记录

S04/M07再次实读后，局部吸收#168身份详情，新增受管operation输入输出、MCP缺口、中文字段表及完整Schema键盘展开。前端npm ci/lint/build通过，视图fixture浏览器2项通过（2.5s），125%缩放无页面横向溢出，截图保留且已实读；不是实际资源或主链验收。#168完整目录/复用/harness与#167仍未完成。

提交钩子另一次2113通过/336跳过/1失败（Responses READ_BODY deadline）；提交未生成，未跳过钩子。首次浏览器启动60s超时，以及复用默认模式构建导致路由不显示均保留；正确live构建后原断言通过。

## 断点续接：正式装配与待人工步骤（2026-09-21）

从 a103b99 / 原 Draft PR #186 续接，核对原候选 12/12 CI；旧绿灯不代表本续接候选。没有重建 Session、Plan、Approval 或模型规划。D324-1/2/3 及三项约束仍是实施依据。

已接通 planning owner 原始 Plan 引用、root 与 Task 参与 Assignment、精确发布资源、同一个 Native worker 的 managed Skill effect、幂等控制、取消停止收据和 PostgreSQL 产物；新增 0034/0035 各 domain checksum 注册。已有 Canonical Run 身份不变量不变，不复制旧 Plan 到另一 owner；资源 READ、Task START、Skill ordinal INVOKE 分别授权。Evidence writer 必须已通过正常切换验证，否则零 Run/派发。

结果评价绑定确切 Criteria、终态快照、产物摘要及 ResourceUse 快照；技术 SUCCEEDED 不等于标准通过或业务解决。原案例标准是 Human 评价的规划标准，且保留“只规划”历史，合成数据不能证实真实成本结论：本批先形成 UNKNOWN/UNDETERMINED，Human 可确认限制或异议，不能自动关闭 Problem。

四项必要资源（Skill、Native profile、Knowledge 合成快照、Agent）及一个 Employee 草稿已通过正常 owner 创建，仍待 Human 发布。Skill Schema 修正和 Employee 重绑均创建正常不可变后继，旧草稿保留。无 MCP 实际依赖，不为演示强加 MCP/Qdrant/模型；Knowledge 使用现有 PG lifecycle/source snapshot。真实绑定/实例/Assignment/执行修订尚未创建，等待发布事实。

原 writer 已精确核对后停止，备份完成，现有 authority controller 激活 generation 3，仅增加请求资格、不发 grant、不延长凭据。原 26 组保护摘要未变化。原执行域确认为零记录后，用明确新建的空 324 SQLite 初始源，经已有导入与校验切换到 PG；它不是历史 323 SQLite 备份。初始化 receipt 保留来源及零记录校验，未来不再执行初始化。

[实际入口预检](../../evidence/s5/v0.2/s5-v023-impl-324/actual-entry-preflight.json)：HTTPS 证书验证、健康、原工作台和独立审批读取三条实际申请均通过；浏览器已打开实际准入入口，显示需要登录。未模拟批准。三条准备申请 PENDING，[集中操作包](../../evidence/s5/v0.2/s5-v023-impl-324/human-operation-package.md) 明确顺序、真实 ID 和范围；完成资源/Employee Human 发布后，再生成实际窄后继、确认及独立执行申请，不能预造将来对象。

受控验证：32 项准备/PG/资源/状态/Skill 测试通过；六 Task 使用真实 PG、Skill owner 和 Native worker，Kubernetes 明确为替身，不能当作原案例实际执行。增加六产物与标准评价关联验证另记结果。前端 lint/build 与两项浏览器 fixture 通过，刷新零命令重发、部分发布失败保留、125% 输入区可见；视觉参考绑定不等于 Human 视觉验收。完整提交门禁和当前候选 CI 待记录。

保留所有失败：旧 Kimi SEND / Responses READ_BODY deadline；本续接完整门禁首次 core compatibility consumer allowlist 失败；六 Task 首次 Skill const-only Schema 不支持、Evidence writer 尚未激活和测试基线 ledger 缺失；首次服务启动缺 gateway PYTHONPATH。按证据修正，未删断言、跳过或覆盖失败。旧第一次门禁/单项复现记录保持。

完整 324 未完成：原案例 Native、真实产物、正式评价、Human 决定和执行后刷新/重启读回均待顺序完成。323 CLOSED，七 UNKNOWN、预留和结算不改；不 Ready/合并/部署/关闭 Session。

续接实现提交 `778f639` 的正常 Ruff/format/pytest 钩子全通过，钩子未输出测试总数，不复用旧数量。新增六产物与 Criteria/ResourceUse 评价关联及 Human 后继测试 2 项通过；测试变量重名导致的首次尾部断言失败保留。前端 lint/live build 通过（既有大 chunk 提示）。正式 Native composition 预检通过且未调用 run_once，固定 kind context 私有副本；原库 Run/Attempt/命令均零。与保留完整备份比较 26 组保护记录一致。当前 CI 以原 PR #186 的后续实际候选检查为准，继续 Draft。

证据追加提交门禁首次失败：2117 passed / 348 skipped / 2 failed（既有 Responses invalid-json 预期 FAILED 实得 UNKNOWN、取消测试取消前已返回）。原日志 `/tmp/s5-324-evidence-commit.log` 保留。一次定点诊断 2 passed：真实收据 PREPARE 已消耗 0.733–0.775 秒，而该 fixture 总预算 1 秒；推测对冷启动/调度敏感，原失败未输出收据，不能认定其确切 phase。仅追加失败时 deadline 和取消前状态诊断，不改任何阈值、断言或生产代码，不把单测复现当完整门禁。

`b508e29` 正常提交门禁通过，保留前两次失败。第一次新诊断未向 Kimi 复用测试传递 record_property，引起 4 项 TypeError；已补传，定点 4 passed，原断言/阈值未改。`778f639` CI 为 11 success / 1 failure；本轮 324 PG 与 UI 步骤成功，后续既有 319 旅程因 324 测试重建 dist 时遗漏原 Draft Assistance enabled 模式而失败。修正 workflow 保留该构建标志；按相同顺序本地 324 UI 2 passed，随后真实 HTTPS mock-provider 旅程 3 passed，使用新建测试子库、清理已完成，未使用原 323 库。失败 ZIP、SHA 及修正证据见 `ci-build-mode-correction.json`。最后候选 CI 另核验，不据局部通过报告整体验收。

## 2026-09-21 登录产品化补充与原主链续接

用户将稳定账号密码登录纳入同一任务及 PR #186。沿用原计划，追加 [D324-4 最小认证差异](../../engineering/S5-V023-IMPL-324-EXECUTION-DELTA-G2.md)，状态 PROPOSED / 待认证 G2 决定；D324-1/2/3 不重新审批。未创建账号、未实施新认证、未修改登录视觉。

此前现有 Authority controller 已追加 generation 4 的两个新限时凭据，原凭据/策略/meta 范围保留；没有追加 323 连续性批准。当前配置为本机 `identity-recovery-v1/runtime.json`，旧 generation 3 runtime 保留，不得作为当前 writer 启动。候选仍为 dceb251；其历史 12 项 CI 通过不作为未来账号实现的验证。

本次真实 HTTPS 诊断确认业务主体登录 303、session/跳转 200、Cookie 安全标记、CSRF 403/204 和 nonce 重放 401；未使用独立审批凭据、未业务执行。历史失败缺少原 POST 和细分错误记录，根因未定，不能归因为过期。三条原申请仍 PENDING/version 1。详见 `login-diagnosis-v1.json`。

批准 D324-4 后按其最小实现/验证顺序推进，并接回既有三条申请及 Native 闭环，不重建理解或规划、不新开 PR/Session、不触动 323 CLOSED、旧 Plan v2/Approval、七 UNKNOWN、预留及结算。当前仍未完成实际 Native、产物、标准评价与 Human 结果决定。

D324-4 已于本次用户决定中 ACCEPTED。按原六项增量实施账号 owner、统一当前性校验、页面与受控验证；旧 PROPOSED 为历史检查点，不再阻塞该范围。

## D324-4 实施候选（待实际入口与 Human）

新增 0036 Browser Session Authority 账号/密码修订/会话绑定/限流/操作审计表；原 0018、0032–0035 不改。generation 增加显式本地账号绑定，引用原主体及静态权限范围，不含 bearer secret 或账号截止时间；旧配置解析继续兼容，旧 writer 拒绝新增 schema/generation。账号会话的兼容 credential_expires_at 字段仅保存该次会话截止时间，绝不延长原 bootstrap。

scrypt N=131072/r=8/p=1 随机 salt 服务端校验；正常启动不生成密码，operator 脚本仅显式 CREATE/RESET 写本机 0600 文件。停用/撤销/重置追加版本，登录、会话、exact Grant/owner 事务同样检查当前账号版本，account 锁先于 session 锁；旧静态来源撤销仍优先。旧 323 委托不接受账号绑定，不追加连续性。持续 15 分钟窗口的全局/账号限流保存在 PG，未知账号使用固定共享桶及同成本密码校验。

IAM01/R30 实读与摘要已补绑定；保留原外观，添加账号/密码/显示密码、中文帮助、身份环境与正常退出。401 表单仍为 same-origin referrer policy，避免错误页后重试丢失同源语义；服务日志记录脱敏诊断编号，不保存密码/Cookie/nonce。恢复原 returnTo，不重发业务。

相关首轮 38 passed / 1 failed：新授权测试缺精确资源目录，正式 owner 正确拒绝。第二轮 fixture 修改未命中目标行，保留同一失败；实际补齐 fixture 后账号套件 9 passed（非实际 Human 证据）。后加迁移摘要/事务保护测试随完整门禁验证。frontend lint/build 通过；首次误在仓库根执行 npm 导致 ENOENT，纠正 cwd 后通过，未改依赖。全库 Ruff/format 通过，正常提交钩子和当前候选 CI 另记。登录诊断及三个历史申请仍保留，不将本候选等同实际 Native 闭环。

D324-4 首次完整提交钩子：2138 passed / 335 skipped / 4 failed。三项旧 recovery fixture 的 SimpleNamespace 缺新增 local_accounts 字段，已显式补空绑定，原断言不变。另一个既有取消测试在 endpoint accepted 前已返回 HTTP 201；原收据未保留，不能判断确切 deadline phase。追加失败前 endpoint/task/deadline 诊断（不改等待、阈值或断言），一次定点运行 16 passed，记录 endpoint_reached=True、before_cancel_task_done=False；不以此覆盖第一次失败或宣称完整门禁通过。日志 `/tmp/s5-324-account-commit.log`、`/tmp/s5-324-account-cancel-diagnostic.log` 及 XML 保留。正常修正后的提交门禁另记。


D324-4 `561a896` 正常提交门禁通过并推送原 PR #186。实际入口发现旧 runtime 的 migrationPath 指向旧工作树，因此 0036 未找到；失败发生在 DDL 前。shell 顺序未阻断后续 generic activation，使 generation 5 已激活但 schema 缺失；服务保持停止，无账号/业务执行。保留原配置并追加 active/runtime.json，核对 0018 原文完全一致后用当前 checkout 迁移目录完成 0036。随后正式创建两个 revision 1 账号，密码分别为本机 0600 文件。补正 stage 的迁移定位，并让 Authority controller 在发布账号代次前核验 schema，阻止同类不完整激活；不改已应用 0036 字节。

实际 HTTPS 与浏览器：旧过期 bootstrap 401，demo324 账号登录 303/session 200；原主体与隔离环境可见，显示密码、中文失败及错误页重登、刷新、正常退出已验证。初次前端构建遗漏 live 路由标志，曾显示 synthetic 外壳；以 VITE_SUPPLIER_QUALITY_DEMO_MODE=live / VITE_PROBLEM_DRAFT_ASSISTANCE=enabled 重建后读回原案例授权缺口，保留该区别。未使用 reviewer324；三条原申请及既有授权事实逐表不变。截图/检查点在 local-account-entry-checkpoint.json，参考图与实际页面已分别实读，不宣称 Human 视觉接受。最终候选重启、读回与 CI 另记私有交付回执，当前不宣称 Native 已执行。
