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
- Current durable-main head: `4d5da13e519627ba40cfdc632e3662f5cf965626`
- Exact-main CI: run `33046211942`, `SUCCESS`
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
| S5-ARCH-010 | `CLOSING / AUTHORIZED / CHECKPOINT_B / PASS_WITH_CONSTRAINTS / READY_FOR_HUMAN_MERGE_GATE` | Active architecture candidate, not completed, merged, or durable main; Human Review Gate passed with constraints; Draft PR #69 contains Hybrid F and the bounded single-node SQLite direction plus one linear safety clarification; implementation task ID is unresolved and no implementation or downstream Session is authorized |
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
| S5-PLAN-001 | `CLOSED / COMPLETED / PASS / SESSION_CLOSED` | Human-confirmed closure; PR #45 merged at `040f324359c6db16ee52c55b8f367d1cc4157de9`; reopen prohibited |
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
reopening it. S5-ARCH-010 is the active architecture-only Session.
Golden Demo implementation and Release have not started. No Product MVS, Runtime or
Provider certification, production Knowledge or recovery support, Golden Demo
readiness, production readiness, or release acceptance is granted.

## Immediate next work

1. Return Draft PR #69 to the Human S5-ARCH-010 Merge Gate. Keep it Draft and
   unmerged; no implementation or downstream Session is active or authorized.
2. If the architecture checkpoint closes and integrates, separately gate the
   exact Native implementation paths, SQLite persistence/security, internal
   DTO/API compatibility, evidence capture, and Product/Technical live adapters.
3. Keep all public API, CRD, existing-schema, production integration, freeze,
   certification, readiness, and release decisions under their separate Gates.

Tracks A–E and all candidate future Session IDs remain `RECOMMENDED_ONLY /
NOT_ACTIVE / NOT_AUTHORIZED`. Historical S5-ARCH-007 and S5-IMPL-001 navigation
does not authorize immediate work.

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
