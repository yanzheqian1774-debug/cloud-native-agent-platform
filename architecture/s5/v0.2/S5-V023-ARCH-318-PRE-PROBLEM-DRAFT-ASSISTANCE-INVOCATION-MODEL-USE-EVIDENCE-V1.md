# S5-V023-ARCH-318 — Pre-Problem Draft Assistance Invocation 与 Model Use/Evidence v1

## 1. 决策记录

| 字段 | 值 |
| --- | --- |
| Session / 标题 | `S5-V023-ARCH-318` / Pre-Problem Draft Assistance Invocation 与 Model Use/Evidence |
| 类型 / Gate | `ARCH / BOUNDED G2` |
| 决策状态 | `PROPOSED / AWAITING_HUMAN_ARCHITECTURE_DECISION` |
| 实现状态 | `NOT_STARTED / NOT_AUTHORIZED` |
| Contract 状态 | internal v0.2.3 candidate；`NOT_FROZEN` |
| 分配权威 | Human 正式分配；仅授权形成 G2 草案、文档验证、Draft PR，不等于接受本方案 |
| 固定仓库基线 | `origin/main` source `f189212232fc194859a695f0307e83b0c7b73c0f`; tree `a8a9251d5d2e47605d18bb63e362164ec4c920d2` |
| 固定 308 输入 | source `141a17ecd34ec3b721e1c8a8ae33277c4b454e42`; tree `b195b4612a4ab9f295e3c6f9a82199b05db7ac0e` |
| 固定 316 输入 | source `3cc98cde9452e5036ad9bd44981f5fff9499b011`; tree `bb614158fded36277bced028baed88240f29f8d0` |
| 后续实现授权 | `NO`; migration、endpoint、provider、frontend、真实调用、部署与运行验收均需单独 Human G1 分配 |

本记录只决定下列最小链路的内部 owner、identity、authorization、恢复和证据候选：

```text
问题输入 → AI 澄清 → 用户补充 → 可编辑草稿 → Human 确认 → 正式 Problem
```

它不重做平台整体架构，不创建公开 API/CRD，不改变 Kubernetes API group，不修改既有
Attempt、Task 或 Workflow lifecycle。附件中的 `PROPOSED` 内容仅是设计输入；本记录
重新给出的所有选择在 Human 裁决前仍为 `PROPOSED`。

## 2. 继承权威与边界

本候选仅继承这些具体条款：

- ARCH-258：Product domain 唯一拥有正式 Business Problem；只有 Human 确认后的现有
  create command 可以写正式 Problem。模型不能创建或修改正式 Problem/Success
  Criterion/Criteria Set，也不能批准 Plan 或启动执行。
- ARCH-019：Attempt 是 Task Run 下的一次授权 execution try；retry 创建 successor
  Attempt。Pre-Problem 辅助不能伪造 Plan、Workflow Run、Task Run 或 Attempt。
- ARCH-266：Execution domain 是 canonical Resource Use 唯一 owner/writer；Evidence 和
  projection 不能拥有 Resource Use。
- ARCH-010：Evidence 是独立、immutable、schema-versioned、append-only 的 allowlisted
  fact；不得成为第二状态机，不得保存 raw prompt/response、secret 或 unrestricted
  diagnostics。
- ARCH-018：新增 product-continuity facts 使用 domain-owned typed ports 和现有
  PostgreSQL primary adapter；不引入新数据库或持久基础设施；历史、删除、tombstone
  和 retention 必须由明确治理规则处理。
- ARCH-259/263：authorization-before-disclosure/credential-resolution/dispatch、
  persist-before-dispatch、`OUTCOME_UNKNOWN`、successor retry、late-result isolation 和
  no-exactly-once-claim 是可复用语义，不把 MCP/Skill Attempt identity 套到本链路。
- 固定 308 的 H308-01/02/03A：Model Governance 继续拥有 exact Model/Provider/Endpoint/
  Profile facts；exact resolution 与 current exact authorization 分离；无 implicit latest、
  display-name、frontend 或 environment default fallback。H308-03C/04A/04B 仍需分别裁决。

若 Human 不接受本记录，以上既有权威不受影响，316 的无模型录入与 317 已授权兼容组合
也不受阻塞。

## 3. 推荐决策概览

推荐建立一个有界、内部的 `Draft Assistance` domain，拥有辅助上下文元数据、turn
元数据、server-owned binding consumption snapshot 和 `DraftAssistanceInvocation`。
该 domain 不拥有模型、授权、Resource Use、Evidence、provider effect 或正式 Problem。

