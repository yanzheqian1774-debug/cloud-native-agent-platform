# S5-V023-ARCH-204 — v0.2.3 Product Workflow, Operations and Fleet-ready Addendum v1

## Decision record

| Field | Value |
| --- | --- |
| Session | `S5-V023-ARCH-204` |
| Gate | `ARCH / G2 / CHECKPOINT_A_CANDIDATE` |
| Durable baseline | merge `caea10abcdd68f28cae9ba81d6ebc81ae8669386`; tree `0376c5ba28b239c978ee4013a1a00b69c5fa8d41`; CI `33715736988 / SUCCESS` |
| Governing baseline | `S5-V023-ARCH-201`, durably integrated by `S5-V023-REL-202` |
| Decision status | `PROPOSED / READY_FOR_HUMAN_CHECKPOINT_A` |
| Contract / release | internal addendum, `NOT_FROZEN`; `NO_PUBLIC_PREVIEW / NO_FORMAL_RELEASE_CLAIM` |

This additive clarification does not modify ARCH-201. It defines Product behavior,
interaction and acceptance boundaries only. It changes no Product code, public CRD,
API group, frozen Contract, database, deployment or v0.2.2 artifact. Every 210–299
identifier below is a candidate routing label: `NOT_ALLOCATED / NOT_RESERVED`.

## 1. Scope and terminology reconciliation

v0.2.3 closes this bounded Product loop:

```text
Digital Employee Definition → Agent/Digital Employee Instance → Assignment
→ approved Plan → Workflow Run → Task Run → Attempt → Placement
→ Native or OpenClaw Runtime → Skill/MCP/Knowledge invocation
→ Events and Evidence → Outcome → Human Intervention
→ immutable corrected successor execution → restart readback, recovery or stop
```

Definitions are immutable published composition intent; Instances are durable
operational identities. Assignment binds approved work to an Instance; Placement
binds an Attempt to a Runtime Instance. Plan is an immutable versioned proposal.
Workflow Run, Task Run and Attempt are distinct. Session is context only.

| Historical track | Current domain | Candidate band |
| --- | --- | --- |
| Capability A — execution authority/persistence | execution application services | 210–219 |
| Capability B — Instances/Assignment/Placement | Digital Employee operations | 220–229 |
| Capability C — Native Runtime | Runtime operations | 230–239 |
| Capability D — OpenClaw adapter | Runtime provider operations | 230–239 |
| Capability E — intervention/successor/resources | Workflow control and invocation | 240–249 |
| Capability F — experience/acceptance | Product assembly and UX | 250–299 |
| Final A — OpenClaw Provider | factory/bootstrap/application adapters | 230–239 |
| Final B — Execution Workbench | Workflow/Intervention experience | 250–259 |
| Final C — Fleet-ready Facts | bounded Runtime Operations foundation | 252 within 250–259 |

Completion in one historical Track proves only its recorded scope: provider-local
execution does not prove Product assembly; UI does not prove authority; typed facts
do not prove a complete fleet manager.

## 2. Workflow Control and Human Intervention

Workflow is a governed Product capability. A Workflow Definition declares reusable
structure. A versioned Plan binds a goal, exact definitions, dependencies, resources
and completion criteria. Approval binds actor, exact revision and digest. A Workflow
Run executes one approved Plan; Task Runs realize nodes; Attempts record individual
executions. Dependency and execution state remain separate. Evidence records facts;
Outcome records the durable result. Correction creates an immutable successor Plan
and, after separate exact approval, a successor Run linked to its predecessor.

