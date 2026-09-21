# ARCH-323 下一批交接草案：同案资源准备到结果决定

状态：PROPOSED / NOT_IMPLEMENTATION_AUTHORIZATION。属于原计划§26 A/B/C及§6增量二的细化，不分配新Task编号，不重开323，不改变D2/D3或版本归属。2026-09-21基线：#184普通合并d26018bd8a24ef7e55200963fa39744e335b973d。原计划及Registry仍为权威索引。

## 目标、起点和不变量

下一任务建议名称：同案资源准备、只读执行与标准验收闭环。起点为原成本Problem `59a1d736-96d5-5060-8ae3-293d82b4b74b`、Plan `5ad74afd-a6bf-4b04-b395-34d18d01c3b6` v2、Approval `6d30f690-d10b-4e6c-afcf-4d8ccea14e4b`；精确摘要见已入库`productization/closure.json`。不重新理解、生成或确认来替换既有事实。任务中若改变批准语义，必须正式后继并重新确认。

交付目标：页面从已确认计划发现缺口、选择权限内精确资源、准备分工与Runtime准入；经新的明确执行授权启动一个Run，展示Task/Attempt真实状态和产物；terminal Run上形成Criteria Evaluation与Human结果决定，刷新/重启后读回同案身份。资源可见不等于可调用、准备完成不等于执行许可、技术成功不等于业务验收。

D2为已接受并实施的confirmed-Problem plan-suggestion用途。D3仍`DIRECTION_ACCEPTED / EXECUTION_CONTRACT_DEFERRED`：同Run下Task级多员工绑定方向成立，根/Task Assignment详细契约未接受。原I2.1–I2.6原号保留，I2.5是标准评估/验收，不将D3等同整个增量二；v0.2.3 Runtime闭环归属不挪到其他版本。

**必须集中解决的范围差异**：原§6估算最多五Task、两职责、线性链且I2.4示例三阶段五任务；当前成本v2四阶段六Task，t4依赖t2/t3，不能硬套五任务、逐Task各开Run或忽略依赖。建议D3包接受有上限的静态无环依赖子集（覆盖此六Task，禁止动态DAG/循环），阶段显示从Plan读取；准确上限及超限行为由同一决定包批准，不静默修改原估算。

## 可复用实现、需要补齐的接缝

| 原编号 | 复用 / owner | 下一批交付 | 准入与验收 |
| --- | --- | --- | --- |
| I2.1 | `execution_application.py`、`execution_repository.py`、`execution_postgres.py`、`governed_execution.py`、`workflow_control_application.py`；现有Kubernetes依赖ready/skip语义 | 同一Plan/Approval→单Run；typed root/Task参与绑定，Definition exact→Instance→Assignment；任务依赖与I/O适配 | 批准/版本/scope/撤销/有效期校验；并发重复start只产生一个Run；跨计划/过时批准拒绝；根Assignment不代理Task权限 |
| I2.2 | `PlanningResourceResolver`、Employee reader、`PublishedRoleMatcher`、Skill/MCP/Knowledge owner、`skill_invocation_*` | 权限内候选、匹配依据、精确发布版本、schema/能力/运行条件及只读来源；追加准备快照 | 区分MISSING/UNREADABLE/UNKNOWN/UNAVAILABLE；同名不等于匹配；费用六任务正例、采购旧职责错位负例；资源缺失阻断执行而非批准保存 |
| I2.3 | `native_dispatch_application.py`、Native worker/Placement、现有managed Skill adapter | 每Task唯一effect owner、每Attempt单managed Skill；Native优先最小只读运行，固定provider/profile | 不重复Native与同步Skill派发；真实运行/输出/Evidence而非fixture进度；OpenClaw不以#169只读连接冒充execute |
| I2.4 | execution/resource-use typed records、既有PG/Evidence readers；任务/结果UI组件 | 有界产物schema/digest/size、Task/Attempt/Plan lineage、时间与stage聚合、输入产物引用 | stage依required Task事实；UNKNOWN单独显示；缺账单仅产出数据缺口报告，绝不生成虚构归因或节约 |
| I2.5 | ARCH-264及既有Criteria/Evidence/Outcome边界 | terminal Run→exact Criteria/Evidence snapshot→Evaluation→HumanConfirmation→Outcome；typed services/repos/API接线 | 自动可验证规则与Human判断分开；NOT_MEASURABLE/UNKNOWN不填0；拒绝/分歧追加保留；可信actor，非模型代判 |
| I2.6 | 既有claim/fence/retry/intervention/dispatch观察与PG读回 | 崩溃后同Run恢复；合法只读重试新Attempt；暂停请求/ack分离；刷新零effect | 双worker不重复、失去权限/过期fail closed、未知不自动重发；恢复先读持久事实，取消不等于远端已停 |

