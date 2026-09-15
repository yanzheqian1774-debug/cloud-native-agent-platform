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
| 本轮固定审阅起点 | source `af9a3b4d528745a87c2027ca9d2d414b884f51df`; tree `c611f9eac8a2cefeb795c40cc8ecebc592611202`; Draft PR `#174` |
| 最终澄清固定起点 | source `9e36e0faba1ddf1298766f25f8ec9b0f17f568d1`; tree `61ab25701215283470108c6e054bfe3dbb625993`; Draft PR `#174` |
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

调用时 Draft Assistance 先从 server-owned profile revision 读取只含 exact identity/digest、
purpose、scope 和 target-format version 的非 secret binding envelope。该 envelope 只用于构造
authorization target，不构成 Model protected read、可调用 snapshot 或 grant。`INVOKE_MODEL`
被允许后，Draft Assistance 才通过 Model Governance exact resolver 读回并验证同一组受保护
facts，生成 immutable `DraftAssistanceBindingSnapshot`。profile successor 只影响新
invocation；既有 snapshot 不跟随 head。缺失、digest mismatch、不 eligible、unknown/stale
required fact 或 store unavailable 均 fail closed。前端不能提交 Model、Provider、Endpoint、
Profile、adapter 或 fallback 值；display name、`latest`、环境默认值和旧 runtime `MODEL_*`
配置都不是 authority。

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

### 5.3 首次 identity、授权与 snapshot bootstrap

首次请求不能依赖预置最终调用 grant，也不能先读受保护 Model facts 再倒推授权。顺序固定为：

1. authenticate principal，建立 trusted `(namespace, security_domain)`，在内存中完成 bounded
   request/canonicalization validation；此时无 Platform identity、Model read 或 provider effect；
2. 按第 7 节先查 scoped key，再按命中记录或新 claim 解析 exact idempotency pepper version；
   命中时恢复原 identity/state，禁止生成新 identity、重新申请授权或 dispatch；仅未命中者
   进入 atomic first-writer claim；
3. winning writer 由 server mint context、首个 turn、invocation 和 snapshot candidate IDs，
   在一个 Draft Assistance transaction 中持久登记 context/turn roots、idempotency claim、
   `AUTHORIZATION_PENDING` invocation shell、exact profile revision reference 和 request target；
4. 从已持久 typed values 构造并完整校验 `REQUEST_DRAFT_ASSISTANCE` exact target，向现有
   Authority 提交带唯一 `authorization_request_id` 的正式请求；Authority 独立持久决定；
5. 恢复/回调按该 request ID 读取 exact 决定并以 CAS 绑定。deny/expired/revoked 追加
   `REJECTED`，不读取 Model facts；allow 才进入下一步；
6. 从 server-owned profile envelope 构造包含预分配 invocation/snapshot candidate 和 exact
   Model refs 的 `INVOKE_MODEL` target，执行 typed parse、scope/purpose/format/digest equality
   validation 后，提交第二个唯一 authorization request；禁止 wildcard、prefix、display name、
   `latest` 或 fixture grant；
7. allow 后才调用 Model Governance exact resolver；将 readback 与 target envelope、profile
   high-water、lifecycle 和所有 digest 做完整比较。通过后在 Draft Assistance transaction 中
   固化 snapshot、两个 decision refs 和 `REQUESTED`；失败则 `FAILED_PRE_DISPATCH`；
8. 只有 durable `REQUESTED` 后才可进入第 9.2 节的 Resource Use/credential/dispatch 顺序。

两个 authorization request 都是幂等 owner 操作：同 request ID 只能返回原决定；timeout/crash
保持 `AUTHORIZATION_PENDING` 并查询原 request，不生成替代 request。Draft Assistance 只保存
decision reference 和 allowlisted decision metadata，Authority 仍是唯一 decision owner。
context/turn/invocation shell 的创建只登记待授权 identity，不授予 read、Model lookup、secret
resolution 或 dispatch。这样首次调用无需循环授权，也不需要 wildcard 或 fixture 预置最终 grant。

