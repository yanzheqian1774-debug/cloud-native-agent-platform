# S5-ARCH-012 — User Intervention, Preference, Feedback, and Governed Optimization Boundary v1

## 1. Status and decision

| Field | Value |
| --- | --- |
| Session | `S5-ARCH-012` |
| Decision | `APPROVED_WITH_CONSTRAINTS` by the Human Architecture Decision |
| Implementation status | `NOT_STARTED` |
| Baseline | `0ea21ab628561f2e1e5e1a08651e9ef5a9b8fc79` |
| Selected architecture | Governed Successor and Cold Optimization Boundary |
| Release boundary | bounded internal v0.2 preview; governed publication reserved for v0.3 |
| Contract status | typed internal candidates; `NOT_FROZEN`; no public API or CRD schema |

This G2 decision defines distinct authorities and contracts for:

```text
ProductSemanticCorrection
→ CanonicalCorrectionPatch
→ immutable SuccessorRevision
→ InterventionEvent and OutcomeFeedback
→ bounded preference suggestion/confirmation
→ ImprovementCandidate
→ OptimizationEvaluation
→ Human/policy OptimizationDecision
→ future versioned PublishedOptimization
→ observation and rollback
```

It is architecture, not implementation evidence. It creates no preference service,
learning system, optimization service, persistence schema, model training, Knowledge
writeback, Demo, public API, CRD, Graph relation, dependency, or Workflow behavior.

## 2. Problem and product principle

S5-ARCH-011 establishes business-semantic correction and immutable successor
revisions, while S5-ARCH-010 preserves independent append-only Execution Evidence.
The platform still needs a safe boundary for recording why Humans intervene,
assessing Outcomes, honoring explicit preferences, and proposing future improvements
without converting one interaction, inference, or synthetic example into policy.

The Product View captures business intent. It is not canonical revision, audit,
preference, learning, publication, or authorization authority. A correction is
compiled deterministically and validated before a new immutable revision can exist.
Facts, assessments, preferences, proposals, evaluations, decisions, and published
versions remain separately typed. The frontend only presents and submits commands.

The governing principle is: **correction may improve the current task through an
approved successor; cross-task improvement is a cold, governed, versioned process.**

## 3. Common envelope without semantic collapse

The contracts below MAY share only an internal metadata envelope containing record
identity, schema version, tenant, security domain, actor/principal reference,
provenance, creation time, authority reference, and digest algorithm/version. Each
contract retains its own typed payload, owner, lifecycle, validation, authorization,
mutability, retention, deletion, and failure semantics. There is no generic Event,
Evidence, Knowledge, Workflow, or authorization authority.

Canonical digests use documented canonical serialization, Unicode normalization,
stable ordering, explicit null rules, and a versioned algorithm. Authorization,
scope, consent, semantic content, predecessor links, and referenced versions are
included where material. Presentation labels, transport metadata, caches, tracing,
secrets, and prohibited content are excluded. A digest MUST NOT be a recoverable hash
oracle for deleted or prohibited data.

All records carry tenant and security domain from trusted context, never model or UI
assertion. Missing, contradictory, expired, or unauthorized context fails closed.

## 4. Authority matrix