| Action | Closed meaning | Identity/result rule |
| --- | --- | --- |
| Pause | quiesce at the next declared safe point | same Run; persisted request before effect |
| Approve/continue | approve exact waiting version/digest | changed content needs new approval |
| Human input | supply schema-bounded gate input | append Evidence; no raw-object edit |
| Resume | continue authoritative paused state | new Attempt only if execution requires it |
| Retry | execute a failed Task Run again | new Attempt; same Run/Plan |
| Rerun | execute an approved Plan again | new linked Workflow Run |
| Correction | change business intent | successor Plan and separately approved Run |
| Compensation | forward action mitigating prior effect | new work; history remains |
| Rollback | restore supported prior Product/configuration | release operation, not correction |
| Cancellation | terminally prevent further target work | no implicit compensation |
| Runtime replacement | authorized compatible Runtime reassignment | preserves Product identity; not retry |

Every Intervention binds actor, target Run/Task Run/Attempt, action type, business
reason, target version, authorization state, lifecycle state
(`REQUESTED/APPLIED/REJECTED/EXPIRED/FAILED`), Evidence, Outcome, timestamps and
optimistic-concurrency identity. Services MUST persist before effect, require
idempotency, reject replay across target/version, detect conflicts and report success
only after authoritative readback. Applied effect and observed Outcome are distinct.

Users can correct intent and request governed actions; they cannot edit PID, container
identity, database rows, Placement, internal Runtime commands or raw execution
objects. SSE/streaming is transport only, never authority.

## 3. Product usability, operability and manageability

| Surface | Usability | Operability | Manageability |
| --- | --- | --- | --- |
| Workflow Workbench | goal, Plan, DAG, hierarchy, correction/follow-up | blockers, timeline, Evidence/Outcome, recovery | approve, pause, input, resume, retry, rerun, cancel |
| Intervention Center | priority, age, owner, pending decision | conflicted/expired/failed and resulting execution | assign, authorize/reject, decision history |
| Digital Employee Management | role, availability, active/recent work | readiness and intervention ownership | Definition/Instance lifecycle, Assignment/bindings |
| Runtime Operations | understandable work readiness | desired/observed, health/readiness/freshness, Placement | supported start/stop/re-observe/replacement |
| Skill/MCP/Knowledge Workbench | discover/select resources | invocation/retrieval health and Evidence | revision, publication, binding, deprecation |
| Product View | business journey and result | truthful partial/stale/disconnected states | business-safe actions only |
| Technical View | exact correlations on demand | diagnosis and re-observation | no direct infrastructure mutation |
| Evidence Inspector | claim-to-event/invocation/citation trace | provenance, gaps and limitations | governed access/retention only |
| Operations Overview / Attention Center | prioritize affected work | cross-Instance freshness/failure | ownership, filtering and action routing |

Normal feedback names persisted state and next action. Failure distinguishes denied,
conflicted, stale, disconnected, unavailable, failed and recovery-required.

## 4. Digital Employee and resource-management model

A Digital Employee Definition is published/versioned composition referencing exact
Agent Definition, organizational role/responsibility, Skill/MCP/Knowledge, workspace,
model, Runtime Profile and policy revisions. A Digital Employee Instance has stable
identity, owner/scope, lifecycle, Assignment history, availability/readiness,
active/recent work, intervention owner, preferences and permitted memory references.
Agent Instance is distinct and binds the exact Agent Definition used for execution.

Assignment records actor, approved Plan/input, target Instance and authorization.
Placement records where an Attempt ran. Binding never grants invocation by itself;
Attempt-scoped authorization remains mandatory. Disclosure progresses
`Business → Operations → Technical → Evidence`; business users need not understand
Kubernetes, containers or provider objects.

### Managed Resource Portfolio and resource-kind semantics

The accepted v0.2.3 foundation term is
`MANAGED_RESOURCE_PORTFOLIO_AND_FLEET_READY_OPERATIONS_FOUNDATION`. It provides a
common discovery and projection envelope without pretending that unlike resources
share one lifecycle. It MUST NOT be described as `UNIVERSAL_RESOURCE_FLEET_COMPLETE`
or `AGENT_FLEET_COMPLETE`.

