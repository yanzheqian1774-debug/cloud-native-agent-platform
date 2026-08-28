# Current Project State

This is a derived operational snapshot. It does not replace source and tests
for implemented behavior, accepted ADRs and architecture evidence for approved
architecture, `PRODUCT.md` for product intent, or `ROADMAP.md` for approved
sequencing. Update it when a Session lifecycle, Human Gate, blocker, release
objective, or durable-main integration changes.

## Project identity

- Repository: `cloud-native-agent-platform`
- Durable product identity: **Enterprise Agent Platform**
- Final product brand: **OPEN**
- “Agent OS” is not an approved final brand.
- `agentos.io` is the current Kubernetes API group, not brand approval.
- Current repository license: **Apache-2.0**.

## Version and baseline

- Latest published release: **v0.1.0-alpha**
- Current development objective: **v0.2 CONNECT — Digital Employee Technical Preview**
- Objective classification: `WORKING_RELEASE_OBJECTIVE`
- v0.2 release acceptance: `NOT_GRANTED`
- v0.2 production readiness: `NOT_GRANTED`
- Current durable-main head: `8757adabc9a95e3b3934303fa9c6f8586ff854e9`
- Exact-main CI: run `33180601090`, `SUCCESS`
- S5-PLAN-003 authorized durable-main baseline:
  `05bac769b61f42aa5643a8496861e8e962c6bf5b`
- S5-PLAN-002 authorized durable-main baseline:
  `7c1bc0266b39c913497fd67dcd4b7783f288dc57`
- S5-GOV-001 starting durable-main SHA:
  `71e0f682c015b49f7afed6e21988c94a080f2450`

The SHA above is the immutable starting baseline for S5-GOV-001, not a promise
that `main` will never advance. The [Governance Registry](docs/governance/REGISTRY.md)
records lifecycle and provenance.

## Session state

