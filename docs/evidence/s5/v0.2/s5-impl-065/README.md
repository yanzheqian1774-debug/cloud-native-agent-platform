# S5-IMPL-065 Checkpoint A Evidence

## Authority and entry gate

- Authorized baseline: `7e9af320053e9451bad112755cebbe1109a39bdd`.
- Entry `HEAD` and `origin/main`: exact authorized baseline.
- Exact-main CI: `33479506470 / SUCCESS` for the authorized SHA.
- Branch: `codex/s5-impl-065-knowledge-purge-recovery-determinism` in an
  isolated Codex worktree.
- GitHub global issue/PR search returned no pre-existing `S5-IMPL-065`.
- S5-IMPL-050 remains closed and merged as PR #103.
- S5-IMPL-054 remains open, Draft and idle as PR #109; it was not modified or
  resumed.
- Open-PR file ownership and active-task inspection found no Knowledge writer or
  collision on either authorized path.

## Diagnosis

Classification: `TEST_PRECONDITION_MISSING`.

The backend purge implementation derives the external cleanup set from persisted
`indexSnapshots`. If that set is empty, a successful SQL purge and tombstone are the
correct result even when Qdrant has no collection. If at least one exact snapshot is
persisted and Qdrant cannot complete deletion, the backend persists
`RECOVERY_REQUIRED` and returns HTTP 202.

The browser test previously waited only for a lifecycle string, removed the Qdrant
collection, and asserted the first matching `RECOVERY_REQUIRED` text. It did not prove
that the exact selected Knowledge identity owned a published revision, active index
snapshot, chunks and real Qdrant points before inducing failure. The unscoped
`.first()` could also hide multiple matching regions. Production behavior is not
defective and the expected recovery semantic is valid.

## Fresh real-service diagnostic

The diagnostic used disposable `postgres:15-alpine` and
`qdrant/qdrant:v1.15.4` containers with a clean database and collection.

The exact partial-failure identity completed Draft, validation, exact-digest Human
review, publication and real ingestion before Qdrant was made unavailable:

- Knowledge: `knowledge:327530f2-ad30-42aa-adaf-b40ebd126ef6`;
- Revision: `knowledge-revision:fbbfc47f-2b84-4840-8934-ea8ff45b4621`;
- Revision digest:
  `3b953ef072865cd2f20774175a97f9993e253cd9fafdbbbf0ffabccfbbba7794`;
- Snapshot: `index-snapshot:77d854ae-e5a2-4b95-b209-06336f356baa`;
- Ingestion job: `ingestion-job:3388406a-9a70-4744-96ad-fae3726d7115`;
- Chunks: `document:8d-procedure:chunk:1` and
  `document:8d-procedure:chunk:2`;
- Qdrant points: `d4647d54-c21d-5134-a1bf-93b3c503d509` and
  `7d1091c9-8a9c-5f09-b4eb-07f2847c6df7`.

After the Qdrant collection became unavailable, the exact purge request returned HTTP
202. The response and subsequent authoritative GET agreed on Product and Technical
identity and persisted:

- lifecycle: `RECOVERY_REQUIRED`;
- purge status: `RECOVERY_REQUIRED`;
- remaining snapshot:
  `index-snapshot:77d854ae-e5a2-4b95-b209-06336f356baa`;
- aggregate version: `6`.

Direct SQL inspection found the Knowledge aggregate with that recovery state and one
persisted index snapshot. No purge tombstone existed for the partial failure. Direct
Qdrant inspection returned 404 for the unavailable collection. The separate successful
journey returned HTTP 200 and retained only its authorized non-sensitive SQL tombstone.

## Test-only correction

Only `console/frontend/tests/e2e/knowledge-workbench.spec.ts` was changed. The test now:

- binds the partial-failure journey to the exact Knowledge, Product and Technical
  identity;
- proves the exact published Revision and digest, active snapshot and chunk identities;
- scrolls live Qdrant with the exact scope/Knowledge/snapshot filter and requires at
  least one matching real point before inducing failure;
- captures and asserts the exact purge response is HTTP 202;
- asserts the backend response and a subsequent authoritative fetch contain the same
  persisted recovery state and remaining snapshot;
- scopes the visible recovery assertion to the selected exact Knowledge detail region;
- removes `.first()` from the recovery assertion;
- preserves the earlier successful-purge journey separately.

No production source, migration, dependency, S5-IMPL-054/056/057, Runtime, OpenClaw,
Gateway, Operator, CRD, PR #109 or deployment path changed.

## Validation

- Corrected focused Knowledge Playwright journey against clean PostgreSQL 15 and
  Qdrant 1.15.4: `1 passed`, one worker, zero retries.
- Complete clean serialized Playwright suite against real services: `9 passed`, one
  worker, zero retries and zero skipped tests.
- Frontend lint: passed.
- Frontend production build: passed.
- `make check`: passed; Ruff lint/format and `1148 passed`, zero skipped tests, with
  one existing Starlette/httpx deprecation warning.
- Pre-commit: passed; Ruff lint, Ruff format and pytest hooks passed.
- `git diff --check`: passed.
- Exact-path, prohibited-scope and secret-pattern audits: passed.

Fresh exact-head CI and the separate correction PR are recorded after the bounded
commit is pushed.

## Routing

Checkpoint A routes to Human review and a separate Durable Integration allocation.
S5-IMPL-054 remains in controlled pause and must not resume automatically.
