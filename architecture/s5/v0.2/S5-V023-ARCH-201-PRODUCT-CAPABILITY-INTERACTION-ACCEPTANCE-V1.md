# S5-V023-ARCH-201 — v0.2.3 Product Capability, Interaction and Acceptance Architecture v1

## 1. Decision record

| Field | Value |
| --- | --- |
| Session | `S5-V023-ARCH-201` |
| Gate | `ARCH / G2 / CHECKPOINT_A_CANDIDATE` |
| Authorized baseline | `d2d1fca641f984f98bb843dea28d69bc60751cb3` |
| Decision status | `PROPOSED / READY_FOR_HUMAN_CHECKPOINT_A` |
| Implementation status | Existing foundations classified below; new work `NOT_ALLOCATED` |
| Contract status | Internal v0.2.3 architecture; `NOT_FROZEN` |
| Release status | `NO_PUBLIC_PREVIEW / NO_FORMAL_RELEASE_CLAIM` |

This architecture turns completed `V0.2.3-CONTROL-200` reconciliation and the
accepted interaction guidance into one implementation-ready baseline. It specializes,
and does not reopen, S5-ARCH-011/012/013/018/019. It changes no public CRD,
Kubernetes API group, frozen Contract, deployment, or v0.2.2 resource.

Suffix `201` was unused before this Human allocation. Every later identifier in this
document is `NOT_ALLOCATED / NOT_RESERVED`.

## 2. Normative product objective

v0.2.3 is a coherent bounded enterprise capability-management increment. A person
submits a business problem, confirms understanding, reviews decomposition and an
exact Plan, inspects the Digital Employee team, corrects or approves that immutable
Plan, executes through Native or exact-version OpenClaw, and inspects progress,
governed resource use, Evidence, Outcome, intervention and a successor execution.

```text
Problem → Intent/Understanding → Approved Plan → Workflow Run → Task Run
→ Attempt → Placement → Runtime Instance → Agent Instance
→ Resource Invocation → Event → Evidence → Outcome → Feedback
```

Digital Employee Definition is immutable composition; Digital Employee Instance is
the assignee. Agent Definition, Agent Instance and Runtime Instance are distinct.
Assignment is not Placement. Session is context only. Provider, Kubernetes and
session identifiers are correlations, never Product identity.

Execution MUST NOT start until approval binds exact canonical Plan bytes, revision
and digest. Changed content invalidates approval. Semantic correction creates an
immutable successor Plan and, after separate exact approval, a successor Workflow
Run; predecessor history and Attempt identities are never rewritten or reused.

PostgreSQL owns durable Product identity, intent and normalized history; Kubernetes
owns actual CRD/workload state; providers own native effects and identifiers.
Product and Technical projections add no authority.

## 3. Capability and subfeature matrix