若未来需要 service-workload identity 的第二授权，必须单独扩展；本候选不假定完整 workload
IAM 已存在。

### 5.4 异步授权、无正文恢复与当前权限 admission

raw request content 不持久化，因此 authorization callback 晚于原 HTTP 连接或服务重启时，
durable allow decision/snapshot 不能自行恢复正文，也不能自行 dispatch。若原受控内存中的正文
仍存在，可继续同一 invocation；否则 projection 为 `REQUESTED_AWAITING_CONTENT`，向已通过
读取/披露授权的调用方返回 `CONTENT_RESUBMISSION_REQUIRED`，不返回原正文。

浏览器恢复首次 dispatch 必须重新提交原 scoped idempotency key 和完整正文。trusted server：

1. authenticate 并用 scoped key 找到原 claim；在披露 invocation ID/state 前，对 exact
   `READ_DRAFT_ASSISTANCE_INVOCATION` target 做**当前**授权检查；HMAC match 或同一 initiating
   principal 都不蕴含 READ grant，deny 使用 non-enumerating 响应；
2. 用 claim 记录的 pepper/canonicalization version 对重交正文重算 commitment；必须 constant-time
   等于原 commitment。mismatch、pepper unavailable/window expired 均零 state change/dispatch；
3. 验证原 context 未 expired/abandoned、原 turn/version 仍是 current writable generation，且
   request 的 expected version 与 claim 完全相同；已产生 successor、用户已编辑到新 generation
   或 context 不活跃时追加/返回 `STALE_DRAFT_VERSION`，不得把旧正文 dispatch；
4. 重新读 exact snapshot refs 和 Model Governance 当前 eligibility/high-water。然后调用 Authority
   对原 `REQUEST_DRAFT_ASSISTANCE` 与 `INVOKE_MODEL` request/decision refs 执行
   `validate-current-and-admit`：在同一 Authority serialization 中检查两者的 exact subject/scope/
   action/target、grant identity、expiry、revocation 和 decision version，并返回 bound、短期、
   single-use `dispatch_admission_id/fence`；这不是新的 authorization request，也不能换 target；
5. 只有步骤 1-4 成功，且 required Resource Use/budget gates 已 durable，才可解析 provider
   credential。Draft Assistance 随后以 invocation 唯一约束和 expected state/version 对 admission
   做 CAS；winning writer 提交 `DISPATCH_RECORDED` 后才调用 sealed transport；
6. 并发重交只有一个 CAS winner。loser 读取 winner state：若仍未记录 dispatch 且 admission lease
   已安全过期，可从步骤 4 获取同一原决定下的新 admission；若已存在 `DISPATCH_RECORDED`，只能
   返回原 identity/state 或 observe 原 correlation，永不因 replay 再调用 provider。

唯一 dispatch admission 的 key 是 exact `invocation_id`，并绑定 snapshot digest、turn/version、
两个 authorization decision versions、eligibility high-water、Resource Use admission reference、
budget snapshot 和 expiry。admission 超时且 `DISPATCH_RECORDED` 不存在时可安全重新 admission；一旦
dispatch fact 存在，即使尚不确定 socket write，也进入第 6 节 unknown/observation 语义。

“不重新授权申请”只禁止创建替代 request ID 或把旧 key 变成新 invocation；它不跳过 current
authorization。撤销与 dispatch admission 的线性化点是 Authority 的
`validate-current-and-admit` transaction：revocation/expiry 先线性化则 admission deny、零 credential
resolution/provider call；admission 先线性化则该单次短期 admission 可以继续，之后的 revocation
阻止新 admission/successor，但不能撤回已批准或已发生的外部效果。binding eligibility 也固定在
该 admission 引用的 current high-water；其后变化不改写原 fact，只阻止后续 admission。平台不据此
宣称 provider effect 可撤销或 exactly-once。

