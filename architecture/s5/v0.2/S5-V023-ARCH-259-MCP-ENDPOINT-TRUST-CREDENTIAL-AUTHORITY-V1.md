# S5-V023-ARCH-259 — v0.2.3 MCP 端点、信任与凭据权威 v1

## 1. 决策记录

| 字段 | 值 |
| --- | --- |
| Session / Title | `S5-V023-ARCH-259` / MCP Endpoint, Trust and Credential Authority |
| 权威分类 | `HUMAN_ACCEPTED_WITH_CONSTRAINTS / ARCHITECTURE_AUTHORITY_ONLY` |
| 发布状态 | `REPOSITORY_PUBLICATION_CANDIDATE`; source Session `CLOSED` |
| Durable baseline | commit `3f4aa05f6641aefc15cf5873f1f6ab279f8d13b2`; tree `5ca583f3a239ed3f1d5cdd33d39db7e2d7fbf860`; CI `34032397080 / SUCCESS` |
| 实现授权 | `NO`; arbitrary write、implementation、migration、network/deployment 均未授权 |

本记录专门定义 MCP endpoint/trust/credential，不把 MCP capability、endpoint、
credential 或一次 invocation 合并为同一对象。它复用
[Capability/Knowledge foundation](S5-ARCH-011-PRODUCT-INTENT-DYNAMIC-WORK-ROLE-KNOWLEDGE-CONSUMPTION-BOUNDARY-V1.md)、
[Plan/Attempt foundation](S5-V023-ARCH-208-WORKFLOW-CONTROL-PLAN-APPROVAL-INTERVENTION-PERSISTENCE-V1.md)、
[Evidence read model](S5-ARCH-010-PRODUCTION-EXECUTION-EVIDENCE-SHARED-READ-MODEL-BOUNDARY-V1.md)
与 [Runtime authority](S5-ARCH-019-V023-EXECUTION-RUNTIME-AUTHORITY-V1.md)。

## 2. 问题与 owner

MCP Definition 中嵌入 URL、调用方 headers 或 magic strings，无法形成可审计的
owner approval、platform approval、trust reassessment、credential resolution 或
exact Attempt-bound invocation。Capability domain 拥有 MCP Definition/Revision；
MCP governance domain 拥有 Endpoint、Trust、Discovery 与 Selection facts；
Execution domain 拥有 Attempt-bound invocation。平台拥有 authorization decision，
而 provider/remote endpoint 只拥有 native effect 与 response。

## 3. 身份、绑定与生命周期

- `mcp_endpoint_id` 是独立、scoped、versioned governed identity，具有 owner；
  immutable revision 固定 normalized public HTTPS address、transport limits 与 digest。
- Endpoint activation 同时要求 resource owner 与 platform-admin approval，且两者绑定
  exact endpoint revision/digest、policy revision 与 scope。
- Trust roots 仅为 public roots 或显式批准的 enterprise CA roots。Trust/allowlist
  approval 最长有效 90 天，期满必须 reassess；不得自动续期。
- Credential 通过 provider-neutral `CredentialResolver` 解析；持久化仅保存 Secret
  Reference metadata、resolver/profile identity 与 digest，绝不保存 secret value。
- Discovery Snapshot 固定 endpoint/trust/policy revision、tool schemas、digest、
  observed time 与 expiry；Tool Selection 固定 exact snapshot/tool/schema digest。
- Invocation 固定 Attempt、MCP revision、Endpoint revision、Trust/allowlist approval、
  Credential Reference、Discovery Snapshot、Tool Selection、authorization decision 与
  bounded request digest；禁止 implicit latest。

```text
端点：草稿(DRAFT) → 待审批(PENDING_APPROVAL) → 生效(ACTIVE)
                    → 暂停(SUSPENDED) / 过期(EXPIRED) / 已退役(RETIRED)
发现：已请求 → 已完成 / 失败 / 结果未知 / 已过期
调用：已请求 → 已记录发起 → 已接受 → 执行中 → 成功/失败/取消/结果未知
```

Endpoint、Trust、Credential、Discovery Snapshot、Tool Selection 与 Invocation 是
separate append-only facts；current state 只是 versioned reducer projection。Capability
maturity（例如 endpoint 是否已治理）与一次 execution status 必须分离。

## 4. P1 网络与 side-effect 边界

P1 默认只允许 public HTTPS；private endpoint 需要 explicit enterprise policy，不能
借 localhost、DNS 重绑定、redirect 或代理绕过。DNS resolution、redirect、resolved
address、TLS hostname、certificate chain、trust root、port、content type、body size、
timeout 与 redirect count 必须 bounded 并在 dispatch 前验证。

P1 只授权真实 `READ_ONLY` 或语义明确的 idempotent MCP path；arbitrary write 未授权。
Caller headers、API magic strings、endpoint 返回的身份声明或 URL possession 都不是
authorization authority。ARCH-259 是
[ARCH-263](S5-V023-ARCH-263-SKILL-ATTEMPT-EXECUTOR-SIDE-EFFECT-CONTRACT-V1.md)
和 [ARCH-266](S5-V023-ARCH-266-UNIFIED-ATTEMPT-RESOURCE-USE-MEASUREMENT-AUTHORITY-V1.md)
中 MCP execution 的前置权威。

