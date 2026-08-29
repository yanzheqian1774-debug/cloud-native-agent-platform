# S5-IMPL-036 — Checkpoint A Evidence

## Scope

Package 7 adds the deterministic, sanitized supplier-quality Demo Scenario Pack
for the exact `s5-v0.2-supplier-quality-v1` scenario and
`s5-v02-supplier-quality-demo` namespace. It owns Demo configuration and local
materialization/reset only.

## Architecture and authority boundary

- G1 implementation within S5-ARCH-006/010/011/012 and S5-PLAN-003 Package 7.
- No public API, CRD, API group, shared DTO, Canonical Graph, lifecycle,
  persistence, dependency, lockfile, CI, frontend, Runtime, credential,
  permission, publication, or production Knowledge change.
- Catalog files declare already-published roles; they do not publish or grant.
- The existing Knowledge Pack is referenced, copied byte-for-byte during local
  materialization, and checksum-validated. Its two source files remain unchanged.

## Determinism and destructive boundary

`bootstrap.sh` verifies every input checksum before writing. It requires the
exact scenario, namespace, and an absolute target whose final component is the
namespace. Repeated bootstrap replaces only a correctly marked target and
reproduces identical content.

`reset.sh` additionally requires exact confirmation and deletes only a target
with the exact two-line scope marker. Missing, implicit, relative, root,
wildcard-like, broad, default-context, namespace-mismatched, cross-scope, or
unmarked targets fail closed. Repeated reset is a no-op.

## Provenance and sanitation

- Configuration and the read-only Knowledge inputs: `DEMO_CONFIGURATION`.
- Historical records: `SYNTHETIC_HISTORY` and explicitly not live Evidence.
- Runtime-owned outputs: `LIVE_EXECUTION`, with zero records included here.
- Supplier names, lots, cases, and history are fictional sanitized Demo values.
- The pack contains no secrets, personal data, credentials, permissions,
  production authority, hidden fallback, or fabricated live Evidence.

## Validation

Checkpoint A validation results are returned to v0.2-CONTROL-002 after focused
tests, Ruff, `make check`, all-files pre-commit plus mutation audit,
`git diff --check`, checksum/Knowledge/sanitation/provenance review, exact
twelve-path audit, and final branch/HEAD/worktree audit. All changes remain
uncommitted for the Human Checkpoint C gate.

## Checkpoint C terminal validation

Checkpoint C revalidated the unchanged Package 7 implementation against the
exact `c033cb31c9cf1287419a81d2c809bc90dffb225d` baseline:

- focused Ruff lint and format checks passed;
- focused Package 7 tests passed with `11 passed`;
- `make check` passed with `926 passed` and one existing Starlette/httpx
  deprecation warning;
- `pre-commit run --all-files` passed, and before/after hashes for all twelve
  paths plus Git status were unchanged;
- all ten checksummed inputs verified, including the two unchanged Knowledge
  files;
- clean-target repeated bootstrap produced identical content, and repeated
  exact-target reset passed;
- `git diff --check`, exact twelve-path, sanitation, provenance, branch,
  baseline, ownership, and prohibited-impact audits passed.

At commit time the normal branch push, Draft PR, and automatically triggered
exact-head Quality Gates and Frontend Quality Gates are intentionally
`PENDING`. GitHub-native terminal results are returned to v0.2-CONTROL-002
without amending this Evidence file. The PR must remain Draft, open, and
unmerged; no REL or downstream session is started here.

## Bounded CI portability correction

Exact-head CI run `33265516363` on commit
`62ce9109abbeab58308fc4e94bdbcc5194f1a1ca` completed with Frontend Quality
Gates successful and Quality Gates failed. The only failure was the focused
Knowledge immutability test invoking `git show` against the authorized baseline
commit. That historical object/path lookup was available locally but was not a
portable assumption for the CI checkout.

The bounded correction removes only that Git-history dependency. It retains
strict integrity by checking both current read-only Knowledge paths against
their exact accepted SHA-256 values, checking those same values are bound in
`checksums.sha256`, checking the scenario manifest binds both exact paths, and
checking bootstrap only copies those sources into the explicit target while
reset never addresses a Knowledge source path. No Knowledge content or Package
behavior changed.

Correction revalidation completed as follows:

- the directly failed test passed with `1 passed`;
- all focused Package 7 tests passed with `11 passed`;
- focused Ruff lint and format verification passed;
- both pre-hook and post-hook `make check` passed with `926 passed` and the one
  existing Starlette/httpx deprecation warning;
- all-files pre-commit passed with unchanged correction-path hashes and Git
  status;
- all ten checksum entries passed, including the two exact Knowledge digests;
- repeated clean-target bootstrap produced identical relative-tree digest
  `49fc1446f4887ee8b9a38c2df65c1c99b26b0e6576517ffecc7691c39fee9414`;
- repeated exact-target reset, Knowledge immutability, `git diff --check`,
  two-correction-path scope, and aggregate twelve-path PR inventory passed.

The correction commit, normal push, and replacement exact-head CI are
intentionally `PENDING` at this file revision and are reported from Git and
GitHub without amending this Evidence file.