```text
Browser volatile draft/content
        │ correlation only; no authority
        ▼
Draft Assistance context/turn/invocation metadata ── exact refs ──► Model Governance
        │                   │                                      Authority
        │                   ├── conditional MODEL use ───────────► Execution Resource Use
        │                   └── conditional Evidence ref ─────────► Evidence owner
        └── Human-confirmed exact link only ─────────────────────► Business Problem owner
Provider adapter owns only native transport/effect/observation.
```

这是一项新的 cross-plane internal ownership 决定，因此是 G2。它不把 Draft Assistance
提升为通用 State Plane、chat system、planning engine 或 execution Control Plane。

## 4. Owner 与 identity 关系

| 对象/事实 | 唯一 owner | 稳定 identity / scope | 持久性与限制 |
| --- | --- | --- | --- |
| 浏览器草稿内容 | frontend 仅拥有当前页面的非权威状态 | client nonce 只作 UI correlation；不是 Platform identity | 仅内存；刷新、关闭、scope/principal 变化即丢失；不得进 local/session storage |
| `DraftAssistanceContext` | Draft Assistance domain | server-minted opaque `draft_assistance_context_id`; `(namespace, security_domain)` 与 initiating principal 固定 | 只存非内容元数据、lease/closed/expired facts；不是 Session/Problem/Run |
| `DraftAssistanceTurn` | Draft Assistance domain | server-minted `draft_assistance_turn_id`; context 内正整数 ordinal/version | 只存 version、predecessor、content disposition；不存用户文本、问题、草稿或其普通 digest |
| `DraftAssistanceBindingSnapshot` | Draft Assistance domain owns the consumption snapshot; Model Governance owns every referenced Model fact | server-minted snapshot ID/digest；同 scope；固定 purpose 与 exact governed revisions | immutable；只能复制 exact IDs/digests/high-water/limits，不得复制 secret 或改写 Model facts |
| `DraftAssistanceInvocation` | Draft Assistance domain | server-minted opaque invocation ID；exact context/turn/version/snapshot | 持久 metadata root 和 append-only state；不是 Attempt |
| authorization decision | existing Authority / Grant Administration | exact subject, scope, action, target, policy generation/version, decision ID, expiry | Draft Assistance 只保存 reference；页面声明无效 |
| provider effect/response | provider | opaque provider correlation | 只作为 observation；不拥有 Platform state、authorization 或 business success |
| `MODEL` Resource Use（若接受 H308-04A 修订） | Execution domain | independent `resource_use_id`，typed context 指向 exact Draft Assistance Invocation | 与 Attempt Resource Use 分表兼容；Draft Assistance 不能写 use state |
| Model Evidence（若接受 H308-04B） | independent Evidence owner | immutable Evidence identity/digest，引用 invocation 和可选 Resource Use | 独立读授权；不推进 invocation/use/problem state |
| 正式 Business Problem | Product/Business Problem domain | existing stable Problem/revision identities | 仅用户确认后的现有 create command 写入；可追加非内容 provenance link |

### 4.1 浏览器内容与持久元数据的明确分离

浏览器持有当前用户输入、澄清回答和可编辑草稿正文。服务端请求处理期间可在受控内存中
处理这些内容，但平台数据库、日志、Evidence、Resource Use、异常和 tracing 均不持久化
raw prompt、raw response、用户输入、澄清答案或草稿正文。

服务端持久化 context/turn/invocation 的存在、版本、状态、exact refs、授权 reference、
时间、受控错误类别和内容处置码。页面关闭不可被可靠观测，因此不得伪造 `CLOSED`；显式
取消可追加 `CONTEXT_ABANDONED`，否则 lease 到期后追加/投影 `CONTEXT_EXPIRED`。这不删除
invocation history。

关闭页面后，持有独立 exact read grant 的同一 scope/principal 可以按 invocation ID 查询
metadata。响应必须明确 `CONTENT_NOT_RETAINED`；平台不能恢复草稿正文，也不能自动重放模型
调用。context 和 turn 的最小 metadata roots 先于 invocation 存在，因此 invocation 不引用
浏览器对象或 dangling row。若受治理删除/最小化发生，non-sensitive tombstone 保留原
identity、scope、authority、time、reason class 和关系状态；禁止复用 identity。

### 4.2 与正式 Problem 的关系