| Session | Current state | Durable basis |
| --- | --- | --- |
| S5-REL-030 | `HUMAN_CONFIRMED_CLOSED / COMPLETED / PASS_WITH_CONSTRAINTS / SESSION_CLOSED` | PR #78 merged at durable main `8757adabc9a95e3b3934303fa9c6f8586ff854e9` with ordered parents `7bb4c43e03d86259373b9fc5ae79fbcb3c1234c6` and `0993a03817123d9565c8fd03d00dd8fa7e2e0d5f`; exact-main CI run `33180601090` succeeded; closure is forward-recorded without reopening; no downstream authority was granted by closure |
| S5-ARCH-013 | `HUMAN_CONFIRMED_CLOSED / COMPLETED / PASS_WITH_CONSTRAINTS / SESSION_CLOSED` | Source head `a8ae79574a4c16e646cb33adb7026d1a97d4af8f`; PR #77 merged through S5-REL-030 and reconciled at durable main `8757adabc9a95e3b3934303fa9c6f8586ff854e9`; exact-main CI run `33180601090` succeeded; closure is forward-recorded without reopening |
| S5-IMPL-030 | `ACTIVE / IMPLEMENTATION_COMPLETE / REVIEW_READY / AWAITING_DURABLE_INTEGRATION / UNMERGED` | Exact baseline `8757adabc9a95e3b3934303fa9c6f8586ff854e9`; branch `codex/s5-impl-030-curated-descriptor-published-role-matcher`; bounded internal Definition authority and advisory published-role matcher validated in exactly seven authorized paths; terminal commit, Draft PR, and exact-head CI are reported in PR/CONTROL Evidence; merge, Durable Integration, closure, Package 3, REL, and downstream work remain unauthorized |
| S5-REL-029 | `ACTIVE / DURABLE_INTEGRATION_COMPLETE / RECONCILIATION_PREPARED / AWAITING_RECONCILIATION_INTEGRATION_AND_HUMAN_CLOSE_CONFIRMATION` | S5-IMPL-015 PR #75 merged as `4713b797c53121f24cb70171926318d575b7fcc8` with ordered parents `05bac769b61f42aa5643a8496861e8e962c6bf5b` and `fbfd3889b587af08b991525a5abda2b4f994562c`; exact-main CI run `33156199625` succeeded; this governance reconciliation remains unmerged and Human Close Confirmation is `NO` |
| S5-IMPL-015 | `ACTIVE / IMPLEMENTATION_COMPLETE / CHECKPOINT_C_PASS_WITH_CONSTRAINTS / DURABLY_INTEGRATED / AWAITING_HUMAN_CLOSE_CONFIRMATION` | Package 1 source commits `388c37b4ecdf22502f1578fb470d0b40ac048891` and `fbfd3889b587af08b991525a5abda2b4f994562c`; exact-head CI run `33153148233` succeeded; PR #75 merged through S5-REL-029 at durable main `4713b797c53121f24cb70171926318d575b7fcc8`; exact-main CI run `33156199625` succeeded; Session closure is not granted and no downstream Package, Demo, or Release authority exists |
| S5-PLAN-003 | `HUMAN_CONFIRMED_CLOSED / COMPLETED / PASS_WITH_CONSTRAINTS / SESSION_CLOSED` | PR #74 merged at durable main `05bac769b61f42aa5643a8496861e8e962c6bf5b`; exact-main CI run `33145152123` succeeded; terminal closure is forward-recorded without reopening; ten logical packages retain mandatory critical path `1 → 2 → (3 || 4) → 5 → 6A → 7 → 8 → 9`; optional Package 6B still requires a separate G2; closure did not itself start or allocate downstream implementation |
| S5-ARCH-012 | `HUMAN_CONFIRMED_CLOSED / COMPLETED / PASS_WITH_CONSTRAINTS / SESSION_CLOSED` | PR #73 merged at durable main `329da75d802886300a6f721c0205d1e5b23c2074`; exact-main CI run `33139763263` succeeded; closure is forward-recorded without reopening; preference/candidate scope remains preview-only and `DRAFT / NOT_APPLIED`; no implementation was authorized by the Session |
| S5-ARCH-011 | `HUMAN_CONFIRMED_CLOSED / COMPLETED / PASS_WITH_CONSTRAINTS / SESSION_CLOSED` | PR #72 merged at durable main `0ea21ab628561f2e1e5e1a08651e9ef5a9b8fc79`; exact-main CI run `33083580433` succeeded; exactly five architecture/evidence/governance paths plus one bounded linear safety correction; closure is forward-recorded without reopening; no implementation was authorized by the Session |
| S5-REL-028 | `HUMAN_CONFIRMED_CLOSED / COMPLETED / PASS_WITH_CONSTRAINTS / SESSION_CLOSED` | PR #70 and PR #71 merged at durable main `a0d82be4387f5706129ee6676ad5965b42a3efdb`; exact-main CI run `33072486290` succeeded; terminal pre-close row was expected governance lag; reopen prohibited |
| S5-IMPL-014 | `HUMAN_CONFIRMED_CLOSED / COMPLETED / PASS_WITH_CONSTRAINTS / SESSION_CLOSED` | Native-only source head `443214c0a0277473648f68800ad008f981d758c9` on Draft PR #70; exact 29-path scope and CI run `33065548477` succeeded with 726 tests recorded; corrected P1 boundaries are Workflow/Task UID binding, independently authorized references, verbatim Canonical Graph relations/no frontend canonical IDs, and terminal semantic completeness; bounded single-node SQLite and internal Technical Preview only |
| S5-ARCH-010 | `HUMAN_CONFIRMED_CLOSED / COMPLETED / PASS_WITH_CONSTRAINTS / SESSION_CLOSED` | PR #69 merged at durable main `13bc16f746a58912bc093ff249ff390250ce20cf`; exact-main CI run `33049808981` succeeded; closure is forward-recorded without reopening; bounded Hybrid F architecture does not grant production persistence, multi-node, Recovery, exactly-once, Golden Demo, or release claims |
| S5-REL-027 | `HUMAN_CONFIRMED_CLOSED / COMPLETED / PASS_WITH_CONSTRAINTS / SESSION_CLOSED` | PR #68 merged into durable main `4d5da13e519627ba40cfdc632e3662f5cf965626`; exact-main CI `33046211942` succeeded; the prior pre-close row was expected terminal snapshot lag; reopen prohibited |
| S5-REL-026 | `HUMAN_CONFIRMED_CLOSED / COMPLETED / PASS_WITH_CONSTRAINTS` | Technical source head `c9cd70108bb3b1bd77458d5340a63a41443b84c9`; PRs #66 and #67 merged; durable-main merge `b244fa5da3e670fa754278a0559da1a3049fb05a`; exact-main CI `33042871796` succeeded |
| S5-IMPL-011 | `HUMAN_CONFIRMED_CLOSED / COMPLETED / PASS_WITH_CONSTRAINTS` | Technical source head `c9cd70108bb3b1bd77458d5340a63a41443b84c9`; PR #66 merged automatically through Technical View durable integration |
| S5-REL-025 | `HUMAN_CONFIRMED_CLOSED / COMPLETED / PASS_WITH_CONSTRAINTS` | Product source head `18fa8f9a0eb5caef18772063c28c8fd414d6959f`; PRs #64 and #65 merged; durable-main merge `4d23f76e6f8a1afa1ada45ac8ac3fb379aa811f9`; exact-main CI `33036620588` succeeded |
| S5-IMPL-010 | `HUMAN_CONFIRMED_CLOSED / COMPLETED / PASS_WITH_CONSTRAINTS` | Product source head `18fa8f9a0eb5caef18772063c28c8fd414d6959f`; PR #64 merged automatically through Product View durable integration |
| S5-PLAN-002 | `CLOSING / AUTHORIZED / PASS_WITH_CONSTRAINTS / READY_TO_CLOSE` | Checkpoint B plan convergence complete at exact baseline `7c1bc0266b39c913497fd67dcd4b7783f288dc57`; Pilot is recommended only and requires a separately allocated `TEST` Session and Human authorization; downstream Sessions remain inactive; Human Close Confirmation pending |
| S5-ARCH-005 | `CLOSED / COMPLETED / PASS / SESSION_CLOSED` | Accepted Candidate artifact and source head |
| S5-REL-004 | `HUMAN_CONFIRMED_CLOSED / COMPLETED / PASS / SESSION_CLOSED` | PR #42 merge plus imported Human confirmation |
| S5-GOV-001 | `CLOSED / COMPLETED / PASS / SESSION_CLOSED` | Checkpoint C finalization; Checkpoint B Human Gate passed with constraints and CI satisfied; Human Close Confirmation passed; reopen prohibited |
| S5-ARCH-006 | `CLOSED / COMPLETED / PASS / SESSION_CLOSED` | Golden Demo Scope Gate passed with constraints; Human Close Confirmation passed; PR #44 merged at the authorized baseline; reopen prohibited |
| S5-REL-006 | `CLOSED / COMPLETED / PASS / SESSION_CLOSED` | Human-confirmed closure forward-imported by S5-PLAN-001; PR #44 and merge `df2a56d48c21e4e74b6fb1d94f39cb2f07894aa9` Git-verified; reopen prohibited |
| S5-PLAN-001 | `CLOSED / COMPLETED / PASS / SESSION_CLOSED / PARTIALLY_SUPERSEDED_FORWARD` | Human-confirmed closure; PR #45 merged at `040f324359c6db16ee52c55b8f367d1cc4157de9`; retained as historical authority for completed work; S5-PLAN-003 supersedes only its unstarted remaining v0.2 sequence, Golden Demo route, and release-readiness route; reopen prohibited |
| S5-REL-007 | `CLOSED / COMPLETED / PASS / SESSION_CLOSED` | Human-confirmed/Git-verified durable Portfolio integration forward-imported by S5-ARCH-007; reopen prohibited |
| S5-ARCH-007 | `CLOSING / AUTHORIZED / PASS / READY_TO_CLOSE` | Human G2 Representation/API Gate passed with constraints; R3 accepted for bounded A1; G2-01–G2-12 dispositioned; Human Close Confirmation pending; no implementation or public schema/API/CRD change |
| S5-REL-010 | `CLOSED / COMPLETED / PASS / SESSION_CLOSED` | Human-confirmed and Git-verified A2 integration at PR #48 merge `a630db68daf29778cedcb8e3826f73d1802c49f0`; forward-imported by S5-IMPL-003; reopen prohibited |

