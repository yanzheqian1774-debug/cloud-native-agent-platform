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
- S5-GOV-001 starting durable-main SHA:
  `71e0f682c015b49f7afed6e21988c94a080f2450`

The SHA above is the immutable starting baseline for S5-GOV-001, not a promise
that `main` will never advance. The [Governance Registry](docs/governance/REGISTRY.md)
records lifecycle and provenance.

## Session state

| Session | Current state | Durable basis |
| --- | --- | --- |
| S5-ARCH-005 | `CLOSED / COMPLETED / PASS / SESSION_CLOSED` | Accepted Candidate artifact and source head |
| S5-REL-004 | `HUMAN_CONFIRMED_CLOSED / COMPLETED / PASS / SESSION_CLOSED` | PR #42 merge plus imported Human confirmation |
| S5-GOV-001 | `REVIEW / AUTHORIZED / PASS / PROJECT_GOVERNANCE_BASELINE_CANDIDATE` | Checkpoint B completed in Draft PR #43; Human baseline Gate pending |

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

The final Demo scenario is an open Human decision. Current directions are:

- durable carried-forward direction: Engineering Release Risk Manager;
- proposed business-facing direction: After-Sales Service Expert / Quality
  Issue Identification and Closure.

Neither direction is recorded here as final Demo approval.

## Immediate next work

1. Finish the S5-GOV-001 minimum governance baseline.
2. Authorize a separate Product/Architecture Session for v0.2 Demo scope.
3. Authorize bounded Contract, prototype, and conformance Sessions afterward.

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
