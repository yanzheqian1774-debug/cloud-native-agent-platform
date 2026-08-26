# S5-SPIKE-008 — Authoring and dual-view mock evidence

## Session identity and provenance

- Session: `S5-SPIKE-008 — Authoring and view mock prototype`
- Type / Track / Checkpoint: `SPIKE / D / A`
- Version: `v0.2 CONNECT — Digital Employee Technical Preview`
- Authorized baseline and initial head:
  `8d5e9c08b05a03e7ea098b871e82d848dd6ae067`
- Source of truth at preflight: `origin/main`, exact baseline match
- Branch: `codex/s5-spike-008-authoring-view-mock-prototype`
- Final head authority: the exact GitHub draft-PR head and delivery report. A
  commit cannot contain its own object ID; the PR head is the non-self-referential
  final provenance record.
- Classification: **INTERNAL MOCK / NON-AUTHORITATIVE / VERSION UNFROZEN**
- Production implementation, support, certification and readiness: **NOT GRANTED**

The worktree was created clean and isolated at the authorized baseline after
the default checkout was correctly rejected as dirty and owned by another
logical Session. No child Agent, parallel implementation, shared writer or
second logical S5-SPIKE-008 Session was used.

## Exact changed-path inventory

| Path | Ownership and purpose |
| --- | --- |
| `experiments/s5-spike-008-authoring-view-mock-prototype/README.md` | isolated prototype usage and boundary |
| `experiments/s5-spike-008-authoring-view-mock-prototype/prototype.py` | disposable authoring/Diff and view-projection reference behavior |
| `experiments/s5-spike-008-authoring-view-mock-prototype/fixtures/customer-complaint-quality-improvement.json` | deterministic synthetic fixture |
| `experiments/s5-spike-008-authoring-view-mock-prototype/web/index.html` | static interaction mock structure |
| `experiments/s5-spike-008-authoring-view-mock-prototype/web/styles.css` | isolated responsive presentation |
| `experiments/s5-spike-008-authoring-view-mock-prototype/web/app.js` | isolated client-only mock interactions |
| `experiments/s5-spike-008-authoring-view-mock-prototype/tests/test_prototype.py` | targeted fixture/interaction boundary tests |
| `docs/evidence/s5/v0.2/s5-spike-008/README.md` | this evidence artifact |

No shared file, production Console path, backend, product DTO, controller,
Workflow, Runtime Provider, Capability Gateway, CRD, schema, Registry, Project
State, dependency declaration or lockfile is changed.

## Users, personas and assumptions

The primary Product View user is a quality manager or business operator who
needs to describe an outcome, review the proposed workforce and plan, supervise
progress, and understand conclusions without selecting infrastructure. The
secondary Technical View user is a platform engineer who needs the exact
identity, Binding, Provider, authorization, evidence and limitation chain.

The fixtures are synthetic and deterministic. They assume no real customer
records, enterprise Knowledge source, credential, policy engine, persistence,
Runtime invocation or production authorization semantics. Digital Employee is
a business projection and is not identical to an Agent Definition, Instance,
Task, Runtime Session, Profile or Provider identity.

## Primary three-step business journey

1. Enter the single plain-language customer complaint analysis problem.
2. Review the two suggested Digital Employees, bounded three-step work plan,
   proposed count of two mock Instances, expected Knowledge sources and Human
   confirmation.
3. Start deterministic mock work and view progress, business Outcome and
   citations. Technical details remain available through a secondary drawer.

Runtime selection is hidden from the default business flow. The Product View
says “Execution environment available.” Any alternative Runtime would require
explicit Human confirmation; silent fallback is prohibited.

## Digital Employee directory and authoring model

The directory provides name, role title and description, business
responsibilities, can/cannot-do boundaries, status and authorized Knowledge
scope for a Customer Insight Specialist and a Quality Analysis Specialist.

