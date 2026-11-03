# Prototype alignment package 03 — continuous business delivery

Authority: user's 2026-11-03 instruction to complete package 02 and continue
package 03 in dependency order, handling ordinary implementation autonomously.
Depends on the shared workspace changes in package 02 on the current branch.
No reopening of closed 323, no change to 324 business grants, no merge/release.

## G1 implementation plan: exact planning entry and recovery

Current PlanningEntry retains the old PlanningInput when the URL's problem
changes. A failed new read can leave generation enabled against a mismatched
visible target. Fix the view's ownership binding before continuing business
orchestration. Scope: PlanningEntry and focused browser regression tests, using
existing planning-input GET and existing planning invocation POST. No endpoint,
state, persistence, model admission, budget, execution or contract change.

Bind read state to the exact problem parameter, hide obsolete target content,
disable generation while loading/unavailable, permit explicit GET recovery,
show the returned confirmed goal and source, and keep refresh read-only. Reject
an empty problem before issuing a request. Keep all invocation recovery under
PlanningDialogue's existing opaque request identity and admission boundaries.
Test delayed reads, failed reads, explicit GET recovery, problem switching,
source return, input persistence, reload and absence of mutations.

## Remaining sequence

1. Exact target entry and existing source/plan/resource/result readbacks.
2. P04 save/activate/enter-planning orchestration, with separately durable steps,
   fail-stop and unknown recovery. This batch does not claim that orchestration.
3. Continue the original case only after valid scoped identity and actual object
   readback; original supplier-delivery standards and resource versions are preserved.
   The old cost 4-stage/6-task plan is regression only, not this case's Plan.
4. Resource preparation, independent execution grant, traceable run, evaluation
   against the original standards and human business acceptance.

The initial missing-session blocker is now resolved using the existing test
account. Current authenticated readback and UNKNOWN dependencies are documented
in docs/engineering/PROTOTYPE-PACKAGE03-CURRENT-RECOVERY.md. No repeated unknown calls,
new provider costs, fabricated identity or fixture-as-real completion.


## Engineering checkpoint and corrected case binding

The entry ownership fix and its generation/continuation guards are implemented.
Three new browser cases pass, including unavailable read recovery without POST,
same-page target switches with delayed replies, and missing problem context.
Shared and existing history/admission/criteria tests remain part of the evidence.

Further inspection of the complete 324 handoff corrects the package-01 script:
that script incorrectly promoted the old cost regression into the business
acceptance mainline. The 2026-09-22 handoff records supplier-delivery problem
5fe6a7c9-3f92-5a09-bd91-bf3380109087 and six original standards, with planning
invocation f078a876-eef8-4cb5-ae69-83bf6cfccd42 OUTCOME_UNKNOWN and no same-case
Plan. Its single incremental call was used. These are historical code-handoff
facts, not a current live-state certification. A valid scoped session must first
read back the current problem/request. If it remains unknown, supplier-verifiable
result/usage and formal recovery basis are required; login alone cannot permit
retry or create a new allowance. Do not substitute the cost Plan or fixture.

Full save/activate/planning orchestration and real business acceptance remain
open; this checkpoint is not completion of package 03. Existing 323/324 sessions,
grants, UNKNOWN records and budget reservations are unchanged.

## 效果图一致性交付门槛

自2026年11月3日起，本节为本包必须通过的完成条件。适用于本包全部交付页面和关键状态，不以公共样式接入、代表页截图、构建或功能测试通过代替。本节优先于此前“已完成”等阶段描述；历史工程成果保留。

1. 逐页绑定已核定的效果图版本、文件与SHA256、页面路由和范围；记录实际源码版本、运行环境、视口、缩放、数据及交互状态。以原图尺寸进行同条件对照，并检查适用的缩放和窄屏状态。
2. 每页提供效果图、实际页面截图及并排对照；弹窗、Tab、悬浮、筛选、钻取、加载、空态、失败、权限等适用状态提供对应截图或操作证据。测试数据须标明，不能充当真实业务验收。
3. 逐项核对布局（区域、尺寸、间距、字体、密度）、色彩（主题、背景、边框、语义色）、图标（形状、尺寸、位置、语义）、图表（类型、配色、坐标轴、单位、图例、标签、提示、筛选和钻取）、交互（入口、反馈、状态转换、键盘焦点）。无图表等不适用项必须写理由，不能留空或默认为通过。
4. 每项记录通过、未通过、待核对或不适用，并链接证据；差异登记责任人、修正动作、依赖和复核结果。未通过、待核对、缺证据项均不得计入完成。修正后须重拍、复核受影响页面与共享组件，不能仅修改状态。
5. 动态文本和日期的排除项需明确说明；缺少原图的状态按已批准交互要求及公共规范补齐并标明设计来源。普通实现问题自行修正；涉及设计变更、矛盾基线、范围取舍或用户最终视觉接受时集中提交决策。执行者不能自行豁免差异。
6. 本包完成须同时满足原功能验收、上述全范围视觉与交互核对、差异关闭及适用的业务接受。工程实现、视觉核验、用户接受、合并和部署分别记账。视觉未达标继续修正，不能推到最后一包再算本包完成。