| Concern | Sole owner; identity/version/mutability | Scope and authorized consumers | Fail closed; prohibited escalation |
| --- | --- | --- | --- |
| Product semantic correction | correction authority; correction ID/revision/digest; immutable decided revision | validator, projections, intervention capture | invalid target/actor blocks; Product View/model cannot revise Canonical Workflow |
| Canonical correction patch | deterministic correction compiler; patch ID/schema/digest; immutable | canonical validator and approval | compilation/schema/before-state mismatch blocks; UI diff is not authority |
| Canonical successor revision | existing canonical revision authority; revision ID/version/digest; immutable | execution, Evidence, projections | no valid patch/approval means no successor; prior approval cannot be reused |
| Intervention audit | append-only Intervention authority; event ID/schema/digest | authorized audit, candidate Evidence-set builder | invalid linkage/consent excludes signal; event never becomes policy |
| Outcome feedback | Feedback authority; feedback ID/revision/digest; immutable revisions | authorized projections and candidate Evidence sets | invalid Outcome/Evidence or viewer blocks; feedback never rewrites Outcome |
| Preference value | user-controlled Preference Profile authority; profile/entry versions | eligible Planner input and authorized presentation | missing value/consent/scope means no use; profile is not audit authority |
| Preference consent | Consent authority; decision ID/version; append-only decisions | preference evaluator and audit | absent/expired/withdrawn consent denies future use; interaction/confidence is not consent |
| Preference scope | trusted scope-policy authority; decision ID/policy version | eligibility evaluator | ambiguous or cross-domain scope denies; user cannot promote to team/tenant |
| Preference deletion | Preference authority executes deletion; tombstone authority records fact | future retrieval/application and minimal audit | incomplete deletion invalidates future bindings; tombstone cannot retain value |
| Improvement candidate | candidate authority; candidate ID/version/digest; immutable version | evaluation and authorized preview | insufficient/unsafe inputs reject; candidate grants no permission or application |
| Candidate input set | Evidence-set assembler; set ID/version/digest; immutable | candidate generation and evaluation | provenance/consent/scope mismatch excludes input; not Execution Evidence authority |
| Evaluation | evaluation authority; evaluation ID/version/digest; immutable | publication decision maker | incomplete/reproducibility failure cannot pass; evaluator cannot publish |
| Publication decision | Human/policy decision authority; decision ID/policy version; append-only | publication service | absent/mismatched decision blocks; metrics/model/evaluator cannot approve |
| Published optimization | publication authority; optimization ID/version/digest; immutable | eligibility and application decision | exact bindings required; publication is not Planner/Workflow/authorization authority |
| Application decision | deterministic application evaluator; decision ID/version; append-only | Planner candidate generation and projections | ineligible/conflicting/denied version is not applied; no permission expansion |
| Rollback | authorized lifecycle authority; rollback record ID/version; append-only | eligibility evaluator and operations | revoked target becomes ineligible; rollback does not rewrite history |
| Execution facts | S5-ARCH-010 Execution Evidence authority | Graph/shared views and authorized audit | optimization records cannot fabricate/overwrite execution facts |
| Knowledge | independent Knowledge authority | separately authorized retrieval/publication | no intervention, feedback, preference, or candidate writeback |
| Workflow template/policy | separately governed template/policy publication authority | planning under explicit eligibility | optimization cannot directly mutate template, policy, active Workflow, or revision |
| Product/Technical projections | one shared backend assembler plus view policies | authorized users | frontend cannot mint identities, feedback, consent, preferences, or optimization state |

Metrics observe named records. They are never decision or publication authority.

## 5. Hot and cold paths

```text
HOT: current task → correction → compile/validate → approval where required
     → immutable successor → execution → Outcome → Execution Evidence

COLD: authorized interventions/feedback/preferences → scoped Evidence set
      → grouping/attribution → candidate → evaluation → Human/policy decision
      → future publication → application decision → observation → rollback
```

Cold-path outage, rejection, retention, or corruption MUST NOT block ordinary task
execution. The cold path cannot mutate an active Workflow, approved revision, running
execution, Outcome, or Evidence. Candidate generation never writes into the Planner.
There is no online self-modification, automatic production publication, automatic
training/fine-tuning claim, or automatic Knowledge writeback.

## 6. Typed contract model

