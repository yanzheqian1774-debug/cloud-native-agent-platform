# S5-PLAN-003 — v0.2 Product Intent and Golden Demo Portfolio Rebaseline

## 1. Authority and status

| Field | Value |
| --- | --- |
| Session | `S5-PLAN-003` |
| Type | `PLAN` |
| Lifecycle | `CLOSING` |
| Checkpoint | `B — INDEPENDENT_PORTFOLIO_CONSISTENCY_SEQUENCE_AND_MERGE_READINESS` |
| Human decision | Checkpoint A `AUTHORIZED_WITH_CONSTRAINTS`; Checkpoint B review `AUTHORIZED_WITH_CONSTRAINTS` |
| Baseline | `329da75d802886300a6f721c0205d1e5b23c2074` |
| Exact-main CI | `33139763263 / SUCCESS` |
| Branch | `codex/s5-plan-003-v0-2-product-intent-golden-demo-rebaseline` |
| Implementation authorization | `NOT_GRANTED` |
| Release acceptance | `NOT_GRANTED` |

This plan converts the accepted boundaries in [S5-ARCH-010](../../../architecture/s5/v0.2/S5-ARCH-010-PRODUCTION-EXECUTION-EVIDENCE-SHARED-READ-MODEL-BOUNDARY-V1.md), [S5-ARCH-011](../../../architecture/s5/v0.2/S5-ARCH-011-PRODUCT-INTENT-DYNAMIC-WORK-ROLE-KNOWLEDGE-CONSUMPTION-BOUNDARY-V1.md), and [S5-ARCH-012](../../../architecture/s5/v0.2/S5-ARCH-012-USER-INTERVENTION-PREFERENCE-FEEDBACK-GOVERNED-OPTIMIZATION-BOUNDARY-V1.md) into an implementation and integration sequence. It allocates no downstream task ID and starts no implementation.

It retains [S5-PLAN-001](S5-PLAN-001-V0.2-IMPLEMENTATION-PORTFOLIO.md) as historical authority for completed work and partially supersedes only its unstarted remaining v0.2 sequence, Golden Demo route, and release-readiness route. [S5-PLAN-002](S5-PLAN-002-HARNESS-PARALLEL-READINESS.md) is unrelated, unchanged, and not reused.

## 2. Product intent and bounded proof

v0.2 is rebaselined around one truthful supplier-quality exception-analysis journey:

```text
business question
→ model-assisted Intent candidate
→ deterministic validation and canonicalization
→ Task decomposition and Workflow candidate
→ exact-digest Human approval
→ canonical Workflow revision
→ governed descriptor and published-role matching
→ Runtime Requirement and bounded Native placement
→ authorized Knowledge retrieval
→ Native execution and immutable Evidence
→ Product answer
→ Product semantic correction
→ newly approved immutable successor
→ successor execution and comparable Outcome
→ Product and Technical inspection
→ Intervention and Outcome feedback record
```

The ordinary experience stays business-first. Technical identities, matching details, policy decisions, and traces use progressive disclosure. Product and Technical views are sibling projections, never Workflow, Evidence, Graph, Knowledge, Runtime, authorization, preference, or optimization authority.

### Model-assisted generation boundary

Model-assisted or replaceable candidate generation may interpret a free-form question and propose Intent, Tasks, Workflow structure, matching suggestions, and explanatory text. Its output is untrusted. Schema validation, canonicalization, stable identity, digest calculation, dependency ordering, cycle rejection, supported-requirement checks, authorization, and approval binding are deterministic.

Malformed, ambiguous, unsupported, contradictory, or `UNKNOWN` requirements fail closed or return for Human correction. A model cannot approve itself, directly create an executable canonical revision, override compatibility or authorization, grant credentials, publish a role, select an unsupported Runtime fallback, manufacture citations, mutate Evidence, or apply preferences or optimization. Only the approved exact canonical digest may reach matching, placement, retrieval, Capability invocation, Provider invocation, or Runtime execution; every preapproval path produces zero such calls.

## 3. Current capability inventory

Current source and tests establish Agent, Task, and Workflow CRDs; the Kubernetes Operator; bounded Native execution; Platform Execution Identity; append-only Execution Evidence; Canonical Graph projection; a deterministic shared execution snapshot; and Product and Technical preview views.

The repository does not currently implement the planned Intent engine, governed descriptor and role matcher, live bounded Knowledge Pack, correction/successor journey, intervention/feedback records, preference/candidate preview, supplier-quality Scenario Pack, enhanced Golden Demo, or release-readiness proof. Planning status must never be presented as implemented capability.

## 4. v0.2 target and boundary

| Classification | Scope |
| --- | --- |
| `V0_2_MUST` | bounded question intake; `IntentRevision`; `TaskRequirement`; `WorkflowCandidate`; deterministic validation/canonicalization; exact-digest approval; `CanonicalWorkflowRevision`; curated Data/Knowledge/Skill/Capability/published-role matching; `ROLE_GAP`; `RuntimeRequirement`; bounded Native placement; authorization-before-invocation and retrieval; one read-only Knowledge Pack; live retrieval Evidence/citations; Native execution; immutable Execution Evidence; shared sibling views; `ProductSemanticCorrection`; immutable successor and rerun; comparable Outcome; `InterventionEvent`; `OutcomeFeedback`; deterministic Scenario Pack; Enhanced Golden Demo; release-readiness evidence |
| `V0_2_SHOULD` | before/after metrics; citation relevance/usefulness; intervention/feedback capture UX; visibly labelled synthetic history; role-gap/preview explanations; cost and latency comparison |
| `V0_2_PREVIEW_ONLY` | non-matchable `RoleCandidatePreview`; user-controlled `UserPreferenceProfile`; `ImprovementCandidate` fixed at `DRAFT / NOT_APPLIED`; consent, scope, and deletion presentation; zero execution authority |
| `V0_3_OR_LATER` | generated-role publication/matching; Agent/Skill/Capability Factory; Tool/Connector Marketplace; `PublishedOptimization`; automatic policy application; generalized learning; enterprise Preference/State Plane; Runtime Manager; distributed placement, scaling, healing, migration, failover; generalized Recovery; OpenClaw/Hermes managed support; Certification; enterprise Knowledge operations; production vector database/RAG/MCP breadth; Knowledge writeback; cross-tenant learning |

