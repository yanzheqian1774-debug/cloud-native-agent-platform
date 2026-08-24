# S5-ARCH-006 — Digital Employee Golden Demo Scope and Acceptance Candidate v1

SESSION

- ID: `S5-ARCH-006`
- Title: v0.2 Digital Employee Golden Demo Scope & Acceptance Contract
- Type: `ARCH`
- Version: `v0.2 CONNECT — Digital Employee Technical Preview`
- Lifecycle: `CLOSING`
- Authorization: `AUTHORIZED`
- Checkpoint: `B — FINAL_SCOPE_CONVERGENCE_AND_IMPLEMENTATION_HANDOFF`
- Result: `READY_TO_CLOSE`
- Baseline: `acbad19a8af7e0b3762007ba708a90ed0be53d07`
- Candidate status: `SCOPE_ACCEPTED_WITH_CONSTRAINTS / READY_TO_CLOSE`

This artifact defines an implementation-ready Product Demo candidate. It does
not authorize implementation, select a persistence representation, add a CRD,
freeze a schema or Contract, certify a Provider, grant release acceptance, or
claim production readiness.

## 1. Evidence and claim boundary

### 1.1 Durable evidence reviewed

The Candidate applies the following evidence in descending specificity:

- [Project State](PROJECT_STATE.md), [Product](PRODUCT.md),
  [Roadmap](ROADMAP.md), [Architecture](ARCHITECTURE.md), and the
  [Governance Registry](docs/governance/REGISTRY.md);
- the accepted [v0.2 Core Schema Candidate v0](S5-ARCH-005-CORE-SCHEMA-DRAFT-V1.md);
- the accepted [Runtime Provider Architecture v1](architecture/s5/v0.2/baselines/s5-arch-002-runtime-provider-architecture-v1.md);
- the closed [Capability Contract spike](docs/evidence/s5/capability-contract/S5-SPIKE-003-CLOSEOUT.md)
  and [Agent Instance and Routing spike](docs/evidence/s5/agent-instance-routing/S5-SPIKE-004-CLOSEOUT.md);
- the [Hermes Evidence Debt](docs/evidence/s5/runtime/hermes/evidence/evidence-debt.md)
  and its failed [closure attempt](docs/evidence/s5/runtime/hermes/evidence/ed-s5-001-closure.md);
- current Agent, Task, and Workflow CRDs; Operator, Native Runtime, Workflow,
  Console, examples, manifests, and tests;
- the [ADR index](adr/README.md), accepted ADR-0001 through ADR-0006, the
  [v0.1 Golden Engineering Demo](examples/golden-engineering-demo/README.md),
  and [v0.1.0-alpha release notes](docs/releases/v0.1.0-alpha.md).

### 1.2 Evidence classification

| Area | Evidence-based state for this Candidate |
| --- | --- |
| Current v0.1 Control Plane | `IMPLEMENTED`: Agent/Task/Workflow CRDs, Operator execution and DAG orchestration, Native Runtime, model adapters, and read-only Workflow Console |
| Core five-resource model | `ACCEPTED_CANDIDATE`: Definition, Instance, Task, Workflow, Capability Definition; not a representation or CRD decision |
| Execution Identity, Bindings, Conditions, Outcomes, Recovery | `ACCEPTED_CANDIDATE_WITH_EVIDENCE_DEBT`: semantics accepted; representation and conformance not frozen |
| Native Provider path | `IMPLEMENTED_RUNTIME_WITH_PROVIDER_GAP`: current Native Runtime works, but the accepted Provider/Binding and Execution Identity path is not implemented |
| OpenClaw path | `PROTOTYPE_READY_WITH_EVIDENCE_DEBT`: architecture fit supported by spike evidence; absent from Production/Core; successful real-model terminal outcome and certification remain unproven |
| REST/MCP Capability paths | `PROTOTYPE_READY_WITH_EVIDENCE_DEBT`: isolation, authorization-before-invocation, and normalization supported in spike evidence; absent from Production/Core |
| Agent Instance routing/recovery | `PROTOTYPE_READY_WITH_EVIDENCE_DEBT`: deterministic spike evidence; absent from Production/Core and not a production recovery claim |
| Hermes | `EXPERIMENTAL / NOT_CURRENTLY_CERTIFIABLE`: ED-S5-001 remains open; successful external-model completion is unproven |
| Product and Technical Views | `NEW_PRODUCT_PROTOTYPE_REQUIRED`: current Console is read-only Workflow/Task projection only |
| AI-assisted authoring | `NEW_PRODUCT_PROTOTYPE_REQUIRED`: no current implementation |

Known ADR-0003/0004/0005 implementation drift is not changed by this artifact.
Bounded prototypes must either remain behind non-production interfaces or pass
the applicable future Architecture Gate before touching public APIs or
lifecycle ownership.

## 2. Product story candidate

### 2.1 Product boundary

**Digital Employee is a product/business projection, not a Core CRD.** It is a
synchronized presentation of one governed Agent Definition, its versions and
Agent Instances, assigned work, Runtime and Capability Bindings, approvals,
and Outcomes. Kubernetes remains the current Control Plane source of truth;
the Product View must not create a second desired-state authority.

The public story is:

> A quality leader describes a recurring quality problem in business language.
> The platform drafts a Quality Issue Identification and Closure Digital
> Employee. The leader reviews its role, workflow, capabilities, permissions,
> and approval points, edits and approves the draft, publishes it, assigns a
> synthetic quality issue, supervises governed execution, and sees a measurable
> closure-readiness outcome. Technical users can inspect the same execution,
> Instance selection, Runtime and Capability evidence, denial, recovery, and
> correction without changing the business-facing source of truth.

### 2.2 Questions the projection answers

| Business question | Product answer | Core/evidence projection |
| --- | --- | --- |
| Who is it? | Quality Issue Identification and Closure Digital Employee, owner, version, lifecycle state | Agent Definition identity and generation/version evidence |
| What is its role? | Detect, investigate, coordinate, and prepare quality issues for approved closure | Definition role, responsibilities, goals, instructions |
| What work can it perform? | Triage issues, correlate evidence, assess severity, propose corrective actions, prepare closure record | Task/Workflow and Capability Bindings |
| What may it use? | Approved synthetic issue API and quality-procedure knowledge service | Capability Definitions/Bindings and permission summary |
| What needs Human approval? | Publication, high-risk action, corrective-action acceptance, final closure | Human Gate interaction boundaries |
| Which Runtime realizes it? | Native or supported external Runtime label and health, with maturity badge | effective Runtime Binding and Provider/package evidence |
| Which Instance was selected? | Friendly Instance name and selection reason | selected Instance reference and routing evidence |
| What is running? | Current case, workflow stage, elapsed state, pending approval | Task/Workflow projections |
| What result was produced? | severity, suspected root cause, evidence completeness, action plan, closure readiness | Capability, Task, and Workflow Outcomes |
| What failed or was denied? | actionable exception and correction proposal | Conditions, authorization decision, Outcome, Recovery Assessment |
| How is it changed? | revise draft, inspect Diff, approve, republish, retest | Definition version/change evidence; no silent mutation |

### 2.3 Core mapping

```text
Digital Employee product projection
  -> Agent Definition
       -> embedded Runtime Binding template
       -> embedded Capability Bindings
       -> thin embedded Model Binding
       -> 1:N Agent Instances
  -> Task / Workflow
       -> Platform Execution Identity
       -> selected Agent Instance
       -> effective Runtime Binding -> Runtime Provider -> opaque native refs
       -> Capability Definition -> authorization -> REST/MCP Provider
       -> domain Conditions and Capability/Task/Workflow Outcomes
  -> Agent Instance Recovery Assessment
```

No sixth first-class Core logical resource is required.

## 3. Demo scenario decision candidate

### 3.1 Comparative evaluation

Scores are relative planning judgments (`High`, `Medium`, `Low`), not measured
release evidence.

| Criterion | Quality Issue Identification and Closure | Engineering Release Risk Manager |
| --- | --- | --- |
| Enterprise relevance | High across manufacturing/service quality | High, but concentrated in engineering organizations |
| Public comprehension | High: issue, evidence, action, approval, closure | Medium: release signals and engineering vocabulary need explanation |
| Digital Employee lifecycle coverage | High | Medium/High |
| Workflow depth | High: triage, correlate, assess, plan, approve, update | High: collect, analyze, review, decide |
| REST and MCP fit | Natural: issue system plus procedure/knowledge service | Natural: repository/CI plus engineering knowledge |
| ALLOW/DENY clarity | High: read issue allowed; unauthorized final close denied | Medium: read signals allowed; deployment/release mutation denied |
| Measurable business Outcome | High: time-to-triage, evidence completeness, closure readiness | High: risk coverage and release decision readiness |
| Runtime neutrality | High | High |
| Native/OpenClaw feasibility | Candidate-feasible; prototypes required | Candidate-feasible; existing Native engineering demo is a stronger seed |
| Hermes visibility | Optional experimental comparison | Optional experimental comparison |
| Implementation effort | Medium/High | Medium because current engineering fixtures can be reused |
| Demo reliability | High with synthetic local providers and deterministic fallback | High on Native current baseline |
| Open-source reproducibility | High with a small synthetic quality dataset | High with repository-local fixtures |
| Data/privacy | Low risk when fully synthetic | Low risk with repository-local/synthetic data |

### 3.2 Recommendation

**Primary public Product Demo Candidate:** Quality Issue Identification and
Closure Digital Employee.

It best communicates a managed Digital Employee to non-engineering audiences,
exercises authoring through correction, and makes authorization and business
Outcome visible without Runtime-native concepts.

**Secondary technical/Conformance example:** Engineering Release Risk Manager.

It preserves the durable engineering direction and current Golden Engineering
Demo investment. It should be retained as an internal engineering scenario,
open-source fixture, regression/conformance example, and deterministic fallback
for technical audiences. This recommendation does not delete or supersede its
evidence.

**Human decision QD-01:** accept or reject this primary/secondary designation.

### 3.3 Safe synthetic data

The Demo package uses only generated records:

- twelve fictional quality cases with product family, lot, region, timestamps,
  severity hints, inspection observations, and anonymized customer summaries;
- a fictional quality procedure and severity matrix exposed through a local
  deterministic MCP server;
- a local deterministic REST issue service with read, annotate, draft-action,
  and final-close operations;
- synthetic audit actors and approvals; and
- no customer identifiers, proprietary specifications, production endpoints,
  private repositories, or live credentials.

The focal case is `QI-1042`: repeated seal-integrity observations across two
synthetic lots. Expected evidence indicates a packaging-temperature control
gap. The Demo never presents model inference as verified physical causality;
it produces a reviewable suspected cause and corrective-action proposal.

## 4. Primary Digital Employee definition

| Dimension | Candidate scope |
| --- | --- |
| Target users | Quality manager (owner/approver), quality analyst (operator), platform engineer (Technical View) |
| Business problem | Quality evidence is fragmented; triage and closure preparation are slow and inconsistent |
| Role | Identify, investigate, and coordinate quality issues through approved closure preparation |
| Responsibilities | ingest issue; gather evidence; assess severity; correlate similar cases; propose suspected cause and corrective/preventive actions; request approval; prepare system update; report Outcome |
| Business goal | Reduce triage time while increasing evidence completeness and preserving Human accountability |
| Inputs | case ID, symptom/observation, product/lot metadata, optional business priority and desired completion time |
| Outputs | structured issue summary, evidence list, severity recommendation, suspected-cause rationale, corrective-action proposal, approval request, closure-readiness report |
| Required data | synthetic quality cases, inspection observations, procedure/severity matrix, action history |
| REST Capability | `quality-issue-records`: read case, add governed analysis note, create draft corrective action; final-close operation exists to demonstrate denial |
| MCP Capability | `quality-procedure-knowledge`: retrieve applicable procedure and severity/closure criteria |
| Human approval | draft publication; proposed corrective action; any high-risk mutation; final case closure |
| Runtime choices | Native primary; OpenClaw supported external prototype path; Hermes optional Experimental display/path |
| Failure path | unauthorized `closeIssue` is denied before Provider invocation; unavailable external Runtime is normalized and does not alter Core identity |
| Correction path | first Outcome lacks supplier-evidence verification; Technical View locates the missing Workflow step; AI proposes it; Human approves version 2; second run is compared |
| Business Outcome | triage completed; required evidence coverage reported; corrective plan prepared; closure readiness stated; approval/denial evidence auditable |

Candidate measures for the synthetic case:

- time to first structured triage;
- required-evidence coverage percentage;
- count of unresolved evidence gaps;
- authorization decisions and unauthorized Provider calls (`0` expected);
- corrective-action approval state; and
- closure readiness (`READY_FOR_HUMAN_CLOSURE`, `NOT_READY`, or `UNKNOWN` as
  product language only; exact Core Outcome vocabulary remains unfrozen).

## 5. AI-assisted authoring

### 5.1 Three primary creation steps

1. **Describe.** The user supplies one natural-language description containing
   the business need, desired role, expected result, and optionally data,
   constraints, or approval expectations.
2. **Review and edit.** AI generates a structured draft. The user edits it in
   natural language or structured fields, inspects validation and a meaningful
   Diff, and resolves blocking issues.
3. **Approve, publish, and test.** An authorized Human approves publication;
   publish creates/updates authoritative platform intent; the user submits a
   test Task and observes the Outcome.

### 5.2 Draft content and authority

| User supplies | AI may generate | Always user-editable |
| --- | --- | --- |
| business description; owner; optional constraints and sample case | name, role, responsibilities, goals, instructions, Workflow, Capability requirements, permission intent, Runtime recommendation, Human review points, expected Outcomes and acceptance tests | every generated field, including Workflow steps, permissions, Runtime recommendation, and Outcome expectations |