| Contract | Typed payload and identity | Lifecycle, mutability, retention and failure |
| --- | --- | --- |
| `ProductSemanticCorrection` | exact target revision/element, structured change, reason, principal, domain, authorization, provenance, time, digest | `DRAFT → VALIDATED → ACCEPTED/REJECTED`; decided revision immutable; invalid/unauthorized target rejects |
| `CanonicalCorrectionPatch` | exact before/after identities and normalized bounded operations compiled from accepted correction | `COMPILED → VALIDATED/INVALID`; immutable; mismatch or unknown operation fails |
| `InterventionEvent` | event kind, prior/successor, element, patch, reason, principal, execution/Outcome/Evidence and optimization-consent references | append-only `RECORDED/EXCLUDED/RETAINED/TOMBSTONED`; malformed or unsafe content rejected |
| `OutcomeFeedback` | immutable Outcome/Evidence target, assessment, reasons, superseded feedback | `RECORDED → SUPERSEDED`; revisions append; unauthorized target/view denies |
| `UserPreferenceProfile` | profile identity, owner, separately versioned entry references and status | mutable aggregate of immutable entry versions; `ACTIVE/DISABLED/DELETED`; no audit authority |
| `UserPreferenceEntry` | typed value, scope, purpose, status, consent and provenance references | `SUGGESTED → CONFIRMED/REJECTED → DISABLED/EXPIRED/DELETED`; value separately erasable |
| `PreferenceConsent` | principal, exact entry version, scope, purpose/use, effective/expiry/withdrawal, provenance | append-only `GRANTED/DENIED/WITHDRAWN/EXPIRED`; no inferred consent |
| `PreferenceTombstone` | entry identity, scope, deletion authority/time, nonsensitive reason and lifecycle fact | immutable minimal record; never contains value, embedding, encryption payload, or value hash |
| `ImprovementCandidate` | exact proposal/type/domain/scope, Evidence set, provenance split, counts, confidence, benefit, cost/latency, risk, counterexamples, limits, evaluation requirements | immutable versions; `DRAFT/EVALUATING/APPROVED/REJECTED/PUBLISHED/SUPERSEDED/REVOKED/ROLLED_BACK`; v0.2 stops at `DRAFT/NOT_APPLIED` |
| `CandidateEvidenceSet` | exact intervention/feedback/Outcome/Evidence/consent decisions, dataset version, inclusion/exclusion policy, retention and provenance classes | immutable set version; missing authorization or mixed-hidden provenance invalidates |
| `OptimizationEvaluation` | exact candidate/set digests, policy, evaluator, datasets, metrics, regressions, safety, rollback readiness, result and limitations | immutable `PENDING/RUNNING/PASSED/FAILED/INCONCLUSIVE`; cannot publish |
| `OptimizationDecision` | exact candidate/evaluation digests, Human/policy actor, scope, reasons and decision time | append-only `APPROVED/REJECTED/REVOKED`; mismatch blocks publication |
| `PublishedOptimization` | publication identity/version/digest, bound decision, scope/domain, effective time and rollback target | immutable `PUBLISHED/SUPERSEDED/REVOKED/ROLLED_BACK`; future v0.3 only |
| `OptimizationApplicationDecision` | exact published version, context/domain, eligibility, authorization, precedence/conflicts and generated-candidate provenance | append-only `APPLIED/NOT_APPLICABLE/DENIED/CONFLICT`; never mutates approved revision |
| `OptimizationRollbackRecord` | actor, reason, time, scope, target and replacement/prior version | append-only; immediately makes target ineligible for future application |

Every contract defines projection-safe summaries separately from protected payloads.
Retention is policy-bound by tenant/security domain. References never embed protected
content. Unknown schema, authority, lifecycle, or digest versions fail closed.

## 7. Correction and immutable successor

`ProductSemanticCorrection` names the exact canonical revision and stable element.
The correction compiler transforms only allowlisted structured business operations
into a `CanonicalCorrectionPatch`. It rejects UI-only fields, raw prompts,
unrestricted payloads, stale before-identities, cycles, incompatible descriptors,
permission expansion, and unsupported operations.

A validated patch creates a new candidate with a new digest. Approval requirements
are re-evaluated; content or digest change invalidates prior approval. Only canonical
revision authority creates the immutable successor and predecessor link. The prior
decided revision and every execution bound to it remain unchanged and queryable.

```text
CORRECTION_DRAFT → VALIDATING → VALIDATED → PENDING_APPROVAL
                                 ├→ REJECTED
                                 └→ APPROVED → SUCCESSOR_CREATED
```

## 8. Intervention boundary

Allowed event kinds are `TASK_ADDED`, `TASK_REMOVED`, `TASK_REWRITTEN`,
`TASK_ORDER_OR_DEPENDENCY_CHANGED`, `ROLE_REPLACED`, `ROLE_GAP_IDENTIFIED`,
`DATA_REQUIREMENT_CHANGED`, `KNOWLEDGE_REQUIREMENT_CHANGED`, `SKILL_CHANGED`,
`CAPABILITY_CHANGED`, `APPROVAL_POINT_CHANGED`, `CONSTRAINT_CHANGED`,
`OUTPUT_FORMAT_CHANGED`, `WORKFLOW_REJECTED`, and `RESULT_FEEDBACK_PROVIDED`.

