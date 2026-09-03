# S5-V023-CONTROL-254 — v0.2.3 P1 Core Capability and Business Assembly Baseline

## Decision record

| Field | Value |
| --- | --- |
| Session | `S5-V023-CONTROL-254` |
| Type | `CONTROL / PRODUCT_DELIVERY_GOVERNANCE` |
| Checkpoint | `A — NAMESPACE_RECONCILIATION_AND_EXECUTION_BASELINE` |
| Predecessor | `S5-V023-CONTROL-214` — immutable historical authority |
| Human product decision | `APPROVED` |
| Durable main inspected | `a77733fd7560067fbf201c1e2f177a2665c8b030` |
| Durable main tree | `29c092f2591a48b6bc6fecc1011c0e9fbe76d04e` |
| Exact-main CI | `33782464121 / push / attempt 1 / SUCCESS` |
| Contract status | Internal delivery-control baseline; not a frozen public Contract |
| Allowed result | `V0_2_3_P1_CORE_CAPABILITY_AND_BUSINESS_ASSEMBLY_CONTROL_READY_FOR_HUMAN_CHECKPOINT_A` |

This successor preserves CONTROL-214 and its REL-226 integration as read-only
historical authority. It narrows the executable v0.2.3 P1 route around two
mandatory stages: independently complete every core managed capability, then
assemble the accepted capabilities around a real Business Problem. It changes
no Product code, API, migration, Runtime, provider, deployment, release, CI, or
historical Evidence.

## Entry reconciliation and provenance

The fresh global audit found suffix `254` unused in repository content and
history, formal local/remote refs, branches, tags, worktrees, GitHub PRs and
Issues, and visible active/archived task records. The newly created candidate
task is the allocation event; exactly one identifier is allocated:
`S5-V023-CONTROL-254`.

| Required authority or work | Durable result at entry | Control interpretation |
| --- | --- | --- |
| CONTROL-214 / REL-226 | PR #142; merge `7c377ac40286236753d986ac4d5c867cc2a36a31`; ancestor of main | Durable, closed, immutable |
| IMPL-240 / REL-227 | PR #143; merge `7977f860c1ca494a663632f579e258e4558518f3`; ancestor of main | Workflow-control application foundation durable; capability acceptance not granted |
| IMPL-244 / REL-245 | PR #144; merge/current main `a77733fd7560067fbf201c1e2f177a2665c8b030` | Knowledge managed lifecycle, real Qdrant retrieval, deterministic citation, and exact Attempt/Digital Employee binding are durable; Product Workbench, P1 consumption and independent local Product acceptance are not granted |
| IMPL-253 | Active Product Experience writer from durable predecessor main; frontend-only declared path family | Sole active heavy writer; no overlap with this document/Registry path set |
| Open PRs | None at entry audit | No competing PR path ownership found |

Exact-main CI run `33782464121` completed successfully with mandatory jobs
`Quality Gates`, `Frontend Quality Gates`, and `Agent Workbench Browser
Acceptance` all successful. Durable ancestry is established by the ordered
main history `7c377ac` → `7977f86` → `a77733f`.

The execution-plan convention does not mandate a per-document index update.
The exact owned path set is therefore this new document and
`docs/governance/REGISTRY.md` only. IMPL-253 owns frontend implementation,
tests, design and visual Evidence paths; it does not own either path here.

## P1 delivery model

### P1-A — Independent core capability completeness

Each of the following must pass its own bounded local acceptance before P1-B
may be claimed complete:

1. Digital Employee;
2. Skill;
3. MCP;
4. Knowledge;
5. Workflow;
6. Runtime;
7. unified lifecycle and Attempt resource-use facts; and
8. Chinese-first managed-capability Product surfaces.

An incremental visual or read-only assembly design may proceed earlier, but it
is not P1-A or P1-B acceptance.

### P1-B — Digital Employee business-problem assembly

```text
Business Problem
→ Success Criteria
→ Digital Employee
→ governed resource assembly
→ Workflow / Plan
→ Human approval
→ Run / Task Run / Attempt
→ real Skill, MCP and Knowledge use
→ real Runtime
→ Evidence
→ Outcome
```