## 6. Invocation state、dispatch、取消和恢复

state 由 append-only facts 的 versioned reducer 得出；调用方不能直接设置 state。完整允许
转移如下：

| 当前状态 | 合法输入 | 下一状态 | 精确规则 |
| --- | --- | --- | --- |
| none | winning scoped idempotency claim | `AUTHORIZATION_PENDING` | 同 transaction 登记 context/turn/invocation shell；无 protected lookup/dispatch |
| `AUTHORIZATION_PENDING` | exact request/model decision deny、expired 或 revoked-before-use | `REJECTED` | disclosure-safe terminal；零 provider credential resolver/dispatch |
| `AUTHORIZATION_PENDING` | 两个 exact allow decisions + exact Model readback/snapshot commit，且原正文仍在受控内存 | `REQUESTED` | snapshot、decision refs、claim 与 request durable 后才成立 |
| `AUTHORIZATION_PENDING` / recovered `REQUESTED` | allow/snapshot 已 durable，但服务无原正文 | `REQUESTED_AWAITING_CONTENT` | 返回 `CONTENT_RESUBMISSION_REQUIRED` 前必须有 current READ grant；不自动 dispatch |
| `REQUESTED_AWAITING_CONTENT` | same-key正文重交、原 commitment/current turn/current admission checks 均通过 | `REQUESTED` | 只恢复原 invocation；不同正文或 stale generation 不改变原 dispatch state |
| `AUTHORIZATION_PENDING` | binding/store/pepper/decision recovery 无法安全完成 | 保持原状态或 `FAILED_PRE_DISPATCH` | 可查询原 request；不得换 request ID 或 dispatch |
| `REQUESTED` | current grant/binding、required Resource Use/budget、unique admission 和 credential resolution 成功，dispatch fact CAS commit | `DISPATCH_RECORDED` | commit 在 transport 前；只表示进入不可安全重派边界 |
| `REQUESTED` | pre-dispatch authority/binding/budget/Resource Use/credential failure | `FAILED_PRE_DISPATCH` | terminal no-effect；修复后只能显式 successor |
| `DISPATCH_RECORDED` | 同步 authoritative success/failure response | `SUCCEEDED` / `FAILED` | 可跳过 `ACCEPTED/RUNNING`；response 必须通过 schema/identity validation |
| `DISPATCH_RECORDED` | authoritative acceptance/progress | `ACCEPTED` / `RUNNING` | observation 不能证明业务成功 |
| `DISPATCH_RECORDED` / `ACCEPTED` / `RUNNING` | timeout、disconnect、crash gap 或 ambiguous transport | `OUTCOME_UNKNOWN` | 不自动重派；只能 observe 原 correlation |
| non-terminal dispatch state / `OUTCOME_UNKNOWN` | unique authoritative observation | `ACCEPTED` / `RUNNING` / `SUCCEEDED` / `FAILED` / `CANCELLATION_CONFIRMED` | UNKNOWN 可被原调用的后续权威 observation 收敛 |
| non-terminal dispatch state / `OUTCOME_UNKNOWN` | Human cancel request | `CANCELLATION_REQUESTED` | 追加 intent；page close/fetch abort 不算 cancel |
| `CANCELLATION_REQUESTED` | authoritative cancellation effective confirmation | `CANCELLATION_CONFIRMED` | 未确认则保持 requested/unknown；不得宣称已取消 |
| `CANCELLATION_REQUESTED` | authoritative success/failure occurred before cancellation became effective | `SUCCEEDED` / `FAILED` | provider causal sequence 决定；取消意图不覆盖已完成效果 |
| `CANCELLATION_REQUESTED` | progress、timeout 或无 authoritative cancel confirmation | 保持 `CANCELLATION_REQUESTED`，并保留独立 observed/unknown flag | 不重派、不伪造 confirmed；继续 observe 原 correlation |
| recoverable terminal or `OUTCOME_UNKNOWN` | explicit Human-visible retry with a new scoped key | original unchanged + new successor `AUTHORIZATION_PENDING` | 新 invocation、新 turn generation、新 snapshot/decisions；无自动 dispatch |
| any original state | late result/observation for original correlation | 只更新原 invocation | 永不写 successor；正文交付仍受 live channel/version gate |