The draft is stored and labelled as `AI DRAFT`, with its source prompt,
generation time, generator/model evidence where supportable, validation state,
and base published version. It is not authoritative desired state. Only an
approved publish action may create or update platform intent.

### 5.3 Validation before publish

Publication must fail closed when any required check fails:

- name, role, goal, responsibilities, instructions, and at least one expected
  Outcome are present;
- Workflow graph is acyclic, references resolve, and required inputs/outputs
  connect;
- requested Capabilities and operations resolve to declared definitions;
- discovery and permission are independently evaluated;
- high-risk operations have a Human approval point and cannot be auto-approved;
- Runtime recommendation resolves only to an eligible declared option;
- Provider-specific configuration is not synthesized into unchecked Core
  intent;
- secrets or likely credential material are rejected/redacted;
- a material Diff against the published/base version is shown; and
- the approving Human and decision are recorded.

AI cannot silently escalate permission, publish to production, change Workflow,
Capability, Runtime, or authorization intent, or convert a recommendation into
a Human decision.

### 5.4 Candidate usability targets

These are prototype targets, not production SLAs:

- creation starts from one natural-language description;
- no more than three primary creation steps;
- technical fields are hidden by default;
- all generated content and material changes are editable and Diff-visible;
- at least one Human approval precedes publication; and
- the public describe-to-test path targets approximately five minutes, subject
  to prototype timing evidence.

## 6. Synchronized views

### 6.1 Product View — minimum surfaces

1. **Digital Employees list:** friendly identity, role, owner, lifecycle state,
   current Runtime label, Experimental badge, active work, last Outcome.
2. **Create/revise wizard:** Describe, Review, Approve/Publish/Test with draft
   state, structured preview, validation, and Diff.
3. **Digital Employee overview:** responsibilities, goal, version/latest
   change, business-friendly Runtime selection, Capabilities and permission
   summary, approvals, current work, history, and revise/republish actions.
4. **Work detail:** Task/Workflow progress, stage, approval wait, result,
   exception requiring action, business metrics, and comparable prior Outcome.

Raw CRD YAML, Kubernetes mechanics, Provider configuration, native IDs, and
translation objects are hidden by default. A link opens the correlated
Technical View without changing execution context.

### 6.2 Technical View — minimum drill-down

```text
Digital Employee
  -> Work (Task / Workflow)
  -> Execution (Platform Execution Identity)
  -> selected Agent Instance
  -> effective Runtime Binding / Provider / package / native correlations
  -> Capability Definition / Binding / authorization / REST or MCP invocation
  -> domain Condition / Outcome / Recovery Assessment
```

The view exposes Definition and version, all Instances and eligibility,
selection decision, effective Runtime Binding, Provider maturity and evidence
classification, opaque native correlations, Workflow/Task trace, Capability
authorization and invocation, Conditions, Outcomes, supportable events/log
links, Recovery Assessment, and configuration/version Diff.

### 6.3 One source-of-truth rule

Both views are read/write experiences over the same authoritative intent and
read projections over the same execution evidence. They share the same:

- Digital Employee-to-Definition mapping and published version;
- Task/Workflow references;
- selected Instance evidence;
- Platform Execution Identity;
- Capability invocation and authorization decision; and
- domain Outcome.

Product labels may summarize technical evidence but may not invent lifecycle
states or store competing desired state. Native identifiers are optional
`0:N` correlation evidence and never user-facing identity.

## 7. Timed public Demo script

### 7.1 Mandatory Golden Path (target: 10 minutes)

| Time | Demonstrator action | Expected visible result |
| --- | --- | --- |
| 0:00–0:40 | Describe the Digital Employee and desired quality Outcome | One natural-language input begins creation |
| 0:40–1:25 | Generate draft | Structured identity, role, responsibilities, Workflow, REST/MCP recommendations, permissions, Runtime, approvals, Outcomes |
| 1:25–2:15 | Review responsibilities and Workflow | Business fields visible; technical fields collapsed |
| 2:15–2:50 | Inspect Capability/permission recommendations | REST read/update intent, MCP retrieval, Human approval, and risk summary |
| 2:50–3:25 | Ask: “Verify supplier evidence before proposing closure” | Draft changes; no authoritative state changes |
| 3:25–4:00 | Inspect Diff and validation | Added step and permission impact highlighted; validation passes |
| 4:00–4:35 | Human approves and publishes | Approved version recorded; authoritative Definition intent created/updated |
| 4:35–5:00 | Resolve/create eligible Instance and submit `QI-1042` Task | Friendly Instance state; Platform Execution Identity appears |
| 5:00–6:15 | Native Runtime executes Workflow | selected Instance recorded; REST case read and MCP procedure retrieval; ALLOW decisions visible |
| 6:15–6:45 | Workflow attempts unauthorized final close | pre-invocation DENY; zero Provider invocation/native ref for denied action |
| 6:45–7:20 | Display Business Outcome | evidence coverage, severity, suspected cause, action plan, gaps, approval/closure readiness |
| 7:20–8:25 | Switch to Technical View | same Execution Identity, selected Instance, Native Binding, REST/MCP correlations, decisions, Conditions and Outcomes |
| 8:25–10:00 | Observe → correct → review → republish → re-execute | missing supplier-evidence step identified; bounded AI change Diff; Human approval; version 2 Outcome compared with version 1 |

The describe-to-first-test submission target is approximately five minutes;
the full narrative includes execution and correction.

### 7.2 Required external Runtime extension (target: 2 minutes)

Run the same Definition semantics and a fresh Task through an OpenClaw-bound
Instance. Show the same logical fields and a new Platform Execution Identity,
with OpenClaw Gateway/session/run identifiers only as opaque correlation
evidence. The claim is a bounded supported external Runtime prototype path,
not certification or production readiness.

### 7.3 Optional Experimental extension (target: 30 seconds)

Show Hermes in the Runtime selector or an optional prepared execution with the
label `EXPERIMENTAL / NOT CURRENTLY CERTIFIABLE — ED-S5-001 OPEN`. Do not claim
successful real-model completion, certification, or readiness. Hermes failure
or unavailability cannot fail the mandatory Golden Path.

### 7.4 Basic recovery extension (target: 1 minute)

Interrupt or replace the Native realization after a completed execution. Show
that the Agent Instance identity stays stable while realization evidence,
routing eligibility, and effective Runtime Binding are reassessed. Display an
Instance-owned Recovery Assessment only after the applicable semantic checks;
do not claim in-flight replay, memory/State continuity, or that restart alone
establishes recovery.

### 7.5 Failure and deterministic fallback

- If OpenClaw is unavailable, load a repository-bounded prerecorded
  fixture from the same build showing request, normalized unavailable Outcome,
  Execution Identity, and native evidence fields; then run the equivalent Task
  on Native. The fallback proves presentation and failure normalization only,
  not live OpenClaw success.
- If any live model is unavailable, use the deterministic local model fixture;
  label it as deterministic Demo execution.
- REST and MCP services run locally from pinned Demo fixtures. A startup
  preflight verifies their exact data and expected responses.
- Never silently substitute Native and call it an OpenClaw execution.

The public fallback does not satisfy OpenClaw implementation acceptance by
itself. Before the required external path is accepted, a bounded live run must
produce the expected normalized terminal evidence through the generic path.

## 8. Capability classification

Each proposed area has exactly one classification.

### 8.1 REQUIRED

| ID | Required v0.2 Demo capability |
| --- | --- |
| R01 | Digital Employee business projection over accepted Core |
| R02 | AI-generated editable draft from natural language |
| R03 | structured review, meaningful Diff, validation, and Human approval |
| R04 | publish and deterministic test Task |
| R05 | Agent Definition/Instance relationship and stable Instance identity |
| R06 | Task/Workflow assignment and execution |
| R07 | Platform Execution Identity propagated end to end |
| R08 | Runtime Binding and selected Instance evidence |
| R09 | deterministic Native primary Golden Path |
| R10 | bounded OpenClaw external Runtime prototype path with honest claim |
| R11 | provider-independent Capability Definition/Binding projection |
| R12 | one REST Capability and one MCP Capability path |
| R13 | authorization ALLOW and pre-invocation DENY with audit evidence |
| R14 | synchronized Product and Technical Views |
| R15 | separate Capability, Task, and Workflow Outcomes and business projection |
| R16 | one observe/correct/Diff/approve/republish/re-execute loop |
| R17 | bounded Instance recovery assessment without state-continuity claim |
| R18 | compatibility with implemented v0.1 Agent/Task/Workflow behavior |
| R19 | synthetic reproducible data, harness, tests, and external fallback |

### 8.2 EXPERIMENTAL

| ID | Experimental capability | Bounded claim |
| --- | --- | --- |
| X01 | Hermes Runtime path | Optional architecture/prototype visibility only; ED-S5-001 open; not certifiable; never blocks required paths |

### 8.3 DEFERRED

| ID | Deferred capability |
| --- | --- |
| D01 | full multi-tenancy, organization, and department hierarchy |
| D02 | complete RBAC/ABAC, Policy-as-code, and approval center |
| D03 | performance/compensation management and workforce analytics |
| D04 | cost/budget management and Agent FinOps |
| D05 | large-scale scheduling, autoscaling, and heterogeneous placement |
| D06 | cross-cloud migration and multi-cluster operation |
| D07 | State portability or continuity across Runtime replacement |
| D08 | advanced Model routing, fallback, and Model marketplace |
| D09 | Provider certification marketplace and third-party loading ecosystem |
| D10 | side-effect replay, durable deferred Capability execution, cancellation, and universal rollback |
| D11 | full Production Readiness, release acceptance, SLOs, and support commitments |

### 8.4 BLOCKED

| ID | Blocked capability/claim | Blocking evidence/gate |
| --- | --- | --- |
| B01 | Core Schema, Runtime Contract, or Capability Contract freeze | normative representation, compatibility, conformance, and Human freeze gates incomplete |
| B02 | Native/OpenClaw/Hermes Provider certification or broad supported-production claim | combination-scoped conformance/certification evidence absent |
| B03 | Hermes successful/certified Golden Path | ED-S5-001 open and successful real-model completion absent |
| B04 | production recovery or State continuity | recovery applicability/state/in-flight evidence incomplete |
| B05 | public API/CRD representation for Candidate resources | separate G2 architecture decision and migration evidence required |

Deferred and Blocked claims are not v0.2 Technical Preview Demo blockers.

## 9. Runtime and Capability acceptance levels

### 9.1 Runtime

| Runtime | Acceptance level | Minimum claim | Required evidence |
| --- | --- | --- | --- |
| Native | `PRIMARY_GOLDEN_PATH` | deterministic end-to-end Demo path through accepted logical semantics | Definition/Instance projection, selection, Binding, unchanged Execution Identity, Task/Workflow, REST/MCP, Outcomes, failure and bounded recovery evidence |
| OpenClaw | `SUPPORTED_EXTERNAL_RUNTIME_PATH` | bounded prototype demonstrates stable Core independence from Native and normalized external evidence | same generic semantic consumer, preserved Execution Identity, opaque native IDs, success/unavailability outcome, Provider-specific config hidden, deterministic fallback |
| Hermes | `EXPERIMENTAL` | optional bounded Provider-path visibility only | Experimental label, ED-S5-001 disclosure, no certification/real-model-success claim; absence does not block Demo |

`SUPPORTED_EXTERNAL_RUNTIME_PATH` is a Product Demo target, not present
Production/Core support or Provider certification.

### 9.2 Capability

REST and MCP are Capability Provider realizations, not separate Core
Capabilities. Acceptance requires provider-independent Capability identity and
operation, distinct discovery and authorization, an ALLOW path, a DENY before
Provider handoff, unchanged Platform Execution Identity, normalized
Capability Outcome, and opaque optional native correlation. The required Demo
uses read-only/idempotent or approval-gated operations; it makes no general
side-effect replay claim.

## 10. Acceptance contract

Automation potential values are `FULL`, `PARTIAL`, or `MANUAL_GATE`.

### 10.1 Product Demo acceptance

| ID | User/system action | Expected result | Required evidence | Automation | Owner track | Blocking scope |
| --- | --- | --- | --- | --- | --- | --- |
| PDA-01 | User enters one business description | Editable structured Digital Employee draft is created; raw technical config is unnecessary | UI/API fixture, draft snapshot | FULL | D | Product Demo |
| PDA-02 | User reviews generated content | Identity, role, responsibilities, goal, Workflow, Capabilities, permissions, Runtime, approvals and Outcomes are understandable/editable | usability script and captured draft | PARTIAL | D | Product Demo |
| PDA-03 | User makes a material natural-language or structured edit | Meaningful before/after Diff identifies every material change | deterministic Diff test and UI evidence | FULL | D | Product Demo |
| PDA-04 | User attempts publish before validation/approval | Publish fails closed with actionable errors | negative UI/API tests | FULL | D | Product Demo |
| PDA-05 | Authorized Human approves and publishes | approved version and decision recorded; authoritative platform intent changes only now | audit/version record and desired-state projection | PARTIAL | A/D | Product Demo |
| PDA-06 | User submits test case `QI-1042` | test Task begins without raw YAML or native ID input | end-to-end Demo record | FULL | D/E | Product Demo |
| PDA-07 | User supervises work | friendly progress, approval wait, exceptions, and current Runtime/Instance summary are visible | Product View snapshots | FULL | D/E | Product Demo |
| PDA-08 | Work completes | business Outcome shows severity, evidence, suspected cause, actions, gaps, approval and closure readiness | synthetic expected-output assertion | FULL | C/D/E | Product Demo |
| PDA-09 | Denied operation occurs | user sees policy denial as governance, not transport failure; no false completion | decision and zero-invocation evidence | FULL | C/E | Product Demo |
| PDA-10 | User revises and re-executes | version 2 is Human-approved and its Outcome is comparable with version 1 | Diff, approvals, two correlated Outcome records | PARTIAL | D/E | Product Demo |
| PDA-11 | User follows lifecycle/history | current state, work history, version/latest change and Experimental labels remain comprehensible | surface checklist | PARTIAL | D/E | Product Demo |
| PDA-12 | Timed creation flow runs | three primary steps; describe-to-test targets about five minutes | timed prototype evidence | MANUAL_GATE | D/E | Candidate usability only |

