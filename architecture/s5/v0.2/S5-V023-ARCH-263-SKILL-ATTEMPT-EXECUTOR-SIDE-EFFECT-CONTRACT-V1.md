# S5-V023-ARCH-263 — v0.2.3 Skill Attempt 执行器与副作用契约 v1

## 1. 决策记录

| 字段 | 值 |
| --- | --- |
| Session / Title | `S5-V023-ARCH-263` / Skill Attempt Executor and Side-Effect Contract |
| 权威分类 | `CLOSED / G2_ACCEPTED_WITH_CONSTRAINTS / ARCHITECTURE_AUTHORITY_ONLY` |
| 发布状态 | `REPOSITORY_PUBLICATION_CANDIDATE`; source Session `CLOSED` |
| Durable baseline | commit `3f4aa05f6641aefc15cf5873f1f6ab279f8d13b2`; tree `5ca583f3a239ed3f1d5cdd33d39db7e2d7fbf860`; CI `34032397080 / SUCCESS` |
| 实现授权 | `NO`; `IMPLEMENTATION_NOT_AUTHORIZED` |

本契约依赖 [ARCH-259 MCP endpoint/trust/credential authority](S5-V023-ARCH-259-MCP-ENDPOINT-TRUST-CREDENTIAL-AUTHORITY-V1.md)，
并复用 [Plan/Attempt](S5-V023-ARCH-208-WORKFLOW-CONTROL-PLAN-APPROVAL-INTERVENTION-PERSISTENCE-V1.md)、
[Evidence](S5-ARCH-010-PRODUCTION-EXECUTION-EVIDENCE-SHARED-READ-MODEL-BOUNDARY-V1.md)、
[Runtime](S5-ARCH-019-V023-EXECUTION-RUNTIME-AUTHORITY-V1.md) 与
[Knowledge/Capability](S5-ARCH-011-PRODUCT-INTENT-DYNAMIC-WORK-ROLE-KNOWLEDGE-CONSUMPTION-BOUNDARY-V1.md)
基础。它不把 Agent、Runtime、Capability 或 provider 合并。

## 2. 问题与 domain owner

现有 bounded Skill test invocation 不能证明 Attempt-bound、persist-before-effect、
restart-safe execution。Skill executor 是可替换的 governed Capability Provider
adapter。Platform Execution domain 拥有 Invocation identity、exact binding、
authorization/policy decision、state、Evidence links 与 recovery decision；provider
拥有 native execution/effect 与 native observation。

## 3. Identity 与 exact execution snapshot

`skill_invocation_id` 是 scope 内稳定 opaque identity，并精确绑定：Workflow Run、
Task Run、Attempt、approved Plan revision/digest、Digital Employee/Agent/Runtime
Instance、Skill Definition/Revision/operation/digest、binding snapshot、executor/provider
revision、authorization decision、side-effect class、bounded input digest 与 idempotency
claim。禁止 implicit latest、provider ID 代替 Platform identity 或 retry 复用 identity。

P1 每个 Attempt 至多一个 deterministic managed Skill slot。Retry 创建 successor
Attempt 和 successor Invocation；旧记录保持 immutable。

## 4. Lifecycle、事实与 side-effect 分类

```text
已请求(INVOCATION_REQUESTED)
  → 已记录发起(DISPATCH_RECORDED)
  → 已接受(INVOCATION_ACCEPTED) → 调用中(INVOCATION_RUNNING)
  → 调用成功 / 调用失败 / 已取消 / 调用结果未知(OUTCOME_UNKNOWN)
```

Typed append-only facts 与 PostgreSQL current projection 是平台权威。
`DISPATCH_RECORDED` 必须在外部调用前 durable，但不证明 provider 接受、运行或成功。
Timeout、disconnect 或 crash 发生在 dispatch 后且无权威终态时必须投影
`OUTCOME_UNKNOWN`。

| 分类 | P1 disposition |
| --- | --- |
| `READ_ONLY` | mandatory real executor path |
| `IDEMPOTENT_WRITE` | disabled；需要单独 Human gate |
| `NON_IDEMPOTENT_WRITE` | Post-P1；不授权 |

调用技术成功不等于 Attempt/Task/Workflow business success。Capability maturity 与
一次 execution state 是两套独立状态；统一事实映射由
[ARCH-266](S5-V023-ARCH-266-UNIFIED-ATTEMPT-RESOURCE-USE-MEASUREMENT-AUTHORITY-V1.md)
定义。

## 5. Authority boundaries

| 系统 | 权威边界 |
| --- | --- |
| PostgreSQL | Invocation/claim/snapshot identities、typed facts、current projection、CAS、Evidence links、recovery state |
| Provider | native acceptance、effect、result 与 observation；不能声明平台授权或业务成功 |
| Kubernetes | workload/Control Plane observed state；Pod phase 不等于 Skill 或 business outcome |
| Qdrant | derived Knowledge index；不拥有 Skill invocation、side effect 或 result |

