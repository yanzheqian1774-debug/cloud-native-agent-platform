# 324 系统性续接：有界诊断与实施增量

沿用原计划、分支与 PR #186。2026-09-22 用户要求同步推进 A/B/C；此文件是原计划的实施增量，不替换既有规划。

## 当前事实与问题矩阵

|问题|根因证据|分类|影响入口/修复位置|验证|架构决定|
|---|---|---|---|---|---|
|真实规划30.7秒UNKNOWN|实际wrapper选择planning-original-d6.json(5/30/60秒)；323 planning.json为5/55/60；stage脚本用timeout revision.previous_read_seconds恢复原配置摘要|配置选择与授权修订衔接缺口；供应商是否处理仍未知|runtime装配、configured_limits、context admission|无真实调用的配置解析/worker传递测试；保留本次receipt|改变独立签发配置需追加决定，不能改原摘要|
|旧主体名称/委托耦合|demo324固定映射human:demo323-requester；新context记录324但复用323账本配置，主体显示不是账号名|已批准兼容映射与产品表达；不得假称新主体|local_accounts/context_call_admission/UI身份|当前账号状态、scope、Grant逐项核对|自动任务范围准入属于新增G2|
|每对象逐项Grant且短窗口|generation requestability按purpose/owner/action；Grant一小时UI；session另有idle/absolute|授权衔接设计缺口|task授权与派生对象规则；单独D324-7候选|不复活旧Grant，撤销/越界/过期/UNKNOWN拒绝|是，先提出完整边界|
|正文与调用恢复不同|理解结果正文不由服务端完整保留；规划请求持久化；查询不调用|既有存储边界及恢复UX|各恢复入口区分动作|已有零重发证据复用；变化项补测|新增持久正文策略需决定，不静默落盘|
|Native管线Kubernetes替身|prepared_native_pipeline生产Skill/PG，但FixtureKubernetes与ExactTestAuthority|真实环境验证缺口|独立合成计划、正式owner装配和真实Kubernetes端口|禁止导入标明非acceptance的seed，禁止构造Human批准；隔离实际执行/产物/重启证据|既有契约内准备自主；正式准入由本人|
|用户手填Employee并发版本|生命周期表单要求expectedAggregateVersion|局部UX缺陷，需保持CAS|Employee读取/命令表单，版本从服务端取得|过期版本冲突、刷新不重发、同视口图对照|不改CAS语义；接口增量G1|
|审批返回无权业务列表|审批页默认返回列表/工作台，审批人无业务LIST|局部路由/恢复缺陷|精确对象返回、操作清单|业务/审批隔离，保留query，无越权读取|否|

## 实施顺序与边界

1. A：追溯55→30的确定证据、实际直连/代理/worker期限；查供应商公开查询契约。UNKNOWN、20次及新增USD0.688128均保持。离线验证配置候选，不新增真实调用。
2. B：读取已有Native契约/测试和正式装配，准备独立隔离环境与明确合成计划。实际执行必须使用生产worker、Kubernetes端口及Skill owner；不得用fixture授权替换准入。先补技术准备；需要本人签发时与D7一次集中呈现。
3. C：实施前逐页读取本机图集、索引/版本与实际基线映射。只修阻断交互；CAS自动取值不放松冲突检查。没有依据的状态写局部设计说明。
4. 汇总D324-7 PROPOSED：任务范围授权与派生对象规则、配置修订承接；新的模型次数/金额另列明确未批准，不隐含在产品方向中。
5. 仅验证新增风险：配置传递、真实Native缺口、相关入口/恢复。正常门禁和CI；最终交付区分隔离能力、同案真实链路、待人工/外部依赖。

兼容：原323所有记录只读，原policy/Grant不改；不改CRD、公有状态语义或引入持久基础设施。独立验证不得改原案例记录。未获决定的授权机制不实施；其余工程继续。

## C1 局部实施设计（先于修改）