## 5. Authority map

| Concern | Sole authority | Prohibited substitute |
| --- | --- | --- |
| Candidate generation | model-assisted/pluggable generator | executable or approved record |
| Validation, canonical identity and digest | deterministic planning validator | model or frontend |
| Approval | exact-digest Human decision | planner, model, or metric |
| Canonical revision | canonical revision authority | Product/Technical projection |
| Descriptor and role selection | authorization-first deterministic matcher | descriptor, model suggestion, or preview |
| Runtime placement | bounded Native placement evaluator | frontend or unavailable external Runtime |
| Execution state | existing Kubernetes resources/controllers | Evidence repository or view |
| Execution facts | append-only Evidence authority | Workflow status, frontend, or optimization record |
| Relationships | existing Canonical Graph | view-local relation or identifier |
| Knowledge authorization/retrieval | independent policy and bounded retrieval authorities | descriptor, MCP transport, model, or citation projection |
| Shared view identity | deterministic backend snapshot assembler | sibling frontend adapters |
| Correction/successor | correction compiler, validator, approval, canonical revision authority | direct Product mutation |
| Intervention and feedback | separately typed append-only authorities | Evidence rewrite or policy |
| Preference/candidate preview | consented preview authorities | Planner, authorization, publication, or application authority |

## 6. Packages and sequence

There are ten logical packages: `1`, `2`, `3`, `4`, `5`, `6A`, `6B`, `7`, `8`, and `9`. Every identifier remains `UNALLOCATED` pending a separate Human allocation and collision check.

Mandatory critical path:

```text
1 → 2 → (3 || 4) → 5 → 6A → 7 → 8 → 9
```

Optional preview path:

```text
(5 + 6A + separate Human G2 approval) → 6B
```

Package 7 may begin after Packages 1–5 are durably integrated, but final Golden Demo acceptance requires 6A. Package 6B is outside the Product MVS and mandatory critical path and may not block the Golden Demo, bounded core release, or ordinary execution.

Packages 3 and 4 may start in parallel only after Packages 1 and 2 durably fix the shared requirement IDs, descriptor/binding IDs, canonical digest/version rules, tenant/security-domain context, authorization decision references, and projection-safe reason-code vocabulary. That synchronization gate freezes only the internal package inputs needed by both branches; it does not freeze a public Contract. Any unresolved ownership or semantic change returns to the owning package or a Human G2 gate rather than allowing divergent local contracts.

### Package 1 — Bounded Intent and Canonical Planning Engine

- **Session type / authority:** future `IMPL`, then durable integration; S5-ARCH-011.
- **Prerequisites:** accepted internal identities and existing authoring/execution bridge.
- **Objective:** turn a bounded question into an untrusted candidate, deterministic validated plan, exact approval, and immutable canonical revision.
- **Mandatory scope:** model-assisted candidate port; `IntentRevision`, `TaskRequirement`, and `WorkflowCandidate`; schema/resource limits; canonical serialization/digest; deterministic dependency ordering; cycle rejection; supported/unknown checks; exact approval binding; `CanonicalWorkflowRevision`.
- **Prohibited:** autonomous approval, direct model execution, public CRD/API, or changed Task/Workflow lifecycle.
- **Likely paths / ownership:** bounded `console/backend/src/agent_console/` domain/service modules and focused backend/operator bridge tests; owns planning contracts, not current controller lifecycle.
- **Implications:** no public API, CRD, Canonical Graph, or Workflow semantic change. Discovery of one stops at G2.
- **Validation:** local unit/contract/mutation/replay tests, `make check`, Ruff, exact-head CI; no Browser QA unless a later UI package consumes it.
- **Rollback:** disable candidate intake/publication bridge; existing execution remains unchanged.
- **Exit / downstream:** only the approved exact digest can be matched or executed; blocks 2–5, 7–9.
- **Gate / ID:** G1; G2 for public/lifecycle change; task ID `UNALLOCATED`.

### Package 2 — Curated Descriptor and Published-Role Matcher

- **Session type / authority:** future `IMPL`, then durable integration; S5-ARCH-011 and accepted Definition/Capability boundaries.
- **Prerequisites:** Package 1 stable requirement and revision identities.
- **Objective:** bind required Data, Knowledge, Skill, Capability, and existing published roles deterministically after authorization.
- **Mandatory scope:** stable descriptor IDs/versions; authorization and compatibility before scoring; stable reasons and ties; selected versions; missing requirements; only `PUBLISHED/MATCHABLE` Definitions; explicit `ROLE_GAP`; optional non-matchable role preview.
- **Prohibited:** marketplace, generated publication/matching, Instance creation, credential or permission grants.
- **Likely paths / ownership:** bounded backend catalogs/matcher/policy ports and tests; owns match decisions, not descriptor publication or authorization policy.
- **Implications:** no public API/CRD/Graph/Workflow change.
- **Validation:** input permutations, ties, gaps, denied-candidate non-observation and non-disclosure, preview rejection at every execution boundary, local/CI quality gates.
- **Rollback:** disable new matcher and bindings without changing published Definitions.
- **Exit / downstream:** every required binding has an exact authorized result or stable fail-closed gap; blocks 3–5 and 7–9.
- **Gate / ID:** G1; Definition lifecycle/authorization ownership change requires G2; task ID `UNALLOCATED`.