An event links prior and, where applicable, successor revisions; affected stable
element; bounded patch; stable reason; principal; tenant/security domain; decision
time; Platform Execution Identity where applicable; immutable Outcome and Execution
Evidence references; and an explicit optimization-use consent decision. It records a
fact, not policy, preference, Knowledge, authorization, or permission.

Raw prompts, secrets, credentials, Provider bodies, unrestricted business payloads,
stack traces, host paths, arbitrary metadata, and recoverable hashes of prohibited
content are rejected before append.

## 9. Outcome feedback

Feedback assesses an exact immutable Outcome/Evidence identity with assessment
`SATISFIED`, `PARTIALLY_SATISFIED`, or `UNSATISFIED`, plus reasons
`MISSING_TASK`, `EXTRA_TASK`, `WRONG_DATA`, `INSUFFICIENT_DATA`,
`WRONG_KNOWLEDGE`, `WRONG_ROLE`, `WRONG_SKILL`, `WRONG_CAPABILITY`,
`WRONG_ORDER`, `MISSING_CONSTRAINT`, `WRONG_OUTPUT_FORMAT`, or
`CITATION_NOT_USEFUL`.

Feedback never rewrites Outcome or Evidence. Correction appends a successor feedback
revision that explicitly supersedes the earlier record. Authorized projections may
show bounded summaries; nondisclosure and field filtering occur before assembly so
hidden content cannot be inferred. Feedback alone cannot influence future planning.

## 10. Preference, consent, precedence, and deletion

Preference types are locale, response style, detail level, output format, citation
requirement, approval preference, notification preference, domain dimensions, and
prohibited actions. Each entry is visible, editable through a successor version,
disableable, and deletable.

| Scope | Admission and use |
| --- | --- |
| `CURRENT_TASK` | explicit user action may affect that task; never silently durable |
| `USER` | explicit confirmation/consent; visible and controlled by user |
| `TEAM` | authorized team-owner approval and compatible member context |
| `TENANT` | authorized tenant/business-owner approval and policy compatibility |

Inference creates `SUGGESTED` only; confidence is not consent. Deterministic
precedence is current-task explicit choice, user-confirmed entry, authorized team
entry, then authorized tenant entry, each subject to mandatory policy and prohibited
actions. Same-rank contradiction is `CONFLICT` and fails closed until explicitly
resolved. No cross-user promotion, cross-tenant use, hidden personalization, or
automatic conversion to Workflow policy, Skill, Knowledge, or tenant rule is allowed.

`PreferenceConsent` is independent of the value. It binds the exact entry version,
principal, scope, purpose, allowed use, effective time, expiry, withdrawal, and
decision provenance. Current-task execution consent is not optimization consent;
user scope is not team/tenant consent. Withdrawal prevents future selection.

Value storage is separable from immutable audit facts. Deletion erases the sensitive
value and bounded recoverable copies, invalidates bindings and cache entries, and
appends only a minimal `PreferenceTombstone`. The tombstone contains identity, scope,
deletion authority/time, nonsensitive reason, and lifecycle fact—never the value,
raw text, reversible ciphertext, recoverable hash, sensitive metadata, or embedding.
Backups may retain encrypted physical blocks until governed expiry; they cannot be
restored into active use without reapplying deletion logs. Immediate physical erasure
from every external backup is not claimed and requires implementation-specific gates.

## 11. Candidate and Evidence-set provenance

Candidate types cover Task description/decomposition, Workflow template, Data or
Knowledge requirement, role matching, Skill/Capability recommendation, approval
point, and output format. A candidate records exact proposal, scope/domain, Evidence
set, separately measured synthetic/live provenance, sample count, confidence,
expected benefit, cost/latency estimate, safety risk, counterexamples, limitations,
evaluation requirements, version/digest, and lifecycle.