P1-B consumes accepted P1-A authority. It cannot create demo-only authority,
infer use from configuration, or manufacture success in the frontend.

## Complete Level-1 / Level-2 capability matrix

The status column describes the strongest durable implementation claim at the
entry commit. `PARTIAL` is never an acceptance result.

| L1 | Required Level-2 baseline | Durable status | Missing acceptance boundary |
| --- | --- | --- | --- |
| Business Problem and Success Criteria | identity; title, description, context; owning scope and actor; explicit criteria; controlled revision history; lifecycle; recommended/selected Digital Employee; exact Plan, Workflow Run, Evidence and Outcome relationships; close/reopen/follow-up; history/related work; Chinese-first surface | `PARTIAL / AUTHORITY_NOT_PROVEN_COMPLETE` — planning and workflow foundations exist, but the complete authoritative Product object and relationship set is not established | Read-only reconciliation first. If existing contracts, API and persistence do not authoritatively represent every fact, stop for bounded G2; frontend-only fields are prohibited |
| Digital Employee | Definition creation; role/responsibility; instructions/business boundary; applicable problems; capability requirements; immutable revision/digest; validation; Human review; publication; suspension/deactivation/archive; exact Skill/MCP/Knowledge/Workflow/Runtime Profile bindings; assembly validation; eligible-revision instantiation; Assignment; Placement; active/paused/unavailable/retired states; current work/Run/Task/Attempt; pending intervention; recent Evidence/Outcome; actual-use history; restart readback; isolation; Chinese-first list/detail/assembly/history | `API_ASSEMBLED / PARTIAL` — durable Definition/template, Instance, Assignment, Placement services and API/bootstrap foundations exist | Complete lifecycle, assembly validation, work/history projections, real execution participation, isolation and local Product acceptance remain unproven |
| Skill | Definition; input/output schemas; dependency/execution boundary; revision/digest; validation; Human review; publication; deactivate/archive; exact Digital Employee and Workflow/Plan bindings; approved deterministic real Skill; Attempt-bound invocation; real input/output; duration/state; Evidence; failure; timeout; replay/idempotency; restart readback; isolation; recent use; Chinese-first surface | `FOUNDATION_COMPLETE / PARTIAL` — managed Skill definitions/projections exist | No complete durable Attempt-bound real invocation, operational semantics, full UI or independent acceptance is proven |
| MCP | Definition; approved callable endpoint; ownership; identity/version; transport; trust; credentials/minimum permission; connectivity validation; initialize; tools/list; tool schema; governed selection; exact Digital Employee and Workflow/Plan bindings; bounded read-only real invocation; Attempt relation; result/duration/state/Evidence; timeout; unavailable; refusal; restart/readback; Chinese-first endpoint/tool surface | `FOUNDATION_COMPLETE / BLOCKED_FOR_REAL_ENDPOINT_AUTHORITY` — bounded MCP management/protocol work exists | A fixture, embedded/spike/synthetic or arbitrary endpoint cannot pass. Route G2 first if endpoint ownership, trust, credentials or invocation authority is unresolved |
| Knowledge | Source; Collection; Document; immutable revision/digest; ingestion; indexing; exact active snapshot; validation; Human review; publication; Digital Employee and Workflow/Plan bindings; real Qdrant retrieval; Attempt relation; deterministic citation/readback; Evidence; no-result; stale/unavailable; revision/snapshot conflict rejection; restart; denial-before-lookup isolation; update/reindex/archive; Chinese-first management/retrieval | `REAL_DATA_PROVEN / DURABLE_BACKEND` — PR #144 durably establishes the managed lifecycle, snapshot-filtered real Qdrant retrieval, deterministic citation and exact Attempt/Digital Employee binding | Knowledge Product Workbench, P1 Product consumption and capability-specific independent local Product acceptance remain pending |
| Workflow | Definition creation; title/purpose/business boundary; immutable revision/digest; ordered steps; I/O mapping; basic conditions; exact Skill/MCP/Knowledge/Runtime and Digital Employee bindings; validation; Human review; publication; execution snapshot; Plan and exact revision/digest; approval/rejection; real Run/Task Run/Attempt; waiting/running/waiting-for-human/completed/failed/cancelled; pause; bounded correction; immutable successor; approve-and-continue; retry; cancel; Evidence linkage; terminal-only Outcome; restart; deterministic replay/conflict rejection; Chinese-first Definition/Execution/Intervention Workbench | `APPLICATION_COMPLETE / PARTIAL` — durable persistence, atomic Unit of Work, successor/Evidence/Outcome contract, and 11-command application foundation exist | Control API/bootstrap, complete Definition lifecycle/resource binding, real execution effects, Product UI and local acceptance remain required |
| Runtime | approved type; exact identity; Profile; provider selection; startup; readiness; execution; observation; stop/shutdown; restart readback; Instance/Placement and Attempt relations; failure/unavailable; Evidence; one real executable P1 path; Chinese-first availability | `APPLICATION_COMPLETE / PARTIAL` — Native continuity and Native/OpenClaw provider/profile foundations exist | One approved real end-to-end Runtime path and truthful status for the other provider, exact execution relationships, Evidence and local Product acceptance remain unproven |
| Unified managed-resource lifecycle | canonical vocabulary: 草稿, 待验证, 已验证, 待审阅, 已发布, 已绑定, 已选择, 已调用, 已成功, 已失败, 暂不可用, 已停用, 已归档, 等待人工, 规划中; exact per-kind applicability | `PARTIAL` — several domain enums and frontend mappings exist | Backend-authoritative cross-resource mapping, applicability table and exhaustive UI mapping remain absent; health/actions must not be projected onto non-Runtime resources |
| Unified Attempt resource use | Digital Employee; optional Agent; Workflow; Skill; MCP endpoint/tool; Knowledge revision/snapshot; Runtime; Assignment; Placement; exact versions/revisions/digests; selected vs invoked; state/duration; bounded I/O; Evidence; Outcome contribution; failure/recovery | `PARTIAL` — Knowledge use and execution identities have bounded projections | One authoritative unified projection and Business Problem right-side panel remain missing; configured/bound never implies selected/invoked |
| Product Experience | Chinese-first shell; business home; Business Problem workspace; Digital Employee, Skill, MCP, Knowledge, Workflow and Runtime management; Evidence Inspector; Outcome; work history; desktop and 390px; keyboard focus; loading/empty/unavailable/failed/planned; Product/Technical disclosure | `ACTIVE / NOT_DURABLE` under IMPL-253 for P1-V1 paths only | IMPL-253 cannot absorb all feature Workbenches. Serialize feature UI tasks after its visual checkpoint and reuse its accepted shared system |
| Outcome | Business Problem and Success Criteria relationships; terminal basis; findings; actions; exact Evidence; Digital Employee; actual resource use; intervention history; criterion evaluation; unresolved risks; follow-up; export/share boundary; Chinese-first explanation | `FOUNDATION_COMPLETE / PARTIAL` — terminal-only Outcome and Evidence rules exist | Complete business projection, criterion evaluation, resource-use summary, Product UI and acceptance are missing |

