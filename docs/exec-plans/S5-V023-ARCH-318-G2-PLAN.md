# S5-V023-ARCH-318 — Bounded G2 plan

## Status and authority

| Field | Value |
| --- | --- |
| Session | `S5-V023-ARCH-318` |
| Type | `ARCH / BOUNDED G2` |
| Task status | `ACTIVE / HUMAN_AUTHORIZED` |
| Candidate decision | `PROPOSED / AWAITING_HUMAN_ARCHITECTURE_DECISION` |
| Implementation | `NOT_STARTED / NOT_AUTHORIZED` |
| Fixed main baseline | source `f189212232fc194859a695f0307e83b0c7b73c0f`; tree `a8a9251d5d2e47605d18bb63e362164ec4c920d2` |
| Fixed reviewed candidate for this revision | source `af9a3b4d528745a87c2027ca9d2d414b884f51df`; tree `c611f9eac8a2cefeb795c40cc8ecebc592611202`; Draft PR `#174` |
| Architecture candidate | [S5-V023-ARCH-318](../../architecture/s5/v0.2/S5-V023-ARCH-318-PRE-PROBLEM-DRAFT-ASSISTANCE-INVOCATION-MODEL-USE-EVIDENCE-V1.md) |
| Evidence | [startup and document evidence](../evidence/s5/v0.2/s5-v023-arch-318/README.md) |

This plan governs preparation of one architecture Draft PR. It does not authorize
code, SQL, public API/CRD, configuration, provider calls, services, credentials,
deployment, Ready, merge, Human acceptance, or Session closure.

## 1. Goal

Decide the minimum internal identity, owner, authorization target, model binding,
recovery and evidence contract for:

```text
problem input -> AI clarification -> user supplement -> editable draft
-> Human confirmation -> existing formal Problem create
```

Preserve the current Attempt meaning and every existing fact owner. Do not redesign
the platform or make the architecture task a prerequisite for the already authorized
317 compatibility scope.

## 2. Inputs and inspection boundary

- repository rules: `AGENTS.md`, `PRODUCT.md`, `ARCHITECTURE.md`, `ROADMAP.md`, and
  the required engineering governance documents;
- latest accessible `origin/main`, Registry, refs, GitHub PR/Issue inventory and
  visible Codex task inventory;
- fixed 308 source/tree and fixed 316 source/tree supplied by Human;
- the two attached reports as design inputs only;
- only concrete clauses from accepted ARCH-010, ARCH-018, ARCH-019, ARCH-258,
  ARCH-259, ARCH-263 and ARCH-266, plus fixed 308 H308-01/02/03A and the three
  retained proposals.

Do not inspect 317 uncommitted content, read credentials, call a model, start a
service, access runtime assets, trial-merge 317, or infer an accepted decision from
any attachment/candidate prose.

## 3. Work sequence

1. **Collision gate** — fetch origin; check exact task ID across current Registry,
   repository tree/history, local/remote refs, branches/tags/worktrees, GitHub
   PRs/issues and visible task inventory. Stop without allocating a substitute ID on
   conflict.
2. **Isolation gate** — after no conflict, create exactly one task branch in the
   pre-created isolated worktree from exact `origin/main`.
3. **Authority inspection** — record complete baseline source/tree and fixed input
   source/tree; read only task-relevant accepted clauses and current implementation
   shapes required for compatibility.
4. **G2 synthesis** — draft owner/identity relationships; state/authorization/error/
   recovery semantics; keyed idempotency; data handling; non-Attempt Resource Use;
   independent Evidence; severable Human decisions and future real-provider fields.
5. **Governance registration** — add one Registry row and one Evidence index entry;
   keep lifecycle `ACTIVE`, candidate `PROPOSED`, Human Gate `PENDING`.
6. **Validation** — run whitespace/link/Markdown/repository documentation checks that
   do not modify files; inspect focused diff and status; scan changed files for
   prohibited implementation/configuration/secrets.
7. **Delivery** — normal commit, non-force push, create exactly one Draft PR, then
   report candidate source/tree and stop at `G2_DRAFT_COMPLETE / AWAITING_HUMAN`.

The bounded revision authorized after the initial delivery reuses the same Session,
branch, worktree and Draft PR. It must edit only the ADR, this plan and necessary
ARCH-318 Evidence; it must not repeat allocation, create another PR, or alter the
already registered owner/direction. Its sequence is:

```text
verify fixed reviewed candidate and Draft PR identity
-> specify first-request identity/auth/snapshot bootstrap
-> specify scoped idempotency lookup/concurrency/pepper rules
-> complete state transitions and terminal conflict reduction
-> specify sole-writer Resource Use/Evidence commit and repair protocol
-> add focused positive/negative acceptance cases
-> validate, normal commit, non-force push, follow existing CI to terminal
-> export the revised originals outside the repository
```

## 4. Required G2 outputs

- bounded ADR candidate and an owner/identity relationship model;
- exact authorization targets and server-owned binding snapshot;
- non-circular first context/turn/invocation/snapshot registration followed by two
  exact, recoverable authorization requests and post-allow protected readback;
- persist-before-dispatch, unknown, cancellation, late-result and successor retry;
- complete sync/async/unknown/cancel/terminal-conflict state reduction without
  automatic redispatch or exactly-once claims;
- implementable no-raw-content idempotency with lookup-before-mint, atomic concurrent
  first writer, payload conflict, denial, pepper rotation/window and resolver separation;
- non-Attempt Resource Use compatibility without nullable Attempt fields;
- independently authorized, reader-first Model Evidence;
- fixed invocation -> Execution-owned Resource Use -> Evidence commit/reference order,
  deterministic repair IDs and no-provider-redispatch partial-failure recovery;
- synthetic-only first-slice data boundary, platform/provider retention distinction,
  and no default 30-day deletion;
- independent recommendations for H308-03C, H308-04A and H308-04B;
- future real-provider authorization fields;
- smallest future G1 package and acceptance matrix.

## 5. Architecture stop conditions

Stop and report rather than expand this task if any finding requires:

- a public CRD/API group or frozen Contract change;
- changing existing Attempt/Task/Workflow lifecycle;
- replacing an accepted owner or adding a second writer;
- a new database or persistent infrastructure dependency;
- access to 317 uncommitted content or assets;
- a model call, credential read, service start or runtime mutation;
- treating task-start authority as Human architecture acceptance.

## 6. Planned document validation

Run, at minimum:

```text
git diff --check
make check
```

The inspected baseline has no dedicated `check-docs` target or Markdown link checker;
record that limitation rather than inventing one. Do not run mutating pre-commit hooks
as a substitute. Inspect `git diff --stat`, the complete diff, referenced relative
paths, and `git status` before commit and after push.

## 7. Future G1 handoff (not allocated)

After Human G2 decisions, a separate Human-authorized G1 may implement, in order:

```text
typed contracts and reader compatibility
-> additive PostgreSQL metadata, scoped idempotency claim and exact authorization requests
-> trusted secret resolver and bounded synthetic adapter
-> conditional sole-writer Resource Use / Evidence ports and repair obligations
-> Workbench clarification/draft/confirm UI
-> real PostgreSQL, restart, security and browser acceptance
-> optional real provider only under a complete H308-03C authorization record
```

No arrow allocates a Session or grants implementation/deployment authority.
