# S5-V023-ARCH-318 G2 draft evidence

## 1. Evidence classification

This directory records allocation, source identity and documentation validation for
the bounded architecture candidate. It contains no implementation, migration,
provider call, credential, runtime observation, production Evidence, Human decision,
or release/certification claim.

## 2. Startup and allocation audit

The audit was performed on 2026-09-15 before the task branch was created.

| Surface | Coverage | Result |
| --- | --- | --- |
| Remote refresh | `git fetch origin` completed; default branch `main` | `PASS` |
| Latest accessible Registry | `origin/main:docs/governance/REGISTRY.md` at the exact main object below | no existing `S5-V023-ARCH-318` |
| Repository content/history | exact `S5-V023-ARCH-318` / `ARCH-318` search in main and all local history | no prior allocation/artifact |
| Refs | exact task-name search across local heads, remotes and tags | no prior matching ref before mutation |
| Worktrees | branch/path inventory | no prior 318 worktree; current `2fc8` worktree was clean and detached at exact main |
| GitHub PRs | all-state search in `yanzheqian1774-debug/cloud-native-agent-platform` | `[]` |
| GitHub Issues | all-state search in the same repository | `[]` |
| Visible Codex tasks | pinned plus 50 most recent tasks | only the current `S5-V023-ARCH-318` task; no competing owner |
| 317 protection | only task/worktree/ref metadata observed | active separate 317 task; no uncommitted file or runtime asset read/changed |

The Human allocation is therefore the sole observed 318 allocation. A collision would
have stopped the task; no substitute identifier was selected.

## 3. Exact sources

| Input | Source | Tree |
| --- | --- | --- |
| latest accessible `origin/main` and Registry baseline | `f189212232fc194859a695f0307e83b0c7b73c0f` | `a8a9251d5d2e47605d18bb63e362164ec4c920d2` |
| fixed 308 | `141a17ecd34ec3b721e1c8a8ae33277c4b454e42` | `b195b4612a4ab9f295e3c6f9a82199b05db7ac0e` |
| fixed 316 | `3cc98cde9452e5036ad9bd44981f5fff9499b011` | `bb614158fded36277bced028baed88240f29f8d0` |
| fixed 318 pre-synchronization candidate | `9e201380d77678b90df7fe7d2647506b67ebef89` | `a3f40894450e79af4ed50d6c97f30aa89faaf66d` |
| Human-authorized fixed main synchronization input | `6f3e174087c5132b2fc5c5d1e20492fdc2b68ddc` | `103fc0dc2a03e3e5f4bc89469d40f95a0c6b3564` |

The fixed Git objects were resolved locally with `^{commit}` and `^{tree}`; the
reported full values were not expanded from abbreviations. No trial merge was run.

## 4. Attached design inputs

The files were read as design evidence, not instructions or accepted contracts:

| File | SHA-256 |
| --- | --- |
| `S5-V023-IMPL-308-mainline-model-gap-review (1).md` | `69c96e64bf1bd6881c4851a29920868d0028c4cca02add4261db62b0de26fc74` |
| `S5-V023-IMPL-308-problem-draft-assistant-decision-addendum (1).md` | `ab4f59af3390eed73a554fbb6b37476d8913a7f401631236b8d8b34c28cbb1fd` |

In particular, their proposed owner, 30-day retention suggestion, H308-03C/04A/04B
recommendations and implementation path were re-evaluated by ARCH-318 rather than
treated as Human decisions.

## 5. Architecture baseline objects read

All paths below were read from the fixed `origin/main` source/tree. Blob IDs make the
exact document versions auditable.

