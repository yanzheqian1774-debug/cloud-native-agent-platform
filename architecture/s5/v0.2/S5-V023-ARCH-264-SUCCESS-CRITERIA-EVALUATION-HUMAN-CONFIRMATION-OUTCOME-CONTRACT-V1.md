# S5-V023-ARCH-264 — v0.2.3 成功标准评估、人工确认与结果契约 v1

## 1. 决策记录

| 字段 | 值 |
| --- | --- |
| Session / Title | `S5-V023-ARCH-264` / Success Criteria Evaluation, Human Confirmation and Outcome Contract |
| 权威分类 | `CLOSED / G2_ACCEPTED_WITH_CONSTRAINTS / ARCHITECTURE_AUTHORITY_ONLY` |
| 发布状态 | `REPOSITORY_PUBLICATION_CANDIDATE`; source Session `CLOSED` |
| Durable baseline | commit `3f4aa05f6641aefc15cf5873f1f6ab279f8d13b2`; tree `5ca583f3a239ed3f1d5cdd33d39db7e2d7fbf860`; CI `34032397080 / SUCCESS` |
| 实现授权 | `NO`; `IMPLEMENTATION_NOT_AUTHORIZED` |

本契约是 [ARCH-258](S5-V023-ARCH-258-BUSINESS-PROBLEM-SUCCESS-CRITERIA-AUTHORITY-V1.md)
的窄化增量，并依赖
[ARCH-266 actual Resource Use snapshot](S5-V023-ARCH-266-UNIFIED-ATTEMPT-RESOURCE-USE-MEASUREMENT-AUTHORITY-V1.md)。
它复用 [Plan/Attempt](S5-V023-ARCH-208-WORKFLOW-CONTROL-PLAN-APPROVAL-INTERVENTION-PERSISTENCE-V1.md)、
[Evidence](S5-ARCH-010-PRODUCTION-EXECUTION-EVIDENCE-SHARED-READ-MODEL-BOUNDARY-V1.md)、
[Runtime](S5-ARCH-019-V023-EXECUTION-RUNTIME-AUTHORITY-V1.md) 与
[Knowledge](S5-ARCH-011-PRODUCT-INTENT-DYNAMIC-WORK-ROLE-KNOWLEDGE-CONSUMPTION-BOUNDARY-V1.md)
基础，不重开 ARCH-258。

## 2. 问题、owner 与 aggregation root

技术终态、模型判断、Evidence presence 或 frontend 颜色都不能单独证明业务问题已
解决。Business Outcome 的唯一业务 aggregation root 是 exact terminal Workflow Run。
Success Criteria Evaluation domain 拥有 authoritative Evaluation；Human governance
domain 拥有 Human Confirmation；Product Outcome domain 依据同一 immutable snapshot
聚合 Business Outcome。`SuccessCriteriaEvaluationService` 是权威 evaluator；model
output 仅 advisory。

## 3. Identity、binding、Lifecycle 与 state/fact model

Evaluation 固定 `evaluation_id`、exact Problem/criterion/set/Plan revisions+digests、
terminal Workflow Run、evaluator kind/version、Evidence snapshot IDs/digests/high-water、
ResourceUseSnapshot ID/digest/high-water、result、limitations 与 canonical digest。
Evaluation result immutable。

`PENDING`, `RUNNING`, `FAILED` 属于 Evaluation job，不属于 Evaluation result。Result
固定为 `SATISFIED`, `NOT_SATISFIED`, `UNKNOWN`, `NOT_MEASURABLE`, `INVALIDATED`。
Invalidation 是 append-only fact + effective projection + optional successor，绝不修改
原 result/digest/Evidence snapshot。

Human Confirmation 是 exact-targeted、separately authorized、append-only fact，绑定
Evaluation/Evaluation Set/Outcome、reviewed Evidence snapshot、actor、authority basis、
decision、reason、time、digest 与 optional superseded confirmation。Disagreement 阻止
confirmed success。

```text
terminal Run → UNKNOWN Evaluation → UNDETERMINED Outcome
→ append Human Confirmation → successor Evaluation → successor Outcome
```

Outcome immutable；correction、新 Evidence 或 confirmation 创建 successor。Business
resolution 只有 `CONFIRMED_SOLVED`, `NOT_SOLVED`, `UNDETERMINED`。
`CONFIRM_PROBLEM_SOLVED` 是 confirmed success 的强制 Human gate。
`RECOVERY_REQUIRED` 禁止 authoritative Business Outcome creation。包含 `UNKNOWN`,
`NOT_MEASURABLE` 或 `INVALIDATED` 的 Outcome 只能为 `UNDETERMINED`。

Technical Outcome 描述 execution terminal facts；Business Outcome 描述业务 resolution。
Capability maturity 与 execution status 另行分离；二者都不能代替 Evaluation。

## 4. Authority boundaries

| 系统 | 权威边界 |
| --- | --- |
| PostgreSQL | Evaluation jobs/results、invalidation/confirmation facts、Outcome/successor、exact links、CAS/idempotency/snapshots |
| Provider/model | 原生 observations 或 advisory assessment；不能创建 authoritative Evaluation/Human fact/business success |
| Kubernetes | Control Plane/workload observed state；Pod/CRD terminal state 不等于 Business Outcome |
| Qdrant | derived Knowledge index；SQL 中 exact Knowledge/citation/Evidence snapshot 才可参与评估 |

## 5. Evidence sufficiency、measurement 与 aggregation

