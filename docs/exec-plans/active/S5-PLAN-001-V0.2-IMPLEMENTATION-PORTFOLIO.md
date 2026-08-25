# S5-PLAN-001 — v0.2 Implementation Portfolio and Release Execution Plan

## Session

| Field | Value |
| --- | --- |
| ID | `S5-PLAN-001` |
| Type | `PLAN` |
| Version | `v0.2 CONNECT — Digital Employee Technical Preview` |
| Lifecycle | `CLOSING` |
| Authorization | `AUTHORIZED` |
| Status | `PASS` |
| Checkpoint | `C — SESSION_FINALIZATION` |
| Result | `READY_TO_CLOSE` |
| Human Checkpoint A Gate | `PASS_WITH_CONSTRAINTS` |
| Human Implementation Entry Gate | `PASS_WITH_CONSTRAINTS` |
| Human Close Confirmation | `PENDING` |
| Authorized baseline | `df2a56d48c21e4e74b6fb1d94f39cb2f07894aa9` |
| Implementation entry | `CONDITIONALLY_GRANTED` |
| Next gate | `Human S5-PLAN-001 Close Confirmation` |

This plan has conditional implementation entry, but it does not authorize or
start any implementation Session. Tracks A–E
and every Session ID below are `PLANNED / NOT_ACTIVE / NOT_AUTHORIZED` or
`RECOMMENDED_ONLY / NOT_ACTIVE / NOT_AUTHORIZED`. No schema or Contract is
frozen; no Provider is certified; production readiness and release acceptance
remain not granted.

## 1. Baseline and provenance

- `origin/main` and the authorized baseline were the same commit at preflight.
- PR #44 was `MERGED` into `main` with merge commit
  `df2a56d48c21e4e74b6fb1d94f39cb2f07894aa9`.
- Source Sessions: S5-ARCH-005, S5-GOV-001, S5-ARCH-006, S5-REL-006.
- The source artifact is
  [S5-ARCH-006](../../../S5-ARCH-006-DIGITAL-EMPLOYEE-GOLDEN-DEMO-V1.md).
- S5-ARCH-006 is `CLOSED / COMPLETED`; reopening is prohibited.
- S5-REL-006 is forward-imported as `CLOSED / COMPLETED / PASS /
  SESSION_CLOSED`, reopening prohibited, provenance
  `HUMAN_CONFIRMED_GIT_VERIFIED / FORWARD_IMPORTED_BY_S5_PLAN_001`.
- G01–G08, 23 Required, one Experimental, 15 Deferred, five blocked
  claim/gate classifications, and all 70 criteria are preserved.

## 2. Current implementation inventory

| Area | State | Source and observed boundary |
| --- | --- | --- |
| Agent CRD/controller | `IMPLEMENTED_WITH_ADAPTATION` | `manifests/crd/agents.agentos.io.yaml`; `operator/src/agent_operator/main.py` and `resources.py`; creates Deployment/Service, reconciles replicas/template, reports phase/readiness. It currently combines definition and realization and has no first-class Instance. |
| Task CRD/API/controller | `IMPLEMENTED_WITH_ADAPTATION` | `manifests/crd/tasks.agentos.io.yaml`; `operator/src/agent_operator/task_controller.py`; synchronous Service invocation, retry/deadline, status/result/error. No Instance target, execution identity, Capability outcome, or Human Gate. |
| Workflow DAG | `IMPLEMENTED_WITH_ADAPTATION` | `manifests/crd/workflows.agentos.io.yaml`; `workflow_controller.py`, `workflow_graph.py`; dependency/data edges, fan-out/fan-in, parallel runnable tasks, failure/skip/timeout. Rich domain Outcome and approval steps are absent. |
| Native Runtime | `IMPLEMENTED_WITH_ADAPTATION` | `runtime/src/agent_runtime/main.py`; `/healthz`, `/readyz`, `/v1/invoke`; prompt construction and Provider factory. It is not yet behind the accepted Runtime Provider/Binding interface. |
| Model providers | `IMPLEMENTED_AND_REUSABLE` | `runtime/src/agent_runtime/providers/`; mock plus OpenAI-compatible provider selected from environment; secret consumption is Kubernetes-env based. This is model integration, not Runtime Provider abstraction. |
| Runtime Provider abstraction | `PROTOTYPE_ONLY` | Architecture and Hermes evidence exist under `architecture/s5/v0.2/` and `docs/evidence/s5/runtime/`; no Production/Core adapter SDK, registration, heartbeat, Compatibility Manifest, or OpenClaw adapter. |
| Capability/REST/MCP | `PROTOTYPE_ONLY` | Capability spike evidence under `docs/evidence/s5/capability-contract/`; Production/Core has no Capability Definition/Binding, governed REST/MCP Provider, gateway, or normalized Capability Outcome. |
| Authorization | `MISSING` | HTTP 403 is classified by the Task controller, but no discovery/authorization split, policy decision, delegated identity, audit decision, or deny-before-provider gateway exists. |
| Gateway | `MISSING` | `gateway/` is reserved; direct Task-to-Agent Service invocation remains current behavior. |
| Console backend | `IMPLEMENTED_WITH_ADAPTATION` | `console/backend/src/agent_console/`; read-only Kubernetes Workflow repository, projection, schemas, and API. No authoring, approval, Digital Employee projection, or separate database. |
| Console frontend | `IMPLEMENTED_WITH_ADAPTATION` | `console/frontend/src/`; Workflow list/detail, DAG, node execution and bilingual presentation. No Product View or extended Technical View. |
| Identity/correlation | `PROTOTYPE_ONLY` | Kubernetes names and Workflow task references are current correlation. Stable Definition/Instance IDs, selected Instance, Platform Execution Identity, and opaque native refs are absent from Production/Core. |
| Conditions/Outcomes/status | `IMPLEMENTED_WITH_ADAPTATION` | Agent readiness condition/phase and Task/Workflow phase/result/reason exist in CRDs/controllers. Domain-owned Conditions, Capability/Task/Workflow Outcomes, freshness, and shared projections are not represented. |
| Recovery | `PROTOTYPE_ONLY` | Kubernetes restarts and retry are current; Agent Instance routing/recovery spike and Hermes recovery evidence are non-production. Restart is not semantic recovery and State continuity is not claimed. |
| Manifests/examples | `IMPLEMENTED_WITH_ADAPTATION` | CRDs, RBAC, operator, Agent/Task/Workflow examples and Golden Engineering Demo exist. No Digital Employee, synthetic quality services, managed Provider, document, or connector package. |
| Tests/conformance | `IMPLEMENTED_WITH_ADAPTATION` | Operator/runtime/backend/repository tests cover current behavior. Spike evidence exists, but no integrated Runtime/Capability Provider Conformance or 70-criterion suite exists. |
| Deployment/local development | `IMPLEMENTED_WITH_ADAPTATION` | Dockerfiles, Kind config, manifests, Make targets and documented v0.1 bootstrap exist; clean v0.2 managed demo bootstrap and exact external-runtime packages are missing. |
| State, tenant, enterprise IAM | `DEFERRED` | Full State portability, multi-tenancy, enterprise SSO/RBAC and policy engines remain beyond the slice. |

## 3. Minimum vertical slice execution contract

The thinnest runnable slice uses synthetic `QI-1042`, the Native managed path,
one deterministic REST service, one deterministic MCP knowledge service, one
ALLOW, one pre-provider DENY, and synchronized projections. OpenClaw evidence
is required for the public external-runtime claim but is not allowed to make
the Native slice unreliable. Hermes is visibly Experimental and non-blocking.

| Step | Existing / missing | Owner and future Session | Input → output; authority/identity | Tests, demo, dependency and fallback |
| --- | --- | --- | --- | --- |
| Business description | Console shell reusable; authoring missing | D / `S5-IMPL-009` | Human text → non-authoritative draft request; user identity retained | fixture and input validation; deterministic seed if generator unavailable; A projection contract |
| Editable AI draft | missing | D / `S5-IMPL-009` | request → labelled AI draft with generator evidence; never desired state | draft snapshot/edit tests; deterministic draft fallback |
| Diff and validation | missing; DAG validator adaptable | D/C / `S5-IMPL-009` | draft/base → material Diff and fail-closed validation | Diff, DAG, capability, permission and secret-pattern negatives; C manifests |
| Human approval | missing | D/A / `S5-IMPL-010` | validated draft + Human decision → approved publish command | unauthorized/absent approval fails closed; P01/P02 |
| Agent Definition | accepted Candidate; current Agent adaptable | A / `S5-IMPL-001` | approved command → authoritative Definition/version reference; Kubernetes remains source of truth | representation/compatibility tests; G2 Human Gate before public representation |
| Agent Instance | spike only | A / `S5-IMPL-002` | Definition + placement → stable Instance and eligibility evidence | 1:N/routing/replacement tests; no eligible Instance fails honestly |
| Native Runtime | runtime exists; Provider binding missing | B / `S5-IMPL-004` | selected Instance/Binding/execution identity → Native realization refs | Provider conformance and managed E2E; exact Native profile; no direct legacy identity substitution |
| Task | current controller reusable | A/C / `S5-IMPL-003` | work + selected Instance + identity → Task execution | v0.1 compatibility and identity equality; legacy translation only if separately approved |
| REST Capability ALLOW | spike only | C / `S5-IMPL-007` | authorized operation/context → normalized Capability Outcome | ALLOW trace; deterministic synthetic service; Provider error normalized |
| Platform Execution Identity | accepted Candidate; missing | A / `S5-IMPL-001` | one generated platform identity → unchanged Runtime/Capability/Task/Workflow refs | end-to-end equality; native refs stay optional/opaque |
| Business Outcome | current result adaptable; domain Outcome missing | C/A / `S5-IMPL-008` | normalized evidence → closure-readiness Outcome | expected `QI-1042` fixture; UNKNOWN on incomplete evidence, never false success |
| Product + Technical Views | Workflow UI reusable; both new | D/E / `S5-IMPL-010`, `S5-IMPL-012` | same Core refs/projections → business and technical representations | cross-view equality and correction/re-execution E2E; backend DTO single writer D |

Shared-file risk is highest in CRDs, `operator/src/agent_operator/`, Console
backend schemas, frontend types, manifests and top-level test configuration.
No Track may edit a shared interface until its owning handoff is accepted.

## 4. Portfolio tracks

### Track A — Core Representation and Execution Identity

- Objective/deliverables: representation-neutral Definition/Instance
  prototype boundary, selected Instance/routing evidence, Platform Execution
  Identity, effective Binding references, placement references, Conditions,
  Outcomes and Recovery Assessment envelope, plus compatibility tests.
