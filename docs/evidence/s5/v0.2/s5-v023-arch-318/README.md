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

| Check | Result |
| --- | --- |
| focused diff and scope inspection | `PASS`; exactly architecture, plan, Evidence index/set and Registry documentation paths; no product code, SQL, public API/CRD or runtime configuration |
| `git diff --check` | `PASS` |
| relative artifact links | `PASS`; all three ARCH-318 repository targets exist at their referenced paths |
| repository baseline | `make check` `PASS`; Ruff, format check and pytest; `1583 passed, 134 skipped`, one dependency deprecation warning |
| dedicated Markdown/link target | `NOT_AVAILABLE`; inspected Makefile and repository scripts contain no `check-docs` or Markdown link-check command |

## 7. Terminal boundary

The only permitted terminal claim for this task is:

```text
G2_DRAFT_COMPLETE
AWAITING_HUMAN_ARCHITECTURE_DECISION
IMPLEMENTATION_NOT_AUTHORIZED
SESSION_OPEN
```