`CandidateEvidenceSet` lists exact InterventionEvent and OutcomeFeedback IDs,
Outcome/Execution Evidence references, consent/scope decisions, dataset version,
inclusion/exclusion policy, retention, and digest. Synthetic history is visibly
labelled and never presented as live experience. Inputs must be authorized,
consented for the purpose, tenant-local, and scope-compatible. One intervention is
insufficient for publication. A candidate grants no access, permission, approval, or
application and cannot modify active or approved work.

## 12. Evaluation, publication, application, and rollback

Evaluation binds exact candidate and dataset/Evidence-set digests, policy version,
evaluator, historical replay, holdouts, deterministic metrics where applicable,
before/after quality, first-plan acceptance, Human corrections, execution success,
DENY regressions, citation quality, cost, latency, safety, counterexamples, rollback
readiness, result, and limitations. It preserves synthetic/live separation and tenant
isolation. Minimum-evidence policy and Human review apply to material policy changes.
Evaluation never authorizes publication.

```text
DRAFT → EVALUATING → APPROVED / REJECTED
                    APPROVED → PUBLISHED
                    PUBLISHED → SUPERSEDED / REVOKED / ROLLED_BACK
```

In v0.2 every candidate remains `DRAFT / NOT_APPLIED`. Future v0.3 publication binds
exact candidate and evaluation digests, approved scope, Human/policy decision,
publisher, effective time, rollback target, and immutable version.

An `OptimizationApplicationDecision` considers an exact published version using
tenant/security domain, applicable domain, deterministic eligibility, authorization,
precedence, conflict handling, and compatibility. It records provenance in a new
Workflow candidate. It cannot expand permission, bypass descriptor compatibility or
required Human approval, or mutate an existing approved revision. Published
Optimization informs candidate generation; it is not Planner, Workflow, approval, or
authorization authority.

Rollback appends an authorized record, stops future application of the target,
identifies replacement/prior version, and preserves historical generated revisions
and Evidence. It does not rewrite past execution, replay tasks, delete Execution
Evidence, or reverse external effects. Reverting this architecture document only
reverts the decision text; future implementations require separate migration,
deletion, operational rollback, and side-effect gates.

## 13. Knowledge non-writeback

InterventionEvent, OutcomeFeedback, UserPreferenceProfile, and ImprovementCandidate
are not Knowledge. Raw correction, feedback, preference, or conversation content
cannot enter a Knowledge Pack automatically. Cross-tenant learning is rejected.

A derived Knowledge article, Skill revision, Workflow template, or Planner policy is
a different governed asset and must pass its own publication, authorization,
provenance, versioning, retention, and rollback boundary. Knowledge deletion and
retention remain independently governed.

## 14. Bounded Demo preview

The supplier-quality preview separates `DEMO_CONFIGURATION`, visibly labelled
`SYNTHETIC_HISTORY`, and `LIVE_EXECUTION`. Live work includes current planning,
authorized Knowledge retrieval, Native execution, Evidence, correction, and Outcome.
A user changes one business criterion; a validated immutable successor executes; the
before/after Outcomes are compared; and authorized history plus the live intervention
may calculate a candidate. That candidate remains `DRAFT / NOT_APPLIED`. The preview
claims no next-task improvement, publication, Knowledge writeback, policy change,
Demo readiness, or Release acceptance. This decision implements no Demo asset.

## 15. Metrics model

Each metric records numerator, denominator, tenant/domain/scope, time window, dataset
version, and synthetic/live provenance. Empty denominators are `NOT_MEASURABLE`, not
zero. Metrics are observational Evidence only.

