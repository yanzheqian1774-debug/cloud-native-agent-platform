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
| S5-ARCH-011 | Product Intent, Dynamic Work Composition, Role and Knowledge Consumption Boundary / ARCH | `REVIEW / AUTHORIZED`; Checkpoint A — Architecture Decision and Boundary Definition | `PASS_WITH_CONSTRAINTS / READY_FOR_HUMAN_S5_ARCH_011_REVIEW_GATE`; architecture candidate only; implementation not started | Durable baseline `a0d82be4387f5706129ee6676ad5965b42a3efdb`; branch `codex/s5-arch-011-product-intent-dynamic-work-role-boundary`; exactly five architecture/evidence/governance paths; bounded supplier-quality domain; no public API, CRD, Graph, dependency, workflow, Portfolio, Demo, Runtime, MCP, Knowledge implementation, Recovery, Certification, or Release change | Human Architecture Decision: `APPROVED_WITH_CONSTRAINTS`; Human Review Gate: `PENDING` | decision and task ID: `HUMAN_CONFIRMED / HUMAN_ALLOCATED`; candidate content: `REPOSITORY_NATIVE / NOT_DURABLE_MAIN`; PR/CI: `PENDING` | Human S5-ARCH-011 Review Gate; no implementation or downstream Session authorized |
| S5-REL-028 | Native Evidence and Shared Read Model Durable Integration / REL | `REVIEW / AUTHORIZED`; Checkpoint A bounded durable integration candidate; candidate is unmerged | `PASS_WITH_CONSTRAINTS / READY_FOR_HUMAN_S5_REL_028_REVIEW_GATE`; no downstream task started | Durable baseline `13bc16f746a58912bc093ff249ff390250ce20cf`; source S5-IMPL-014 head `443214c0a0277473648f68800ad008f981d758c9`, Draft PR #70 and exact 29-path scope; provenance merge `af3dab64deec8a95138a28f7f7dd5c3ce44c6e7f`; corrected P1 boundaries are Workflow/Task UID binding, independent Evidence/Citation authorization, verbatim Canonical Graph relations with no frontend-minted canonical IDs, and terminal semantic completeness with contiguous non-terminal evidence classified partial | Human Integration Implementation Decision: `APPROVED_WITH_CONSTRAINTS`; Human Review Gate: `PENDING` | decision and source closure: `HUMAN_CONFIRMED`; merge/evidence: `REPOSITORY_NATIVE`; source PR/CI: `PR_NATIVE` | Human S5-REL-028 Review Gate; keep both PRs Draft and unmerged; no downstream task |
| S5-IMPL-014 | Native Execution Evidence and Shared Read Model / IMPL | `CLOSED / COMPLETED`; Human-confirmed terminal closure; reopen prohibited | `PASS_WITH_CONSTRAINTS / SESSION_CLOSED`; closure does not grant durable-main integration, production certification, or release acceptance | Baseline `13bc16f746a58912bc093ff249ff390250ce20cf`; branch `codex/s5-impl-014-native-evidence-shared-read-model`; source head `443214c0a0277473648f68800ad008f981d758c9`; Draft PR #70; exact 29-path scope; exact-head CI run `33065548477` succeeded with 726 tests recorded | Human implementation, scope, review, and close decisions: `APPROVED_WITH_CONSTRAINTS / PASS_WITH_CONSTRAINTS`; closure: `PASS_WITH_CONSTRAINTS` | closure and decisions: `HUMAN_CONFIRMED`; implementation/evidence: `REPOSITORY_NATIVE`; PR/CI: `PR_NATIVE` | None; reopen prohibited; integration is owned only by S5-REL-028 |
| S5-ARCH-010 | Production Execution Evidence and Shared Read Model Boundary / ARCH | `CLOSING / AUTHORIZED`; Checkpoint B — Independent Architecture Safety and Merge Readiness; active, not completed | `PASS_WITH_CONSTRAINTS / READY_FOR_HUMAN_S5_ARCH_010_MERGE_GATE`; Human G2 approved bounded v0.2 architecture direction only; candidate is not durable main; implementation not authorized | Baseline `4d5da13e519627ba40cfdc632e3662f5cf965626`; Checkpoint A head `e3766bf5640759b035f740e0cffbe4889b88f995`; Draft PR #69; branch `codex/s5-arch-010-execution-evidence-read-model`; Hybrid F; future bounded single-node SQLite-backed append-only internal repository; exactly five architecture/governance paths; one linear bounded safety correction; implementation task ID unresolved | Human Architecture Decision: `PASS_WITH_CONSTRAINTS`; Human G2: `APPROVED_FOR_BOUNDED_V0_2_ARCHITECTURE_ONLY`; Human Review Gate: `PASS_WITH_CONSTRAINTS`; Human Merge Gate: `PENDING` | decisions and ID: `HUMAN_CONFIRMED / HUMAN_ALLOCATED`; candidate content: `REPOSITORY_NATIVE / NOT_DURABLE_MAIN`; PR/CI: `PR_NATIVE` | Human S5-ARCH-010 Merge Gate; no downstream Session active or authorized |
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
| S5-PLAN-001 | v0.2 Implementation Portfolio & Release Execution Plan / PLAN | `CLOSED / COMPLETED` | `PASS / SESSION_CLOSED`; implementation route conditionally granted, no implementation Session active; reopen prohibited | Source: S5-ARCH-005, S5-GOV-001, S5-ARCH-006, S5-REL-006; branch `codex/s5-plan-001-v0-2-implementation-portfolio`; PR #45; merge `040f324359c6db16ee52c55b8f367d1cc4157de9` | Checkpoint A and Implementation Entry Gates: `PASS_WITH_CONSTRAINTS`; Human Close Confirmation: `PASS` | `HUMAN_CONFIRMED_GIT_VERIFIED / PR_NATIVE / REPOSITORY_NATIVE` | None; reopen prohibited |
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