模型输出仅产生 `NEEDS_CLARIFICATION` 或 `DRAFT_READY`。用户可编辑、拒绝或放弃；任何
状态都不自动调用 Problem writer。只有用户在当前可信 context 中确认可见最终字段后，
现有 Business Problem create authorization/idempotency path 才运行。

成功创建后可由 application coordinator 追加一个 exact、非内容的
`DRAFT_CONFIRMED_AS_PROBLEM` link，引用 invocation/turn version 与 Problem revision/digest。
该 link 不复制正文、不授予 Problem READ、不让模型成为 creator，也不允许 Draft
Assistance 修改 Problem history。若 link append 失败，Problem 创建结果保持权威，link
报告 `RECOVERY_REQUIRED`，不得重建 Problem。

## 5. Server-owned exact Model binding 与 authorization target

### 5.1 Binding policy 与 snapshot

每个可调用 scope 必须有一个由服务端管理、versioned、CAS-protected 的
`ProblemDraftAssistanceProfileRevision`。它固定：

- purpose `PROBLEM_DRAFT_ASSISTANCE`；
- exact Model ID/revision/digest；
- exact Provider、Endpoint、Connection Profile ID/revision/digest；
- adapter identity/revision；
- output schema version；
- bounded token/body/time/call limits；
- Model Governance lifecycle/high-water validation requirement；
- authorization target format version。

调用时 Draft Assistance 在当前 authorization 后通过 Model Governance exact resolver
读回同一组 facts，生成 immutable `DraftAssistanceBindingSnapshot`。profile successor 只
影响新 invocation；既有 snapshot 不跟随 head。缺失、digest mismatch、不 eligible、
unknown/stale required fact 或 store unavailable 均 fail closed。前端不能提交 Model、
Provider、Endpoint、Profile、adapter 或 fallback 值；display name、`latest`、环境默认值和
旧 runtime `MODEL_*` 配置都不是 authority。

### 5.2 最小授权动作与 exact targets

| owner / action | trusted-server exact target | 允许的唯一效果 |
| --- | --- | --- |
| `DRAFT_ASSISTANCE / REQUEST_DRAFT_ASSISTANCE` | `draft-assistance:context:{context_id}:turn:{turn_id}:version:{version}` | 为该 exact turn 请求一次辅助；不创建 Problem |
| `MODEL_GOVERNANCE / INVOKE_MODEL` | `model:invocation:draft-assistance:{context_id}:{turn_id}:{invocation_id}:{binding_snapshot_id}:{model_id}:{model_revision_id}:{model_digest}` | 允许该 exact invocation 最小 Model read 与一次 dispatch admission |
| `DRAFT_ASSISTANCE / READ_DRAFT_ASSISTANCE_INVOCATION` | `draft-assistance:invocation:{invocation_id}` | 读取 allowlisted metadata；不读取 raw content/Evidence |
| `DRAFT_ASSISTANCE / CANCEL_DRAFT_ASSISTANCE_INVOCATION` | `draft-assistance:invocation:{invocation_id}` | 追加取消请求并按 provider 能力尝试取消 |

所有 segment 由 trusted server 从 typed values 构造并完整比较；无 wildcard/prefix match。
scope 是 principal、decision、record 和 repository key 的独立必填字段，不能由 target string
或前端提供。`INVOKE_MODEL` decision 绑定 initiating authenticated principal；provider
transport 只接受封装后的 authorized invocation，不接受 caller header `authorized=true`。

顺序固定为：authenticate/trusted scope → validate bounded request → server mint IDs and
load exact profile reference → build exact targets → current authorization → Model owner exact
readback/snapshot → persist request → secret resolution → persist dispatch fact → transport。
授权拒绝发生在 Model protected lookup、secret resolution 与 provider call 之前，并产生零
resolver/provider call。若未来需要 service-workload identity 的第二授权，必须单独扩展，不在
本候选中假定完整 workload IAM 已存在。

## 6. Invocation state、dispatch、取消和恢复

```text
REQUESTED
  ├─> REJECTED / FAILED_PRE_DISPATCH / NOT_EXECUTED
  └─> DISPATCH_RECORDED
        ├─> ACCEPTED ─> RUNNING ─> SUCCEEDED | FAILED
        ├─> CANCELLATION_REQUESTED ─> CANCELLATION_CONFIRMED
        └─> OUTCOME_UNKNOWN
```

- invocation identity、turn/version、exact binding snapshot、authorization decision、
  idempotency claim 和 `REQUESTED` 在 PostgreSQL commit 后才可继续。
