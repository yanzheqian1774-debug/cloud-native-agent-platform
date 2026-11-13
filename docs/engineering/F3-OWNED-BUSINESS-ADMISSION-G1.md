G1 proposal — owned new business work, bounded exact sources/resources
2026-11-13. Source review only. No implementation/deployment/DB/model action.

Verified obstruction
- conversation_experience_admission.py ExperiencePolicy.conversations is a 1..2
  dictionary. v3 ownedConversationUnderstanding admits ownership-verified chats,
  but prepare stores GENERAL_CONVERSATION_UNDERSTANDING and
  owned_understanding_policy_digest. It does not create business authority.
- ConversationWorkAuthorization._draft rejects that marker for normal drafts;
  when C2 resolver is present it delegates to AdoptionOrigin.business_source.
- understanding_adoption_origin.py business_source requires the oldest context
  to lack the owned marker AND its conversation to be in the old named dictionary.
  Therefore an actual C2 adoption rooted in any new ordinary chat still fails.
- ConversationPlanningAdmission.require_source enforces the same named-origin
  gate. Current history resolver intentionally mirrors that business-origin gate.
- AutomationPolicy.work requires an exact problem reference and source digest.
  ReadonlyContinuationPolicy.work likewise requires exact problem, subject,
  sourceContentDigest and expiry. Merely admitting CREATE would stop downstream.
Root's current safe-policy review: reviewer324/human:demo323-approver,
ownedUnderstanding=true, same allowance, only two old document chats; current
readonly policy also contains exact existing works. This is an actual complete-chain
restriction, not a model inability or just a missing UI selector.

Boundary
Do not relabel or modify original GENERAL contexts. Keep C1/C2 model schema,
profile digests, old contexts, UNKNOWN, ledgers and prior problem objects intact.
The new authorization is a separate, immutable business-scope decision based on
an actual ready task and currently authorized exact data/resource references.
New conversation/problem IDs are output identities, not the business perimeter.
Greeting/direct answer/missing source never obtains business authority.

Standing policy successor (default off)
A separate server-side owned-business policy, leaving ExperiencePolicy v3 intact:
- exact tenant/domain/subject/account; current root/C2 profile/config identifiers;
- existing ledger+allowance+fixed deadline, no new cap/account/budget;
- explicit business cases and exact approved source revisions/content digests;
- exact already-approved published capability/employee/skill/runtime/document-rule
  references and operation/effect limits, plus provenance of their standing approval;
- readonly/externalWrites=false, same Native agent/runtime/operation boundaries.
Publication or READ alone is not USE/START permission. Sources/resources lacking
actual standing execution authorization are ineligible. Start with the proven
existing document scope. Sales is included only if root can identify its existing
exact authorization, not inferred from the enum or the user's general request.
No conversation allowlist, arbitrary resource prefix, model-selected authority,
new approver role, or silent promotion of any catalogue entry.

One durable business authorization
Recommended: small internal append-only authorization_admin.business_work_admissions
(+ append-only revocations) migration, default-off, current owners issue grants.
Reasons not to overload existing tables:
- context_call_requests is immutable and first_invocation_id is UNIQUE; inventing
  a new context for the same invocation either rewrites history or violates it.
- context_call_decisions is the latest call-lease resolver; inserting another kind
  of decision there could accidentally alter understanding admission/expiry.
- context_call_objects already supplies exact actual problem->invocation binding
  but cannot carry the source/policy/resources decision payload and revocation.
- prepared_resource_commands is a different owner; do not hide business authority
  in its arbitrary JSON receipts just because the columns fit.
