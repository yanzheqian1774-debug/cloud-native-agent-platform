# S5-ARCH-011 — Product Intent, Dynamic Work, Role, and Knowledge Consumption Boundary v1

## 1. Status and decision

| Field | Value |
| --- | --- |
| Session | `S5-ARCH-011` |
| Decision status | `APPROVED_WITH_CONSTRAINTS` by the Human Architecture Decision; repository candidate pending review and merge gates |
| Implementation status | `NOT_STARTED` |
| Baseline | `a0d82be4387f5706129ee6676ad5965b42a3efdb` |
| Release boundary | bounded internal v0.2 Digital Employee Technical Preview architecture |
| Contract status | internal candidate; `NOT_FROZEN`; no public API or CRD schema |
| Selected domain | supplier-quality exception analysis |

This decision defines one bounded path:

```text
business question
→ IntentRevision
→ TaskRequirements
→ WorkflowCandidate
→ deterministic validation
→ Human approval bound to exact digest
→ CanonicalWorkflowRevision
→ Data/Knowledge/Skill/Capability/Role matching
→ RuntimeRequirement
→ bounded Native placement
→ authorized retrieval/invocation
→ Native execution and Evidence
→ Product answer and citations
→ ProductSemanticCorrection
→ immutable SuccessorRevision
```

The decision is normative architecture, not implementation evidence. Future
implementation MUST pass separately authorized implementation and release gates.

## 2. Problem and scope

The current platform can execute bounded Native work and project shared Product and
Technical views, but it has no approved v0.2 authority model for turning a previously
unprepared business question into an approved, dynamically composed Workflow with
governed descriptor, role, Runtime, and Knowledge consumption.

v0.2 MUST prove that path for one business domain without creating a general planner,
Knowledge Plane, Agent Factory, Runtime Manager, or production RAG system. The
architecture therefore adds internal, versioned contract boundaries while preserving
Kubernetes execution-state authority, the existing Canonical Graph semantics, and the
S5-ARCH-010/S5-IMPL-014 Evidence and shared-read-model boundary.

### 2.1 Normative classifications

- **Normative architecture**: identities, authorities, state machines, validation,
  authorization order, matching, failure behavior, and projection invariants below.
- **Future implementation obligations**: code, storage, internal DTOs, policies,
  tests, and UI journeys required to realize this decision.
- **Demo-only assets**: curated descriptors, supplier data, and Knowledge documents.
- **Synthetic historical inputs**: visibly labelled sanitized prior cases and outcomes.
- **Live execution**: current planning, matching, authorization, retrieval, execution,
  Evidence, citations, correction, and Outcome.
- **Unsupported claims**: any capability listed as v0.3, rejected, or a non-goal.

### 2.2 Checkpoint B durable-architecture consistency review

The independent review found no unresolved contradiction. Apparent overlaps resolve as
follows:

| Governing architecture or implementation | Apparent contradiction | Resolution |
| --- | --- | --- |
| Current Workflow/Task CRDs and controllers | New planning contracts could become a second current Workflow authority | candidates are internal proposal/approval records; only the approved canonical revision maps to and invokes the existing bounded execution path; current source remains authority for implemented lifecycle behavior |
| S5-ARCH-005/007 Definition and Instance separation | Role matching or preview could create or replace Instance identity | matching uses exact existing `PUBLISHED/MATCHABLE` Definition versions; preview creates no Definition or Instance; Platform-minted Instance identity remains separate |
| S5-ARCH-009 Canonical Graph and sibling views | new Intent, planning, or Knowledge identities could define new Graph semantics or view-local relationships | existing Graph node/relation vocabulary, directions, cardinality, and relationship authority remain unchanged; unsupported mappings fail or become authorized limitations; views consume one upstream graph |
| S5-ARCH-009 synthetic Knowledge boundary | live bounded retrieval could retroactively convert synthetic fixtures into production Knowledge | synthetic fixtures remain labelled; S5-ARCH-011 authorizes only a future bounded live read-only Pack and explicitly makes no production RAG, persistence, governance, or Enterprise Knowledge claim |
| S5-ARCH-010/S5-IMPL-014 Evidence and shared snapshot | retrieval Evidence or citation assembly could replace execution Evidence or shared-view authority | retrieval Evidence is a future append-only Evidence kind; Kubernetes remains current state authority, Graph remains relationship authority, and the one backend assembler remains sibling snapshot authority |
| Accepted Runtime/Provider decisions and known drift | placement contracts could introduce RuntimeClass, a Runtime Manager, or external routing | placement is limited to one already declared Native target and existing Native path; no RuntimeClass refactor, provisioning, lifecycle management, OpenClaw/Hermes selection, or certification |
| Capability authorization | descriptor selection could grant invocation authority | authorization precedes scoring and invocation; a descriptor or model cannot grant permission; live invocation retains separate authorization Evidence |
| Human approval and Product correction | Product correction could mutate an approved plan or become policy | Product emits a semantic correction request only; deterministic validation and a new exact-digest Human approval create an immutable successor; tenant policy is unchanged |
| Golden Demo architecture | supplier-quality example could claim Demo completion or replace the approved scenario gate | it is a bounded architecture example and future package only; no Demo asset, acceptance, readiness, or Release state changes |
| Public API and `agentos.io/v1alpha1` Agent/Task/Workflow CRDs | internal contracts could become new public schemas | all S5-ARCH-011 contracts are internal, versioned candidates; public API/CRD/schema changes require a separate Human G2 gate |

