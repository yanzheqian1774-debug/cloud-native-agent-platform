# ARCH-323 身份连续性 G2 决定包 v1

Decision Status: PROPOSED — 待 Human 决定。Implementation Status: NOT IMPLEMENTED。

关联：原计划§27.4、323产品化回执、PR #184。Session OPEN；仅323本地隔离验证。本文直接固化既有阻塞与建议，不重新申请模型、费用或同范围持续开发授权。Human本次要求提交决定包不等于已批准新身份语义；批准记录须追加实际决定及时间。

## 1. 请求决定与推荐

批准 `task-delegation-continuity.323.v1`：在现有PostgreSQL及Authority Foundation边界内，以追加记录表达原委托在新有效身份代次中的连续性。旧凭据/代次文件、委托原文、动态Grant、调用、UNKNOWN、预留和结算不改写。它不是新身份权威、第二账本、一般跨代次授权或撤销恢复机制。

当前阻塞已查明：两名原主体凭据过期；0028委托绑定generation/recovery_epoch，active()拒绝跨代次，同task/subject/root/ledger存在唯一绑定；0031只支持精确读取期限修订。更换凭据不能自动让原委托生效。按Architecture Gates的“authentication architecture”须G2决定。

推荐追加连续性记录；拒绝直接改旧generation/expiry、复制新委托绕过唯一绑定、放宽active()、改主体/账本和调用方自批。保留现状作为替代，则仅交付受控候选、原实例只读，真实新增中文验证继续阻塞。

## 2. 可信代次关联与签发主体

1. 旧代次取原委托记录中的generation/recovery_epoch，并绑定旧Authority配置完整摘要与旧委托摘要。新代次必须是同一部署、同一databaseFingerprint、同一scope通过现有受信operator代次激活机制加载并由Authority Foundation校验的新配置；配置摘要不匹配即拒绝。
2. 固化operator身份、旧/新generation及各自configuration digest、同一recovery_epoch、激活审计事件引用。不能仅凭principal_id字符串相同、文件名、调用方提交的JSON或旧过期凭据证明连续性。摘要证明内容绑定，信任来源仍是现有受控operator加载与权威审计，不新增自制签名权威。
3. 原subject与原独立issuer的主体标识、tenant/security domain必须逐一相同；旧、新credential_id分别绑定同一主体，由新受信配置明确证明。旧credential仍保留且不再接受认证。新credential不得复用旧秘密，不输出其明文或hash到公共PR/日志。
4. 连续性签发者必须是原独立issuer在新代次的当前有效身份；通过正式登录，拥有当前精确 `GRANT_ADMIN / DECIDE / grant-scope:<tenant>:<security_domain>`。在事务内用has_current_grants重验，包括static Grant，不接受dynamic-only替代。签发者不得等于subject，调用方不得持有/使用issuer凭据代签。
5. 原issuer无法安全恢复、scope改变、recovery_epoch改变或旧主体被撤销时，本v1拒绝；不自动指定替代issuer或桥接灾难恢复epoch，须另行明确决定。

## 3. 继承范围、撤销与有效期

连续性仅使已签原委托在目标代次可被评估，**不复制或自动恢复任何Grant**。每个实际操作仍须当前精确权限检查；必要新Grant沿现有独立申请/签发机制取得，并逐项限制为原批准操作集合的子集。

不变集合：323任务ID、原subject/issuer、namespace/security domain、原理解root、已显式登记采购/成本case及各自精确对象、用途、原ledger IDs、配置及已签V2/V3/read55修订、串行准入、UNKNOWN恢复规则和计量。案例登记不重做，不跨案例借用权限。原持续开发授权保留；1U+4P、旧USD10/绝对窗口不重新成为总额度。

撤销优先：委托control、append-only委托撤销、development stop、credential tombstone、static/dynamic Grant撤销均检查。旧凭据自然到期可恢复；旧凭据被撤销不能借新credential_id消除其撤销影响。本v1对原subject/issuer凭据或委托显式撤销一律拒绝连续性。Grant被撤销则该权限不继承，连续性批准不抵消撤销。签发后撤销立即阻断后续准入，并进入现有有界取消/回收；已发出远端调用仍可能UNKNOWN及产生费用。

建议技术有效期：签发时间使用DB时钟，not_before不回溯；expires_at不晚于签发后8小时、目标subject与issuer指定新凭据到期时间中的最早值。动态精确Grant还受其自身期限约束。8小时是单次恢复会话/凭据技术期限，不限制持续开发授权总时间；过期默认拒绝，禁止自动续期。批准本决定允许后续在相同边界内由有效独立issuer追加续期记录，不需重新申请模型/费用，但每次必须正式签发，不能由调用方自动续签。

## 4. 追加记录、并发、幂等与历史兼容

新增连续性记录建议字段：版本、continuity_id、原delegation_id/digest、predecessor_continuity_id/digest、旧/目标代次与配置摘要、epoch、databaseFingerprint、subject/issuer及旧新credential引用、operator激活事件、精确scope/cases/config/ledger绑定摘要、签发依据、not_before/expires_at、idempotency_key、canonical_payload_digest、签发审计ID。仅追加；有效记录由权威事务解析，不改原delegation.generation。撤销事件同样追加，失效记录保留。