### 10.2 Technical Demo acceptance

| ID | User/system action | Expected result | Required evidence | Automation | Owner track | Blocking scope |
| --- | --- | --- | --- | --- | --- | --- |
| TDA-01 | Open Technical View from Product work | Same Digital Employee, Task/Workflow, version, and Platform Execution Identity open | cross-view identity assertions | FULL | E | Technical Demo |
| TDA-02 | Resolve or create Instance | Definition `1:N` Instance relationship and distinct stable Instance ID are visible | representation fixture and identity tests | FULL | A | Vertical slice |
| TDA-03 | Route Task targeting Definition | eligible set evaluated; selected Instance and reason recorded before Runtime handoff | deterministic routing tests | FULL | A/B | Vertical slice |
| TDA-04 | Invoke Native path | effective Binding and Native Provider evidence correlate without native identity becoming authoritative | end-to-end trace | FULL | A/B/E | Golden Path |
| TDA-05 | Invoke OpenClaw path | same generic Core semantics and unchanged identity cross external Provider; native IDs remain opaque | bounded live external-path run plus deterministic conformance fixture | PARTIAL | A/B/E | Required external path, not Native path |
| TDA-06 | Display Hermes | Experimental/non-certifiable label and ED-S5-001 shown | label and claim tests | FULL | B/E | Hermes scope only |
| TDA-07 | Invoke REST and MCP | each authorized invocation receives unchanged execution context and produces a distinct normalized Capability Outcome | Provider harness and traces | FULL | C/E | Required Capability paths |
| TDA-08 | Request unauthorized operation | DENY is recorded before Provider invocation; native invocation refs are empty | mock/spied Provider zero-call test | FULL | C/E | Governance path |
| TDA-09 | Inspect Conditions/Outcomes | Runtime/Instance Conditions and Capability/Task/Workflow Outcomes retain domain ownership | projection/schema assertions | FULL | A/B/C/E | Technical Demo |
| TDA-10 | Replace/interrupt realization | Instance identity remains stable; eligibility/Binding reassessed; Recovery Assessment is shown; no State-continuity claim | deterministic recovery test and UI evidence | FULL | A/B/E | Basic recovery only |
| TDA-11 | Inspect change | version/configuration Diff and supportable event/log links correlate to the same logical execution | traceability test | PARTIAL | D/E | Technical Demo |

### 10.3 Engineering and conformance acceptance

| ID | User/system action | Expected result | Required evidence | Automation | Owner track | Blocking scope |
| --- | --- | --- | --- | --- | --- | --- |
| ECA-01 | Run deterministic required-path suite | authoring, Native, OpenClaw fixture/live profile, REST, MCP, ALLOW, DENY, views, correction and recovery cases pass | versioned test report | FULL | A–E | Checkpoint implementation acceptance |
| ECA-02 | Run current repository tests | v0.1 Agent/Task/Workflow/API/Console behavior remains compatible | `make check`, targeted compatibility tests | FULL | A–E | Required compatibility |
| ECA-03 | Run failure matrix | invalid draft, unresolved Capability, no eligible Instance, Runtime unavailable, Provider error, DENY, stale/unknown recovery are deterministic and fail honestly | negative test report | FULL | A–E | Applicable required path |
| ECA-04 | Start Demo from clean environment | synthetic data and local services reproduce without private data or credentials | documented bootstrap and hashes/versions | PARTIAL | E | Public Demo |
| ECA-05 | Disable external Runtime | deterministic fallback executes and cannot be mistaken for live OpenClaw success | fallback test and visible label | FULL | B/E | Public reliability |
| ECA-06 | Scan claims and artifacts | no freeze, certification, production, release, private-data, or secret claim is introduced | claim linter/review and secret scan | PARTIAL | E | Entire Candidate |
| ECA-07 | Verify one source of truth | Product/Technical views derive from same Core refs; Console has no competing database/desired state | repository/projection tests | FULL | D/E | Architecture boundary |
| ECA-08 | Verify classification/traceability | every required capability maps to acceptance evidence and every Demo step maps to Product/Core | completeness check | FULL | E | Scope acceptance |

### 10.4 Required-capability coverage

| Required IDs | Acceptance coverage |
| --- | --- |
| R01–R04 | PDA-01–PDA-06, ECA-07 |
| R05–R09 | TDA-02–TDA-04, ECA-01–ECA-03 |
| R10 | TDA-05, ECA-01, ECA-05 |
| R11–R13 | PDA-09, TDA-07–TDA-08, ECA-03 |
| R14–R16 | PDA-07–PDA-11, TDA-01/TDA-11, ECA-07 |
| R17 | TDA-10, ECA-03 |
| R18 | ECA-02 |
| R19 | ECA-01/ECA-04–ECA-06/ECA-08 |

## 11. Implementation gap map

| Required area | Gap classification | Evidence and minimum gap |
| --- | --- | --- |
| Digital Employee projection | `NEW_IMPLEMENTATION_REQUIRED` | product concept accepted; no current projection |
| AI authoring/review/Diff/approval | `NEW_IMPLEMENTATION_REQUIRED` | absent from current code; Human Gate representation remains thin |
| Definition/Instance | `PROTOTYPE_REQUIRED` | accepted Candidate and spike evidence; current Agent only; representation undecided |
| logical routing | `PROTOTYPE_REQUIRED` | spike supported; current Task calls same-name Service directly |
| Platform Execution Identity | `PROTOTYPE_REQUIRED` | accepted embedded value; not in current Task/Workflow/runtime path |
| Runtime Binding/provider resolution | `PROTOTYPE_REQUIRED` | accepted architecture; current Agent embeds runtime type/image and Operator constructs resources |
| Native Provider | `EXISTS_WITH_GAP` | Native Runtime and deterministic path exist; accepted Provider/Binding/identity chain does not |
| OpenClaw Provider | `PROTOTYPE_REQUIRED` | architecture/spike input exists; no Production/Core adapter; live-success/conformance debt |
| Hermes Experimental path | `EVIDENCE_REQUIRED` | experimental evidence exists; ED-S5-001 open; optional only |
| Capability Definition/Binding | `PROTOTYPE_REQUIRED` | accepted Candidate/spike; current Agent has string list only |
| REST Capability | `PROTOTYPE_REQUIRED` | spike evidence only |
| MCP Capability | `PROTOTYPE_REQUIRED` | deterministic local spike evidence; third-party evidence debt |
| authorization | `NEW_IMPLEMENTATION_REQUIRED` | no current enterprise authorization; spike proves deny-before-handoff shape |
| Task/Workflow | `EXISTS_WITH_GAP` | current CRDs/controllers/DAG work; Instance target, identity, richer Outcomes/Human Gate absent |
| Conditions | `EXISTS_WITH_GAP` | Agent conditions exist; accepted domain/four-way/freshness model not represented |
| Outcomes | `PROTOTYPE_REQUIRED` | current Task result and Workflow phase exist; domain Outcome separation absent |
| Recovery | `PROTOTYPE_REQUIRED` | spike only; current restart/readiness cannot be called semantic recovery |
| Product View | `NEW_IMPLEMENTATION_REQUIRED` | current Console has no Digital Employee management/authoring |
| Technical View | `EXISTS_WITH_GAP` | current read-only Workflow DAG projection is a seed; missing Core/Provider/identity/capability/recovery detail |
| v0.1 compatibility | `EVIDENCE_REQUIRED` | accepted additive direction; mapping/backfill/mixed behavior not implemented or tested |
| deterministic tests | `NEW_IMPLEMENTATION_REQUIRED` | current tests cover v0.1; spike harnesses are evidence, not integrated conformance |
| Demo packaging/data/fallback | `NEW_IMPLEMENTATION_REQUIRED` | current engineering demo is reusable secondary seed; quality scenario absent |
| documentation | `NEW_IMPLEMENTATION_REQUIRED` | implementation/runbook docs await approved implementation |

No row equates architecture readiness with implementation completion.

## 12. Minimum vertical slice

Implement first, after a separate Human implementation authorization:

```text
business description
  -> generated editable Digital Employee draft
  -> validation + Diff + Human approval
  -> published Agent Definition projection
  -> one stable Agent Instance
  -> Definition-targeted Task and selection evidence
  -> Native Runtime
  -> one read-only REST Capability with ALLOW
  -> Platform Execution Identity propagated unchanged
  -> Capability and Task Business Outcome
  -> synchronized Product and Technical Views
```

This slice deliberately excludes MCP, OpenClaw, correction, and recovery until
the identity/authority spine is proven. It must preserve v0.1 compatibility and
use an approved non-production representation or receive any required G2
decision before public API/CRD changes.

## 13. Implementation portfolio candidate

Session IDs remain unassigned and all tracks remain unapproved.

| Track | Proposed Session type / objective | Dependencies | Write scope / likely shared files | Conflict risk | Required tests / artifact | Human Gate | Parallelism |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A — Core Representation and Execution Identity | `ARCH then SPIKE/DEV`: choose bounded representation; prove Definition/Instance, routing, identity and v0.1 translation | this Scope Gate; any G2 representation decision | candidate prototype area; Operator/API projection; Task/Workflow schemas only if separately approved | High: Task/Workflow/Core contracts | identity, mapping, routing, restart/delete/recreate, compatibility; representation decision + PR | Representation/API Gate and implementation authorization | Starts first; interface owner for B–E |
| B — Runtime Provider: Native/OpenClaw | `SPIKE then DEV`: adapt Native differential path and bounded OpenClaw external path behind accepted boundary | A identity/Binding interface; Runtime ADR clarification when production boundary requires it | Runtime Provider prototype, Native adapter, OpenClaw adapter, fixtures | Medium/High: shared provider interface and execution envelope | unchanged consumer, Binding translation, success/unavailable, opaque refs, fallback; separate PR(s) | Runtime prototype/claim Gate | Parallel after A interface stabilizes |
| C — Capability/Workflow/Authorization | `SPIKE then DEV`: Capability definitions/bindings, REST/MCP, ALLOW/DENY, Workflow/Outcomes | A identity; approved authorization/Human Gate boundary | Capability prototype/providers, Workflow integration, policy stub/fixture | High: execution envelope, Task/Workflow | REST/MCP, zero-call DENY, outcome ownership, DAG compatibility, error matrix | Capability prototype/authorization Gate | Parallel with B after A interface |
| D — AI Authoring and Product View | `PRODUCT/SPIKE then DEV`: three-step draft/review/publish flow and Digital Employee projection | accepted product story; A projection contract; Human approval representation | Console frontend/backend and draft/publish service boundary; no separate desired-state DB | High: Console APIs and projections | draft edit, Diff, validation, approval, source-of-truth, usability; Product prototype PR | Product UX and authority Gate | UX prototype can start; integration follows A |
| E — Technical View, Observability, Demo Harness | `DEV/TEST/SOLUTION`: correlated Technical View, synthetic services/data, packaging, timing and fallback | A–D integrated interfaces | Console projection, test/e2e harness, examples/docs | Medium: consumes all tracks | cross-view correlation, E2E matrix, clean bootstrap, fallback, claims/secret scans; Solution PR | Golden Demo execution Gate | Harness skeleton parallel; final integration last |

### 13.1 Parallel work map

```text
Scope Gate
  -> A representation/identity spine
       |-> B Native/OpenClaw
       |-> C Capability/Workflow/Authorization
       `-> D Authoring/Product View
              \      |      /
               -> E integration, Technical View and Demo harness
