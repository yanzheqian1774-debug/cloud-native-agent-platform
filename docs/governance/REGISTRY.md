# Governance Registry

This is the authoritative index for Project Session lifecycle, Human Gates,
open decisions, and Evidence Debt metadata. It links to full evidence instead
of duplicating product or architecture narratives. Source and tests remain
authoritative for implementation; accepted ADRs and architecture evidence
remain authoritative for architecture.

## Registry semantics

### State vocabularies

- Session lifecycle: `NEW`, `ACTIVE`, `REVIEW`, `CLOSING`, `CLOSED`
- Authorization: `PROPOSED`, `AUTHORIZED`, `COMPLETED`
- Human Gate outcomes: `PASS`, `PASS_WITH_CONSTRAINTS`,
  `MORE_EVIDENCE_REQUIRED`, `STOP`
- Decision states: `PROPOSED`, `PENDING`, `ACCEPTED`,
  `ACCEPTED_WITH_EVIDENCE_DEBT`, `DEFERRED`, `BLOCKED`, `SUPERSEDED`
- Evidence states: `SUPPORTED`, `NOT_YET_PROVEN`, `DEFERRED`, `NOT_FROZEN`,
  `CERTIFIED`

`CERTIFIED` may be used only when an explicit certification gate identifies the
certified combination and evidence. Absence of certification is not evidence
of failure unless the governing claim requires it.

### Lifecycle rules

- A `CLOSED` Session cannot be reopened; follow-up work requires a new Session.
- Codex does not grant final Human product or architecture decisions.
- Session `PASS` does not imply Schema Freeze, Contract Freeze, Provider
  certification, production readiness, release acceptance, or semantic
  recovery.
- `SUPPORTED` does not mean `CERTIFIED`; `CANDIDATE` does not mean `FROZEN`;
  implemented does not mean Done.
- Each lifecycle change records its provenance and must link the strongest
  available evidence.

### Provenance

- `REPOSITORY_NATIVE`: directly established by durable-main content/history.
- `PR_NATIVE`: established by pull-request metadata and merge history.
- `HUMAN_CONFIRMED`: established by an explicit structured Human Gate/result.
- `DERIVED`: computed from authoritative evidence.
- `PROPOSED`: not yet Human-approved.

## Session Registry