### Required distinctions

Every implementation and Product surface must preserve:

- Definition != Instance != Assignment != Placement;
- resource exists != published != bound != selected != invoked != succeeded;
- Agent != Runtime != Model;
- Runtime desired state != observed state;
- Knowledge SQL lifecycle authority != derived Qdrant index;
- a technical terminal state != a business Outcome.

## Missing-capability and critical-path matrix

| Capability | Primary missing work | Blocking dependency | Earliest independent gate |
| --- | --- | --- | --- |
| Business authority | prove or decide authoritative Business Problem/criteria representation | read-only authority audit; possible G2 | Before P1-B implementation |
| Digital Employee | complete lifecycle/assembly/history and real execution participation | stable bindings, Workflow and Runtime facts | P1-A/DE |
| Skill | durable real invocation with replay, errors and Evidence | unified Attempt identity/projection | P1-A/SKILL |
| MCP | approved endpoint/trust/credential authority and real call | G2 before implementation when unresolved | P1-A/MCP |
| Knowledge | add the Product Workbench and P1 Product consumption around the durable managed lifecycle and retrieval authority | PR #144 durable main, stable shared UI | P1-A/KNOWLEDGE |
| Workflow | Definition completeness, API/bootstrap, real effects and Workbench | durable control application, capability/runtime bindings | P1-A/WORKFLOW |
| Runtime | minimum real executable assembly and truthful alternate provider | exact Attempt/Placement, approved provider path | P1-A/RUNTIME |
| Unified lifecycle/use | canonical backend mappings and one read model | stable domain facts from all capability owners | P1-A/UNIFIED |
| Product surfaces | serialized feature Workbenches | accepted IMPL-253 shared foundation | P1-A/UX |
| Outcome | business projection and criterion assessment | unified resource use and terminal Workflow | Before P1-B acceptance |

