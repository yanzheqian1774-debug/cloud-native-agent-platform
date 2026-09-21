# IMPL-324 执行契约集中差异决定包 v1

状态：PROPOSED，非服务端执行签发；2026-09-21。原323保持CLOSED。

## 已接受方向与本次唯一请求

本Session及附件已经授权：同案成本Plan复用、四阶段六任务、单Run、有限静态DAG、精确资源映射、不强制Workflow编辑器、Native只读优先、合成数据、真实产物和Human结果决定。以上不再请求批准。

本包请求接受下列D3具体责任及状态语义，作为324编码的架构依据。不是请求重新理解、重新生成计划或批准相同开发方向；也不代替后续服务端独立准入与页面Human决定。

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
| 已知FAILED/TIMED_OUT且已证实停止 | 所有必需依赖后裔SKIPPED | 继续已准入的只读分支 | 所有Task已终结后Run失败；可明确授权新Attempt重试，保留旧事实 |
| effect结果UNKNOWN或fence失联 | 不派发依赖任务 | 停止新增派发，已运行继续观测 | RECOVERY_REQUIRED，不自动重试，不作为terminal Business Outcome输入 |
| 用户取消请求已保存 | 不再新增派发，未派发Task记录取消原因 | 向已运行Attempt发有权取消请求 | CANCEL_REQUESTED不等于CANCELLED；无ack保持待确认/UNKNOWN |
| 全部运行Attempt停止已确认 | 未运行任务终结并保留原因 | 无新增派发 | 汇聚CANCELLED；部分成功产物仍保留 |
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

建议Human一次决定：接受D324-1/2/3，或列出修改项。未接受前不实施上述身份与生命周期扩展。