- Secret resolver 成功后，`DISPATCH_RECORDED` 必须在 transport 前 durable。它只证明平台
  已越过不可安全重发边界，不证明 provider accepted/running/succeeded。
- 授权、binding 或 secret resolution 在 dispatch 前失败，记录稳定非泄露类别；零外部调用。
- transport 已可能发生而无法获得权威终态时必须 `OUTCOME_UNKNOWN`。即使 crash 发生在
  `DISPATCH_RECORDED` 后、实际 socket write 前，也保守保持 unknown，不自动重发。
- refresh/restart 首先按 provider 的受信 observation/correlation 能力 re-observe 原
  invocation；无法证明则保持 unknown。
- 用户取消先追加 `CANCELLATION_REQUESTED`。只有 provider 或受信 observation 明确确认
  才追加 `CANCELLATION_CONFIRMED`；关闭页面、abort fetch 或断开 HTTP 不是确认。
- 显式重试创建新的 successor invocation、新 idempotency key 和新 turn generation，引用
  predecessor；不复用 invocation identity。UNKNOWN 不自动重试。
- late result 只能追加到原 invocation；只有仍活跃、同 principal/scope、同 context lease、
  同 exact turn version 的浏览器响应通道可接收正文。否则解析后立即丢弃正文，记录
  `RESULT_CONTENT_NOT_RETAINED`，不得覆盖 successor/local edits。
- provider exactly-once 不作承诺。若 provider 支持 native idempotency key，可传递受控值
  并保存 opaque correlation，但不能提升平台保证。

### 6.1 稳定错误分类

| Reason code | 外部调用可能性 | 恢复语义 |
| --- | --- | --- |
| `DRAFT_ASSISTANCE_AUTHORIZATION_DENIED` | `NO` | disclosure-safe terminal rejection；新授权后显式新请求 |
| `MODEL_BINDING_NOT_ELIGIBLE` / `MODEL_BINDING_MISMATCH` | `NO` | 修正 server-owned profile/successor 后显式新请求 |
| `IDEMPOTENCY_PAYLOAD_MISMATCH` | `NO` | fail closed；不能换 payload 复用 key |
| `IDEMPOTENCY_REPLAY_UNVERIFIABLE` | `NO` | 不 dispatch；Human 可显式创建 successor |
| `SECRET_REFERENCE_UNAVAILABLE` / `CREDENTIAL_RESOLUTION_FAILED` | `NO` | 原 invocation 终止于 pre-dispatch failure；修复后 successor |
| `PROVIDER_RATE_LIMITED` / `PROVIDER_UNAVAILABLE` | 只有 provider 权威响应可证明 `YES` | 记录 failed 与 retry-after（若 allowlisted）；不自动 retry |
| `PROVIDER_TIMEOUT` / `TRANSPORT_AMBIGUOUS` | `UNKNOWN` | `OUTCOME_UNKNOWN`；re-observe，否则显式 successor |
| `PROVIDER_RESPONSE_INVALID` / `OUTPUT_SCHEMA_INVALID` | `YES` | 技术调用可完成但无可用草稿；正文丢弃，显式 successor |
| `STALE_DRAFT_VERSION` / `CONTEXT_EXPIRED` | 已完成的原调用不变 | 不交付/覆盖内容；只更新原 invocation metadata |
| `RESULT_CONTENT_NOT_RETAINED` | 原调用可能已成功 | metadata 可查询，正文不可恢复；只能显式 successor |

HTTP/status 文案由 backend versioned mapping 产生，不能包含 provider body、endpoint secret、
foreign existence 或 stack。`FAILED` 只用于存在权威 failure/validation result 的情况；无法
证明终态时必须使用 `OUTCOME_UNKNOWN`。

## 7. 无 raw 内容条件下的 idempotency

普通 SHA-256 或可读摘要会让低熵业务文本可被离线猜测，因此禁止把 raw payload、普通
payload digest、可搜索摘要或 embedding 持久化。推荐使用受信服务端的 versioned keyed
commitment：

```text
payload_commitment = HMAC-SHA-256(
  idempotency_pepper_version,
  domain_separator || canonicalization_version || scope || action ||
  context_id || turn_id || expected_version || exact request content
)
```

pepper 通过外部 typed Secret Reference 提供，仅在授权后的受信服务内存中使用；数据库
只保存 commitment、algorithm/canonicalization version 和 pepper reference identity/version，
不保存 pepper。该 commitment 不进入 frontend、Evidence、Resource Use、日志或错误文本。

