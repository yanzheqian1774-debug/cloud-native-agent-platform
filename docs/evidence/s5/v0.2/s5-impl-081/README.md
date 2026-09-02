# S5-IMPL-081 — Enforced Read-Only Candidate Boundary Correction

## Scope and authority

This bounded correction changes only the versioned Release Runner, its focused
tests, Release Runner engineering documentation, and this evidence package. It
does not change product, backend, migrations, Runtime, Operator, OpenClaw,
public/staging deployment, S5-DEPLOY-069, attempt-06, or prior rehearsal
evidence.

Entry revalidation started from durable `origin/main`
`6cfa523a6bc97ea3c8f7386693e92759cd046476`, whose exact-main CI completed
successfully. Suffix `080` is allocated to an active isolated OpenClaw provider
task; `081` was otherwise unused. No open PR existed, and the active `080`
provider scope did not overlap the Release Runner paths.

## Corrected boundary

- A writable underlying candidate is owned by an explicit non-root validation
  identity, making chmod-only denial insufficient by construction.
- The presented candidate must be a Linux bind mount with an effective `ro`
  VFS option and source/target device/inode correlation.
- Ordinary-write and Python-bytecode probes run through `setpriv` as the exact
  selected uid/gid; uid or gid zero is forbidden.
- A separate validation-runtime directory is writable by that identity and is
  exercised as the authorized external cache boundary.
- Pre-mount, mounted-post-probe, and unmounted-post-probe manifests are retained
  and must be identical.
- Only the exact runner-owned mount target may be unmounted. Cleanup preserves
  the first failed stage and verifies the underlying candidate after unmount.
- Fixed sanitized codes cover mode-bit-only, root identity, missing/invalid
  read-only mount, identity mismatch, and unexpected ordinary/bytecode success.

## Checkpoint evidence

Fresh local results before commit/PR:

- Focused runner suite: `38 passed, 1 skipped`; the skip is the intentionally
  root/Linux-gated real-mount test on the macOS host.
- Existing combined Runner/Harness regression: `65 passed, 1 skipped` with the
  same environment-gated integration control.
- Disposable privileged Linux positive control: passed enforced `ro` bind
  presentation, exact non-root identity, ordinary-write denial, bytecode-write
  denial, authorized external-cache write, three identical manifests, and
  owned unmount. Retained manifest evidence SHA-256:
  `bf496f5757b627c3bddb437614a790dc242efe98becc75106fb01b7cf0baf236`.
- Versioned no-mutation preflight: passed all applicable stages.
- Real PostgreSQL/Qdrant orchestration: provenance, Docker preflight,
  PostgreSQL start/provision/migrations, Qdrant health, candidate presentation,
  and owned cleanup passed. The macOS host then failed closed before acceptance
  with `CANDIDATE / READ_ONLY_MOUNT_MISSING`; no owned container remained.
- Full repository `make check`: `1228 passed, 23 skipped`; one existing
  Starlette/httpx deprecation warning.
- `pre-commit run --all-files`: passed Ruff lint, Ruff format, and pytest.
- Minimum-disclosure scan of preflight, fail-closed readiness, and retained
  manifest artifacts: passed.
- Exact-path/prohibited-scope and Secret/private-key scans: passed.

Exact committed head/tree, changed paths, exact-head CI, Draft PR identity, and
the S5-DEPLOY-069 resumption recommendation are appended after the commit and
fresh CI run. This evidence grants no deployment, attempt-06, cutover, merge,
or release authority.