The authoring prototype preserves the published mock definition as immutable
input. Editing creates a separate Draft. The AI suggestion is stored as
`PENDING_HUMAN_REVIEW`; it does not alter a field until a Human accepts the
candidate. The deterministic field Diff retains published and Draft values.
Empty required fields or pending suggestions fail closed. Reject produces
`DRAFT_REJECTED_NOT_PUBLISHED`. Approval is required before mock publish, which
returns `IN_MEMORY_ONLY_NOT_PERSISTED` and performs no real publication.
Defensive-copy tests prove caller fixture input is not mutated.

## Product View mock inventory

- Digital Employee directory cards with clear business boundaries;
- one-question business entry;
- employee and bounded plan recommendation;
- proposed mock Instance count and expected sources;
- Human plan confirmation;
- business status, assigned employees, progress and current step;
- prioritized business Outcome and intervention state;
- business-friendly Runtime availability without implementation detail;
- view-only citations with visible mock/governance limitations;
- authoring published/Draft/suggestion/Diff/approve/reject/publish states.

## Technical View mock inventory

- Definition, Agent Definition reference, Instance, Task, Workflow and Platform
  Execution identities;
- requested/effective Runtime, target, version and Binding;
- Runtime Provider and provider-native correlation identities;
- Capability decision and request identity, Provider call count and replay
  barrier;
- internal Outcome and evidence classification;
- desired/effective Instance count, selected Instance, mock utilization and
  recommendation-only capacity presentation;
- Knowledge Collection, Asset, Revision, authorization, retrieved Evidence ID,
  fixture version, citations and provider correlation;
- explicit `DENY`, `UNKNOWN`, `NOT_SUPPORTED` and `NOT_YET_PROVEN` states;
- no automatic retry after possible effects and no exactly-once claim.

## Product-to-Technical mapping

| Product concept | Technical evidence for the same truth |
| --- | --- |
| Mira, Customer Insight Specialist | Digital Employee `de.synthetic.customer-insight.v1`; Definition `definition.synthetic.customer-insight.v1` |
| Assigned mock work | Agent Definition ref `agent-definition.synthetic.customer-insight.v1`; Instance `instance.synthetic.customer-insight.001`; Task `task.synthetic.qi-1042`; Workflow `workflow.synthetic.complaint-analysis.v1` |
| Execution status and Outcome | Platform Execution Identity `pei-synthetic-qi-1042-attempt-1`; internal Outcome `SUCCEEDED / DETERMINISTIC_SYNTHETIC_MOCK` |
| Execution environment available | requested/effective `Native`; target `native deterministic mock profile`; Binding `binding.synthetic.native.qi-1042` |
| Two-person proposed capacity | desired/effective Instance count `2`; selected Instance and `62%` mock utilization; no scale action |
| Approved Knowledge sources | Collection `knowledge-collection.synthetic.quality.v1`; three distinct Asset, Revision and Retrieved Evidence identities |
| Available citations | exact citations link to the three mock Asset revisions and evidence IDs |
| No intervention needed | Capability `ALLOW`, one Provider call; DENY fixture separately proves zero calls |

Both views copy the same Platform Execution Identity from the execution fixture.
Provider-native correlation is distinct and cannot replace Platform identity.

## Runtime support presentation

| Runtime | Product label | Technical state and limitation | Demo role |
| --- | --- | --- | --- |
| Native | `AVAILABLE` | `INTEGRATED_COMPONENT_TESTED_CANDIDATE`; deterministic mock profile; `NOT_CERTIFIED`; production readiness not granted | primary execution path |
| OpenClaw `2026.7.1-2` | `EXPERIMENTAL / NOT CURRENTLY AVAILABLE` | exact-version Candidate; live managed-profile evidence required; support `NOT_GRANTED` | compatibility and safe rejection only |
| Hermes | `EXPERIMENTAL` | `NOT_CURRENTLY_CERTIFIABLE`; support `NOT_GRANTED` | Evidence Debt and extension boundary only |

The architecture panel describes Stable Core, a minimal logical Provider
boundary, pluggable Runtime Providers, Runtime Packages, Compatibility
Manifest and Conformance Evidence. Managed Native Profile/Extension/Plugin
options are labelled `FUTURE_V0_3_PLANNING_ONLY / IMPLEMENTATION_PROHIBITED`.

## Knowledge and Citation evidence

