# ONTOLOGY-BUSINESS-02 — 真实销售数据只读试点准入方案

状态：PROPOSED / NOT_IMPLEMENTED。2026-11-04。用户授权本轮展示页面、视觉交互修正、真实业务条件与集成差异梳理；原ONTOLOGY-SALES-01只批准合成数据只读验证。本决定不由旧批准自动继承。

## 需要决定什么

推荐选项B：在现有PostgreSQL和原有Knowledge/Planning/Execution/授权owner中，增加真实数据的版本化合同和只读微型试点；先采用业务方正式导出，不连生产ERP，不写回，不增加模型调用，不新增图数据库或审批权威。

选项A：继续合成路径，只做真实数据字典/对账准备与离线口径核验。改动少，但不能完成平台内真实业务运行验收。

选项B（推荐）：新增真实数据合同、来源清单/分块读取、真实只读executor和独立评估，接回现有规划与结果旅程。可在受控范围验收，数据由责任方批准后才接入。

选项C：直接连接生产ERP/CRM，自动抽取和持续同步。需要额外连接器、凭据/网络和增量一致性设计，当前没有数据源及授权证据，递延。

G2触发：AGENTS.md要求架构门；ARCHITECTURE_GATES.md规定“frozen Contract changes”“State architecture”“authentication architecture”“cross-plane ownership changes”须先有架构决定。真实数据分类、用途/来源批准进入执行承诺，属于需明确决定的合同与授权边界。本方案尚未执行；页面修复不依赖它。

## 已验证的阻断点

1. OntologyContent只接受business-ontology.v1且synthetic=True；SourceMapping只允许sales-diagnostic-source.v1。
2. ExecutionPreparation及其v2本体子类只允许synthetic=True、ISOLATED_SYNTHETIC_READ_ONLY；OntologyPlanOrigin为HUMAN_ONTOLOGY_SYNTHETIC。
3. ontology_planning要求SALES_SYNTHETIC_ONLY；生产查询的validate_source拒绝非合成来源；executor配置和独立评估器均固化合成分类。去掉一个前端标签不能改变这些合同。
4. 现有CSV底层虽支持4MiB/10000行，但本体路径要求单文档/单chunk；Knowledge每chunk4KiB，pack总512KiB。已发布Skill限输入512KiB、输出256KiB、属性4096、深度16；依赖结果和来源重复携带后，真正可用容量更小。不能承诺“企业一万行已经可用”。
5. 业务方尚未提供真实导出、权威系统、口径签字、独立对账结果、访问/用途和保存期限。当前不存在真实业务验收PASS依据。

## B的具体新增与复用

### 数据、来源与责任

- 新增enterprise-sales-source.v1与enterprise-sales-manifest.v1。synthetic明确False；固定两个已结账期间、时区/会计期间、业务范围、CNY币种/两位小数、净销售额和成本定义、唯一分录键、源系统/导出时间/截止时间、原文件SHA256、字段映射、维度版本、行数及分币种控制总额。
- 先接受数据负责人批准的完整小范围导出。原始行身份可用脱敏稳定键，但必须可由数据方在受控系统追溯；不索取客户姓名、联系方式、银行账户等非必要字段。脱敏真实数据仍是ENTERPRISE，不能改标合成。
- 复用Knowledge的不可变pack/chunk、独立发布与精确READ。增加manifest驱动的受限row-batch读取适配器：每批是完整规范JSON并有chunk摘要、顺序/分录范围和全局逻辑快照摘要；逐批验证再合并，不把向量检索当权威读取，不依赖trim后拼接还原原CSV字节。原文件摘要与规范快照摘要分别保存。
- 不新增数据owner或对象存储。超出已有pack/Skill限额时拒绝，并缩小明确业务范围；不静默截断、不抽掉异常行。批处理/对象存储扩展另评审。

### 合同与运行绑定

- 新增business-ontology.v2的ENTERPRISE变体，明确允许来源schema、数据分类和用途，保持v1模型/摘要原样；读入口按schema区分，不把旧True字段放宽为任意bool。
- 新增execution-preparation.v3（EnterpriseOntologyExecutionPreparation），synthetic=False、AUTHORIZED_ENTERPRISE_READ_ONLY。绑定exact ontology/mapping/query/manifest/source/Skill/executor、业务范围、用途、截止时间与真实数据批准决定引用；这些都进入批准前摘要。
- 保留v1/v2字节、摘要、Plan/Run ID、旧拒绝语义；parse按版本分派，未知版本拒绝。数据库能力记录在实施前清点迁移编号后追加，不抢占编号、不改旧receipt、不允许旧writer继续写新版本。
- 复用BUSINESS_ONTOLOGY USE、Knowledge READ和原任务/Skill/ResourceUse/执行权限；新增的数据用途/范围批准由已有来源/执行owner记录真实主体、精确目标、有效期并在准备/派发/结果读取时校验。浏览器不能自声明“已获批准”，不能用本体USE替代数据访问授权。
- 新的EnterprisePlanOrigin如HUMAN_ONTOLOGY_ENTERPRISE_READ_ONLY；不得继续声称HUMAN_ONTOLOGY_SYNTHETIC，也不伪造模型生成/人工签字。业务数据批准、资源审核、Plan确认、执行准入、最终业务结果决定分开。

