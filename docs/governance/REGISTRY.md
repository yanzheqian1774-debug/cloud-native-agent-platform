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
| S5-ARCH-005 | v0.2 Core Schema Draft & Compatibility Map / ARCH | `CLOSED / COMPLETED` | `PASS / SESSION_CLOSED` | Source: S5-ARCH-004; branch `codex/s5-arch-005-core-schema-draft`; PR #42; source head `771929705093ff14e444faa508229a84c929d2e7` | Final Schema Candidate Gate and Close Confirmation: `PASS_WITH_CONSTRAINTS / PASS` | `REPOSITORY_NATIVE / PR_NATIVE` | None; reopen prohibited |
| S5-REL-004 | Core Schema Candidate Integration / REL | `CLOSED / COMPLETED` | `PASS / SESSION_CLOSED` | Source: S5-ARCH-005; PR #42; merge `71e0f682c015b49f7afed6e21988c94a080f2450` | Merge Gate, Closeout Authorization, Close Confirmation: `PASS` | Closure: `HUMAN_CONFIRMED`; merge: `PR_NATIVE / REPOSITORY_NATIVE` | None; reopen prohibited |
| S5-GOV-001 | Project Source of Truth & Release Governance Foundation / GOV | `CLOSING / AUTHORIZED` | `PASS / READY_TO_CLOSE`; Checkpoint C — Session Finalization | Source: S5-REL-004; branch `codex/s5-gov-001-release-governance`; isolated worktree; Draft PR #43; commit recorded in Git/PR | Checkpoint A: `PASS_WITH_CONSTRAINTS`; Checkpoint B: `PASS_WITH_CONSTRAINTS`; Human Close Confirmation: `PENDING` | `HUMAN_CONFIRMED / REPOSITORY_NATIVE / PR_NATIVE` | Human S5-GOV-001 Close Confirmation |

S5-REL-004 closure was not previously repository-native. Its Registry entry is
an explicit import of Human-confirmed closure; PR #42 and its merge commit are
independently Git/PR-native.

After S5-GOV-001 is Human-confirmed `CLOSED`, the recommended integration
Session is **S5-REL-005 — Project Governance Baseline Integration**, with
source Session S5-GOV-001 and source PR #43. This is a recommendation only;
S5-REL-005 is not `ACTIVE` or `AUTHORIZED`.

## Human and Open Decision Index

| Subject | State | Durable scope / source |
| --- | --- | --- |
| v0.2 Core Schema Candidate v0 | `ACCEPTED_WITH_EVIDENCE_DEBT` | [Final Candidate Gate](../../S5-ARCH-005-CORE-SCHEMA-DRAFT-V1.md#107-human-final-schema-candidate-gate) |
| Five logical resources | `ACCEPTED_WITH_EVIDENCE_DEBT` | Logical Candidate only; five CRDs are not authorized or approved |
| Option B compatibility direction | `ACCEPTED_WITH_EVIDENCE_DEBT` | Additive compatibility direction; representation, migration, and conformance remain debt |
| Platform Execution Identity | `ACCEPTED_WITH_EVIDENCE_DEBT` | Embedded Core value; serialization and propagation conformance remain debt |
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