```

Shared-interface ownership stays with Track A. Tracks B and C must not invent
separate execution envelopes. Track D must not introduce a second desired-state
store. E consumes interfaces and owns end-to-end fixtures; it does not redefine
them. High-conflict public API/CRD, Task/Workflow, Console schema, and shared
identity files must be sequenced or isolated by explicit ownership.

## 14. Architecture exit rule

Broad architecture work exits and bounded implementation planning may be
authorized when Humans accept:

1. Quality Issue Identification and Closure as primary and Engineering Release
   Risk Manager as secondary;
2. the three-step AI authoring and authority boundary;
3. synchronized Product and Technical Views;
4. exact Required/Experimental/Deferred/Blocked classifications;
5. the testable layered acceptance contract;
6. the minimum vertical slice; and
7. the track boundaries, dependencies, and conflicts.

Schema Freeze, Contract Freeze, Provider Certification, complete Evidence Debt
closure, and Production Readiness are not prerequisites for a bounded
prototype. Uncertainty that does not block the vertical slice remains
claim-scoped debt or deferred work. No implementation begins from this
artifact alone.

## 15. Evidence debt and bounded spike recommendations

| Evidence debt | Scope blocked | Bounded follow-up |
| --- | --- | --- |
| representation, serialization, migration/backfill | public API/CRD and freeze | representation spike plus Human G2 Gate where applicable |
| unchanged identity through combined Runtime + Capability path | Contract conformance/freeze | minimum-slice conformance harness |
| OpenClaw successful terminal result and dependency recovery | broad supported/certified claim | bounded external Runtime live spike; keep fixture fallback |
| Native/OpenClaw Provider combination evidence | certification/production | combination-scoped conformance after Contract profile exists |
| third-party MCP and side effects/deferred execution | broad MCP/side-effect claims | Demo stays local/read-only/idempotent; later dedicated spikes |
| approval/authorization representation | enterprise governance claim | bounded prototype with synthetic actor/policy evidence; no full RBAC claim |
| Condition/Outcome/Recovery vocabulary | freeze and production recovery | deterministic four-way/failure/replacement conformance |
| mixed-version and Console old-client tolerance | migration/cutover readiness | differential compatibility suite |
| Hermes ED-S5-001 | Hermes success/certification/readiness | no retry in this Session; optional Experimental display only |
| timed usability and public reliability | usability target/Demo acceptance | instrumented rehearsal from clean environment |

## 16. Open Human decisions

| ID | Decision | Recommendation / effect |
| --- | --- | --- |
| QD-01 | Primary and secondary scenario | accept Quality Issue primary; Engineering Release Risk secondary |
| QD-02 | Authoring flow and five-minute target | accept as Candidate, subject to prototype evidence |
| QD-03 | Required/Experimental/Deferred/Blocked set | accept exact Section 8 boundary |
| QD-04 | Product/Technical minimum surfaces | accept as v0.2 scope, not full Console design |
| QD-05 | Acceptance contract and minimum slice | authorize subsequent planning only after acceptance |
| QD-06 | Implementation portfolio/parallel boundaries | accept tracks without assigning Session IDs |

Final brand, serialization, API/CRD count, Contract freezes, Provider
certification, release acceptance, production readiness, and commercial model
remain outside this Gate.

## 17. Contradiction and stop-condition review

| Check | Result |
| --- | --- |
| Requires private systems/data | No; synthetic local data/providers defined |
| Requires sixth Core resource | No; Digital Employee is a projection |
| Reinterprets current CRDs | No; implementation-neutral/additive Candidate and compatibility requirements preserved |
| Requires code in this Session | No; gaps become future tracks/spikes |
| Requires Hermes stable claim | No; Experimental only |
| Conflicts with accepted Core | None found |
| Resolves known ADR drift silently | No; drift retained and future Gates required |

## 18. Historical Checkpoint A recommendation

This was the state presented to the Human Golden Demo Scope Gate. Section 19
records its resolution and Section 28 is the current Session state.

- Status: `PASS`
- Result: `GOLDEN_DEMO_SCOPE_CANDIDATE`
- Production/Core change: `0`
- Schema change: `0`
- CRD change: `0`
- ADR change: `0`
- Runtime Provider change: `0`
- Capability Provider change: `0`
- Console change: `0`
- Test source change: `0`
- Next action at Checkpoint A: `WAIT_FOR_HUMAN_GOLDEN_DEMO_SCOPE_GATE`
- Next gate at Checkpoint A: `Human S5-ARCH-006 Golden Demo Scope Gate`

# Checkpoint B — Final Scope Convergence and Implementation Handoff

Sections 1–18 remain the evidence and Checkpoint A candidate record. The Human
Gate below resolves its open scope decisions. This section is the authoritative
implementation-planning handoff where a Checkpoint B table refines an earlier
candidate table. It still grants no implementation authorization.

## 19. Human Golden Demo Scope Gate

**HUMAN DECISION: `PASS_WITH_CONSTRAINTS`**

| ID | Decision | Disposition | Binding constraint |
| --- | --- | --- | --- |
| G01 | Primary public v0.2 Demo: Quality Issue Identification and Closure Digital Employee | `ACCEPTED_AS_V0_2_CANDIDATE` | safe synthetic and reproducible data only |
| G02 | Secondary technical example: Engineering Release Risk Manager | `ACCEPTED_AS_SECONDARY` | deterministic engineering, testing, and Conformance evidence; must not compete with the primary public story |
| G03 | business description → AI draft → editable preview → Diff/validation → Human Review → publish → test | `ACCEPTED_WITH_HUMAN_AUTHORITY_CONSTRAINT` | draft is non-authoritative; material content editable; Human approval required; no silent permission escalation; Provider translation remains Provider-owned |
| G04 | Product and Technical Views are both required | `ACCEPTED_AS_REQUIRED` | same Core references and Platform Execution Identity; no competing source of truth |
| G05 | Native primary; OpenClaw supported external-path Candidate; Hermes Experimental/not certifiable | `ACCEPTED_WITH_EVIDENCE_DEBT` | OpenClaw claim needs bounded live evidence; Hermes is optional, visibly Experimental, ED-S5-001 open |
| G06 | minimum vertical slice and Tracks A–E are the planning basis | `ACCEPTED_FOR_IMPLEMENTATION_PLANNING` | no implementation Session is active or authorized before close, integration, and separate authorization |

| G07 | Runtime integrations use independently versioned Provider Adapters between stable Core and exact upstream Runtime versions/profiles | `ACCEPTED_AS_V0_2_PROVIDER_POLICY` | v0.2 implementation evidence must select, pin and test exact Native, OpenClaw and Experimental Hermes targets; this Session selects no unsupported version |
| G08 | SaaS Control Plane with separately placed Runtime execution; Platform-managed is the v0.2 primary path, Customer-managed is architecture-ready/deferred, and Edge/Desktop is optional/deferred | `ACCEPTED_AS_V0_2_DEPLOYMENT_AND_ASSET_POLICY` | placement never replaces Platform identity; managed Native/OpenClaw and Experimental Hermes server paths; governed Skill/Memory assets; no Edge fleet implementation or desktop dependency |

All eight Human decisions are recorded exactly. QD-01 through QD-06 from
Section 16 are resolved by G01 through G06. G07 adds the versioned Runtime
Provider support policy within the accepted Core/Provider boundary; it creates
no new Core resource, implementation authorization, freeze, or certification.

## 20. Final capability classification and handoff

`BLOCKED_CLAIM_OR_GATE` means only that a named freeze, certification,
production, API, or supported claim cannot be granted without its evidence. It
does not automatically block bounded prototype implementation. Deferred work
is not a v0.2 blocker.

### 20.1 Required capability matrix

| ID | Product behavior | Technical mapping | Acceptance | Required evidence | Automatable | Track | Dependency | v0.2 blocker |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R01 | manage one Digital Employee in business language | projection over Definition, Instances, Bindings and work | PDA-01/02/07/11; ECA-07 | cross-view projection fixtures and source-of-truth tests | `YES/PARTIAL` | D/E | A projection contract | Yes: Product Demo |
| R02 | begin from natural language and receive editable draft | draft generation outside authoritative desired state | PDA-01/02 | deterministic prompt/draft fixture and edit tests | `YES/PARTIAL` | D | G03 authority boundary | Yes: Product Demo |
| R03 | review Diff/validation and approve | version/change evidence plus Human Gate boundary | PDA-03/04/05 | Diff, negative validation, approval/audit tests | `YES/PARTIAL` | D/A | R02; approval representation | Yes: Product Demo |
| R04 | publish and run deterministic test | approved Definition projection then Task | PDA-05/06; ECA-04 | publish authority test and clean test execution | `YES/PARTIAL` | D/E | R03; A execution interface | Yes: Product Demo |
| R05 | see stable Definition/Instance relationship | Definition `1:N` Instance, distinct Instance identity | TDA-02 | identity, restart, update and mapping tests | `YES` | A | approved bounded representation | Yes: vertical slice |
| R06 | assign and follow Task/Workflow | current-compatible Task/Workflow plus richer projections | PDA-06/07; ECA-02 | DAG and v0.1 differential tests | `YES` | A/C | R05 and execution interface | Yes: full Demo; Task only in first slice |
| R07 | correlate work end to end | embedded Platform Execution Identity propagated unchanged | TDA-01/03–08 | creation, persistence, propagation and mismatch tests | `YES` | A | representation and retry rules | Yes: vertical slice |
| R08 | understand selected Instance and Runtime | selected Instance plus effective Runtime Binding evidence | TDA-03/04 | eligibility, selection and Binding projection tests | `YES` | A/B | R05/R07 | Yes: vertical slice |
| R09 | execute deterministic Native Golden Path | current Native Runtime behind bounded Provider mapping | TDA-04; ECA-01/02 | Native end-to-end and v0.1 differential suite | `YES` | B | A interface spine | Yes: release Golden Path |
| R10 | run same semantics on OpenClaw | external Runtime Provider path; opaque native refs | TDA-05; ECA-01/05 | bounded live success plus conformance/fallback fixtures | `PARTIAL` | B/E | A interface; OpenClaw environment | Yes: full v0.2 Demo, not first slice |
| R11 | understand governed Capability assignment | Capability Definition and embedded Binding projection | PDA-02; TDA-07/08 | identity/version/operation and Binding tests | `YES` | C | A identity envelope | Yes: full Demo |
| R12 | use REST and MCP | two Provider realizations behind one Capability boundary | TDA-07; ECA-01/03 | local REST/MCP success/failure fixtures | `YES` | C/E | R11/R13 | Yes: REST in first slice; MCP in full Demo |
| R13 | see ALLOW and pre-invocation DENY | authorization separate from discovery/Provider | PDA-09; TDA-08 | zero-call DENY, ALLOW, audit and error tests | `YES` | C/E | bounded auth representation | Yes: full Demo; REST ALLOW in first slice |
| R14 | switch between synchronized views | shared Core refs and Execution Identity | TDA-01/11; ECA-07 | cross-view equality and no-second-store tests | `YES` | D/E | A/C projections | Yes: vertical slice |
| R15 | understand business result | separate Capability, Task and Workflow Outcomes | PDA-08; TDA-09 | domain ownership and projection tests | `YES` | A/C/D/E | R07/R11; Outcome representation | Yes: Task/Capability Outcome in first slice |
| R16 | correct, approve and compare a rerun | new Definition version and comparable fresh execution | PDA-10; TDA-11 | two-version Diff, approval and Outcome comparison | `YES/PARTIAL` | D/E | R03/R07/R15 | Yes: full Demo, not first slice |
| R17 | see bounded recovery assessment | stable Instance, reassessed Binding/eligibility, Instance-owned Recovery | TDA-10; ECA-03 | replacement, stale/unknown and no-continuity tests | `YES` | A/B/E | R05/R08; recovery predicates | Yes: full Demo only |
| R18 | preserve current v0.1 behavior | additive translator/projection over Agent/Task/Workflow | ECA-02 | current suite plus old/new differential fixtures | `YES` | A–E | every changed interface | Yes: all implementation |
| R19 | reproduce Demo and fallback safely | synthetic services/data, versioned harness and honest fallback | ECA-01/04–06/08 | clean bootstrap, fixture integrity, claim and secret scans | `YES/PARTIAL` | E | integrated A–D outputs | Yes: public Demo |

### 20.2 Other final classifications

| Classification | IDs | Final disposition |
| --- | --- | --- |
| `EXPERIMENTAL` | X01 Hermes path | optional and visibly Experimental; ED-S5-001 open; not part of mandatory Release Golden Path |
| `DEFERRED` | D01–D11 | unchanged from Section 8.3; none is a v0.2 blocker |
| `BLOCKED_CLAIM_OR_GATE` | B01–B05 | Section 8.4 claims retained: freezes, Provider certification, Hermes success/certification, production recovery/State continuity, and public API/CRD representation |

Every proposed capability is classified exactly once. The labels `BLOCKED` in
Checkpoint A Section 8.4 are normalized to `BLOCKED_CLAIM_OR_GATE` here without
changing their evidence or blocker scope.

## 21. Final acceptance matrix

The 31 non-duplicated criteria in Section 10 are the Product, Technical, and
Engineering/Conformance base criterion registry:
PDA-01–12 (`PRODUCT`), TDA-01–11 (`TECHNICAL`), and ECA-01–08
(`CONFORMANCE`). For Checkpoint B, `FULL`, `PARTIAL`, and `MANUAL_GATE` in the
Automation column normalize to `YES`, `PARTIAL`, and `NO`. Their existing
blocking-scope column remains binding. The prerequisite register below
completes every base criterion without duplicating its action, result,
evidence, owner, or scope. Section 33 adds the G07 Provider Conformance
criteria to the consolidated Checkpoint B acceptance registry.

| Criterion IDs | Layer | Prerequisite |
| --- | --- | --- |
| PDA-01–02 | `PRODUCT` | G01/G03; synthetic input and draft generator available |
| PDA-03–05 | `PRODUCT` | editable draft, version base, validator, Human approval boundary |
| PDA-06–08 | `PRODUCT` | approved publish, minimum identity/execution spine, Native and required Capabilities |
| PDA-09 | `PRODUCT` | authorization decision point and instrumented Provider |
| PDA-10 | `PRODUCT` | completed first execution, version/Diff/approval and comparable Outcome model |
| PDA-11 | `PRODUCT` | work/version projections and Runtime maturity metadata |
| PDA-12 | `PRODUCT` | integrated prototype and timed clean rehearsal |
| TDA-01 | `TECHNICAL` | same Core projection exposed to both views |
| TDA-02–04 | `TECHNICAL` | Track A bounded representation and Native Provider mapping |
| TDA-05 | `TECHNICAL` | stabilized A interface and bounded live OpenClaw environment |
| TDA-06 | `TECHNICAL` | maturity/debt metadata; no Hermes live success required |
| TDA-07–08 | `TECHNICAL` | Capability definition/binding, authorization and REST/MCP providers |
| TDA-09 | `TECHNICAL` | domain Condition/Outcome projections |
| TDA-10 | `TECHNICAL` | stable Instance identity and bounded recovery predicates |
| TDA-11 | `TECHNICAL` | version/configuration evidence and supportable event/log references |
| ECA-01 | `CONFORMANCE` | all Required integrated paths available in test profile |
| ECA-02 | `CONFORMANCE` | current v0.1 fixtures and unchanged compatibility baseline |
| ECA-03 | `CONFORMANCE` | normalized failures, stale/unknown evidence and controllable providers |
| ECA-04 | `CONFORMANCE` | clean bootstrap and synthetic dependency package |
| ECA-05 | `CONFORMANCE` | external Runtime disable switch and labelled fixture fallback |
| ECA-06 | `CONFORMANCE` | complete artifact/claim inventory |
| ECA-07 | `CONFORMANCE` | shared projection repository and no Console desired-state database |
| ECA-08 | `CONFORMANCE` | final capability, criterion and Core traceability registries |

### 21.1 Acceptance scopes

| Acceptance scope | Criteria/evidence required | Disposition |
| --- | --- | --- |
| Minimum vertical slice | PDA-01–09 except full Workflow/MCP; TDA-01–04, REST ALLOW portion of TDA-07, TDA-09 Task/Capability portion; ECA-02/07 | implementation entry evidence, not release acceptance |
| Full v0.2 Golden Demo | all PDA, TDA except optional Hermes live execution, ECA, and applicable PCA criteria; all R01–R19 | required for future Golden Demo Gate |
| Optional extended Demo | TDA-06 Hermes display/path and recovery extension presentation | optional; cannot fail mandatory Golden Path |
| External dependency fallback | ECA-04/05 plus visible non-live label and Native deterministic path | public reliability only; does not satisfy OpenClaw live acceptance |
| Release Gate evidence | successful Golden Demo Gate, compatibility, reproducibility, CI, bounded Runtime claims and separate release governance | evidence input only; Release Acceptance remains `NOT_GRANTED` |

## 22. Final implementation gap convergence

| ID | State | Concrete gap / affected component | Minimum implementation | Test evidence | Dependency | Track | Shared-file risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R01 | `NEW_IMPLEMENTATION_REQUIRED` | no Digital Employee projection; Console | derived projection and minimum surfaces | PDA-01/02/07/11, ECA-07 | A projection | D/E | High |
| R02 | `NEW_IMPLEMENTATION_REQUIRED` | no authoring service/UI; Console/product boundary | deterministic editable AI draft prototype | PDA-01/02 | G03 | D | Medium |
| R03 | `NEW_IMPLEMENTATION_REQUIRED` | no Diff/validation/approval; Console plus authority boundary | validator, version Diff, explicit approval record | PDA-03–05 | R02/A representation | D/A | High |
| R04 | `NEW_IMPLEMENTATION_REQUIRED` | no approved publish/test flow | publish adapter to authoritative intent and test Task | PDA-05/06 | R03/A | D/E | High |
| R05 | `PROTOTYPE_REQUIRED` | current Agent has no distinct Instance; prototype/Core representation | bounded Definition/Instance identity and projection | TDA-02 identity matrix | Human representation Gate as needed | A | High/single-writer |
| R06 | `EXISTS_WITH_GAP` | current Task/Workflow lacks richer targeting/identity/Human Gate | additive compatible Task/Workflow integration | current plus TDA/PDA flow | R05/R07 | A/C | High/single-writer |
| R07 | `PROTOTYPE_REQUIRED` | no Platform Execution Identity in current path | mint, persist/project and propagate unchanged | identity/conformance suite | bounded representation | A | High/single-writer |
| R08 | `PROTOTYPE_REQUIRED` | no logical selection/effective Binding in current path | eligibility, selection record and Binding projection | TDA-03/04 | R05/R07 | A/B | High |
| R09 | `EXISTS_WITH_GAP` | Native exists without accepted Provider/identity path | Native differential adapter/mapping | Native E2E and v0.1 differential | A stabilized interface | B | Medium |
| R10 | `PROTOTYPE_REQUIRED` | OpenClaw absent from Production/Core; live success debt | bounded external Provider path and fixture fallback | live TDA-05 plus ECA-05 | A interface/environment | B/E | Medium |
| R11 | `PROTOTYPE_REQUIRED` | string capabilities only | bounded Definition/Binding projection | identity/binding tests | A execution context | C | Medium/High |
| R12 | `PROTOTYPE_REQUIRED` | REST/MCP only in spike evidence | local deterministic Provider implementations | TDA-07 success/failure | R11/R13 | C/E | Medium |
| R13 | `NEW_IMPLEMENTATION_REQUIRED` | no enterprise authorization path | bounded decision interface and pre-handoff enforcement | zero-call DENY/ALLOW/audit | Human authority boundary | C | High |
| R14 | `NEW_IMPLEMENTATION_REQUIRED` | current Console only Workflow view | synchronized Product/Technical projections | TDA-01, ECA-07 | A/C contracts | D/E | High/single-writer Console schemas |
| R15 | `PROTOTYPE_REQUIRED` | current result/phase not separated domain Outcomes | bounded Capability/Task/Workflow Outcome projections | TDA-09/domain ownership | R07/R11 | A/C/D/E | High |
| R16 | `NEW_IMPLEMENTATION_REQUIRED` | no version correction loop | revise/Diff/approve/republish and compare | PDA-10 | R03/R15 | D/E | Medium |
| R17 | `PROTOTYPE_REQUIRED` | recovery exists only as spike evidence | stable identity replacement and Instance assessment | TDA-10/stale-unknown tests | R05/R08 | A/B/E | Medium/High |
| R18 | `EVIDENCE_REQUIRED` | additive mapping/mixed-mode unproven | differential compatibility harness and explicit translator | ECA-02 | every track | A–E | High |
| R19 | `NEW_IMPLEMENTATION_REQUIRED` | quality Demo package absent | synthetic data/services, bootstrap, fixtures, fallback and claims checks | ECA-01/04–06/08 | A–D integrated | E | Medium |

No Required capability is `EXISTS` without qualification. This reflects
current source, not architecture readiness.

## 23. Implementation portfolio handoff

All tracks are `PROPOSED / NOT_ACTIVE / NOT_AUTHORIZED`. No final Session IDs
are assigned.

### 23.1 Track A — Core Representation and Execution Identity

- Objective: establish the bounded identity/interface spine and v0.1-compatible
  projection for Definition, Instance, Task targeting, selection, Binding,
  Execution Identity, minimal Outcomes and recovery ownership.
- Input Contract: accepted Core Candidate, G04/G06, current v0.1 behavior.
- Output: approved prototype representation/interface, compatibility mapping,
  deterministic identity/routing/conformance evidence.
- Write scope: separately approved prototype/Core projection and relevant
  Operator/API tests; public CRD/schema only after G2 approval.
- Probable locations: `operator/`, `manifests/crd/`, `tests/`, a dedicated
  prototype area, and Console-facing projection schemas.
- Prohibited: silent CRD reinterpretation, API group change, freeze, Provider
  implementation, Console UX.
- Dependencies: Session close/integration and representation Gate.
- Shared files: Task/Workflow schemas/controllers, projection schemas,
  execution envelope.
- Conflict risk: High; single writer for identity and public representation.
- Required tests: identity lifecycle, routing, propagation, conflict/missing,
  v0.1 differential, recovery-negative fixtures.
- Completion result: `IDENTITY_INTERFACE_SPINE_READY_FOR_DEPENDENT_TRACKS`.
- Human Gate: bounded representation/implementation authorization.
- Parallel start: first; other track design may proceed read-only, integration
  waits for stabilized interfaces.

### 23.2 Track B — Runtime Provider: Native, OpenClaw and bounded Hermes Experimental Adapter evidence

- Objective: select exact upstream targets through evidence; produce
  independently versioned Native, OpenClaw, and bounded Experimental Hermes
  Adapter/package Candidates; validate versions; prove Native differential and
  bounded live OpenClaw paths; and collect feasible Hermes Experimental
  evidence behind one generic Runtime boundary.
- Input Contract: Track A Execution Identity, selected Instance and Binding;
  accepted Runtime Provider architecture.
- Output: Provider package Candidates, pinned-version evidence, Compatibility
  Manifest Candidate, version-mismatch tests, Runtime-specific evidence
  bundles, Native mapping, OpenClaw external prototype, bounded Hermes
  Experimental evidence where feasible, normalized evidence, deterministic
  fallback, and supported/experimental claim recommendation.
- Write scope: separately approved Runtime Provider prototype/adapters,
  fixtures and tests.
- Probable locations: new bounded Provider module/prototype, `runtime/`,
  Operator handoff integration, Demo fixtures.
- Prohibited: Runtime Contract freeze, certification, Hermes remediation,
  Core Provider-family fields, production claim.
- Dependencies: stabilized A interface; bounded OpenClaw environment.
- Shared files: execution envelope, Binding projection, Operator handoff,
  integrated harness.
- Conflict risk: Medium/High.
- Required tests: unchanged consumer; exact match, untested and unsupported
  version behavior; Native differential; OpenClaw live terminal result; Hermes
  Experimental behavior where feasible; Binding/configuration translation;
  Execution Identity propagation; native correlation; Condition/Outcome
  normalization; unavailable/error/recovery evidence; cleanup; fallback.
- Completion result: `NATIVE_AND_OPENCLAW_DEMO_PATHS_EVIDENCED`.
- Human Gate: Runtime prototype and supported-claim evidence Gate.
- Parallel start: with C/D after A interface stabilization.

### 23.3 Track C — Capability / Workflow / Authorization

- Objective: implement bounded Capability Definition/Binding projection,
  REST/MCP realizations, pre-handoff authorization and domain Outcomes inside
  the required Workflow.
- Input Contract: A identity envelope, Capability Candidate, current Workflow
  compatibility, G03 authority constraint.
- Output: governed REST/MCP paths, ALLOW/DENY audit evidence, Workflow and
  Capability Outcomes.
- Write scope: separately approved Capability prototype, authorization fixture,
  Workflow integration and tests.
- Probable locations: new Capability prototype/module, `operator/` Workflow and
  Task integration, `tests/`, Demo providers.
- Prohibited: full RBAC/ABAC, policy language, Capability Contract freeze,
  marketplace, broad side-effect/replay guarantee.
- Dependencies: A interface; bounded authorization representation.
- Shared files: Task/Workflow controllers and schemas, execution envelope,
  Outcome projection, Demo harness.
- Conflict risk: High; Task/Workflow integration must be sequenced with A.
- Required tests: REST/MCP success/failure, discovery vs authorization,
  zero-call DENY, identity propagation, Outcome ownership, DAG compatibility.
- Completion result: `GOVERNED_CAPABILITY_WORKFLOW_PATH_EVIDENCED`.
- Human Gate: Capability prototype/authorization Gate.
- Parallel start: Provider-local work after A interface; shared Workflow writes
  only after A handoff.

### 23.4 Track D — AI-assisted Authoring and Product View

- Objective: deliver the accepted three-step authoring flow and business
  projection without creating another source of truth.
- Input Contract: G01/G03/G04, Track A projection contract, Track C permission
  and Outcome projections.
- Output: editable draft, Diff, validation, Human approval/publish/test and
  minimum Product View surfaces.
- Write scope: separately approved Console frontend/backend and bounded draft
  service/projection; authoritative writes only through approved platform path.
- Probable locations: `console/backend/`, `console/frontend/`, projection/API
  tests, optional bounded prototype module.
- Prohibited: Console database as desired-state authority, silent permission
  change, full enterprise Console, production auth, brand decisions.
- Dependencies: A projection; C permission shape for integration.
- Shared files: Console schemas/API/client/types, Digital Employee projection,
  version/Diff evidence.
- Conflict risk: High; Console schema files are single-writer during slice.
- Required tests: draft/edit/Diff/validation/approval, fail-closed publish,
  source-of-truth, cross-view refs, usability rehearsal.
- Completion result: `AUTHORING_AND_PRODUCT_VIEW_VERTICAL_SLICE_READY`.
- Human Gate: Product UX/authority Gate.
- Parallel start: UX/draft prototype after Gate; authoritative integration
  waits for A and relevant C interface.

### 23.5 Track E — Technical View, Observability, Provider Conformance and Golden Demo Harness

- Objective: correlate the Technical View, own the Provider Conformance Harness
  and Compatibility Manifest validation, and package deterministic end-to-end
  evidence for the accepted public story.
- Input Contract: integrated A–D interfaces and all final acceptance criteria.
- Output: Technical View, Provider Contract conformance results, exact-version
  evidence report, manifest validation, mismatch/rejection results, identity
  propagation/native-correlation/normalization/recovery/cleanup evidence,
  synthetic dataset/services, bootstrap, correction/recovery scripts, fallback
  and Golden Demo evidence report.
- Write scope: separately approved Console technical projection, examples,
  e2e/conformance harness and documentation.
- Probable locations: `console/`, `examples/`, `docs/`, dedicated e2e fixtures
  and CI scripts where approved.
- Prohibited: redefine A–D interfaces, fake live Provider success, persist a
  second source of truth, broaden release/certification claims.
- Dependencies: stable integrated outputs from A–D.
- Shared files: Console projection schemas, Demo manifests/docs, CI entry
  points, execution/Outcome fixtures.
- Conflict risk: Medium/High at integration.
- Required tests: the full Product/Technical/Engineering and Provider
  Conformance matrices; Compatibility Manifest validation; exact-version,
  mismatch/rejection/degradation, identity propagation, native correlation,
  Condition/Outcome normalization, failure/recovery evidence and cleanup;
  clean bootstrap, cross-view equality, fallback, claim/secret checks, timed
  rehearsal.
- Completion result: `GOLDEN_DEMO_CANDIDATE_READY_FOR_EXECUTION_GATE`.
- Human Gate: Golden Demo execution/acceptance Gate; separate Release Gate.
- Parallel start: harness/data skeleton may begin after contracts are fixed;
  integration waits for A–D.

## 24. Execution order and parallel map

1. **Phase 1 — Track A:** establish the bounded identity/interface spine and
   compatibility constraints. The first implementation authorization should
   target the Section 12 minimum vertical slice, not the full portfolio.
2. **Phase 2 — Tracks B, C, D:** start Provider-local, Capability-local, and
   authoring UX work in parallel against stabilized A interfaces. B/C shared
   handoff and D authoritative publication integration wait for A. C Workflow
   writes sequence with A. D permission/Outcome integration waits for C.
3. **Phase 3 — Track E:** integrate A–D, execute the full acceptance matrix,
   package synthetic dependencies, and rehearse live/fallback paths.

```text
close + REL integration + separate authorization
  -> A [single-writer identity/interface spine]
       |-> B Runtime Providers ---------|
       |-> C Capability/Workflow/Auth ---|-> E integration and evidence
       `-> D Authoring/Product View -----|
```