### 执行与独立评估

- 新executor enterprise-sales-readonly revision1；仅READ_DATA/VALIDATE_DATA/SUMMARIZE/RENDER_REPORT，保留SUM/SUBTRACT、取消排除、退货符号/口径、分币种处理及来源行。初期仅CNY，不隐含汇率和跨币种合计。
- 新独立评估器ENTERPRISE_ONTOLOGY_SALES v1，整数分单位核算，不调用生产聚合函数。成功标准绑定exact源、manifest、口径和独立财务控制表。没有成本或口径未确认时阻止毛利指标，不补0。
- 观察性差异和分组贡献不升级为经营因果或已解决。业务负责人独立判断结果可用性与后续行动。
- 默认不需LLM；若后续要求自动解释原因，模型身份/来源证据/预算及提示版本另做适用准入，不继承旧模型授权或用推断填补缺字段。

## 首批数据与验收边界

一个法人/明确业务单元、一个币种CNY、两个完整已关闭期间、一个业务负责人。建议20—50条完整分录起步，包含正常销售/退货/取消和零基期边界；如果真实范围没有某类异常，不能造入真实数据，沿用独立合成回归补边界覆盖。行数不是容量承诺：对规范源、依赖输入、产物和报告完整预检，必须同时满足pack/chunk、Skill字节/属性/深度和API上限。

来源系统待数据负责人指定：净销售额/成本应由负责入账确认与成本归集的权威系统导出；CRM机会金额不能未经口径转换代替已确认收入。系统品牌、负责人及权限均未假定。

验收建议（待业务方确认）：

- 完整性：批准业务范围的源行数、唯一键、两个期间、分币种净额/成本控制总额全部一致；必填字段和维度匹配100%，无未解释重复/漏行。
- 金额：按批准舍入规则，与数据负责人独立控制表逐币种/期间/指标/必要维度精确到分；差额0.00。若源系统有特定舍入差异，须事先明确规则与逐项解释，不设置笼统误差率掩盖问题。
- 可追溯：每项金额、变化、贡献和排除行均能回到原始分录及exact版本；汇总与明细可复核。
- 操作：一次批准业务范围后，技术人员准备的资源与任务全部走原owner；无重复Run/调用/产物，撤销/过期/错scope/错误来源/错误口径全部拒绝，GET无派发。
- 业务：负责人确认至少三项可核实观察（或确认无显著变化），记录证据与使用决定；没有强制“诊断必有原因/问题必须解决”的伪成功门。
- 性能目标建议：微型固定快照本地只读运算≤30秒、结果页就绪后展示≤3秒；这些是待确认目标，不是已测真实业务SLA。

## 与当前平台的集成顺序

当前对比固定：本体3001406；并行平台969775c。共享工作区未写入。后者另有未提交D11提案，状态PROPOSED，不能据此自动实现政策审批。

I1（可复用/普通整合）：先在独立候选合并SourceChangeOrigin与OntologyPlanOrigin两种来源；旧None序列化不变。保留P08/P10候选发现/正式来源更换与本体精确绑定，并复用已有GET自动读回hook和共享导航/结果组件。只做合成兼容，不启动历史案例。

I2（B批准后）：真实manifest/版本化定义/准备v3/独立executor与评估；数据方批准后建立新的业务问题与标准、资源/实例/Plan和有限精确权限。现有页面的JSON导入保留为技术维护入口，业务入口从问题工作台选择已发布口径/来源，不要求业务用户复制JSON或授权ID。

I3（B批准后，依赖D10已接受机制）：来源更换必须同时处理新source/manifest、新ontology mapping revision、bindingDigest以及内容绑定标准。现有D10仅允许标准applicability的sourceContentDigest变化，不能通过删除bindingDigest绕过。新增明确的本体来源影响合同，证明规则/单位/目的未变才能沿用业务含义；改变退货/收入/成本口径须新的业务决定。保留旧来源、标准、Plan、Run、UNKNOWN。

I4（不随B自动批准）：D11政策资源发布/自动确认是另一决定的责任；在其接受并验收前，继续使用现有真实主体审批。生产ERP连接、跨系统维度治理、增量同步、汇率、写回和企业级容量扩展均不在本次B内。

## 分阶段交付与停止条件

B1：合同/数据导入适配及旧v1/v2回归；交付typed schema、data manifest、失败分类与容量预检证据。
B2：独立环境用获批真实微型快照完成Plan→3任务→产物→独立对账→业务决定；交付exact资源、审查/权限/Run证据、0.00差额及业务反馈。
B3：在固定平台集成候选复验工作台旅程、旧供应商/销售回归、撤销/过期/UNKNOWN保持与重启读回；交付冲突解决和视觉证据。合并/发布仍须其原有门。

任一数据来源未确认、口径/成本不全、权限未批准、容量超限、对账差额未解释或UNKNOWN出现，即停止后续派发；不改分类、不放宽断言、不重复旧运行。

需要用户决定：是否接受B的增量真实数据合同和有限只读试点。接受架构不等于已提供数据、已获得企业访问权或已接受业务结果；具体数据方、范围与标准须按下列清单确认后准入。
