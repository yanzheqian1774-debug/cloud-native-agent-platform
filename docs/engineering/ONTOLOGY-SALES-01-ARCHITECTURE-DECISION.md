# ONTOLOGY-SALES-01 — 业务本体与销售诊断运行绑定方案

- 日期：2026-11-04（Asia/Shanghai）。
- 决策状态：ACCEPTED；用户2026-11-04明确答复“批准选项B，继续阶段1—2”。
- 实现状态：阶段1—2已实现并完成隔离工程验证；真实业务、独立视觉与发布未验收。
- 任务授权：用户明确要求推进阶段0—2，普通问题自行处理，架构决策提交具体方案。
- 固定基线：`9df4c7fe95278fd85246abe3645ae7dfc244b485`，tree `8f9afe54ddcf1558734b1c71ae89782d9ad7509b`。
- 独立分支：`codex/ontology-sales-stages-0-2`。
- 合并、发布、生产部署、真实业务结果验收：本决策不授予。

## 1. 申请的决定及触发原因

批准在既有 PostgreSQL 中增加业务语义域，拥有本体定义与发布；由既有规划域和执行域消费精确版本，并引入只用于本体销售路径的版本化执行准备和权限操作。

这不是新增数据库，而是新增业务域权威、持久绑定和跨域消费规则。现有 `ExecutionPreparation` 是严格的 v1；资源绑定 kind 和授权 owner/action 是封闭集合，没有 ONTOLOGY。不能把 JSON 字段偷偷放进旧结构，也不能沿用 Knowledge READ 授权执行本体发布。AGENTS.md 和 ARCHITECTURE_GATES.md 将跨层归属、State 架构与授权语义变更列为需要架构决定的事项。

用户已经授权阶段0—2工程工作；本次只申请下述具体架构差异，不重复请求普通开发测试授权。

## 2. 当前能力与缺口

| 已核查实现 | 复用方式 | 未具备能力 |
| --- | --- | --- |
| FastAPI、Pydantic、psycopg 与 PostgreSQL 域仓储 | 原技术栈、typed port 和事务模式 | 本体专属仓储、生命周期与 API |
| Skill/MCP、Knowledge、Employee 的修订、摘要和发布 | 精确引用与独立领域责任的设计 | 可运营的业务对象/指标/映射定义 |
| `sales_diagnostic_skill.py` | 原 v1 保留并回归 | 销售规则仍在代码中，不能独立发布 |
| `sales_evaluation.py` | 原独立整数分单位基准保留 | 新口径、新绑定与通用错误校验 |
| `prepared_execution_*` | 原 Plan→Run→Task→Attempt、只读执行和证据链 | 本体版本进入批准摘要及 dispatch 校验 |
| `authority_configuration.py`、owner authorization | 既有可信身份、精确授权和撤销屏障 | 本体 owner/action 的显式注册 |
| Knowledge + Qdrant | 术语和制度说明检索 | 权威结构化规则读取不能靠向量检索 |
| 关系投影与内联结果页 | 复用视图和结果展开方式 | 可编辑、可发布的业务关系定义 |

历史交付中销售路径为合成数据；技术成功不代表真实经营诊断已成立。D8/D9、旧供应商及 UNKNOWN 记录不作为本体案例的隐式执行权限。

## 3. 推荐选项 B：独立语义域，现有执行链消费

| 选项 | 结果 | 判断 |
| --- | --- | --- |
| A：规则放在提示词或 Knowledge 文本 | 易接入，不能保证执行器用同一口径、无法强制校验 | 不满足任务 |
| B：独立语义域＋精确绑定＋现有 Skill 执行 | 可维护定义，保留现有授权和执行责任 | 推荐 |
| C：图数据库＋RDF/OWL推理＋新策略引擎 | 新依赖与治理复杂度增加，当前两期表格案例不足以证明必要性 | 递延 |

### 3.1 权威归属