Every managed-resource projection has a typed `resourceKind`, stable canonical ID,
version/revision where the kind is versioned, owner, organizational scope, lifecycle
authority, policy/authorization references, directed bindings/dependencies,
active/recent usage, Evidence/Outcome links, supported actions, prohibited actions,
restart/readback semantics and links to Product, Operations, Technical and Evidence
projections. Optional fields are omitted or explicitly `NOT_APPLICABLE`; their
absence never means unknown success. Kind-specific repositories and controllers
remain authoritative—the envelope is not a new source of truth.

| Resource kind | Identity/version and lifecycle authority | Availability/health; desired/observed; Placement | Bindings, usage, Evidence/Outcome | Management actions; prohibited/non-applicable | Restart and projections |
| --- | --- | --- | --- | --- | --- |
| Digital Employee Definition | stable Definition ID plus immutable revision/digest; publication lifecycle in domain service | publish/matchability availability; validation status, not Runtime health; desired/observed and Placement N/A | points to exact Agent/Workflow/Skill/MCP/Knowledge/Profile/policy revisions; Instance/Run consumers; review/publication Evidence | draft/validate/review/publish/deprecate; no start/stop/restart/Placement | PostgreSQL readback; Product composition, Operations consumers, Technical revisions, Evidence review |
| Digital Employee Instance | stable Instance ID plus generation/version; Instance lifecycle service | availability/readiness meaningful; desired/observed meaningful; Placement only as execution relationship, not placement of the Definition | exact Definition, Assignment, Runtime/Agent Instance and resource bindings; active/recent Runs; lifecycle/Outcome Evidence | create/assign/enable/disable and governed re-observe/replacement where supported; no revision editing or direct Pod action | durable identity/readback plus Runtime re-observation; all four projections |
| Native Runtime | stable Runtime Instance/provider ID plus desired generation and observed revision; Runtime manager/Kubernetes actual state | health/readiness/freshness and desired/observed meaningful; Placement target | Agent Instance/Attempt/command correlations; active/recent execution; observation/command Evidence and Outcomes | governed start/stop/re-observe/replace where supported; no business-intent correction or direct database edit | reacquire Kubernetes/provider facts; Operations default, Product summary, Technical detail, Evidence facts |
| OpenClaw Runtime | stable Runtime Instance/provider correlation plus exact supported provider version and generation; Runtime manager/provider actual state | health/readiness/freshness and desired/observed meaningful; Placement target | same execution bindings as Native with exact OpenClaw provenance; provider Evidence/Outcome | governed lifecycle actions supported by accepted adapter; no silent Native fallback, provider-version mutation or direct process control | provider re-observation and ambiguity=`RECOVERY_REQUIRED`; all four projections with technical provenance |
| Skill | stable Skill Definition ID plus immutable published revision/digest; Skill lifecycle service | publication/matchability/test status; Runtime health, desired/observed and Placement N/A | capability/MCP bindings and Digital Employee consumers; Attempt invocation usage and Evidence/Outcome | author/validate/test/review/publish/bind/deprecate; no start/stop/restart | PostgreSQL readback; Product catalog, Operations invocation status, Technical manifest, Evidence invocation |
| MCP Server | stable MCP Definition ID plus revision/digest and external endpoint reference; MCP lifecycle service | configured/enabled plus timestamped connection health/freshness; desired/observed only for managed connection configuration; Placement N/A | exposes discovered Capabilities; Skill/employee bindings and Attempt calls; health/invocation Evidence | author/test/discover/review/publish/enable/disable/deprecate; start/stop only if a separately managed Runtime owns it, never inferred here | durable definition/readback and safe external re-probe; four projections with secrets excluded |
| MCP Capability | stable capability identity scoped to exact MCP revision/discovery snapshot; MCP capability authority | callable/compatible status; independent Runtime health, desired/observed and Placement N/A | child of MCP Server; selected by Skill/employee/Attempt; invocation Evidence/Outcome | select/authorize/invoke through governed parent; no server lifecycle, start/stop or independent Placement | rediscover without silently changing identity; Product use, Operations status, Technical schema, Evidence call |
| Knowledge Source | stable Source ID plus immutable configuration/content revision; Knowledge lifecycle service | access/index-input status and freshness; desired index intent may apply, Placement N/A | feeds Collections/index snapshots; employee/Workflow consumers; ingestion/access Evidence | register/validate/review/publish/refresh/deprecate/purge where authorized; no Runtime start/stop | PostgreSQL authority readback; external source revalidation; four projections with minimum disclosure |
| Knowledge Collection | stable Collection/Pack ID plus revision, document versions and index snapshot identity; PostgreSQL authoritative, Qdrant derived | retrieval/index health and freshness; desired index generation/observed snapshot may apply; Placement N/A | Source membership, exact consumer bindings and Attempt retrieval/citation usage; Evidence/Outcome | curate/publish/reindex/deprecate/governed purge; no Runtime replacement/start/stop | durable facts rebuild derived index; Product knowledge view, Operations freshness, Technical snapshot, Evidence citations |
| Workflow Definition | stable Workflow Definition ID plus immutable revision/digest; Workflow lifecycle service | validation/publication availability; execution health, desired/observed and Placement N/A | Plan/Run consumers and exact resource requirements; approval/publication Evidence | author/validate/review/publish/deprecate; no pause/resume/retry/start/stop because those target execution | PostgreSQL readback; Product design, Operations usage, Technical DAG, Evidence approval |
| Workflow Run | stable Run ID bound to exact approved Plan revision/digest; execution service | execution state and attention meaningful; desired/observed applies to governed control intent/effect; Run itself is not a Placement target | Assignment, Task Runs, interventions, resources and Outcome; active until terminal | pause/resume/cancel; rerun creates new Run; correction creates successor; no in-place Plan edit or Runtime replacement without targeted Product action | durable readback/reconciliation; all four projections |
| Task Run | stable Task Run ID within Run and Definition node identity; execution service | dependency/execution state meaningful; desired/observed only for governed task control; not a Placement target | parent Run, Attempts, dependencies and task Outcome/Evidence | cancel where authorized; retry acts by creating Attempt; no rerun identity reuse or direct Runtime control | durable readback; Product hierarchy, Operations blocker, Technical dependency, Evidence task facts |
| Attempt | stable immutable Attempt ID/ordinal; execution service | execution state meaningful; observed Runtime state applies; Placement required for executable Attempts | parent Task Run, Placement, Runtime, invocations, Events, Evidence and Outcome | request cancellation or retry after failure; retry creates successor Attempt; no mutation/rerun/start/stop of the immutable record | durable readback plus Runtime re-observation; all four projections and primary trace anchor |