现存业务闭环只到Plan/Approval，当前成本两项必要资源未准备；Skill/MCP/Knowledge候选owner接线和无Workflow匹配契约未完成。`GovernedExecutionApplication.start`旧exact批准/单Skill路径不是323 v3六任务兼容证明，不得将start当预检。原采购Plan按旧契约不符合，仅用于拒绝准入回归；要执行采购必须另作语义修订及确认。

## 下一批一次性决定和数据边界

建议在编码前形成一包G2决定，不在实现中逐项追加：

1. D3 root Assignment职责、Task参与绑定、单Run唯一性、授权交集/撤销/过期、并发幂等、静态六Task依赖及terminal/skip/failure/UNKNOWN状态表；旧Plan不自动迁移。
2. 无Workflow时，以已批准Plan的typed operation/I/O建立候选匹配和执行映射的owner契约；是否要求受治理Workflow revision、何时改变Plan需重批、匹配快照何时失效。推荐显式映射快照、exact引用、执行前重核，不凭名称匹配。
3. Artifact有界schema/大小/保留/权限、Evidence与Criteria Evaluation关系；复用PG与现有Evidence owner，不引入新文件服务/平行账本；若现有存储不能满足才另列基础设施决定。
4. Native首条运行与OpenClaw后续强制垂直切片的界线。#169当前execute/lifecycle仍UNSUPPORTED；选择OpenClaw执行必须先接受明确adapter行为/取消/回执契约并补实现，Hermes/完整Fleet非本批默认范围。

执行授权需明确：隔离namespace、安全域、原subject及独立批准主体、单个已确认Plan/Approval、只读数据来源、Task operation白名单、资源revision/digest、每次及总技术上限、输出大小、重试/取消/UNKNOWN处理。现323持续开发授权不是新的业务执行许可；身份技术有效期与任务授权分开核验，不能自批或恢复撤销权限。

推荐数据方案：合成费用账单/用量/分摊资料、明确合成标记、独立受控只读MCP或fixture-backed正式资源入口；不得读取真实企业订单/账单，不允许外部写入/采购/付款。输入若仍未提供，只交付真实缺口与不可评估项，不声称完成成本分析。运行记录/产物的必要追加写入归平台owner，与修改来源业务数据严格区分。模型如用于分析，另明确模型用途/配置及精确资源授权，保留原账本UNKNOWN，不复制账本规避限制。

## 未合并PR与最小集成顺序

2026-09-21重新核对远端：下列HEAD均与§26原审计相同，全部仍OPEN/Draft；旧CI不是本次组合验证。以d26018b进行无改分支的merge-tree复核，均存在冲突，具体清单见`final-integration.json`。

| PR / HEAD | 用途 / 依赖 | 下一处理 |
| --- | --- | --- |
| #163 `141a17e` | Model治理核心已按内容入main；0019同摘要；当前4文件冲突 | 归档残余诊断/文档后提出替代关闭，不整支合入；本轮未关闭 |
| #164 `5a32fbb` | 可信BFF/权限核心已由REL-316接收；0020同摘要；14文件冲突 | 保留main加强authority，核残余再建议关闭 |
| #170 `020c1d6` | Problem/Criteria旧入口核心已接收并演进；0020同摘要；32文件冲突 | 保留原证据，不还原旧工作台，残余清点后建议替代关闭 |
| #166 `b0f934e` | Workflow画布、节点与依赖编辑，独立需保留 | 当前harness冲突；仅当选择Workflow映射路线列为前置；刷新组合CI和真实UI |
| #167 `bb1f821` | Knowledge预览/来源/中文，需保留；无SQL新增，pypdf/锁文件 | 当前CI workflow冲突；只接链路必要知识能力，不自动扩大解析/存储范围 |
| #168 `388b6e3` | Skill/MCP目录、exact详情与复用，资源链优先 | harness及test两冲突；保留双方诊断/回收断言；补产品审阅与当前组合门禁 |
| #169 `947a4ca` | OpenClaw固定版本只读连接/PG恢复；0021依execution0008 | 原浏览器CI失败仍在，execution_postgres/operator/Registry三冲突；先修与Native共存/升级验证；不作为已支持执行 |

