# S5-V023-ARCH-266 — v0.2.3 统一 Attempt 资源使用与度量权威 v1

## 1. 决策记录

| 字段 | 值 |
| --- | --- |
| Session / Title | `S5-V023-ARCH-266` / Unified Attempt Resource Use and Measurement Authority |
| 权威分类 | `CLOSED / G2_ACCEPTED_WITH_CONSTRAINTS / ARCHITECTURE_AUTHORITY_ONLY` |
| 发布状态 | `REPOSITORY_PUBLICATION_CANDIDATE`; source Session `CLOSED` |
| Durable baseline | commit `3f4aa05f6641aefc15cf5873f1f6ab279f8d13b2`; tree `5ca583f3a239ed3f1d5cdd33d39db7e2d7fbf860`; CI `34032397080 / SUCCESS` |
| 实现授权 | `NO`; `IMPLEMENTATION_NOT_AUTHORIZED` |

本权威统一资源使用 envelope，但不压平各资源的 typed semantics。它引用
[ARCH-258 business authority](S5-V023-ARCH-258-BUSINESS-PROBLEM-SUCCESS-CRITERIA-AUTHORITY-V1.md)、
[ARCH-259 MCP authority](S5-V023-ARCH-259-MCP-ENDPOINT-TRUST-CREDENTIAL-AUTHORITY-V1.md)、
[ARCH-263 Skill executor](S5-V023-ARCH-263-SKILL-ATTEMPT-EXECUTOR-SIDE-EFFECT-CONTRACT-V1.md)
与 [ARCH-264 Outcome contract](S5-V023-ARCH-264-SUCCESS-CRITERIA-EVALUATION-HUMAN-CONFIRMATION-OUTCOME-CONTRACT-V1.md)，
并复用 [Plan/Attempt](S5-V023-ARCH-208-WORKFLOW-CONTROL-PLAN-APPROVAL-INTERVENTION-PERSISTENCE-V1.md)、
[Evidence](S5-ARCH-010-PRODUCTION-EXECUTION-EVIDENCE-SHARED-READ-MODEL-BOUNDARY-V1.md)、
[Runtime](S5-ARCH-019-V023-EXECUTION-RUNTIME-AUTHORITY-V1.md) 和
[Knowledge](S5-ARCH-011-PRODUCT-INTENT-DYNAMIC-WORK-ROLE-KNOWLEDGE-CONSUMPTION-BOUNDARY-V1.md)
基础。

## 2. 问题与 accepted owner

Skill/MCP invocation、Knowledge retrieval、Runtime observation、Evidence 与 Accounting
目前分属不同模型，不能直接拼接成 authoritative actual-use 状态。Execution domain
拥有 canonical Resource Use authority，因为 use 是 Attempt execution history。Evidence
证明 use facts；projection 消费 snapshot；两者都不拥有 Resource Use。

## 3. Resource Use identity 与 exact binding

`resource_use_id` 是 scope 内稳定、不透明的 Platform identity。它固定 exact Attempt、
`resource_kind`、deterministic `slot_key`/`occurrence_ordinal`、resource revision/digest、
binding snapshot、approved Plan revision/digest、Workflow Run、Task Run、Digital Employee
Definition/Instance、Agent/Runtime Instance、executor/provider/profile revision、authorization
decision 与 predecessor Attempt/Run。任何缺失或 implicit latest 均 fail closed。

P1 每个 Attempt、每个 resource class 使用一个 deterministic managed slot；retry 创建
successor Attempt 和新的 Resource Use，原 identity/facts 不变。Resource-specific payload
继续由 Skill、MCP、Knowledge、Workflow、Runtime 与 Digital Employee typed schema 管理。

## 4. Lifecycle、append-only facts 与 effective state

最低 typed facts 区分：configured、bound、selected、requested、dispatch recorded、accepted、
running、succeeded、failed、cancellation requested/confirmed、outcome unknown、rejected、
unavailable、stale、not executed，以及 measurement recorded/not collected/not measurable。
更正追加 superseding fact，不改写历史。

Versioned reducer 在 named high-water 上计算 canonical projection，并验证 transition 与
source authority：selected 不推出 requested；dispatch 不推出 accepted；accepted/running
不推出 succeeded；cancel requested 不推出 confirmed；timeout 无终态为 unknown；conflicting
terminal facts 为 conflicted/fail closed。“调用成功”不推出 Attempt/Task/Workflow Business
Outcome。