- Included: R05–R08 and identity portions of R14/R17/R20/R23. Excluded:
  five-CRD assumption, schema/Contract freeze, State portability, pools,
  multi-tenancy, provider-native translation.
- Source/test ownership: a Human-approved bounded Core package and its contract
  tests; single writer for shared identity/projection DTOs and any migration
  shim. Public CRD/API changes require G2 and are not pre-authorized here.
- Entry: P01/P02 pass and representation Gate resolves persistence. Exit:
  stable in-slice references, routing and replacement fixtures pass, v0.1
  compatibility passes, versioned handoff published.
- Debt: addresses representation, identity/backfill, routing, Conditions,
  Outcomes and Recovery shape; retains freeze, migration, vocabulary and
  production-recovery debt.
- PR/rollback: small interface PR followed by separately bounded realization
  PRs if needed; rollback is the compatibility boundary. Begins first; only
  read-only fixture preparation elsewhere may run in parallel. Consumer: B–E.

### Track B — Managed Runtime Providers

- Objective/deliverables: Native primary Provider package; exact-version
  OpenClaw spike then managed Candidate adapter; bounded Hermes Experimental
  evidence; Compatibility Manifest candidate; lifecycle, registration,
  heartbeat, isolation, status normalization, cleanup and mismatch behavior.
- Included: R09/R10/R20, applicable PCA-01–19 and MRA Provider criteria.
  Excluded: Hermes certification, all-version support, Customer/Edge fleet,
  State portability and universal SDK freeze.
- Ownership: `runtime/` Provider packages and provider conformance fixtures;
  B alone writes native translation and managed topology. It consumes A
  identity/Binding and may not change Core semantics.
- Entry: exact-version spikes and fixture/image research may start before A;
  adapter integration waits for A handoff and P07/P08. Exit: Native managed
  E2E, OpenClaw exact target evidence, mismatch zero-invocation, isolation,
  fallback and cleanup evidence; Hermes labels retained.
- Debt: addresses exact package/profile and live OpenClaw evidence; retains
  certification, thresholds, sharing/tenancy, upgrade/deprecation and
  ED-S5-001.
- PR/rollback: one PR per Provider/package and one conformance integration PR;
  disable external Provider and fall back to labelled Native. Consumer: E.

### Track C — Capability, Workflow and Authorization

- Objective/deliverables: provider-independent Capability manifest/binding
  prototype, governed gateway, deterministic REST and MCP Providers, explicit
  discovery/authorization, ALLOW/DENY audit, workflow/Human-Gate integration,
  Document/File slice and normalized Outcomes.
- Included: R11–R13/R15/R21/R22 and TDA-07/08. Excluded: broad marketplace,
  third-party MCP certification, unrestricted side-effect replay, full IAM,
  high-risk sandbox platform and real connector unless separately chosen.
- Ownership: Capability gateway/authorization modules and synthetic services;
  C alone writes authorization decision and invocation envelope. Workflow
  controller changes wait for A and compatibility Gate.
- Entry: spike fixtures and synthetic service can start before A; identity
  integration waits for A. Exit: ALLOW and DENY/zero-call, REST/MCP,
  document-read, normalized outcome and retry/rate-limit fixtures pass.
- Debt: addresses Provider conformance foundation and deny-before-handoff;
  retains full policy/IAM, delegated identity, third-party MCP and replay debt.
- PR/rollback: gateway, each Provider, then workflow integration PRs; feature
  boundary can be removed without altering current direct v0.1 path. Consumer: D/E.

### Track D — AI-assisted Authoring and Product View

- Objective/deliverables: three-step authoring, editable deterministic/AI
  draft, Diff/validation, Human approval/publish/test, Digital Employee list
  and overview, work status, business Outcome, correction and re-execution.
- Included: R01–R04/R14/R16/R23 and PDA-01–12. Excluded: Console-owned desired
  state/database, full Factory/Catalog, tenant administration and raw
  Provider configuration.
- Ownership: Product projection schemas/API/UI; D is sole writer for shared
  Console DTOs and versioned projection contract. It consumes A/C refs.
- Entry: UI wire fixtures may begin before A; backend schema/publish begins
  only after P02 and A/C handoffs. Exit: authoring negatives, approval audit,
  synchronized work/outcome, correction and usability rehearsal evidence.
- Debt: addresses authoring and Console synchronization; retains production AI
  evaluation, enterprise approval/IAM and additive old-client tolerance debt.
- PR/rollback: backend projection contract before frontend surfaces; hide the
  Product route to roll back while preserving current Workflow Console. Consumer: E.

### Track E — Technical View, Observability, Conformance and Demo Harness

- Objective/deliverables: correlated Technical View, deterministic Golden
  fixtures, Provider/Capability conformance runner, managed Demo bootstrap,
  negative/fallback/recovery/claim tests and release evidence bundle.
- Included: R18/R19/R23, TDA/ECA, applicable PCA/MRA. Excluded: new Core or
  Provider semantics and release acceptance by test existence alone.
- Ownership: conformance harness, Demo fixtures, evidence output and Technical
  projection consumer; E never redefines A–D DTOs. Single writer for Golden
  Demo expected outputs and evidence index.
- Entry: fixture skeleton can start early; integration requires versioned A–D
  handoffs, P04 and required component gates. Exit: all applicable 70 rows
  have actual evidence or explicit not-pass disposition, clean reproduction,
  timed rehearsal and claim scan.
- Debt: measures rather than erases debt; retains any failed/unrun item and all
  certification/freeze decisions. PR/rollback: harness PR then integration
  bundle; individual optional Provider profiles can be disabled. Consumer: REL.

## 5. Execution order and parallel work

```text
CURRENT: S5-PLAN-001 candidate -> Human Portfolio Gate
  -> Track A interface/identity spine -> Human representation/interface Gate
       -> B Native + OpenClaw integration -----------+
       -> C gateway + workflow integration ----------+-> Track E integration
       -> D authoring backend + synchronized views --+   -> REL integration

Before A completes (preparatory only):
  B exact-version spikes, package/fixture research
  C synthetic REST/MCP/document fixtures and policy test vectors
  D static UX fixtures and deterministic draft/Diff research
  E harness skeleton and criterion manifest

Paused: all writes to shared Core identity, Binding, Conditions/Outcomes and
shared Console DTOs until owners/Gates are fixed.
Blocked: freeze, certification, production-readiness and release claims.
Deferred: Customer-managed/Edge, State portability, marketplace breadth,
full sandbox, all-version support and real connector selection if unnecessary.
```

### Machine-readable dependency table

| Work package | Owner | Predecessor | Type | Writable scope | Start condition | Completion condition | Consumer | Risk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 identity/interface | A | Portfolio Gate | hard | approved Core prototype package/tests | P01/P02 | versioned handoff + compatibility | A2/B/C/D/E | high: CRD/operator |
| A2 routing/recovery | A | A1 | hard | routing/assessment package/tests | A1 stable | deterministic selection/replacement | B/E | high: operator |
| B0 version spikes | B | Portfolio Gate | soft | experiments/evidence only | authorization | exact candidates/evidence | B1/B2 | low |
| B1 Native Provider | B | A1,B0 | hard | runtime Native adapter/tests | A handoff | managed conformance | E | medium |
| B2 OpenClaw Provider | B | A1,B0 | hard | isolated adapter/package/tests | exact target | live + deterministic evidence | E | medium |
| B3 Hermes Experimental | B | B0 | soft | isolated experiment/evidence | explicit scope | labelled bounded result | E optional | low |
| C0 synthetic systems | C | Portfolio Gate | soft | demo services/fixtures | authorization | deterministic REST/MCP/docs | C1/E | low |
| C1 gateway/auth | C | A1,C0 | hard | capability gateway/tests | A identity | ALLOW/DENY zero-call | C2/D/E | medium |
| C2 workflow/outcome | C | A2,C1 | hard | bounded workflow integration/tests | interfaces stable | correlated outcomes | D/E | high: workflow |
| D0 UX fixtures | D | Portfolio Gate | soft | isolated UI fixtures | authorization | reviewed fixture contract | D1 | low |
| D1 authoring/backend | D | A1,C1,D0 | hard | Console schemas/API/service | DTO ownership fixed | approval/publish tests | D2/E | high: shared DTO |
| D2 Product View | D | D1,C2 | hard | Product UI/API consumer | backend handoff | PDA evidence | E | medium |
| E0 harness skeleton | E | Portfolio Gate | soft | isolated conformance fixtures | authorization | criterion manifest loads | E1 | low |
| E1 integrated harness | E | A2,B1,B2,C2,D2,E0 | hard | demo/conformance/evidence | P04 | applicable 70 dispositions | REL | high: integration |
| REL bundle | REL | merged approved PRs | governance | registry/release evidence only | Human Merge Gates | durable-main validation | Release Gate | medium |

### Shared-file ownership

| Shared scope | Single writer | Consumers / collision rule |
| --- | --- | --- |
| Core identity, Binding, placement, Condition/Outcome envelopes | A | B–E import a versioned handoff; no concurrent semantic edits |
| Runtime packages/native translation | B | A/C/D/E consume status/evidence only |
| Capability invocation/authorization decision | C | B runtimes cannot bypass it; D/E consume projections |
| Console backend projection DTO/API | D | E Technical View consumes the same schema; backend-before-frontend merge |
| Golden fixtures, expected outputs, criterion evidence index | E | A–D provide component artifacts; E does not alter their contracts |
| CRDs, controller registration, top-level manifests | designated integration Session | serialized after G2/interface decision |
| Governance Registry/Project State | active PLAN/REL Session only | merge-order update; never concurrently edited by coding Tracks |

## 6. Recommended future Session map

All IDs are recommendations only. Each writable Session maps to one Codex
conversation, branch, isolated worktree and primary PR. CLOSED Sessions are
never reused.

