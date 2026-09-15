# S5-V023-ARCH-318 — Bounded G2 plan

## Status and authority

| Field | Value |
| --- | --- |
| Session | `S5-V023-ARCH-318` |
| Type | `ARCH / BOUNDED G2` |
| Task status | `ACTIVE / HUMAN_AUTHORIZED` |
| Candidate decision | `ACCEPTED / HUMAN_GATE_PASS_WITH_CONSTRAINTS` |
| Human itemized decision | bound to source `676b746d7fef87cf99856bf9ba894392d3d509fc`, tree `5370e94d596c08442dde089ad557fd12263a3008`; external record SHA-256 `c868d5d2f44a585ce749df9d89de9ada64e8ce074602014f0a4634eccd6711d1` |
| Implementation | `NOT_STARTED / NOT_AUTHORIZED` |
| Fixed main baseline | source `f189212232fc194859a695f0307e83b0c7b73c0f`; tree `a8a9251d5d2e47605d18bb63e362164ec4c920d2` |
| Fixed reviewed candidate for this revision | source `af9a3b4d528745a87c2027ca9d2d414b884f51df`; tree `c611f9eac8a2cefeb795c40cc8ecebc592611202`; Draft PR `#174` |
| Fixed final-clarification candidate | source `9e36e0faba1ddf1298766f25f8ec9b0f17f568d1`; tree `61ab25701215283470108c6e054bfe3dbb625993`; Draft PR `#174` |
| Fixed main synchronization | 318 source `9e201380d77678b90df7fe7d2647506b67ebef89`; tree `a3f40894450e79af4ed50d6c97f30aa89faaf66d`; ordinary-merge main source `6f3e174087c5132b2fc5c5d1e20492fdc2b68ddc`; tree `103fc0dc2a03e3e5f4bc89469d40f95a0c6b3564` |
| Architecture candidate | [S5-V023-ARCH-318](../../architecture/s5/v0.2/S5-V023-ARCH-318-PRE-PROBLEM-DRAFT-ASSISTANCE-INVOCATION-MODEL-USE-EVIDENCE-V1.md) |
| Evidence | [startup and document evidence](../evidence/s5/v0.2/s5-v023-arch-318/README.md) |

This plan governed preparation of one architecture Draft PR and now records the
itemized Human G2 decision without changing the accepted protocol. It does not
authorize code, SQL, public API/CRD, configuration, provider calls, services,
credentials, deployment, Ready, merge, G1 allocation, or Session closure. The Human
decision remains bound to the fixed source/tree above; this persistence change is not
a new acceptance of its resulting commit.

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

The final clarification additionally records the prior candidate CI independently:
one authorized `rerun-failed` of run `34956715756`, no rerun of successful workflows,
and no timeout/assertion/code change. It then specifies content resubmission before a
first dispatch and current authorization at disclosure/dispatch admission. The first
failure and unknown deeper cause remain evidence even if the one rerun passes.

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
- no-content async/restart recovery through same-key body resubmission, original
  commitment/current turn checks and one CAS/unique dispatch admission;
- current READ authorization for replay disclosure and a linearized current
  grant/expiry/revocation/binding admission before credential resolution, without
  implying that a completed external effect can be revoked;
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

## 8. Human G2 decision registration

The Human Gate is `PASS_WITH_CONSTRAINTS`. H318-01 through H318-04, H318-06 and
H308-04B are `ACCEPT`; H318-05 and H308-03C are
`ACCEPT_WITH_CONSTRAINTS`; H308-04A is `ACCEPT_WITH_AMENDMENT`. For H318-07,
only no default automatic deletion is accepted; the exact retention duration and
production data governance remain `DEFERRED` and must not be interpreted as approval
for indefinite retention. Real-provider execution still requires the complete,
separately Human-approved authorization record defined by the ADR.

These decisions are independent. Implementation remains
`NOT_STARTED / NOT_AUTHORIZED`, the Session remains `OPEN`, and the next possible
repository action is a separate Human Ready/merge gate after this registration
candidate and its own CI are verified.