### Package 3 — Runtime Requirement and Native Placement Bridge

- **Session type / authority:** future `IMPL`, then durable integration; S5-ARCH-011 and current Native Runtime boundary.
- **Prerequisites:** Packages 1 and 2.
- **Objective:** derive `RuntimeRequirement` and deterministically select an already-declared compatible Native target.
- **Mandatory scope:** placement request/decision, exact target version, stable reason codes, availability and compatibility checks, honest unavailable/unsupported states.
- **Prohibited:** provisioning, Runtime Manager, external routing, OpenClaw/Hermes, pools, failover, Recovery, certification.
- **Likely paths / ownership:** bounded backend bridge plus existing operator/runtime integration seams and focused tests; owns placement decision, not Runtime lifecycle.
- **Implications:** no public API/CRD/Graph/Workflow change.
- **Validation:** absent target, unsupported requirement, deterministic choice, authorization denial with zero Provider call, local/CI gates.
- **Rollback:** disable placement bridge; no target lifecycle action or migration.
- **Exit / downstream:** approved matched work either receives the exact Native target or fails explicitly; blocks 5 and 7–9.
- **Gate / ID:** G1; Runtime lifecycle change requires G2; task ID `UNALLOCATED`.

### Package 4 — Bounded Knowledge Pack and Authorized Retrieval

- **Session type / authority:** future `IMPL`, then durable integration; S5-ARCH-011 with S5-ARCH-010 Evidence rules.
- **Prerequisites:** Package 1 identities and Package 2 authorization-capable matching; may run parallel with Package 3 after shared identities stabilize.
- **Objective:** provide one live, authorization-first, read-only Knowledge path with stable references, Evidence, and citations.
- **Mandatory scope:** descriptors/bindings; stable document/version/section/chunk identities and digests; authorization before retrieval; deterministic ordering; `KnowledgeRetrievalEvidence`; independently authorized citations; sibling projection.
- **Prohibited:** ingestion platform, vector database, production RAG, writeback, enterprise operations, synthetic live citation/fallback, MCP authority.
- **Likely paths / ownership:** bounded backend Knowledge/retrieval/policy/Evidence modules, approved Demo configuration, and security/contract tests; owns retrieval result, not Knowledge publication.
- **Implications:** no public API/CRD/Graph/Workflow change; new persistent infrastructure requires G2.
- **Validation:** `DENY` zero calls and zero identity/title/count/chunk/existence disclosure; deterministic ties; exact citation binding; tenant/security isolation; distinct `STALE`, `EXPIRED`, `DENIED`, `NOT_FOUND`, `UNAVAILABLE`, `UNKNOWN`, and `ERROR`; local/CI gates.
- **Rollback:** disable live retrieval/citation adapter; never switch silently to fixtures.
- **Exit / downstream:** required authorized Knowledge yields live Evidence-backed citations or an exact fail-closed state; blocks 5 and 7–9.
- **Gate / ID:** G1 plus security/exact-path gate; persistent architecture requires G2; task ID `UNALLOCATED`.

### Package 5 — Product View Live Planning and Correction Journey

- **Session type / authority:** future `IMPL`, then durable integration; S5-ARCH-010/011/012 and the shared-view implementation.
- **Prerequisites:** Packages 1–4.
- **Objective:** expose the live business journey without transferring canonical authority to either view.
- **Mandatory scope:** question-to-plan state; approval; matching/placement results; live answer and citations; `ProductSemanticCorrection`; deterministic patch/validation; new approval; immutable successor; rerun and comparable Outcome; equal Product/Technical source identities.
- **Prohibited:** frontend plan, Graph, Evidence, authorization, citation, or revision authority; silent fixture fallback.
- **Likely paths / ownership:** shared backend DTO/service/projection modules and Product/Technical frontend adapters/pages/tests; backend owns shared identity, frontend owns presentation only.
- **Implications:** no public API/CRD/Graph/Workflow semantic change; any new external/public boundary needs its gate.
- **Validation:** backend equality/direct-mutation tests; frontend lint/build; live/error/stale/deny states; desktop and `390×844` Browser QA in its implementation session.
- **Rollback:** disable live planning/correction adapters while retaining explicit preview mode and existing execution.
- **Exit / downstream:** the Product MVS journey reaches a newly approved successor and comparable Outcome with identical sibling identities; blocks 6A, 6B, and 7–9.
- **Gate / ID:** G1; public API or authority change requires G2; task ID `UNALLOCATED`.

### Package 6A — Intervention and Outcome Feedback Record