Applicability is normative: passive definitions and resources MUST NOT acquire
Runtime lifecycle fields or actions merely to fit the envelope. Health means
timestamped operational reachability only for kinds that can be probed; validation,
publication and matchability remain distinct. Desired/observed applies only where a
reconciler or governed control intent exists. Placement applies only to executable
Attempts targeting Runtime Instances, with read-only relationship projections on
Instances and Runs.

The unified Resource Portfolio supports kind, owner, organization/scope, lifecycle,
availability, health/freshness where applicable, policy, binding gap and active/recent
usage filters. Results name the authoritative freshness and limitation and navigate
to the specialized Digital Employee, Runtime, Skill/MCP, Knowledge, Workflow or
execution Workbench. The Portfolio owns neither lifecycle actions nor denormalized
truth.

End-to-end navigation preserves exact canonical IDs and direction:

```text
Digital Employee Definition → Digital Employee Instance → Assignment
→ Workflow Run → Task Run → Attempt → Placement → Runtime Instance
→ Skill/MCP/Knowledge invocation → Evidence → Outcome
```

## 5. Fleet-ready v0.2.3 foundation and v0.2.5 boundary

v0.2.3 defines
`MANAGED_RESOURCE_PORTFOLIO_AND_FLEET_READY_OPERATIONS_FOUNDATION`, never
`UNIVERSAL_RESOURCE_FLEET_COMPLETE` or `AGENT_FLEET_COMPLETE`. Typed facts cover stable Definition/Instance/provider/runtime
identity, owner/scope, Assignment, Placement, desired/observed state, health,
readiness, freshness, lifecycle, active Run/Task Run/Attempt, resource/policy
bindings, last command/outcome, restart/re-observation identity and Evidence/Outcome.