| Capability | Required v0.2.3 subfeatures | Current status | Required closure |
| --- | --- | --- | --- |
| Problem/understanding | Chinese-first input; facts, assumptions, uncertainty; typed failure | `DURABLY_IMPLEMENTED` foundation | assemble without fixture fallback |
| Decomposition/Plan | requirements, dependencies, roles, validation, canonical digest | `DURABLY_IMPLEMENTED` foundation | bind to durable Run/successor |
| Exact approval | exact digest, change rejection, approval Evidence, zero early execution | `DURABLY_IMPLEMENTED` foundation | enforce at Placement/invocation |
| Digital Employee composition | exact Agent/Workflow/Knowledge/Skill/MCP/Profile revisions | `DURABLY_IMPLEMENTED` v0.2.2 template | preserve immutable composition |
| Digital Employee Instance | create/read/reuse; exact definition; bounded lifecycle | `PLANNED_NOT_IMPLEMENTED` | PostgreSQL service/API/UI |
| Agent Instance | exact Agent Definition and Runtime Instance; history | `PARTIALLY_IMPLEMENTED` repository | service/lifecycle/UI acceptance |
| Assignment | approved Plan/input to Digital Employee Instance; stable rejection | `PARTIALLY_IMPLEMENTED` repository | persist-before-route behavior |
| Workflow Run | exact Plan/Workflow; predecessor/successor; terminal state | `PARTIALLY_IMPLEMENTED` repository | application orchestration |
| Task Run/Attempt | retry makes new Attempt; ordered state/result | `PARTIALLY_IMPLEMENTED` repository | application/Runtime correlation |
| Placement | immutable decision/digest and selected Instances | `PARTIALLY_IMPLEMENTED` | governed selection/two-instance proof |
| Native Runtime | translator, reconcile, health/readiness/freshness, stop/replace | `IMPLEMENTED_NOT_ASSEMBLED` | persistent real Platform path |
| OpenClaw Runtime | exact version, factory, accepted/running/terminal, multi-instance | `IMPLEMENTED_NOT_ASSEMBLED` provider-local | complete Platform path |
| Runtime Operations | desired generation, observation, uncertainty, stop/replacement | `PARTIALLY_IMPLEMENTED` | command/observation services and UI |
| Skill/MCP invocation | exact binding; authorization/compatibility; normalized Evidence | `PARTIALLY_IMPLEMENTED` | Attempt-scoped propagation |
| Knowledge consumption | exact revision/index, auth-before-lookup, citation Evidence | `DURABLY_IMPLEMENTED` before execution | exact Attempt/Outcome linkage |
| Event/Evidence | append-only ordered canonical facts and minimum disclosure | `DURABLY_IMPLEMENTED` persistence | sole PostgreSQL writer in assembly |
| Outcome/comparison | immutable Outcome; Evidence; successor comparison; `NOT_MEASURABLE` | `PARTIALLY_IMPLEMENTED` | durable writer/projection/UI |
| Intervention | requested/applied/observed, exact target/generation | `PARTIALLY_IMPLEMENTED` | persist-before-effect closure |
| Correction/successor | immutable successor, separate approval, rerun/comparison | `IMPLEMENTED_NOT_ASSEMBLED` | durable rather than process-local |
| Restart readback | same identities/history; re-observe; no blind replay | `IMPLEMENTED_NOT_ASSEMBLED` components | complete restart acceptance |
| Stop/replacement | block new work, drain/stop, observe, bounded generation | `IMPLEMENTED_NOT_ASSEMBLED` | end-to-end command/UI proof |
| Security/isolation | auth before lookup/effect; zero-call denial; scope/secrets | `PARTIALLY_IMPLEMENTED` | cross-layer negative/isolation proof |
| Sibling views | Product/Technical/Evidence, exact URL context, no implicit latest | `DURABLY_IMPLEMENTED` v0.2.2 shell | live v0.2.3 objects/facts |
| Public Preview | real services, version data, health, rollback, truthful label | `PLANNED_NOT_IMPLEMENTED` | independent 280-band gates |

Schema is not usable behavior; component tests are not assembled acceptance; backend
projection is not visible UI; provider-local OpenClaw is not Platform execution; and
Public Preview is not Formal Release.

## 4. Mandatory Chinese business-first journey

1. **提出业务问题 / Ask.** One primary submit action; no fabricated employee, Plan,
   metric, execution or success.
2. **确认系统理解 / Confirm understanding.** Facts, assumptions, uncertainty,
   missing input and provenance. Correction creates a successor record.
3. **查看问题拆解 / Review decomposition.** Tasks, dependencies, outputs and
   completion criteria in business language.
4. **审查计划 / Review Plan.** Immutable revision, actions, risk, resources and
   approval impact.
5. **审查数字员工团队 / Review team.** Responsibility, exact definition and
   Capability/Skill/MCP/Knowledge/Runtime coverage; show gaps truthfully.
6. **修正或精确批准 / Correct or approve exactly.** No execute action exists for an
   unapproved or changed revision.
7. **观察执行 / Observe.** Vertical timeline for Run, Task Run, Attempt, Placement,
   Instances, invocations, Events and interventions.
8. **查看结果与证据 / Inspect result.** Separate findings, conclusion, actions,
   execution result, limitations, citations, Evidence and Outcome.
9. **跟进、修正或重新运行 / Follow up.** Compare immutable predecessor/successor
   Plans, Runs, Evidence and Outcomes.

`ROLE_GAP`, `DENIED`, `UNAVAILABLE`, `FAILED`, `UNKNOWN`, `STALE`,
`RECOVERY_REQUIRED` and `NOT_MEASURABLE` remain distinct textual states. Denial
precedes discovery and causes zero downstream effects.

