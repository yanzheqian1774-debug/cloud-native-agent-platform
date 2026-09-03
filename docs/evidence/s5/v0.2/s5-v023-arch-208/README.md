# S5-V023-ARCH-208 Checkpoint A Evidence

## Entry reconciliation

| Gate | Evidence | Result |
| --- | --- | --- |
| Allocation | Human-authorized `S5-V023-ARCH-208`; no prior repository/history/ref/branch/tag/worktree/GitHub PR/Issue/visible-task/explicit allocation owned suffix `208`; this task is the authorized allocation | `PASS` |
| Baseline | fresh `origin/main` commit `090ff05beaaa2d44b77fa98efcc5b21fc149a153`; tree `27d9245674d5b97a1456e23c3fa18485602ef1ea` | `PASS` |
| Exact-main CI | run `33727444881`, exact head, completed `SUCCESS` | `PASS` |
| Authorities | ARCH-201/REL-202, ARCH-204/REL-206, IMPL-210/REL-205 and IMPL-230/REL-207 are durable in main | `PASS` |
| IMPL-240 blocker | no Plan/approval aggregate, exact execution target, replay constraint, CAS versions, immutable transitions, enforced Evidence/Outcome links or atomic Unit of Work | `CONFIRMED` |
| Isolation | no product code, migration, IMPL-220 path, v0.2.2 task/deployment or Runtime effect touched | `PASS` |

Migration `0008` preserves scoped Run, Task Run and Attempt identities but has no
authoritative Plan/approval aggregate. Its single Intervention row references
Assignment and/or Runtime Instance, cannot enforce exactly one Run/Task/Attempt
target, and cannot retain immutable decisions. Current protocols lack the required
replay key, target CAS versions, scoped Evidence/Outcome links and command-wide
atomic transaction.

The decision therefore requires additive migration `0009` and leaves `0008`
unchanged. It defines entity/relation/state, transition, rollback,
concurrency/idempotency and migration matrices; PostgreSQL authority; SQLite
non-authority; minimum disclosure; and REL-205/IMPL-220/REL-207 compatibility.

Exactly five paths are changed: the decision, this README, both S5 indexes and the
Governance Registry. Final commit/tree, Draft PR and exact-head CI are GitHub-native
facts and are not embedded self-referentially before they exist.

`PASS / WORKFLOW_CONTROL_PERSISTENCE_G2_DECIDED / READY_FOR_HUMAN_CHECKPOINT_A`

No migration, downstream identifier, behavior, Runtime effect, deployment, Preview,
Formal Release or merge is authorized.
