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
digest-bound. For readiness and private-precheck modes, Linux mount authority,
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
