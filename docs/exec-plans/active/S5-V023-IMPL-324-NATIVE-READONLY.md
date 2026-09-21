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
