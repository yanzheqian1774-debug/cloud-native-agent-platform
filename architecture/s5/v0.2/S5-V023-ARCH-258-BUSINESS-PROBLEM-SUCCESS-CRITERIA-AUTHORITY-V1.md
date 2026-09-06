# S5-V023-ARCH-258 — v0.2.3 业务问题与成功标准权威 v1

## 1. 决策记录

| 字段 | 值 |
| --- | --- |
| Session / Title | `S5-V023-ARCH-258` / Business Problem and Success Criteria Authority |
| 权威分类 | `HUMAN_ACCEPTED_WITH_CONSTRAINTS / ARCHITECTURE_AUTHORITY_ONLY` |
| 发布状态 | `REPOSITORY_PUBLICATION_CANDIDATE`; source Session `CLOSED` |
| Durable baseline | commit `3f4aa05f6641aefc15cf5873f1f6ab279f8d13b2`; tree `5ca583f3a239ed3f1d5cdd33d39db7e2d7fbf860`; CI `34032397080 / SUCCESS` |
| 实现授权 | `NO`; 后续实现、migration、API、frontend、部署与验收均需单独 Human 授权 |

本记录发布 Human-accepted 架构权威，不声明实现完成、P1 完成、Contract
freeze、Preview、release、production readiness 或 certification。它专门定义业务
问题与成功标准，不取代 [Plan/Execution foundations](S5-V023-ARCH-208-WORKFLOW-CONTROL-PLAN-APPROVAL-INTERVENTION-PERSISTENCE-V1.md)、
[Evidence foundation](S5-ARCH-010-PRODUCTION-EXECUTION-EVIDENCE-SHARED-READ-MODEL-BOUNDARY-V1.md)、
[Runtime authority](S5-ARCH-019-V023-EXECUTION-RUNTIME-AUTHORITY-V1.md) 或
[Knowledge consumption boundary](S5-ARCH-011-PRODUCT-INTENT-DYNAMIC-WORK-ROLE-KNOWLEDGE-CONSUMPTION-BOUNDARY-V1.md)。

## 2. 问题与已接受的 domain owner

当前基础有 Plan、Run、Task Run、Attempt、Evidence 与 Outcome，却没有可重启
恢复的第一类 Business Problem 或 typed Success Criteria authority。继续以会话、
字符串列表或 frontend 状态代替，会使批准、执行与业务结果无法绑定同一精确意图。

Product domain 是 Business Problem、Success Criterion 与 Success Criteria Set 的
owner；PostgreSQL 是这些 durable Product facts 的 authoritative writer。会话只提供
provenance/context，不能成为身份或事实权威。

## 3. 身份、精确绑定与事实模型

- `business_problem_id` 是 scope 内稳定、不透明且不可复用的身份；语义内容位于
  immutable `BusinessProblemRevision`，由 revision 与 canonical digest 标识。
- `success_criterion_id` 稳定；criterion revision 固定 type、target、unit/category、
  measurement rule、Evidence requirements、evaluator version 与 applicability。
- `SuccessCriteriaSetRevision` 是独立 immutable aggregate，固定有序 membership、
  每个 exact criterion revision 及整个 set digest；不得以临时数组替代。
- Approved Plan 必须绑定 exact Problem revision/digest 与 Criteria Set
  revision/digest；禁止 implicit `latest`。Run 通过 exact approved Plan 继承绑定。
- Evidence、Evaluation、Human Confirmation 与 Outcome 保持各自身份；引用使用
  exact ID/digest，不把关系只藏在任意 JSON 中。

## 4. 生命周期、状态与业务/技术分离

```text
业务问题：草稿(DRAFT) → 生效(ACTIVE) → 处理中(IN_PROGRESS)
                         → 已解决(RESOLVED) → 已关闭(CLOSED)
                         → 已重开(REOPENED) → 处理中

标准修订：草稿(DRAFT) → 生效(ACTIVE) → 已退役(RETIRED) → successor
```

生命周期变化追加 fact 并受 CAS 保护；语义修订创建 successor，不能改写已批准
revision。被引用对象不得 hard-delete，只能 close、retire 或 non-sensitive
tombstone，并保留 immutable history。

Evaluation result vocabulary 固定为 `SATISFIED`, `NOT_SATISFIED`, `UNKNOWN`,
`NOT_MEASURABLE`, `INVALIDATED`。`NOT_MEASURABLE` 同时是 declared criterion
type 与诚实的 evaluation result。未测量、缺失或未授权数据绝不填零。

Technical Outcome 描述 Attempt/Task/Run 的执行事实；Business Outcome 描述业务
问题是否解决。技术成功不推出业务成功，Capability maturity 也不等于某次
execution status。完整评估与业务聚合由
[ARCH-264](S5-V023-ARCH-264-SUCCESS-CRITERIA-EVALUATION-HUMAN-CONFIRMATION-OUTCOME-CONTRACT-V1.md)
窄化定义。

## 5. Authority boundaries

| 系统 | 权威边界 |
| --- | --- |
| PostgreSQL | Problem/criterion/set identity、immutable revisions、Plan binding、lifecycle facts、Evaluation/Human Confirmation/Outcome links、CAS/idempotency |
| Provider | provider-native effect 与原生 observation；不决定业务问题或成功标准 |
| Kubernetes | public Control Plane resources 与实际 workload observed state；不拥有业务结果 |
| Qdrant | derived Knowledge vector index；SQL 保存 Knowledge/snapshot identity，Qdrant 不拥有 Problem、criterion 或 Evidence |