Known ADR-0003 Operator/Workflow and ADR-0004 Runtime abstraction drift is neither
resolved nor expanded by this decision. Current source defines implemented behavior;
accepted ADRs retain architecture authority until a separately approved decision.

## 3. Product experience principle

Business users primarily submit a question and receive an answer. The work process is
visible in business language; technical identifiers, matching detail, policy decisions,
and execution traces use progressive disclosure. Internal governance vocabulary MUST
NOT become mandatory business-user vocabulary.

Product View MAY submit a business-semantic correction. It MUST NOT directly mutate a
Workflow, execution, Canonical Graph, or Evidence. An accepted correction compiles into
a deterministic validated patch, produces a new candidate digest, receives a new exact
Human approval, and creates an immutable successor revision. Technical View observes
the same authoritative identities and state through the shared backend projection; it
is not a second plan or execution authority.

## 4. Authority matrix

Each row names exactly one authority. A consumer MUST fail closed rather than use the
prohibited competing authority or reconstruct a missing authoritative value.

| Concern | Owner and source | Identity/version/mutability | Decision scope and consumers | Fail closed; forbidden competing authority |
| --- | --- | --- | --- | --- |
| Intent revision | Intent authority; normalized accepted question and constraints | `intent_revision_id`, schema/revision/digest; immutable once generated | planning and projections | reject missing/invalid revision; model, Product View, and frontend cannot declare approval |
| Task requirements | canonical planning validator; validated Intent-derived set | `task_requirement_id`; versioned and immutable per candidate | matching and Workflow validation | unknown requirement is `UNSUPPORTED`; model output is not authority |
| Workflow candidate | candidate authority; parsed model proposal plus deterministic normalization | `workflow_candidate_id`, revision/digest; immutable proposal | validation and approval | never executable; frontend/model cannot publish it |
| Validated candidate digest | deterministic canonicalizer | algorithm/schema version plus digest; immutable | approval binding and replay | digest mismatch rejects; timestamps, display text, and mutable runtime metadata cannot affect it |
| Human approval | Human approval decision record | `approval_id`, candidate digest, decision and timestamp; append-only | publication eligibility | absent, expired, rejected, or mismatched approval blocks publication; planner cannot approve |
| Canonical Workflow revision | approved Workflow revision authority | `canonical_workflow_revision_id`, version and digest; immutable | matching, placement, execution | only exact approved revision is consumable; Product/Technical views cannot reconstruct it |
| Data Descriptor | curated Data catalog | stable ID/version/digest; immutable version | Data matching | unauthorized/unavailable version excluded before scoring; descriptor cannot grant permission |
| Knowledge Descriptor | curated Knowledge Pack catalog | stable ID/version/content digest; immutable version | Knowledge matching and retrieval | denied source excluded before retrieval; retrieval cannot publish Knowledge |
| Skill Descriptor | curated Skill catalog | stable ID/version/digest; immutable version | Skill matching | unsupported or unauthorized version excluded; model suggestion cannot authorize |
| Capability Descriptor | curated Capability catalog | stable ID/version/digest; immutable version | Capability matching/invocation | authorization and compatibility required; frontend cannot substitute |
| Digital Employee Definition | existing versioned Definition authority | Definition ID/version/status/digest; immutable published version | role matching | only `PUBLISHED/MATCHABLE`; publication does not approve high-risk execution |
| RoleGap | deterministic role-match decision | decision ID/version/reasons; append-only | Product/Technical presentation and execution blocking | grants no support; no invented fallback Definition |
| RoleCandidatePreview | preview authority | preview ID/version; `DRAFT`, immutable revision | Product preview only | non-executable/non-matchable; no credentials, permissions, publication, Instance, or access |
| Runtime Requirement | canonical planning validator over approved tasks | requirement ID/version/digest; immutable per Workflow revision | Native placement | missing/unsupported requirement blocks; frontend cannot weaken it |
| Runtime placement decision | bounded Native placement evaluator | decision ID, target version, reason codes; append-only | existing Native execution bridge | unavailable Native target blocks; no OpenClaw/Hermes or fabricated availability |
| Platform Execution Identity | existing identity spine | execution ID/UID binding; immutable | all live Evidence and views | no view-local or provider-local execution identity |
| Kubernetes execution state | Kubernetes API/control plane | resource UID/resourceVersion/status; mutable under controller rules | current execution state | internal repositories and views cannot replace it |
| Canonical Graph | existing canonical graph assembler/authority | canonical node/relation identities; versioned snapshot | shared Product/Technical relationships | this decision adds no Graph semantics; frontend cannot mint canonical IDs or relations |
| Execution Evidence | S5-ARCH-010 append-only Evidence authority | evidence ID/type/sequence/execution binding; append-only | Graph and shared views | Evidence records what happened; it is not Workflow, policy, Knowledge, or Graph authority |
| Knowledge authorization | trusted policy decision authority | decision ID/policy version/result/reason; append-only | filtering before source/chunk retrieval | parent execution allow is not inherited; retrieval or descriptor cannot self-authorize |
| Knowledge retrieval result | bounded deterministic retrieval service | result ID/query digest/policy and source versions; immutable result | Evidence and authorized answer context | failure remains failure; model/frontend cannot fabricate results |
| Authorized citation projection | deterministic backend citation assembler | citation ID/reference and Evidence IDs; immutable per snapshot | sibling Product/Technical projections | no frontend-minted, inferred, reconstructed, or synthetic live citation |
| Product projection | shared backend assembler plus Product policy | snapshot ID/version/source identities; immutable response | business experience | cannot mutate or become plan/Graph/Evidence authority |
| Technical projection | same shared backend assembler plus Technical policy | same snapshot spine/source identities; immutable response | technical inspection | cannot become execution/Graph authority or expose unauthorized detail |

