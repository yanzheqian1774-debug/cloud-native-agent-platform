# Deterministic Release Runner

`scripts/acceptance/release_runner.py` is the repository-owned entrypoint for
v0.2.2 rehearsal preconditions. It consumes only an explicit, versioned JSON
contract and rejects duplicate, missing, unknown, malformed, unpinned, or unsafe
values before service mutation.

## Modes

- `preflight` validates provenance, the locked frontend manifest, interpreter,
  approved source roots, and contract safety without contacting Docker.
- `micro-postgres` additionally verifies the Docker daemon, exact local image
  digests, isolated ports and storage; starts one labeled PostgreSQL 15
  container; provisions an identifier-safe exact validation role; and exercises
  TCP identity, DDL, CRUD, and rollback through the container client.
- `readiness-rehearsal` performs the complete isolated PostgreSQL/Qdrant,
  immutable-candidate, LIVE_DEMO, browser, disclosure, manifest and continuity
  sequence.
- `private-acceptance-precheck` runs the same fail-closed sequence to establish
  readiness for a separately authorized candidate. It never creates or
  authorizes a candidate or public cutover.

Example read-only preflight:

```sh
.venv/bin/python scripts/acceptance/release_runner.py preflight \
  --contract scripts/acceptance/release_contract.v1.json \
  --evidence /private/tmp/s5-impl-078-preflight.json
```

The evidence file is a JSON array. Every item contains exactly schema version,
stage ID, state, start/completion timestamps, exit code, sanitized error
category, optional SQLSTATE/errno, and a correlation digest. Raw subprocess,
Docker, database, browser, URL, path, settings, source, and credential values are
not copied into evidence.

## Ownership and credentials

Each execution generates a cryptographically random ownership token. Container
names are exact and containers carry the same token in the
`io.agent-platform.release-owner` label. Cleanup checks both the in-memory owned
set and the exact label before removal; it never enumerates or pattern-matches
processes or containers.

PostgreSQL credentials are generated per execution, written with mode `0600`,
mounted read-only, never passed as arguments, and unlinked even when a stage
fails. The runner invokes only `psql` inside the pinned PostgreSQL container and
does not depend on a host client.

## Fault controls

`--fault` accepts only the fixed name-conflict, port-conflict, missing-image,
invalid-mount, permission-failure, daemon-unavailable,
storage-resource-failure, and invalid-configuration classes. This option is for
isolated negative-control validation only.

The checked-in contract is host/worktree-specific by design. A different
workspace or release input requires a reviewed new contract version; values are
never taken from ambient release-related environment variables.

The candidate is assembled from the exact product tree plus the exact
acceptance-source Playwright configuration. Its frontend dependencies are
installed from the lockfile and its LIVE_DEMO output is externally
digest-bound. Before the authoritative pre-mount manifest is sealed, the Runner
audits its newly created owned copy without following symlinks, rejects escaping
symlinks, regular files with additional hard links, unsupported entry types,
ownership mismatch, and traversal or chmod failure. It then assigns the exact
non-root validation identity and deterministically normalizes non-executable
regular files to `0444`, executable regular files to `0555`, and directories to
`0555`. Symlink targets are never chmodded. A second complete audit requires
zero writable entries and verifies every preserved executable.

The aggregate normalization Evidence contains only entry count,
writable-before count, writable-after count, executable-preserved count,
unsupported-entry count, and a correlation digest. It contains no absolute path
or individual file name. The Browser Harness independently requires a zero
writable-mode count before browser execution.

For readiness and private-precheck modes, Linux mount authority,
`findmnt`, `setpriv`, and an unprivileged `nobody` identity are mandatory. The
runner bind-mounts an exact runner-owned target, remounts it read-only, verifies
the effective operating-system mount options and source/target inode
correlation, and only then runs ordinary-write and Python-bytecode denial probes
as that exact non-root identity. Mode bits alone are never accepted as the
immutable boundary.

The external validation runtime remains writable by only the selected probe
identity. Pre-mount, mounted-post-probe, and unmounted-post-probe manifests are
written beside the stage evidence. Cleanup verifies the runtime ownership token
and exact target before unmounting; an unowned target is never unmounted or
removed. The underlying candidate must remain manifest-identical after
unmount. Unsupported, non-root, missing-tool, writable-mount, identity-mismatch,
or ownership-mismatch environments fail closed with fixed sanitized codes.

The browser executable path and digest are contract-pinned. PostgreSQL and
Qdrant use exact image digests and loopback-only ports.

## Browser first-failure preservation

When the Harness exits unsuccessfully after browser execution, the Runner first
loads and strictly validates `browser-first-failure.json`, scans it for
prohibited disclosure, and establishes the Runner-side
`<evidence>.browser-first-failure.json` record before raising the classified
`browser-harness` stage failure. Owned-runtime cleanup therefore cannot erase
the only sanitized diagnostic record. The original stage failure remains first;
a later cleanup failure is appended and never overwrites it.

The Runner recognizes Harness schema version 1 only with its original exact
20-field set and schema version 2 only with its exact 22-field set documented in
`ISOLATED_BROWSER_ACCEPTANCE.md`. Mixed, partial, extra-field, contradictory, and
unknown-version records fail closed. Its browser-stage categories
preserve assertion, timeout, HTTP, navigation, process, and diagnostic-gap
boundaries. Missing, malformed, or disclosure-unsafe records fail closed as
`BROWSER_DIAGNOSTIC_GAP`; the Runner never copies raw Playwright reports,
messages, paths, URLs, selectors, exact HTTP status, or browser artifacts. It
does not infer HTTP status or operation identity independently.