重复 observation 以 `(provider_correlation, observation_id, observation_kind/version)` 唯一；完全
相同内容为 idempotent no-op。相同唯一键但不同内容、不同 authoritative terminal 或无法确定
success 与 cancellation 的 provider causal order 时，追加 `TERMINAL_CONFLICT` integrity fact，
保留此前 facts，不用到达顺序覆盖；projection 为 `CONFLICT_REVIEW_REQUIRED`，禁止自动 successor
或业务成功推断。已确定 terminal 只允许完全重复 observation 和 non-state completion refs；不能
回退到 RUNNING/UNKNOWN。

`DISPATCH_RECORDED` 后即使 crash 发生在 socket write 前也保守进入/保持 unknown，不自动重派。
refresh/restart 只按 provider 的受信 observation/correlation 能力 re-observe 原 invocation；无法
证明则保持 unknown。late result 只有在仍活跃、同 principal/scope、同 context lease、同 exact
turn version 的浏览器响应通道才可接收正文；否则解析后立即丢弃正文并记录
`RESULT_CONTENT_NOT_RETAINED`。

provider exactly-once 不作承诺。若 provider 支持 native idempotency key，可传递受控值并保存
opaque correlation，但平台最多声明 crash-safe identity reuse、no-automatic-redispatch 和
at-least-once observation ingestion，不能提升为 exactly-once effect。

### 6.1 稳定错误分类

| Reason code | 外部调用可能性 | 恢复语义 |
| --- | --- | --- |
| `DRAFT_ASSISTANCE_AUTHORIZATION_DENIED` | `NO` | disclosure-safe terminal rejection；新授权后显式新请求 |
| `MODEL_BINDING_NOT_ELIGIBLE` / `MODEL_BINDING_MISMATCH` | `NO` | 修正 server-owned profile/successor 后显式新请求 |
| `IDEMPOTENCY_PAYLOAD_MISMATCH` | `NO` | fail closed；不能换 payload 复用 key |
| `IDEMPOTENCY_REPLAY_UNVERIFIABLE` | `NO` | 不 dispatch；Human 可显式创建 successor |
| `IDEMPOTENCY_REPLAY_WINDOW_EXPIRED` | `NO` | key tombstone 禁止复用；新动作必须使用新 key/successor |
| `CONTENT_RESUBMISSION_REQUIRED` | `NO` | 通过 current READ grant 后重交 same key/body；平台不能恢复正文 |
| `DISPATCH_ADMISSION_DENIED` / `DISPATCH_ADMISSION_EXPIRED` | `NO` | 原 identity 保留；不得解析 provider credential；显式 successor 仍需独立授权 |
| `SECRET_REFERENCE_UNAVAILABLE` / `CREDENTIAL_RESOLUTION_FAILED` | `NO` | 原 invocation 终止于 pre-dispatch failure；修复后 successor |
| `PROVIDER_RATE_LIMITED` / `PROVIDER_UNAVAILABLE` | 只有 provider 权威响应可证明 `YES` | 记录 failed 与 retry-after（若 allowlisted）；不自动 retry |
| `PROVIDER_TIMEOUT` / `TRANSPORT_AMBIGUOUS` | `UNKNOWN` | `OUTCOME_UNKNOWN`；re-observe，否则显式 successor |
| `PROVIDER_RESPONSE_INVALID` / `OUTPUT_SCHEMA_INVALID` | `YES` | 技术调用可完成但无可用草稿；正文丢弃，显式 successor |
| `STALE_DRAFT_VERSION` / `CONTEXT_EXPIRED` | 已完成的原调用不变 | 不交付/覆盖内容；只更新原 invocation metadata |
| `RESULT_CONTENT_NOT_RETAINED` | 原调用可能已成功 | metadata 可查询，正文不可恢复；只能显式 successor |
| `TERMINAL_CONFLICT` | 原调用可能已有外部效果 | 保留所有 facts，projection 为 review required；不覆盖、不自动重派 |
| `RESOURCE_USE_COMPLETION_PENDING` / `EVIDENCE_APPEND_PENDING` | 原调用状态不变 | 只补记对应 owner fact/reference；禁止 provider dispatch |