## 5. Common contract envelope and digest rules

Every contract in section 6 MUST carry this envelope unless a row narrows it:

- stable ID, `schema_version`, revision or version, and `canonical_digest`;
- lifecycle/status and explicit support state;
- `tenant_id` and `security_domain` from trusted context, never model output;
- authorization decision/reference when consumption is protected;
- provenance kind and source-authority identity;
- `created_at` and, for decisions, `decided_at` in UTC;
- deterministic ordered collections or an explicit stable sort key;
- explicit validation result, reason codes, and unsupported/failure state;
- Platform Execution Identity link only when live execution exists;
- Evidence links only to append-only records actually emitted;
- Product/Technical projection links that preserve authoritative identities.

Canonical digest inputs are the normalized semantic identity, schema version,
revision/version, requirements, dependencies, constraints, bindings, tenant/security
domain, and source version/digests named by each contract. Digest encoding MUST use a
documented canonical serialization, Unicode normalization, explicit null handling, and
stable ordering.

Excluded from digests are display-only localized labels, presentation ordering,
transport envelopes, mutable repository/database metadata, storage locations, cache
metadata, observation time, tracing IDs, generated timestamps not semantically required,
and secrets. Exclusion cannot hide a field that changes authorization, compatibility,
execution, retrieval, or business semantics.

Decided and published revisions are immutable. Mutable draft annotations and display
preferences MUST be held outside the canonical semantic payload. Changes to semantic
content always create a new revision and digest.

## 6. Normative contract model

The following table supplements the common envelope. `Failure` names the minimum
fail-closed outcome; it never authorizes fallback.

| Contract | Identity and digest-specific inputs | Lifecycle and authority | Validation, failure, Evidence, and projection |
| --- | --- | --- | --- |
| `IntentRevision` | Intent ID/revision; normalized question, business constraints, locale-independent semantics | planning states in section 7; Intent authority | invalid/unsupported intent stops planning; proposal/validation/approval provenance projected |
| `TaskRequirement` | requirement ID; intent revision, kind, required/optional, success criterion, constraint values | immutable within candidate; planning validator | unknown kind is `UNSUPPORTED`; matching decisions become Evidence only after execution context exists |
| `WorkflowCandidate` | candidate ID/revision; ordered Tasks, requirements, dependencies, provenance | proposal states only; candidate authority | parse/schema/cycle/digest failure is terminal; never projected as approved/executable |
| `CanonicalWorkflowRevision` | Workflow ID/revision; validated candidate digest, approval ID, canonical Tasks and dependencies | `APPROVED`, `PUBLISHED_FOR_EXECUTION`, `SUPERSEDED`; canonical authority | approval mismatch blocks; execution/Evidence bind exact revision; both views show same ID |
| `DataRequirement` | requirement ID; dataset semantics, version/freshness/classification constraints | immutable per Task requirement | gap/deny blocks required Task; decision is projection-safe only as authorized |
| `DataDescriptor` | descriptor ID/version; schema, owner, classification, support state, source digest | curated catalog authority | invalid/unauthorized descriptor excluded before scoring; descriptor is not permission |
| `DataBinding` | binding ID; requirement and descriptor IDs/versions, decision and score | append-only match decision | `DATA_GAP`, `DENIED`, or `UNSUPPORTED`; live reads emit separate Evidence |
| `KnowledgeRequirement` | requirement ID; topic/document type, freshness, classification and citation requirements | immutable per Task requirement | required failure blocks cited answer; optional omission remains explicit |
| `KnowledgeDescriptor` | descriptor ID/version plus Knowledge identity in section 11 | curated Pack authority | non-available or unauthorized versions excluded; never grants access |
| `KnowledgeBinding` | binding ID; requirement, descriptor version, authorization decision and match reasons | append-only match decision | gap/deny/status explicit; no content retrieval is implied by binding |
| `AuthorizedKnowledgeReference` | reference ID; authorization decision, document/version/section/chunk/digest and citation ID | retrieval service after trusted allow | no object on nondisclosable deny; permitted references project identically to both views |
| `KnowledgeRetrievalEvidence` | Evidence ID; query digest, policy version, authorization IDs, ordered reference IDs, statuses | append-only Evidence authority | raw prompts/secrets/provider bodies excluded; failure cannot be rewritten as success |
| `SkillRequirement` | requirement ID; skill semantics, version/support constraints | immutable per Task requirement | `SKILL_GAP`, deny, unsupported, or error blocks when required |
| `SkillDescriptor` | descriptor ID/version; interface/digest/support/classification | curated catalog authority | unauthorized/unsupported excluded before scoring |
| `SkillBinding` | binding ID; requirement/descriptor versions, reasons and precedence | append-only match decision | no invocation or permission implied; projection uses exact identities |
| `CapabilityRequirement` | requirement ID; operation, input/output, risk and support constraints | immutable per Task requirement | gap/deny/unsupported blocks required invocation |
| `CapabilityDescriptor` | descriptor ID/version; operation contract/digest/support/risk | curated catalog authority | descriptor cannot authorize itself; implementation/transport remains replaceable |
| `CapabilityBinding` | binding ID; requirement/descriptor versions, authorization/compatibility decisions | append-only match decision | invocation requires separate live authorization and Evidence |
| `RoleRequirement` | requirement ID; duties and required Data/Knowledge/Skill/Capability/Runtime coverage | immutable per Task | absence yields `ROLE_GAP`; requirement cannot invent Definition |
| `RoleMatchDecision` | decision ID; requirement and published Definition versions, coverage, reasons | deterministic matcher authority | matched/partial/gap explicit; both views preserve decision ID |
| `RoleGap` | gap ID; missing requirement IDs and stable reason codes | terminal factual match result | blocks required assignment; grants no support or access |
| `RoleCandidatePreview` | preview ID/version; derived role suggestion and provenance | `DRAFT` only in v0.2 | non-executable/non-matchable; Product preview label required; no runtime Evidence |
| `RuntimeRequirement` | requirement ID; approved Task needs, Native support and resource constraints | immutable per canonical revision | unsupported requirement yields `RUNTIME_UNAVAILABLE`/`UNSUPPORTED` |
| `RuntimePlacementRequest` | request ID; execution ID, canonical revision, requirement and declared targets | append-only request to bounded evaluator | only declared Native target eligible; no provisioning semantics |
| `RuntimePlacementDecision` | decision ID; request, exact target/version, availability, limitations, reasons | append-only bounded placement authority | unavailable blocks execution; both views preserve decision and target identity |
| `ProductSemanticCorrection` | correction ID/revision; source Workflow revision, normalized business patch, actor/decision | draft/validated/accepted/rejected; correction authority | cannot mutate source; accepted correction produces a new candidate and approval cycle |
| `SuccessorRevision` | successor ID; predecessor ID/digest, accepted correction ID, new candidate/approval/digest | immutable canonical revision | predecessor remains queryable; executions stay bound to their exact revision |