| Metric | Numerator / denominator |
| --- | --- |
| First-plan acceptance | first plans accepted without correction / eligible first plans |
| Corrections per task | accepted corrections / eligible completed tasks |
| Task add/remove/rewrite | events of each kind / eligible task plans |
| Role replacement / RoleGap | respective events / eligible role decisions |
| Skill/Capability/Data/Knowledge replacement | respective changes / eligible bindings |
| Correction-to-Outcome improvement | corrected successors improving defined Outcome metric / comparable successor pairs |
| Citation usefulness | useful cited Outcomes / assessed cited Outcomes |
| Preference confirmation/rejection | confirmed or rejected suggestions / presented suggestions |
| Candidate creation | valid candidates / eligible Evidence sets |
| Candidate adoption/rejection | approved or rejected candidates / decided candidates |
| Similar-task intervention reduction | baseline minus observed interventions / comparable tenant-local task cohort |
| Execution success | successful executions / terminal eligible executions |
| DENY zero-call | denied decisions with zero Provider calls / denied decisions |
| Cost and latency | normalized total and distribution / eligible executions or evaluations |
| Rollback | rolled-back published versions / published versions |

## 16. Privacy, security, and abuse threat model

| Threat; affected authority | Attack/failure path | Mitigation and fail-closed behavior | Required future test; residual limitation |
| --- | --- | --- | --- |
| Hidden inference; Preference | model suggestion applied silently | suggestion-only state and explicit consent; no consent means no use | unconfirmed suggestion never affects plan; social inference remains imperfect |
| Consent spoofing; Consent | UI/model asserts another principal | trusted identity, exact version/purpose binding; mismatch denies | forged/expired/withdrawn consent; upstream identity assurance required |
| Cross-user/tenant use; scope/Evidence set | cache, query, or aggregate crosses domain | pre-query isolation and domain-bound cache/set; deny contradiction | cross-domain query/aggregation/cache negatives; full tenant IAM is future |
| Feedback poisoning/repeated manipulation; Candidate | malicious signals dominate | principal/rate provenance, diversity/minimum-evidence, counterexamples, Human review | sybil/repetition/outlier fixtures; organizational collusion remains residual |
| Synthetic shown as live; Evidence set | labels removed in aggregation/UI | immutable provenance class and separate metrics; hidden mix invalidates | projection and digest separation tests; synthetic realism can still bias review |
| Sensitive Diff leakage; correction/event | patch embeds protected payload | allowlisted operations, classification and field filtering; reject unsafe patch | secret/business-payload/hash-oracle negatives; classifiers are fallible |
| Deleted value retained; Preference | tombstone/hash/embedding/cache/backups preserve value | value/audit separation, cache invalidation, prohibited tombstone fields | deletion/recovery/backup-restore tests; physical backup expiry is delayed |
| Denied Knowledge leakage; Evidence set/evaluation | denied content becomes feature or proposal | independently authorized references only; exclusion before load | DENY corpus zero-read and no-derived-output tests; side-channel research continues |
| Permission expansion; Candidate/application | proposal broadens Capability/Data/Knowledge | independent authorization/compatibility and no-expansion invariant | privilege-diff and descriptor mismatch tests; policy configuration risk remains |
| Approval bypass/insufficient evidence; publication | model/evaluator/metric self-approves | exact digest binding, minimum policy, separate Human/policy decision | single-event, self-approval, digest-mismatch negatives; Human error remains |
| Policy conflict; application | multiple versions/preferences conflict | deterministic precedence and explicit `CONFLICT`; no application | equal-rank and mandatory-policy conflict tests; policy design remains Human-owned |
| Rollback ineffective; lifecycle | caches keep applying revoked version | authoritative eligibility check, invalidation and observation; deny stale version | concurrent rollback/cache/restart tests; in-flight external effects remain |
| Metrics become authority; publication | threshold triggers automatic publish | metrics are Evidence only; explicit decision required | threshold-without-decision never publishes; reviewer automation bias remains |

## 17. Future implementation decomposition — not allocated