- 业务语义域：本体身份、不可变修订、校验、测试、审核、发布与废弃记录。
- 规划域：用户选择、口径变更后的后继建议和批准计划；不发布本体。
- 执行域：精确运行绑定、dispatch 及 Attempt/Resource Use/Evidence；不修改本体。
- 原授权域：可信身份、会话、精确 grant、撤销和独立签发；语义域不能签发执行权。
- 企业系统：真实订单等业务事实；本阶段仅用固定合成快照。
- Kubernetes：原有控制面权威保持。
- 前端和关系图：只投影及发起操作，不自行宣布发布、授权或执行成功。

遵循已登记的 ARCH-018 PostgreSQL 域责任、ARCH-263 Skill、ARCH-264 Outcome 和 ARCH-266 Resource Use 边界；不重开已关闭的架构任务。

### 3.2 组件边界

在 `agent_console` 增加 `ontology_domain`、`ontology_repository`、`ontology_postgres`、`ontology_service`、`ontology_api`、`ontology_authorization`、`ontology_query` 和 `sales_ontology_executor`。文件名为实施候选，职责在本决策中固定。

沿用现有数据库、连接池、身份和页面框架；阶段0—2不引入 Cube、OpenMetadata、OPA、Neo4j、外部推理服务、新队列或调度器。不新增公网路由，不改 CRD/API group，不扩展企业 Tenant/SSO 架构。

## 4. 定义与存储合同

### 4.1 OntologyRevision v1

一个修订是有界、可独立发布的业务域包；内部对象使用稳定 code。修订完整绑定范围、前驱和内容摘要：

```text
scope(namespace, security_domain)
ontology_id / revision_id / predecessor_revision / content_digest
schema_version = business-ontology.v1
name / description / business_owner / data_owner / effective_from
objects[]: code, identity_fields, properties, descriptions
relations[]: code, from, to, key_mapping, cardinality, missing_reference_policy
metrics[]: code, input_object, expression, unit, grain, time_field,
           aggregation, allowed_dimensions, supported_filters, rule_codes
source_mappings[]: code, source_schema, source_reference, source_digest,
                   object_code, field_mapping, identity_scope, freshness_policy
constraints[]: code, typed_parameters, severity, applicable_objects
action_contracts[]: code, READ_ONLY, exact_skill_reference, operation,
                    executor_revision_digest, input/output_schema_digests
limitations[] / evidence_references[]
```

首期范围建议上限：单修订1MiB、32对象、256属性、64关系、32指标、128约束、32映射；一次运行仍受现有输入/输出/产物上限约束，取更严格者。边界是设计值，实施时须测试超限拒绝，不暗中放宽既有上限。

首期销售对象只有来源确有的销售记录、产品、区域、渠道、期间和币种。产品/区域/渠道成员可由快照生成只读维表；其身份仅在声明的数据集范围内有效，不冒充企业主数据。业务记录使用 `(source_id,rowId)`，防止跨数据源 rowId 碰撞。没有客户与订单主数据时不建立虚构关系。

金额统一使用明确的合成源两位小数合同；JPY样本仍服从此源合同，不宣称ISO币种精度适配已完成。拒绝NaN、无穷、超限值和隐式汇率换算。

### 4.2 首期表达能力

表达式为类型化、白名单 AST，仅支持字段、SUM、SUBTRACT、按维度分组及两期比较；过滤为已声明字段上的有限枚举/相等/集合/期间范围。禁止 eval、Python片段、任意SQL、动态导入、自定义脚本和循环推理。

支持净销售额、毛利额、两期变化及贡献；单位、统计粒度、币种分组、取消与退货规则显式化。毛利率及其他未被当前执行器和独立基准覆盖的计算不自动纳入。

关系首期支持声明的确定性键关联及基数校验。发现重复键、缺失必需引用或聚合扩张直接拒绝；不做模糊身份合并。模型补造或猜测对象身份被拒绝。

### 4.3 PostgreSQL 方案

同一既有数据库中新增 `business_ontology` schema：