HTTP/status 文案由 backend versioned mapping 产生，不能包含 provider body、endpoint secret、
foreign existence 或 stack。`FAILED` 只用于存在权威 failure/validation result 的情况；无法
证明终态时必须使用 `OUTCOME_UNKNOWN`。

## 7. 无 raw 内容条件下的 idempotency

普通 SHA-256 或可读摘要会让低熵业务文本可被离线猜测，因此禁止把 raw payload、普通
payload digest、可搜索摘要或 embedding 持久化。推荐使用受信服务端的 versioned keyed
commitment：

```text
payload_commitment = HMAC-SHA-256(
  pepper[idempotency_pepper_version],
  length_prefixed(
    domain_separator || canonicalization_version || namespace || security_domain ||
    authenticated_principal_id || action || scoped_idempotency_key ||
    parent_kind(FIRST | EXISTING_TURN) || optional_parent_context_id ||
    optional_parent_turn_id || expected_parent_version || exact bounded request fields
  )
)
```

server-minted context/turn/invocation/snapshot ID 不进入首次请求 commitment，否则会形成“先有
identity 才能查 key”的循环；已有 turn 请求则显式携带并绑定 parent identity/version。
canonicalization 必须是版本化、无歧义的 typed encoding（含字段标签、长度和 absent/null 区分），
不能依赖 JSON key 顺序、locale 或展示文本。

精确查找/竞争规则为：

1. scoped key 唯一域是 `(namespace, security_domain, authenticated_principal_id, action,
   scoped_idempotency_key)`；authenticate、scope 与 bounded request validation 后，先查 claim，
   不先生成 Platform identity；
2. 命中 claim 时解析记录的 exact pepper version、重算 commitment：相同仅证明请求 payload 与原
   claim 一致；返回 identity/state 前仍需 exact current READ/disclosure authorization。通过后返回
   原 identity/state，不创建新 authorization request 或 dispatch；不同则
   `IDEMPOTENCY_PAYLOAD_MISMATCH`；
3. 未命中时解析当前 active pepper version、计算 commitment，再生成 candidate IDs，并以唯一域
   做单 transaction compare-and-insert。并发只有一名 writer 获胜；loser 丢弃 candidate IDs、
   读取 winner，并按步骤 2 比较；不得留下 orphan identity；
4. authorization deny/pre-dispatch failure 仍保留 claim 和原 invocation。相同 replay 返回原拒绝/
   failure；权限后来变化不会使旧 key dispatch。重新尝试必须显式新 key/successor；
5. claim 固定 `created_at`、`replay_not_after`、algorithm/canonicalization/pepper version。窗口内
   exact pepper version 必须可解析；不可用时 `IDEMPOTENCY_REPLAY_UNVERIFIABLE` 且零 dispatch；
6. 到达 `replay_not_after` 后，key tombstone 仍禁止复用并返回 `IDEMPOTENCY_REPLAY_WINDOW_EXPIRED`；
   无需为过期 replay 解析 pepper，也不能把相同 key 当新请求。pepper 只有在引用它的所有窗口
   关闭且 secret governance/hold 允许后才可销毁；rotation 只影响新 claim；
7. replay 时正文已丢弃，只有 current READ grant 才返回 allowlisted metadata 和
   `RESULT_CONTENT_NOT_RETAINED`/`CONTENT_RESUBMISSION_REQUIRED`；不能重建响应。若尚未越过
   `DISPATCH_RECORDED`，可按第 5.4 节重交原正文争取唯一 admission；越过后 replay 永不 dispatch。