每包交付必含：页面与状态覆盖清单、原图与实页并排对照、五项核对台账、差异修正与复核记录、源码和部署身份、阶段结论。使用《12-每包效果图一致性核对模板.csv》逐页逐状态登记，按图表或复杂交互需要拆行；模板空白不代表验收通过。

普通问题由执行者处理，仅在阶段成果完成或确需用户登录、授权、设计或范围决策时集中汇报。阻塞不影响的工作继续，保持原UNKNOWN和授权边界。

执行台账与对照模板：/Users/tristan/Documents/Codex/2026-11-03/d/outputs/原型对齐交付任务包/。本计划旧工程完成描述不代表新增门槛已通过。

## Current-state audit and read-only recovery UI, 2026-11-03

User explicitly requests checking the supplier case and UNKNOWN recovery basis,
without retrying unknown calls; ordinary development continues independently.
Existing demo324 test credentials may be retained privately and reused under
user instruction. No new account or permission is needed for login itself.
Never place passwords, session cookies or CSRF tokens in deliverables or Git.

Read-only host diagnostics use a direct connection with server-enforced
transaction_read_only=on, repeatable-read and rollback, scoped to this case and
its original ledger. This is technical evidence, not an authenticated business
projection. Existing nonce/password login and normal BFF GETs separately verify
current user access. No provider endpoint, new invocation, settlement, allowance,
account generation or business migration is invoked by this audit.

The broader source checkpoint and current technical snapshot identify TWO
same-case records: the 20th provider timeout and the 21st claimed invocation
without durable terminal result or provider receipt. Previous package handoffs
that only described the 20th record are incomplete and must be supplemented.
Both are still unresolved; no same-case proposal/Plan exists. Existing original
8, cumulative20 and cumulative21 records are distinct immutable facts.

G1 UI implementation: add explicit GET-only original-record recovery and a
status-specific explanation for provider UNKNOWN versus absent durable terminal
result. Keep recovery distinct from retry/continue; display exact original
invocation and source. Bind displayed responses to their request/invocation URL
locator, reject a readback belonging to another problem, and disable all writes
while a requested record is unread or mismatched. No new owner/API/persistence
or recovery adjudication semantics. Tests verify repeated GET/reload with zero
POST, unavailable read, stale locator, mismatched problem and original UNKNOWN
preservation. Retain existing admission and history tests.

Also finish the previously blocked isolated PostgreSQL shared-lock/successor
checks in a new disposable tmpfs container. Do not run fixtures against the
business database. This is engineering verification, not permission for a 22nd
real call or proof of zero supplier usage for the 21st record.

## G1 P04 bounded save-and-enter-planning composition

Implement one primary action to save a Human-evaluated criterion and its set,
fresh-read their exact association, activate a DRAFT problem if required, and
open planning. Existing save-only action remains a secondary compatibility path;
existing lifecycle/API contracts and independent durable steps are unchanged.
This action does not invoke a model, prepare execution or start a run. Every
failed, ambiguous, stale, unreadable or identity/input-changed step stops; an
already saved criterion/set remains saved and is not rolled back or recreated.
Permission/UNKNOWN recovery resumes only the frozen save command; it does not
automatically resume the planning composition. New composer input during saving
must be retained and stop navigation/activation. Tests retain the old save-only
zero-activation assertions and add normal, denied, ambiguous and new-input cases.

The workspace now contains a separately authored package-02 visual completion
gate. Preserve that uncommitted user change; do not stage or overwrite it. New
package-03 screenshots and page/state ledger must distinguish component review,
whole-page visual acceptance, business acceptance and deployment.


## User standing dev/test authorization and current checkpoint

The user explicitly approved the nine exact READ permissions, then authorized
retaining/reusing test credentials and handling routine dev/test read, model,
needed quota and execution approvals without repeated per-item questions.
Use the existing account/owner mechanisms, precise scopes, immutable records and
current limits; do not claim that a chat approval is already a persisted
allowance, supplier observation or business acceptance. No model was dispatched
in this stage. The original USD10 cap and all UNKNOWN reservations are intact.

Normal existing-issuer approval was mechanically submitted on the user's
explicit decision; current original BFF GETs now succeed. Current invocation20
and21 are separately UNKNOWN, no same-case proposal/Plan. The original login and
read-permission blockers are resolved. Prior source notes limited to20 are
historical and superseded by the current two-record verification, not rewritten.

The independent recovery UI and bounded save-and-plan composition are implemented
and tested. This is an engineering checkpoint, not full-page or business
acceptance. See the current recovery document for remaining additive recovery/
follow-up design. The separately authored package02 visual gate is preserved.
