# S5-IMPL-083 — Immutable Candidate Mode Normalization Contract Alignment

## Scope and authority

This bounded correction is limited to the versioned Release Runner, its focused
tests, Release Runner engineering documentation, and this evidence package. It
does not change the release Contract schema, any product/backend/migration/
OpenClaw path, the Browser Harness immutable-mode gate, the filesystem-enforced
read-only mount, S5-DEPLOY-069, or prior rehearsal/attempt Evidence.

Entry revalidation started from durable `origin/main`
`39ec0c35ea892c847512cfea185100f90e6ed19d`, tree
`d087f1007dbae707543ff51f645dbdc98c9e5885`, with successful exact-main CI run
`33596336138`. Shared suffixes `080`–`082` were consumed, while `083` was unused.
The sole open PR, Draft PR #121 / S5-IMPL-080, changes no authorized S5-IMPL-083
path.

## Corrected boundary

- The Runner audits its newly created owned candidate before any chmod.
- Escaping symlinks, extra hard links, unsupported types, ownership mismatch,
  traversal failure, and chmod failure fail closed with sanitized codes.
- Non-executable regular files become `0444`, executable regular files become
  `0555`, and directories become `0555`; symlink targets are never chmodded.
- The aggregate mode-normalization Evidence discloses only the five authorized
  counts and a correlation digest.
- The authoritative pre-mount manifest is sealed only after normalization and
  verification prove zero writable entries and preserved required executables.
- The Browser Harness zero-writable-mode preflight, Linux read-only bind mount,
  exact non-root identity, write/bytecode denial, three-way manifest equality,
  underlying integrity, and owned cleanup remain mandatory.

## Checkpoint evidence

Fresh local results before commit/PR:

- Focused Release Runner suite: `48 passed, 1 skipped`; the skip is the
  intentionally root/Linux-gated real-mount test on the macOS host.
- Combined Release Runner/Browser Harness regression: `75 passed, 1 skipped`
  with the same environment-gated control.
- Sacrificial full candidate from the pinned product source and frontend
  lockfile: 7,452 entries, 7,434 writable before, zero writable after, 89
  executable regular files preserved, zero unsupported entries, Browser Harness
  immutable-candidate preflight passed, and aggregate Evidence passed the
  minimum-disclosure scan. Correlation digest:
  `6a4b1d4fb928f099e4066d0986d2fb6cd797dd86e3f6a84eb90db89453a54662`.
- Disposable privileged Linux control: normalization passed from three writable
  entries to zero while preserving its executable; enforced `ro` bind
  presentation, exact non-root identity, ordinary-write denial,
  bytecode-write denial, authorized external-cache write, identical pre/mounted/
  unmounted manifests, owned unmount, and cleanup all passed.
- Versioned no-mutation preflight: every applicable stage passed.
- Real PostgreSQL/Qdrant regression: Docker preflight, PostgreSQL start,
  provisioning, migrations, Qdrant health, candidate presentation, and owned
  cleanup passed. The macOS host then failed closed at the expected Linux-only
  boundary with `CANDIDATE / READ_ONLY_MOUNT_MISSING`; no ownership-labeled
  runner container remained.
- Full repository `make check`: `1238 passed, 23 skipped`; one existing
  Starlette/httpx deprecation warning.
- `pre-commit run --all-files`: passed Ruff lint, Ruff format, and pytest.
- Minimum-disclosure, exact-path/prohibited-scope, diff-check, and
  Secret/private-key scans: passed.

Exact committed head/tree, Draft PR identity, fresh exact-head CI, and the
S5-DEPLOY-069 resumption recommendation are appended after the commit and CI
run. This Evidence grants no deploy, attempt-06, cutover, merge, or release
authority.