- same scoped key + same commitment 返回原 invocation metadata，不重复 dispatch；
- same key + different commitment 返回 `IDEMPOTENCY_PAYLOAD_MISMATCH`；
- replay 发生在结果正文已丢弃后，只能返回 `RESULT_CONTENT_NOT_RETAINED`，不能重建响应；
- pepper version 在 idempotency replay window 内必须可解析。若 key 被销毁、不可用或
  canonicalization version 不受支持，返回 `IDEMPOTENCY_REPLAY_UNVERIFIABLE` 并禁止 dispatch；
- HMAC 只降低离线猜测风险，不是加密、内容恢复、语义证明或长期 Evidence；pepper 泄露会
  降低保护，因此其 rotation、访问和销毁需要独立 secret governance；
- 内存、swap、crash dump、APM 和 provider transport 仍是残余暴露面，G1 必须验证禁采样、
  禁 body logging、bounded buffers 和 error normalization。

该方案明确接受一个产品限制：页面关闭或成功响应丢失后，原草稿不能恢复；用户只能显式
发起 successor。不能用保存 raw 内容或自动重发 UNKNOWN 来掩盖此限制。

## 8. 非 Attempt `MODEL` Resource Use 兼容方案

### 8.1 H308-04A 推荐修订

推荐 `ACCEPT_WITH_AMENDMENT`：接受 `MODEL` Resource Use 和 Execution 唯一 owner，但
不把 Draft Assistance Invocation 伪造成 Attempt，也不修改现有 `ResourceUseBinding` 的
required `attempt_id/plan/workflow/task` 字段为 nullable。

现有 `resource_use.uses` 及其 child tables 保持 Attempt-only v1，schema、FK、ID 算法和
readers 不变。新增一个 additive、Execution-owned typed sibling family，工作名为
`ContextualResourceUseV2`，首批只允许：

```text
context_kind = DRAFT_ASSISTANCE_INVOCATION
resource_kind = MODEL
context_id = exact draft_assistance_invocation_id
```

它固定 scope、独立 resource_use_id、context kind/id、slot/ordinal、exact Model/Provider/
Endpoint/Profile/adapter revisions/digests、binding snapshot、authorization decision、
predecessor invocation、typed facts、measurements、Evidence refs、claims、high-water 和
snapshot。不存在 Attempt/Plan/Workflow/Task placeholder、sentinel 或 nullable 字段。

Draft Assistance coordinator 调用 Execution-owned application port；只有 Execution writer
可创建/use/reduce。Draft Assistance、Model Governance、provider 和 Evidence writer 均不能
直接写 Resource Use。Technical success 仍不推出正式 Problem、Execution Attempt 或
Business Outcome。

### 8.2 Reader-first 与 migration/rollback

1. 先发布 versioned union reader/reducer/projection，现有 Attempt v1 被显式投影为
   `context_kind=ATTEMPT`；unknown context/schema 显示 `UNSUPPORTED / NOT_VERIFIED`，不崩溃、
   不丢历史、不推断成功。
2. conformance 同时验证原 Attempt-only repository 与新 typed sibling repository；现有 API
   和 reader 继续只返回原集合，除非调用方明确请求 v2 union contract。
3. 添加 sibling tables 和独立不相交 typed ID namespace；不修改 migration 0015，不回填
   环境变量模型调用，不 dual-write 同一 fact。
4. 在 writer activation 前完成 reader/restart/backup/forward-fix 证明和 single-writer gate；
   新 writer 启用后，回滚必须先停 Draft Assistance writer。旧 binary 可继续读 Attempt v1，
   新 v2 facts 保留但不可宣称已被旧 reader理解。
5. 只有 reader gate、H308-04A Human 接受和单独 G1 migration authority 全部满足后，writer
   才能发出首条 `MODEL` use。

该方案的代价是首批存在两个物理 family 和一个 union projection；它换取旧 Attempt reader
零破坏和无伪造 identity。未来物理合并需要另一个兼容决定，不能在 G1 顺手完成。

若 H308-04A 被拒绝，Draft Assistance Invocation metadata 仍可独立存在，但产品和验收必须
明确 `CANONICAL_MODEL_RESOURCE_USE_NOT_AVAILABLE`，不得把 invocation metadata 或 Evidence
冒充 Resource Use。

## 9. Model Evidence 方案

### 9.1 H308-04B 推荐

