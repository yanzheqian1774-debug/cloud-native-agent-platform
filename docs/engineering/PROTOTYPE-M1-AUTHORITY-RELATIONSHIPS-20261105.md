# 业务链权威关系与下一单元限定实现任务

2026-11-05，源码核对基线550d3e123535。原型R1/R1.1均为探索/待确认，不能把五步固定画布或BP02/W02混用当语义契约。原图仅提供视觉/交互语言，既有执行活动不冒充整个采购流程。

|对象|现有权威与准确关系|当前不能据此宣称|
|---|---|---|
|业务问题|business_problem_domain.BusinessProblemRevision：稳定problem_id、revision_id/digest、title/description、owner、前驱修订；独立问题生命周期|没有显式业务流程定义、业务流程实例、当前活动/上下游关联字段；描述文字不能充当正式流程状态|
|目标/成功标准|SuccessCriterionRevision、SuccessCriteriaSetRevision；ProblemTarget绑定准确问题与标准集、逐条criterion_revision_ids及expected_problem_version|技术判定不等于业务审核；不能为自动办理静默改目标、来源或标准|
|问题与计划关联|PlanProblemBinding把plan_id/version/digest与problem/criteria精确修订相连；PlanSemantics.target含同样引用|Plan绑定业务问题，不代表已存在独立业务事项/流程实例owner|
|活动要求与任务计划|FlexiblePlanSemantics有title/effect/business_rules/boundaries、stages、tasks、requirements；task有目标职责、输入输出、依赖、标准和资源requirement_id|当前活动要求是已有确认Plan的投影，不是新实现的原始需求理解。没有独立ActivityRequirement持久对象；stages不是整个业务流程|
|长期员工定义|EmployeeRevision.role/responsibilities/members，准确版本/digest，独立验证发布；定义不等于实例，不必每问题新建定义|当前自动选择整组现有员工不是任务级动态装配，也不是为每个新问题自动生成能力|
|员工实例及工作分配|CreateDigitalEmployeeInstance绑定精确定义；Assignment绑定实例、业务角色、有效期；workspaceReference/policyReferences为既有不透明声明|员工实例不是业务流程实例；workspaceReference不能未经契约核定变成流程权威或状态|
|本次执行准备/逐步资源绑定|ExecutionPreparation.v1：Plan准确版本、approval_id、root_instance/assignment、source_snapshot；TaskParticipation按task_id绑定instance/assignment/definition、Skill操作与I/O摘要、resources[]、profile/executor/runtime|已有逐步绑定字段可复用；当前readonly_instance_assembly按整组4资源装配，资源选择还没有按活动步骤细分。不能画共享资源连线冒充逐步绑定|
|运行轨迹|PreparedExecutionStore/Native coordinator/TaskRun/Attempt/ResourceUse/Artifact/Outcome记录真实运行及准确父链；Plan只是声明，Run才是运行事实|工作流/Run的执行状态不能当成业务流程关口状态；技术SUCCEEDED/SAT不等于真实业务解决|
|重规划/恢复|ProposalRevision有predecessor_digest；确认Plan版本不可改写；来源/资源后继保留旧Plan/产物；UNKNOWN先核查；本批选择提交丢失已GET恢复|尚无完整受影响节点局部重规划/所有业务流程上下文恢复验收，不能把浏览器模拟当真实对账|

## 两个明确断点

1. 原始问题→办理上下文/当前活动要求：现有问题/标准/草稿辅助/规划owner可复用，但自动上下文识别、活动范围衔接与必要澄清尚未串起。业务流程内事项需要已有实例/当前活动/上下游和成果；目前未找到正式流程实例关联owner，因此先核定可复用接口，不能新造流程。无预定义流程的开放诊断允许直接形成活动要求与临时计划，不虚构采购流程。
2. 活动要求→逐步可执行绑定：FlexiblePlanSemantics与TaskParticipation已有任务I/O/依赖/资源精确引用；但协调器目前按现有员工整组装配。Skill owner的skill_invocation_postgres.py明确校验调用Skill必须是该员工精确members中的SKILL，绑定摘要也含employeeDefinitionId/revision。readonly_instance_assembly另有整组精确匹配/4项组合限制。不能删除这些检查来通过动态装配。

## 兼容路径与门槛

- 首选G1候选：沿用已有批准员工承担责任，在其已批准成员范围内按本次活动/步骤选择Skill操作与资源，复用TaskParticipation/ResourceBinding/源快照/Plan版本及准入；不创建长期员工、不修改其定义，不把Plan当业务流程。需先验证多步I/O/版本/权限/数据范围/受影响节点及重规划读回。
- 超出现有员工成员的动态Skill调用会被当前Skill owner拒绝。若首版必须支持该范围，涉及现有精确绑定语义的具体契约决定；届时形成方案并集中决策，不以现有方向批准推定可绕过owner。
- 业务流程上下文缺少正式权威关系时，不用任意字符串新增隐含父子关系。先接入已存在且可核实的上下文；开放分析问题单列。需要新持久化/生命周期/owner关系时按G2处理，不先建整套抽象。

## 下一单元工作清单

1. 核对已有问题/草稿理解/标准/规划入口，建立“流程内事项／开放分析”上下文能力与缺口映射，保留原目标和标准。
2. 先用开放分析的现有批准上下文打通问题→活动要求→初步任务计划；缺少事实或边界时至多一轮集中业务澄清，不能让用户填资源/角色/技术ID。
3. 覆盖、规划、资源发现允许迭代；每步记录I/O、具体资源、数据范围、权限、版本和选择依据。试探读取也须走受控执行/证据。
4. 在批准成员范围内实现本次逐步绑定与验证，再接现有实例和Run；计划/运行状态分开，业务关口按真实制度判定。
5. 测试不同活动分解、兼容/不兼容绑定、撤权、局部失败与已知回执恢复；确认前不照搬原型固定read/validate/analyze/evaluate/report五步。

## 对日期窗口的影响

11/10候选、11/12稳定试用仍为待核算的条件目标，不是承诺。新增关键路径是业务链语义/上下文关系与逐步装配契约；11/06检查点需核定兼容范围和已确认页面。当前已有活动内自动选择不抵扣这些项。如必须新增流程owner或越过员工成员绑定，先决定再重排，不为日期降低验收或静默顺延。
