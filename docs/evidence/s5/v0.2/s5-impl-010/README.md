# S5-IMPL-010 — Product View evidence

## Candidate identity

- Session: `S5-IMPL-010 — Product View`
- Baseline: `25f755432381b40efae2f3e251863db0ca32acee`
- Branch: `codex/s5-impl-010-product-view`
- Final head: `RESOLVED_BY_EXACT_GIT_PR_AND_CI`
- Classification: `DETERMINISTIC / SYNTHETIC / NON_AUTHORITATIVE / TECHNICAL_PREVIEW`

## Scope and authority

The production-owned Console Product View presents a bounded business journey,
Digital Employee directory, Draft/Diff/Human Approval boundary, correction,
execution progress, Outcome/Evidence/Citation, honest Runtime states, and the
canonical Product graph projection. The frontend fixture adapter is explicitly
non-authoritative. It performs no network access, persistence, authorization,
Runtime or Provider invocation and creates no second graph or execution identity.

The existing Shared DTO and Graph Projection semantics remain unchanged. The
fixture compatibility suite binds the display concepts to `product_view()`, the
Product projection context, canonical snapshot identity prefix, raw relation
evidence, cardinalities, and Platform Execution Identity.

## Authorized path inventory

Exactly the 18 paths in the Human G1 authorization are changed. No public API,
CRD/schema, backend DTO, canonical graph semantic, dependency, lockfile,
Technical View, Golden Demo, Runtime, Knowledge Provider, or release path is
modified.

## Product behavior and retained constraints

- The question-to-plan-to-approval-to-outcome path is deterministic and browser-only.
- Approval replay requires the exact revision fingerprint; reject and correction fail closed.
- Correction creates immutable successor revision `plan-revision.synthetic.qi-1042.r2`.
- Instance allocation is labelled synthetic preview and does not imply autoscaling.
- DENY reports zero Provider calls; UNKNOWN and failure are never success.
- Citations are synthetic/view-only and do not claim production Knowledge or RAG.
- Native is available/component-tested/not certified. OpenClaw is experimental/currently unavailable/support not granted. Hermes is experimental/not currently certifiable/support not granted.
- `zh-CN` and `en-US` change display only; journey state and stable identities remain mounted outside locale state.
- Raw graph expansion preserves relation IDs, type, direction, cardinality and Evidence. Fixture 6 order is `DEPENDS_ON / TRIGGERS / DATA_FLOW`.

## Validation and browser QA

Local candidate validation on 2026-08-27:

- targeted Product View suite: **25 passed**;
- full repository suite through `make check`: **641 passed**, with one existing
  Starlette/httpx deprecation warning;
- Ruff lint: passed; Ruff format: **107 files already formatted**;
- frontend lint: passed;
- frontend production build: passed, **49 modules transformed**;
- `git diff --check`: passed.

Interactive browser QA passed the complete `en-US` and `zh-CN` journeys,
mid-plan locale switching, stable selected question and Platform Execution
Identity, directory content, plan/tasks/roles/preview instances,
Draft/Diff/Approval, correction revision, raw aggregate expansion, ALLOW and
synthetic Citation, DENY with zero calls, UNKNOWN/failure honesty, all three
Runtime states, desktop layout, keyboard focus, and browser logs with zero
warnings/errors. At **390×844**, viewport, body, and document scroll widths all
measured exactly **390 px**, proving no horizontal overflow.

Exact-head GitHub Quality Gates and Frontend Quality Gates are recorded by the
Draft PR checks. The non-self-referential final commit identity is resolved by
the matching local, remote, and PR heads.

## Rollback

Revert the bounded S5-IMPL-010 commits or delete the newly added Product View
files and restore the five modified frontend files. No data migration, external
effect reversal, dependency cleanup, API rollback, or Kubernetes action exists.

## Human gate

Stop at the Human S5-IMPL-010 Product View Review Gate. Do not merge the PR.