推荐独立接受 versioned `model-draft-assistance-invocation-evidence.v1`，由现有 Evidence
owner/sole writer 追加。allowlist 只包含：

- Evidence identity、schema version、scope/security domain；
- exact context/turn/invocation/binding snapshot IDs；
- exact Model/Provider/Endpoint/Profile/adapter revision IDs/digests；
- exact authorization decision reference；
- optional Execution-owned resource_use_id/snapshot digest（仅 H308-04A 已接受并实际写入时）；
- requested/dispatch/provider observation/recorded timestamps 和 typed terminal status；
- bounded provider correlation、call count、latency/token/cost measurement；不能测量时使用
  `NOT_COLLECTED`/`NOT_MEASURABLE`，不能填零；
- stable error/limitation/content-disposition codes。

禁止 raw prompt/response、prompt/response plain digest、keyed idempotency commitment、secret
reference value、credential、Authorization header、private Human content、provider raw body、
stack 或 unrestricted diagnostics。未知字段/unsafe value fail closed。

Evidence append 不推进 invocation 或 Resource Use state；Resource Use fact 也不等于 Evidence。
Evidence reference visibility 与 Evidence content dereference 各自需要 exact authorization；
Resource Use/Invocation grant 不隐含 Evidence grant。reader-first 规则与 H308-04A 相同，
Evidence writer 必须在所有相关 readers 接受 schema version 后才启用。

若 H308-04B 被拒绝，调用仍可能产生 owner metadata，但不能声称 canonical Model Evidence、
完整审计或 provider-confirmed evidence chain；任何真实 provider acceptance 需要 Human 另行
说明可接受的替代证据。

## 10. 数据处理、retention、删除与 provider 留存

首批推荐只使用明确版本化的合成问题数据：不得包含真实客户、员工、生产、个人、机密或
credential 内容。raw prompt 仅在受控请求内存中存在；raw provider response 仅在受控内存
中完成 strict schema parsing，frontend 只接收 allowlisted clarification/draft fields，永不
接收 provider raw body。两者的平台持久化期限均为零。用户确认后的最终
`title/description` 按 Business Problem 既有规则持久化；它是 Human-confirmed Product
content，不是 raw provider log。

Invocation metadata 是 immutable facts + reducer projection。当前不存在已接受的精确期限，
因此本候选明确**不实施或默认 30 天自动删除**。在 Human retention/legal-hold/erasure
决定前：

- 不宣称合规 retention 或 hard deletion；
- 不由 controller、页面关闭、rollback 或 shutdown 自动删除；
- authorized tombstone/minimization 只追加 non-sensitive fact，不改写历史；
- identity、authority、time、reason class、predecessor/successor 和 Problem link 的最小事实
  保留，且不得包含被移除内容；
- backup expiry、provider deletion 和 cryptographic deletion 均不作推定。

“平台不持久化”不等于 provider 不留存。真实调用会把内容传给 provider；H308-03C 的后续
授权必须记录 provider/endpoint 的 data-retention、training/logging、region 和 deletion
能力/限制。provider 侧留存由 provider 原生政策/协议负责，平台只能记录受控声明和
Evidence，不能宣称已删除外部副本。若 provider 条款不满足 Human 允许的数据边界，真实
验收被阻塞，synthetic local adapter 测试不能替代。

## 11. H308 三项分别处置

| 决定 | 推荐处置 | 本候选的精确修订/约束 | 若拒绝或未决的影响 |
| --- | --- | --- | --- |
| `H308-03C` | `ACCEPT_WITH_CONSTRAINTS`，仅作为后续单独授权的真实 provider acceptance | 只用合成数据；明确 provider/endpoint/dataset/预算/credential ref/timeout/cancel/Evidence；不授予 certification、production 或持续可用性 | 不阻塞 deterministic G1 开发，但不能声称真实 provider 闭环 |
| `H308-04A` | `ACCEPT_WITH_AMENDMENT` | Execution 仍唯一 owner；增加非 Attempt typed sibling `ContextualResourceUseV2`；不 nullable 化 Attempt 字段；reader-first | Draft Assistance 可运行，但必须标记无 canonical Model Resource Use |
| `H308-04B` | `ACCEPT` 本记录第 9 节的 versioned allowlist | Evidence owner 独立、reader-first、独立授权；无 raw/payload digest/HMAC | 不能声称 canonical Model Evidence 或完整 provider-confirmed evidence chain |