- **Classification / type / authority:** `V0_2_MUST`; future `IMPL`, then durable integration; S5-ARCH-012.
- **Prerequisites:** stable Package 1 and Package 5 identities.
- **Objective:** record correction interventions and feedback as auditable facts without rewriting revisions, Outcomes, Evidence, or policy.
- **Mandatory scope:** append-only `InterventionEvent`; exact element/prior/successor/execution/Outcome/Evidence links; stable reasons; Human principal/time; versioned `OutcomeFeedback`; supersession; synthetic/live provenance; tenant/security isolation; bounded sibling projections.
- **Prohibited:** preference inference, optimization publication, Planner/Workflow policy mutation, Knowledge writeback, cross-tenant aggregation, raw prompts, secrets, credentials, or unrestricted payloads.
- **Likely paths / ownership:** bounded typed backend ports/repositories and shared projection contracts/tests; owns intervention/feedback facts, not Execution Evidence or policy.
- **Implications:** no public API/CRD/Graph/Workflow change. Reuse of the append-only repository requires an exact compatibility scope; new persistence authority or deletion semantics requires G2.
- **Validation:** append/supersession/immutability, authorization, isolation, provenance, prohibited-field, non-critical write-failure isolation, local/CI gates; Browser QA for capture/projection UX when implemented.
- **Rollback:** disable capture/projection while retaining already governed records; execution state remains untouched.
- **Exit / downstream:** corrections and feedback produce linked append-only records; original revision, Outcome, and Evidence remain immutable; required before 8 and 9 but not the earliest execution-only slice.
- **Gate / ID:** G1 if compatible reuse is proven; otherwise Human G2; task ID `UNALLOCATED`.

### Package 6B — Preference and Improvement Candidate Preview

- **Classification / type / authority:** `V0_2_PREVIEW_ONLY`; future `IMPL`; S5-ARCH-012.
- **Prerequisites:** stable Packages 5 and 6A identities and a separate Human G2 persistence/privacy/State decision.
- **Objective:** present user-controlled preferences and draft improvement candidates with no influence on planning or execution.
- **Mandatory scope:** visible preference preview; explicit consent/scope; edit, disable, delete; non-recoverable-value tombstone; synthetic/live Evidence-set separation; `ImprovementCandidate` fixed at `DRAFT / NOT_APPLIED`; Product and Technical preview.
- **Prohibited:** current/future planning influence, personalization, publication/application, production learning, cross-user/tenant promotion, Knowledge writeback.
- **Likely paths / ownership:** separately gated backend State/privacy ports, projection DTOs, preview UI, and privacy/security tests; owns preview values/candidates only.
- **Implications:** no public API/CRD/Graph/Workflow change; selected storage/State/deletion architecture is unresolved.
- **Validation:** consent/withdrawal, conflict precedence, erasure/cache/backup-restoration behavior, tombstone non-recoverability, zero execution influence, frontend lint/build and desktop/`390×844` Browser QA.
- **Rollback:** disable preview and future selection; execute governed deletion; never affect ordinary work.
- **Exit / downstream:** preview is visibly user-controlled and `NOT_APPLIED`; optional for 8 and outside Product MVS/release critical path.
- **Gate / ID:** separate Human G2 required; task ID `UNALLOCATED`.

### Package 7 — Supplier Quality Demo Scenario Pack

- **Session type / authority:** future `SOLUTION/DEMO`, then durable integration; S5-ARCH-006/011/012.
- **Prerequisites:** Packages 1–5 durably integrated; 6A before final Golden Demo acceptance. 6B is optional.
- **Objective:** package a deterministic bounded supplier-quality environment for clean reproduction.
- **Mandatory scope:** exact scenario ID/namespace; sanitized business data; curated descriptors and published roles; minimum Knowledge Pack; idempotent bootstrap; bounded reset; checksums; explicit `DEMO_CONFIGURATION`, `SYNTHETIC_HISTORY`, and `LIVE_EXECUTION` labels.
- **Prohibited:** generalized platform assets, production data/Knowledge claims, hidden fallback, destructive broad reset.
- **Likely paths / ownership:** repository-native manifests/examples/configuration, scenario docs/tests; owns only Demo configuration and reset boundary.
- **Implications:** no public API/CRD/Graph/Workflow change; new persistent infrastructure requires G2.
- **Validation:** repeated initialization/reset, exact namespace targeting, clean environment, provenance and secret scans, no cross-domain leakage, local/CI gates.
- **Rollback:** bounded target-validated reset/removal; no broad or implicit deletion.
- **Exit / downstream:** clean environments reproduce the same bounded live scenario and labelled history; blocks 8 and 9.
- **Gate / ID:** G1 and exact Demo scope gate; task ID `UNALLOCATED`.

### Package 8 — Enhanced Golden Demo Acceptance

- **Session type / authority:** future `TEST/SOLUTION`, then independent durable integration; accepted Golden Demo contract and S5-ARCH-010/011/012.
- **Prerequisites:** Packages 1–5, 6A, and 7; 6B only if separately approved and complete.
- **Objective:** prove the complete live bounded claim set and rollback.
- **Mandatory scope:** live planning/matching/retrieval/execution/correction/Outcome; intervention/feedback; identity equality; zero-call denial; no fallback; claim/evidence and limitation inventories; rollback rehearsal; desktop/mobile acceptance.
- **Prohibited:** inferred certification, production readiness, external Runtime, or optional preview claims.
- **Likely paths / ownership:** Golden E2E/conformance tests, evidence reports, runbooks, frontend acceptance; owns acceptance evidence, not implementation authority.
- **Implications:** validation only; no public API/CRD/Graph/Workflow change.
- **Validation:** clean bootstrap/reset, failure matrix, `DENY` zero Provider and Knowledge calls/no metadata, exact identity equality, before/after Outcome, rollback, desktop and `390×844` Browser QA, full CI.
- **Rollback:** revert acceptance artifacts; execute the Scenario Pack's bounded rehearsal, never mutate canonical history.
- **Exit / downstream:** every supported claim has exact Evidence and every limitation is visible; blocks 9.
- **Gate / ID:** no new G2 if validation remains within accepted behavior; task ID `UNALLOCATED`.