## Accepted architecture state

The **v0.2 Core Schema Candidate v0 is ACCEPTED**. Its five first-class logical
resource candidates are:

- Agent Definition;
- Agent Instance;
- Task;
- Workflow;
- Capability Definition.

Five logical resources do **not** authorize five CRDs. CRD count and persistence
representation remain `NOT_AUTHORIZED / NOT_APPROVED / UNDECIDED`.

- Runtime Binding: embedded
- Capability Binding: embedded
- Model Binding: thin embedded foundation
- Core Schema Freeze: `NO`
- Runtime Contract Freeze: `NO`
- Capability Contract Freeze: `NO`
- Provider Certification: `NOT_GRANTED`
- Hermes: `EXPERIMENTAL / NOT CURRENTLY CERTIFIABLE`
- ED-S5-001: `OPEN`

## Current release focus

The bounded working objective is to demonstrate Digital Employee construction
and governed execution across the stable Core and external Runtime Providers.
A Digital Employee is a business-facing projection, not a Core CRD.

The accepted primary public Demo candidate is Quality Issue Identification and
Closure Digital Employee. Engineering Release Risk Manager is the accepted
secondary technical/conformance example. Implementation entry is conditionally
granted as a route only; no future Session is active or authorized. Provider
certification, production readiness and release acceptance remain not granted.