Bounded operations are list/filter and view Instances; compare desired/observed;
inspect health/freshness, Placement/Runtime and recent execution; identify attention;
and, where supported, govern start/stop/re-observe/replacement.

v0.2.5 owns optimization, scaling, HA/failover, multi-cluster/region, disaster
recovery, fleet rolling upgrades, capacity optimization, mass remediation/batch
actions, topology-aware placement, provider certification and complete Fleet Manager.
No new public CRD or API group is introduced.

## 6. Chinese-first Product interaction and visual contract

The journey is `提出业务问题 → 确认系统理解 → 查看拆解 → 审查计划 → 审查数字员工团队
→ 业务修正 → 精确批准 → 观察执行 → 查看证据与结果 → 跟进或重跑`. Chinese is
primary, business meaning precedes detail, and each screen has one primary action.
Use restrained white/near-black/gray/blue and a vertical journey/timeline.

Status pairs text/icon/semantics with color. Require logical keyboard/focus behavior,
44×44 CSS-pixel targets, desktop 1280×720 and mobile 390×844 without horizontal
overflow. Loading, empty, partial, stale, disconnected, denied, failed and recovered
are explicit. There is no fake lifecycle, employee, data or success.

Workflow Workbench includes goal/approved Plan, Run/Task/Attempt, DAG/current position,
timeline, blockers, intervention, before/after correction, Evidence/Outcome, restart
and rerun. Intervention Center includes approvals, paused Runs, failed Attempts,
expired/conflicted requests, owner, priority/age, decision history and successor.

## 7. Skill/MCP/Knowledge capability closure

S5-IMPL-059 is durable at merge `7e9af32…`; it corrected Skill/MCP Workbench status
locator determinism only. It did not add invocation authority.

| Area | Classification | Closure |
| --- | --- | --- |
| Skill discovery/selection | `DURABLY_IMPLEMENTED_NOT_ASSEMBLED` | bind exact resource to Attempt |
| MCP discovery | `DURABLY_IMPLEMENTED_NOT_ASSEMBLED` | move beyond bounded localhost fixture |
| Capability Definition | `PARTIAL` | unify execution capability contract |
| Digital Employee binding | `DURABLY_IMPLEMENTED_NOT_ASSEMBLED` | propagate Instance/Attempt identity |
| Attempt authorization | `MISSING` | authorize before discovery/effect |
| actual Skill/MCP invocation | `PARTIAL` | assemble bounded real invocation into Run |
| result/failure Evidence | `PARTIAL` | canonical Attempt/Outcome linkage |
| Knowledge access/journey | `DURABLY_IMPLEMENTED_NOT_ASSEMBLED` | execution/citation linkage |
| capability matching | `PARTIAL` | assemble published-role selection |
| data discovery | `PARTIAL` | join bounded MCP/Knowledge paths |
| restart/readback | `DURABLY_IMPLEMENTED_NOT_ASSEMBLED` | full execution continuity |
| browser accessibility | `PARTIAL` | responsive keyboard Product loop |

Closure requires exact published revisions, zero calls on denial, Attempt correlation,
real result/failure Evidence, exact Knowledge revision/index/citation, Outcome linkage
and restart readback. UI, preview data and focused tests are insufficient proof.