- 沿用同数据库事务与现有323治理锁，固定锁序：治理锁→active_generation→delegation/control→continuity链→ledger/dispatch guard。签发与撤销/代次切换并发必须线性化；提交前重新检查当前代次、撤销、有效期与前驱摘要。一个委托仅允许一个有效链头，数据库唯一约束加CAS防双签。
- 幂等域是scope+delegation+目标generation+操作类型+key；相同key/规范payload返回原记录；相同key不同payload拒绝，无新签名或副作用。不同key并发竞争同前驱只允许一个成功，另一方读回冲突。签发提交未知时先按key只读恢复，不能盲目重签。
- 签发记录不派发模型、不创建会话或业务对象。新模型尝试仍使用独立调用ID/key、准确case关联、正式admit与dispatch_guard。原ledger串行锁不能因代次变化而重置；先核验原worker已本地回收，UNKNOWN及预留仍保留，回收不代表远端停止。
- 旧代次会话不能通过连续性延寿；新会话须正常登录。GET、页面刷新、服务重启仅重建有效投影，不自动签发、续期或重发模型。
- 新迁移仅增表/约束/版本，沿当前migration顺序分配实际编号，不在批准前占用编号。旧二进制必须在启动/就绪时拒绝新的schema能力版本，不允许旧新writer同时运行。未设置连续性的旧路径继续原严格代次匹配；历史记录、摘要及旧请求签名不变。
- 回退优先停止新writer、撤销/暂停新连续性准入并保留新增审计；不能将已升级数据库交给不兼容旧writer，不能恢复备份覆盖新调用/预留。回退可进入只读维护，恢复服务须用兼容schema且不接受未批准准入的候选。

## 5. 配置与中文验证：不捆绑扩大资源权限

中文planning使用现有profile、Kimi、read55/total60/connect5、output8192、非流式及同ledger；请求策略版本独立绑定，不以身份恢复绕过配置摘要。外层循环默认3次/180秒、回收2秒为技术边界，不自动确认或启动执行。

中文understanding `v2-zh-CN` 目前只完成代码与受控验证，尚未加载。本决定**不自动授权模型资源发布或修改冻结的owner绑定/ledger配置**。本轮复用已保存Problem/Criteria与原理解证据，先在原成本case验证新增中文规划与修正。若完整新理解策略确需新的owner资源修订，激活包必须标为未激活缺口，不以通用profile变更条款代替精确权限；不得新增无关理解演示。

## 6. 实施决定与运行激活分开

### A. 本次请求Human一次性决定

批准第1–5节的323专用追加连续性语义及其G1实施、测试；并确认门禁/预检通过后按下述B执行一次集中激活包，沿既有授权连续完成真实中文验证。此决定不是运行签发，不授予调用方GRANT_ADMIN、不使过期凭据恢复，不是视觉接受。

### B. 决定后实施与唯一集中激活包

Codex先实现owner/domain/API/追加迁移、当前代次精确Grant评估和有效投影；测试完成并正常提交/推送#184 Draft。预检输出实际候选SHA/tree、迁移摘要、旧/新代次摘要、operator事件、原委托/cases/config/ledgers/UNKNOWN清单摘要、有效issuer及subject、精确操作/有效期、签发payload digest、启动/回收/健康检查与失败恢复分阶段清单。未准备齐不得要求Human盲目运行。

Human只需在届时提供的原正式operator/独立issuer入口完成集中包中的可信代次激活与连续性签发；秘密只经原安全渠道输入。该运行动作属于独立主体身份操作，不能由Codex代签，也不能用本G2批准文字伪装正式签发。实施前批准与后续运行签发是两种不同证据，不再追加同范围权限/费用确认。

集中包按持久状态恢复：备份与历史hash→停旧writer并核验回收→追加迁移/受信新代次激活→新兼容候选就绪→独立issuer精确签发→新subject登录/权限及配置读回。每步保存已完成标记；失败先读回，不重复迁移/签发/派发。服务认证不关闭；原case不重登记。提交后的签名证据由独立issuer产生，调用方只能验证。

### C. 验证和收口

必须覆盖：旧新配置摘要与主体绑定不符、epoch漂移、过期/撤销、自批/无当前admin权限、串行锁、双签竞态、同key重放/异payload、提交未知读回、旧writer拒绝、原精确case隔离、旧新会话、期限取消及UNKNOWN预留、页面刷新零重发。

激活后在原成本case使用已确认8,000元/排除试验项目/数据缺口，通过真实Kimi生成中文后继建议；自然出现可修正错误时由有界循环处理，若首轮成功则真实修正能力不得冒称已验证。不人为制造业务纠正或伪造模型自然失败；受控自动修正证据复用，真实修正覆盖不足时明确登记剩余缺口。计划确认仍需页面显式动作，只确认新后继、保留原Plan/Approval；刷新与PG读回同对象，记录用量、实际候选及历史差异仅为预期新增行。零Assignment/Run/TaskRun/业务执行。

## 7. 影响、兼容与验收边界

受影响：Authority Foundation已认可代次记录的消费、task_delegation/task_development、BFF管理入口、runtime就绪版本校验；不改Kubernetes/CRD、租户/组织模型或资源owner权威。主要风险是撤销被复活、权限跨代次扩大、并发双签、旧writer误运行；以上否定测试与fail-closed是必须验收项。

真实闭环、功能验证、视觉接受、投影测试与业务执行验收分开记录。#184 Draft / Session OPEN，不合并、生产部署或执行任务。