### Package 9 — v0.2 Release Readiness Candidate

- **Session type / authority:** future release-readiness evidence and separately Human-allocated `REL`; Definition of Done and release governance.
- **Prerequisites:** all mandatory packages durably integrated and Package 8 accepted.
- **Objective:** assemble evidence for a Human v0.2 release decision.
- **Mandatory scope:** exact-main CI; full validation; clean supported-environment reproduction; security/privacy/secrets/authorization/tenant reviews; provenance/Evidence/rollback inventories; supported/unsupported claims.
- **Prohibited:** automatic release, inferred certification, or unsupported production claims.
- **Likely paths / ownership:** separately authorized release evidence/docs/governance paths; owns readiness evidence only.
- **Implications:** no public API/CRD/Graph/Workflow change.
- **Validation:** `make check`, Ruff, frontend lint/build, clean reproduction, claim and rollback audits, exact-main CI.
- **Rollback:** revert readiness evidence; no release or runtime action without Human authority.
- **Exit / downstream:** complete evidence reaches an explicit Human release decision.
- **Gate / ID:** release gate; G2 only for discovered architecture change; task ID `UNALLOCATED`.

## 7. Product MVS gate

The Product MVS requires an unprepared bounded question to produce traceable candidate Intent, Tasks, and Workflow; deterministic validation and Human approval bound to one exact canonical digest; deterministic governed matching with explicit gaps; live authorized Knowledge retrieval and Native execution; Evidence and citations supporting the answer; a newly approved immutable successor after correction; a comparable successor Outcome; identical canonical identities in Product and Technical views; and proof that no unapproved candidate executes.

Package 6A may follow the earliest execution-only vertical slice but must finish before Golden Demo acceptance and Release Readiness. Package 6B is not a Product MVS requirement.

## 8. Knowledge scope

The mandatory read-only Pack contains issue-severity rules, closure-time policy, escalation rules, the 8D procedure, and sanitized historical cases. Source assets may be deterministic Demo configuration, but authorization, descriptor binding, retrieval, ordering, Evidence creation, citation binding, and sibling projection run live.

`DENY` performs zero retrieval calls and leaks no Knowledge identity, title, count, chunk, or existence. Live mode has no synthetic citation or fixture fallback. Stale, expired, denied, not-found, unavailable, unknown, and error states remain distinct. MCP is transport-only and never Knowledge authority. The package makes no ingestion, vector database, production RAG, writeback, or enterprise Knowledge operations claim.

## 9. Demo Scenario and Golden Demo gates

The Scenario Pack uses an exact namespace and scenario identity, deterministic idempotent bootstrap, bounded reset, sanitized supplier-quality data, curated descriptors/roles, the minimum Knowledge Pack, and explicit provenance.

Golden Demo acceptance requires live current planning, matching, retrieval, execution, correction, Evidence, Outcome, append-only intervention, and versioned feedback; visibly labelled synthetic history; no silent fallback or synthetic live citation; `DENY` zero Provider/Knowledge calls and no metadata disclosure; before/after Outcome comparison; Product/Technical identity equality; rollback rehearsal; claim-to-Evidence mapping; visible limitations; and desktop plus `390×844` validation. Package 6B may appear only after its separate G2 and implementation and remains visibly preview-only.

## 10. Release Readiness gate

All mandatory packages must be durably integrated. Exact-main CI, full validation, clean supported-environment reproduction, security/privacy/secrets/authorization/tenant review, provenance/Evidence/rollback inventories, and supported/unsupported claim audits must pass. No OpenClaw, Hermes, MCP, Recovery, Certification, distributed Runtime, automatic optimization, enterprise Knowledge, or production-readiness claim is allowed without exact evidence. Release requires a separate Human approval.

## 11. Metrics

Every metric records numerator, denominator, tenant/domain/scope, time window, definition and dataset versions, synthetic/live provenance, authorized audience, and limitations. Empty denominators are `NOT_MEASURABLE`. Metrics observe evidence and never authorize execution or publication.

Required demonstration metrics are first-plan acceptance, corrections per task, task/role/Skill replacement, role-gap rate, retrieval relevance, citation validity/usefulness, execution success, correction-to-Outcome improvement, latency/cost comparison, intervention capture, and feedback capture. The `DENY` zero-call rate must be 100%. Preference use and candidate generation are preview-only. Candidate adoption, production rollback, and generalized-learning metrics are deferred until the corresponding v0.3 authorities exist.

## 12. Risks and mitigations