Critical path:

```text
authority audits/G2 where required
→ stable shared Product foundation
→ backend capability completion
→ serialized capability Workbenches
→ independent ACCEPT gates
→ governed P1 data/bootstrap
→ P1-B ASSEMBLY
→ local clickable ACCEPT
```

## Canonical lifecycle vocabulary

| Product label | Canonical fact | Applies to |
| --- | --- | --- |
| 草稿 / 待验证 / 已验证 / 待审阅 / 已发布 | revision-governed lifecycle facts | Definitions and versioned managed resources where the domain supports the transition |
| 已绑定 | exact persisted binding | bindable resources only |
| 已选择 | exact Plan/selection record | resources selected for execution |
| 已调用 / 已成功 / 已失败 | exact invocation/execution record | Attempt-used Skill, MCP, Knowledge and Runtime effects |
| 暂不可用 | authoritative health/readiness/error fact | resources with an availability contract; never inferred from CSS |
| 已停用 / 已归档 | controlled lifecycle transition | applicable managed resource kinds |
| 等待人工 | authoritative Workflow/Intervention state | Plan/Run/Task/Attempt requiring Human action |
| 规划中 | explicit future/non-current state | unavailable planned Product entry only |

Each downstream design must publish an applicability table mapping stored/API
values to these labels. Unknown values fail safe and retain the exact raw value
in Technical detail.

## Required downstream task routing matrix

Identifiers below are deliberately not allocated. Each row requires a fresh
collision audit at activation.