| Work package / type | Prerequisites and scope | Non-goals, acceptance and gates | Demo/Release status |
| --- | --- | --- | --- |
| Product Correction and Intervention Capture / `IMPL` | Human implementation gate; typed correction/compiler/successor/event ports and projection integration | no public schema/Graph change; exact linkage, allowlisting, approval and privacy negatives | possible Demo prerequisite; never Release approval alone |
| Outcome Feedback / `IMPL` | immutable Outcome/Evidence identities and authorization | append-only revisions and nondisclosure; no Outcome rewrite or Planner effect | optional preview input; non-blocking to ordinary execution |
| Bounded Preference Preview / `IMPL` | State/privacy/deletion gate and trusted identity | current-task/user preview only; CRUD, consent, conflict and erasure tests; no full State Plane | preview-only; not production personalization |
| Improvement Candidate Preview / `IMPL` | intervention/feedback inputs, consent/scope and provenance policy | deterministic Evidence set/candidate display; no evaluation service/application | supplier preview extension; no Release claim |
| Supplier Quality Optimization Demo Extension / `SOLUTION` | accepted Demo gate and preceding preview packages | labelled synthetic/live split and `DRAFT/NOT_APPLIED`; no Knowledge/policy writeback | separate Golden Demo and Release gates required |
| v0.3 Evaluation and Publication Service / future `ARCH` then `IMPL` | v0.3 architecture, Tenant/State/governance/persistence decisions | evaluation, publication, application, observation/rollback; no self-approval | outside v0.2; independently release-blocking if selected |

Expected future path families are bounded domain modules, repositories/adapters only
after persistence gates, Console backend projection contracts, frontend presentation,
and dedicated unit/contract/privacy/conformance tests. No task ID or owner is allocated.

## 18. v0.2/v0.3 boundary

**v0.2 MUST:** ProductSemanticCorrection, CanonicalCorrectionPatch, immutable
SuccessorRevision linkage, append-only InterventionEvent, versioned OutcomeFeedback,
consent contract, tenant/security-domain isolation, and Knowledge non-writeback.

**v0.2 PREVIEW ONLY:** bounded UserPreferenceProfile suggestion/confirmation,
calculated ImprovementCandidate, and candidate/Evidence presentation. There is no
production or next-task automatic application.

**v0.3:** generalized aggregation, evaluation service, PublishedOptimization, policy
application, lifecycle operations, governed cross-task learning within one tenant,
observation, rollback automation, and full Preference/State Plane.

Rejected in every boundary: cross-tenant learning, automatic production publication,
online self-modifying Planner, automatic training/fine-tuning claims, raw-prompt
Knowledge writeback, automatic permission expansion, and one-intervention publication.

## 19. Compatibility

- S5-ARCH-011 remains correction and canonical successor authority; this decision
  refines downstream intervention/feedback/optimization and never mutates its revision.
- S5-ARCH-010 Execution Evidence stays independent and append-only. References do not
  duplicate evidence payloads or make optimization a second execution-fact authority.
- Product and Technical projections consume the same authoritative identities through
  the shared assembler; neither frontend nor view owns learning state.
- Existing approval digest semantics remain: changed content requires new approval.
- Knowledge remains authorization-first, read-only consumption for the bounded v0.2
  path; there is no automatic Knowledge publication.
- Canonical Graph vocabulary, relationship ownership, direction, cardinality, and
  identity remain unchanged.
- Platform Execution Identity is referenced where live execution exists and is never
  replaced by Runtime, Provider, event, or optimization identity.
- Runtime boundaries and Native execution are unchanged; no Runtime Manager,
  OpenClaw, Hermes, MCP, Recovery, or certification change is made.
- Current public APIs and `agentos.io/v1alpha1` Agent/Task/Workflow CRDs are unchanged.

If implementation requires a public schema, persistence architecture, Graph semantic,
Workflow lifecycle, authorization, Tenant, or full State Plane change, it MUST stop at
a new Human G2 gate.

## 20. Consequences, limitations, and non-goals

Benefits are auditable correction, explicit consent, erasable preference values,
tenant-safe proposal provenance, and a governable path to future optimization without
online self-modification. Costs are more typed records, explicit decisions, retention
coordination, and cold-path latency. The design intentionally favors safety and replay
over automatic adaptation.

Limitations include no selected storage, physical schema, retention duration, full
tenant/IAM system, production policy engine, full State Plane, statistical validity
thresholds, high-scale aggregation, immediate erasure from every backup, production
evaluation, publication service, automated rollback, or certification.

Non-goals are application code, tests, API/CRD/Graph changes, dependencies, Workflow
changes, Portfolio sequencing, Knowledge implementation, Demo assets, Runtime work,
MCP/OpenClaw/Hermes work, Recovery, Certification, Release readiness, model training,
and production learning claims.