Complete Schema or Contract Freeze is not required for bounded prototype work.
Any public API/CRD or lifecycle change still requires its applicable Gate.

## 25. Shared-file ownership and conflict map

| Likely shared path | Primary owner | Consumers | Allowed change | Sequencing | Risk | Integration strategy |
| --- | --- | --- | --- | --- | --- | --- |
| bounded Core representation/identity interface | A | B/C/D/E | approved prototype contracts and tests | A first | High | versioned handoff; no consumer edits |
| logical Runtime Provider Contract Candidate | A | B/E | A owns stable Core-facing logical capabilities; no frozen method/API names | A first; B/E consume | Critical | A single writer; B supplies Adapter evidence; E supplies conformance feedback through reviewed handoff |
| Compatibility Manifest Candidate/metadata | B | A/E | representation-neutral Provider/package/upstream compatibility evidence | A Contract boundary first | High | B single writer; E validates; A consumes compatibility result only |
| Runtime Provider package directories | B | A/E | Runtime-specific translation, validation and version evidence | A interface first | High | B-only writes; package-specific PRs may follow after shared boundary is integrated |
| Provider Conformance Harness | E | A/B | tests and evidence only; cannot redefine Contract | A/B Candidates available | High | E single writer; failures return to owning track through explicit interface change review |
| `manifests/crd/` | A, only after G2 | C/E | separately approved additive API work only | single writer | Critical | dedicated PR and compatibility Gate |
| `operator/src/agent_operator/task_controller.py` | A initially; C after handoff | B/C/E | identity/routing first, capability handoff second | serial | Critical | A merge/integration before C write |
| `operator/src/agent_operator/workflow_controller.py` | C | A/E | compatible Workflow/Outcome/Human Gate integration | A Task interface first | High | C owns; E consumes fixtures |
| `runtime/` generic interface | B | A/C/E | Native/OpenClaw Provider mapping | A contract first | High | B-owned PR; unchanged-consumer tests |
| Capability prototype/provider directory | C | B/D/E | Capability/auth/REST/MCP only | A contract first | Medium | C-owned interface and fixtures |
| `console/backend/src/agent_console/schemas.py` and projection/API | D during slice | A/C/E | Product projection and shared DTOs | A/C shapes first | Critical | single-writer D; E follows versioned DTO |
| `console/frontend/src/` shared API/types/routes | D | E | Product View first, Technical View extension by agreed handoff | serial for shared types | High | D owns base; E rebases after integration |
| Demo fixtures/examples/docs | E | B/C/D | integration-only scenario data/runbook | interfaces stable | Medium | E owns canonical fixture versions |
| CI/e2e entry points | E | A–D | additive bounded gates only | final phase | Medium | E integrates track test commands |
| `docs/governance/REGISTRY.md` | active governance/REL Session | all read-only | lifecycle/provenance only | governance-serialized | High | never edited concurrently by implementation tracks |