| # | Required task | Type / proposed owner | Dependencies | Changed-path family | Gate | Heavy writer / parallel rule | Required evidence | Stop conditions | Completion claim boundary |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Business Problem and Success Criteria authority reconciliation | `ARCH` or read-only `CONTROL`; Product/domain architecture owner | current contracts/source/ADRs | architecture/authority evidence only | G2 if authority absent | No; parallel read-only | field-by-field authority map and alternatives | missing authoritative representation or cross-plane conflict | decision/audit only; no implementation |
| 2 | Digital Employee complete lifecycle and capability assembly | `IMPL`; Digital Employee backend owner | task 1 decision where referenced; durable DE foundations | backend domain/repository/service/tests | G1; G2 on lifecycle/Instance redesign | Yes; max two | persistence, restart, isolation, exact bindings, real participation | public/lifecycle/tenant architecture change | backend capability only |
| 3 | Digital Employee Management Workbench | `IMPL`; Product UI owner | 2 and accepted shared UI | DE frontend/tests/browser Evidence | G1 | Yes; serialize with shared frontend ownership | desktop/390px, real API states, keyboard | frontend-inferred authority or overlap | UI available; not independent acceptance |
| 4 | Skill managed capability and real Attempt invocation | `IMPL`; capability backend owner | stable Attempt/use model | Skill service/repository/execution/tests | G1; G2 on contract/authority change | Yes; parallel only if paths disjoint | real deterministic call, restart, denial, timeout/failure, replay, Evidence | fixture-only success or frozen-contract change | Skill backend real-use proof |
| 5 | Skill Management Workbench | `IMPL`; Product UI owner | 4 and shared UI | Skill frontend/tests/browser Evidence | G1 | Yes; serialized UI | lifecycle and invocation/history states at both viewports | invented state or path collision | UI available only |
| 6 | Approved MCP endpoint/trust/invocation architecture | `ARCH`; security/capability architecture owner | endpoint candidate and threat/credential analysis | architecture/ADR/evidence | G2 | No; parallel read-only | owner, version, transport, trust, credential, permission and cleanup decision | no approved callable endpoint or unresolved secret authority | architecture authority only |
| 7 | MCP endpoint, discovery and real Attempt invocation | `IMPL`; capability backend owner | 6 accepted and durable; stable Attempt/use model | MCP service/repository/invocation/tests | G1 behind approved contract | Yes | initialize/list/schema, authorized read-only call, Evidence, timeout/refusal/restart | fixture/synthetic/arbitrary endpoint; secret exposure | MCP backend real-use proof |
| 8 | MCP Endpoint and Tool Management Workbench | `IMPL`; Product UI owner | 7 and shared UI | MCP frontend/tests/browser Evidence | G1 | Yes; serialized UI | real endpoint/tool/status/result and negative states | fabricated connectivity/call success | UI available only |
| 9 | Knowledge durable integration and Product consumption | `IMPL`; Knowledge/Product owner | PR #144 durable lifecycle/retrieval authority; stable UI | Knowledge Product API/frontend/tests | G1 | Yes; avoid IMPL-253 overlap | real Workbench consumption of exact durable revision/snapshot/citation facts, browser negatives and local readback | duplicate retrieval authority, Qdrant-as-authority or frontend-manufactured lifecycle | Product consumption candidate; independent acceptance still required |
| 10 | Workflow Definition completeness reconciliation | read-only `CONTROL`/`ARCH`; Workflow architecture owner | current CRD/internal definitions/ADRs | audit/evidence | G2 if representation/lifecycle change needed | No | required-field authority and gap map | CRD/frozen Contract change | audit/decision only |
| 11 | Workflow Definition lifecycle and resource binding | `IMPL`; Workflow backend owner | 10 disposition; capability identities | Workflow domain/repository/tests | G1 or G2 per 10 | Yes | immutable revisions/digests, review/publication and exact bindings | unauthorized Workflow semantic/CRD change | Definition backend only |
| 12 | Workflow Control API/bootstrap and execution assembly | `IMPL`; Workflow application/API owner | durable IMPL-240; 11; runtime/capability paths | backend API/bootstrap/integration tests | G1 | Yes | exact commands, real Run/Task/Attempt, replay/conflict/restart | demo-only authority or effect-before-persist | API/execution assembly only |
| 13 | Workflow Definition/Execution/Intervention Workbench | `IMPL`; Product UI owner | 11–12 and shared UI | Workflow frontend/tests/browser Evidence | G1 | Yes; serialized UI | real lifecycle, execution, Human actions and failures | local-only state or path overlap | UI available only |
| 14 | Runtime minimum real-execution assembly | `IMPL`; Runtime/Control owner | Attempt/Placement and one approved provider | runtime/operator/backend integration/tests | G1; G2 on lifecycle change | Yes | startup/readiness/execute/observe/stop/restart/Evidence | provider test only, provider identity collapse | one bounded real Runtime path |
| 15 | Managed-resource lifecycle/state vocabulary | `IMPL`; shared backend/frontend contract owner | stable per-domain facts | shared DTO/mapping/frontend/tests | G1; G2 if public contract changed | Yes; serialize shared files | applicability table, exhaustive mappings, raw fallback | frontend becomes authority | mapping foundation only |
| 16 | Unified Attempt resource-use projection | `IMPL`; execution read-model owner | 4, 7, 9, 12, 14 facts | backend projection/API/tests | G1; G2 on ownership change | Yes | selected/invoked distinctions, versions, durations, Evidence/Outcome links | cross-plane authority or inferred use | authoritative projection only |
| 17 | Outcome business projection | `IMPL`; Workflow/Product owner | terminal Workflow, 16, Business authority | backend projection/API/frontend/tests | G1 | Yes | criterion evaluation, Evidence/resource/intervention links, truthful partial failure | nonterminal Outcome or fabricated business result | bounded Outcome capability |
| 18 | P1 real governed data/bootstrap | `ASSEMBLY`; integration-data owner | completed APIs for all P1-A candidates | bootstrap/config/integration fixtures explicitly approved for setup | G1 | Yes; after APIs stabilize | authoritative create/readback manifest and owned cleanup | fake success, v0.2.2 state reuse, uncontrolled external data | reusable local acceptance data only |
| 19 | Capability-specific local ACCEPT tasks | `ACCEPT`; independent acceptance owner per capability | corresponding candidate and real services | Evidence/reports only | G0 | No; may parallel if environments isolated | real-browser/API proof, negatives, restart, isolation, cleanup | fixture-created success or shared-resource collision | one named P1-A capability accepted |
| 20 | P1 Business Assembly | `ASSEMBLY`; cross-domain integration owner | all eight P1-A gates accepted | minimal integration/bootstrap/Evidence paths | G1; G2 on discovered authority gap | Yes; serialize after capability acceptance | exact end-to-end identities and real effects | any P1-A gate absent or demo authority needed | assembled candidate; not Product acceptance |
| 21 | P1 local clickable Product Acceptance | `ACCEPT`; independent Product acceptance owner | 20, exact services/build/data | acceptance Evidence/screenshots/reports | G0 | No | complete Chinese-first desktop/390px journey, restart, cleanup, limitations | fabricated state, unavailable real service, provenance mismatch | local P1-B acceptance only; no Preview/release |