idempotency pepper resolver 与 provider credential resolver 是两个 purpose-scoped port。pepper
resolver 可在 authenticated trusted service、validated scope/request 后且在 invocation grant 前
使用，唯一效果是计算/验证 commitment；它不能返回 provider credential 或读取 Model protected
facts。provider credential resolver 必须等到 exact `INVOKE_MODEL` allow decision、snapshot
readback、durable `REQUESTED`、required Resource Use root/budget checks 全部通过后才可调用；它
只能把 credential 临时交给 sealed transport，不能用于 HMAC。任一 resolver 的 grant、reference、
cache 或成功均不蕴含另一个 resolver 的权限。

数据库只保存 commitment、algorithm/canonicalization version 和 pepper reference identity/version，
不保存 pepper。commitment 不进入 frontend、Evidence、Resource Use、日志或错误文本。HMAC 只
降低离线猜测风险，不是加密、内容恢复、语义证明或长期 Evidence；内存、swap、crash dump、
APM 和 provider transport 仍是残余暴露面，G1 必须验证禁采样、禁 body logging、bounded
buffers 和 error normalization。

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

### 9.2 Invocation、Resource Use 与 Evidence 的提交和恢复

三个 owner 不共享跨域 transaction，也不 dual-write 对方事实。application coordinator 只保存
流程 obligation/reference；每个 owner 继续通过自己的 typed port、transaction 和 sole writer
提交。所有跨 owner 命令均带由 server 从 exact invocation/observation 生成的 deterministic
`write_operation_id`，目标 owner 对该 ID 实施 same-payload idempotency、different-payload
conflict。固定顺序为：

| 阶段 | 唯一 writer / durable fact | 下一步 gate 与部分失败恢复 |
| --- | --- | --- |
| A | Draft Assistance：context/turn/invocation shell、claims、decision refs、snapshot、`REQUESTED` 和条件性 `resource_use_required` / `evidence_required` obligations | commit 前无下游写入；恢复只读原 invocation 并继续缺失 obligation |
| B | Execution（仅 04A 已接受/启用）：创建 exact invocation context 的 Resource Use root 和 pre-dispatch admission fact | required write 失败则 Draft 追加 `FAILED_PRE_DISPATCH`，零 credential/provider call；重试同 operation ID 不生成第二 use |
| C | Model Governance current eligibility readback；Authority 对原 decision 执行 current grant/revocation/expiry 的 linearized single-use admission；provider credential resolver；Draft Assistance CAS 提交 `DISPATCH_RECORDED` | 任一检查/resolver/CAS 失败均不得调用 provider；只有 dispatch fact winner 可进入 D |
| D | provider transport；Draft Assistance 追加 authoritative/unknown observation 和 reduced invocation state | crash/timeout 按第 6 节 observe 原 correlation；不得重新执行 B/C/D 的 provider dispatch |
| E | Execution（若启用）按 exact observation operation ID 追加 use outcome/measurement fact | 失败只产生 `RESOURCE_USE_COMPLETION_PENDING` obligation；重放 Execution write，不改变 invocation、不调用 provider |
| F | Evidence owner（仅 04B 已接受/启用）按 `(schema_version, invocation_id, observation_id)` 追加一份 allowlisted Evidence | 失败只产生 `EVIDENCE_APPEND_PENDING` obligation；相同 payload 返回原 Evidence ID，不生成重复 Evidence |
| G | Execution 追加 Evidence reference（若 E/F 均存在），Draft Assistance 追加 allowlisted completion refs | 任一 reference 失败仅重放 reference write；Evidence/Resource Use/Invocation facts不回滚、不重建、不重新 dispatch |