Product and Technical Views are both durably integrated. PRs #64 and #65 merged
through Product durable merge `4d23f76e6f8a1afa1ada45ac8ac3fb379aa811f9`;
PRs #66 and #67 merged through Technical durable merge. S5-REL-027 then merged
the governance reconciliation through current main
`4d5da13e519627ba40cfdc632e3662f5cf965626`; exact-main CI run `33046211942`
succeeded, and its Human-confirmed closure is forward-imported here without
reopening it. S5-REL-028 is Human-confirmed closed and its PR #70/PR #71 result
is durable main `a0d82be4387f5706129ee6676ad5965b42a3efdb`; its earlier pre-close row was
expected terminal governance lag and is forward-recorded without reopening it.
S5-ARCH-010, S5-ARCH-011, and S5-ARCH-012 are Human-confirmed closed. Their
accepted architecture is not implementation evidence. S5-PLAN-003 now owns the
bounded supplier-quality Product Intent and Golden Demo Portfolio rebaseline and
is Human-confirmed closed after PR #74 and exact-main CI. Its ten logical packages
retain the accepted sequence. Closure did not itself allocate or authorize any
downstream implementation, integration, test, Demo, Solution, or release Session.
S5-PLAN-002 remains the unrelated Harness & Parallel Delivery Readiness Plan and
is unchanged.

S5-PLAN-003 terminal closure does not establish downstream implementation state.
Golden Demo implementation and Release were not started by that Plan Session. No
Product MVS, Runtime or Provider certification, production Knowledge or recovery
support, Golden Demo readiness, production readiness, or release acceptance is
granted.

S5-IMPL-015 Package 1 is now durably integrated through PR #75 and S5-REL-029 at
main `4713b797c53121f24cb70171926318d575b7fcc8`; exact-main CI run
`33156199625` succeeded. Both S5-IMPL-015 and S5-REL-029 remain active and await
Human Close Confirmation. The S5-REL-029 reconciliation PR must be integrated by
a separate Human Gate. Package 2–4, Golden Demo, Enhanced Golden Demo, and
Release remain unauthorized and have not started.

## Immediate next work

1. Complete the separately gated S5-REL-029 governance reconciliation and Human
   Close Confirmations; do not start downstream work from integration alone.
2. Preserve the model-assisted/untrusted candidate boundary, deterministic
   canonicalization and exact-digest approval, authorization-first matching and
   Knowledge retrieval, Native-only placement, and immutable Evidence/successor
   authorities.
3. Keep Package 6B outside the critical path and behind a separate Human G2
   persistence/privacy/State decision; it remains `PREVIEW / NOT_APPLIED`.
4. Keep all public API, CRD, Graph, Workflow, dependency, production
   integration, certification, readiness, and release decisions under their
   separate Gates.

S5-PLAN-003 recommendations do not allocate or activate future Session IDs.
Historical S5-ARCH-007 and S5-IMPL-001 navigation does not authorize work.

## Source-of-truth links

- [Governance Registry](docs/governance/REGISTRY.md)
- [Product direction](PRODUCT.md)
- [Roadmap](ROADMAP.md)
- [Current implementation](docs/engineering/CURRENT_IMPLEMENTATION.md)
- [Target architecture](ARCHITECTURE.md)
- [ADR index and known drift](adr/README.md)
- [Accepted v0.2 Core Schema Candidate](S5-ARCH-005-CORE-SCHEMA-DRAFT-V1.md)
- [S5 v0.2 architecture evidence](architecture/s5/v0.2/README.md)
- [Latest published release notes](docs/releases/v0.1.0-alpha.md)
- [Exec-plan conventions](docs/exec-plans/README.md)