### 6.1 Existing-contract reuse and mapping

These names do not authorize duplicate competing domain objects. Future implementation
MUST reuse the existing `agent_core.representation.v0_2` identity, Definition, Instance,
Task, Workflow, Capability, Runtime Binding, Platform Execution Identity, Outcome, and
Evidence values where their accepted semantics match. The new contracts are either:

- proposal/approval records that reference the existing Workflow/Task identities;
- typed requirement or binding records that reference existing Definition, Capability,
  Runtime, and execution identities; or
- Knowledge-specific internal values mapped into the existing append-only Evidence and
  shared projection seams.

If implementation discovers that an existing similarly named type has incompatible
semantics, it MUST stop at its implementation Architecture Gate. It MUST NOT alias,
shadow, fork, or silently replace the existing contract. Public Agent/Task/Workflow CRDs
remain unchanged and are not serialization targets for these candidate envelopes.

## 7. Intent and planning state machine

```text
DRAFT → GENERATED → VALIDATING → VALID → PENDING_APPROVAL
                                      ├→ APPROVED
                                      │    → PUBLISHED_FOR_EXECUTION → SUPERSEDED
                                      └→ REJECTED

Any permitted pre-publication state → INVALID | UNSUPPORTED | EXPIRED | CANCELLED
```

- `DRAFT`: trusted question and explicit user constraints captured.
- `GENERATED`: model proposal exists; it has no execution authority.
- `VALIDATING`: deterministic parsing, schema validation, normalization, requirement
  validation, dependency resolution, and cycle detection are running.
- `VALID`: one canonical digest has been calculated over supported content.
- `PENDING_APPROVAL`: exact digest awaits a Human decision.
- `APPROVED`: approval record matches the exact digest and remains valid.
- `PUBLISHED_FOR_EXECUTION`: canonical immutable revision is eligible for matching and
  execution. Publication itself does not grant protected access or high-risk approval.
- `SUPERSEDED`: a successor is current; historical identity and executions remain valid.
- `INVALID`: syntax, schema, dependency, invariant, or canonicalization failure.
- `UNSUPPORTED`: a validly expressed requirement has no supported v0.2 semantics.
- `REJECTED`, `EXPIRED`, `CANCELLED`: terminal decision/time/user outcomes.

Changed content or digest requires a new candidate and approval. No unapproved
candidate reaches Data, Knowledge, Skill, Capability, Runtime, Provider, or execution.
Model timeout, malformed output, or failure becomes bounded `UNAVAILABLE`/`ERROR`; it
cannot fabricate a successful plan.

## 8. Workflow and Task semantics

Each Task has a stable `task_id` within a Workflow identity and an immutable revision
within a candidate. Each requirement has its own stable ID; requirements are not
identified by display text. A dependency is a directed `predecessor_task_id →
successor_task_id` relation with an optional explicit condition from a supported closed
vocabulary.

Canonical ordering uses topological level, then explicit canonical ordinal, then stable
Task ID. Kahn-style deterministic traversal or an equivalent algorithm MUST reject any
cycle and report stable involved Task IDs. It MUST NOT drop an edge to make a plan valid.

Tasks declare `REQUIRED` or `OPTIONAL`, but every missing requirement remains explicit.
An optional Task may be omitted only under a canonical policy and emits the applicable
skip/limitation reason. Required Tasks define measurable success criteria and failure
propagation. Each Task separately lists required Data, Knowledge, Skill, Capability,
Role, and Runtime constraints.

