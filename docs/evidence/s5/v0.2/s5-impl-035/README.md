# S5-IMPL-035 — Checkpoint A Evidence

## Boundary

This uncommitted Checkpoint A candidate implements a bounded internal
`journey-event.v1` Server-Sent Events projection for Package 5. It is an
Internal Technical Preview only: process-local, in-memory, single-process replay,
maximum 64 journey buffers, 256 retained events per journey, 15-minute retention,
eight subscribers per journey, 16 KiB allowlisted payloads, and 32 KiB envelopes.

The stream does not own planning, approval, Workflow, Runtime, Evidence, Canonical
Graph, intervention, feedback, or execution semantics. The existing Package 5
coordinator publishes only transitions it observes; replaceable publisher/source
ports isolate that coordination from SSE framing. There is no persistence, durable
or cross-instance replay, public API, CRD, dependency, lockfile, CI, Package 6A, or
Package 6B change.

## Contract and safety evidence

- Every envelope binds `schemaVersion: journey-event.v1`, backend-issued ID,
  positive sequence and aware UTC time, allowlisted event/stage/status, terminal
  marker, stable reason/localization keys, `LIVE_EXECUTION`, the unchanged Package 5
  canonical identity bundle, and a strict typed payload.
- The broker fails closed on conflicting duplicate IDs, gaps, out-of-order events,
  and post-terminal publication. Byte-identical duplicates are idempotent.
- `Last-Event-ID` is evaluated only after trusted-principal authorization and scope
  resolution. Replay returns only retained subsequent events; unavailable cursors
  produce an explicit terminal `RESUME_UNAVAILABLE` event with no snapshot, fixture,
  polling, or synthetic-progress substitution.
- Denied, absent, and foreign-scope journeys share the existing nondisclosing 403
  response shape. Authorization is rechecked before cursor access and before each
  replayed or live delivery. Buffers use exact tenant/security-domain/journey keys.
- Product and Technical views use the same endpoint, strict parser, idempotent
  reducer, backend event IDs, sequences, localization keys, and canonical identity
  values. Technical values remain untranslated. en-US is the existing fallback for
  zh-CN/en rendering.

## Checkpoint A validation record

- Entry: local HEAD, authorized branch, freshly fetched `origin/main`, and exact
  baseline all matched `dd0d3d75b93cddf1394e693fa292e41d81a3dd11`.
- Exact-main CI: GitHub Actions run `33234652122` succeeded for that SHA.
- Open PRs: none at entry. The authorized branch was unattached and collision-free.
- Focused validation: 54 tests passed before final full-suite validation.
- External frontend copy: `npm ci`, ESLint, TypeScript, and Vite production build
  passed in `/tmp/s5-impl-035-frontend.QP43BB`.
- Browser QA: default desktop and 390×844 Product/Technical views rendered with
  intact navigation and no horizontal overflow; live mode with its backend absent
  rendered `JOURNEY_STREAM_UNAVAILABLE` explicitly and did not silently substitute a
  successful live journey.

Final Ruff, complete pytest/make, all-files pre-commit mutation audit, post-hook
`make check`, diff check, and exact-path/status audits are recorded in the terminal
Checkpoint A response after execution.

## Checkpoint C terminal limits validation

The Human Checkpoint C Gate authorized terminal limit validation and remote handoff.
The candidate now has explicit accepted/rejected coverage for every allocated bound:

- 64 journey buffers remain available; a 65th active buffer fails closed with
  `JOURNEY_BUFFER_LIMIT` and cannot evict or disconnect another scope;
- 256 ordered events remain retained; the 257th deterministically evicts only the
  oldest retained event, while subscriber delivery remains complete;
- an event one microsecond inside the 15-minute window remains replayable and an
  event exactly at the 15-minute boundary is expired;
- eight subscribers remain attached and a ninth fails with
  `JOURNEY_SUBSCRIBER_LIMIT` without altering the existing subscribers;
- an exactly 16 KiB payload and exactly 32 KiB envelope validate, while one byte over
  either limit is rejected before publication;
- 200-character identifiers, reason codes and localization keys validate, while 201
  characters fail closed; and
- a full subscriber queue rejects the next publication before buffer or subscriber
  mutation, preventing truncation or partial publication.

Checkpoint C local validation completed on 2026-08-29:

- focused backend/API/compatibility matrix: 61 passed;
- repository-wide Ruff lint and format verification: passed;
- clean external frontend copy at
  `/tmp/s5-impl-035-checkpoint-c-frontend.xz5TiN`: `npm ci`, ESLint, TypeScript and
  Vite production build passed;
- full `make check`: 915 passed;
- all-files pre-commit: Ruff lint, Ruff format and pytest hooks passed;
- hook mutation audit: exactly the fourteen authorized paths remained;
- post-hook `make check`: 915 passed; and
- `git diff --check`: passed.

The suite reports one existing Starlette/httpx deprecation warning. This Evidence
does not claim merge, Durable Integration, production durability, distributed replay,
v0.3 implementation, release acceptance or Human closure. Commit, Draft PR and
exact-head CI facts are reported by the terminal Checkpoint C handoff after they are
observed.

## Limitations and extension seam

Replay is deliberately same-process and best-effort. Restart, expiration, eviction,
or a foreign cursor is unavailable. Disconnect removes only the subscriber. There is
no HA, multi-node, durable replay, exactly-once, certification, or production claim.
A future v0.3 transport/store may replace the publisher/source ports only after its
own architecture and implementation gates; it cannot change this task into a
persistent Event Store or execution authority.