Capability maturity 与 individual execution status 是独立状态系统：资源可成熟但某次
调用失败，也可处于试验成熟度但某次技术调用成功。任何 UI 颜色不得混淆二者。

## 5. Resource-specific mappings

- Skill：复用 ARCH-263 exact Skill/binding/executor、dispatch-before-call、one managed
  slot、READ_ONLY、unknown 与 successor retry。
- MCP：复用 ARCH-259 Endpoint/Trust/allowlist/Secret Reference/Credential Resolver/
  Discovery Snapshot/Tool Selection；P1 仅 read/idempotent path。
- Knowledge：分别记录 published/bound/selected/retrieval requested/retrieved/no result/
  citation/stale/unavailable/not executed；Qdrant snapshot exact-bound。
- Workflow：记录 Definition/approved Plan selection、Run/Task/Attempt eligibility、execution、
  skip/failure/retry/correction/successor；frontend/Pod phase 不得推断。
- Runtime：映射 Provider/Profile、Placement/Instance desired state、observed readiness、
  scheduling、workload/command observation、stop/restart/replace/stale/unavailable。
- Digital Employee：Definition selected → Instance assigned → Placement chosen →
  participation observed → exact Attempt contribution；身份不得合并。

## 6. Measurement authority

每个 `measurement_id` 绑定 Resource Use、metric、source 与 observation window，至少包含
value/null、unit、availability、source identity/digest、observed times、authority level、
confidence、limitations、precision、aggregation eligibility、redaction profile、Evidence
references 与 optional superseded measurement。

Vocabulary 固定为 `MEASURED`, `NOT_COLLECTED`, `NOT_MEASURABLE`, `ESTIMATED`, `STALE`,
`CONFLICTED`。Missing value 永不写零。P1 core metrics 是 duration、request count、
invocation count、retrieval count、citation count 与 attempt count。Cost、token 与
infrastructure/resource usage 只有在 provider/source 具有 authoritative fact 时才
`MEASURED`；否则使用正确的 non-measured state。`ESTIMATED` 不是 billing authority。

## 7. Snapshot 与 Outcome relation

`ResourceUseSnapshot(snapshot_id, digest, high_water)` immutable，包含 exact uses、facts、
measurements、Evidence links、limitations 与 conflicts。ARCH-264 `OutcomeSnapshot` 必须引用
同一个 snapshot ID/digest/high-water。缺失、stale、conflicted 或未授权 snapshot 时，
Business Outcome 只能 `UNDETERMINED`，不能 `CONFIRMED_SOLVED`。

Technical Attempt/Task Outcome 与 Workflow Run Business Outcome 保持不同。Resource Use
事实可证明技术参与，不直接证明业务问题解决。

## 8. Authority boundaries

| 系统 | 权威边界 |
| --- | --- |
| PostgreSQL / Execution domain | Resource Use identities、exact bindings、typed facts、measurements、reducer high-water、snapshots、CAS/idempotency |
| Evidence domain | 证明 use/measurement 的 immutable records；不拥有 use state |
| Provider | native effect、usage 与原生 authoritative measurements；平台验证后摄取 |
| Kubernetes | Control Plane/workload observed resource state；不拥有 Product Resource Use 或 Business Outcome |
| Qdrant | derived vector index；SQL 保存 Knowledge/index snapshot identity 与 authoritative retrieval/citation links |

## 9. Concurrency、CAS、idempotency 与 restart

Resource Use identity、exact binding 与 requested fact 在 dispatch 前同一 PostgreSQL
transaction 持久化；dispatch fact 也必须先 durable。Observation ingestion 以 source
observation ID + digest 幂等；同 identity/bytes replay，different digest conflict且不追加。
Snapshot 使用 CAS/high-water。能同库的 Evidence/fact 同事务；不能原子时明确记录
partial/recovery，不能假装完整。

Restart 从 PostgreSQL 恢复 requested/dispatch/high-water，再向 provider/Kubernetes
re-observe。已 dispatch 但结果不可证明时保持 outcome unknown，不盲目重复 dispatch。
Retry/rerun 创建 successor Attempt/Run。晚到 callback 只关联原 Attempt。

## 10. Authorization、Evidence 与 redaction