## Two-writer concurrency and integration plan

Maximum heavy repository writers: **2**.

At this baseline IMPL-253 occupies writer slot 1. Slot 2 is unoccupied after
the durable Knowledge integration. This CONTROL documentation is not a heavy
writer and touches no Product path. The next backend task may use slot 2 only
after its fresh ownership audit. A second frontend task must wait until
IMPL-253 reaches its accepted visual checkpoint and releases or explicitly
shares its path family.

Read-only authority audits for Business Problem, Skill executable candidates,
MCP endpoint/trust, Workflow Definition/API, Digital Employee completeness,
and acceptance-data design may proceed concurrently. Durable integrations are
serialized. After each integration: fetch main, reconcile PRs, refresh only
affected branches, run complete validation, obtain exact-head CI, and repeat
routing.

## Incremental local acceptance plan

| Checkpoint | Required content | Required local proof | Claim limit |
| --- | --- | --- | --- |
| P1-V1 | global Product shell; business home; Business Problem workspace; truthful Digital Employee/resource panel | real services/data plus desktop and 390px screenshots | visual/information foundation only |
| P1-V2 | Digital Employee, Skill, MCP, Knowledge, Workflow and Runtime management surfaces | authoritative lifecycle/availability states, negative states, browser operation | surfaces available; no capability accepted without its backend gate |
| P1-V3 | Attempt-bound Skill/MCP/Knowledge use; Workflow execution; Evidence; basic intervention; Outcome | real calls/execution, exact identities and Evidence, restart readback | integrated candidate only |
| P1-B | complete Business Problem-to-Outcome journey | all P1-A acceptance records plus local clickable Chinese-first journey | bounded local Product acceptance only |

Use task types `ASSEMBLY` and `ACCEPT`; do not allocate a `DEMO` task type.
Every checkpoint states limitations and performs owned-resource cleanup.

## Independent P1-A acceptance gates

Each gate must independently prove authoritative state, exact identities and
revisions, restart readback where applicable, isolation, truthful negative
states, no fixture-created success, owned cleanup, and clickable local Evidence
when a Product surface applies.

| Gate | Passing proof |
| --- | --- |
| Digital Employee | complete managed lifecycle, assembly, Instance/Assignment/Placement, real work participation and Product history |
| Skill | governed published revision plus real Attempt-bound input/output invocation, duration/state, Evidence and negatives |
| MCP | approved real endpoint, initialize/discovery/schema, governed selection and bounded real Attempt call with refusal/unavailable/timeout proof |
| Knowledge | durable lifecycle, exact snapshot, real Qdrant retrieval, deterministic citation/Evidence, denial-before-lookup and conflict/stale/no-result proof |
| Workflow | complete Definition/Plan lifecycle, exact bindings, real hierarchy/effects, intervention/correction/replay, terminal Outcome and Workbench |
| Runtime | approved exact provider/Profile, lifecycle and observation, real Attempt execution, Evidence and truthful alternate-provider status |
| Unified facts | authoritative lifecycle mappings and unified selected/invoked resource-use projection |
| Chinese-first Product | complete applicable management surfaces, desktop/390px, keyboard and all truth states |