- `definitions`：稳定身份、范围、预期版本与草稿/发布索引。
- `revisions`：不可变规范化JSONB、摘要、前驱、编制人。
- `lifecycle_facts`：不可变校验、测试、审核、发布、废弃事实。
- `dependency_refs`：修订与指标/映射/来源/Skill依赖的精确索引。
- `schema_migrations`：本域迁移版本和校验和。

Execution域另有本体绑定/检查证据的 typed repository；规划域保留其选择事实。JSONB方便定义演进，关系身份及依赖建立受约束索引，不能以JSON代替引用和范围校验。

所有唯一键包含范围；同身份同规范字节幂等，不同内容冲突。并发草稿/发布用预期版本CAS；发布与审核精确绑定revision+digest。禁止 UPDATE/DELETE 已发布修订及历史事实。迁移编号在实施前检查现有最高序号再分配，避免与并行P10的0043碰撞。

## 5. 生命周期、权限与接口

生命周期沿用既有资源精神：DRAFT → VALIDATED → TESTED → HUMAN_REVIEWED → PUBLISHED → DEPRECATED。编辑生成草稿后继修订，旧校验/测试/审核不继承；发布验证上述事实均指向同一digest。首期不提供物理删除。

新增 owner `BUSINESS_ONTOLOGY`，操作 `CREATE/LIST/READ/REVISE/VALIDATE/TEST/REVIEW/PUBLISH/DEPRECATE/USE`；精确资源前缀 `business-ontology:`。collection权限只能访问已授权范围内的目录元信息；精确内容和历史须 READ，运行须 USE。不会因获得LIST自动可见全部定义或外域数量。

复用现有可信上下文及同事务授权检查。不得由浏览器提供可信scope/actor。编制人与审核人分离；发布者须具备PUBLISH且有独立审核事实；研发自动化只能用明确标注的独立测试账户，不模拟业务人工接受。撤销与发布/准入在既有锁顺序下串行，避免嵌套连接死锁。

候选内部API（精确版本、服务端身份、写操作含request_key及expected_version）：

```text
POST /api/business-ontologies                        创建草稿
GET  /api/business-ontologies                        有界授权目录
GET  /api/business-ontologies/{id}/revisions/{rev}     精确修订
POST /api/business-ontologies/{id}/revisions          后继草稿
POST /api/business-ontologies/{id}/validate           结构/引用校验
POST /api/business-ontologies/{id}/test               固定样本验证
POST /api/business-ontologies/{id}/review             审核决定
POST /api/business-ontologies/{id}/publish            发布精确修订
POST /api/business-ontologies/{id}/deprecate          废弃未来使用
POST /api/business-ontologies/{id}/query-preflight    语义请求校验，不派发
```

GET、刷新、校验、发布和预检均不调用模型、不创建Run、不签发执行授权。

## 6. 本体如何进入批准与执行

新增版本化 `BusinessSemanticsBinding v1`，含精确 ontology、mapping、metric/rule/query、source snapshot、Skill/executor/schema版本和摘要；绑定摘要覆盖全部执行相关语义。它不是权限凭证。

1. 在执行方案批准前，准备本体绑定及确定性查询；展示口径、来源、合成限制、兼容性。
2. 生成新的、本体专属执行修订请求v2，明确后继来源；mapping_digest包含语义绑定摘要且排除尚未产生的Plan/Approval，避免摘要循环。批准文本/结构记录绑定承诺，不能在批准后偷偷附加。
3. 新 `execution-preparation.v2` 显式携带该绑定。旧v1类、序列化、摘要、Run ID算法输入和回放结果保持原样。只有新路径支持v2，新字段绝不混进旧v1。
4. Execution域原有调用链持久化精确绑定，创建新运行仍依赖原Plan批准、资源、独立执行权限和预算准入。
5. dispatch前从本体责任方读取精确版本，核验已发布、USE权限、来源/映射/执行器兼容、当前废弃/禁用情况及批准摘要。只读校验也不能被浏览器绕过。
6. 新销售本体执行器通过原Skill registry注册为独立executor/revision/configuration digest；消费结构化定义完成确定性计算。原sales v1 executor继续可用，不能静默升级。
7. 产物固定本体、映射、查询、数据和执行器版本，输出规则命中、排除记录、原始行证据和明确限制。Evidence与Outcome由原责任方记录。