| ID | Type | Track / purpose | Depends on | Parallel class | Primary PR boundary |
| --- | --- | --- | --- | --- | --- |
| S5-PLAN-002 | PLAN | Harness and parallel delivery readiness; routing, ownership, failure propagation and bounded pilot design | S5-REL-017 | sequential planning; no parallel execution authorized | planning/evidence metadata only |
| S5-ARCH-007 | ARCH | representation/interface Human decision | S5-PLAN-001 | sequential | decision artifact only |
| S5-SPIKE-005 | SPIKE | exact Native/OpenClaw targets + Manifest representation evidence | S5-PLAN-001 | early parallel | experiments/evidence |
| S5-SPIKE-006 | SPIKE | bounded Hermes target evidence | S5-PLAN-001 | optional parallel | experiments/evidence |
| S5-IMPL-001 | IMPL | A identity/Definition envelope | S5-ARCH-007 | sequential spine | one interface PR |
| S5-IMPL-002 | IMPL | A Instance routing/recovery | S5-IMPL-001 | sequential | one routing PR |
| S5-IMPL-003 | IMPL | A current Task/Workflow compatibility integration | S5-IMPL-002 | sequential | one compatibility PR |
| S5-IMPL-004 | IMPL | B Native Provider | S5-IMPL-001,S5-SPIKE-005 | parallel after A1 | one Provider PR |
| S5-IMPL-005 | IMPL | B OpenClaw Candidate adapter | S5-IMPL-001,S5-SPIKE-005 | parallel after A1 | one Provider PR |
| S5-IMPL-006 | IMPL | B Hermes Experimental adapter/evidence | S5-SPIKE-006 | optional | one isolated PR |
| S5-IMPL-007 | IMPL | C Capability gateway + REST/MCP | S5-IMPL-001 | parallel after A1 | one gateway PR |
| S5-IMPL-008 | IMPL | C workflow/Human Gate/document integration | S5-IMPL-002,S5-IMPL-007 | sequential C | one integration PR |
| S5-IMPL-009 | IMPL | D draft/Diff/validation authoring | S5-IMPL-001,S5-IMPL-007 | parallel after handoffs | backend-first PR |
| S5-IMPL-010 | IMPL | D Product View/approval/re-execution | S5-IMPL-008,S5-IMPL-009 | sequential D | frontend/product PR |
| S5-TEST-005 | TEST | Provider and Capability conformance | B/C PRs | parallel validation | test/evidence PR |
| S5-IMPL-011 | IMPL | E Technical View | A–D schemas | integration | Technical View PR |
| S5-IMPL-012 | IMPL | E Golden Demo harness | A–D,TEST-005 | integration | harness/fixtures PR |
| Later REL IDs allocated once | REL | one REL per merged implementation PR, or Human-approved integration bundle after Portfolio integration | corresponding PR | serialized governance | Registry/evidence only |

S5-PLAN-002 is the closing planning owner for Harness and parallel-delivery
readiness. Its Human-closed plan and a separately allocated and authorized
`TEST` pilot are prerequisites for using parallel Codex delivery on downstream
work; the exact Pilot Session ID remains subject to a Human Pilot Selection
Gate.
`S5-TEST-005` remains the first conformance-Harness Session and
`S5-IMPL-012` remains downstream Golden Demo integration; neither is activated
by S5-PLAN-002.

## 7. Document/File and enterprise connector plan

The minimum Document/File path is: synthetic upload/input → governed Document
Reference (owner, media type, integrity, version) → immutable snapshot or
isolated execution workspace → authorized `read` Capability → correlated
Output Artifact → Human review → separately authorized, version-checked
writeback. Evidence must include ALLOW, DENY/zero-read-or-write, audit and the
same Platform Execution Identity. This belongs to C for provider/gateway, A
for references/identity, B for workspace materialization, D for review, and E
for evidence. It is not a new Core resource or v0.2 document platform.

Planning placements:

| Item | v0.2 placement |
| --- | --- |
| Generic REST/OpenAPI Provider | C required foundation; exact operation manifest, auth mode, timeout/retry/rate-limit and normalized outcome |
| MCP Provider | C required deterministic local path; third-party breadth remains debt |
| Document/File Capability Provider | C bounded slice; read required, controlled writeback only if P05 includes it |
| Synthetic Enterprise Document Service | C/E deterministic fixture; no private data or credentials |
| Connector Capability Manifest | C internal candidate; identity, operations, risk, versions, health, rate/retry and Secret refs |
| Delegated identity | follow-up decision; use only if evidence and selected connector require it |
| Service identity | bounded synthetic default; Secret reference only, never committed value |
| Health/version/audit/rate/retry | C provider evidence and E conformance; explicit stale/unavailable state |
| Connector Conformance | E layer over C manifest; no certification implication |
| Real enterprise connector | P06 follow-up; neither Microsoft Graph nor Feishu selected without evidence |
| Obsidian | deferred Vault Import/Edge use case |

## 8. Runtime Provider execution plan

- Native is `PRIMARY_GOLDEN_PATH`: adapt the current runtime through the A
  Binding/identity handoff; package exact image/profile; prove managed
  lifecycle, isolation, identity, outcome, replacement and cleanup.
- OpenClaw is `SUPPORTED_EXTERNAL_RUNTIME_PATH_CANDIDATE /
  EXACT_VERSION_EVIDENCE_REQUIRED`: S5-SPIKE-005 selects and pins the target,
  then B implements only the evidenced server profile.
- Hermes is `EXPERIMENTAL_ADAPTER / EXACT_VERSION_EVIDENCE_REQUIRED /
  NOT_CURRENTLY_CERTIFIABLE`: a bounded spike may select a target and show
  honest unavailable/experimental behavior. It is outside the release
  critical path and ED-S5-001 stays open absent separately authorized evidence.
- Compatibility Manifest representation is decided at P08/S5-ARCH-007. The
  candidate records adapter/package/upstream versions, profile, contract
  range, capabilities, limitations, isolation, health evidence and fallback.
- Registration/heartbeat, lifecycle and mismatch checks are Adapter-owned;
  A owns logical identity/Conditions. Unsupported or unsafe mismatch is
  rejected before invocation. Native correlation stays opaque.
- Profile/Home/Workspace/Secret scopes are isolated per approved Instance (or
  explicit sharing boundary); only Secret references cross Core. Skills are
  approved/versioned package metadata and cannot bypass C authorization.
- Replacement preserves Instance and execution identity, reassesses Binding,
  reports Recovery Assessment, performs owned idempotent cleanup and makes no
  cross-Runtime State-continuity claim.

## 9. Product and Technical views

Product View includes Digital Employee list; Describe/Review/Approve flow;
editable draft, Diff and validation; overview; business work status; Outcome;
correction and re-execution. Technical View uses the same execution to show
Definition, Instances, selected Instance/reason, effective Binding, Provider
and compatibility evidence, Platform Execution Identity, opaque native refs,
ALLOW/DENY, Conditions, Task/Workflow/Capability Outcomes and Recovery
Assessment. Both query D's shared backend projection over Kubernetes/Core
references. They do not create a second database or desired-state authority.

## 10. Test and conformance portfolio

Environment codes: `U` unit/no cluster; `C` component with fakes; `K` Kind;
`M` managed demo profile; `L` bounded live external target; `H` Human timed
or approval gate. Every row below is a plan disposition, not a passing claim.

### Product acceptance (12)

| ID | Automation / owner | Fixture / environment | Dependency | Evidence output / Release relevance |
| --- | --- | --- | --- | --- |
| PDA-01 | unit+E2E / D | draft seed / U,C | D authoring | draft snapshot / public demo |
| PDA-02 | partial+usability / D | editable draft / C,H | UI | capture+checklist / public demo |
| PDA-03 | unit+UI / D | v1/v2 / U,C | Diff | Diff assertion / MVS |
| PDA-04 | negative API/UI / D | invalid/unapproved / C | validation | fail-closed report / MVS |
| PDA-05 | component+Human / A,D | approval actor / C,H | authority model | audit+version / MVS |
| PDA-06 | E2E / D,E | QI-1042 / M | A–D | trace / public demo |
| PDA-07 | UI E2E / D,E | running/wait/error / C,M | projections | snapshots / public demo |
| PDA-08 | E2E / C,D,E | expected outcome / M | C outcomes | assertion / RC |
| PDA-09 | negative E2E / C,E | closeIssue / C,M | gateway | decision+zero-call / RC |
| PDA-10 | E2E+Human / D,E | v1/v2 / M,H | approval+outcome | comparison / public demo |
| PDA-11 | UI checklist / D,E | history+labels / C,H | projections | checklist / public demo |
| PDA-12 | timed manual / D,E | creation script / H | integrated demo | timing record / usability gate |

### Technical acceptance (11)

| ID | Automation / owner | Fixture / environment | Dependency | Evidence output / Release relevance |
| --- | --- | --- | --- | --- |
| TDA-01 | contract/UI / E | linked views / C | D DTO | equality / public demo |
| TDA-02 | contract / A | 1:N instances / U,C | A model | identity report / MVS |
| TDA-03 | component / A,B | eligible set / C | routing | selection trace / MVS |
| TDA-04 | E2E / A,B,E | Native / M | B Native | trace / Golden path |
| TDA-05 | conformance+live / A,B,E | OpenClaw / C,L | exact target | live bundle / external claim |
| TDA-06 | claim/UI / B,E | Hermes unavailable / C | manifest | labels / Experimental only |
| TDA-07 | provider E2E / C,E | REST+MCP / C,M | gateway | two outcomes / RC |
| TDA-08 | zero-call negative / C,E | denied op / C,M | auth | audit+spy / RC |
| TDA-09 | schema/projection / A–C,E | domain records / C | A/C envelopes | ownership assertions / RC |
| TDA-10 | recovery E2E / A,B,E | replacement / C,M | routing/provider | assessment / RC |
| TDA-11 | trace/UI / D,E | config v1/v2 / C | projections | correlated Diff / public demo |

### Engineering acceptance (8)

| ID | Automation / owner | Fixture / environment | Dependency | Evidence output / Release relevance |
| --- | --- | --- | --- | --- |
| ECA-01 | full suite / A–E | required matrix / C,K,M,L | all | versioned report / implementation gate |
| ECA-02 | repository CI / A–E | current tests / U | each PR | CI report / compatibility |
| ECA-03 | negative matrix / A–E | all failures / C,K | components | report / RC |
| ECA-04 | clean bootstrap / E | synthetic bundle / K,M | packages | hashes/log / public demo |
| ECA-05 | fallback E2E / B,E | external off / M | Native | labelled trace / reliability |
| ECA-06 | claims+secret scan / E | repo/artifacts / U | all | scan report / release gate |
| ECA-07 | architecture test / D,E | shared refs / C | DTO | equality/no-DB report / gate |
| ECA-08 | completeness / E | criterion manifest / U | all | coverage report / release gate |

### Provider Conformance acceptance (20)

