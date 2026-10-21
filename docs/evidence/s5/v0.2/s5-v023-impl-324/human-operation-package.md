# 324 集中人工操作包（资源与执行修订前置）

状态：待人工步骤。三条实际申请已由独立审批身份只读预检，均 HTTP 200 / PENDING；未签发、未发布、未确认计划、未启动 Native。

这是原用户要求的正式职责分离，不是再次申请 D324-1/2/3。资源 owner 要求 Human 审核，计划 owner 要求 Human 确认，独立准入禁止自批。

## 1. 独立审批人

打开以下入口，以 `human:demo323-approver` 登录。若当前是 requester，请先正常退出再登录。依次点击“检查授权申请”，核对下表与附带 JSON 的精确 owner/action/resource，再由本人决定是否“批准精确权限”。每条分别保留正式决定。

- [四项资源的精确读取与审核发布（8项）](https://127.0.0.1:19436/authorization-admin?request=grant-request-048bc8a3051e77383a1ef9fd11010844)：`grant-request-048bc8a3051e77383a1ef9fd11010844`
- [精确 Employee 的读取、校验、批准、发布及 Agent 读取（5项）](https://127.0.0.1:19436/authorization-admin?request=grant-request-b2447ead173fe891b7df923fed4551e5)：`grant-request-b2447ead173fe891b7df923fed4551e5`
- [原 Plan 的读取、窄后继准备与确认，以及原 Problem/Criteria 读取（6项）](https://127.0.0.1:19436/authorization-admin?request=grant-request-366a7309c01ced50e54ac4b967b1c9f4)：`grant-request-366a7309c01ced50e54ac4b967b1c9f4`

精确范围见 [已登记申请](initial-admission-requests.json)。这些权限不包含 EXECUTION START 或 Skill INVOKE，不会直接启动任务。页面默认决定有效期为操作时起一小时，但凭据自身到期后权限不可继续使用；本次既有凭据在 **2026-09-21 21:33:04 Asia/Shanghai** 到期，不延长或复用 323 连续性例外。

## 2. 资源审核与发布

切换为 `human:demo323-requester`，打开 [四项资源审核页](https://127.0.0.1:19436/work?problem=59a1d736-96d5-5060-8ae3-293d82b4b74b&resource=skill%7Cskill-definition%3A451512ee-fedd-47fe-a470-3cc32fccf0b9%7Cskill-revision%3A6c45c0e3-4d7e-4bd4-81e0-c66cf8d43883&resource=runtime%7Cruntime-profile%3A58de00f7-00b8-4536-8660-b6dfafd06ea0%7Cruntime-profile-revision%3Af0065dba-6b71-470d-aa23-cc94cd53f5d6&resource=knowledge%7Cknowledge%3Ac588c392-017b-495b-9580-3f06f8d358fd%7Cknowledge-revision%3Af11197ab-6e23-4528-95f1-0f1dfe0e046b&resource=agent%7Cagent-definition%3Ac2b74a7b-6af4-4efb-8afb-46a6ed7e2eb2%7Cagent-revision%3A51a65c3f-f5a4-4d36-a88d-77834251b5da)，刷新正式状态。展开 Skill、运行配置、合成资料和 Agent，核对精确修订、摘要、输入输出契约、无外部网络/真实账单与隔离只读边界。填写本人审核依据、勾选后审核发布。四项分别记账；部分失败保留，不重复已完成项。不要重复申请已有权限。

随后打开 [Employee 精确修订](https://127.0.0.1:19436/digital-employees?employeeDefinitionId=employee-definition%3A0486f684-a417-494d-847a-401727158ca4&employeeDefinitionRevisionId=employee-revision%3A7c6e26e7-3f20-4685-8bef-1816682af5cf&detail=1)，执行现有页面的校验、本人批准、发布。本次 Employee 绑定当前 Skill 后继修订，旧草稿保留；技术资源配置不代表已经执行。

## 3. 继续同一任务

上述操作完成后，代理读回正式记录，正常创建精确实例/Assignment 绑定，调用已有无模型窄后继入口，展示原 Plan v2 与实际下一版本的差异，请原主体确认。之后由实际准备摘要形成精确执行准入申请，再由独立审批人决定。不能预造未来 Plan/Approval/候选 ID，故这部分必须顺序生成，仍属于本操作流程及同一 324 任务。

准入通过后继续 Native、产物、标准评价、Human 结果决定及刷新/重启 PostgreSQL 读回。原 Criteria 是 Human 评价的规划标准，合成执行不能证明真实业务问题解决；允许正式确认限制或记录异议，不自动关闭 Problem。

## 保护及限制

323 CLOSED，Plan v2、旧 Approval、七 UNKNOWN、USD 4.816896 预留及结算保留。原案例目前无 Run/Task/Attempt/实际产物/评价/Human 结果决定；受控六任务测试使用真实 PostgreSQL 和 Skill owner，但 Kubernetes 为替身，不当作实际执行验收。未 Ready、未合并、未生产部署、未关闭 324。