Task requirements map onto existing Canonical Graph node and relation identities using
the approved Workflow revision, match decisions, bindings, authorization decisions, and
Evidence IDs. This decision introduces no new Graph node kind, relation kind, direction,
cardinality, aggregation, or authority. An unsupported mapping fails validation or is
represented as an authorized limitation; the frontend cannot invent the mapping.

A candidate becomes canonical only after deterministic validation and exact-digest Human
approval. Successors retain predecessor digest, correction, validation, approval, and
publication provenance. Prior approved, rejected, and executed revisions remain immutable.

## 9. Deterministic authorization-first matching

Matching MUST execute in this order:

1. resolve trusted tenant and security domain;
2. filter descriptors using independent authorization decisions;
3. validate exact descriptor versions and support states;
4. evaluate complete requirement compatibility;
5. calculate documented deterministic precedence or score;
6. resolve equal results by stable descriptor identity and version;
7. return a selected binding or explicit gap;
8. record the decision and stable reason codes.

The result vocabulary is `MATCHED`, `PARTIAL`, `ROLE_GAP`, `DATA_GAP`,
`KNOWLEDGE_GAP`, `SKILL_GAP`, `CAPABILITY_GAP`, `RUNTIME_UNAVAILABLE`, `DENIED`,
`UNSUPPORTED`, `AMBIGUOUS`, and `ERROR`.

Required coverage cannot be silently partial. `AMBIGUOUS` is used when policy forbids
the documented stable tie from selecting safely; it is not random selection. Rejected
candidates and reasons are disclosed only when authorization permits. Unauthorized
descriptors never enter scoring, counts, model context, or results. A model may suggest
candidates but cannot authorize or override compatibility. The frontend cannot match,
substitute, or fall back to fixtures.

## 10. Role lifecycle boundary

`RoleGap` is an append-only deterministic fact identifying missing requirement IDs and
stable reasons. It creates no Agent, Definition, Instance, permission, credential, or
support claim.

`RoleCandidatePreview` is a versioned `DRAFT` presentation only. It is non-executable,
non-matchable, unpublished, and receives no credentials, permissions, Runtime Instance,
Capability access, or production effect.

Only existing Digital Employee Definition revisions whose authoritative status is
`PUBLISHED/MATCHABLE` participate in v0.2. Publication does not approve high-risk
execution. Definition and Agent Instance remain separate. A preview cannot create an
Agent Instance.

Generated-role validation, approval/publication, catalog participation, Agent Factory,
and managed Agent Instance lifecycle are v0.3.

## 11. Runtime boundary

v0.2 defines `RuntimeRequirement`, `RuntimePlacementRequest`, and
`RuntimePlacementDecision` only to select one already declared, available Native target.
Selection is deterministic, records availability and limitations, binds Platform
Execution Identity, and bridges to the existing Native execution path.

It does not provision, distribute, pool, autoscale, heal, fail over, migrate, recover,
route across runtimes, optimize capacity/cost, roll upgrades, select OpenClaw/Hermes,
certify support, or claim multi-node availability. Missing support blocks execution
honestly.

## 12. Bounded Knowledge consumption

v0.2 consumes one curated, deterministic, read-only Knowledge Pack. Five separate
authorities are preserved:

1. document/version/content authority in the curated Pack;
2. trusted authorization decision authority;
3. bounded retrieval result authority;
4. append-only retrieval Evidence authority;
5. deterministic backend citation projection authority.

Authorization MUST occur before source or chunk retrieval. Denied Knowledge cannot
enter the candidate set, ranking, counts, summary, citation, model context, or either
projection. A nondisclosable `DENIED` outcome exposes no document identity, title,
section, chunk, count, digest, rank, metadata, or existence. Its policy decision may be
recorded using a non-source-revealing decision ID and reason.

Parent execution `ALLOW` is never inherited by a Knowledge reference. Retrieval cannot
publish Knowledge or grant permission. Raw prompts, secrets, credentials, tokens,
provider bodies, unrestricted diagnostics, and sensitive source content MUST NOT be
persisted as generic retrieval Evidence.

### 12.1 Knowledge identity and digest

Every source has stable `document_id`, `document_version`, `document_type`, owner,
classification, tenant, security domain, effective time, expiry time, freshness, and
status. Every retrievable unit has stable `section_id` and `chunk_id`. Normalized
approved content, structural identities, document version/type, owner/classification,
and tenant/security domain form the content digest inputs.

Repository path, database row ID, cache key, ingestion timestamp, retrieval rank,
runtime host, locale-specific display label, and transport metadata do not change source
identity. A semantic content update creates a new version and digest. Historical
Evidence remains bound to the exact source version used.

Each retrieval records retrieval-policy version, ordered authorized references,
independent authorization decision IDs, `citation_id`, and retrieval Evidence ID.
Identical authorized query inputs, Knowledge versions, and policy versions produce the
same order; ties use document, section, and chunk stable identities. Locale may change
presentation but not authoritative retrieval or citation identity.

### 12.2 Knowledge status and failure

| Status | Required behavior |
| --- | --- |
| `AVAILABLE` | eligible after authorization and policy validation |
| `STALE` | remains explicitly stale; used only if the approved requirement/policy allows it |
| `EXPIRED` | excluded and reported without becoming `NOT_FOUND` |
| `DENIED` | excluded before retrieval with zero existence disclosure |
| `NOT_FOUND` | authorized search found no eligible match |
| `UNAVAILABLE` | known service/source cannot currently be accessed |
| `ERROR` | bounded unexpected retrieval or validation failure |