## 6. 并发、CAS、幂等与重启

每个 mutable projection 使用正整数 `aggregate_version`；写入携带 expected version，
零行更新返回 stable stale/conflict，禁止静默重试到新版本。创建、修订、lifecycle、
Plan binding、Evaluation 与 Human action 使用 scoped idempotency key + canonical
payload digest；同 key/同 digest 返回原结果，不同 digest fail closed。

PostgreSQL commit 后才可声明 durable acceptance。重启从 immutable revisions、
facts、claims 与 links 重建 projection；不得从进程缓存、frontend 或 provider
推测 Problem、criterion、approval、measurement、Human actor 或 business success。

## 7. Authorization、Evidence 与 redaction

Authorization 必须先于 lookup、existence disclosure、list/count、join、Evidence
dereference、snapshot、export 与任何 mutation。拒绝不得泄露对象存在性，并产生零
下游调用。Problem/criterion 与每条 Evidence reference 分别授权。

Evidence 是 immutable、schema-versioned、append-only fact；更正通过 superseding
Evidence。Human Confirmation 是另一个 exact-targeted、separately authorized、
append-only fact，不能改写 Evaluation、Evidence 或 Outcome。持久化与日志仅保留
bounded category、identity、digest、actor/authority basis、reason、timestamp、
limitations 与已授权 reference；不得保存 secret、credential、raw prompt、private
message 或 provider payload。

## 8. Product 与 Technical projections

Product View 以自然中文展示“业务问题、成功标准、度量规则、证据充分性、业务
结论、限制与后续工作”；Technical View 展示 exact IDs/revisions/digests、lineage、
evaluator version、Evidence references、CAS/high-water 与 conflict。两者消费同一
backend-issued snapshot，不拥有事实，也不得 synthetic fallback。

术语绑定：Business Problem=`业务问题`；Success Criterion=`成功标准`；Success
Criteria Set=`成功标准集`；Evaluation=`评估`；Human Confirmation=`人工确认`；
Business Outcome=`业务结果`；Technical Outcome=`技术结果`；Not Measurable=
`不可度量`；Unknown=`未知`；Invalidated=`已失效`。

## 9. Failure 与 recovery

拒绝 cross-scope reference、digest mismatch、implicit latest、stale CAS、conflicting
replay、未授权 Evidence、nonterminal target、伪造 measurement/Human actor，以及把
technical success 投影为 business success。事务失败必须完整 rollback。缺失、过期、
冲突或不可恢复的来源产生 `UNKNOWN`/`INVALIDATED`/`RECOVERY_REQUIRED` 或明确
limitation；永不伪造成功。恢复创建 successor fact/revision/Run，而非改写历史。

## 10. P1 acceptance

P1 必须以真实 PostgreSQL 和真实服务证明：稳定 scoped identity；immutable
Problem/criterion/set revisions 与 digests；ordered set membership；exact Plan approval
binding；terminal Run 到 evaluation/outcome 链；Human confirmation；close/reopen 与
successor lineage；CAS/replay conflict；restart/readback；authorization non-disclosure；
Evidence redaction；Product/Technical projection parity；未测量值不填零。Mock、fixture、
API-only、frontend-only 或 architecture-only 不构成 capability acceptance。

## 11. Rejected、Post-P1 与 implementation dependency

P1 拒绝 process-local authority、generic untyped table、in-place mutation、implicit
latest、model-owned success、frontend evaluation、hard delete、synthetic Evidence、
public CRD/API-group change 与 exactly-once external-effect claim。Portfolio scoring、
learned evaluator、multi-level approval、legal hold、generalized recovery、HA/multi-region
与 certification 属于 Post-P1。

后续实现依赖现有 Plan/Attempt/Evidence/Runtime/Knowledge contracts，并应先完成
typed domain contract、additive PostgreSQL persistence、service、shared snapshot、
Chinese-first surfaces 与独立 acceptance；顺序不分配 Session，也不授权修改。

## 12. Human constraints、provenance 与 supersession

Human constraints：保持 distinct Criteria Set aggregate；exact Plan binding；五态
Evaluation vocabulary；append-only Human Confirmation；referenced-object deletion
protection；复用现有 CAS/idempotency/auth-before-disclosure/restart foundations。

Source provenance：`S5-V023-ARCHITECTURE-PUBLICATION-AUTHORITY-BUNDLE.md`，
`118730` bytes，`2696` lines，SHA-256
`8570e725c4a43df2d94b2cf59b87cedefd15b9362cba20c4835f495be3ad7420`；其中
ARCH-258 Human Authority Capsule 优先于所附完整 proposal/review。Proposal 中旧
baseline、`READY_FOR_HUMAN_G2_DECISION`、`PENDING` evaluation workflow 与任何仍
标为 open/proposed 的选项均已被 Capsule 和 [ARCH-264](S5-V023-ARCH-264-SUCCESS-CRITERIA-EVALUATION-HUMAN-CONFIRMATION-OUTCOME-CONTRACT-V1.md)
收敛；它们只保留为 provenance，不是并列权威。未发现与既有 accepted architecture
的实质冲突。