Single-writer files in the first vertical slice are the chosen Core identity
representation, public CRD files if separately approved, Task controller/schema,
and Console backend schemas/projection. Every writable Session follows:

```text
one Session -> one Codex conversation -> one branch
            -> one isolated worktree -> one primary PR
```

## 26. Architecture exit and remaining debt

`BROAD_ARCHITECTURE_CONVERGENCE: COMPLETE_FOR_BOUNDED_V0_2_IMPLEMENTATION`

`IMPLEMENTATION_ENTRY: READY_AFTER_SESSION_CLOSE_AND_INTEGRATION`

Further architecture work is allowed only when implementation finds a material
Core contradiction, compatibility cannot be preserved, identity/authority is
ambiguous, a Human decision is required, or sufficient evidence exists for a
Freeze Gate. Do not create another general architecture-convergence Session.

Non-blocking uncertainty remains the claim-scoped Evidence Debt in Sections 15
and 32: representation/backfill, combined identity conformance, exact Provider
targets and packaging mechanics, Compatibility Manifest representation,
version-range/mismatch/deprecation behavior, OpenClaw live and combination
evidence, Provider Contract conformance/certification thresholds,
MCP/side-effect breadth, bounded authorization, domain vocabulary/recovery,
mixed-version/Console tolerance, Hermes ED-S5-001, and timed usability. None is
silently closed or converted into implementation evidence.

## 27. Next Session portfolio

| Order | Work | State |
| --- | --- | --- |
| 1 | REL Session to integrate the accepted S5-ARCH-006 artifact after close confirmation and merge authorization | `RECOMMENDED_ONLY / NOT_ACTIVE / NOT_AUTHORIZED` |
| 2 | minimum vertical-slice implementation planning/authorization | `PROPOSED / NOT_ACTIVE / NOT_AUTHORIZED` |
| 3 | Tracks A–E according to Section 24 dependency readiness | `PROPOSED / NOT_ACTIVE / NOT_AUTHORIZED` |

No implementation Session is activated by this Checkpoint.

## 28. Checkpoint B finalization state

- Lifecycle: `CLOSING`
- Authorization: `AUTHORIZED`
- Status: `PASS`
- Checkpoint: `B — FINAL_SCOPE_CONVERGENCE_AND_IMPLEMENTATION_HANDOFF`
- Result: `READY_TO_CLOSE`
- Human Close Confirmation: `PENDING`
- G07 Provider support policy: `ACCEPTED_AS_V0_2_PROVIDER_POLICY`
- G08 deployment/asset policy: `ACCEPTED_AS_V0_2_DEPLOYMENT_AND_ASSET_POLICY`
- Broad architecture convergence: `COMPLETE_FOR_BOUNDED_V0_2_IMPLEMENTATION`
- Implementation entry: `READY_AFTER_SESSION_CLOSE_AND_INTEGRATION`
- Production/Core change: `0`
- Schema change: `0`
- CRD change: `0`
- ADR change: `0`
- Runtime Provider change: `0`
- Capability Provider change: `0`
- Console change: `0`
- Test source change: `0`
- Next action: `WAIT_FOR_HUMAN_CLOSE_CONFIRMATION`
- Next gate: `Human S5-ARCH-006 Close Confirmation`

S5-ARCH-006 is not closed. PR #44 must remain open and unmerged.

## 29. G07 — Versioned Runtime Provider Support Policy

**Disposition: `ACCEPTED_AS_V0_2_PROVIDER_POLICY`**

```text
Stable Core
  -> Runtime Binding
  -> Versioned Runtime Provider Contract
  -> independently versioned Provider Adapter Package
  -> exact supported upstream Runtime version/profile
```

Stable Core remains independent of Hermes, OpenClaw, and Native Runtime
implementation versions, Provider configuration and identity, and native
lifecycle mechanics. Core owns Platform identity; Definition, Instance, Task
and Workflow semantics; Platform Execution Identity; logical Runtime intent;
Capability governance; normalized domain Conditions and Outcomes; and control
and authority boundaries.

The Runtime Provider Adapter owns Provider-specific validation, Runtime
Binding and native configuration translation, realization creation/connection,
start/stop/observe/cleanup and Task execution translation, unchanged Platform
Execution Identity propagation, native identity correlation, native-to-domain
Condition/Outcome normalization, recovery evidence, version compatibility and
unsupported-version behavior, and explicit Provider limitations/evidence.
Native Runtime, OpenClaw, and Hermes each own their native mechanics and native
evidence. An Adapter cannot replace Platform identity or authority with native
identity or mechanics.

Logical Provider capability Candidates are:

- validate Binding and compatibility;
- resolve or create a realization;
- start, stop, execute, observe, and clean up;
- correlate native evidence;
- normalize Conditions and Outcomes; and
- provide recovery evidence.

Names such as `validateBinding`, `validateCompatibility`,
`resolveOrCreateRealization`, `start`, `stop`, `execute`, `observe`,
`correlateNativeEvidence`, `normalizeCondition`, `normalizeOutcome`,
`provideRecoveryEvidence`, and `cleanup` describe logical capabilities only.
They are not frozen interface, method, serialization, transport, or API names.

## 30. v0.2 Provider classification and version support matrix

| Runtime | Final classification | v0.2 requirements and constraints |
| --- | --- | --- |
| Native Runtime | `PRIMARY_GOLDEN_PATH` | exact platform Runtime version/profile selected and tested by bounded implementation evidence; full minimum slice; deterministic path; identity propagation and normalized Condition/Outcome evidence; certification `NOT_GRANTED` |
| OpenClaw | `SUPPORTED_EXTERNAL_RUNTIME_PATH_CANDIDATE / EXACT_VERSION_EVIDENCE_REQUIRED` | independently versioned Adapter; exact pinned/tested upstream; bounded live path; Binding translation; identity/native correlation; normalized evidence; limitations; reject unsupported or explicitly degrade safely; no future/all-version or certification claim |
| Hermes | `EXPERIMENTAL_ADAPTER / EXACT_VERSION_EVIDENCE_REQUIRED / NOT_CURRENTLY_CERTIFIABLE` | independently versioned Adapter; exact pinned target selected by bounded evidence; feasible Experimental path; identity/profile/session correlation and normalization where supported; explicit unavailable/unsupported behavior; visible label; ED-S5-001 open; non-blocking |
| Future Runtime | `EXTENSION_POINT` | same logical Provider Contract, exact compatibility profile, applicable Conformance Harness, and separate support/certification decision |

### 30.1 Provider Version Support Matrix Candidate

| Runtime Provider | Provider package/version | compatible Core Contract version | exact supported upstream Runtime version/profile | support classification | required feature profile | live evidence | Conformance | known limitations | certification | deprecation | fallback/rejection |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Native | `TO_BE_SELECTED_BY_BOUNDED_IMPLEMENTATION_EVIDENCE` | `CANDIDATE / NOT_FROZEN; exact version TBD` | `TO_BE_SELECTED_BY_BOUNDED_IMPLEMENTATION_EVIDENCE` | `PRIMARY_GOLDEN_PATH` | minimum vertical slice, deterministic execute/observe, identity, Conditions/Outcomes | current v0.1 Native exists; versioned Provider path not yet proven | `NOT_YET_RUN` | current implementation predates accepted Provider boundary | `NOT_GRANTED` | `UNDECIDED` | deterministic failure; no silent version substitution |
| OpenClaw | `TO_BE_SELECTED_BY_BOUNDED_IMPLEMENTATION_EVIDENCE` | `CANDIDATE / NOT_FROZEN; exact version TBD` | `TO_BE_SELECTED_BY_BOUNDED_IMPLEMENTATION_EVIDENCE` | `SUPPORTED_EXTERNAL_RUNTIME_PATH_CANDIDATE` | external connection/execution/observe, identity, native refs, Conditions/Outcomes, cleanup as applicable | bounded successful terminal live evidence required | `NOT_YET_RUN` | successful real-model completion/dependency recovery and exact-version support unproven | `NOT_GRANTED` | `UNDECIDED` | reject unsafe mismatch; optional explicit safe degradation; labelled fixture plus Native public fallback does not prove live support |
| Hermes | `TO_BE_SELECTED_BY_BOUNDED_IMPLEMENTATION_EVIDENCE` | `CANDIDATE / NOT_FROZEN; exact version TBD` | `TO_BE_SELECTED_BY_BOUNDED_IMPLEMENTATION_EVIDENCE` | `EXPERIMENTAL_ADAPTER` | feasible Experimental execute/observe, identity, profile/session refs, normalized evidence | Hermes v0.20.4 evidence exists but did not close ED-S5-001 and is not selected here as the supported target | `NOT_YET_RUN / ED-S5-001_OPEN` | successful external-model completion absent; unavailable path must be non-blocking | `NOT_CURRENTLY_CERTIFIABLE` | `UNDECIDED` | explicit unavailable/unsupported result; never blocks Native or Core v0.2 claim |
| Future Provider | `UNASSIGNED` | declared exact Candidate/Contract compatibility required | exact version/profile required | `EXTENSION_POINT` | declared required/optional/unsupported features | none | `REQUIRED_BEFORE_SUPPORT_CLAIM` | unknown until evidence | `NOT_GRANTED` | declared by future decision | fail closed or explicitly declared safe degradation |

No row means “latest,” “current,” “all supported versions,” or general future
compatibility. Exact Provider packages, Core Contract versions, and upstream
targets are selected by separately authorized bounded implementation or Spike
evidence.

## 31. Compatibility Manifest Candidate

Classification: `CANDIDATE_WITH_EVIDENCE_DEBT`