## 6. Concurrency、CAS、idempotency 与 restart

Invocation identity、idempotency claim、exact snapshot 与 requested fact 在一个
PostgreSQL transaction 中持久化；`DISPATCH_RECORDED` 在调用边界前提交。相同 scoped
key + digest replay 返回原 Invocation/projection，不重复 dispatch；不同 digest 为
`IDEMPOTENCY_PAYLOAD_MISMATCH`。Fact ingestion 使用 source observation ID + digest；
conflicting terminal facts fail closed。CAS/high-water 保证 reducer snapshot 一致。

Restart 从 claims、facts 与 high-water 恢复并重新观察 provider/Kubernetes。对已记录
dispatch 但结果不可证的 Invocation 不 redispatch，而保持 `OUTCOME_UNKNOWN`；retry
必须由单独授权创建 successor Attempt。晚到 callback 只能更新原 Invocation。
Exactly-once external effect 不作承诺。

## 7. Authorization、Evidence 与 redaction

Authorization 先于 existence lookup/list/count、binding/executor selection、claim
disclosure、snapshot/Evidence join 与 provider call。拒绝产生零 provider call，不泄露
protected resource 是否存在。Evidence 只保存 exact identities/digests、typed fact、
timing、bounded/redacted input/output/error summary、source、limitations 与 authorization
reference；不得保存 secret、credential、raw prompt/request/response 或 private Human
content。Evidence 与 Invocation 分别授权，export/share 再授权。

## 8. Product/Technical projections 与中文术语

Product View 显示“技能是否已选择/调用、是否真实发起、结果是否已知、业务限制”；
Technical View 显示 exact Skill/binding/executor/Attempt、fact sequence、source、digest、
high-water、Evidence 与 conflicts。两者消费同一 backend invocation snapshot，不得
frontend 拼装或 synthetic fallback。

Skill Invocation=`技能调用`；Managed Slot=`托管技能槽位`；Dispatch Recorded=
`已记录发起`；Accepted=`已接受调用`；Running=`调用中`；Succeeded=`调用成功`；
Failed=`调用失败`；Outcome Unknown=`调用结果未知`；Read Only=`只读`。产品文案必须
说明“调用成功”是技术事实，不等于“业务问题已解决”。

## 9. Failure 与 recovery

必须拒绝 cross-scope、missing/changed approval、Skill/binding/executor digest mismatch、
unsupported side-effect class、second managed slot、stale CAS、conflicting replay、
authorization 后置、dispatch 冒充 accepted/success、blind retry 与 late callback
污染 successor。Pre-dispatch failure 可安全结束而无外部调用；post-dispatch ambiguity
保持 unknown；recovery 追加 observation/recovery fact，不改写历史。

## 10. P1 acceptance

真实 `READ_ONLY` executor 路径必须证明：exact Attempt/Plan/Skill/binding/executor
snapshot；one managed slot；authorization-before-dispatch 与 denial zero-call；durable
request/claim/dispatch ordering；accepted/running/terminal distinction；timeout/cancel/crash
unknown；same replay no redispatch；conflicting replay fail closed；successor retry；restart
readback；redaction；Product/Technical parity；invocation success 与 Business Outcome
分离。Mock/fixture-only 不满足。

## 11. Rejected/Post-P1、dependency 与 Human constraints

P1 拒绝 `IDEMPOTENT_WRITE`、`NON_IDEMPOTENT_WRITE`、多 managed Skill slot、implicit
latest、generic untyped history、provider-owned platform state、automatic unknown retry、
frontend authority、silent fallback、exactly-once 与 CRD/API-group change。Write enablement、
dynamic multi-Skill orchestration、compensation、general recovery、HA 与 certification
属于 Post-P1/单独 gate。

后续 implementation 依赖 ARCH-259 durable contract、typed Invocation domain、additive
PostgreSQL persistence、adapter、Resource Use integration、shared snapshots 与真实 E2E；
这里不分配 Session。Human constraints 固定 Platform/provider ownership、persist-before-
dispatch、unknown-no-redispatch、READ_ONLY mandatory、writes disabled、one managed slot、
shared projection 与 implementation authorization `NO`。

## 12. Provenance 与 supersession

Source provenance：`S5-V023-ARCHITECTURE-PUBLICATION-AUTHORITY-BUNDLE.md`，
`118730` bytes，`2696` lines，SHA-256
`8570e725c4a43df2d94b2cf59b87cedefd15b9362cba20c4835f495be3ad7420`。ARCH-263
Human Authority Capsule 优先于完整 proposal/review。Proposal 的旧 `OPEN_DECISIONS`、
`READY_FOR_HUMAN_G2_DECISION` 及 conditional `IDEMPOTENT_WRITE` 已被 supersede；当前
权威明确将其 disabled。未发现与其他 Capsule 或既有 accepted architecture 的实质冲突。