若 04A 未接受，A 明确记录 `CANONICAL_MODEL_RESOURCE_USE_NOT_AVAILABLE`，跳过 B/E/G 中的
Execution 写入；若 04B 未接受，记录 `CANONICAL_MODEL_EVIDENCE_NOT_AVAILABLE`，跳过 F 和对应
references。跳过只体现独立 Human 决策的限制，不允许 Draft Assistance 代写替代 Resource Use
或 Evidence。

恢复 worker 只能枚举 durable pending obligations，先验证 invocation identity/scope、目标 schema
version、原 authorization/snapshot refs 和 operation payload commitment，再调用缺失 owner port。
same operation ID/different payload、foreign existing ID、terminal observation conflict 或 unknown
schema 均 fail closed 并进入人工完整性审查。补记可以在 invocation terminal 后发生，但不得改变
provider outcome、重新解析已丢弃 raw content、重新申请调用 grant、重新解析 provider credential
或重新 dispatch provider。

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
| First bootstrap | 首次请求 durable 登记 roots/shell，两个 exact request ID 的 allow 决定恢复后才固化 snapshot/`REQUESTED` | 无循环授权、wildcard/prefix/fixture final grant；deny/crash 不读取 protected Model facts 或 provider credential |
| Identity/owner | restart 后 exact context/turn/invocation/snapshot metadata readback | 无 Attempt/Plan/Run/Problem 伪造；frontend/provider 不能 mint Platform identity；first-request loser 无 orphan IDs |
| Scope/auth | persisted typed values 构造 exact targets；same-key replay经 current READ grant 后披露；原 decision 经 current validate-and-admit | HMAC/same principal 不授予 READ；wrong subject/scope/action/target/format/expiry/revocation 零 credential/provider call |
| Binding | exact Model/Provider/Endpoint/Profile/adapter refs 与 high-water 一致 | latest/name/env/default/fallback 与 digest mismatch fail closed |
| Content | live response形成 clarification 或 editable draft；Human confirm 后才创建 Problem | DB/log/Evidence/trace 无 raw prompt/response/普通 digest；模型不能创建正式对象 |
| Idempotency | 先查 claim；same key/commitment 返回原 identity；并发首次请求只有一个 winner；rotation 后按 stored pepper version 重放 | different payload、pepper unavailable、window expired 均零 dispatch；deny 后同 key 不因新 grant 复活；provider resolver 不能用于 HMAC |
| Content resubmission | async allow/restart 后浏览器重交 same key/body，原 commitment、current turn/version 和 exact snapshot 均通过，仅一个 CAS winner dispatch | 无正文不 dispatch；mismatch/stale/successor/context expired fail closed；`DISPATCH_RECORDED` 后 replay 只 read/observe |
| Current permission | revocation前 linearized admission可完成单次 dispatch；admission ref绑定decision/high-water/expiry | revocation/expiry先发生则零 credential/provider call；不创建替代 authorization request；不宣称撤回已发生 effect |
| Dispatch/recovery | 同步 terminal、UNKNOWN 后 observation、重复 observation均按表收敛 | dispatch≠success；UNKNOWN 不自动重发；相同 observation key 冲突进入 review；late result 不污染 successor |
| Cancel/retry | success/cancel 竞争按 provider causal order；explicit successor 独立授权/identity | 无 causal order 不覆盖 terminal；fetch abort/page close≠confirmed；不复用 key/invocation/snapshot |
| Resource Use | 若 04A 接受，B/E/G 顺序与同 operation ID 补记通过；v1 Attempt 与 v2 context union 正确 | 不 nullable Attempt；旧 reader不推断；sole writer；补记失败不触发 provider |
| Evidence | 若 04B 接受，F/G 顺序、versioned allowlist、same observation replay 返回同 Evidence | Evidence 不推进 state；无 raw/HMAC/secret；partial failure 不双写或重新 dispatch |
| Cross-owner recovery | A-G 任一点 crash 后只完成 durable pending obligations，最终 refs 收敛 | different-payload replay、foreign ID、unknown schema fail closed；无第二 owner、跨域 rollback 或 provider redispatch |
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