Authorization 先于 lookup、existence、list/count、join、snapshot assembly、Evidence
dereference、measurement/export/disclosure。Resource Use 与 Evidence 独立授权；denial
不得通过 status、颜色、count 或 timing 泄露存在性，并产生零外部调用。

仅保存 bounded/redacted input/output/error summary、IDs/digests、typed facts、sources、
timestamps、high-water、measurements、limitations 与 authorized Evidence links。永不保存
secret、credential、完整 prompt、raw request/response 或 private Human content；provider
native ID 按最小必要原则披露。

## 11. Product/Technical projections 与中文术语

Product 与 Technical View 消费同一 ResourceUseSnapshot。Product 显示资源是否真正
参与、结果是否已知、度量是否可用及对业务结果的限制；Technical 显示 exact IDs/
digests、facts、sources、timestamps、high-water、Evidence、measurements 与 conflicts。
不得分别组装或 synthetic fallback。

自然中文：已配置、已绑定、已选择、已请求调用、已发起调用、已接受调用、调用中、
调用成功、调用失败、已请求取消、已确认取消、调用结果未知、不可用、绑定已过期、
未执行、已采集、尚未采集、不可度量、估算值、数据已过期、数据存在冲突。
“调用成功”必须标明是技术结果，不等于业务目标达成。

状态颜色由 backend versioned mapping 产生：绿色只用于权威、完整、新鲜、无冲突的
技术成功；黄色用于 running/partial/stale/not collected/estimated/unknown；红色用于
failed/rejected/unavailable/conflicted/authorization failure；灰色用于 configured/bound/
selected-not-executed 或 not measurable/not applicable。颜色不表示 Capability maturity。

## 12. Failure/recovery 与 P1 acceptance

拒绝 implicit latest、binding/digest mismatch、selected 冒充 invoked、dispatch 冒充
accepted、technical success 冒充 business outcome、denial 后外部调用、duplicate dispatch、
conflicting replay、late callback 污染 successor、stale snapshot、missing measurement=0、
cross-scope count leak、Evidence 越权与 Pod phase 冒充 Outcome。Recovery 追加 facts、
re-observe 并诚实投影 unknown/partial/conflict。

P1 独立验收必须用真实服务证明 22 项完整边界，包括 exact identity/binding、fact reducer、
measurement vocabulary/core metrics、snapshot/Outcome linkage、CAS/replay/restart、auth/
redaction、shared projections 与所有负向行为。Skill、MCP、Knowledge、Native Runtime
四条真实路径不能由 fixture/mock 替代；OpenClaw 只需 truthful partial/unavailable，
不得 fallback。验收不授予 Preview/release/production/certification。

## 13. Rejected/Post-P1、dependency 与 Human constraints

P1 拒绝 exactly-once external effects、cost/billing authority、cross-provider scheduling、
automatic replacement、dynamic multi-Skill/MCP orchestration、OpenClaw fallback、完整 Model
Governance、generic FinOps、HA/multi-cluster、production certification、generic untyped status
与 public CRD/API-group change。

后续实现顺序为 typed Resource Use/reducer/measurement contract、additive PostgreSQL
schema/repository、Skill/MCP/Knowledge/Runtime adapters、snapshot/Outcome authorization、
shared projections 与独立 real acceptance；不分配 Session。Human constraints 固定
Execution-domain owner、one slot per resource class、append-only facts、six-state measurement、
core metrics、missing never zero、technical/business separation、maturity/execution separation、
auth-before-disclosure 与 implementation authorization `NO`。

## 14. Provenance 与 supersession

Source provenance：`S5-V023-ARCHITECTURE-PUBLICATION-AUTHORITY-BUNDLE.md`，
`118730` bytes，`2696` lines，SHA-256
`8570e725c4a43df2d94b2cf59b87cedefd15b9362cba20c4835f495be3ad7420`。ARCH-266
Human Authority Capsule 优先于完整 proposal/review。Proposal 的旧 baseline、
`SOURCE_CONFLICTS`、九项 `OPEN_DECISIONS`、`PROPOSED` owner/metrics/schema choices 与
`READY_FOR_HUMAN_G2_DECISION` 均已被 Capsule supersede；物理 schema/migration owner
仍留给单独 implementation gate，不能由本 publication 推定。未发现 Capsule 间或与
既有 accepted architecture 的实质冲突。