| IDs | Automation / owner | Fixture / environment | Dependency | Evidence output / Release relevance |
| --- | --- | --- | --- | --- |
| PCA-01 | package test / B,E | immutable package / U,C | manifest | identity report / support |
| PCA-02 | manifest test / B,E | exact targets / U | P08 | validation / support |
| PCA-03 | boundary test / A,E | future provider / U | A | no-native-field report / architecture |
| PCA-04 | translation test / B,E | bindings / C | A | unchanged consumer / path |
| PCA-05 | ordered interaction / B,E | match+mismatch / C | version detect | trace / safety |
| PCA-06 | deterministic+live / B,E | Native/OpenClaw / M,L | exact targets | run bundle / support |
| PCA-07 | zero-call mismatch / B,E | unsafe version / C | manifest | spy evidence / safety |
| PCA-08 | degradation tests / B,E | declared/undeclared / C | manifest | report / degraded claim |
| PCA-09 | negative status / B,E | untested version / C | manifest | no-supported assertion / claim |
| PCA-10 | identity E2E / A,B,E | executable paths / C,M,L | A | equality / acceptance |
| PCA-11 | trace refs / B,E | native IDs / C,M | adapter | opacity assertion / demo |
| PCA-12 | normalization / B,E | health matrix / C,M,L | Conditions | fixtures/live / condition claim |
| PCA-13 | normalization / B,E | results / C,M,L | Outcomes | fixtures/live / outcome claim |
| PCA-14 | failure matrix / B,E | failures / C | adapter | report / failure claim |
| PCA-15 | replacement / B,E | unavailable/recreate / C,M | recovery | bounded evidence / recovery |
| PCA-16 | cleanup / B,E | owned+foreign / C,M | ownership | idempotency report / lifecycle |
| PCA-17 | manifest/UI / B,E | limitations / C | D/E view | assertions / public support |
| PCA-18 | bounded live / B,E | pinned OpenClaw / L | exact target | live bundle / required external |
| PCA-19 | claim/UI / B,E | Hermes / C | ED-S5-001 | labels / Experimental only |
| PCA-20 | generic fixture / A,E | third adapter / U,C | P08 | load/compile report / extension only |

### Managed Runtime acceptance (19)

| IDs | Automation / owner | Fixture / environment | Dependency | Evidence output / Release relevance |
| --- | --- | --- | --- | --- |
| MRA-01 | rehearsal / B,E | clean server / M | package | inventory/log / Golden path |
| MRA-02 | E2E / B,E | Native isolated / M | A/B | trace / Golden path |
| MRA-03 | bounded live / B,E | OpenClaw / L | exact target | bundle / external path |
| MRA-04 | partial / B,E | Hermes / L | target+debt | labelled evidence / Experimental |
| MRA-05 | projection / A,D,E | placement / C | A | equality / demo |
| MRA-06 | replacement / A,B,E | device/realization / C,M | Instance | identity assertion / recovery |
| MRA-07 | lifecycle / A,B,E | register/start/observe / C,M | adapter | condition trace / managed path |
| MRA-08 | manifest/view / B,E | compatibility / C | P08 | visible evidence / support |
| MRA-09 | isolation negative / B,E | two scopes / M | topology | filesystem/secret report / isolation |
| MRA-10 | assignment / B–E | approved skill / C,M | metadata | integrity trace / bounded skill |
| MRA-11 | negative auth / B,C,E | unapproved skill / C | C auth | zero-install / boundary |
| MRA-12 | authority negative / A,D,E | personal memory / C | policy | no-promotion / governance |
| MRA-13 | promotion negative / C,D,E | learned asset / C | Human review | audit / governance |
| MRA-14 | DENY E2E / B,C,E | bypass attempt / C,M | gateway | zero-call / governed execution |
| MRA-15 | E2E / B,C,E | REST+MCP / M | R12/R13 | one-identity traces / demo |
| MRA-16 | status fixtures / B,E | offline/incompatible / C,L | lifecycle | reconnect/failure report / claimed modes |
| MRA-17 | policy negative / C,E | high-risk op / C | risk class | deny/route evidence / safety |
| MRA-18 | cross-view / D,E | same execution / C,M | A–C DTO | equality / public demo |
| MRA-19 | fallback / B,E | external off / M | Native | labelled trace / public reliability |

Coverage count is exactly 70: 12 PDA + 11 TDA + 8 ECA + 20 PCA + 19 MRA.
Required capability coverage preserves each of `R01`, `R02`, `R03`, `R04`,
`R05`, `R06`, `R07`, `R08`, `R09`, `R10`, `R11`, `R12`, `R13`, `R14`, `R15`,
`R16`, `R17`, `R18`, `R19`, `R20`, `R21`, `R22`, and `R23`; X01 stays
Experimental; D01–D15
stay Deferred; B01–B05 remain blocked claims/gates. No planned test is marked
passing until its evidence is executed and recorded.

## 11. Release critical path

| Milestone | Scope / chain | Blocking conditions and Human Gate | Exit evidence / rollback | Effort / confidence |
| --- | --- | --- | --- | --- |
| M0 Portfolio approval | this plan | P01–P12 | accepted bounded portfolio / no implementation | 1 Gate / high |
| M1 Interface spine | A1→A2 | representation/G2, identity ownership | contract+routing compatibility / remove prototype boundary | 2–4 bounded Sessions / medium |
| M2 Minimum Vertical Slice | A + Native + REST ALLOW/DENY + authoring + shared views | A/C/D handoffs, approval authority | QI-1042 Native trace, correction, cross-view equality / disable Product route | 5–8 Sessions / medium-low |
| M3 Public Golden Demo | M2 + MCP + document path + managed packaging + deterministic fallback | P05, clean bootstrap, usability Gate | 10-minute rehearsal, synthetic hashes, fallback / Native deterministic fixture | 3–6 Sessions / medium |
| M4 External runtime claim | M1 + exact OpenClaw adapter | exact target and PCA-18 live evidence | conformance/live bundle / remove claim and show unavailable | 2–4 Sessions / low-medium |
| M5 Release Candidate | M3 + M4 + all applicable 70 dispositions + compatibility/claim/security CI | P09/P10 and Human RC Gate | versioned report, unresolved debt scoped / revert integration bundle | 2–4 integration/REL Sessions / low |
| M6 Release Acceptance | RC durable main | Human Release Acceptance only | signed decision/evidence; no automatic grant | Human-owned / low until implementation |

Minimum slice: A spine, Native, Task/Workflow compatibility, REST ALLOW/DENY,
one identity, Outcome and both views. Public Demo adds MCP, bounded
Document/File, managed clean reproduction, correction, usability and fallback.
RC adds exact OpenClaw evidence and applicable conformance. Optional:
Experimental Hermes visibility. Deferred after v0.2: Customer-managed, Edge,
State portability, full catalog/sandbox/connector breadth. Blocked future
claims: freezes, certification, production readiness and all-version support.

Effort is expressed as bounded Session ranges, not calendar commitment. It
assumes one focused PR per Session, current v0.1 behavior remains compatible,
no new persistent store, synthetic providers, and timely Human Gates. Overall
confidence is medium-low because representation, external versions and shared
Console interfaces are intentionally unfrozen.

## 12. Progress model

Stage view uses evidence milestones: `planning → vertical slice → parallel
implementation → integration → conformance → Release Acceptance`. Each stage
reports entry Gate, bounded deliverables, evidence complete, blockers and next
Gate; it does not use unsupported percentages.

Work-package view records: total bounded deliverables, completed with evidence,
active, blocked, deferred, and next Gate. A deliverable is complete only when
its stated output and validation exist.

Day Start fields: Session; checkpoint; objective; dependency; files owned;
expected evidence; next Human Gate; branch/worktree/PR; conflict risk.

Day Closeout fields: Session; checkpoint; progress made; validation; blockers;
Evidence Debt changed; files actually changed; evidence links; next action;
next Human Gate; durable-main relationship. Use `NONE`, never silence.

## 13. P01–P12 final dispositions

Checkpoint A supplied sufficient repository evidence for a recommended final
disposition. These are planning dispositions recorded by the Human Checkpoint
A Gate; they do not activate their implementation Sessions.