Reuse grant_requests/decisions/grants/audit, creator receipts, context_call_objects,
C2 result_adoptions and existing budgets. Only the bounded business fact/revocation
needs new persistence; no public CRD, model result schema or frozen execution enum.
Root must reserve migration number before implementation (0065 is C2's, not reused).

Admission evidence and idempotency
Under established account/conversation/context lock order, re-read:
1. active ordinary session/account, own nonarchived chat and actual user message;
2. exact primary SUCCEEDED/DRAFT_READY or canonical real C2 adoption ancestry;
   original/result IDs, turn/version/commitments, retained result and settled usage;
3. actual selected source with current exact READ and approved revision/content hash;
4. uniquely matching standing business scope, exact allowed resource/operation proof;
5. current policy digest, generation, allowance identity/expiry and revocation state.
Record a canonical immutable decision digest and idempotency key derived from scope,
subject, actual ready invocation/version/commitment, source and policy scope.
No copying model output into a fake primary invocation. Ambiguous matches, missing
source, stale result, changed profile, unrelated/greeting or unresolved predecessor
fail closed without another model call. A source change needs a new explicit saved
answer/source transition and new exact fact, not mutation of the original.
CREATE continues through ConversationWorkAuthorization and the existing owner.
The resulting problem/revision is bound by existing context_call_objects in the
creator transaction to the actual invocation. The immutable admission is looked up
by that exact binding, not by latest chat/task. Same request replay must read the
same creator receipt; no new business object or permission from a new arbitrary key.

Full chain adapters (must all be included before claiming ready)
A. CREATE/criteria/activation: primary and C2 origin resolver accept either legacy
   named business origin or a valid exact new business admission. Existing exact
   grant request/decision and owner CRUD checks remain. No global business LIST.
B. Planning: use the same admission and exact problem binding, preserve source
   equality/preflight/shared allowance and unresolved-call safeguards; include exact
   PLAN READ needed by streaming. No special planning profile/second understanding.
C. Resource preparation: derive a per-problem WorkScope only from the persisted
   bounded admission; exact selected source + permitted capability/resource tuple.
   Still use existing select/test/publish/use grant owners, no arbitrary catalogue
   resources or newly synthesized capabilities treated as approved.
D. Readonly execution: derive a per-problem ReadonlyWork from that same fact,
   including original exact documentRules/native agent/case/source digest/expiry.
   Prepared plan/task/runtime digest must fit that tuple. Existing exact START,
   participant USE, runtime checks and worker startup provenance remain mandatory;
   new run is still created by the real execution owner, never an old UNKNOWN replay.
E. History and C2: centralized business-origin resolver supports exact original and
   adopted results; history mode may renew prior READ only, never USE/START. Current
   runtime dispatch still rechecks revocation/current permissions. Archived/foreign
   chat or changed source/profile cannot bootstrap a new admission from a receipt.
F. Results: actual new problem/run messages return to its original chat; unrelated
   questions preserve the task/head. Readonly observation of old history remains
   separate from permission for future dispatch.

Revocation and expiry
Each consumption checks current policy, account, business admission revocation and
exact grants. Revoking a parent/origin blocks new child business use, planning,
resource consumption and START; no new key can bypass it. Expiry never resets quota.
Historical READ uses its own retained-view rule; a business revoke must not silently
manufacture a READ renewal, nor erase existing immutable facts. Old UNKNOWN budgets
and receipts remain unresolved, never reset or reissued by this feature.

Phased implementation and evidence (one deliverable, no false partial completion)
1. Policy + immutable owner + primary/C2 exact resolver + create/plan tests.
2. Resource/readonly adapters + exact grant/worker compatibility; this is still a
   blocking dependency, not deferred while declaring new chat business support.
3. History/clarification/result return and browser/full owner integration.
Tests: two unrelated new chat IDs under same scope, actual adoption and primary
DRAFT_READY, missing/foreign source, published-but-unapproved resource, READ-only
without USE, revoked/expired identity/policy, concurrent same-key create, stale
source/profile and old UNKNOWN preservation. Show shared-budget/count invariants,
no greeting business grants, one message/one understanding, current streaming READ,
real new problem/run receipt and original-chat return. Root owns real execution.

Approval boundary
This is a G1 implementation/policy proposal, not a currently granted permission or
migration approval. No need to republish C1/C2 model configs if model schemas remain
unchanged. A frozen public contract change discovered during implementation must be
reported explicitly. The concrete new standing business policy and migration still
need root's normal review/activation; do not label this document HUMAN_REVIEWED.

Important idempotency refinement
Existing context_call_objects uniqueness is by resource, NOT by invocation, so it
alone cannot prevent the same ready result creating two new problems with different
client keys. The new feature must add a one-to-one admission->actual problem binding
(or an equivalent unique admission claim owned by the business creator), atomically
with the creator transaction. Freeze the first actual owner request key and receipt;
replay that key returns its original receipt, a different key for the same admission
is rejected/readback-only. Do not add a global uniqueness constraint to legacy
context_call_objects or reinterpret old business objects. This extra binding is part
of the internal persistence proposal and concurrent/different-key tests, not an
assumption that the current creator already enforces it.

Implementation-read correction: context_call_objects DDL alone is insufficient, but
context_call_admission.bind_problem already locks the exact context and rejects a
second different problem/invocation. BusinessProblemOwnerAdapter invokes binding in
the creator transaction, so this owner protects different-key duplicate creation by
rollback. Prefer this existing binding and verify it with races; do not add a new
binding table unless a concrete remaining gap is demonstrated. 0066 is reserved for
the separate bounded admission/revocation facts, not duplicate creator machinery.
Root approved full A-F implementation, default off, based on e226db0; no actual
configuration, database or model operation is delegated to this worktree.

### Retained-result and host integration refinement

A completed GENERAL understanding call is immutable evidence, not the future
business authorization lifetime. New business admission checks the exact retained
SUCCEEDED/DRAFT_READY result, current goal, C2 actual reference ancestry, exact
current source READ, current account/generation/standing policy and all explicit
context revocations. It does not renew or rewrite the prior model context lease.
The creation transaction uses the same bind_problem owner with an internal exact
retained-authorization callback; one-context/one-problem uniqueness is unchanged.
Planning records the immutable admission ID/digest and the budget guard rechecks
that basis while keeping its original allowance and ledger counters.

BFF and Native host share OwnedBusinessWorkReader. This reader cannot insert an
admission, publish resources, dispatch a model or manufacture a browser session.
The host passes the original persisted command identity through its existing
owner_authority_factory and authorization checks. Current policy, generation,
account, exact problem/result/source/ancestry, READ and revocation are rechecked.
The dispatch effect gate checks the same proof again using its existing connection;
its admission lock is shared with the append-only revocation writer. This adds no
new frozen command kind and does not claim a source READ is runtime USE or START.

Both direct published employee tuple and exact explicit capability binding are
supported: capability is optional, while agent/employee/skill/runtime/operation,
source and document rules remain exact. The historical expired work is scope
evidence only. A new enabled standing policy is a separate current authorization.

Validation so far: 10 pure policy tests passed; the disabled concrete candidate
schema passed without edits. New PostgreSQL owner tests are written but not yet
run. Full resource/worker integration and actual UI are not yet validated.

### Whole-chain authority matrix (implementation checkpoint, not live acceptance)

| Step | Exact decision object / required authority | Authorization basis | Current status / remaining gate |
| --- | --- | --- | --- |
| Ownership / account | Current trusted principal, namespace/domain, active ordinary account and own unarchived conversation | Existing identity owner, current generation | Existing owner retained; new source/standing paths must reject wrong subject and tenant |
| Context and question | Actual message, retained successful invocation, exact current journal goal; C2 original/result/version/source reference chain | Existing understanding/C2 owner and shared model allowance | C2 is installed; business fact path written, still needs isolated combination tests |
| Source discovery | Own conversation plus each source exact revision READ_RESOURCE | Current identity/understanding policy and existing exact resource grant | Separate source-discovery patch under root validation; no global LIST and no new resource authority |
| Source consumption for business | Exact approved synthetic source version/content digest plus current READ | Current standing policy scope plus resource owner | Schema/candidate validated; actual current READ belongs to root live verification |
| Create / plan | Exact CREATE then exact newly bound Problem READ, criteria writes, PLAN PREPARE/READ, exact model INVOKE | New immutable business admission + existing requestability/decision owners | Initial/C2 origin and creation/planning hooks written; different-key uniqueness and retained lease expiry need PG proof |
| Budget | Existing ledger/allowance, current caps/window and reservations | Existing model allowance, original budget owner | No new ledger or cap; planning stores admission reference and guard rechecks it; integrated proof outstanding |
| Resource selection | Exact employee/agent/skill/runtime/knowledge/rule refs and allowed operation; optional exact capability | Existing published owner records plus same standing scope | Peer adapter written with controlled-port checks; actual shared-owner combination outstanding |
| Runtime use / START | Original current resource USE, exact execution START/subject/root/source and effect policy | Existing execution/resource owners, current admission recheck | Never derived from READ; effect-time same-connection hook in peer package; isolated combined effect/revoke proof outstanding |
| Progress / questions | Exact preparation/run/participant historical READ; answering separately rechecks START/USE/owner question/version | Existing progress and interaction owners | READ/runtime split already installed; new admission proof must remain exact without starting a run |
| Result in original conversation | Exact original context/problem/run result, own conversation link and current result READ | Existing result/retention owner and immutable admission lineage | No new delivery identity or generic latest selection; actual end-to-end run/result not yet accepted |
| Expired historical READ | Prior exact READ only, same subject/problem/source/version, no explicit denial/revocation | Existing history-access explicit request + shared read-only lineage reader | New reader path written; repeated expiry/recovery and zero START/model changes require PG proof |

A/B remaining: current standing basis and retained original/C2 scope tests, wrong
identity/archived/source mismatch negatives. E remaining: real shared-owner resource
and effect-time permission/revocation combination. F remaining: original history,
result read and exact proof through worker. Default-off/schema absence and legacy
paths must also remain functional. No entry in this matrix claims that an expired
old work grant is active or that an untested live permission is already present.

### Retained old C2 plus source-body successor (incremental G1)

The current retained NEEDS_DATA and its successor may belong to different
explicitly configured C2 profiles. Source admission resolves every actual
context against the root or configured retained/current adoption admissions;
there is no registry/latest-profile discovery. The writer verifies current
policies and exact configuration under the existing context locks, then freezes
`understandingBindings` in the existing immutable 0066 JSON record (context ID,
configuration, understanding-policy digest and question-only marker). The
standalone host reader matches the actual adoption chain to exactly this frozen
set and rechecks current standing policy, account/generation, READ and explicit
revocation. It does not reinterpret old contexts using the newest profile, renew
an old call lease or turn a general question into a business origin.

Existing newly owned work history also contributes exact PLAN READ and the
bound source KNOWLEDGE READ targets before an execution receipt exists. The
history owner still requires a prior exact READ and rejects revocation/denial;
this is not first access or USE/START renewal. Changes are isolated and untested
at this checkpoint while the coordinator runs the urgent combined hook.

### 文档执行前的资料角色检查（2026-11-13，只读证据复核）

检查对象与检查规范必须分别确认，不能把 POLICY 正文当作 SUBMISSION，
也不能因规则匹配即宣称业务交接完整或实际验证通过。
当前保存的 `document-rule-live-candidate-r1/source.json` 包含两份文档：

- `order-release` / `SUBMISSION`：订单服务生产上线交接说明；同一系统为订单服务、
  同一批次为模拟发布001。唯一上线负责人同时填李明与陈玲，影响范围待确认，
  缺回退章节，验证依据只有 TEST-001 合成记录的文字陈述。
- `production-handover-policy` / `POLICY`：生产环境规范；约束同系统同批次的唯一负责人、
  明确影响范围、回退步骤及触发条件/负责人、验证记录。明确不适用于访谈等其他文档，
  文字存在不证明测试实际通过。

该 JSON 按存储的 canonical JSON 算法得到内容摘要
`f231837aa6f77675069562246ca00ba31fd16a67643483122c0f3851aa14c4eb`，
与 `document-rule-exact-candidate-r1/content.json` 的 production_handover 映射、
当前禁用 standing policy 中 exact sourceContentDigest 一致。
这是保存证据的离线核对，没有查询实时数据库，也没有修改已冻结正文模型候选。

A–F 文档执行验收必须覆盖：仅规范而无对象、仅对象而无可适用规范、两者皆有但范围不符、
多对象尚未明确目标、有效对象与规范齐备。前三种不得产出“交接完整”结论；业务资料缺口
在原会话明确提出，平台资源/规则配置缺口由后台处理，不要求用户填写配置标识。
当前快照两类资料齐备但对象本身存在上述缺陷，缺陷应成为检查结果而非资料加载失败。
现有 deterministic-rule-evaluation 的 CONFLICT/UNKNOWN/MISSING/SATISFIED 与
businessConclusion=UNDETERMINED 可作为预期证据；SATISFIED 仅表示验证记录字段存在。
此条为新增验收要求，尚未宣称 A–F 整链已运行通过。

现有执行侧已具备角色硬门槛：`native_document_tools.validate_source` 要求
2–12 份文档且恰好一份 SUBMISSION，其余只能 POLICY 并须提供有效范围与章节；
`native_document_rule_tools.invoke(review_document)` 再核对象/规范角色和已确认范围与
精确规则绑定相符。本包复用该边界，不另造规则引擎；联合测试与缺口呈现仍需覆盖。

### 原 CREATE 请求只读观察（A–F 增量，无新增存储）

GET `/conversations/{id}/create-status?draftInvocationId=...&requestKey=...`
只服务当前未归档自有会话的 CREATE 阶段与原已保留草案。校验当前 standing、账户、
精确来源 READ、采用谱系、原主体与 journal key；requestKey 必须为原 journey key 的
`:problem`，不能由客户端另选业务对象。进入当前授权 barrier 后复用同事务读取。

返回 NOT_CREATED / CREATED / UNKNOWN，附 draftInvocationId、requestKey、journeyKey、
journalVersion、aggregateVersion。NOT_CREATED 仅表示本次观察无已提交 owner 幂等记录、
creator receipt、上下文对象绑定或派生问题对象；它不授予 CREATE，也不保证并发请求未在途。
CREATED 必须四类事实自洽、原命令摘要相符、真实首版内容相符且当前精确问题 READ 有效，
才附 revision。已有 receipt 到期不抹除历史，但不续 creator 权限。
任意部分事实、摘要/绑定不一致均 UNKNOWN；访问失败/配置未启用/存储失败不表示未创建。

前端明确继续时先 GET，核当前 owner/journal 后 CAS；NOT_CREATED 仍只调用现有 CREATE
并保持原内容与幂等键，所有当前授权重新检查，幂等 owner 处理并发。CREATED 读回同首版
再续原标准阶段；未知只观察。不重新理解、不新造消息、不扩数据或执行权限。