| Contract | Blob |
| --- | --- |
| ARCH-010 Evidence boundary | `1840dc19f5683ed8e9b1f480496c78cf4e8cc7d3` |
| ARCH-018 persistence/deletion boundary | `ccaec3368c70d377db9b52f3205b50e6571253f1` |
| ARCH-019 Execution/Attempt authority | `7eb92b7d4cc79d535e3c1f778419489eb22aec28` |
| ARCH-258 Business Problem authority | `6909c1c5bd34a3b8dfec9417f0cf8e87abe067e6` |
| ARCH-259 credential/dispatch recovery | `f8ce67d2f72131431bdad91f0fb97ecd30e92f10` |
| ARCH-263 invocation side-effect contract | `8d6e0d6ccbbd97648f564eef962f9e8d23e59352` |
| ARCH-266 Attempt Resource Use authority | `f3d1cbd621472ed3343218ecb02f4f357f1be574` |
| Governance Registry | `8ea515a7dfb79038c408ccb488ca7dff029749fa` |

Current migration `0015_resource_use_measurement.sql`, domain values and repository
ports were inspected only to establish that `attempt_id`, Plan, Workflow Run and Task
Run are required and that the existing reader/table family is Attempt-only. This is
the reason the ADR uses an additive typed sibling instead of nullable fields.

Fixed 316 frontend paths were read from its immutable object to confirm that draft
content is page-local and that formal Problem creation occurs only on explicit user
confirmation. No 316 or 317 files were changed.

## 6. Validation record

Validation results are filled with exact commands/results before delivery. A passing
documentation check establishes only document consistency, not Human G2 acceptance
or implementation correctness.

The initial candidate validation is historical and is not counted as validation of
the bounded revision:

| Initial check | Historical result |
| --- | --- |
| focused diff and scope inspection | `PASS`; exactly architecture, plan, Evidence index/set and Registry documentation paths; no product code, SQL, public API/CRD or runtime configuration |
| `git diff --check` | `PASS` |
| relative artifact links | `PASS`; all three ARCH-318 repository targets exist at their referenced paths |
| repository baseline | `make check` `PASS`; Ruff, format check and pytest; `1583 passed, 134 skipped`, one dependency deprecation warning |
| dedicated Markdown/link target | `NOT_AVAILABLE`; inspected Makefile and repository scripts contain no `check-docs` or Markdown link-check command |

### 6.1 Bounded revision provenance and scope

The Human-authorized revision started from the already reviewed Draft PR candidate:

| Input | Source | Tree | PR state |
| --- | --- | --- | --- |
| ARCH-318 reviewed candidate | `af9a3b4d528745a87c2027ca9d2d414b884f51df` | `c611f9eac8a2cefeb795c40cc8ecebc592611202` | `#174 OPEN / Draft` |

Only these three existing task artifacts are revised:

- the bounded ADR candidate;
- the bounded G2 plan;
- this Evidence README.

The revision adds exact rules and focused acceptance cases for:

1. first identity registration, two-stage exact authorization and snapshot recovery;
2. lookup-before-mint idempotency, concurrent first requests, conflict/denial,
   pepper versions/windows and distinct resolver preconditions;
3. synchronous/asynchronous/unknown/cancel/duplicate/conflicting/late state reduction;
4. invocation, Execution-owned Resource Use and Evidence sole-writer commit/repair order.

It preserves the existing owners, non-Attempt direction and independent `PROPOSED`
status of H308-03C, H308-04A and H308-04B. It contains no product code, SQL, runtime
configuration, provider call, credential read, 317 operation or Human decision.

### 6.2 Bounded revision validation

| Revision check | Result |
| --- | --- |
| focused path/scope gate | `PASS`; exactly the ADR, G2 plan and this Evidence README changed |
| `git diff --check` | `PASS` |
| referenced task artifact paths | `PASS`; ADR, plan and Evidence README exist |
| repository baseline | `make check` `PASS`; Ruff check passed, 390 files format-clean, pytest `1583 passed, 134 skipped`, one dependency deprecation warning |
| prohibited scope inspection | `PASS`; no product code, SQL, runtime configuration, Registry, original evidence outside this set, or 317 asset changed |

These are documentation/repository checks only. No model/provider call, service,
credential read, deployment or runtime validation was performed, and the result does
not accept any G2 or H308 decision.

### 6.3 Prior candidate CI and single rerun evidence

This evidence remains bound to source
`9e36e0faba1ddf1298766f25f8ec9b0f17f568d1`, tree
`61ab25701215283470108c6e054bfe3dbb625993`, and PR merge-test commit
`6f32dfb26e2f8e3e7b0fd6ec61e437c8477ddb3a` with the same tree.