三项完全可分割。Human 接受、修改或拒绝任一项，不推定另外两项，也不自动授权 migration、
真实调用、部署、Ready 或 merge。

## 12. 真实 provider 验收的后续授权字段

任何真实调用前必须有一份 Human-approved execution authorization record；以下字段缺一即
fail closed：

| 字段 | 要求 | 未确定影响 |
| --- | --- | --- |
| source/tree + adapter revision | 固定待验收代码与 exact adapter | 无法复现，禁止调用 |
| provider/endpoint | exact Provider/Endpoint ID、revision、digest、region、native model ID | 无 exact target，禁止调用 |
| dataset | synthetic dataset ID、immutable revision/digest、允许字段和禁止数据分类 | 无法证明数据边界，禁止调用 |
| call cap | 推荐完整链最多 `2` 次 provider dispatch；无自动 retry | 无硬上限，禁止调用 |
| cost cap | Human 指定数值、currency、计价 source；无法权威计量时仍需外部预付/配额硬限制 | 不得以 `NOT_MEASURABLE` 绕过预算，禁止调用 |
| credential reference | exact Secret Reference ID/version、resolver/profile、expiry/revocation owner | 不读取 fallback/env key，禁止调用 |
| timeout | 推荐 connect `10s`、read `60s`、total `75s`，并受 provider profile 更小上限约束 | 无 bounded I/O，禁止调用 |
| cancellation | provider 是否支持 cancel/observe；不支持时只能 `CANCELLATION_REQUESTED`/UNKNOWN | 不得宣称 confirmed cancellation |
| Evidence | required schema/version、writer、read grants、provider correlation/receipt、redaction profile | 若 04B 未接受，必须由 Human 指定替代且不得称 canonical Evidence |
| provider data policy | retention/training/logging/region/deletion 能力与 limitation codes | 不满足 synthetic-only/approved policy 时禁止调用 |

推荐验收正向链为一次 clarification + 一次 draft，故 dispatch cap 为 2。任何 transport
ambiguity 不自动消耗额外 dispatch；重新尝试需要新的 Human-visible successor action，并且
仍受剩余 cap 约束。本 G2 不填写 provider、cost 或 credential 的真实值，也不执行调用。

## 13. Human 可分项裁决表

| ID | 推荐选择 | Human 可接受/修改/拒绝的边界 | 未解决影响 |
| --- | --- | --- | --- |
| `H318-01` | 接受独立 Draft Assistance owner 和 metadata roots | owner、scope、identity、非内容持久化 | 未决则无合法 invocation identity，G1 writer blocked |
| `H318-02` | 接受非 Attempt Invocation | 保持 Attempt/Plan/Run 语义不变 | 拒绝需另一个 G2 扩展 Attempt；不得伪造执行链 |
| `H318-03` | 接受 server-owned exact binding snapshot 与第 5 节 targets | profile/snapshot/target versioning | 未决则 Model resolution/authorization/dispatch blocked |
| `H318-04` | 接受第 6 节 recovery state machine | persist-before-dispatch、UNKNOWN、cancel、late result、successor retry | 未决则外部调用 blocked |
| `H318-05` | 接受 keyed commitment | HMAC algorithm、canonicalization、pepper lifecycle、不可恢复限制 | 未决则 crash-safe payload consistency 与 no-content persistence 不能同时满足 |
| `H318-06` | 接受 synthetic-only、raw content zero-persistence | platform data handling 与 confirmed Problem boundary | 未决则任何 provider/production-like acceptance blocked |
| `H318-07` | 决定 metadata retention/tombstone policy；本候选推荐暂不自动删除 | exact duration/legal hold/erasure/backup policy 可后续收敛 | 不阻塞纯合成内部开发，但阻塞合规/production claim；不得默认 30 天 |
| `H308-03C` | 见第 11/12 节，单独裁决 | 真实 provider acceptance 及其授权包 | 未接受则不得真实调用或声称闭环 |
| `H308-04A` | 见第 8/11 节，单独裁决 | `MODEL` Resource Use + non-Attempt compatibility | 未接受则无 canonical Model use history |
| `H308-04B` | 见第 9/11 节，单独裁决 | versioned Model Evidence | 未接受则无 canonical Model Evidence |

Human 可以对每行分别 `ACCEPT`、`ACCEPT_WITH_AMENDMENT`、`DEFER` 或 `REJECT`。本文件、
任务分配、commit、Draft PR 或 CI 结果均不构成任何行的接受。

## 14. 后继 G1 最小实施包