Employee精确读取已有owner聚合版本，BFF projection遗漏。增量返回aggregateVersion，前端类型接受可选字段兼容旧服务；操作准备时重新GET所选精确修订，在同一身份下冻结服务端版本/摘要，用户仅确认业务动作。版本缺失或状态已变化时拒绝准备并显示刷新说明；提交仍原CAS、原commandId幂等。未知结果不自动刷新版本再重发。
设计核验：本机R37-Design-Anchors-Review/README-R37说明仅新增6张、旧锁定图不自动替换；完整R35包D09实际实读，与R30 SHA256 08d6061f8a4395f9dacd0467dacd1bc36bf61cd533326170cf545f892ffe89a5一致。保留现有框架/卡片，仅将技术版本输入替换为自动核验说明；确认区保留版本于技术详情，不借图中已启用示例伪造状态。
验证：BFF精确READ版本投影、无READ不能泄露；浏览器无手填、显式确认才POST、版本变化拒绝、未知结果同key不变。无迁移、无新权限、无生命周期语义变更。

## 本轮实施与仍未就绪的前置

已实施：Employee精确READ投影aggregateVersion，准备动作重新读取并冻结；Native装配CLI必须传入精确plan-id/version/digest；交付Skill依赖、操作及executor revision/digest在创建实例前校验。旧成本Plan不再作为默认值。CLI调用方须显式提供三项参数，未提供时不发生写入。

隔离预检已读取真实Kubernetes Task CRD，交付READ_DATA→RENDER_REPORT契约有效；独立scope没有preparation，namespace尚未创建，未派发。预检不是正式Plan，也没有Approval、独立执行准入或Human结果。

剩余接线：execution_successor/validate_approved_preparation仍使用成本专属SYNTHETIC_ONLY边界；所选required资源仅支持EMPLOYEE/KNOWLEDGE，其他kind必须在计划确认前展示并完成准确映射。不能用替换成本案例名称或伪造审批消除此限制。真实规划与独立合成验证均须走同一正式执行契约，未解决前不得标记执行就绪。

新增浏览器测试首次失败是测试在异步POST到达前读取数组、随后错误地定位status角色；错误快照已显示正式409冲突正文，版本7已实际发送。改为等待请求观察和精确可见冲突正文，不改超时、不弱化CAS断言。修正后该项通过；另外三项生命周期测试已通过。

前端功能与视觉分开：本轮lint/build通过，尚未完成更新后真实服务的同视口对照；不以TEST_ADAPTER浏览器测试作为视觉接受或实际业务执行。旧运行后端尚未投影新字段，兼容前端将明确拒绝准备命令而不是猜测版本。

### 最终候选CI发现的真实owner缺口

0f4ed09 的 PostgreSQL Business Problem and Plan Entry 在两项Employee精确读取/撤销测试失败，KeyError aggregateVersion。根因是普通owner.read已有字段，但read_revision_for_workbench独立SQL投影没有；初始单元替身人工提供该字段，未覆盖真实SQL路径。已在同一授权事务/FOR SHARE内选择definition.aggregate_version并返回，不新增授权、不读取其他修订；真实PG两项回归通过，继续核查相邻授权路径。保留失败job106698749023；不得以重跑掩盖。

## 交付场景接线增量（2026-09-22，实施前 G1）

沿用用户已批准的交付专用能力适配。执行后继请求增加有界case=cost/delivery（默认cost）；cost请求摘要继续按旧字段计算，旧幂等身份不变。delivery使用交付专属合成限制；原图、目标、标准、成本及任务均保持，通过正常后继确认。执行准入按参与者的精确executor区分边界，禁止delivery套用cost边界。required SKILL选择必须精确等于参与者Skill；MCP/WORKFLOW仍拒绝，不扩建owner。无新权限或自动确认，D7待审不实施。