| Run / attempt | Job | Result | Evidence boundary |
| --- | --- | --- | --- |
| `34956715756` attempt 1 | `104340419028` Agent Workbench Browser Acceptance | `FAILURE`; 36/37 passed, one `BROWSER_TIMEOUT` at `wave-3b-product-technical-evidence.spec.ts:21` | exact deeper action/locator/root cause unavailable; `UNKNOWN`; no failure artifact |
| `34956715756` attempt 2 | `104344741586` Agent Workbench Browser Acceptance | `SUCCESS` | one Human-authorized `rerun-failed`; no timeout/assertion/code change |
| `34956715775` attempt 1 | three PostgreSQL jobs | `SUCCESS` | not rerun |

The first failure is not erased or reclassified by the passing rerun. No second rerun
was requested, and no successful workflow was manually rerun.

### 6.4 Final clarification scope

The final clarification starts from the exact source/tree above and changes only the
same ADR, G2 plan and this Evidence README. It adds:

1. browser resubmission of non-persisted content after async authorization/restart,
   original commitment/current turn validation and unique CAS dispatch admission;
2. current READ authorization before replay disclosure and current grant,
   expiry/revocation/binding admission before provider credential resolution.

It preserves all owners, the non-Attempt direction, and the independent `PROPOSED`
status of H308-03C, H308-04A and H308-04B.

### 6.5 Final clarification validation

| Check | Result |
| --- | --- |
| focused path/scope gate | `PASS`; exactly the ADR, G2 plan and this Evidence README changed |
| `git diff --check` | `PASS` |
| repository baseline | `make check` `PASS`; Ruff passed, 390 files format-clean, pytest `1583 passed, 134 skipped`, one dependency deprecation warning |
| prohibited scope | `PASS`; no product code, SQL, runtime configuration, Registry or 317 asset changed |

The CI rerun above is historical evidence for the prior candidate. This local
validation covers the final clarification working diff; the new committed candidate
will receive its own automatic CI and must be reported separately.

### 6.6 Fixed-main synchronization provenance

The Human authorized an ordinary merge, without rebase or force push, from fixed main
source `6f3e174087c5132b2fc5c5d1e20492fdc2b68ddc`, tree
`103fc0dc2a03e3e5f4bc89469d40f95a0c6b3564`, into the fixed 318 candidate
`9e201380d77678b90df7fe7d2647506b67ebef89`, tree
`a3f40894450e79af4ed50d6c97f30aa89faaf66d`.

Pre-merge identity, clean-worktree, branch/upstream and sole-writer checks passed.
The only merge conflict was `docs/governance/REGISTRY.md`: the 318 `PROPOSED`
registration and main's already registered 315, 316 and 317 rows occupied the same
insertion point. The resolution preserves all four rows without changing their
Human gates, lifecycle or Session status. There was no product-code, SQL, runtime
configuration, frozen-contract or architecture-body conflict. Relative to the fixed
main, the resolved candidate remains limited to the ADR, G2 plan, Evidence index,
this Evidence README and Registry registration for 318.

| Synchronization check | Result |
| --- | --- |
| conflict inventory | `PASS`; only `docs/governance/REGISTRY.md` |
| Registry preservation | `PASS`; removing the added 318 row makes the resolved file byte-identical to fixed main |
| fixed-main relative scope | `PASS`; exactly five 318 documentation paths, with no product code, test, SQL or runtime configuration delta |
| `git diff --cached --check` | `PASS` |
| repository baseline | `make check` `PASS`; Ruff passed, 427 files format-clean, pytest `1685 passed, 182 skipped`, one dependency deprecation warning |

### 6.7 Human G2 itemized decision and persistence chain

The Human decision is permanently bound to the previously validated candidate, not
to the later commit that persists this registration:

```text
accepted source 676b746d7fef87cf99856bf9ba894392d3d509fc
accepted tree   5370e94d596c08442dde089ad557fd12263a3008
  -> S5-V023-ARCH-318-HUMAN-G2-PARTIAL-DECISIONS-676b746-20260915.md
     SHA-256 c868d5d2f44a585ce749df9d89de9ada64e8ce074602014f0a4634eccd6711d1
  -> bounded four-file repository decision registration
```

