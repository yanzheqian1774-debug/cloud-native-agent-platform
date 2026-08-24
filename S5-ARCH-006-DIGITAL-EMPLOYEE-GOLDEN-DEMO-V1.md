# S5-ARCH-006 — Digital Employee Golden Demo Scope and Acceptance Candidate v1

SESSION

- ID: `S5-ARCH-006`
- Title: v0.2 Digital Employee Golden Demo Scope & Acceptance Contract
- Type: `ARCH`
- Version: `v0.2 CONNECT — Digital Employee Technical Preview`
- Lifecycle: `REVIEW`
- Authorization: `AUTHORIZED`
- Checkpoint: `A — GOLDEN_DEMO_SCOPE_AND_ACCEPTANCE_BASELINE`
- Result: `GOLDEN_DEMO_SCOPE_CANDIDATE`
- Baseline: `acbad19a8af7e0b3762007ba708a90ed0be53d07`
- Candidate status: `HUMAN_DECISION_REQUIRED`

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

## 18. Checkpoint recommendation

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
- Next action: `WAIT_FOR_HUMAN_GOLDEN_DEMO_SCOPE_GATE`
- Next gate: `Human S5-ARCH-006 Golden Demo Scope Gate`