验证：旧请求摘要/后继不变、delivery边界生成且成本声明缺席、错用executor/资源拒绝；既有PG正式后继/Native管线回归。对象准备只用正常owner入口；无有效Grant或缺少无模型合成计划来源契约时保留准备材料，不向库注入批准或伪造invocation。404使用当前session及只读PG诊断授权时间/主体/scope/精确对象，保留发布。前端如无修改，复用c74b880修改页D09基线并补实际页面对照，权限拒绝不能算已发布详情的视觉接受。

### 实际页面发现的相邻入口缺陷及G1实施增量

真实Chrome登录前URL含完整Employee ID/revision/section，提交后却到/work；safe_return仅允许work/authorization，故加入本批实际只读页面的精确白名单（不放行api/外站/路径逃逸）。另运行脚本直接挂载共享dist，普通测试构建将VITE_PROBLEM_DRAFT_ASSISTANCE清除后实际页面退化手工模式。为构建生成非秘密模式清单，serve校验模型装配需要assistance=enabled，并按内容摘要复制固定前端包，测试build不再改变运行资产。无新业务权限或模型调用；验证清单不匹配拒绝、源dist后续修改不影响固定包、真实登录返回及截图。

## D324-7 A/B批准后的实施增量（2026-09-22，原计划续接）

A与B分别ACCEPTED。先实现可审查的授权契约与追加持久记录，再接正式owner及入口，不将批准文本转成实际签名。

1. 任务授权owner：精确root/scope/subject/account revision、阶段动作、资源/config摘要、8小时上限、显式续期及撤销；派生血缘同scope。正式owner创建绑定，客户端不能认领任意对象。
2. 预算/config：追加次数修订，原8及D6=20保留，D7=21只适用精确后继；共用reservation事务和全部历史金额。签发值/运行值在效应前相等，60秒总期限含读取，2秒仅清理。
3. Native：正常计划owner新增明确无模型合成来源；确认前无Run，原AI proposal摘要兼容。隔离root/scope独立，不继承原案例Grant或发布决定。
4. 拒绝测试：跨scope/root、过期/撤销/账号版本、来源冒充、配置漂移、未知结果重发、并发次数/金额与旧摘要兼容。迁移先在隔离PG验证，再正式运行装配。
5. 实际对象只通过正式入口准备；完成入口预检后集中提供独立本人操作。真实规划/Native分别报告，未形成实际产物不得报告执行完成。

### D7第一组实施证据与仍待接线

A/B分别已登记ACCEPTED。追加0039任务授权、0040精确规划后继；原policy=8、D6=20、D7=21按适用对象选择累计上限，不相加。统一预算owner保留全部预留。任务root/scope/账号修订、有效期、撤销及配置漂移拒绝；撤销后继不回退旧任务窗口。合成proposal显式origin且invocation为空；旧proposal JSON/digest不变。已有实际资源不重新发布。

真实PG已通过任务签发/撤销/账号变更/跨scope/幂等、D7第21次并发幂等、原金额上限及终态拒绝；9项最新针对性验证见本机s5-324-d7-final-authority-tests.log，29项相邻PG见s5-324-d7-pg-adjacent.log。真实账本只读仍20次、USD5.956372计费及预留；配置55候选f592f2e2b55fce9c64b9b3d1fd7a919f21e452991859b9b572d1649170e73ca6仅暂存，尚未切换实际运行/签发/调用。

新审核页按IAM07局部映射，实现精确task链接、显式独立签发、4小时窗口、状态查询/撤销。浏览器视图测试1项通过，刷新零重签、长正文可达；初始测试漏session schemaVersion，未放松产品校验，保留失败。正常make check已通过（2170 passed，384按专用环境条件跳过）；新增PG已在专用PG运行并纳入既有CI PG job。新增PG首次普通门禁漏环境条件、测试pool清理调用错误均已修正，未改变断言/超时。

待办：真实服务升级/入口预检；正式task对象创建及独立本人签发；精确规划后继创建后模型准入。Native隔离root/scope尚需独立环境和正式owner资源准备，不将合成规格当作Run。实际同视口截图和Native执行/产物/评价均尚未完成。