| ID | Recommended decision and alternatives | Reason / implementation and critical-path impact | Debt / reversibility | Human disposition |
| --- | --- | --- | --- | --- |
| P01 | Native-first thin MVS: description, editable draft, approval, Definition/Instance, Native, one Task, one REST ALLOW, execution identity, one Outcome, both views. Alternatives: add OpenClaw/document/MCP now, or reduce to backend-only. | It is the smallest accepted business/technical story; additions lengthen C before evidence exists, reductions fail G03/G04. It defines stage C of the critical path. | Retains external Runtime, broad capability and production debt; additive and feature-gated. | `ACCEPTED_FOR_IMPLEMENTATION_HANDOFF` |
| P02 | A owns Core identity/interface envelopes; D owns shared Console DTOs; public representation is gated separately. Alternative: each Track defines local DTOs. | Prevents competing identities and projections. A1 must precede A2 and all integration. | Representation/backfill/freeze debt retained; prototype can be removed behind compatibility boundary. | `ACCEPTED_WITH_EVIDENCE_DEBT` |
| P03 | Only Provider-local, synthetic fixture and mock-UX preparation may start before A; shared integration waits for a versioned A handoff. Alternative: fully sequential or concurrent shared writes. | Preserves throughput without interface races. Preparatory Sessions are non-critical except where their evidence feeds B/C. | Mocks may be invalidated by A; disposable by design. | `ACCEPTED_FOR_IMPLEMENTATION_HANDOFF` |
| P04 | E1 harness preparation may start early; E2 requires A spine, Native, Task/REST ALLOW, view contracts, fixture, environments and identity correlation. Alternatives: wait for all Tracks or integrate continuously against unstable contracts. | Objective entry criteria reduce integration churn; E2 remains critical after the vertical-slice components. | Harness adapters may change; criteria manifest remains stable. | `ACCEPTED_FOR_IMPLEMENTATION_HANDOFF` |
| P05 | Document/File is a public Golden Demo extension after the first MVS: synthetic/upload input, governed reference, isolated materialization, authorized read, artifact/review; controlled writeback optional. Alternatives: first-slice requirement or post-v0.2 deferral. | It demonstrates enterprise content without blocking the first runnable spine. It is stage E after C. | Persistence, delegated identity, writeback and sandbox debt retained; provider is removable. | `ACCEPTED_WITH_EVIDENCE_DEBT` |
| P06 | Select no real connector for the first slice; decide only after synthetic connector conformance exposes a need and before RC claim scope is frozen. Alternatives: Graph, Feishu, or no connector framework. | No repository evidence makes a real service essential; credentials/network would reduce reproducibility. Not on current critical path. | Real identity/protocol/rate evidence retained; fully reversible. | `DEFERRED` |
| P07 | Native first; OpenClaw exact-version external extension second; Hermes exact-version Experimental evidence only. Alternative orderings over-weight unevidenced external paths. | Native is implemented; OpenClaw is required for external Candidate claim; Hermes ED-S5-001 remains open. OpenClaw follows A, Hermes does not block release. | Exact versions, conformance and certification debt retained; adapters independently removable. | `ACCEPTED_WITH_EVIDENCE_DEBT` |
| P08 | Use an internal, versioned, non-frozen Compatibility Manifest candidate outside Stable Core; representation selected in S5-SPIKE-005 and approved before Provider integration. Alternatives: Core fields now or code-only metadata. | Makes versions/limitations testable without contaminating Core. B depends on its bounded Gate. | Serialization, range, upgrade and certification debt retained; candidate format replaceable. | `ACCEPTED_WITH_EVIDENCE_DEBT` |
| P09 | Preserve all 70 criteria with one primary future Session owner and layered component/conformance/E2E/Human evidence. Alternatives: only E2E or Track-local checklists. | Provides traceable release evidence and exposes unrun criteria honestly. It blocks RC only per applicability. | Test environment, timed usability and live external evidence debt retained. | `ACCEPTED_FOR_IMPLEMENTATION_HANDOFF` |
| P10 | Use stages A–I below; MVS precedes OpenClaw and Document/File extensions, then view completion, E integration, RC and Human acceptance. Alternative: one large integration release. | Gives rollback and Human Gates at architecture-sensitive boundaries. Longest chain is planning→A1→A2→A3→MVS components→views→E2/E4→RC→acceptance. | Estimates remain Session ranges, not calendar commitments. | `ACCEPTED_WITH_EVIDENCE_DEBT` |
| P11 | Normalize future writable work as one Session/conversation/branch/worktree/PR; use `IMPL` as the single coding type and separate SPIKE/TEST/REL. Alternative: combined or synonymous DEV/IMPL types. | Matches governance isolation and makes ownership auditable. First recommended authorization is S5-ARCH-007, then S5-IMPL-001 after its Gate. | Session map is replaceable before authorization. | `ACCEPTED_FOR_IMPLEMENTATION_HANDOFF` |
| P12 | Use evidence milestones and bounded deliverable counts with Day Start/Closeout records; no percentages. Alternative: time or percentage tracking. | Works across parallel Codex Sessions and aligns progress with Gates. Not on product critical path. | Process can be simplified without product impact. | `ACCEPTED_FOR_IMPLEMENTATION_HANDOFF` |

## 14. Evidence Debt and non-promotion

ED-S5-001 remains `OPEN`. Unassigned debt remains for representation,
migration, translation, routing/mixed versions, Conditions/Outcomes/Recovery,
Provider conformance, Console tolerance, side effects, third-party MCP,
managed packaging, exact profiles/versions, heartbeat thresholds, isolation,
Secret management, Skill metadata/scanning, Memory/retention, connector
identity/protocol, sandboxing, Customer/Edge and State portability. The plan
assigns prospective evidence owners but does not close or renumber debt.

Freeze state: `UNCHANGED / NOT_FROZEN`. Certification state: `UNCHANGED /
NOT_GRANTED`. Release acceptance: `NOT_GRANTED`. Contradictions found: `NONE`.

## 15. Authorized scope and validation contract

Authorized files are this artifact, `PROJECT_STATE.md`,
`docs/governance/REGISTRY.md`, and `docs/exec-plans/README.md`. Production/Core,
schemas, CRDs, ADRs, Runtime/Capability Providers, Console, tests,
dependencies, generated artifacts, release tags and release-completion notes
are out of scope.

Before review: validate authorized-path inventory, relative links, Registry /
Project State lifecycle consistency, source-path references, Track ownership,
dependency acyclicity, single-writer collisions, R01–R23 and 70-criterion
coverage, Evidence Debt preservation, non-promotion claims, secret patterns,
`git diff --check`, `make check`, and repository CI requirements. Existing
warnings must be reported separately.

## 16. Final Minimum Vertical Slice package

| Capability | Exact behavior / owner | Expected source scope / interface | Predecessor | Automated test / Demo evidence | Failure and completion |
| --- | --- | --- | --- | --- | --- |
| Business description | D accepts one bounded quality-work description | new authoring API/UI package; internal draft request | D mock contract | input/schema tests; captured `QI-1042` prompt | invalid/secret-like input rejected; complete when deterministic request is reproducible |
| Editable AI draft | D generates or loads a labelled, fully editable draft | D authoring service/UI; internal non-authoritative draft model | description | snapshot/edit tests; draft capture | generator unavailable uses labelled deterministic fixture; complete when every generated field is editable |
| Human approval | D records explicit approval before publish; A consumes approved intent | D approval API plus A publish boundary; internal until representation Gate | validation/Diff | unauthorized/missing approval negatives; audit record | fail closed with no desired-state write; complete when decision and actor correlate |
| Definition/Instance distinction | A represents one Definition/version and one stable selected Instance without assuming two new CRDs | A internal prototype package first; public API/CRD only after separate G2 | A1 decision | 1:N, distinct ID and replacement tests; Technical View evidence | no eligible Instance is explicit; complete when identity survives realization replacement |
| Native execution | B adapts current runtime behind selected Binding | B Provider-local package; internal Runtime adapter handoff | A2 + Native profile | managed Native conformance/E2E | unavailable is normalized; complete when execution returns correlated evidence |
| One Task | A/C adapts one current Task execution without breaking v0.1 | current controller through compatibility interpreter; existing public schema unchanged unless separately gated | A2/A3/B Native | current compatibility + new identity tests | translation failure/no Instance fails honestly; complete on one terminal correlated Task |
| REST Capability ALLOW | C authorizes one synthetic read operation before Provider invocation | internal Capability gateway/provider; no frozen public Contract | A2 + C fixture | ALLOW trace and Provider spy | deny/error produces no false success; complete on distinct normalized Capability Outcome |
| Platform Execution Identity | A generates one identity and propagates it unchanged through Task, Native, Capability and Outcome | internal execution envelope/projection | A2 | equality assertions across all hops | missing/mismatch fails integration; complete when every required hop matches |
| Business Outcome | C normalizes quality evidence; D projects one closure-readiness result | internal Outcome envelope and Product projection | Task + REST | deterministic expected-output assertion | incomplete evidence yields `UNKNOWN`/not-ready, never false ready; complete on correlated display |
| Synchronized views | D owns shared backend DTO; D Product and E Technical surfaces consume it | Console projection contract; internal API until separate API Gate | all above | cross-view reference/equality tests and screenshots | missing correlation shown explicitly; complete when same work opens in both views |

First-slice exclusions are full OpenClaw, Hermes execution, real Microsoft
Graph/Feishu, broad MCP, Document/File, controlled writeback, Customer-managed
and Edge/Desktop Runtime, cross-Runtime State portability, production-scale
multi-tenancy, Provider certification, Schema/Contract freeze and commercial
packaging. None is required by repository evidence for the first runnable
slice. Document/File follows as a public-Demo extension; OpenClaw follows as
the external-Runtime claim.

## 17. Track A implementation entry package

### A1 — representation/prototype decision work

- Objective: select an internal, replaceable representation for Definition,
  Instance, Platform Execution Identity, Binding references, Conditions,
  Outcomes and Recovery Assessment without presuming new CRDs.
- Recommended Session: `S5-ARCH-007` (decision) followed by
  `S5-IMPL-001` only after the Gate.
- Likely source scope: a new bounded package under `operator/src/agent_operator/`
  or a Human-approved Core package, with new tests under `operator/tests/`.
  Likely adaptation consumers are `operator/src/agent_operator/resources.py`,
  `task_controller.py`, `workflow_controller.py` and their matching tests, but
  those current files are read-only in A1. Existing CRDs and public schemas are
  also read-only in A1.
- Exclusive ownership: Core semantic envelope names, stable logical IDs,
  selected-Instance reference and placement/Binding reference semantics.
- Interface: internal prototype only. Any public API, CRD, status schema or
  lifecycle change is G2 and requires a separate explicit Gate.
- Tests: round-trip, 1:N identity, invalid/missing refs, upstream-field
  exclusion and additive-reader tolerance.
- Exit: Human-approved representation boundary and versioned fixture. Stop on
  CRD necessity, accepted-ADR conflict, competing source of truth or frozen
  Contract implication.

### A2 — identity and interface spine implementation

- Objective: implement generation and unchanged propagation of Definition,
  Instance and Platform Execution Identity references through the internal
  selection/Binding/execution envelope.
- Recommended Session: `S5-IMPL-002`; predecessor A1.
- Likely source scope: approved A package, narrowly bounded operator adapters,
  likely `operator/src/agent_operator/resources.py` and
  `task_controller.py`, plus owned tests in `operator/tests/`. Any
  `workflow_controller.py` touch is serialized with its declared owner. A2
  exclusively owns the identity envelope; B/C/D/E only consume it.
- Runtime Binding boundary: stable Core refers to Provider/package/profile and
  placement abstractly; B alone translates native configuration and IDs.
- Status/evidence boundary: A defines domain owner and correlation fields; B/C
  supply observations; E projects evidence. Exact vocabulary stays unfrozen.
- Tests/negatives: uniqueness, unchanged propagation, missing/duplicate ID,
  invalid selected Instance, native-ID substitution and realization
  replacement.
- Rollback: disable the internal spine and retain current v0.1 direct path;
  never write irreversible migration in this Session.
- Exit: versioned handoff passes component and v0.1 compatibility tests.

### A3 — compatibility interpreter and migration evidence

- Objective: translate current Agent/Task/Workflow references into the internal
  spine for the bounded slice, or prove that a later public migration Gate is
  necessary.
- Recommended Session: `S5-IMPL-003`; predecessor A2.
- Likely source scope: bounded compatibility interpreter/tests adjacent to
  `operator/src/agent_operator/task_controller.py`, `resources.py`, optionally
  serialized `workflow_controller.py`, and their matching `operator/tests/`.
  Existing CRDs remain unchanged absent a new G2 Gate.
- Backfill boundary: deterministic derived references are permitted only in
  fixtures/prototype scope; no durable bulk backfill, destructive conversion or
  cutover claim.
- Tests: legacy current manifests, mixed presence/absence, ambiguous mapping,
  rollback, current `make check` and no silent identity remap.