| ID | Title / type | Lifecycle / authorization | Status / result | Source / execution mapping | Final Human Gate | Provenance | Next gate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| S5-GOV-003 | v0.2.2, v0.2.3 and v0.2.4 Authority, Persistence and Workbench Continuity Reconciliation / GOV | `ACTIVE / AUTHORIZED`; Checkpoint A | `GO_WITH_CONDITIONS`; records binding Business, Enterprise Resource, Runtime Operations, Model Governance and Technical Inspection Workbench continuity; governance reconciliation only; no implementation, deployment, release, architecture implementation, certification or public Contract authority | Exact baseline `474b19e7bf32a342d93b4b891f6c7a799b9261b6`; branch `codex/s5-gov-003-v022-v024-authority-persistence-reconciliation`; [exec plan](../exec-plans/active/S5-GOV-003-V022-V024-AUTHORITY-PERSISTENCE-RECONCILIATION.md); [Evidence](../evidence/s5/v0.2/s5-gov-003/README.md) | Product definitions, persistence direction, Workbench continuity, ordering and reconciliation scope: `HUMAN_CONFIRMED`; review, Durable Integration and closure: `PENDING` | authority/allocation: `HUMAN_CONFIRMED`; baseline/CI: `REPOSITORY_NATIVE / PR_NATIVE`; reconciliation: `IN_PROGRESS` | Human review and Durable Integration decision; no downstream task starts automatically |
| S5-ARCH-018 | Bounded Product Continuity Persistence Architecture / ARCH G2 | `ACTIVE / AUTHORIZED / CHECKPOINT_A / PROPOSED_DECISION_READY_FOR_HUMAN_REVIEW` | Architecture/governance only; proposes typed repository ports, one bounded single-node SQLite store, immutable/append-only history, PostgreSQL seam and first Durable Agent Definition entry; no implementation, public API/CRD, State Plane, Tenant, multi-node or production authority | Exact baseline `a6ec463a365b5f12e8fb64b0b84772a3beb0ae15`; exact-main CI `33359075556` succeeded; branch `codex/s5-arch-018-bounded-product-continuity-persistence`; [decision](../../architecture/s5/v0.2/S5-ARCH-018-BOUNDED-PRODUCT-CONTINUITY-PERSISTENCE-V1.md); [Evidence](../evidence/s5/v0.2/s5-arch-018/README.md) | Allocation/G2 entry: `HUMAN_CONFIRMED`; architecture acceptance, merge, Durable Integration and implementation allocation: `PENDING` | baseline/CI/collision/content: `REPOSITORY_NATIVE / PR_NATIVE`; decision: `PROPOSED` | Human Architecture Review and Durable Integration decision; no implementation starts automatically |
| S5-ARCH-014–S5-ARCH-017 | historical architecture-number reconciliation debt / ARCH | `RESERVED / UNRECONCILED / NOT_REUSABLE` | Durable repository lacks sufficient authoritative records to establish exact contents, decisions, acceptance or closure; no contents are reconstructed | Visible historical session traces exist outside durable authority; they are not imported as accepted architecture | Reconciliation Gate: `NOT_HELD` | debt classification: `HUMAN_CONFIRMED`; exact historical authority: `NOT_YET_PROVEN` | Separate Human reconciliation; never reuse these identifiers |
| S5-IMPL-041 | governed problem-to-plan streaming / IMPL | `CLOSED / COMPLETED`; Human-confirmed terminal closure; reopen prohibited | `SESSION_CLOSED`; code already durable; reimplementation and reintegration not required; binding process-local, derived-index, planning-only, non-production limitations preserved; no downstream execution authority | Source commits `de681a97ee11d6dbec758c3cb3eea4067c00d422`, `8393b67568d2e0329ea5ad6f066b330e1568ca56`; PR #91 merged at durable main `2fdf54edb8658929fde6c1259fefda43a8406a62`; exact-main CI run `33344714261` succeeded | Human Close Confirmation: `PASS / CLOSED` | closure: `HUMAN_CONFIRMED`; implementation/merge/CI: `GIT_NATIVE / PR_NATIVE / VALIDATED`; terminal addendum: `FORWARD_RECORDED_BY_S5_GOV_002` | None; reopen prohibited; no automatic S5-IMPL-042, S5-REL-044, deployment, release, integration, or downstream implementation authority |
| S5-REL-030 | Durable Integration of S5-ARCH-013 / REL | `CLOSED / COMPLETED`; Human-confirmed terminal closure; reopen prohibited | `PASS_WITH_CONSTRAINTS / SESSION_CLOSED`; governance reconciliation only; no downstream authority | PR #78 merged at durable main `8757adabc9a95e3b3934303fa9c6f8586ff854e9`; ordered parents `7bb4c43e03d86259373b9fc5ae79fbcb3c1234c6`, `0993a03817123d9565c8fd03d00dd8fa7e2e0d5f`; exact-main CI run `33180601090` succeeded | Human reconciliation merge and Close Confirmation: `PASS_WITH_CONSTRAINTS` | closure: `HUMAN_CONFIRMED`; merge/CI/content: `PR_NATIVE / REPOSITORY_NATIVE`; terminal addendum: `FORWARD_RECORDED_BY_S5_IMPL_030` | None; reopen prohibited |
| S5-ARCH-013 | Definition Publication and Matchability Authority / ARCH | `CLOSED / COMPLETED`; Human-confirmed terminal closure; reopen prohibited | `PASS_WITH_CONSTRAINTS / SESSION_CLOSED`; internal architecture authority for bounded Package 2 only | Source head `a8ae79574a4c16e646cb33adb7026d1a97d4af8f`; PR #77 merge `7bb4c43e03d86259373b9fc5ae79fbcb3c1234c6`; reconciled through S5-REL-030 at durable main `8757adabc9a95e3b3934303fa9c6f8586ff854e9`; exact-main CI run `33180601090` succeeded | Human Architecture, Integration, Reconciliation, and Close decisions: `PASS_WITH_CONSTRAINTS` | closure/decisions: `HUMAN_CONFIRMED`; architecture/merge/CI: `REPOSITORY_NATIVE / PR_NATIVE`; terminal addendum: `FORWARD_RECORDED_BY_S5_IMPL_030` | None; reopen prohibited |
| S5-IMPL-030 | Curated Descriptor and Published-Role Matcher / IMPL | `ACTIVE / IMPLEMENTATION_COMPLETE / REVIEW_READY / AWAITING_DURABLE_INTEGRATION` | `PASS_WITH_CONSTRAINTS / CHECKPOINT_C / UNMERGED`; internal in-memory Package 2 only; no downstream authority | Baseline `8757adabc9a95e3b3934303fa9c6f8586ff854e9`; branch `codex/s5-impl-030-curated-descriptor-published-role-matcher`; exactly seven authorized implementation, test, Evidence, and governance paths; terminal commit, Draft PR, and exact-head CI are reported in PR/CONTROL Evidence | Checkpoints A, B, and C: `PASS_WITH_CONSTRAINTS`; merge and Durable Integration: `NOT_AUTHORIZED` | gates/lifecycle: `HUMAN_CONFIRMED`; implementation/evidence: `GIT_NATIVE / PR_NATIVE / VALIDATED`; integration: `PENDING` | Human S5-IMPL-030 Terminal Evidence Review and REL Allocation Decision; do not mark Ready, merge, or start REL/downstream work |
| S5-REL-029 | Durable Integration of S5-IMPL-015 / REL | `ACTIVE / DURABLE_INTEGRATION_COMPLETE / RECONCILIATION_PREPARED`; awaiting reconciliation-PR integration and Human Close Confirmation | `PASS_WITH_CONSTRAINTS / AWAITING_RECONCILIATION_INTEGRATION_AND_HUMAN_CLOSE_CONFIRMATION`; governance and Evidence only; no downstream authority | Source S5-IMPL-015 head `fbfd3889b587af08b991525a5abda2b4f994562c`; PR #75 merge `4713b797c53121f24cb70171926318d575b7fcc8`; ordered parents `05bac769b61f42aa5643a8496861e8e962c6bf5b`, `fbfd3889b587af08b991525a5abda2b4f994562c`; exact-main CI `33156199625` succeeded | Durable Integration Gate: `PASS_WITH_CONSTRAINTS`; Human reconciliation-merge and Close Confirmation: `PENDING / NO` | merge/CI: `PR_NATIVE`; integration decision: `HUMAN_CONFIRMED`; reconciliation: `REPOSITORY_NATIVE / PENDING_PR_INTEGRATION` | Human S5-REL-029 Reconciliation Merge and Final Closure Gate; do not merge or close without authorization |
| S5-IMPL-015 | Bounded Intent and Canonical Planning Engine / IMPL | `ACTIVE / IMPLEMENTATION_COMPLETE / AWAITING_HUMAN_CLOSE_CONFIRMATION`; Checkpoint C received Human `PASS_WITH_CONSTRAINTS` | `PASS_WITH_CONSTRAINTS / DURABLY_INTEGRATED / HUMAN_CLOSE_CONFIRMATION_NO`; internal in-memory Package 1 only; no execution, matching, persistence, public API, CRD, Graph, Workflow, DTO, dependency, frontend, Demo, or Release authority | Baseline `05bac769b61f42aa5643a8496861e8e962c6bf5b`; commits `388c37b4ecdf22502f1578fb470d0b40ac048891`, `fbfd3889b587af08b991525a5abda2b4f994562c`; exact-head CI `33153148233` succeeded; PR #75 merged through S5-REL-029 at durable main `4713b797c53121f24cb70171926318d575b7fcc8`; exact-main CI `33156199625` succeeded | Checkpoint A, B, C, and Durable Integration Gates: `PASS_WITH_CONSTRAINTS`; Human Close Confirmation: `PENDING / NO` | implementation/evidence: `GIT_NATIVE / PR_NATIVE / VALIDATED`; integration: `PR_NATIVE / HUMAN_CONFIRMED`; lifecycle reconciliation: `FORWARD_RECORDED_BY_S5_REL_029` | Human S5-IMPL-015 Close Confirmation; do not start downstream work |
| S5-PLAN-003 | v0.2 Product Intent and Golden Demo Portfolio Rebaseline / PLAN | `CLOSED / COMPLETED`; Human-confirmed terminal closure; reopen prohibited | `PASS_WITH_CONSTRAINTS / SESSION_CLOSED`; planning authority only; closure does not authorize downstream work by itself | PR #74 merged at durable main `05bac769b61f42aa5643a8496861e8e962c6bf5b`; exact-main CI run `33145152123` succeeded; ten logical packages retain critical path `1 → 2 → (3 || 4) → 5 → 6A → 7 → 8 → 9`; optional 6B requires separate G2 | Human Portfolio, Review, Merge, and Close decisions: `AUTHORIZED_WITH_CONSTRAINTS / AUTHORIZED_WITH_CONSTRAINTS / PASS / PASS_WITH_CONSTRAINTS` | closure: `HUMAN_CONFIRMED`; merge/CI/content: `PR_NATIVE / REPOSITORY_NATIVE`; terminal addendum: `FORWARD_RECORDED_BY_S5_IMPL_015` | None; reopen prohibited |
| S5-ARCH-012 | User Intervention, Preference, Feedback and Governed Optimization Boundary / ARCH | `CLOSED / COMPLETED`; Human-confirmed terminal closure; reopen prohibited | `PASS_WITH_CONSTRAINTS / SESSION_CLOSED`; architecture decision only; implementation not started | PR #73 merged at durable main `329da75d802886300a6f721c0205d1e5b23c2074`; exact-main CI run `33139763263` succeeded; Governed Successor and Cold Optimization Boundary; v0.2 preference/candidate preview remains `DRAFT / NOT_APPLIED`; no public API, CRD, Graph, dependency, Workflow, Knowledge implementation, Demo, Runtime, Recovery, Certification, or Release change | Human Architecture, Review, Merge, and Close decisions: `APPROVED_WITH_CONSTRAINTS / APPROVED_WITH_CONSTRAINTS / PASS / PASS_WITH_CONSTRAINTS` | closure: `HUMAN_CONFIRMED`; merge/CI/content: `PR_NATIVE / REPOSITORY_NATIVE`; terminal addendum: `FORWARD_RECORDED_BY_S5_PLAN_003` | None; reopen prohibited |
| S5-ARCH-011 | Product Intent, Dynamic Work Composition, Role and Knowledge Consumption Boundary / ARCH | `CLOSED / COMPLETED`; Human-confirmed terminal closure; reopen prohibited | `PASS_WITH_CONSTRAINTS / SESSION_CLOSED`; architecture decision only; implementation was not started by this Session | PR #72 merged at durable main `0ea21ab628561f2e1e5e1a08651e9ef5a9b8fc79`; exact-main CI run `33083580433` succeeded; exactly five architecture/evidence/governance paths plus one bounded linear safety correction; no public API, CRD, Graph, dependency, Workflow, Portfolio, Demo, Runtime, MCP, Knowledge implementation, Recovery, Certification, or Release change | Human Architecture, Review, Merge, and Close decisions: `APPROVED_WITH_CONSTRAINTS / APPROVED_WITH_CONSTRAINTS / PASS / PASS_WITH_CONSTRAINTS` | closure and decisions: `HUMAN_CONFIRMED`; merge/CI/content: `PR_NATIVE / REPOSITORY_NATIVE` | None; reopen prohibited |
| S5-REL-028 | Native Evidence and Shared Read Model Durable Integration / REL | `CLOSED / COMPLETED`; Human-confirmed terminal closure; reopen prohibited | `PASS_WITH_CONSTRAINTS / SESSION_CLOSED`; closure does not grant production certification or release acceptance | Durable merge `a0d82be4387f5706129ee6676ad5965b42a3efdb`; PR #70 and PR #71 merged; exact-main CI run `33072486290` succeeded; corrected P1 boundaries are Workflow/Task UID binding, independent Evidence/Citation authorization, verbatim Canonical Graph relations with no frontend-minted canonical IDs, and terminal semantic completeness with contiguous non-terminal evidence classified partial | Human Integration Review, Merge, and Close decisions: `APPROVED_WITH_CONSTRAINTS / PASS / PASS_WITH_CONSTRAINTS` | closure: `HUMAN_CONFIRMED`; merge/evidence: `PR_NATIVE / REPOSITORY_NATIVE` | None; reopen prohibited |
| S5-IMPL-014 | Native Execution Evidence and Shared Read Model / IMPL | `CLOSED / COMPLETED`; Human-confirmed terminal closure; reopen prohibited | `PASS_WITH_CONSTRAINTS / SESSION_CLOSED`; closure does not grant durable-main integration, production certification, or release acceptance | Baseline `13bc16f746a58912bc093ff249ff390250ce20cf`; branch `codex/s5-impl-014-native-evidence-shared-read-model`; source head `443214c0a0277473648f68800ad008f981d758c9`; Draft PR #70; exact 29-path scope; exact-head CI run `33065548477` succeeded with 726 tests recorded | Human implementation, scope, review, and close decisions: `APPROVED_WITH_CONSTRAINTS / PASS_WITH_CONSTRAINTS`; closure: `PASS_WITH_CONSTRAINTS` | closure and decisions: `HUMAN_CONFIRMED`; implementation/evidence: `REPOSITORY_NATIVE`; PR/CI: `PR_NATIVE` | None; reopen prohibited; integration is owned only by S5-REL-028 |
| S5-ARCH-010 | Production Execution Evidence and Shared Read Model Boundary / ARCH | `CLOSED / COMPLETED`; Human-confirmed terminal closure; reopen prohibited | `PASS_WITH_CONSTRAINTS / SESSION_CLOSED`; bounded v0.2 architecture decision; implementation authorization remained separate | PR #69 merged at durable main `13bc16f746a58912bc093ff249ff390250ce20cf`; exact-main CI run `33049808981` succeeded; Hybrid F and bounded single-node SQLite direction; no production certification, multi-node, Recovery, exactly-once, Golden Demo, or release claim | Human Architecture, G2, Review, Merge, and Close decisions: `PASS_WITH_CONSTRAINTS / APPROVED_FOR_BOUNDED_V0_2_ARCHITECTURE_ONLY / PASS_WITH_CONSTRAINTS / PASS / PASS_WITH_CONSTRAINTS` | closure: `HUMAN_CONFIRMED`; merge/CI/content: `PR_NATIVE / REPOSITORY_NATIVE`; terminal addendum: `FORWARD_RECORDED_BY_S5_PLAN_003` | None; reopen prohibited |
| S5-REL-027 | Portfolio and Governance State Reconciliation / REL | `CLOSED / COMPLETED`; Human-confirmed terminal closure; reopen prohibited | `PASS_WITH_CONSTRAINTS / SESSION_CLOSED`; durable pre-close row was expected terminal snapshot lag | PR #68 merged into durable main `4d5da13e519627ba40cfdc632e3662f5cf965626`; exact-main CI run `33046211942` succeeded; no downstream task was activated by closure | Human Portfolio Sequence, Review, Merge, and Close decisions: `PASS_WITH_CONSTRAINTS / PASS_WITH_CONSTRAINTS / PASS / PASS_WITH_CONSTRAINTS` | closure: `HUMAN_CONFIRMED`; merge/CI: `PR_NATIVE / REPOSITORY_NATIVE`; forward import: `S5-ARCH-010` | None; reopen prohibited |
| S5-REL-026 | Technical View Durable Integration / REL | `CLOSED / COMPLETED` | `PASS_WITH_CONSTRAINTS / SESSION_CLOSED`; Human-allocated REL ID | Source S5-IMPL-011 head `c9cd70108bb3b1bd77458d5340a63a41443b84c9`; PR #66 merged automatically through durable integration; PR #67 merged; durable-main merge `b244fa5da3e670fa754278a0559da1a3049fb05a`; exact-main CI run `33042871796` succeeded | Human Naming, Implementation, Review, Merge, and Close decisions: `PASS / PASS_WITH_CONSTRAINTS / PASS_WITH_CONSTRAINTS / PASS / PASS_WITH_CONSTRAINTS` | closure: `HUMAN_CONFIRMED`; PRs/merge/CI: `PR_NATIVE / REPOSITORY_NATIVE`; state reconciliation: `DERIVED` | None; reopen prohibited |
| S5-IMPL-011 | Technical View / IMPL | `CLOSED / COMPLETED` | `PASS_WITH_CONSTRAINTS / SESSION_CLOSED`; closure does not imply Product MVS completion, Golden Demo readiness, or release readiness | Branch `codex/s5-impl-011-technical-view`; source head `c9cd70108bb3b1bd77458d5340a63a41443b84c9`; PR #66 merged automatically as part of durable-main merge `b244fa5da3e670fa754278a0559da1a3049fb05a`; exact-main CI run `33042871796` succeeded | Human Technical View Review and Close decisions: `PASS_WITH_CONSTRAINTS / PASS` | closure: `HUMAN_CONFIRMED`; PR/merge/CI: `PR_NATIVE / REPOSITORY_NATIVE`; integration conclusion: `DERIVED` | None; reopen prohibited |
| S5-REL-025 | Product View Durable Integration / REL | `CLOSED / COMPLETED` | `PASS_WITH_CONSTRAINTS / SESSION_CLOSED`; Human-allocated REL ID | Source S5-IMPL-010 head `18fa8f9a0eb5caef18772063c28c8fd414d6959f`; PR #64 merged automatically through durable integration; PR #65 merged; durable-main merge `4d23f76e6f8a1afa1ada45ac8ac3fb379aa811f9`; exact-main CI run `33036620588` succeeded | Human Implementation, Review, Merge, and Close decisions: `PASS_WITH_CONSTRAINTS / PASS_WITH_CONSTRAINTS / PASS / PASS_WITH_CONSTRAINTS` | closure: `HUMAN_CONFIRMED`; PRs/merge/CI: `PR_NATIVE / REPOSITORY_NATIVE`; state reconciliation: `DERIVED` | None; reopen prohibited |
| S5-IMPL-010 | Product View / IMPL | `CLOSED / COMPLETED` | `PASS_WITH_CONSTRAINTS / SESSION_CLOSED`; closure does not imply Product MVS completion, Golden Demo readiness, or release readiness | Branch `codex/s5-impl-010-product-view`; source head `18fa8f9a0eb5caef18772063c28c8fd414d6959f`; PR #64 merged automatically as part of durable-main merge `4d23f76e6f8a1afa1ada45ac8ac3fb379aa811f9`; exact-main CI run `33036620588` succeeded | Human Product View Review and Close decisions: `PASS_WITH_CONSTRAINTS / PASS` | closure: `HUMAN_CONFIRMED`; PR/merge/CI: `PR_NATIVE / REPOSITORY_NATIVE`; integration conclusion: `DERIVED` | None; reopen prohibited |
| S5-PLAN-002 | Harness & Parallel Delivery Readiness Plan / PLAN | `CLOSING / AUTHORIZED` | `PASS_WITH_CONSTRAINTS / READY_TO_CLOSE`; plan complete for Human Close Confirmation; Pilot recommended only, not active or authorized | Source: closed S5-REL-017; baseline `7c1bc0266b39c913497fd67dcd4b7783f288dc57`; branch `codex/s5-plan-002-harness-parallel-readiness`; isolated worktree; Draft PR #56 | Harness & Parallel Readiness Review Gate: `PASS_WITH_CONSTRAINTS`; Human Close Confirmation: `PENDING`; future Pilot ID requires separate Human selection | `HUMAN_CONFIRMED / REPOSITORY_NATIVE / PR_NATIVE` | Human S5-PLAN-002 Close Confirmation |
| S5-ARCH-005 | v0.2 Core Schema Draft & Compatibility Map / ARCH | `CLOSED / COMPLETED` | `PASS / SESSION_CLOSED` | Source: S5-ARCH-004; branch `codex/s5-arch-005-core-schema-draft`; PR #42; source head `771929705093ff14e444faa508229a84c929d2e7` | Final Schema Candidate Gate and Close Confirmation: `PASS_WITH_CONSTRAINTS / PASS` | `REPOSITORY_NATIVE / PR_NATIVE` | None; reopen prohibited |
| S5-REL-004 | Core Schema Candidate Integration / REL | `CLOSED / COMPLETED` | `PASS / SESSION_CLOSED` | Source: S5-ARCH-005; PR #42; merge `71e0f682c015b49f7afed6e21988c94a080f2450` | Merge Gate, Closeout Authorization, Close Confirmation: `PASS` | Closure: `HUMAN_CONFIRMED`; merge: `PR_NATIVE / REPOSITORY_NATIVE` | None; reopen prohibited |
| S5-GOV-001 | Project Source of Truth & Release Governance Foundation / GOV | `CLOSED / COMPLETED` | `PASS / SESSION_CLOSED`; Checkpoint C — Session Finalization; reopen prohibited | Source: S5-REL-004; branch `codex/s5-gov-001-release-governance`; isolated worktree; Draft PR #43; commit recorded in Git/PR | Checkpoint A: `PASS_WITH_CONSTRAINTS`; Checkpoint B: `PASS_WITH_CONSTRAINTS` with CI satisfied; Human Close Confirmation: `PASS` | `HUMAN_CONFIRMED / REPOSITORY_NATIVE / PR_NATIVE` | None; reopen prohibited |
| S5-REL-005 | Project Governance Baseline Integration / REL | `CLOSED / COMPLETED` | `PASS / SESSION_CLOSED`; Checkpoint C — Session Closeout; reopen prohibited | Source: S5-GOV-001; PR #43; source head `71739cdcf035fd404176519d2df9975a9a781229`; merge and durable main `acbad19a8af7e0b3762007ba708a90ed0be53d07` | Merge Gate, Closeout Authorization, Close Confirmation: `PASS` | `HUMAN_CONFIRMED_GIT_VERIFIED`; import method: `FORWARD_IMPORTED_BY_S5_ARCH_006` | None; reopen prohibited |
| S5-ARCH-006 | v0.2 Digital Employee Golden Demo Scope & Acceptance Contract / ARCH | `CLOSED / COMPLETED` | `PASS / SESSION_CLOSED`; Checkpoint B — Final Scope Convergence and Implementation Handoff; reopen prohibited | Source: S5-ARCH-005, S5-REL-004, S5-GOV-001, S5-REL-005; branch `codex/s5-arch-006-digital-employee-demo`; Draft PR #44 | Golden Demo Scope Gate: `PASS_WITH_CONSTRAINTS`; G07 Provider support: `ACCEPTED_AS_V0_2_PROVIDER_POLICY`; G08 deployment/assets: `ACCEPTED_AS_V0_2_DEPLOYMENT_AND_ASSET_POLICY`; Human Close Confirmation: `PASS` | `HUMAN_CONFIRMED / PR_NATIVE` | Recommended only: S5-REL-006 Golden Demo Scope Integration; not active or authorized |
| S5-REL-006 | Golden Demo Scope Integration / REL | `CLOSED / COMPLETED` | `PASS / SESSION_CLOSED`; reopen prohibited | Source: S5-ARCH-006; source PR #44; merge and durable main `df2a56d48c21e4e74b6fb1d94f39cb2f07894aa9` | Merge Gate, Closeout Authorization, Close Confirmation: `PASS` | `HUMAN_CONFIRMED_GIT_VERIFIED`; import method: `FORWARD_IMPORTED_BY_S5_PLAN_001` | None; reopen prohibited |
| S5-PLAN-001 | v0.2 Implementation Portfolio & Release Execution Plan / PLAN | `CLOSED / COMPLETED`; Human-confirmed terminal closure; reopen prohibited | `PASS / SESSION_CLOSED`; retained as historical authority for completed work; S5-PLAN-003 partially supersedes only its unstarted remaining v0.2 sequence, Golden Demo route, and release-readiness route | Source: S5-ARCH-005, S5-GOV-001, S5-ARCH-006, S5-REL-006; branch `codex/s5-plan-001-v0-2-implementation-portfolio`; PR #45; merge `040f324359c6db16ee52c55b8f367d1cc4157de9`; bounded forward-navigation addendum only | Checkpoint A and Implementation Entry Gates: `PASS_WITH_CONSTRAINTS`; Human Close Confirmation: `PASS`; S5-PLAN-003 Portfolio Decision: `AUTHORIZED_WITH_CONSTRAINTS` | `HUMAN_CONFIRMED_GIT_VERIFIED / PR_NATIVE / REPOSITORY_NATIVE`; partial supersession: `FORWARD_RECORDED` | S5-PLAN-003 owns only the rebaselined unstarted route; S5-PLAN-001 remains closed |
| S5-REL-007 | Implementation Portfolio Integration / REL | `CLOSED / COMPLETED` | `PASS / SESSION_CLOSED`; reopen prohibited | Source: S5-PLAN-001; PR #45; merge and durable main `040f324359c6db16ee52c55b8f367d1cc4157de9` | Merge Gate, Closeout Authorization, Close Confirmation: `PASS` | `HUMAN_CONFIRMED_GIT_VERIFIED`; import method: `FORWARD_IMPORTED_BY_S5_ARCH_007` | None; reopen prohibited |
| S5-ARCH-007 | v0.2 Core Representation & API Gate / ARCH | `CLOSING / AUTHORIZED` | `PASS / READY_TO_CLOSE`; Checkpoint B — Final G2 Convergence and A1 Handoff | Source: S5-ARCH-005, S5-ARCH-006, S5-PLAN-001, S5-REL-007; baseline `040f324359c6db16ee52c55b8f367d1cc4157de9`; branch `codex/s5-arch-007-core-representation-api-gate`; Draft PR #46 | Human G2 Representation/API Gate: `PASS_WITH_CONSTRAINTS`; R3 accepted for bounded A1; G2-01–G2-12 dispositioned; Human Close Confirmation: `PENDING`; A1 inactive/unauthorized | `HUMAN_CONFIRMED / REPOSITORY_NATIVE / PR_NATIVE` | Human S5-ARCH-007 Close Confirmation |
| S5-REL-010 | A2 Identity Spine Integration / REL | `CLOSED / COMPLETED` | `PASS / SESSION_CLOSED`; Checkpoint C — Session Closeout; reopen prohibited | Source: S5-IMPL-002; PR #48; source head `e3e4d10711e6d89be2bfd9b9d383a89c19ff3c0d`; merge and durable main `a630db68daf29778cedcb8e3826f73d1802c49f0` | Merge Gate, Closeout Authorization, Close Confirmation: `PASS` | `HUMAN_CONFIRMED_GIT_VERIFIED`; import method: `FORWARD_IMPORTED_BY_S5_IMPL_003` | None; reopen prohibited |