| Threat or risk | Prevention / fail-closed behavior | Validation owner or future gate |
| --- | --- | --- |
| Prompt injection influences canonical approval | Treat all generated content as untrusted; allowlisted schema/canonicalizer; exact Human approval cannot be supplied by content | Package 1 adversarial parser, digest, approval-replay, and zero-preapproval-call tests |
| Approval replay or semantic mutation | Bind canonicalizer version, candidate identity, tenant/security domain, and exact semantic digest; mismatch rejects | Package 1 contract and mutation tests |
| Malicious, poisoned, or unauthorized descriptor | Authorize and validate compatibility before candidate creation/scoring; denied descriptors contribute no rank, reason detail, or count | Package 2 poisoning, permutation, nondisclosure, and tie tests |
| Unauthorized Knowledge discovery | Authorize before retrieval; `DENY` makes zero calls and returns no existence, identity, title, count, or chunk metadata | Package 4 security and timing/count review |
| Citation forgery or stale substitution | Only the backend may bind independently authorized citation IDs to exact document/version/section/chunk digests and retrieval Evidence | Packages 4 and 5 citation mutation and sibling-equality tests |
| Role fallback escalates authority | Match only existing `PUBLISHED/MATCHABLE` Definitions; `ROLE_GAP` grants nothing; previews are rejected at every execution boundary | Package 2 lifecycle and negative-boundary tests |
| Runtime fallback or provider escalation | Select only a declared available compatible Native target; unavailable/unsupported requirements fail with zero Provider call | Package 3 placement and zero-call tests |
| Unapproved execution | No matching, retrieval, placement, Capability, Provider, or Runtime call before exact canonical approval | Packages 1–4 integration tests and Package 8 E2E |
| Cross-tenant matching, retrieval, cache, or projection | Trusted tenant/security-domain context, pre-query isolation, domain-bound cache/snapshot, fail closed on mismatch | Packages 2, 4, 5, and 6A isolation tests; enterprise tenant architecture remains future |
| Sensitive intervention or feedback payload | Typed allowlisted fields only; reject raw prompts, Provider bodies, secrets, credentials, arbitrary metadata, and unrestricted payloads | Package 6A prohibited-field and redaction tests |
| Preference inferred or used without consent | Inference may only create a visible suggestion; explicit versioned consent/scope required; Package 6B has zero planning influence | Separate Package 6B Human G2 and consent/withdrawal tests |
| Deleted preference remains recoverable | Separate value/audit storage; erase active/cache copies; tombstone retains no value, digest, embedding, ciphertext, or sensitive metadata | Package 6B privacy/deletion G2 and backup-restore tests |
| Metric manipulation becomes authority | Versioned numerator/denominator/dataset/provenance; metrics remain evidence only and cannot approve or publish | Packages 6A/6B and 9 metric/claim audits |
| Optimization candidate published by implication | v0.2 candidate is always `DRAFT / NOT_APPLIED`; no publication or application port exists | Package 6B zero-influence tests and separate future v0.3 architecture gate |
| Synthetic history presented as live | Immutable provenance classes, separated counts, visible labels, and rejection of mixed/hidden provenance | Packages 4, 6A/6B, 7, and 8 provenance tests |
| Hidden live-to-fixture fallback | Live and synthetic modes are explicit; live failure remains failure and cannot load fixture results or citations | Packages 4, 5, 7, and 8 failure/fallback tests |
| Package ownership collision | Single writer per authority and separate implementation/durable-integration sessions | Human task allocation and every package entry gate |

## 13. Rollback and compatibility

This plan changes no application behavior, public API, CRD, Kubernetes API group, Canonical Graph semantics, dependency, or Workflow lifecycle. Future packages must keep rollback bounded to their adapters, configuration, or separately governed records. Rollback never rewrites canonical revisions, Outcomes, or Evidence; never silently enables fixtures; and never performs broad data deletion. Any package that discovers a need for a public schema, changed lifecycle, new authority, persistent infrastructure, Tenant/State architecture, or production claim stops at a Human G2 gate.

## 14. Task allocation and integration rules

- No implementation, `REL`, `TEST`, `DEMO`, `SOLUTION`, release, or evidence-debt task ID is allocated here.
- Human allocation and collision checking precede every future task.
- Material packages use separate implementation and durable-integration sessions.
- One writer owns each shared contract or high-conflict path.
- Package completion is not durable integration, Golden Demo acceptance, release readiness, or release approval.
- Package 6B remains outside the critical path and cannot delay ordinary execution.

## 15. Governance reconciliation and traceability

S5-ARCH-010 is Human-confirmed closed with constraints; PR #69 merged as `13bc16f746a58912bc093ff249ff390250ce20cf`, with exact-main CI `33049808981 / SUCCESS`. S5-ARCH-011 remains Human-confirmed closed; PR #72 merged as `0ea21ab628561f2e1e5e1a08651e9ef5a9b8fc79`, with exact-main CI `33083580433 / SUCCESS`. S5-ARCH-012 is Human-confirmed closed with constraints; PR #73 merged as `329da75d802886300a6f721c0205d1e5b23c2074`, with exact-main CI `33139763263 / SUCCESS`.

These are forward terminal addenda. Historical checkpoint evidence is unchanged and none of the architecture sessions is reopened. S5-PLAN-003 owns only this rebaseline. No downstream implementation, Product MVS, Golden Demo, release, production-readiness, certification, or v0.3 completion is claimed.

| Architecture authority | Portfolio packages |
| --- | --- |
| S5-ARCH-010 — execution Evidence and shared read model | 4, 5, 6A, 8, 9 |
| S5-ARCH-011 — Intent, dynamic work, roles, Runtime and Knowledge | 1, 2, 3, 4, 5, 7, 8 |
| S5-ARCH-012 — correction, intervention, feedback and governed preview | 5, 6A, 6B, 7, 8 |

## 16. Checkpoint B independent review result

The independent review found no contradictory v0.2 classification, missing package, circular dependency, public API/CRD/Graph/Workflow assumption, unsupported capability claim, or broken authority boundary. It required one bounded linear clarification: the exact Package 3/4 synchronization gate, explicit zero-call preapproval coverage, complete misuse dispositions, and exact Ruff inspection wording in the evidence index.

This remains a planning artifact only. The next gate is the Human S5-PLAN-003 Merge Gate, followed by an independently authorized merge/close sequence. Until those gates pass, every downstream package and identifier remains `UNALLOCATED / NOT_ACTIVE / NOT_AUTHORIZED`.