只有 H318-01..06 获得足够明确的 Human 决定且 Human 另行分配 G1 后，才建议按以下顺序：

1. **Contract/readers first**：增加 internal domain values、ports、versioned DTO/reducers、
   exact target builders 和 unknown-version readers；不接 provider writer。
2. **Additive persistence/authorization**：在现有 PostgreSQL 内添加 Draft Assistance metadata
   schema、CAS/idempotency claims、binding snapshots；装配 current exact authorization。
3. **Secret/transport boundary**：接入 provider-neutral trusted resolver、sealed invocation、
   bounded adapter 和稳定 error mapping；先用 deterministic synthetic adapter。
4. **Conditional Resource Use/Evidence**：只在 H308-04A/04B 分别接受后部署相应 reader-first
   schema 和 sole-writer paths；未接受项保持明确 limitation。
5. **Workbench**：接入 clarification/draft/edit/cancel/confirm/manual fallback；正式 create
   继续复用 316 owner path，不添加 Plan/Criteria/Run side effect。
6. **Acceptance**：真实 PostgreSQL/restart/security/real-browser；只有 H308-03C 及第 12 节
   execution authorization 完整时才进行最多两次真实 provider dispatch。

未来 G1 必须选择一个 Human 固定的集成 base。它可以包含 317 已交付的兼容组合，但本 ADR
不读取 317 未提交内容、不修改其文件、不把 318 作为 317 的前置 gate。共享文件冲突由未来
集成 owner 在固定 source/tree 上处理。

## 15. 后继验收矩阵

| 边界 | 正向证明 | 必须负向证明 |
| --- | --- | --- |
| Identity/owner | restart 后 exact context/turn/invocation/snapshot metadata readback | 无 Attempt/Plan/Run/Problem 伪造；frontend/provider 不能 mint Platform identity |
| Scope/auth | exact targets、current decision、same-scope read | wrong subject/scope/action/target/expiry/revocation 零 lookup/resolver/provider call |
| Binding | exact Model/Provider/Endpoint/Profile/adapter refs 与 high-water 一致 | latest/name/env/default/fallback 与 digest mismatch fail closed |
| Content | live response形成 clarification 或 editable draft；Human confirm 后才创建 Problem | DB/log/Evidence/trace 无 raw prompt/response/普通 digest；模型不能创建正式对象 |
| Idempotency | same key/commitment 返回原 identity；conflict typed | pepper unavailable 不 dispatch；不能恢复已丢失正文 |
| Dispatch/recovery | request/dispatch durable ordering，restart re-observe | dispatch≠success；UNKNOWN 不自动重发；late result 不污染 successor |
| Cancel/retry | request/confirmed 分离；explicit successor | fetch abort/page close≠confirmed；不复用 invocation identity |
| Resource Use | 若 04A 接受，v1 Attempt 与 v2 context union 正确 | 不 nullable Attempt；旧 reader 不崩溃/不推断；sole writer |
| Evidence | 若 04B 接受，versioned allowlist、independent grant/read | Evidence 不推进 state；无 raw/HMAC/secret；unknown schema not verified |
| Retention | tombstone/minimization 保持最小非敏感关系 | 无默认 30 天、shutdown delete 或外部 provider deletion claim |
| Browser | clarification→supplement→draft→edit→confirm 的真实 UI/BFF 链 | page helper/fixture/mock 不冒充正式闭环；manual fallback 保持可用 |
| Real provider | 仅在 03C 授权包完整时 provider-confirmed technical result | call/cost/data/timeout caps；无 certification/business success 推断 |

## 16. Rejected 与 out of scope

明确拒绝：复用或扩展现有 Attempt 作为 pre-Problem identity；BFF 直接无记录调用 provider；
frontend model selection；implicit latest/display-name/env fallback；raw content 或普通 digest
持久化；Evidence/Resource Use 双写；UNKNOWN 自动重发；exactly-once claim；取消请求冒充
确认；late result 覆盖 successor；模型直接创建 Problem/Success Criterion、批准 Plan 或
启动 Workflow/Task/Runtime。

本任务不含产品代码、SQL、公开 API/CRD、运行配置、服务、凭据、真实模型调用、317 资产、
部署、Ready、merge、G2 代签或 Session 关闭。

## 17. 草案终态

```text
G2_DRAFT_COMPLETE
AWAITING_HUMAN_ARCHITECTURE_DECISION
IMPLEMENTATION_NOT_AUTHORIZED
SESSION_OPEN
```
