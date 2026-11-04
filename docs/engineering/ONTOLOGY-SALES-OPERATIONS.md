# 业务本体销售闭环 — 运维与接入

适用范围：ONTOLOGY-SALES-01 选项B；仅隔离、合成、只读研发。代码包含本体owner和执行v2，未合并main、未生产部署。真实经营结论、独立视觉验收保持待定。

## 部署组件

沿用 FastAPI/Pydantic/psycopg/PostgreSQL、React、现有浏览器session/CSRF/精确grant、Planning、Native/Skill/ResourceUse/Evidence。新增 `business_ontology` schema（0044）和Execution-owned不可变语义绑定（0045）。没有引入图数据库、独立策略引擎或模型调用。

先部署支持0045的代码，使用owner migration安装；旧binary不能写入增加0045后的执行schema。禁止删除migration receipt、降版本或删除历史绑定“回退”。feature flag关闭只停止公开新本体入口，不代表可降级数据库。

`BUSINESS_ONTOLOGY_ENABLED=1` 启用既有workbench bootstrap中的本体API；`BUSINESS_ONTOLOGY_CREATION_TARGETS` 为有限精确目标数组，例如 `["business-ontology:sales-diagnosis:r1"]`；`BUSINESS_ONTOLOGY_PLAN_TARGETS` 为有限未来Plan目标，例如 `["plan:v2:ontology-sales-plan-r1"]`。这些只允许申请授权，不授予权限。仍需独立grant管理员批准。

运行服务需由现有bootstrap注入 Planning 和 PreparedNativeCoordinator。Native worker 显式组合 `compose(..., mode="ontology-sales-v1")`，使用真实当前授权reader和已有Native worker/ready driver。不能只开启页面就声称运行可用；默认旧组合继续旧执行器。

## 日常运营

1. 业务负责人确定指标与退货/取消口径；数据负责人固定Knowledge来源修订与摘要；技术维护来源映射和只读Skill合同。
2. `/ontology` 导入定义包，维护责任人与规则，创建草稿。所有code、关系键、类型、表达式使用有限白名单；不支持SQL、脚本或任意工具。
3. 依次定义校验、样本测试；另一名主体独立审核，再由有权限主体发布。每个动作均使用expected version、request key、exact revision/digest。
4. `/ontology/sales` 导入明确的执行方案包；核对后由用户确认Plan，保存v2准备。此来源为 `HUMAN_ONTOLOGY_SYNTHETIC`，没有伪造模型生成记录。
5. 单独核对执行、任务、Skill、资源使用、证据、评估权限，才提交开始。业务本体USE不替代EXECUTION START，Knowledge READ不替代本体USE。
6. 原Native/Skill链持久化Run/Task/Attempt/使用/产物；独立整数分单位评估器核对来源、金额、贡献、异常与结论边界。页面内联结果和来源行。
7. 规则变化必须后继修订、独立审核发布、重新确认Plan和标准。旧运行始终读取旧exact binding，禁止latest替换。废弃阻止新消费，授权历史读取仍可用。

## 接口与失败

- GET `/api/workbench/v1/business-ontologies`：有限目录，逐项READ过滤；不显示外域数量。
- GET `/{identity}/revisions/{revision}`：内容、摘要与不可变生命周期事实。
- POST `/{identity}/{create|revise|validate|test|review|publish|deprecate}`：typed OntologyCommand。
- GET `/{identity}/revisions/{revision}/sales-runs`：另需PLAN READ与EXECUTION READ的已准备候选。
- POST `/{identity}/execution-drafts`：显式v2草案校验和Planning proposal；语义预检合并在此操作，未单建query-preflight端点。
- 后续确认、prepared-executions start/read/evaluate复用现有API。

接口以上路径中的 `/{identity}` 均接在 `/api/workbench/v1/business-ontologies` 后。

典型拒绝：版本/CAS冲突、独立审核不足、摘要变化、来源/Skill合同变化、歧义指标、非法维度/过滤、混币种、精度/重复行错误、撤销权限、废弃修订。只接受SUM与SUBTRACT；维度关系仅快照内投影，不冒充跨系统主数据治理。

## 故障与恢复

观察到首例Native任务UNKNOWN后立即停止后续派发。查明调用前授权摘要序列化错误，Skill/产物/ResourceUse均0；修复后新增独立Plan、实例、授权和运行，保留原UNKNOWN及Kubernetes UID，未重置、重放或删除。后续两例各3任务成功。此开发案例不能推导所有UNKNOWN可自动恢复。

后续遇UNKNOWN：停止自动执行，读取持久记录与外部Task UID；先诊断是否已产生效果。不清状态、不重放、不伪造成功。需要恢复授权时遵循原执行owner规则。

## 验证与限制

验收矩阵见 `ONTOLOGY-SALES-ACCEPTANCE.csv`；原生证据、实际浏览器截图、重启前后owner状态、测试日志随阶段交付包提供。全库检查中的环境依赖skip逐项披露，不能作为真实外部服务证明。图表不是本页必需项，金额和贡献采用表格；没有真实经营数据/写回/汇率换算/OWL推理/通用图遍历。

与并行P08/P10共享bootstrap、授权、规划和执行代码；合并前比较其固定候选并处理冲突。本分支交付不代表共享main的可发布状态。