<a id="s5-v023-impl-322"></a>
## S5-V023-IMPL-322 — 问题工作台视觉收口——对齐最终效果图

2026-09-17 Human-authorized bounded frontend increment. This entry owns scope,
comparison, evidence and remaining work; no parallel plan or authority package.
Registration is local in the existing Governance Registry, not durable-main or
external Delivery-Tracking publication. Repository registries across available
worktrees, local branches, remote matching heads, GitHub issue/PR search and
visible tasks found no competing allocation. The sole matching task is this task.

### Baseline and write gate

- Read-only starting main: `b5e013f806bd864e0c10ba421b7966e084b36576`.
- Reference candidate: PR #181 OPEN, source `4001b412340398ea42d813efd7f7f5f2cf9bf01d`, tree `846e7b5536ebd68d2e12d31d907d0e32a6195a70`; not received, copied or merged.
- Current owner task is ACTIVE and has uncommitted `DraftAssistanceCard.tsx` and `s5-321-understanding.spec.ts` changes. Candidate delivery does not transfer write ownership. No shared UI write is permitted yet.
- Implementation baseline remains UNSELECTED pending explicit owner handoff and mutually fixed source/tree. Existing Session closure is not required. No automatic integration of #179/#180/#181.
- One existing isolated worktree, one branch `codex/s5-v023-impl-322-workbench-visual`, one eventual Draft PR. No subtask Session or subagent.

### Final references and observed gaps

Final references: `/Users/tristan/Downloads/101.png` and `102.png` for conversation
and confirmation; `103.png` for visual styling only. All three are available.
No earlier replaced images are used. Future execution, planning and resource
buttons shown in references are not authorized functionality.

Observed comparison inputs are the upstream owner's current local
`docs/evidence/s5/v0.2/s5-v023-impl-321/experience-review/` screenshots:
`02-clarification.png`, `05-confirm-current.png`, `07-refreshed-fixture.png`.
These are labelled UI/API fixtures, currently uncommitted, not immutable candidate
or real-model proof. Their gaps must be rechecked against the handed-off baseline.

| State | Observed gap | Bounded proposed change | Protected behavior |
| --- | --- | --- | --- |
| Initial input | Large nested shell and competing contextual text | Clear heading, readable input and a single primary submit action | Existing authorization and explicit submission |
| Clarification | Refusal/manual fallback are prominent; answer action distant; draft-success badge can conflict with missing information | Foreground question and current understanding; secondary fallback styling; state-accurate badge | Current owner's ongoing status fix; user corrections and unknown facts |
| Confirmation | Small fact labels/body; conversation and confirmation are visually fragmented | Readable goal/fact card, consistent spacing, one primary confirm action | Latest revision equals submitted payload; no automatic confirmation |
| Created/readback | Heading remains new conversation; permission and summary cards repeat; refresh action dominates | State-aware heading, one next action, quieter historical authorization details | Creation fact card stays mounted; READ is independent; restoration provenance and scroll stability |
| All states | Dense nested cards, small labels, multiple equally weighted outlines | Scoped typography, blue/neutral palette, lighter borders/shadows, consistent buttons and status chips | Visible focus, keyboard and mobile access |

### Proposed implementation scope

Reuse `console/frontend/src/problems/ProblemWorkspacePage.tsx`,
`ProblemConversation.tsx`, `DraftAssistanceCard.tsx`, the existing understanding
and context-card components, and their current stylesheet. Limit style selectors
to the problem workspace. Inspect handed-off CSS and source before changing;
do not redesign global navigation or introduce another workspace.
Keep handlers, contracts, model policies, persistence, authorization and
idempotency unchanged. Technical details default collapsed; material failures,
unknown outcomes, synthetic provenance and required approvals remain visible.
Never relabel created/read-back as executing or solved.

### Validation and delivery plan

After handoff, capture the same synthetic case before and after at desktop and
390px mobile widths: initial input, clarification, confirmation and readback.
Reuse existing understanding, W2A/W3 and isolated browser journeys. Verify IME,
held Enter, focus visibility/order, stale response protection, correction adoption,
creation retry/idempotency, independent READ and refresh/scroll restoration.
Use a task-owned isolated environment, never the upstream acceptance environment
or a formal Problem; real model calls prohibited. Fixture screenshots are visual
proof only, not backend persistence proof.
Run `make check`, frontend `npm run lint` and `npm run build`, relevant browser
gates, normal commit hooks and non-force push; create only one Draft PR after
baseline selection. No tests were executed in this read-only preparation stage.

Remaining: explicit handoff/source/tree/sole writer; immutable before screenshots;
UI implementation; after screenshots; relevant gates; one reviewable Draft PR.
Nonblocking extra ideas stay in this existing plan entry as follow-up, not scope
expansion. Completion requires visual consistency and no behavioral regression;
Human controls Ready, merge, deployment and Session closure.


### Formal shared UI handoff received — 2026-09-17

Owner task `01a0adf4-2cb3-78e1-8ec5-276c8d7a3db2` explicitly stopped writes to
`console/frontend/src/api/draftAssistanceTypes.ts`,
`src/problems/{DraftAssistanceCard,ProblemConversation,ProblemWorkspacePage}.tsx`,
`src/problems/{problemConversationModel,problemUnderstandingModel}.ts`
(all src paths beneath console/frontend), and frontend styles/shell/browser tests.
The owner states remaining work is quality-preparation documentation only;
no remaining shared UI modification was identified. This task accepts that
file-ownership handoff; shared UI remains unwritten pending the baseline gate.