S5-REL-004 closure was not previously repository-native. Its Registry entry is
an explicit import of Human-confirmed closure; PR #42 and its merge commit are
independently Git/PR-native.

S5-REL-005 final closure occurred after it merged the governance baseline and
therefore could not be recorded recursively in its own source PR. S5-ARCH-006
forward-imported the exact Human-confirmed and Git-verified historical state;
S5-REL-005 remains closed and is not reopened.

S5-REL-006 final closure likewise occurred after its source PR merged. This
Registry forward-import records the Human-confirmed closure against the
Git-verified PR #44 merge without reopening S5-REL-006 or creating a recursive
closeout PR.

S5-REL-007 final closure occurred after PR #45 durably integrated the accepted
Portfolio. S5-ARCH-007 forward-imports the Human-confirmed and Git-verified
closure without reopening S5-REL-007 or creating a recursive closeout PR.

S5-REL-010 final closure occurred after PR #48 durably integrated the A2
Identity Spine. S5-IMPL-003 forward-imports the Human-confirmed and
Git-verified closure without reopening S5-REL-010 or creating a recursive
closeout PR.

## Human and Open Decision Index

| Subject | State | Durable scope / source |
| --- | --- | --- |
| v0.2 Core Schema Candidate v0 | `ACCEPTED_WITH_EVIDENCE_DEBT` | [Final Candidate Gate](../../S5-ARCH-005-CORE-SCHEMA-DRAFT-V1.md#107-human-final-schema-candidate-gate) |
| Five logical resources | `ACCEPTED_WITH_EVIDENCE_DEBT` | Logical Candidate only; five CRDs are not authorized or approved |
| Option B compatibility direction | `ACCEPTED_WITH_EVIDENCE_DEBT` | Additive compatibility direction; representation, migration, and conformance remain debt |
| Platform Execution Identity | `ACCEPTED_WITH_EVIDENCE_DEBT` | Embedded Core value; serialization and propagation conformance remain debt |
| S5-ARCH-010 execution evidence/read model | `ACCEPTED_WITH_EVIDENCE_DEBT` | Hybrid F and bounded single-node SQLite direction approved for architecture only; implementation, persistence/security proof, DTO/API compatibility, production certification, multi-node operation, and exactly-once claims remain ungranted |
| S5-ARCH-007 prototype representation | `ACCEPTED_WITH_EVIDENCE_DEBT` | R3 internal-first representation accepted for bounded A1; no public API/CRD/schema authorization; future public form deferred |
| Runtime and Capability Bindings | `ACCEPTED_WITH_EVIDENCE_DEBT` | Embedded boundaries |
| Model Binding | `ACCEPTED_WITH_EVIDENCE_DEBT` | Thin embedded foundation; routing remains deferred |
| Final v0.2 Demo scenario | `PENDING` | Engineering Release Risk Manager is durable direction; After-Sales Service Expert is proposed; neither is final |
| Final product brand | `PENDING` | Enterprise Agent Platform is durable identity; “Agent OS” is not final brand approval |
| Simplified v0.1/v0.2/v0.5/v0.9/v1.0 sequence | `PROPOSED` | `NOT_APPROVED / OPEN`; [approved roadmap](../../ROADMAP.md) remains authoritative |
| Open-core and commercial packaging | `PENDING` | `OPEN`; no approved boundary or packaging decision |
| Current repository license | `ACCEPTED` | Apache-2.0 in `LICENSE`, README, and project metadata |
| Provider certification | `BLOCKED` | `NOT_GRANTED`; combination-scoped evidence required |
| Core Schema, Runtime Contract, Capability Contract freezes | `BLOCKED` | `NOT_GRANTED / NOT_FROZEN`; independent gates remain unsatisfied |

## Evidence Debt Index

Evidence Debt is claim-scoped. An indexed item is not automatically a v0.2
release blocker. Only ED-S5-001 has an existing durable Evidence Debt ID; all
other items remain unnumbered until an authorized Session assigns one.

### Assigned Evidence Debt

| ID | Source | State | Affected claim/gate | Blocker scope | Owner / target Session |
| --- | --- | --- | --- | --- | --- |
| ED-S5-001 | [Hermes evidence](../evidence/s5/runtime/hermes/evidence/evidence-debt.md), [Candidate debt map](../../S5-ARCH-005-CORE-SCHEMA-DRAFT-V1.md#95-claim-scoped-evidence-debt) | `NOT_YET_PROVEN / OPEN` | Hermes Provider/package certification and readiness | Blocks applicable Hermes certification/readiness only; does not block Core Candidate or Native/OpenClaw schema path | `UNASSIGNED / UNASSIGNED` |

### UNASSIGNED_EVIDENCE_DEBT

| Category | Source | Current state | Affected claim or gate / supported blocker scope | Owner / target Session |
| --- | --- | --- | --- | --- |
| Serialization and API representation | [Candidate Sections 94–95](../../S5-ARCH-005-CORE-SCHEMA-DRAFT-V1.md#94-candidate-stability-classification) | `NOT_YET_PROVEN` | Blocks normative schema/API/persistence and freeze claims | `UNASSIGNED / UNASSIGNED` |
| Identity mapping and backfill | Same Candidate debt map | `NOT_YET_PROVEN` | Blocks migration/API approval; not Definition/Instance distinction | `UNASSIGNED / UNASSIGNED` |
| Translation losslessness | Same Candidate debt map | `NOT_YET_PROVEN` | Blocks legacy adoption/fallback claims | `UNASSIGNED / UNASSIGNED` |
| Routing and mixed-version behavior | Same Candidate debt map | `NOT_YET_PROVEN` | Blocks routing vocabulary, migration, and cutover readiness | `UNASSIGNED / UNASSIGNED` |
| Conditions and Outcomes vocabulary | Same Candidate debt map | `NOT_YET_PROVEN` | Blocks exact serialization, reasons, and taxonomy freeze | `UNASSIGNED / UNASSIGNED` |
| Recovery semantics and thresholds | Same Candidate debt map | `NOT_YET_PROVEN` | Blocks vocabulary freeze and production recovery claims | `UNASSIGNED / UNASSIGNED` |
| Runtime Provider conformance | Same Candidate debt map | `NOT_YET_PROVEN` | Blocks Runtime Contract freeze and combination certification | `UNASSIGNED / UNASSIGNED` |
| Capability Provider conformance | Same Candidate debt map | `NOT_YET_PROVEN` | Blocks Capability Contract freeze and broad Provider claims | `UNASSIGNED / UNASSIGNED` |
| Console tolerance | Same Candidate debt map | `NOT_YET_PROVEN` | Blocks additive old-client compatibility claim | `UNASSIGNED / UNASSIGNED` |
| Side effects and deferred execution | Same Candidate debt map | `NOT_YET_PROVEN` | Blocks safe replay/idempotency and durable deferred-execution claims | `UNASSIGNED / UNASSIGNED` |
| Third-party MCP | [Capability evidence](../evidence/s5/capability-contract/S5-SPIKE-003-CLOSEOUT.md) | `NOT_YET_PROVEN` | Blocks certification or broad third-party MCP claim only | `UNASSIGNED / UNASSIGNED` |
| State portability | Candidate debt map | `DEFERRED` | Blocks portability/continuity claim; not thin State reference | `UNASSIGNED / UNASSIGNED` |
| Model routing | Candidate debt map | `DEFERRED` | Blocks Model Contract/routing schema; not thin Model Binding | `UNASSIGNED / UNASSIGNED` |
| Multi-tenancy | Candidate debt map | `DEFERRED` | Blocks tenant-isolation/enterprise-production claim | `UNASSIGNED / UNASSIGNED` |

## ADR Drift Index

ADR files remain unchanged. Source defines current behavior; accepted ADRs
define approved architecture until explicitly amended or superseded.

| ADR | Follow-up state | Recorded drift / architecture evidence |
| --- | --- | --- |
| [ADR-0003](../../adr/ADR-0003.md) | `CLARIFY_LATER` | Task execution and Workflow orchestration currently reside under the Operator package; see [Candidate ADR impact](../../S5-ARCH-005-CORE-SCHEMA-DRAFT-V1.md#112-adr-impact-finalization) |
| [ADR-0004](../../adr/ADR-0004.md) | `AMEND_LATER` | Accepted Runtime Provider/Binding direction differs from the original RuntimeClass/Adapter boundary; amendment requires a separate Human decision |
| [ADR-0005](../../adr/ADR-0005.md) | `CLARIFY_LATER` | Thin Model Binding is accepted as Candidate foundation while platform-level Model routing remains deferred |

## Registry update rules

- A Session owner updates its row at authorization and each lifecycle Gate.
- A REL integration Session verifies merged provenance and durable current state.
- Human decisions and debt changes update their indexes without rewriting
  historical artifacts.
- Daily start/closeout records link Registry changes and preserve before/after
  durable-main SHAs; see [exec-plan conventions](../exec-plans/README.md).