## 5. Visual and accessibility contract

- Chinese-first, English-secondary copy; raw enums never replace explanation.
- White base, near-black text, restrained blue accent, light gray-blue boundaries.
- Status color is sparse, semantic and always paired with icon/text.
- One visually dominant primary action per screen.
- A vertical journey/timeline, not a dashboard card wall.
- Progressive disclosure for IDs, revisions, digests, generations, correlations,
  Kubernetes facts and raw payloads; visible exact values are selectable and wrap.
- Complete visible-control acceptance at desktop `1280×720` and mobile `390×844`;
  no horizontal page/timeline overflow.
- Mobile targets are at least `44×44` CSS pixels; long Chinese copy and opaque IDs
  remain safe.
- Keyboard access, logical focus order, visible focus, managed dialog/drawer focus
  and focus restoration are mandatory.
- Heading/landmark/label/status semantics never depend only on color or position.
- Business meaning is default; raw JSON and provider/infrastructure facts collapse.

The prior prototype is authoritative for structure, copy, navigation, disclosure and
responsive behavior only. Mock data, fixture authority, hard-coded metrics, local
lifecycle state and simulated success cannot satisfy acceptance.

## 6. Information architecture

Product View and Technical View are sibling projections over one backend-owned graph.
Switching view preserves:

```text
(namespace, security_domain, object_kind, object_id, revision_id,
 run_id, task_run_id, attempt_id, selected_section, predecessor_id)
```

Missing/unauthorized context yields a typed empty/denied state. No surface may select
“latest,” a similarly named object, or a fixture silently.

| Surface | Canonical objects | Mandatory links |
| --- | --- | --- |
| Workspace/Business journey | Problem, Intent, Plan, Digital Employee, Run, Outcome | team, timeline, Evidence, successor |
| Digital Employee management | Definition, Instance, Assignment, Agent Definition/Instance | Runs/Tasks, Runtime, gaps |
| Resource Workbench | Agent, Workflow, Skill, MCP, Knowledge, Capability, Profile | consumers, lifecycle, invocation Evidence |
| Runtime Operations | Run, Task Run, Attempt, Placement, Runtime/Agent Instance, command, observation | Product task, Evidence, intervention |
| Technical View | canonical IDs plus provider/Kubernetes correlations and health facts | exact return to Product context |
| Evidence Inspector | claim, Evidence, Event, invocation, citation, Attempt, Outcome | bidirectional claim/Evidence/technical navigation |
| Knowledge Workbench | revision, index snapshot, retrieval/citation, consuming Attempt | exact source and conclusion |
| Intervention | Intervention, command, target generation, applied/observed facts | timeline and resulting successor/state |
| Successor comparison | predecessor/successor Plan, Run, Outcome, Evidence, method/version | both journeys and missing values |

## 7. Runtime and governed consumption

Native remains the reference path and reuses current controllers, coordinator,
envelope, translator and Kubernetes observer. OpenClaw is mandatory but bounded: the
provider compatibility boundary currently requires exact `2026.7.1-2`, distribution
provenance, real accepted/running/terminal task execution and exact correlations.
Factory selection fails closed; it never falls back to Native, OpenClaw or mock.

Commands are authorized and persisted before effects. Observations are timestamped,
append-only facts. Health, readiness and freshness are separate. Restart reacquires
state; ambiguity becomes `RECOVERY_REQUIRED`. Stop blocks new Assignment, requests
bounded drain/stop and observes termination. Replacement obeys generation policy and
preserves Product identity; only retry creates a new Attempt.

Every Skill, MCP and Knowledge use is Attempt-scoped and binds exact revisions.
Authorization, publication/matchability and compatibility precede lookup/invocation.
Evidence carries normalized identity, source correlation, decision references and
limitations without secrets. Knowledge citations bind exact revision/index snapshot.
`DENIED` performs zero discovery or invocation and discloses no protected metadata.

## 8. Ownership and shared-path rules