每种 criterion revision 声明 required Evidence kinds、freshness、measurement rule、
evaluator version 与 applicability。Evaluator 只读取授权且 exact-bound 的 immutable
Evidence/ResourceUse snapshots。Missing、stale、conflicting、unauthorized 或不足的
Evidence 产生 `UNKNOWN`/`INVALIDATED`/limitation，而非 success。

`NOT_MEASURABLE` 是诚实状态；`NOT_COLLECTED` 与 `NOT_MEASURABLE` 不同。未测量、
未采集或无 authoritative provider source 的值不得填零。`ESTIMATED` 不得冒充 measured
或 billing authority。OutcomeSnapshot 必须引用 exact ResourceUseSnapshot；缺失/冲突
时可诚实创建 `UNDETERMINED`，但不能 `CONFIRMED_SOLVED` 或满足 P1 complete。

## 6. Concurrency、CAS、idempotency 与 restart

Evaluation job claim、terminal snapshot、invalidation、confirmation 和 Outcome creation
使用 scoped idempotency key + canonical digest 与 expected version/CAS。同 key/同 digest
返回原结果；不同 digest/stale version fail closed。每个 exact target/evaluator/snapshot
组合只有一个 authoritative result；并发 successor 或 confirmation 只有一个有效链头。

Restart 从 PostgreSQL jobs、immutable results/facts、claims、high-water 与 successor
links 恢复。不能从 UI/cache/model 重建。Terminal Run 或 Resource Use 有 ambiguity/
`RECOVERY_REQUIRED` 时停止 authoritative aggregation，等待 re-observation 或 Human-
authorized successor；不得篡改旧结果。

## 7. Authorization、Evidence 与 redaction

Authorization 先于 target existence、lookup/list/count、Evidence/Resource Use join、
evaluation、confirmation、snapshot assembly、disclosure/export。Evaluation authority、
Human confirmation authority 与每条 Evidence access 分别验证；拒绝不泄露 existence，
不产生 model/provider call。

Evidence/Outcome 保存 exact identities/digests、typed result、source/evaluator、actor/
authority basis、reason、timestamps、confidence/limitations 与 authorized references；
不得保存 secret、credential、raw prompt/provider payload、private Human message。Model
explanation 必须 bounded/redacted 且永远标为 advisory。

## 8. Product/Technical projections 与中文术语

Product 与 Technical View 消费同一 backend-issued `OutcomeSnapshot`。Product 显示
“成功标准、证据是否充分、人工确认/异议、业务结论、限制与后续工作”；Technical
显示 exact IDs/digests、job/result、evaluator version、Evidence/ResourceUse high-water、
confirmation chain、CAS 与 conflicts。Frontend 不创建或提升结果。

Evaluation=`评估`；Evaluation Job=`评估任务`；Human Confirmation=`人工确认`；Human
Disagreement=`人工异议`；Business Outcome=`业务结果`；Technical Outcome=`技术结果`；
Confirmed Solved=`已确认解决`；Not Solved=`未解决`；Undetermined=`尚无法确定`；
Not Measurable=`不可度量`。技术调用成功不等于业务目标达成。

## 9. Failure/recovery 与 P1 acceptance

拒绝 nonterminal root、Task/Attempt 代替 Business Outcome root、model-only success、
unknown-as-success、missing confirmation、changed Plan/problem/criteria digest、stale或
unauthorized Evidence、cross-scope、conflicting replay、frontend-generated Evaluation、
in-place mutation、旧 invalidated/superseded result 参与当前聚合，以及缺失 measurement
填零。Recovery 追加 invalidation/successor，不重写历史。

P1 真实验收必须证明：terminal Workflow Run gate；exact ARCH-258 bindings；typed
Evaluation job/result separation；deterministic evaluator；Evidence sufficiency；Human-
evaluated unknown→confirmation→successor chain；disagreement；mandatory
`CONFIRM_PROBLEM_SOLVED`；three-state business resolution；ResourceUseSnapshot linkage；
unknown/not-measurable honesty；restart/readback；CAS/replay；authorization/redaction；
shared OutcomeSnapshot parity。Mock/fixture-only 不满足。

## 10. Rejected/Post-P1、dependency 与 Human constraints

拒绝 automatic/model-owned scoring authority、frontend-owned evaluation、execution
success=business success、universal Outcome 混合技术与业务、in-place mutation、implicit
latest、synthetic Evidence、missing=zero、OpenClaw fallback、public CRD/API-group change
与 exactly-once claim。Learned/weighted scoring、portfolio aggregation、multi-level approval、
legal hold、general recovery、HA 与 certification 属于 Post-P1。

实现依赖 ARCH-258 durable foundation、terminal execution/Evidence、ARCH-266 actual-use
snapshot、typed Evaluation/Human/Outcome contract、additive PostgreSQL persistence、service、
shared API/views 与真实 acceptance；不分配 Session。Human constraints 固定 terminal Run
root、job/result separation、service authority、append-only invalidation/confirmation、
mandatory confirmation、three-state business resolution 与 implementation authorization `NO`。

## 11. Provenance 与 supersession

Source provenance：`S5-V023-ARCHITECTURE-PUBLICATION-AUTHORITY-BUNDLE.md`，
`118730` bytes，`2696` lines，SHA-256
`8570e725c4a43df2d94b2cf59b87cedefd15b9362cba20c4835f495be3ad7420`。ARCH-264
Human Authority Capsule 优先于所附完整 proposal/review。Proposal 中十二项
`OPEN_DECISIONS`、旧 `READY_FOR_HUMAN_G2_DECISION`、将 `PENDING` 混入 result 的可能
解释，以及对 root/confirmation/recovery 的未决选择均已被 Capsule supersede。ARCH-264
只窄化 ARCH-258，不冲突或重写它；未发现其他实质冲突。