## 5. Authority boundaries

| 系统 | 权威边界 |
| --- | --- |
| PostgreSQL | Endpoint/approval/trust/allowlist/Secret Reference/discovery/selection/invocation identities、digests、facts、CAS/idempotency |
| Provider/MCP server | native availability、accepted request、effect 与 response；不能决定平台 authorization 或 business success |
| Kubernetes | public Control Plane/workload observed state；不保存 MCP secret 或拥有 endpoint trust |
| Qdrant | 仅 derived Knowledge index；不是 MCP discovery、trust、credential 或 invocation authority |

## 6. 并发、幂等、restart 与 recovery

Endpoint revision、approvals、discovery、selection 与 invocation 用 expected version/CAS
和 scoped idempotency key + canonical digest。相同 replay 返回原 identity/result；digest
mismatch、stale approval、expired trust 或 selection/schema mismatch fail closed。

Invocation identity、claim、exact snapshot 与 `DISPATCH_RECORDED` 必须先 durable，后
调用网络。重启从 PostgreSQL 恢复；对外部结果不能证明时为 `OUTCOME_UNKNOWN`，
不得盲目 redispatch。Retry 创建 successor Attempt 与 Invocation。晚到 response 只能
关联原 Invocation。Exactly-once external effect 不作承诺。

## 7. Authorization、Evidence 与 redaction

Authorization 先于 endpoint lookup、existence、list/count、approval、credential
resolution、discovery、selection、snapshot assembly、Evidence dereference 与 transport。
拒绝使用 non-disclosing `401/404` policy，产生零 resolver/transport 调用，并避免
status、颜色或 timing side channel。

Evidence 只记录 bounded/redacted method/tool、IDs/digests、decision、timing、status、
response digest、error category 与 limitations；不得记录 secret、credential、auth
header、raw request/response、完整 prompt 或 private data。Secret Reference metadata
与 secret value 分离，export/share 重新授权。

## 8. Product/Technical projections 与中文术语

Product View 显示“端点所有者、审批状态、信任有效期、工具、调用是否真实发生、
结果是否已知、限制”；Technical View 显示 exact revisions/digests、resolved network
facts、TLS/trust、resolver reference、discovery high-water、selection、invocation facts
与 Evidence。两者消费同一 backend snapshot，不得 frontend 推断或 synthetic fallback。

MCP Endpoint=`MCP 端点`；Trust Root=`信任根`；Allowlist=`允许清单`；Credential
Resolver=`凭据解析器`；Secret Reference=`密钥引用`；Discovery Snapshot=`发现快照`；
Tool Selection=`工具选择`；Invocation=`调用`；Outcome Unknown=`调用结果未知`。
“调用成功”仅表示技术调用成功，不等于业务目标达成。

## 9. Failure/recovery 与 P1 acceptance

必须拒绝 missing owner/admin approval、approval expiry、untrusted CA、hostname/cert
mismatch、private/reserved target without policy、redirect escape、oversize/timeout、
schema drift、credential disclosure、cross-scope lookup、stale CAS、conflicting replay、
authorization 后置与 dispatch 冒充 success。Failure append typed fact；uncertainty 保持
unknown；恢复 re-observe，不修改历史。

P1 独立验收需要真实 public HTTPS MCP endpoint 和真实 read/idempotent tool，证明双
审批、90-day upper bound、public/enterprise trust、Credential Resolver + Secret
Reference、bounded I/O、exact Attempt binding、persist-before-dispatch、restart/readback、
unknown recovery、zero-call denial、redaction、Product/Technical parity 与无 arbitrary
write。Fixture/mock-only 不满足。

## 10. Rejected/Post-P1、dependency 与 Human constraints

拒绝 embedded credentials、caller-header authorization、implicit latest、unbounded
network I/O、trust-on-first-use、silent fallback、arbitrary write、frontend authority、
exactly-once claim 与 public CRD/API-group change。Private enterprise networking、dynamic
trust federation、general write tools、full IAM/RBAC、HA 与 certification 属于 Post-P1
或单独 gate。

实现顺序依赖 governed MCP definitions、typed endpoint/trust/credential ports、additive
PostgreSQL storage、bounded transport、Attempt executor、Resource Use snapshot、shared
views 与真实 acceptance；这里只定义依赖，不分配 Session。

Human constraints 是：独立 owner-bearing Endpoint；owner + platform-admin 双审批；
public HTTPS 默认；trust/allowlist 最长 90 天；provider-neutral resolver；只存 Secret
Reference；P1 仅真实 read/idempotent path；authorization-before-disclosure。

## 11. Provenance 与 supersession

Source provenance：`S5-V023-ARCHITECTURE-PUBLICATION-AUTHORITY-BUNDLE.md`，
`118730` bytes，`2696` lines，SHA-256
`8570e725c4a43df2d94b2cf59b87cedefd15b9362cba20c4835f495be3ad7420`。ARCH-259
Human Authority Capsule 优先于完整 proposal/review；其中旧 baseline、Human G2
questions、`PROPOSED` 网络/写入选项只作为 provenance。与 Capsule 不一致的宽松
write 或 trust 解释均被 supersede。未发现与其他 Capsule 或既有 accepted
architecture 的实质冲突。