| Boundary | Backend/core | Runtime/operator | Frontend | Invariant |
| --- | --- | --- | --- | --- |
| Execution application | feature-local execution services/repositories | typed envelope consumer | Runtime Operations API/types | no public CRD redesign |
| Instances/Assignment | feature-local services/repositories | exact Placement consumer | Digital Employee management | no template-as-instance |
| Runtime lifecycle | command/observation service | manager, translator, observer, providers | Runtime operations | provider owns no Product ID |
| Resource invocation | binding/auth services | invocation adapters | Evidence/Knowledge inspection | no frontend authorization |
| Outcome/intervention | append-only services | applied/observed facts | comparison/intervention | no prior fact mutation |
| Projections | versioned backend DTO composition | normalized facts | sibling projections | no frontend lifecycle authority |
| Acceptance | black-box reporters | real provider/Kubernetes fixtures | visible-control Playwright | test data owns no runtime state |

Application bootstrap/routes, global navigation/styles, provider factory/bootstrap,
shared DTO/URL types, compatibility allowlists, CI/acceptance runner, and deployment
or cutover manifests each have one owner per wave. Domain writers do not edit them.
At most two heavy writers run concurrently, in isolated worktrees with disjoint path
manifests. The serialized shared owner is not a third heavy writer.

## 9. Acceptance matrix

| ID | Required proof | Rejected substitute |
| --- | --- | --- |
| A01 | zero Run/Placement/provider/resource call before exact approval | UI-only disabled action |
| A02 | byte-equal IDs/revisions/digests across Product/Technical/Evidence | labels or latest lookup |
| A03 | real PostgreSQL execution facts and sole Evidence authority | memory/SQLite/fixture |
| A04 | real Native accepted/running/terminal path | unit/provider-only test |
| A05 | exact-version real OpenClaw terminal path and provenance | startup/readiness only |
| A06 | required Skill/MCP/Knowledge use with invocation/citation Evidence | declared binding only |
| A07 | truthful gap/denial/unavailable/failure; denial zero calls | generic fallback/fake success |
| A08 | persisted intervention request before applied/observed facts | process-local button state |
| A09 | separately approved successor Run and immutable comparison | edited/reused predecessor |
| A10 | restart returns same history and reacquires observations | warm cache/recreated IDs |
| A11 | two scoped Runtime/Agent Instances with isolated placement/effects | two cards over one instance |
| A12 | persisted stop, blocked work, observed stop, bounded replacement | Pod deletion/retry conflation |
| A13 | claim ↔ Evidence ↔ technical fact/citation/Attempt navigation | static one-way IDs |
| A14 | full `1280×720` visible-control journey against real services | screenshot/API-only proof |
| A15 | full `390×844`, 44×44, keyboard/focus, no overflow, non-color states | render-only responsive check |
| A16 | scoped denial/secret attempts fail before discovery/effect, sanitized output | UI hiding only |
| A17 | separate health/readiness/freshness and exact build/provider/source identity | HTTP/Pod inference |
| A18 | isolated rollback without discarding authoritative post-cutover facts | destructive reset/runbook only |
| A19 | unsupported topology/recovery/certification/readiness visible in product | docs-only limitation |

Evidence names exact commit/tree, builds/images, provider integrity, PostgreSQL/Qdrant
instances, scope and timestamps. Synthetic setup data is labelled and never presented
as live execution.

### Explicit non-acceptance matrix

| Evidence offered | Classification |
| --- | --- |
| Existing Question-to-Outcome Demo | UX guidance and bounded shell; not v0.2.3 execution authority |
| Migration/schema or repository tests | storage foundation; not usable application behavior |
| Native component tests | not assembled persistent execution |
| OpenClaw startup/readiness | not Platform terminal task execution |
| Rendered Product/Technical pages | not canonical live identity equality |
| Mock/snapshot/fixture journey | not real providers, persistence, denial or restart |
| One successful Runtime Instance | not bounded two-instance isolation |
| Cached restart reconstruction | not durable readback and external re-observation |
| Public URL and health response | not Preview security, rollback or product acceptance |
| Passing Public Preview | not Formal Release, certification or production readiness |

## 10. Public Preview versus Formal Release

Public Preview requires A01–A19 in a clean isolated real-service deployment, health
preflight, version-scoped data, rollback, minimum disclosure and the label
`v0.2.3 Public Preview`. It MUST NOT claim Formal Release, production readiness,
certification, HA, exactly-once effects, generalized recovery, autoscaling, state
portability, rolling upgrades or enterprise-scale multi-tenancy.