Retrieval failure cannot become a successful cited answer. Required Knowledge failure
blocks the dependent answer/Task. Optional omission is explicit and cannot produce a
synthetic citation.

### 12.3 Product/Technical equality

Product and Technical sibling projections preserve the same Knowledge reference ID,
document version, section/chunk IDs, content digest, authorization decision ID,
retrieval Evidence ID, citation ID, and provenance. Presentation and authorized detail
may differ. Neither backend view policy nor frontend may mint, infer, reconstruct, or
substitute a reference.

### 12.4 MCP boundary

MCP is transport/exposure, not Knowledge authority. A future MCP Resource binding MUST
preserve Knowledge identity, version, digest, tenant/security domain, authorization,
provenance, and citation identity. General MCP Knowledge access is not implemented in
v0.2.

## 13. Live and synthetic provenance

| Provenance | Meaning | Authority limit |
| --- | --- | --- |
| `DEMO_CONFIGURATION` | deterministic Data/Knowledge/Skill/Capability/Role descriptors and source assets | configuration only; not live Evidence |
| `SYNTHETIC_HISTORY` | visibly labelled sanitized prior tasks, interventions, and outcomes | not production history or policy authority |
| `LIVE_EXECUTION` | current Intent, planning, matching, authorization, retrieval, execution, Evidence, citations, correction, and Outcome | generated by the running bounded path |

Source documents may be deterministic Demo assets, but current authorization,
retrieval, ranking, Evidence, and citation projection execute live. Live mode MUST NOT
substitute fixture results or synthetic citations.

## 14. Supplier-quality exception analysis example

The bounded example asks:

> Which supplier quality issues are most likely to miss closure this week, why,
> and what should we do first?

Future Demo configuration may include synthetic supplier-quality business data,
severity rules, closure-time policy, escalation rules, an 8D procedure, sanitized
historical cases, curated descriptor catalogs, existing published Digital Employees,
and one Native analysis operation.

Live behavior comprises Intent capture, dynamic Tasks, canonical approval, matching,
Native placement, authorized Knowledge retrieval, execution Evidence, citations, a
business answer, Product correction, immutable successor, Outcome, and Technical
inspection. The answer is traceable to both Data Evidence and authorized Knowledge
citations. This decision does not create the Demo Scenario Pack or Knowledge Pack.

## 15. Threat and misuse model