## P1-B assembly acceptance

The one coherent real-data journey must:

1. create or select an authoritative Business Problem and explicit Success Criteria;
2. select an eligible published Digital Employee Definition and create/select its real Instance;
3. confirm Assignment and Placement;
4. bind exact Skill, MCP, Knowledge, Workflow and Runtime revisions;
5. validate assembly completeness and create an exact immutable Plan;
6. obtain Human approval before effects;
7. create real Workflow Run, Task Run and Attempt identities;
8. invoke a real Skill and approved MCP tool, retrieve real Knowledge, and execute through a real Runtime;
9. show actual—not merely configured—resource use in the workspace panel;
10. create exact Evidence, perform one bounded Human Intervention, and continue or complete;
11. create a terminal Outcome and evaluate every Success Criterion;
12. prove restart readback and provide a local clickable Chinese-first demonstration.

All facts originate through authoritative APIs, persistence or an approved
bootstrap path. No hard-coded frontend state or fabricated success is allowed.

## P2 deferred advanced scope

P2 owns advanced orchestration and operations only: multiple Skill/MCP calls
in one Run; dynamic capability/tool selection; complex branching; multi-level
approval; resource replacement and automatic recovery; cross-provider
scheduling; advanced retry/rerun; complex compensation; fleet operations;
expanded operations/cost views; arbitrary graphs; deep nesting; large dynamic
fan-out/fan-in; calendar scheduling; cross-region migration; exactly-once
external effects; complete BPMN compatibility; and Workflow Marketplace.

Basic Skill, MCP and Workflow completeness is P1-A and cannot be deferred to
P2.

## Prohibited scope and claims

This CONTROL does not authorize Product implementation, provider work,
deployment, Preview, Formal Release, Golden Demo, full Agent Fleet, merge of
`release/v0.2.2-maintenance`, PR #136 or PR #138, port 18080, attempt-06, or
reuse of v0.2.2 fixture/fake state. It does not reopen or amend CONTROL-214.

At Checkpoint A do not claim downstream implementation, P1, Product
Experience, Digital Employee, Skill, MCP, Workflow or Runtime complete;
Knowledge complete merely because PR #144 is durable; Golden Demo; Public
Preview; Formal Release; certification; or production readiness.

## Recommended next executable routing

No downstream identifier is allocated here. Subject to a fresh collision and
ownership audit, recommend next:

1. the read-only Business Problem/Success Criteria authority reconciliation;
2. the read-only MCP endpoint/trust/invocation architecture discovery, routing
   a bounded G2 decision if authority remains unresolved; and
3. at most one backend heavy writer in slot 2, preferably Knowledge Product
   Workbench/P1 consumption because its managed lifecycle and retrieval
   authority are now durable on main.

Do not start another frontend writer while IMPL-253 owns the shared Product
surface. Do not start P1-B acceptance until all P1-A gates are accepted.

## Closure and supersession

This document supersedes CONTROL-214 only for the forward P1 capability and
business-assembly execution baseline. CONTROL-214 and REL-226 remain immutable
historical authority and provenance. Any conflict with their durable facts is
an escalation, not permission to rewrite them.

The CONTROL-254 local branch and Draft PR are non-durable candidate authority.
Only a separate Human-authorized Final Integration Routing and REL session may
integrate it. No implementation task may treat this baseline as durable until
that succeeds. Human Checkpoint A may grant only:

```text
PASS /
V0_2_3_P1_CORE_CAPABILITY_AND_BUSINESS_ASSEMBLY_CONTROL_READY_FOR_HUMAN_CHECKPOINT_A
```