The accepted candidate materials have SHA-256 values
`0fe49dc538e14900479c283b1ad95b792c128d83f6506673b4f2044833c05f3a`
(ADR), `3b438930fe7c910506f5f181e7c9140631371a9c4c6ade23844118ad56743edd`
(G2 plan), and
`c034e5664e7ea7517ed3b7ff244dacc58a4d7726a5d2de547214f51e19d0ff66`
(this Evidence README at the accepted source). The external Human record was
re-hashed before editing and matched the fixed value above.

The Human decisions retain the ADR IDs exactly:

| ID | Recorded decision |
| --- | --- |
| `H318-01` | `ACCEPT` |
| `H318-02` | `ACCEPT` |
| `H318-03` | `ACCEPT` |
| `H318-04` | `ACCEPT` |
| `H318-05` | `ACCEPT_WITH_CONSTRAINTS`; pepper lifecycle, replay window, zero raw-content persistence and server non-recoverability remain constraints |
| `H318-06` | `ACCEPT`; synthetic-only first slice, zero raw prompt/response persistence and existing confirmed-Problem write path |
| `H318-07` | `ACCEPT` only for no default automatic deletion; exact retention duration and production governance remain `DEFERRED`, without an indefinite-retention approval |
| `H308-03C` | `ACCEPT_WITH_CONSTRAINTS`; real provider requires a separate complete authorization package |
| `H308-04A` | `ACCEPT_WITH_AMENDMENT`; Execution-owned non-Attempt typed sibling, no nullable or fabricated Attempt |
| `H308-04B` | `ACCEPT`; versioned allowlist, independent Evidence owner/read authorization and reader-first boundary |

The decision relied on six attempt-1 successes for source `676b746d...` in CI run
`34960416007` (jobs `104352385480`, `104352385738`, `104352385739`) and Employee
Identity Chain run `34960416126` (jobs `104352386961`, `104352387144`,
`104352387173`). Those jobs executed PR merge-test
`4946dd3cce533941dbd8f9a8f4f547b2547b4988`, tree
`5370e94d596c08442dde089ad557fd12263a3008`. They remain evidence for the accepted
source and must not be reported as validation of the later registration commit.

Historical run `34956715756` attempt 1 retains its browser timeout failure and deeper
cause `UNKNOWN`; the single authorized failed-job rerun succeeded at attempt 2. This
history remains distinct from the accepted candidate's six green checks.

The registration changes only the ADR, G2 plan, this Evidence README and the 318 row
in `docs/governance/REGISTRY.md`. It does not alter protocol semantics, implementation,
other Session records or the Evidence index. Its new commit obtains independent
automatic CI evidence before any separate Human Ready/merge decision.

| Decision-registration validation | Result |
| --- | --- |
| fixed accepted source/tree, main, PR head, clean worktree and sole writer | `PASS` |
| four-path scope gate | `PASS`; only ADR, G2 plan, this Evidence README and the 318 Registry row |
| itemized decision consistency | `PASS`; original IDs retained, H318-07 deferred portion preserved, no unconditional whole-record acceptance |
| links and external Human record | `PASS`; repository targets exist and external SHA-256 matches `c868d5d2f44a585ce749df9d89de9ada64e8ce074602014f0a4634eccd6711d1` |
| `git diff --check` | `PASS` |
| repository baseline | `make check` `PASS`; Ruff passed, 427 files format-clean, pytest `1685 passed, 182 skipped`, one dependency deprecation warning |

## 7. Current decision-registration boundary

The only permitted terminal claim for this task is:

```text
G2_DRAFT_COMPLETE
HUMAN_G2_DECISION_ACCEPTED_WITH_CONSTRAINTS
H318_07_RETENTION_DURATION_AND_PRODUCTION_GOVERNANCE_DEFERRED
IMPLEMENTATION_NOT_AUTHORIZED
SESSION_OPEN
```