Formal Release remains blocked on a Human-approved support/compatibility matrix,
backup/restore/retention, upgrade/downgrade, certification, capacity/performance,
SLO/support policy, broader fault/security review, applicable public Contract gates
and release ownership.

## 11. Deferred scope

- **v0.2.4:** Model Catalog/revisions, Provider/Endpoint/Profile, evaluation, policy
  selection, Human override, exact binding, invocation/usage Evidence, measurable
  latency/token/cost, `NOT_MEASURABLE` and evidence-backed fallback.
- **Proposed v0.2.5:** a separately confirmed bounded Fleet/product-operations
  increment may cover inventory, bulk-safe reads, capacity visibility and limited
  multi-node acceptance. This horizon/scope is proposed, not historical authority.
- **v0.3.0+:** complete Runtime Manager, autoscaling, HA/failover, cross-node state,
  rolling upgrades, generalized recovery, multi-cluster/region/hybrid cloud, GPU-aware
  placement, large-scale Tenant/Organization, SSO, centralized policy/RBAC,
  Marketplace, billing/FinOps, certification and production readiness.

Public CRD/API-group expansion, Digital Employee CRD, Kubernetes authority changes
and any new persistent infrastructure always require separate G2 approval.

## 12. Updated 2xx routing and critical path

The obsolete CONTROL-200 suggestions `201–207` are withdrawn; `201` is this
architecture task. All following slots remain unallocated.

```text
201 Architecture and Human Checkpoint A
 ├─ 210–219 execution/PostgreSQL application assembly
 │    └─ 220–229 Instance, Assignment and Placement
 └─ 230–239 Native/OpenClaw Runtime assembly
      └─ 240–249 intervention, successor and resource invocation
           ├─ 250–259 Product Experience
           └─ 260–269 UX/accessibility hardening
                    ↓
             270–279 serialized assembly and independent E2E
                    ↓
             280–289 Public Preview deployment/acceptance
                    ↓
             290–299 Formal Release/reserve
```

| Band | Ownership and exit | Dependency/parallel rule |
| --- | --- | --- |
| 210–219 | execution services, Runs/Attempts/Placement/Outcome; PostgreSQL/restart tests | heavy writer 1; Track A foundation |
| 220–229 | Digital Employee/Agent/Runtime Instances and Assignment; two-instance proof | stable 210 interfaces |
| 230–239 | Native/OpenClaw factory, bootstrap, command/observation and real task path | heavy writer 2; stable envelope |
| 240–249 | correction/retry/rerun/stop/replace and resource propagation | after 210/220/230 identity stability |
| 250–259 | business journey, management, Runtime Operations and sibling views | feature-local paths; versioned DTOs |
| 260–269 | visual/mobile/keyboard/focus/error/nondisclosure hardening | no lifecycle semantics |
| 270–279 | sole shared-path assembly, then independent A01–A19 acceptance | heavy writers quiescent; one shared owner |
| 280–289 | isolated Preview deployment, health, provenance, rollback, public acceptance | separate deployment authorization |
| 290–299 | unresolved Formal Release gates or reserve | explicit Human decisions only |

Critical path:

```text
Checkpoint A + durable architecture integration
→ execution services + Native/OpenClaw assembly
→ Instances/Assignment/Placement
→ governed resources + intervention + successor
→ Product/Technical/Runtime Operations
→ sole shared assembly → real-service acceptance
→ Preview deployment/rollback → Human Preview decision
```

STOP for public CRD/API, frozen Contract, new database/dependency, lifecycle semantic,
dual-authority, frontend-authority, unbounded provider, weakened approval/security,
unconfirmed v0.2.5 or Formal Release changes.

## 13. Checkpoint A result

`PASS / V0_2_3_PRODUCT_CAPABILITY_INTERACTION_ARCHITECTURE_READY_FOR_HUMAN_CHECKPOINT_A`

This is complete for Human review, not accepted, integrated, implemented, deployed or
released. It allocates no downstream identifier.

## 14. Separate Final Integration Routing

After Human Checkpoint A approval, a separately allocated integration session may
validate and integrate only this architecture/evidence/index change and record exact
commit/tree/PR/CI identity. It MUST NOT allocate 210–299 work, change product code,
deploy, activate Preview, touch v0.2.2 or `S5-DEPLOY-069`, or infer release acceptance.