Verified PR #181 OPEN/Draft head:
`0de78aa8fe7f50325a525506f8aee33b295aca80`,
tree `d8ddcaa33d755f39d077382cb3f17c54a2943eac`.
All five screenshot hashes in the owner's `experience-review/fixed-0de78aa/receipt.json`
match files (input, clarification, understanding, correction pending, confirmation).
This fixed-source fixture stops before creation; it is not new database/readback
or model-quality evidence. Retain the corrected “等待补充信息” label.

Baseline discrepancy: current branch main `b5e013f` contains merged #179 commits
`89a8dad` and `8fd78e8` (including Evidence keyboard-focus behavior), absent from
the handed-off candidate. Common ancestor is
`e51334aa9780291b3d077a1edb698dca630a6b3f`. Replacing current code with #181 would
lose already-delivered behavior; combining them would constitute candidate
integration, which Human explicitly prohibited doing autonomously.
Thus UI ownership is received but implementation baseline remains UNSELECTED.
Required next input is an explicitly accepted combined baseline, or Human's
explicit instruction for a stacked candidate and later integration ownership.
No merge, cherry-pick, candidate copy, branch reset or shared UI edit performed.


### Development baseline authorized — 2026-09-17

Human explicitly authorized the fixed `0de78aa8fe7f50325a525506f8aee33b295aca80`
source / `d8ddcaa33d755f39d077382cb3f17c54a2943eac` tree for this independent
worktree. This supersedes the preceding baseline pause. Existing branch and
preparation edits retained; no upstream worktree changes or PR integration.
Actual owner activity checked: quality preparation, existing fixture services,
no shared UI build/test writer observed. Explicit file handoff remains effective.
This task is sole writer for its own UI increment. Parent #181 is still Draft/open;
its changes are dependencies, not this task's diff. #179 integration is not part
of this task; do not claim the candidate includes current-main-only commits.

Implement the six agreed presentation changes; keep state transitions and API
contracts untouched. Capture before/after using the same isolated UI/API fixture
case at 1440x1050 and 390x844, with no real provider or database access.


### Visual candidate delivery evidence

Implemented only the bounded presentation changes: explicit clarification-answer
focus entry; secondary fallback actions; readable fact/source typography; user
corrections before the current confirmation; no-wrap unavailable search label;
state-aware heading; collapsed read-complete authorization summary and technical
facts. Creation/restoration cards remain mounted. No API handlers, models,
contracts, idempotency payloads, persistent domains or authorization flows changed.

Owned UI changes: DraftAssistanceCard.tsx, ProblemConversation.tsx,
ProblemWorkspacePage.tsx, ProblemTaskSummary.tsx, product-experience.css.
The existing interaction config accepts an isolated port (original default retained);
the existing interaction suite includes three additional visual/focus/order journeys.
No 321 tree, runtime or database was modified. Existing services were not stopped.

[Before/after viewer](../../evidence/s5/v0.2/s5-v023-impl-322/index.html) contains
28 unedited screenshots (1440x1050 / 390x844): input, clarification, confirmation,
created, independently authorized fixture readback and refresh, plus mobile action
positions. [Capture manifest](../../evidence/s5/v0.2/s5-v023-impl-322/capture-manifest.json)
binds baseline source/tree, changed-file hashes, built assets and screenshot hashes.
The same synthetic DTO scenario runs before and after. This is UI regression
proof, not a fresh true-backend/PG or model-quality claim.

Validation actually executed:
- `make check`: 1853 passed, 200 pre-existing environment-dependent skips, one warning.
- Frontend `npm run lint`: PASS; production `npm run build` via both Playwright configs: PASS (existing chunk-size warning).
- Existing understanding suite plus three visual/focus/order journeys: 33 passed, retries 0.
- Existing W2A/W3 suites: 19 passed, unchanged assertions, including exact scroll position, focus/modal containment, independent READ and refresh restoration.
- Fixed-source baseline screenshot journeys: 2 passed.
- `git diff --check`: PASS.

Retained failures: occupied initial port (no service touched); malformed screenshot
fixture link response (corrected fixture, recaptured baseline); real visual
regression of scroll 365→348 after approval (read-complete geometry restored;
original scroll assertion then passes). Logs remain in the evidence checks folder.
No arbitrary sleeps, weakened assertions or additional test skips were introduced.

Delivery uses this single branch and one Draft PR based on the #181 branch so the
review diff excludes parent work. Parent source remains fixed above; parent
12/12 CI is not claimed as this candidate's checks. Normal hooks/commit/non-force
push and candidate CI are tracked in that PR with exact source/tree. Default CI
only auto-runs for main-target PRs; dispatch its existing workflow against this
branch rather than weakening filters or merging parent candidates.

Remaining close conditions: Human visual review; applicable candidate CI terminal
results; separately authorized parent integration/rebase and exact-main verification
before merge. This candidate does not include main-only #179 changes, does not
integrate #181, and does not close either Session. No Ready/merge/deploy authority.
Nonblocking follow-up: broader shell/navigation and real model quality remain
outside this visual increment, under their existing owners and plans.

Normal commit hooks passed for implementation source `4e9ec6895e9a315cdae3154c0f28e9c69b303064` / tree `bbcc960cae0958a6f7755a3b84a6738f25e1181a`. The evidence-text successor trims log trailing whitespace only (original logs retained in the task temporary directory); UI and screenshot hashes remain identical. Final candidate identity and CI links are pinned in the single Draft PR.