The view-only fixture contains one Collection and three Assets/Revisions, an
internal mock Binding, synthetic Provider, deterministic ALLOW evidence,
zero-call DENY evidence, three Retrieved Evidence IDs and three citations.
Labels are exact: `INTERNAL_MOCK / VERSION_UNFROZEN`, `SYNTHETIC / VIEW_ONLY`,
`LIVE ENTERPRISE PROVIDER: NOT_IMPLEMENTED`, and `GOVERNANCE: NOT_GRANTED`.
It contains no vector/chunk internals and implements no ingestion, RAG,
document parsing, production Knowledge Provider, public DTO or authorization
semantics.

## Mock-state coverage

The deterministic state manifest includes: empty; Draft; Diff pending
approval; approved mock definition; business question entered; employee
recommendation; plan awaiting confirmation; execution running; execution
succeeded; capability denied; outcome unknown; OpenClaw unavailable; Hermes
experimental; Knowledge authorization allowed and denied; citation available;
and citation unavailable or stale. Success is the primary interactive path;
the remaining states are explicit fixture/test evidence for later UX review.

## Validation evidence

Executed on 2026-08-26 against the candidate worktree:

- targeted S5-SPIKE-008 tests: **22 passed**;
- full repository pytest: **520 passed**, with one existing Starlette/httpx
  deprecation warning;
- Ruff lint: **passed**;
- Ruff format check: **98 files already formatted**;
- `make check`: **passed**, including the same 520-test repository suite;
- browser interaction QA: **passed** for step 1 → plan review → confirmation →
  Outcome; exact execution identity in Technical View; AI candidate acceptance;
  Human mock publish; no browser warning/error logs;
- frontend lint/build: **not applicable**; the mock is static HTML/CSS/JS and
  does not use or alter production frontend tooling or dependencies;
- remaining final-head, GitHub CI and audit results are recorded after commit
  in the draft PR and delivery report.

## Human UX01–UX10 decisions prepared

| ID | Candidate for Human decision | Spike evidence |
| --- | --- | --- |
| UX01 | Accept one-question, three-step primary business flow | complete interactive path |
| UX02 | Accept name, role, responsibilities, can/cannot-do and Knowledge Scope minimum | directory fixtures/cards |
| UX03 | Accept Draft, deterministic Diff and Human Approval | reference behavior and authoring UI |
| UX04 | Accept Product/Technical projections of one execution | exact identity equality tests/drawer |
| UX05 | Accept Native as primary visible execution path | support matrix and Product label |
| UX06 | Accept OpenClaw exact-version Candidate/unavailable pending live evidence | exact `2026.7.1-2` state |
| UX07 | Accept Hermes as Experimental/not currently certifiable | explicit support card |
| UX08 | Accept view-only Knowledge fixtures and citations | three traceable citations |
| UX09 | Confirm full Knowledge semantics require a separate ownership gate | visible governance limitation |
| UX10 | Accept proposed Instance count/utilization as mock evidence only | count and recommendation-only panel |

These are prepared decisions, not approvals. Human acceptance remains pending.

## Limitations and Evidence Debt

- Static local prototype; no production Console route, API, backend or DTO.
- No persistence, authorization engine, publish service, workflow execution,
  Runtime invocation, retry, scaling, provider discovery or external call.
- No live OpenClaw evidence, Hermes certification, Native certification,
  support or production-readiness claim.
- No production Knowledge semantics, Provider, source, ingestion, RAG or
  governance. Full Knowledge ownership remains unresolved.
- Mock identities and JSON shapes are disposable, internal and version-unfrozen;
  downstream implementation must adapt to the accepted Track A/D handoff and
  must not import this experiment into production.
- Human UX01–UX10 convergence and a separately authorized integration Session
  remain required. Golden Demo production integration has not started.

## Rollback

Delete or revert only
`experiments/s5-spike-008-authoring-view-mock-prototype/` and
`docs/evidence/s5/v0.2/s5-spike-008/`. There is no migration, persistent state,
Runtime resource, Knowledge index, dependency or lockfile cleanup. Production
behavior and public contracts are unaffected.