- Exit: one current Task can enter A2 without behavior regression, or an
  explicit architecture escalation identifies the public change required.

Track A entry requires this Checkpoint B handoff, the Implementation Entry Gate
and separate authorization of S5-ARCH-007. Downstream consumers are B Native,
C gateway/workflow, D projections and E harness. Track A stops for public CRD
or API change, Kubernetes source-of-truth change, lifecycle semantic change,
new persistent infrastructure, incompatible ADR drift, or a freeze request.

## 18. B/C/D parallel start packages

| Track/package | Class | Owner / writable paths | Upstream and fixture boundary | Merge dependency / risk / invalidation |
| --- | --- | --- | --- | --- |
| B exact-version and package investigation | `PREPARATORY_PARALLEL_SAFE` | S5-SPIKE-005; `experiments/` and evidence only | Candidate manifest fixture; no Stable Core | informs B; low conflict; invalid if upstream/package evidence changes |
| B Native/OpenClaw adapter scaffold | `PREPARATORY_PARALLEL_SAFE` | S5-SPIKE-005; isolated provider-local prototype | mock A identity/Binding fixture, versioned locally | cannot merge into runtime integration before A2/P08; medium invalidation |
| B Native Provider integration | `REQUIRES_TRACK_A_INTERFACE` | S5-IMPL-004; Native adapter package/tests | released A2 envelope | merge after A2/A3; medium runtime collision |
| B OpenClaw integration | `REQUIRES_VERTICAL_SLICE_SPINE` | S5-IMPL-005; isolated adapter/package/tests | A2 plus exact manifest and Native reference conformance | after MVS spine; medium; invalid if target unsupported |
| B Hermes execution | `DEFERRED` | S5-IMPL-006 recommendation only | Experimental fixture | optional, never blocks; invalid if no safe bounded target |
| C synthetic quality REST/MCP/document fixtures | `PREPARATORY_PARALLEL_SAFE` | S5-SPIKE-007; new fixture/service paths only | local provider protocol and spy; no Capability Contract | feeds C/E; low; invalid if accepted operation set changes |
| C authorization decision fixtures | `PREPARATORY_PARALLEL_SAFE` | S5-SPIKE-007; tests/evidence outside production | mock identity and deny-before-handoff vectors | feeds C; low; invalid if A identity fields change |
| C gateway + REST integration | `REQUIRES_TRACK_A_INTERFACE` | S5-IMPL-007; new gateway/provider modules/tests | A2 execution envelope | after A2; medium; no Task/Workflow schema write |
| C Task/Workflow/Outcome integration | `REQUIRES_VERTICAL_SLICE_SPINE` | S5-IMPL-008; bounded operator integration/tests | A3 + B Native + C gateway | serialized with Task/Workflow owner; high collision |
| C broad MCP/real connector/sandbox | `DEFERRED` | future separately scoped work | conformance evidence required | outside first slice; invalid absent claim need |
| D authoring UX and view wireframes | `PREPARATORY_PARALLEL_SAFE` | S5-SPIKE-008; isolated mocks/assets/evidence | versioned mock DTO only; no Console authoritative schema | feeds D; low; invalid if D DTO handoff materially changes |
| D draft/Diff engine prototype | `PREPARATORY_PARALLEL_SAFE` | S5-SPIKE-008; isolated prototype/tests | deterministic non-authoritative model | before D integration; low-medium |
| D authoring backend/publish boundary | `REQUIRES_TRACK_A_INTERFACE` | S5-IMPL-009; Console backend schema/service/tests | A1/A2 and C capability manifests | backend sole writer; high shared DTO risk |
| D Product View/re-execution | `REQUIRES_VERTICAL_SLICE_SPINE` | S5-IMPL-010; frontend and owned API consumer | D backend + C Outcome | after MVS backend; medium frontend risk |

No preparatory package may write Core identity models, Task/Workflow schemas,
Runtime or Capability Contracts, Console authoritative projections, Registry
or Project State. A mock is discarded or version-adapted when its handoff
differs from the accepted A interface.

## 19. Track E entry and subpackages

- E1 Conformance Harness preparation (`S5-TEST-005`) may begin after its own
  authorization with criterion manifest, runner skeleton and synthetic fixture
  loaders only. It cannot claim passes or redefine component interfaces.
- E2 Minimum Vertical Slice integration (`S5-IMPL-012`) requires: A2/A3 stable;
  managed Native available; one Task and REST ALLOW available; D Product View
  contract and E Technical evidence contract available; deterministic
  `QI-1042` fixture; unit/component/Kind/managed environments documented; one
  Platform Execution Identity visible across all required hops.
- E3 OpenClaw extension integration requires E2 and S5-IMPL-005 exact-version
  live plus deterministic Provider evidence. Native remains fallback.
- E4 Golden Demo timing/fallback/public evidence requires E2, E3 claim
  disposition, Document/File extension, synchronized views, clean bootstrap,
  failure matrix and Human usability rehearsal.

Hermes visibility is an optional labelled input to E4; it does not block E2,
RC or Release Acceptance. E2 entry fails if any required handoff is a mock,
identity correlation is incomplete, or the synthetic environment is not
reproducible.

## 20. Final Document/File and connector disposition

Document/File is `PUBLIC_GOLDEN_DEMO_EXTENSION_AFTER_FIRST_SLICE /
ACCEPTED_WITH_EVIDENCE_DEBT`. Its minimum boundary is synthetic/upload input,
governed reference with version/integrity, isolated workspace snapshot,
authorized Runtime read, Output Artifact, Human review, DENY/zero-call audit
and unchanged execution identity. Controlled writeback is optional and must be
approval-gated, version-checked and separately tested. It is not required for
the first MVS and is not deferred beyond v0.2.

The connector framework keeps Generic REST/OpenAPI, MCP, manifest,
delegated/service identity slots, Secret references, health/version, audit,
retry/rate-limit and conformance boundaries. A real connector choice is
`DEFERRED` until the synthetic provider and Document/File extension are
integrated and before RC scope approval if a public real-connector claim is
desired. Microsoft Graph and Feishu are not selected. Obsidian remains later
Vault Import/Edge.

## 21. Runtime Provider priority package

| Priority | Session / predecessor | Version/package/manifest | Identity, lifecycle, isolation and evidence | Fallback/conformance/release relevance |
| --- | --- | --- | --- | --- |
| 1 Native managed | S5-IMPL-004 / A2 + S5-SPIKE-005 | exact repository image/profile selected in spike; independently versioned Native Provider package; internal manifest | unchanged execution identity; provision/start/observe/replace/cleanup; Instance-scoped workspace/Secret refs; mismatch reject; normalized Conditions/Outcomes | deterministic unavailable fixture; required MVS and Golden path; applicable PCA/MRA |
| 2 OpenClaw managed/server | S5-IMPL-005 / A2,A3,spike and MVS spine | upstream target selected only by bounded live spike; isolated adapter/package and exact manifest | unchanged identity; register/heartbeat/execute/observe/cleanup; isolated profile/home/workspace; unsafe mismatch zero-invocation | visibly fall back to Native without claiming live success; required external Candidate/RC claim; PCA-18 live evidence |
| 3 Hermes Experimental | S5-IMPL-006 / S5-SPIKE-006 | exact target selected only if safe evidence exists; Experimental package/manifest | identity and lifecycle where feasible; isolation/normalization; limitations and ED-S5-001 visible | unavailable is non-blocking; optional PCA/MRA evidence; never certification or critical path |

No upstream version number is selected by this plan.

## 22. Session type and future portfolio rule

Use exactly these types:

- `ARCH`: Human-owned architecture or public-interface decision.
- `PLAN`: bounded sequencing, ownership and execution handoff; no code.
- `SPIKE`: disposable evidence or version-selection investigation; never a
  production claim.
- `IMPL`: the single coding Session type for bounded production or product
  implementation. Do not also use `DEV`.
- `TEST`: conformance or evidence implementation whose primary deliverable is
  test/evidence, not product behavior.
- `REL`: merge/integration, durable-main validation and release evidence; it
  does not invent implementation.
- `GOV`: governance rules, Registry model or policy foundation.

Every writable Session has one conversation, branch, isolated worktree and
primary PR. Relationships use `SOURCE_SESSION` and `DEPENDS_ON`; IDs never
embed another Session ID.

### Final recommended future Session portfolio

All rows are `RECOMMENDED_ONLY / NOT_ACTIVE / NOT_AUTHORIZED`. Effort is
focused Codex work plus local validation, excluding Human waiting and CI queue.