Each immutable evidence snapshot must be capable of declaring:

- Provider name and Provider package version;
- compatible Core Contract version/profile;
- supported upstream Runtime version/range and tested exact version;
- required, optional, and unsupported features;
- required configuration extensions;
- known limitations and evidence links;
- Conformance and certification states as independent values;
- deprecation state; and
- explicit fallback, degradation, or rejection behavior.

The declaration is representation-neutral. Field names, nesting,
serialization, file format, Kubernetes/public API exposure, version-range
syntax, and Provider Registry representation are not frozen. Runtime Package
and Provider Registry remain internal metadata. A change to that boundary
requires a separate Human architecture decision.

## 32. Version mismatch behavior and Evidence Debt

Compatibility validation occurs before unsafe Provider invocation:

1. detect the upstream Runtime version/profile;
2. compare it with the evidenced Compatibility Manifest;
3. accept an exact supported match;
4. identify an untested version without promoting it to supported;
5. reject an unsupported/unsafe mismatch before Provider invocation; or
6. enter an explicitly declared degraded mode only when the manifest and
   evidence prove that mode safe.

Every mismatch preserves Platform identity and emits actionable
operator-facing Condition/diagnostic evidence. An unsafe failure produces no
Provider invocation. No Adapter may silently report `SUPPORTED` outside its
declared and evidenced compatibility profile.

Claim-scoped `UNASSIGNED_EVIDENCE_DEBT` is retained for exact Native profile,
OpenClaw version, Hermes target, Provider package versioning mechanics,
Compatibility Manifest representation, version-range policy, mismatch and
safe-degradation behavior, Provider Contract conformance, certification
thresholds, and upgrade/deprecation policy. OpenClaw live execution evidence
also remains debt. Hermes debt remains the assigned `ED-S5-001 / OPEN`.
Only the corresponding exact-version support, conformance, certification,
upgrade, deprecation, or production claim is blocked; these debts do not all
block the bounded v0.2 prototype or Native Golden Path.

## 33. Provider Conformance acceptance

Conformance is independent of certification. Passing these bounded tests does
not grant Provider certification, Production Readiness, all-version
compatibility, or Runtime Contract Freeze.

| ID | Provider applicability | Expected behavior | Required evidence | Track | Automation | Blocking claim/gate |
| --- | --- | --- | --- | --- | --- | --- |
| PCA-01 | all | Provider package has immutable Candidate identity/version | package metadata and repeatability test | B/E | `YES` | package support claim |
| PCA-02 | all | exact upstream version/profile is declared; no ambiguous latest/all label | manifest validation | B/E | `YES` | exact-version support claim |
| PCA-03 | all | Stable Core schema/identity contains no upstream-version dependency | architecture/source boundary test | A/E | `YES/PARTIAL` | Core independence claim |
| PCA-04 | all | Runtime Binding is translated only by selected Adapter | unchanged-consumer/translation test | B/E | `YES` | Provider path acceptance |
| PCA-05 | all | detected version is validated before unsafe execution | ordered interaction test | B/E | `YES` | supported path |
| PCA-06 | Native/OpenClaw; Hermes where feasible | exact supported match executes under declared profile | bounded live/deterministic run | B/E | `PARTIAL` | corresponding support classification |
| PCA-07 | all | unsupported unsafe version is rejected before invocation | zero-invocation mismatch test | B/E | `YES` | safety/support claim |
| PCA-08 | declared profiles only | degraded mode occurs only when explicitly declared and evidenced | positive/negative degradation fixtures | B/E | `YES` | degraded support claim |
| PCA-09 | all | untested version never appears as supported | manifest/status negative test | B/E | `YES` | any version-support claim |
| PCA-10 | all executable paths | Platform Execution Identity propagates unchanged | end-to-end equality assertion | A/B/E | `YES` | Runtime path acceptance |
| PCA-11 | all executable paths | native IDs remain opaque correlation evidence | trace/reference assertions | B/E | `YES` | technical Demo acceptance |
| PCA-12 | all | native observations normalize to Runtime-domain Conditions | normalization fixtures/live evidence | B/E | `YES/PARTIAL` | Condition support claim |
| PCA-13 | all executable paths | native results normalize as evidence for domain Outcomes | normalization fixtures/live evidence | B/E | `YES/PARTIAL` | Outcome support claim |
| PCA-14 | all | failures are normalized without replacing Platform semantics | failure matrix | B/E | `YES` | supported failure claim |
| PCA-15 | all applicable modes | Adapter provides bounded recovery evidence without declaring State continuity | replacement/unavailable evidence | B/E | `YES/PARTIAL` | recovery claim |
| PCA-16 | owned modes | cleanup respects declared ownership and is idempotent/safe | cleanup and foreign-resource tests | B/E | `YES` | lifecycle/cleanup claim |
| PCA-17 | all | known limitations and unsupported features are visible | manifest/Technical View assertions | B/E | `YES` | public support claim |
| PCA-18 | OpenClaw | pinned exact version succeeds through bounded live path | live evidence bundle and trace | B/E | `PARTIAL` | OpenClaw supported-candidate acceptance |
| PCA-19 | Hermes | Experimental/non-certifiable/ED-S5-001 labels remain visible | UI/manifest/claim tests | B/E | `YES` | Hermes optional path only |
| PCA-20 | future Provider fixture | generic Contract/manifest can describe another Adapter without Core Provider fields | representation-neutral fixture/conformance compile or load test | A/E | `YES/PARTIAL` | extension-point feasibility only |

The final acceptance registry now contains the original 31 Product, Technical,
and Engineering/Conformance criteria plus 20 Provider Conformance criteria.
Full v0.2 Golden Demo acceptance requires applicable PCA criteria for Native
and OpenClaw. Hermes PCA criteria remain optional/Experimental. External
fallback cannot substitute for PCA-18 live evidence.

## 34. G08 — Managed Runtime Primary and Hybrid Placement Policy

**Disposition: `ACCEPTED_AS_V0_2_DEPLOYMENT_AND_ASSET_POLICY`**

**v0.2 primary placement: `PLATFORM_MANAGED / PRIMARY_REQUIRED_PATH`.** The
Golden Path runs without employee desktop installation.

| Placement | Final v0.2 disposition | Intended use and boundary |
| --- | --- | --- |
| `PLATFORM_MANAGED` | `PRIMARY_REQUIRED_PATH` | platform-managed isolated Container, VM, Runtime Pool, or equivalent for continuous Digital Employees, background Tasks/Workflows, controlled versions, monitoring and recovery |
| `CUSTOMER_MANAGED` | `ARCHITECTURE_READY / IMPLEMENTATION_DEFERRED` unless bounded Capability connectivity evidence makes a narrower prototype necessary | future customer VPC, on-premises, private cloud/cluster or managed workstation pool for private data/models, residency and restricted systems; prefer outbound authenticated connectivity |
| `EDGE_DESKTOP` | `OPTIONAL_EXTENSION / NOT_V0_2_PRIMARY_PATH / IMPLEMENTATION_DEFERRED` | only explicit local file/application/device/browser/model needs; offline, user-session, drift, state and credential constraints; no v0.2 fleet implementation |

### 34.1 Control Plane and Runtime Plane authority

```text
SaaS Control Plane
  -> Digital Employee desired state
  -> Agent Definition / Agent Instance identity
  -> Task / Workflow
  -> Runtime Binding including placement intent/evidence
  -> Capability policy
  -> Platform Execution Identity
  -> normalized Conditions / Outcomes
  -> governance / audit

separately placed Runtime Plane
  -> Provider Adapter
  -> Provider-specific configuration
  -> Runtime process / Gateway
  -> Profile/Home / Workspace
  -> native Session / local execution state
  -> native evidence
```

The SaaS Control Plane owns logical semantics and authority. The Runtime Plane
owns native execution mechanics. Process, device, Gateway, Profile, Container,
VM and native Session identities remain opaque evidence and cannot replace
Agent Instance or Platform Execution Identity.

### 34.2 v0.2 managed topology

```text
SaaS Control Plane
  -> Managed Runtime Plane
       |- Native Managed Runtime [REQUIRED]
       |- OpenClaw Managed/Server Runtime [REQUIRED external evidence]
       `- Hermes Managed/Server Runtime [EXPERIMENTAL]
  -> Capability Gateway / Provider
       |- REST
       `- MCP
  -> safe synthetic enterprise systems
```

Native uses a managed deterministic path with one isolated realization per
applicable Instance scope. OpenClaw runs its evidence-selected exact upstream
version in a managed/server environment without employee desktop installation
and preserves Gateway capability only where evidenced. Hermes runs its
evidence-selected exact upstream version in a managed/server environment with
an isolated Profile/Home per Agent Instance or equivalent approved scope; it
does not require Hermes Desktop and remains Experimental/not certifiable.

## 35. Runtime Connectivity, lifecycle and isolation Candidates

### 35.1 Runtime Connectivity Candidate

Classification: `THIN_FOUNDATION / REPRESENTATION_NOT_FROZEN`.

Platform-managed Runtime may use internal trusted Control Plane connectivity.
Future Customer-managed and Edge placements should use a customer/device-side
Enterprise Runtime Connector that initiates an outbound authenticated
connection. Its logical responsibilities may include registration, Runtime or
device identity, Provider/Runtime version and compatibility reporting,
heartbeat, desired-operation retrieval, start/stop handling, Task delivery,
Execution Identity propagation, status/Outcome and policy-bounded evidence
reporting, disconnection, local buffering, reconnect and resynchronization.

Protocol, endpoint, WebSocket/gRPC choice, serialization, public API and
deployment technology remain unfrozen. Connector/Edge implementation is not a
v0.2 blocker.

### 35.2 Lifecycle and status

Logical lifecycle capabilities are register, validate compatibility, provision
or connect, configure, synchronize approved assets, start, observe, execute,
stop, drain, replace, recover and clean up. Conceptual statuses are registered,
connected, ready, busy, degraded, offline, incompatible, draining and recovery
required. These are not frozen method names, state vocabulary, serialization,
or public APIs. Provider Adapters translate native state into domain-owned
Conditions and retain native evidence.

### 35.3 Managed Runtime isolation Candidate

Each Agent Instance—or an explicitly approved sharing boundary—must isolate:
Runtime process/execution boundary, Profile/Home, Workspace, Memory namespace,
Secret scope, network policy, resource quota, Skill assignment and execution
evidence. Hermes Profiles cannot be concurrently shared by independent Agent
processes until a safe external Memory design is evidenced. OpenClaw Gateway
sharing cannot silently cross tenant, Digital Employee, identity, credential,
or policy boundaries. Exact tenancy/sharing rules remain evidence debt.

## 36. Enterprise Skill, Memory and execution boundaries

### 36.1 Skill asset boundary

| Concept | Authority/classification | Boundary |
| --- | --- | --- |
| Runtime-native Skill | Provider-native execution material | Hermes Skill, OpenClaw plugin, instructions/scripts; never automatically authoritative enterprise state |
| Enterprise Skill Package | `PRODUCT_ASSET / INTERNAL_PACKAGE_METADATA_CANDIDATE` | governed identity/version, purpose, owner, source/license, Runtime compatibility, instructions/assets, required Capabilities/Secret refs, risk, review, integrity/signature evidence, limitations and deprecation; not a Core resource or CRD |
| Capability Definition | Provider-independent governed semantic operation | Skill assignment cannot bypass Capability Binding or authorization |

Promotion is:

```text
Runtime-native or learned Skill -> Asset Candidate -> secret scan
  -> malware/dependency scan -> license review
  -> Capability/data-boundary analysis -> Human Review
  -> version/integrity evidence -> Enterprise Skill Catalog
  -> approved Digital Employee assignment -> Provider translation
```

v0.2 requires one bounded pre-approved Skill/configuration example. Arbitrary
unreviewed installation and automatic learned-Skill promotion are prohibited.
Complete Catalog/Marketplace productization is deferred to BUILD/GOVERN.

### 36.2 Memory, Session and State authority

| Content | Default authority |
| --- | --- |
| personal preference, private conversation, local file/application context | `PERSONAL_MEMORY / USER_OWNED / NOT_AUTOMATICALLY_ENTERPRISE_ASSET` |
| Task context, Runtime session, intermediate result, tool cache | `EXECUTION_STATE / EXECUTION_SCOPED / RETENTION_CONTROLLED` |
| approved business knowledge, procedures, governed examples/policies/terms | `ENTERPRISE_KNOWLEDGE / ENTERPRISE_OWNED / VERSIONED / GOVERNED` |
| learned Skill/Workflow/rule or summarized business knowledge | `LEARNED_ASSET_CANDIDATE / NON_AUTHORITATIVE_UNTIL_REVIEWED_AND_APPROVED` |

Runtime-local Memory may be used in the bounded managed path. Cross-Runtime
State portability remains `DEFERRED`; no seamless Hermes/OpenClaw Memory
portability is claimed.

### 36.3 Understanding-to-execution trace

```text
business request -> Digital Employee context -> approved knowledge / Skill
  -> plan / Workflow -> Capability selection -> authorization
  -> REST/MCP or sandboxed execution -> execution feedback
  -> Business Outcome -> governed asset candidate where applicable
```

The managed path must preserve core reasoning/execution, require no employee
desktop, exclude/defer local-device-only capabilities, enforce Capability
authorization, propagate Execution Identity, expose Skill/Memory authority and
prevent learned content from automatically becoming enterprise state.

### 36.4 High-risk execution boundary

Classification: `ARCHITECTURE_CANDIDATE_WITH_IMPLEMENTATION_EVIDENCE_DEBT`.

