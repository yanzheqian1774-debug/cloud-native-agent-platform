# Original Kimi acceptance: load-existing recovery (G1)

Same acceptance task, no new Session allocation. Human authorized bounded recovery
on 2026-09-16. Base source 89a8dad42e8746d50248015e7c6f8a0cdff7918e,
tree ad3277fa934d0c3bdbeef47af8aea1d6716cd86a. This isolated recovery
branch is a distinct version; the original acceptance export is preserved.

## Scope and implementation

- Add an explicit non-migrating authority foundation path. Validate the existing
  migration checksum, active generation, host control gate and original keys;
  never initialize, activate, repair or fall back to migration. Existing default
  composition behavior stays compatible.
- Add a bounded recovery server entry in scripts/acceptance. Require a private
  preserved-assets manifest binding file contents/owners/modes, database system
  identity, schema inventory and ledger facts. Recheck before bind, take a
  process-lifetime advisory lock, reject competing clients/ports and mismatch.
- Assemble only existing BFF authentication, authorized Problem LIST/READ and
  original Draft invocation READ. No provider transport, budget mutator, creation
  or grant-administration write route is mounted. Reject all mutations except
  the existing login/logout protocol; never mount the initialization fixture.
- Serve a separately built fixed-source frontend with its existing manual mode
  (VITE_PROBLEM_DRAFT_ASSISTANCE disabled). No frontend source changes and no
  restoration of model text as if retained. Original dist and source untouched.
- No public contract, identity, authorization, lifecycle or database schema
  change; no new infrastructure. No formal Problem creation in this task.

## Validation and delivery

Preserve source diff/config/logs and a consistent pg_dump; decode the full archive
without restoring the original database. Unit tests isolate missing/tampered
assets, wrong DB identity, incompatible schema, epoch mismatch, concurrency and
write-route rejection. Run make check and frontend lint/build. Before and after
actual startup compare protected files, schema, business/authority facts and
ledger snapshots; authentication may append only its normal session records.
Read formal state through the existing authorization boundary. An empty authorized
complete LIST is evidence; 404, denied or failed reads are not absence evidence.
Append results to the original parameter record. Screenshot only the synthetic
manual draft, stop before Confirm Create. No model call, reset, expiry extension,
merge, deployment, release or cleanup.

## Risks and stop conditions

The original launcher rewrites keys and seeds state and must not run. Historical
loaded versions cannot be inferred from the current export or mtime. Preserve
uncertain provenance explicitly. Missing keys, stale host control, incompatible
DB/ownership, competing writer or insufficient current read grants fail closed;
none permits asset replacement or a new authorization decision.