| ID / title | Type/Track/objective | Depends on / writable and excluded scope | Gates / output / PR | Effort/confidence/group/consumer |
| --- | --- | --- | --- | --- |
| S5-ARCH-007 — Core representation boundary | ARCH/A; decide A1 | S5-PLAN-001; decision artifact only; excludes implementation | Implementation Entry→Representation Gate; accepted decision artifact; docs PR | 0.5–1.5 sessions/high/sequential/A |
| S5-SPIKE-005 — Runtime target and Manifest evidence | SPIKE/B; exact Native/OpenClaw targets and manifest candidate | S5-PLAN-001; experiments/evidence; excludes production adapter | Entry authorization→Evidence Gate; spike report; evidence PR | 1–3 sessions/medium/Prep-1/B |
| S5-SPIKE-006 — Hermes bounded target evidence | SPIKE/B; optional target feasibility | S5-PLAN-001; experiments/evidence; excludes certification | explicit optional Gate→Evidence Gate; report; evidence PR | 1–2 sessions/low/Prep-1/B/E optional |
| S5-SPIKE-007 — Synthetic capability fixtures | SPIKE/C; REST/MCP/document/policy vectors | S5-PLAN-001; new isolated fixtures; excludes Contract/Core | Entry authorization→Fixture Gate; deterministic bundle; fixture PR | 1–2 sessions/high/Prep-1/C/E |
| S5-SPIKE-008 — Authoring and view mock prototype | SPIKE/D; draft/Diff/wireframes | S5-PLAN-001; isolated mocks; excludes Console authoritative DTO | Entry authorization→UX Fixture Gate; prototype evidence; isolated PR | 1–2 sessions/medium/Prep-1/D |
| S5-IMPL-001 — A1 representation prototype | IMPL/A; implement approved internal representation | S5-ARCH-007; new A package/tests; excludes public CRD/API | Representation Gate→A1 Exit; versioned fixture/package; interface PR | 1–2 sessions/medium/A/A2 |
| S5-IMPL-002 — A2 identity spine | IMPL/A; identity/routing envelope | S5-IMPL-001; A package/bounded adapters; excludes migration/Provider | A1 Exit→A2 Exit; tested handoff; spine PR | 2–4 sessions/medium/A/B–E |
| S5-IMPL-003 — A3 compatibility interpreter | IMPL/A; current-resource bridge/migration evidence | S5-IMPL-002; bounded operator interpreter/tests; excludes CRD change | A2 Exit→Compatibility Gate; bridge/evidence; compatibility PR | 1–3 sessions/medium/A/MVS |
| S5-IMPL-004 — Native managed Provider | IMPL/B; primary adapter | A2,SPIKE-005; Native Provider package/tests; excludes OpenClaw | A2/P08→Native Gate; managed package/evidence; Provider PR | 2–4 sessions/medium/Post-A/E2 |
| S5-IMPL-005 — OpenClaw Candidate Provider | IMPL/B; exact external adapter | A2,A3,SPIKE-005,E2 spine; isolated adapter/tests; excludes broad versions | External Entry→OpenClaw Evidence Gate; package/live bundle; Provider PR | 3–6 sessions/low-medium/Post-MVS/E3 |
| S5-IMPL-006 — Hermes Experimental adapter | IMPL/B; optional bounded path | SPIKE-006,A2; isolated adapter/evidence; excludes certification | optional Gate→Experimental Evidence Gate; labelled artifact; PR | 2–5 sessions/low/Optional/E4 |
| S5-IMPL-007 — Capability gateway and REST | IMPL/C; ALLOW/DENY + synthetic REST | A2,SPIKE-007; new gateway/provider/tests; excludes broad MCP/real connector | A2→Capability Gate; gateway evidence; PR | 2–4 sessions/medium/Post-A/MVS |
| S5-IMPL-008 — Workflow, Outcome and Document extension | IMPL/C; Task integration, Outcome, later document path | A3,IMPL-004,IMPL-007; bounded controller/provider/tests; excludes public schema absent Gate | Spine Gate→C Exit; integration + document extension; PR may split at document boundary | 3–6 sessions/low-medium/Post-A/D/E |
| S5-IMPL-009 — Authoring backend | IMPL/D; draft/Diff/validation/approval | A1,A2,IMPL-007,SPIKE-008; Console backend DTO/service/tests; excludes frontend | DTO Gate→D Backend Exit; projection API; backend PR | 2–4 sessions/medium/Post-A/D2/E |
| S5-IMPL-010 — Product View | IMPL/D; list/overview/work/correction | IMPL-008,IMPL-009; frontend + owned API consumer; excludes Technical View | Backend Exit→Product Gate; UI evidence; frontend PR | 2–5 sessions/medium/Post-MVS/E2 |
| S5-TEST-005 — Conformance harness | TEST/E1; criterion manifest and component/provider suite | Plan Gate; harness/fixtures/evidence; excludes component semantics | Test Entry→Harness Gate; runner/report schema; test PR | 2–4 sessions/high/Prep-1/E2–E4 |
| S5-IMPL-011 — Technical View | IMPL/E; correlated technical projection | A2,B/C/D handoffs; Technical UI/API consumer; excludes DTO ownership | E Entry→View Gate; UI/equality evidence; PR | 2–4 sessions/medium/Integration/E2 |
| S5-IMPL-012 — Golden Demo integration | IMPL/E; E2/E4 harness and deterministic package | required A–D,TEST-005; Demo fixtures/evidence; excludes new semantics | P04→Demo Gate; clean bundle/report; integration PR | 3–6 sessions/low-medium/Integration/REL |
| S5-REL-007 — Implementation Portfolio Integration | REL; integrate this accepted planning artifact | S5-PLAN-001 and PR #45; Registry/planning evidence only; excludes implementation | Human Close Confirmation→Durable-main Gate; portfolio integration record; REL PR | 1–2 sessions/high/serialized/S5-ARCH-007 |
| S5-REL-008 — Implementation integration baseline | REL; integrate Human-approved MVS bundle | merged component PRs; Registry/evidence only; excludes implementation | Merge Gates→Durable-main Gate; integration record; REL PR | 1–2 sessions/medium/serialized/RC |
| S5-TEST-006 — Release Candidate validation | TEST/E; exact final-head 70-criterion disposition | REL-008 + external/document scope; tests/evidence only | RC Entry→RC Human Gate; versioned report; evidence PR | 2–4 sessions/low/RC/REL-009 |
| S5-REL-009 — v0.2 Release Acceptance handoff | REL; assemble immutable RC provenance | TEST-006; Registry/release evidence only; excludes granting acceptance | RC Gate→Human Release Gate; acceptance candidate; REL PR | 1–2 sessions/medium/serialized/Human |

The chronologically next recommended Session is S5-REL-007 for Portfolio
integration. The first recommended architecture/implementation-entry Session
is `S5-ARCH-007`, downstream of that integration. Preparatory
`S5-SPIKE-005`, `S5-SPIKE-007`, `S5-SPIKE-008` and E1 `S5-TEST-005` are safe
parallel recommendations only after Portfolio integration and separate
authorization. `S5-SPIKE-006` is optional. All IMPL integration Sessions wait
for the stated A handoff.

## 23. Final shared-file single-writer map

| Scope | Owner Session | Readers / prohibited concurrent writers | Handoff / conflict resolution |
| --- | --- | --- | --- |
| Core identity representation | S5-IMPL-001 then S5-IMPL-002 | B–E read; all other writers prohibited | A1/A2 exit artifact; pause and return to S5-ARCH-007 Gate |
| public API/CRDs | no owner until separate G2 | all read; every planned Session prohibited | explicit architecture authorization and new owner Session |
| Task schema/controller | S5-IMPL-003, then S5-IMPL-008 only after handoff | A/B/D/E read | A3 Compatibility Gate; serialize PRs; architecture escalation on schema need |
| Workflow schema/controller | S5-IMPL-008 | A/B/D/E read; no parallel operator integration writer | C entry handoff; split/sequence on overlap |
| Runtime Provider Contract candidate | S5-ARCH-007 semantic boundary; S5-SPIKE-005 manifest evidence | B/E read; Provider Sessions cannot redefine | P08/Representation Gate; escalate divergence |
| Capability Contract candidate | S5-IMPL-007 bounded internal gateway | B/D/E read; Runtime cannot bypass or redefine | Capability Gate; architecture Session if public/frozen scope needed |
| Provider packages | S5-IMPL-004 Native; 005 OpenClaw; 006 Hermes, disjoint paths | E reads; no cross-package writer | per-Provider Exit Gate; B owner resolves shared SDK through serialized PR |
| Console backend schema/projection | S5-IMPL-009 | D frontend/E Technical read; no other backend DTO writer | versioned D handoff; D owner resolves consumers |
| Console frontend Product surfaces | S5-IMPL-010 | E reads shared types only | Product Gate; frontend paths partitioned from Technical View |
| Console frontend Technical surfaces | S5-IMPL-011 | D reads; no shared-type mutation without D | View Gate; change request returns to D DTO owner |
| Golden Demo fixtures | S5-IMPL-012 | all Tracks provide inputs; no competing expected-output writer | Demo Gate; E adjudicates fixture changes with source Track |
| Conformance Harness | S5-TEST-005, then TEST-006 final-head evidence | component Sessions contribute adapters only | Harness schema Gate; E resolves conflicts |
| Governance Registry | current authorized PLAN/REL Session only | all read; coding Sessions prohibited | merge-order handoff to corresponding REL Session |
| Project State | current authorized PLAN/REL Session only | all read; coding Sessions prohibited | same durable-main Gate as Registry |
| release documentation | S5-REL-009 | all contribute evidence; no pre-acceptance completion claims | Human Release Gate; release owner resolves |

No two simultaneously recommended parallel Sessions own the same write scope.

## 24. Acceptance primary-ownership manifest

The detailed evidence type, automation, fixture/environment, prerequisites and
Release relevance remain authoritative in Section 10. This manifest adds one
and only one primary future Session owner per criterion; contributing Sessions
do not become co-owners. Planned output roots are
`docs/evidence/s5/v0.2/<session-or-suite>/` for reports and owned test paths for
executable evidence. Unresolved debt is the named Section 14 category or
`NONE_BEYOND_EXECUTION`.

| Primary Session | Criteria owned exactly once | Count | MVS / Golden Demo / RC blocking summary | Primary evidence and retained debt |
| --- | --- | --- | --- | --- |
| S5-IMPL-009 | PDA-01, PDA-02, PDA-03, PDA-04, PDA-05 | 5 | all MVS/GD/RC except PDA-02 partly Human | unit/component/UI; authoring/approval evaluation debt |
| S5-IMPL-010 | PDA-06, PDA-07, PDA-08, PDA-10, PDA-11 | 5 | MVS/GD/RC | UI/E2E; Console tolerance debt |
| S5-IMPL-012 | PDA-09, PDA-12 | 2 | PDA-09 MVS/GD/RC; PDA-12 GD/RC Human | negative E2E/timed evidence; usability debt |
| S5-IMPL-002 | TDA-02, TDA-03 | 2 | MVS/GD/RC | identity/routing component; representation debt |
| S5-IMPL-004 | TDA-04 | 1 | MVS/GD/RC | Native E2E; exact profile debt |
| S5-IMPL-005 | TDA-05 | 1 | not MVS; GD/RC external claim | live+fixture; exact OpenClaw evidence debt |
| S5-IMPL-006 | TDA-06 | 1 | non-blocking all; Experimental only | label/claim; ED-S5-001 |
| S5-IMPL-007 | TDA-07, TDA-08 | 2 | MVS REST subset; GD/RC REST+MCP | provider/zero-call; third-party MCP debt |
| S5-IMPL-011 | TDA-01, TDA-09, TDA-10, TDA-11 | 4 | TDA-01/09 MVS; all GD/RC | projection/recovery UI; vocabulary/recovery debt |
| S5-IMPL-012 | ECA-01, ECA-03, ECA-04, ECA-05, ECA-07, ECA-08 | 6 | applicable MVS/GD/RC | integrated reports; environment/fallback debt |
| S5-TEST-006 | ECA-02, ECA-06 | 2 | MVS/GD/RC exact final head | CI/claim scans; execution only |
| S5-TEST-005 | PCA-01, PCA-02, PCA-03, PCA-04, PCA-05, PCA-07, PCA-08, PCA-09, PCA-17, PCA-20 | 10 | applicable MVS Native; GD/RC claimed Providers | contract/manifest fixtures; representation/range debt |
| S5-IMPL-004 | PCA-06, PCA-10, PCA-11, PCA-12, PCA-13, PCA-14, PCA-15, PCA-16 | 8 | Native subset MVS/GD/RC | Native component/managed evidence; certification/recovery debt |
| S5-IMPL-005 | PCA-18 | 1 | not MVS; GD/RC external claim | bounded live evidence; exact target debt |
| S5-IMPL-006 | PCA-19 | 1 | non-blocking all; Experimental | labels/claims; ED-S5-001 |
| S5-IMPL-004 | MRA-01, MRA-02, MRA-06, MRA-07, MRA-09 | 5 | MVS/GD/RC | managed Native/isolation; sharing/retention debt |
| S5-IMPL-005 | MRA-03, MRA-08, MRA-16 | 3 | not MVS; GD/RC where external mode claimed | live/status/manifest; heartbeat/version debt |
| S5-IMPL-006 | MRA-04 | 1 | non-blocking all; Experimental | bounded evidence; ED-S5-001 |
| S5-IMPL-007 | MRA-11, MRA-14, MRA-15, MRA-17 | 4 | MRA-14 and REST subset MVS; all GD/RC | auth/gateway; policy/sandbox debt |
| S5-IMPL-009 | MRA-05, MRA-12, MRA-13 | 3 | MRA-05 MVS; all GD/RC | projection/authority negatives; Memory policy debt |
| S5-IMPL-008 | MRA-10 | 1 | not MVS; GD/RC bounded Skill | assignment/integrity; Skill metadata/scanning debt |
| S5-IMPL-011 | MRA-18 | 1 | MVS/GD/RC | cross-view equality; Console tolerance debt |
| S5-IMPL-012 | MRA-19 | 1 | not MVS; GD/RC | fallback rehearsal; external availability debt |