建议先D3/匹配/数据包决定，再按所需资源集成#168与#167；若必须通过Workflow编辑映射则#166先行。共享harness单owner串行协调，不因编号排序机械全合。#169单独修复，不阻塞Native最小路径，亦不取消v0.2.3 OpenClaw后续义务。#181/#183/#184已入main，#182包含后关闭；来源分支保留。编号0021已有owner，不抢占/重编号；后续迁移必须按domain ledger核验checksum/兼容，不执行全目录盲升级。

## 图集实读与下一批视觉约束

实际目录`/Users/tristan/Downloads/Resource-Management-PC-R29`。VERSION/CATALOG为R29，index title为“企业智能体平台 · 产品与体验 R29”；VERSION状态为“按认可视觉方向实现Index；待页面审阅”，179当前图、105历史图，R29新增图片0。已读index、CATALOG、PAGE-CONTRACT、Memory-Context契约，核验选定文件对R29-MANIFEST的SHA256全部一致。逐文件完整摘要见`next-gallery.json`（版本标签不是接受证据）。

本轮实际打开P08、D07、D09、W06、R04、O08、H05、H06图片。P08参考主区候选/匹配解释、右栏缺口；D07/D09定义/实例/分工分离；W06输入输出映射；R04保存分配不启动；O08同Run/Task/Attempt/Evidence空态；H05真实进度/暂停请求；H06产物/标准/Human决定分开。下一批编码前还需逐页打开其最终采用页面（包括S/M/K详情），绑定明确图片与交互契约。

集中差异：P06 pages标R26而revisionAudit仍R20，Memory契约末段仍沿用旧323状态，不能当当前授权；H05/H06保留旧英文平铺导航，P08/D页分组导航不同，O/R图为新增待审稿，所有示例用户/日期/任务数均非真实事实。应一次确认适用页/公共导航及状态组件，而非自行拼混版本。原323仅R24 P06/IAM01局部接受，IAM03安全功能接受、视觉非阻断；不被R29覆盖。

布局、蓝白配色、字体层级、导航、右栏、紧凑底部输入及滚动依据最终绑定图/契约；功能数据可适配六任务，不能按示例固定五任务。未覆盖状态复用已有组件并列差异。交付同视口参考/实际截图，验证长中文、缩放、滚动、输入/发送/右栏；截图与功能测试不代表Human视觉接受，实际投影未做则如实列出。

## 实施顺序、测试与最终验收

1. 固定届时main、owner与上述集中决定；核对精确资源/数据授权，形成G1与逐页设计绑定。无权限可继续契约/受控验证，不伪造可执行资源。
2. 接入必要owner reader与资源PR，保存准备快照；补合法与拒绝准入测试，采购历史负例必测。
3. 实现I2.1/I2.3同Plan单Run及静态Task协调，先受控再获准隔离只读执行；I2.2数据与Skill/MCP逐任务接线。
4. I2.4产物/过程可视与I2.6恢复并行设计但串行验证effect；通过重启/并发/权限撤销/UNKNOWN测试后再真实跑完整同案。
5. I2.5 terminal Run标准评估及Human结果决定；最终刷新PG与Evidence读回，同一链路身份一致。

测试矩阵：六Task/多依赖、缺资源/权限/版本漂移、输入schema不符、artifact缺失/篡改/超限、重复start、worker crash/fence、已知失败/UNKNOWN、取消请求无ack、重复无进展停止、刷新零副作用、旧批准/账本完整、Human拒绝及后继结果历史。自动评估不替代Human，真实与受控证据分开，未知用量不记零。

本批必需上下文仅为同案Problem/Criteria/Plan/已确认纠正/资源快照/Attempt/Evidence精确引用；优先已有信息，真正决策才少量选项+自由输入。公共组件仅修复该链路复用/状态安全所需部分，不建立新长期记忆权威。完整Fleet、客户端、全面资源改版、组织管理、多任务交叉协作、通用Agent自治、跨Runtime迁移进入后续待办；新中文理解真实验证若非此链路必要不绑入执行验收。

完成条件：页面可从原批准计划到一次有权只读运行、真实产物、逐标准评价和Human决定；审计可证明Plan/Approval→Run→TaskRun→Attempt→Evidence→Evaluation→Human结果全链关联；来源只读、旧数据/UNKNOWN保留、独立权限有效、无模型/执行重复；主分支精确候选CI和视觉范围分别交付。任何资源/权限/执行契约缺失则阻断启动，保留准备成果，不能宣称端到端完成。