## 8. Memory, preferences and persistent-state boundaries

| State | Authority / retention | Restart / portability | Mutation, visibility, deletion, audit |
| --- | --- | --- | --- |
| Definition instructions/role | immutable domain PostgreSQL revision | durable; exact-revision portable | Product-visible; successor/deprecate; audited |
| user preferences | scoped typed repository only when implemented | declared scope only | policy-visible; version/delete actions audited |
| Digital Employee memory | separately approved State provider/reference | no cross-app claim | minimum disclosure; explicit retention/deletion audit |
| conversation/session | session provider; non-authoritative | may expire; never rebuilds Run identity | participant-scoped, bounded and logged |
| Workflow/Task/Attempt | PostgreSQL Product history; Kubernetes actual state where applicable | durable readback/re-observation | append/link; retry creates Attempt; audited |
| Runtime-local | provider/Runtime authority | reacquire; portable only by contract | technical-only; never directly edited |
| Skill/MCP/Knowledge | domain PostgreSQL; Qdrant is derived index | durable identity/rebuild | governed revision/deprecation/purge |
| Evidence/Outcome | append-only PostgreSQL execution authority | canonical readback | minimum disclosure; correction appends/links |

No cross-application persistent personal memory is claimed. Secrets stay external.
Deletion cannot silently break Evidence or predecessor/successor integrity.

## 9. Cross-view canonical identity and consistency

Product, Technical and Evidence views project the same Definition/Instance,
Assignment, Plan, Run, Task Run, Attempt, Placement, Runtime, resource invocation,
Intervention, Evidence and Outcome IDs/revisions/digests. No surface silently chooses
`latest`, a similar name or a fixture. `STALE` names observation time/threshold;
`PARTIAL` names missing facts; `UNAVAILABLE` preserves known facts; `DENIED` reveals no
protected existence; `DISCONNECTED` never promotes cache to success. Acceptance
requires byte-equal live-service identities, not labels or a backend/UI shell.

## 10. Scenario Pack, Golden Demo and acceptance matrix

Each real-service scenario records precondition, Product action, authoritative
transition, Evidence, Outcome, feedback, failure and restart/readback (`RR`).

| Scenario | Preconditions/action → transition | Evidence, Outcome, feedback / failure / RR |
| --- | --- | --- |
| 1 Governed happy path | publish/bind; approve exact Plan; execute → terminal hierarchy | approval/provider/resource Evidence and Outcome; mismatch fails closed; RR |
| 2 Pause/decision/resume | active safe point; pause/decide/resume → paused then resumed | actor/reason/version; conflict distinct; RR |
| 3 Business correction | correct predecessor → successor Plan, approval, Run | immutable before/after and Outcome; RR |
| 4 Failed Attempt retry | retry failed Attempt → new Attempt | old failure plus decision/result; old Attempt unchanged; RR |
| 5 Approved Plan rerun | rerun exact approved Plan → new linked Run | comparative Outcome; never reuse ID; RR |
| 6 Denial/conflict | unauthorized/stale request → rejected/conflicted, no effect | zero downstream calls and typed feedback; RR |
| 7 Runtime unavailable | replace or fail safely → new generation or terminal safe state | freshness, command/outcome; no fallback; RR |
| 8 Restart continuity | restart persisted execution → same IDs plus re-observation | recovery identity; ambiguity=`RECOVERY_REQUIRED`; RR is scenario |
| 9 Native execution | real supported Native execute → accepted/running/terminal | exact correlations/Outcome; explicit provider failure; RR |
| 10 OpenClaw execution | accepted exact version execute → accepted/running/terminal | provenance/Outcome; no Native/mock fallback; RR |
| 11 Resource invocation | exact bindings execute → authorize/invoke/retrieve | Skill/MCP result/failure and Knowledge citation Evidence; denial zero calls; RR |
| 12 Instance isolation | two scoped Instances assign → distinct Placement/effects | owner/scope visibility; cross-scope denied; RR |
| 13 Cross-view consistency | select execution/switch views → projection only | byte-equal IDs/bidirectional links; partial/stale explicit; RR |
| 14 Responsive/keyboard | live desktop/mobile keyboard journey → governed transitions | focus/touch/overflow evidence; inaccessible action fails |
| 15 Minimum disclosure | denied/failure/partial inspect → sanitized facts only | no secret/private data/fake success; RR |

