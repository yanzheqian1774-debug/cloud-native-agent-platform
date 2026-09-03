# S5-V023-IMPL-221 Checkpoint A Evidence

## Scope

This task implements only the persistence foundation authorized by ARCH-208:
additive migration `0009`, typed internal repository ports, the PostgreSQL adapter,
the atomic Workflow Control Unit of Work, and focused persistence tests. It does
not implement IMPL-240 application behavior, frontend, bootstrap, deployment, or
Runtime/provider effects.

## Entry evidence

- Human-authorized allocation: `S5-V023-IMPL-221`; no earlier repository history,
  ref, branch, tag, worktree, GitHub PR/Issue, visible task, or explicit allocation
  owned suffix `221`.
- Fresh baseline: commit `89d8c2a97f408a614deb1234adeafcaddcc45079`, tree
  `481720679c4e54d740aee0361eb801caadc593ec`.
- Exact-main CI: `33732859242 / SUCCESS`.
- PR #134 / IMPL-220 owns four Digital Employee application/adapter/test paths;
  none overlap this task.
- Paused IMPL-240 made no changes and remains blocked pending durable IMPL-221.

## Persistence and recovery boundary

PostgreSQL remains the authoritative writer. Migration `0008` is unchanged.
Migration `0009` is additive and maps populated legacy rows to explicit
`LEGACY_UNBOUND`, `LEGACY_IMPORTED`, `RECOVERY_REQUIRED`, or
`LEGACY_CONTEXT_ONLY` states without fabricating Plan approval, target, actor, or
success facts. The Unit of Work authorizes before lookup, uses a serializable
transaction, validates scoped targets, claims normalized payload digests, performs
CAS mutation, appends immutable history, writes successor/command/Evidence/Outcome
facts and links, completes the claim, and performs authoritative readback before
commit. It exposes no Runtime, provider, Kubernetes, or external-effect entrypoint.

Automatic destructive downgrade is intentionally unsupported. After any `0009`
authoritative fact exists, rollback requires stopped writers, a verified backup and
high-water capture, followed by forward repair or explicit export/reconciliation.

## Validation

Final commands and exact results are recorded in the Draft PR description after
the required focused PostgreSQL 15 suite, `make check`, Ruff, formatting,
pre-commit, diff/path/overlap, and security/prohibited-scope scans complete.