| Attack or failure | Affected authority | Fail-closed behavior | Required future test | Residual limitation |
| --- | --- | --- | --- | --- |
| Model output executes directly | Workflow authority | candidate is non-executable; reject without exact approval | attempt every invocation from proposal states | malicious model content still requires parser hardening |
| Candidate changes after approval | digest/approval | digest mismatch blocks publication/execution | mutate every semantic field after approval | canonicalizer defects remain implementation risk |
| Dependency-cycle bypass | validator | reject whole candidate with stable involved IDs | self-loop and multi-node cycles/order permutations | extremely large graphs need bounded resource policy |
| Unauthorized descriptor enters matching | authorization/matcher | filter before scoring and counts | denied high-score candidate never observed by scorer | policy correctness remains external dependency |
| Product View becomes plan authority | Workflow authority | accept only correction command; require compile/validate/approve | direct mutation and forged revision tests | usability may tempt hidden shortcuts |
| Preview becomes executable | Definition/Instance authority | reject preview IDs at match/placement/invocation | preview ID across every execution boundary | future v0.3 migration needs explicit gate |
| Missing role silently falls back | role matcher | return `ROLE_GAP`; zero assignment | empty and partial catalogs | disclosure-safe reasons may be less descriptive |
| Automatic permission/credential grant | policy authority | descriptors/previews cannot grant; deny absent decision | malicious descriptor requests access | credential systems remain outside this decision |
| Unsupported Runtime appears available | placement authority | exact declared Native support required | unsupported features and absent target | single-node availability remains limited |
| OpenClaw/Hermes fallback | placement authority | target-kind allowlist rejects | Native unavailable with external targets present | no heterogeneous fallback in v0.2 |
| Denied Knowledge influences ranking | authorization/retrieval | denied sources removed before candidate creation | sentinel denied document with uniquely high relevance | side-channel resistance needs implementation review |
| Authorization occurs after retrieval | authorization/retrieval | retrieval API requires allow decision reference | missing/late/foreign decision tests | trusted policy service availability can block answers |
| Denied source existence leaks | authorization/projection | generic nondisclosing deny; zero source metadata/counts | compare absent versus denied responses | timing side channels need bounded operational controls |
| Frontend mints citation | citation authority | accept backend citation IDs only | injected/reconstructed citation tests | copied text outside platform cannot be controlled |
| Synthetic citation shown as live | provenance/citation | provenance mismatch rejects live response | fixture fallback and mixed-provenance tests | Demo labelling still needs UX verification |
| Cross-tenant Knowledge leak | tenant/auth authority | trusted tenant equality required at catalog, policy, retrieval, projection | foreign tenant at each boundary | cross-tenant Knowledge is rejected for v0.2 |
| Stale Knowledge shown as current | Knowledge status | preserve status; policy blocks or visibly qualifies | stale/expired boundary-time tests | clock and freshness policy quality remain dependencies |
| Raw prompt/secret persisted | Evidence authority | schema allowlist/redaction rejects sensitive fields | secret canaries in prompt/provider bodies | free text needs ongoing leakage testing |
| Generated text writes Knowledge | Knowledge authority | read-only interface; no publication capability | attempt create/update/delete operations | ingestion/publication deferred to v0.3 |
| Correction becomes tenant policy | correction/policy authority | correction scopes only a successor candidate | policy-shaped correction test | repeated feedback is not learning in v0.2 |
| Optimization candidate affects production | execution authority | preview/candidate has zero production influence | inject optimization candidate into matcher/runtime | optimization lifecycle remains v0.3 |
| Approval replay uses a changed normalized digest | approval/canonical Workflow authority | approval lookup requires exact digest, canonicalizer version, tenant/security domain, and candidate identity; mismatch rejects | replay old approval across semantic, normalization-version, tenant, and candidate changes | canonicalization implementation defects remain a review focus |
| Malicious or invalid model output exploits parser limits | planning validator | bounded parser/schema/resource limits reject before canonicalization or approval | adversarial structure, oversized output, unknown fields, injection text, and parser differential tests | model output remains untrusted even after syntactic parsing |
| Descriptor enumeration through rejection reasons | catalog authorization/matcher | unauthorized descriptors are absent before scoring and use nondisclosing reasons/counts | compare absent and denied descriptors across result body, ordering, and counts | timing and aggregate side channels require operational measurement |
| Knowledge existence inferred from result count or timing | Knowledge authorization/retrieval | denied sources contribute zero candidates/counts and responses use bounded nondisclosing behavior | absent-versus-denied count, rank, cache, error, and timing comparisons | strict timing equivalence is not claimed in v0.2 |
| Citation remains stale after document version changes | Knowledge/citation authority | citation stays bound to historical exact version/digest and current answers rerun matching/retrieval | update document while replaying old Evidence and creating a new answer | historical citations may intentionally reference superseded content with visible status |
| UI state makes a candidate or preview matchable | candidate/Definition authority | backend accepts only authoritative published lifecycle state, never UI flags | tamper with Product/Technical UI state, payload labels, and cached status | compromised backend authority is outside frontend controls |
| Product View hides a Runtime limitation | placement/shared projection authority | shared snapshot retains limitation identity; Product may simplify wording but cannot omit a decision-blocking limitation | compare Product/Technical limitation IDs and blocked-execution state | progressive disclosure may reduce Product detail, never the blocking fact |
| Synthetic history contaminates live optimization or policy | provenance/execution/policy authority | v0.2 has no production optimization/learning path; provenance filter excludes synthetic history from live authority | inject synthetic outcomes into matching, policy, correction, and proposed optimization inputs | evaluation may use labelled synthetic history but cannot influence live execution |
| Future MCP wrapper becomes Knowledge authority | Knowledge/MCP boundary | wrapper must preserve authoritative reference/version/digest/auth/citation and cannot publish, authorize, rank, or mint identity | malicious wrapper identity, authorization, content, rank, and citation substitution tests | future MCP Resource support requires its own architecture and implementation gates |

## 16. Validation and acceptance requirements

Future implementation acceptance MUST include:

1. stable identity, version, canonical serialization, digest inclusion/exclusion, and
   mutation tests for every contract;
2. deterministic planning under repeated and permuted inputs;
3. cycle, malformed, unknown, and unsupported requirement rejection;
4. exact approval-digest binding, changed-content rejection, expiry, and replay;
5. immutable successor and unchanged historical execution binding;
6. zero retrieval, Capability, Runtime, or Provider invocation before publication;
7. authorization-first deterministic descriptor matching, stable ties, explicit gaps,
   and disclosure-safe rejection reasons;
8. `RoleGap` factual behavior and `RoleCandidatePreview` non-executability across all
   boundaries;
9. declared Native-only placement and honest unavailable behavior;
10. authorization-before-retrieval and denied-source zero-knowledge/non-disclosure;
11. exact document/version/section/chunk identity and deterministic retrieval ordering;
12. distinct stale, expired, denied, not-found, unavailable, and error behavior;
13. citation provenance and exact Product/Technical Knowledge identity equality;
14. live/synthetic separation and no live fixture fallback;
15. tenant isolation, no writeback, and MCP transport-only assertions;
16. Demo provenance, rollback, backward compatibility, and unsupported-claim audits.

## 17. Future implementation decomposition

No task ID is allocated and no package is authorized by this decision.