Primary ownership total: `12 PDA + 11 TDA + 8 ECA + 20 PCA + 19 MRA = 70`.
Automation/Human status remains as Section 10: no criterion is declared passed
by this ownership assignment. R01–R23 are covered through those same 70 rows;
first-slice blockers are only the subsets explicitly marked MVS above.

## 25. Final release critical path and effort model

| Stage | Predecessor / blocking deliverable | Exit evidence / Human Gate | Effort / confidence / fallback | Non-blocking parallel work |
| --- | --- | --- | --- | --- |
| A Planning closure/integration | this PR | durable merged planning artifact; Implementation Entry + later close/REL Gates | 1–2 sessions/high/no implementation | prep authorization design |
| B Track A spine | A; A1 decision, A2 identity, A3 compatibility | versioned handoffs and current compatibility; Representation/A exits | 4–9 sessions/medium/retain current v0.1 path | B/C/D/E prep |
| C Minimum Vertical Slice | B; Native, REST ALLOW, authoring, Task, Outcome, views | deterministic QI-1042 MVS; MVS Human Gate | 8–15 sessions/low-medium/disable Product route and retain Native direct baseline | OpenClaw investigation, fixture refinement |
| D OpenClaw extension | B/C spine; exact package/live evidence | PCA-18 bundle; External Runtime Gate | 3–6 sessions/low-medium/label unavailable and use Native | Document/File, view refinement |
| E Document/File extension | C; authorized read/artifact/review | ALLOW/DENY/audit E2E; Demo Scope Gate | 2–5 sessions/medium/omit extension, not MVS | OpenClaw and UX |
| F Product/Technical completion | C plus D/E evidence contracts | cross-view and correction evidence; View Gate | 3–7 sessions/medium/use technical fixture views | harness execution |
| G E conformance/Demo integration | C–F; reproducible harness | applicable 70 dispositions, clean/timed/fallback evidence; Demo Gate | 4–8 sessions/low-medium/Native deterministic profile | Hermes labelled optional evidence |
| H Release Candidate validation | G and approved external/document scope | exact-final-head CI/security/claim/evidence report; RC Human Gate | 2–4 sessions/medium/remove unsupported optional claim | documentation review |
| I Human v0.2 Release Acceptance | H | explicit Human acceptance/REL record | Human-owned/low until H/no release | none material |

Current longest dependency chain:

```text
S5-PLAN-001 -> REL-007 -> S5-ARCH-007 -> IMPL-001 (A1) -> IMPL-002 (A2)
-> IMPL-003 (A3) -> IMPL-004 + IMPL-007 + IMPL-009
-> IMPL-008 + IMPL-010 -> IMPL-011 -> IMPL-012
-> REL-008 -> TEST-006 -> REL-009 -> Human Release Acceptance
```

The single-Codex mostly sequential scenario executes roughly 25–50 focused
Session-equivalents because component, integration and REL work queue. A
controlled parallel scenario uses Prep-1, then disjoint B/C/D work after A,
and is roughly 15–30 critical-path Session-equivalents while total work remains
similar. Optimistic critical path is 15–20; expected is 21–32; risk range is
33–50 Session-equivalents. Confidence is low-medium.

These are not calendar commitments. Codex execution is bounded implementation
and local validation; CI/integration adds queue and failure diagnosis; Human
Gate waiting is unbounded and excluded; external Runtime investigation may
invalidate packages; Demo refinement needs repeated rehearsal; rework reserve
is concentrated in A representation, OpenClaw, Console DTOs and integration.

## 26. Progress dashboard

```text
Overall product: RUN [COMPLETED_BASELINE] -> CONNECT [ACTIVE/current]
                 -> BUILD [FUTURE] -> GOVERN [FUTURE]
                 -> SCALE [FUTURE] -> TRUST [FUTURE]

v0.2: architecture/product contract [COMPLETE]
      -> implementation portfolio [ACCEPTED / FINALIZING/current]
      -> Portfolio integration [PENDING]
      -> Representation/API Gate [PENDING]
      -> vertical slice [NOT_STARTED]
      -> parallel implementation [NOT_STARTED]
      -> Golden Demo integration [NOT_STARTED]
      -> Release Acceptance [NOT_GRANTED]

S5-PLAN-001: Checkpoint A [COMPLETE] -> Checkpoint B [COMPLETE]
             -> Implementation Entry Gate [PASS_WITH_CONSTRAINTS]
             -> Checkpoint C [CURRENT]
             -> Human Close Confirmation [PENDING]

Future dependency: Track A [pending] -> B/C/D [pending]
                   -> E [pending] -> Release Gate [blocked until evidence]

Deferred: Hermes certification; Customer-managed and Edge/Desktop Runtime;
State portability; production multi-tenancy; all-version support; final
commercial packaging and final product brand.
```

## 27. Checkpoint C — Session finalization

Human dispositions:

- Checkpoint A Gate: `PASS_WITH_CONSTRAINTS`.
- Implementation Entry Gate: `PASS_WITH_CONSTRAINTS`.
- Portfolio: `ACCEPTED`; P01–P12: `ACCEPTED_AS_RECORDED`.
- Minimum Vertical Slice: `ACCEPTED_FOR_IMPLEMENTATION_HANDOFF`.
- Implementation Entry: `CONDITIONALLY_GRANTED`.
- Tracks A–E: `ACCEPTED_FOR_PORTFOLIO_PLANNING / NOT_ACTIVE /
  NOT_AUTHORIZED`.
- Future Sessions: `RECOMMENDED_ONLY / NOT_ACTIVE / NOT_AUTHORIZED`.
- Human Close Confirmation: `PENDING`; Session closed: `NO`.

`CONDITIONALLY_GRANTED` accepts the route only. Implementation has not begun.
The conditions are: close S5-PLAN-001 through Human confirmation; integrate PR
#45 through separately authorized S5-REL-007; separately authorize every
writable future Session; take any public API/CRD/existing-schema change through
the G2 Representation/API Gate; and enforce the accepted single-writer scopes.

Accepted order:

1. close S5-PLAN-001;
2. integrate PR #45 through recommended S5-REL-007;
3. separately authorize the narrow S5-ARCH-007 Representation/API Gate;
4. execute A1 representation selection after its authorization;
5. authorize and execute A2 identity/interface spine;
6. execute A3 compatibility evidence;
7. converge the Native MVS;
8. execute bounded B/C/D work against stabilized interfaces;
9. use E for integration, Conformance and Demo evidence; and
10. run separate RC and Human Release Acceptance Gates.

S5-ARCH-007 is `RECOMMENDED_ONLY / NOT_ACTIVE / NOT_AUTHORIZED` and downstream
of S5-REL-007. Its narrow scope is minimal Definition and Instance
representation, Platform Execution Identity representation/propagation,
Definition/Instance compatibility, Runtime Binding reference, existing
API/CRD impact, migration/backfill need, prototype alternatives and a G2 Human
decision. It must not reopen product positioning, Digital Employee, G01–G08,
the five-resource Candidate, Provider/managed-Runtime policy, Golden Demo or
Tracks A–E. It contains no implementation unless separately authorized.

Parallel-safe recommendations remain S5-SPIKE-005, S5-SPIKE-007,
S5-SPIKE-008 and S5-TEST-005, all inactive and unauthorized. Their isolated
evidence/mocks/fixtures may later be authorized only after Portfolio
integration and cannot redefine or write shared Core interfaces.

Final progress:

```text
Overall: RUN [COMPLETED_BASELINE] -> CONNECT [ACTIVE/current]
         -> BUILD [FUTURE] -> GOVERN [FUTURE] -> SCALE [FUTURE]
         -> TRUST [FUTURE]

v0.2: architecture/product contract [COMPLETE]
      -> implementation portfolio [ACCEPTED / FINALIZING/current]
      -> Portfolio integration [PENDING]
      -> Representation/API Gate [PENDING]
      -> Minimum Vertical Slice [NOT_STARTED]
      -> parallel implementation [NOT_STARTED]
      -> Golden Demo integration [NOT_STARTED]
      -> Release Acceptance [NOT_GRANTED]

S5-PLAN-001: Checkpoint A [COMPLETE] -> Checkpoint B [COMPLETE]
             -> Implementation Entry Gate [PASS_WITH_CONSTRAINTS]
             -> Checkpoint C [CURRENT]
             -> Human Close Confirmation [PENDING]
```

Finalization state: `CLOSING / AUTHORIZED / PASS / C — SESSION_FINALIZATION /
READY_TO_CLOSE`. Next recommended Session is `S5-REL-007 — Implementation
Portfolio Integration`, source S5-PLAN-001 and PR #45, state
`RECOMMENDED_ONLY / NOT_ACTIVE / NOT_AUTHORIZED`. Next action is
`WAIT_FOR_HUMAN_CLOSE_CONFIRMATION`.