本体发布新版本不改变进行中的绑定；废弃或撤销USE阻断后续未派发消费，已完成历史仍按原版本解释。重试新Attempt保留原精确语义；想换口径须新方案/批准/运行，不能把旧结果标为新口径成功。

本阶段不把 ONTOLOGY 直接塞入旧ResourceUse封闭kind。Execution-owned语义绑定及检查证据作为受控Skill使用的精确辅助证据关联；如果实施发现必须修改ResourceUse核心合同，另提差异，不自行扩大本决定。

## 7. 变更、兼容与回退

- 来源变更与本体变更分别建模；并行P10/D10不是本体变更授权。
- 来源、指标定义或关系改变必须使依赖的旧校验、审核和内容绑定标准失效，使用后继标准修订并重新确认；不自动降低验收标准。
- 已发布v1对象不迁移重写，不给旧运行回填“曾经使用本体”的证据。
- v2准备格式由显式功能开关和已知writer版本启用。旧二进制遇到v2或未知schema必须拒绝，不降级到v1忽略字段。
- 数据库迁移仅追加；部署前停相关writer、备份及检查校验和，旧writer不得接触不兼容新记录。
- 回退停止新的本体编写与v2准入，保留事实及可读新版本的服务；原v1兼容路径继续可用。不能通过降级二进制或删表回退。
- 不在共享研发库直接实验。阶段1—2先独立临时PG和独立前后端；安装到既有现场另核候选、备份、writer与兼容性。
- 不借用原供应商/D9的签名、本体发布权或执行权，不复活UNKNOWN，不释放预留，不创建第二账本或提高既有预算。

## 8. 验证与完成标准

阶段0：源码全量摘要与独立基线；相关基线测试有当前结果；并行变更清单；本设计和30项验收案例可评审。架构决定未接受前，状态为工程准备完成、架构门待决定。

阶段1：真实PostgreSQL上的草稿→校验→测试→独立审核→发布→重启读回；CAS、幂等、篡改、跨范围、撤销及未授权发布负向通过；真实浏览器可完成基础定义操作，逐页/状态提供参考与实际对照。发布本体不证明执行闭环。

阶段2：真实本地服务和PG的本体销售链路产生新的绑定、Run/Task/Attempt、Skill产物与独立评估；固定30项验收案例全部通过；同一源在两份批准口径下有可核验差异，不能只显示版本号变化；旧sales/supplier回归；不重复共享现场旧运行。固定数据的CNY销售1000→800、毛利变化-160继续作为原口径基准。

运行基准由人工确定的golden金额与独立分单位算法验证；评估器不调用生产编译器/执行器，也不复用其汇总结果作为期望值。技术通过与人工业务接受分开。

研发合成闭环通过不代表真实企业数据、因果解释、经营改善、生产多租户隔离或发布接受。所有skip和未测项目逐项列出，不能折算为PASS。

## 9. 待Human决定

请接受、修改或拒绝选项B，范围包括：

1. 新业务语义域在现有PG拥有本体定义与发布。
2. 新本体owner/action，沿用原身份/精确授权/独立审核。
3. 新版本化绑定、执行修订v2及准备v2，原v1语义和字节不变。
4. 独立新销售本体执行器及评估扩展，限合成、只读、独立研发验证。
5. 上述范围内阶段1—2实施和独立环境验证；发现额外架构差异再提交。

决定本身不调用模型、不安装共享迁移、不派发运行，不替代独立执行准入或最终发布决定。

## 10. Human接受记录

用户对本决策具体选项B明确答复：“批准选项B，继续阶段1—2”。本条记录接受第9节五项范围，实施按本计划进行；普通研发测试无需再次确认，额外架构差异、合并和发布门保留。