| Work package | Type and prerequisites | Exact future scope / expected path families | Non-goals | Acceptance and blocking status |
| --- | --- | --- | --- | --- |
| Intent and Canonical Planning Engine | `IMPL`; this decision and internal-contract gate | backend domain/contracts/services plus focused tests; proposal parsing, validation, digest, approval, revisions | public API/CRD, autonomous approval | section 16 planning tests; blocks enhanced Demo, not current release acceptance by itself |
| Curated Descriptor and Published-Role Matcher | `IMPL`; planning contracts and catalog fixtures | backend catalogs/matching/policy integration plus tests | marketplace, generated publication, credential grant | deterministic authorization-first matching/gaps; blocks enhanced Demo |
| Runtime Requirement and Native Placement Bridge | `IMPL`; approved revision/matcher and existing Native contract | backend/runtime bridge and tests using declared Native target | Runtime Manager, external routing, recovery | Native-only and unavailable tests; blocks live enhanced Demo execution |
| Bounded Knowledge Pack and Authorized Retrieval | `IMPL`; Knowledge contracts, security gate, source-asset approval | bounded Demo Knowledge assets, backend retrieval/policy/Evidence and tests | ingestion, vector DB, production RAG, writeback, MCP | denial, identity, ordering, citation tests; blocks cited enhanced Demo |
| Product View Live Planning and Correction Journey | `IMPL`; shared DTO/projection and planning/retrieval packages | backend shared DTO/service and frontend Product journey/tests | frontend plan authority, citation minting | progressive disclosure, correction/successor, equality; blocks product Demo journey |
| Supplier Quality Demo Scenario Pack | `DEMO`; all bounded services available | Demo configuration/data/manifests/docs and scenario tests | general Knowledge platform or production claim | end-to-end provenance and business Outcome; blocks enhanced Golden Demo only |
| Enhanced Golden Demo Acceptance | `TEST/REL`; scenario pack complete | Golden E2E, support-claim, rollback, documentation and release evidence | certification or production readiness by inference | all section 16 gates; blocks any future enhanced Golden Demo acceptance |

Expected path families are indicative and require separate Human scope authorization.
Portfolio, Golden Demo, and Release artifacts are unchanged here.

The prerequisite order is: internal contract/identity mapping and planning engine;
authorization-capable matcher; Native placement bridge and bounded Knowledge retrieval
in parallel only after their shared identities are fixed; shared Product correction
journey after planning/retrieval DTOs; Scenario Pack after all live seams; enhanced
Golden acceptance last. A package MUST NOT write another package's authority and a
single writer owns each shared contract change. Any public API, CRD, Graph semantic,
dependency/lockfile, persistent-infrastructure, or workflow-lifecycle impact discovered
by a package requires its own Human Architecture Gate before implementation. No package
or task ID is allocated here.

## 18. v0.2/v0.3 boundary

| Classification | Knowledge capability |
| --- | --- |
| `V0_2_MUST` | contracts; one bounded read-only Pack; deterministic authorized retrieval; live retrieval Evidence; live authorized citations |
| `V0_2_SHOULD` | limited retrieval/citation evaluation |
| `V0_2_PREVIEW_ONLY` | user feedback on citation usefulness, without policy or learning effect |
| `V0_3` | general ingestion, document processing, indexing, vector database, hybrid retrieval operations, enterprise Knowledge lifecycle/publication/operations, MCP Resource integration, scale and quality operations |
| `REJECT_FOR_V0_2` | cross-tenant Knowledge, automatic conversational writeback/publication, hidden ingestion, production RAG claims |

Generated-role publication/matching, Agent Factory, managed Agent Instance lifecycle,
Runtime Manager, distributed placement, Recovery, optimization, OpenClaw/Hermes managed
support, and production Certification are also v0.3 or later.

Preference, Intervention, feedback-to-policy, and Optimization/PublishedOptimization
authority require a **second Human Architecture Review**. `ProductSemanticCorrection`
does not implement preference learning, an Intervention ledger, tenant policy, an
optimization candidate lifecycle, or production influence. No authoritative four-stage
v0.3 Portfolio is created or implied here.

## 19. Consequences and limitations

The decision creates a traceable separation between model proposal, deterministic
validation, Human decision, protected-resource authorization, live execution, Evidence,
and projection. It supports a business-first experience without granting the frontend
control-plane authority.

The cost is additional internal identities, versioning, policy decisions, and explicit
failure states. v0.2 remains a bounded single-domain, Native-only Technical Preview.
This architecture proves neither production scale nor general planner, Knowledge, role,
Runtime, recovery, optimization, or certification capability.

## 20. Compatibility and rollback

This decision changes no public API, CRD, Kubernetes API group/version, Canonical Graph
semantics or code, dependency, lockfile, workflow, Runtime implementation, or persistent
infrastructure. It is compatible with current Product/Technical views by requiring one
shared authoritative identity spine and additive future internal contract versions.

It is compatible with S5-ARCH-010 and S5-IMPL-014: Kubernetes remains execution-state
authority; detailed Evidence remains append-only; the Canonical Graph retains relationship
authority; the deterministic backend assembler retains shared Product/Technical snapshot
authority. Knowledge retrieval Evidence is an additional future Evidence type, not a new
execution-state, Workflow, Graph, or Knowledge-publication authority.

Architecture rollback is `git revert -m 1 <future-pr-72-main-merge-commit>` for the
required future GitHub merge commit. No data migration,
infrastructure cleanup, credential rotation, Runtime action, or Demo reset is required
because this decision implements none. Future internal contracts MUST be explicitly
versioned; storage/API migration decisions remain deferred to their implementation gates.

## 21. Explicit non-goals

- application code, tests, APIs, CRDs, or Canonical Graph changes;
- general Knowledge ingestion, indexing, vector database, RAG, or operations;
- cross-tenant Knowledge, learning, writeback, or publication;
- MCP Knowledge infrastructure;
- generated-role publication, Agent Factory, or generated-role matching;
- managed Agent Instance or Runtime Manager lifecycle;
- distributed placement, pools, scaling, failover, migration, or Recovery;
- OpenClaw/Hermes fallback or selection;
- Golden Demo or Knowledge Pack implementation;
- Provider certification, production readiness, or release acceptance;
- automatic permission, credential, policy, correction, or optimization effects.