Golden Demo uses real services and persisted identities but cannot replace complete
acceptance. Capability implementation, durable integration, assembly, Product
acceptance, Demo, Preview deployment, Preview acceptance and Formal Release are
independent. Preview may disclose a bounded subset; Preview Evidence is not Formal
Release proof.

## 11. Dependency graph, delivery waves and task routing

```text
(210 execution || 230 Runtime) → (220 Instances || 240 intervention)
→ (241 resources || 250 Workbench) → (251 management || 252 Runtime/fleet views)
→ 260 UX hardening → 270 serialized assembly → 271 acceptance → 272 Demo
→ 280 Preview deployment → 281 Preview acceptance
```

| Candidate | Candidate scope | Dependency/exit |
| --- | --- | --- |
| `S5-V023-IMPL-210` | Runs/Task Runs/Attempts/Evidence/Outcome services | durable APIs/restart |
| `S5-V023-IMPL-220` | Instance/Assignment/Placement | stable 210; isolation |
| `S5-V023-IMPL-230` | Native/OpenClaw factory/bootstrap/adapters | stable envelope; real path |
| `S5-V023-IMPL-240` | approval/pause/correction/resume/retry/rerun/cancel/feedback | stable 210/220/230 |
| `S5-V023-IMPL-241` | Attempt-scoped resource auth/invocation/Evidence | stable Attempt/resources |
| `S5-V023-IMPL-250` | Workflow Workbench/Intervention Center | live 240 DTOs |
| `S5-V023-IMPL-251` | Employee Management/Operations Experience | live 220/240 facts |
| `S5-V023-IMPL-252` | Runtime Operations/fleet facts/Technical/Evidence views | live 220/230 facts |
| `S5-V023-IMPL-260` | responsive/accessibility/state hardening | assembled surfaces |
| `S5-V023-ASSEMBLY-270` | sole-owner shared assembly/cross-view integration | heavy writers quiescent |
| `S5-V023-ACCEPT-271` | complete real-service loop | assembled candidate |
| `S5-V023-ACCEPT-272` | Golden Demo/Scenario Pack | disclosed accepted subset |
| `S5-V023-PV-DEPLOY-280` | Preview deployment | separate authorization |
| `S5-V023-PV-ACCEPT-281` | browser/continuity/limitation acceptance | exact deployed version |

At most two heavy writers run concurrently and declare shared-path ownership. Then
270–281 serialize. These labels allocate, reserve, activate and authorize nothing.

## 12. Explicit exclusions and deferred-version scope

Excluded: complete tenant IAM/RBAC/ABAC, Marketplace, FinOps/billing/quota/SLA,
autoscaling, HA/failover, multi-cluster/region, disaster recovery, session migration,
zero-downtime upgrades, exactly-once external effects, provider certification, new
public CRD/API group, complete Runtime/Fleet Manager, and complete Digital Employee
evaluation/continuous optimization. Model governance is v0.2.4; fleet automation is
v0.2.5; broader scale/trust is later. Formal Release additionally needs separately
approved support/compatibility, backup/restore/retention, upgrade, security,
performance, capacity, SLO, certification and public Contract gates.

## Checkpoint A result

`PASS / V0_2_3_PRODUCT_WORKFLOW_OPERATIONS_AND_FLEET_READY_ARCHITECTURE_READY_FOR_HUMAN_CHECKPOINT_A`

Ready for Human review only. No downstream task/identifier or deployment is active.