The preferred enterprise pattern is a longer-lived managed Agent Runtime using
a governed Capability Gateway and an ephemeral/isolated execution sandbox for
high-risk shell, arbitrary code, browser automation, file transformation,
untrusted-content processing, or network access beyond approved Capabilities.
A complete sandbox platform is not required in the minimum slice unless later
evidence requires it. v0.2 cannot claim unrestricted high-risk execution as a
supported enterprise capability.

## 37. G08 capability classification update

Existing required IDs are refined as follows: R05/R08 require identity and
Runtime placement to remain independent; R09 is the platform-managed Native
path; R10 is the managed/server OpenClaw path; R12/R13 retain governed REST/MCP;
R14 adds placement/asset visibility; and R19 includes desktop-independent clean
reproduction. Four additional Required capabilities complete the G08 scope:

| ID | Required behavior | Technical mapping | Acceptance | Evidence | Automation | Track | Dependency | v0.2 blocker |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R20 | show and operate managed Runtime lifecycle/status | placement-aware Binding, Adapter lifecycle and domain Conditions | MRA-01–08/16 | managed startup/observe/replace/offline fixtures | `YES/PARTIAL` | A/B/E | G07 packages and A placement semantics | Yes: managed Golden Path |
| R21 | assign only approved Skill/configuration | internal Skill Package metadata, approved synchronization, Capability boundary | MRA-09–11 | approval/integrity assignment and rejection tests | `YES/PARTIAL` | B/C/D/E | Skill metadata and authority policy | Yes: bounded Skill example |
| R22 | trace understanding through governed execution | Workflow, Capability authorization, managed Provider evidence and Outcomes | MRA-12–15 | end-to-end trace with authority assertions | `YES/PARTIAL` | C/E | R12/R13/R15/R21 | Yes: full Demo |
| R23 | expose placement and Skill/Memory authority in both views | shared Instance/Binding/asset/evidence projections | MRA-17/18 | cross-view equality and business-label tests | `YES/PARTIAL` | D/E | A/B/C projections | Yes: full Demo |

`EXPERIMENTAL` X01 now explicitly includes managed/server Hermes Adapter plus
bounded Profile/Skill/Memory evidence. Existing Deferred IDs cover
multi-tenancy/sharing (D01), Runtime pools/scheduling (D05), State portability
(D07), and marketplace breadth (D09). Additional Deferred capabilities are:

| ID | Deferred capability |
| --- | --- |
| D12 | full Customer-managed Runtime deployment and Connector implementation |
| D13 | Edge/Desktop as primary path and Edge fleet management |
| D14 | complete Enterprise Skill Catalog and automatic learned-Skill promotion |
| D15 | complete high-risk execution sandbox platform beyond slice requirements |

All Blocked claim/gate classifications remain unchanged. Deferred placement or
asset work is not automatically a v0.2 blocker.

## 38. G08 implementation gap map

| Area | State | Concrete gap / minimum follow-up | Track | Blocking scope |
| --- | --- | --- | --- | --- |
| managed Native provisioning | `EXISTS_WITH_GAP` | current Kubernetes Native realization exists; prove exact managed profile, Instance scope and G07 identity/status path | A/B/E | Native managed Golden Path |
| managed OpenClaw server path | `PROTOTYPE_REQUIRED` | no Production/Core path; add bounded exact-version managed/server Adapter evidence | B/E | required external path |
| managed Hermes server path | `EVIDENCE_REQUIRED` | spike evidence exists but ED-S5-001 open; bounded isolated managed evidence only | B/E | Hermes Experimental claim only |
| Runtime placement | `NEW_IMPLEMENTATION_REQUIRED` | representation-neutral placement intent/evidence absent; prototype under A Gate | A/D/E | managed Demo visibility |
| Runtime registration | `PROTOTYPE_REQUIRED` | no generic Provider registration lifecycle | A/B/E | managed Provider path |
| heartbeat | `PROTOTYPE_REQUIRED` | no generic connection/freshness evidence | B/E | applicable managed/external status claim |
| start/stop | `EXISTS_WITH_GAP` | Native lifecycle exists; generic Adapter semantics/version evidence absent | B/E | Provider lifecycle claim |
| status normalization | `PROTOTYPE_REQUIRED` | accepted Conditions not represented across Providers | A/B/E | Technical Demo |
| Profile/Home isolation | `PROTOTYPE_REQUIRED` | Hermes/provider isolation not integrated or tested | B/E | Hermes/managed isolation claim |
| Workspace/Memory namespace | `PROTOTYPE_REQUIRED` | thin boundary only; retention/persistence rules unresolved | A/B/E | bounded managed state claim |
| Secret references | `EXISTS_WITH_GAP` | current Kubernetes Secret refs exist; Provider/Instance scope and consumption evidence incomplete | A/B/C/E | secure managed path |
| approved Skill synchronization | `NEW_IMPLEMENTATION_REQUIRED` | no governed assignment/sync path | B/C/D/E | bounded Skill example |
| Skill asset metadata | `PROTOTYPE_REQUIRED` | representation-neutral internal package Candidate only | B/C/D | Skill governance claim |
| Capability Gateway | `PROTOTYPE_REQUIRED` | REST/MCP spike boundary not integrated as managed gateway | C/E | governed execution path |
| customer Connector concept | `DEFERRED` | thin foundation only; protocol/identity unfrozen | A/B/C | no v0.2 blocker |
| high-risk sandbox boundary | `DEFERRED` | architecture Candidate; full platform outside slice | C/E | blocks unrestricted high-risk claim only |
| learned asset promotion | `DEFERRED` | policy documented; Catalog/scans/workflow absent | C/D/E | no v0.2 blocker |
| State portability | `DEFERRED` | unsupported across Native/OpenClaw/Hermes | A/B/E | blocks portability claim only |
| fleet/placement scale | `DEFERRED` | Customer/Edge fleet and Runtime Pool scheduling absent | A/B/E | no v0.2 blocker |

## 39. Managed Runtime acceptance matrix

| ID | Classification | Expected result | Required evidence | Track | Automation | Prerequisite | Blocking scope |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MRA-01 | `REQUIRED` | Golden Path runs without employee desktop | clean managed rehearsal and dependency inventory | B/E | `PARTIAL` | managed package/profile | v0.2 Golden Path |
| MRA-02 | `REQUIRED` | Native runs as isolated managed primary Runtime | Native managed E2E trace | B/E | `YES/PARTIAL` | A/G07 interface | v0.2 Golden Path |
| MRA-03 | `REQUIRED` | OpenClaw exact target runs in managed/server environment | bounded live evidence | B/E | `PARTIAL` | G07 exact-version selection | external path |
| MRA-04 | `EXPERIMENTAL` | Hermes exact target is managed/server, isolated and visibly Experimental | bounded evidence/labels where feasible | B/E | `PARTIAL` | selected target; ED-S5-001 remains | Hermes only |
| MRA-05 | `REQUIRED` | selected Instance records exact placement evidence | projection/equality tests | A/D/E | `YES` | placement Candidate | managed Demo |
| MRA-06 | `REQUIRED` | Instance identity survives realization replacement/device change | identity/replacement tests | A/B/E | `YES` | stable Instance | recovery/identity claim |
| MRA-07 | `REQUIRED` | managed Runtime registers, starts and is observed through normalized evidence | lifecycle/Condition tests | A/B/E | `YES` | Provider Adapter | managed path |
| MRA-08 | `REQUIRED` | Runtime/package/upstream compatibility evidence is visible | manifest and Technical View tests | B/E | `YES` | G07 manifest | support claim |
| MRA-09 | `REQUIRED` | Profile/Home/Workspace are isolated per approved Instance/sharing scope | isolation and cross-scope negative tests | B/E | `YES/PARTIAL` | managed topology | managed isolation claim |
| MRA-10 | `REQUIRED` | pre-approved Skill/configuration is assigned and synchronized | version/integrity/assignment evidence | B/C/D/E | `YES/PARTIAL` | Skill Package Candidate | bounded Skill example |
| MRA-11 | `REQUIRED` | arbitrary or unauthorized Skill installation is rejected | negative authorization/zero-install test | B/C/E | `YES` | approval policy | enterprise Skill boundary |
| MRA-12 | `REQUIRED` | Personal Memory is not promoted to enterprise asset automatically | authority/retention negative test | A/D/E | `YES` | Memory classification | asset governance claim |
| MRA-13 | `REQUIRED` | learned Skill/knowledge remains non-authoritative until approval | promotion negative/audit test | C/D/E | `YES` | Human review boundary | learned asset claim |
| MRA-14 | `REQUIRED` | Runtime/Skill cannot bypass Capability authorization | end-to-end DENY and zero-call evidence | B/C/E | `YES` | Capability Gateway | governed execution |
| MRA-15 | `REQUIRED` | REST/MCP execute through managed Capability governance with one identity | end-to-end traces | B/C/E | `YES/PARTIAL` | R12/R13 | full Demo |
| MRA-16 | `REQUIRED_WHERE_APPLICABLE` | disconnected/offline/incompatible state is explicit and fails honestly | status/failure/reconnect fixtures | B/E | `YES` | lifecycle/status Candidate | external/connector claims |
| MRA-17 | `REQUIRED` | high-risk work is denied or routed only through approved bounded execution | negative policy/sandbox-boundary evidence | C/E | `YES/PARTIAL` | risk classification | blocks unrestricted high-risk claim |
| MRA-18 | `REQUIRED` | Product/Technical Views share placement, identity, status and asset authority | cross-view equality tests | D/E | `YES` | A–C projections | full Demo |
| MRA-19 | `REQUIRED` | external Runtime fallback is deterministic, labelled and desktop-independent | unavailable/fallback rehearsal | B/E | `YES/PARTIAL` | Native path and fixture | public reliability; not live support evidence |

The consolidated acceptance registry now contains 70 criteria: 12 Product, 11
Technical, 8 Engineering/Conformance, 20 Provider Conformance and 19 Managed
Runtime criteria. MRA-04 remains Experimental; MRA-16 applies only to a claimed
connection mode. Neither makes Hermes or Edge a mandatory Golden Path.

## 40. G08 Track updates and ownership

These deltas are authoritative additions to Section 23:

- **Track A:** owns placement-reference semantics, identity independence from
  realization/device, and conceptual lifecycle/Condition boundaries.
- **Track B:** owns managed/server profiles, Adapter lifecycle, isolated
  Profile/Home/Workspace, exact-version managed images/packages, registration
  and heartbeat evidence, Native/OpenClaw managed paths, and bounded Hermes
  Experimental managed evidence.
- **Track C:** owns the Capability Gateway boundary, prevents Runtime bypass of
  authorization, retains the thin enterprise Connector concept for private
  systems, and provides synthetic enterprise systems for v0.2.
- **Track D:** owns business-friendly placement/Runtime selection, approved
  Skill assignment, Skill/Memory authority visibility, and hides raw native
  configuration by default.
- **Track E:** owns managed-runtime E2E tests, placement/status views,
  replacement/offline/incompatible evidence, Skill/configuration evidence,
  Product/Technical synchronization and desktop independence.

Single-writer boundaries remain: A owns placement and Platform identity
semantics; B owns Runtime packages/native translation and managed topology
evidence; C owns Capability Gateway/authorization integration; D owns Product
projection schemas; E owns conformance/Demo evidence. A–E consume versioned
handoffs and cannot concurrently redefine placement, Provider Contract,
Capability authority or shared Console DTOs.

## 41. G08 Evidence Debt and final disposition

Claim-scoped `UNASSIGNED_EVIDENCE_DEBT` is recorded for managed Runtime
packaging, placement representation, Connector protocol/identity, heartbeat
and disconnection thresholds, Runtime sharing/tenancy, Profile/Home isolation,
Workspace persistence, Secret management, Skill Package representation,
Skill scanning/signing, learned-asset promotion, Personal/Enterprise Memory
policy, State retention, cross-Runtime State portability, high-risk sandboxing,
Customer-managed/Edge deployment and Runtime fleet management. Existing
ED-S5-001 remains open. These debts block only their named support, isolation,
portability, high-risk, deployment, fleet, production or certification claims;
deferred Customer/Edge work is not a v0.2 blocker.

Final G08 output:

- G08: `ACCEPTED_AS_V0_2_DEPLOYMENT_AND_ASSET_POLICY`
- v0.2 primary placement: `PLATFORM_MANAGED`
- Native: `MANAGED / REQUIRED / PRIMARY_GOLDEN_PATH`
- OpenClaw: `MANAGED_SERVER_PATH / SUPPORTED_EXTERNAL_RUNTIME_PATH_CANDIDATE / EXACT_VERSION_EVIDENCE_REQUIRED`
- Hermes: `MANAGED_SERVER_PATH / EXPERIMENTAL_ADAPTER / EXACT_VERSION_EVIDENCE_REQUIRED / NOT_CURRENTLY_CERTIFIABLE`
- Customer-managed: `ARCHITECTURE_READY / IMPLEMENTATION_DEFERRED`
- Edge/Desktop: `NOT_V0_2_PRIMARY_PATH / DEFERRED`
- Enterprise Skill Package: `PRODUCT_ASSET / INTERNAL_PACKAGE_METADATA_CANDIDATE`
- Personal Memory: `NOT_AUTOMATICALLY_ENTERPRISE_ASSET`
- State portability: `DEFERRED`

G08 authorizes no Connector, Provider, Skill Registry, Memory, sandbox, Core,
Schema, CRD, Console or test implementation. S5-ARCH-006 remains
`CLOSING / READY_TO_CLOSE`, subject to validation on the amended head and the
still-pending Human Close Confirmation.
