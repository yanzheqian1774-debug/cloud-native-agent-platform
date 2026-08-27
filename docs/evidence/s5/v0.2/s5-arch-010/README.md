# S5-ARCH-010 — Architecture Evidence

## Decision record

| Field | Value |
| --- | --- |
| Session | `S5-ARCH-010` |
| Checkpoint | `B — INDEPENDENT_ARCHITECTURE_SAFETY_AND_MERGE_READINESS` |
| Authorized baseline | `4d5da13e519627ba40cfdc632e3662f5cf965626` |
| Human decision | `PASS_WITH_CONSTRAINTS` |
| Human G2 | `APPROVED_FOR_BOUNDED_V0_2_ARCHITECTURE_ONLY` |
| Selected architecture | `HYBRID_F` |
| Persistence direction | bounded, single-node SQLite-backed append-only internal repository |
| Implementation | `NOT_AUTHORIZED / NOT_STARTED` |
| Publication | `CANDIDATE / NOT_DURABLE_MAIN / READY_FOR_HUMAN_MERGE_GATE` |

## Preflight evidence

- `HEAD` and `origin/main` were the exact authorized baseline.
- Exact-main CI run `33046211942` was `SUCCESS` for that SHA.
- The S5-ARCH-010 worktree and index were clean.
- No open PR, competing S5-ARCH-010 owner, or downstream Session existed.
- Product and Technical Views remained durably integrated.
- S5-REL-027 Human-confirmed closure was accepted as authoritative; its durable
  pre-close Registry and Project State rows were terminal snapshot lag.
- No other worktree's dirty contents were inspected or modified.

## Architecture result

The Human-approved candidate keeps Kubernetes Workflow/Task as public
control/current-state authority, adds a replaceable append-only internal
evidence authority, preserves the Canonical Graph as relationship authority,
and assigns one deterministic backend assembler to the shared Product and
Technical read snapshot. The frontend remains presentation-only.

The approved future SQLite direction is local and single-node only. It requires
transactional append, unique record identity, digest conflict rejection,
bounded configuration, Git exclusion, explicit security/locking/WAL review,
and a replaceable storage port. It is not implemented, multi-node, production
certified, or a substitute for a downstream PostgreSQL/event-journal design.

## Scope and claim boundary

This checkpoint changes exactly five architecture/governance paths. It changes
no code, test, dependency, database schema, migration, API, DTO, frontend
adapter, Runtime, Provider, Gateway, CRD, or existing Task/Workflow behavior.
No implementation, Golden Demo, recovery, certification, release, or
exactly-once claim is authorized. The future implementation task ID remains
unresolved.

## Checkpoint B safety correction

Independent review made previously implicit safety constraints explicit:

- Runtime/Provider-native identifiers are correlation-only;
- the assembler is read-only, derived, deterministic, and reproducible;
- every snapshot carries namespace and security domain;
- prohibited values never become digest inputs or recoverable digest oracles;
- Evidence/Citation references require independent authorization;
- correction and tombstone records cannot leak removed content;
- SQLite durability is bounded to a local single-node demonstration and grants
  no HA, scale, tenant-isolation, certification, or production claim; and
- Golden Demo readiness and production persistence retain separate future
  gates.

This is one linear five-path-bounded correction. Checkpoint A commit
`e3766bf5640759b035f740e0cffbe4889b88f995` is not amended or rewritten.

## Source

- [Production Execution Evidence and Shared Read Model Boundary v1](../../../../../architecture/s5/v0.2/S5-ARCH-010-PRODUCTION-EXECUTION-EVIDENCE-SHARED-READ-MODEL-BOUNDARY-V1.md)
