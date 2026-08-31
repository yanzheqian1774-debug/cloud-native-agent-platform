# S5-IMPL-050 Checkpoint A Evidence

## Authority and baseline

- Authorized baseline: `b21888277de3f285bfb349a1e43901f69abf70bb`.
- Exact baseline CI: `33395352329 / SUCCESS` (Human supplied).
- Branch: `codex/s5-impl-050-knowledge-retrieval-quality-operations`.
- Gate: `G1`, bounded by v0.2-CONTROL-003 and accepted S5-ARCH-018.
- Durable-main assembly baseline: `f5294c7fe22f60074b1037036a99445d9a33db0f`.
- Exact assembly-baseline CI: `33405497333 / SUCCESS`.
- Accepted pre-assembly source head: `0e498291b8ff3b9fa36c9389e45bbbcad3f398af`.
- Normal merge commit: `0fbff60bc945155d0ab1371af3e412277a37e991` with ordered parents
  `0e498291b8ff3b9fa36c9389e45bbbcad3f398af` and
  `f5294c7fe22f60074b1037036a99445d9a33db0f`.
- Status: `FINAL_INTEGRATION_ROUTING_CANDIDATE`.

## Final migration assembly

Durable migration `0004_skill_mcp_professional_experience.sql` entered main through
PR #102 and was incorporated by the normal two-parent merge recorded above. The final
migration directory is contiguous and ordered exactly `0001 -> 0002 -> 0003 -> 0004
-> 0005`; there is no placeholder, duplicate, reorder, skipped number or symlink.

Migrations `0001` through `0004` are byte-for-byte identical to durable main. S5-IMPL-050
owns only `0005_knowledge_quality_operations.sql`, whose SHA-256 is
`f481454ca9e217663cb151baa4b702a9a03337e77198f8e922266e75b15bca36`. Migration
`0004` retains its mandated SHA-256
`437b128d3439cd961a0c8b4f210fc175cfe347c07cdc93035814376f4f35cc82`.

The exact five-file chain was applied sequentially to a clean PostgreSQL 15 database.
All four scoped schemas were present afterward. Adapter startup, persisted restart
recovery and controlled checksum-tamper rehearsals passed: altered `0004` and `0005`
checksums failed closed, exact checksums were restored, and compatibility revalidated.

## Implemented result

- Search Playground exposes explicit `LEXICAL`, `SEMANTIC` and `HYBRID` modes, Top-K,
  stable ranks/scores, raw authorized recall and exact source/revision/document/chunk
  Citation provenance.
- Chinese lexical retrieval uses `CJK_BIGRAM_V1`: NFKC normalization, Latin
  case-folding, stable word extraction and deterministic CJK bigrams.
- Hybrid retrieval uses deterministic reciprocal-rank fusion with `k=60`, zero for an
  absent rank and canonical Knowledge/document/chunk identity tie-breaking.
- Evaluation persists versioned datasets, runs and metric facts; binds policy,
  tokenizer, fusion, Knowledge authority/revision and Qdrant snapshot identities;
  calculates Recall@K, Precision@K, MRR, Citation completeness and unauthorized-result
  count; returns `NOT_MEASURABLE` when relevance truth is absent.
- Before/after comparison renders exact run and dataset identities plus neutral metric
  deltas. If either run lacks ground truth, comparison remains `NOT_MEASURABLE`; no
  improvement claim is inferred.
- Duplicate scanning records exact digest matches and bounded token-set near candidates
  with `NORMALIZED_TOKEN_SHINGLE_V1`, threshold `0.6` and pending Human decisions. It
  does not delete, merge or rewrite history.
- The Product View provides a Human review queue with exact/near classification,
  algorithm version, threshold, source identities and bounded `DUPLICATE`, `DISTINCT`
  or `NEEDS_INVESTIGATION` decisions. Decisions are persisted as record-only facts.
- Summaries use `DETERMINISTIC_EXTRACTIVE_V1`, model `NOT_APPLICABLE`, generated-content
  digest and exact authorized revision/chunk Citations.
- Import preview accepts bounded UTF-8 `txt`, `md` and strict `jsonl`, rejects archives,
  unknown fields and invalid controls, and persists an idempotent digest-derived
  `PREVIEW` job. Accepted records execute to deterministic, idempotent Knowledge Draft
  and revision identities; progress, accepted/rejected counts, partial/terminal state
  and controlled retry are persisted without exposing rejected content. Validation,
  review and publication remain separate. Export contains only scoped authorized
  revision identities/digests, Citations and evaluation facts.
- Search filters include authorized Pack, source, document/content type, exact revision
  and active snapshot context. Filter values and empty/count states are derived only
  after the trusted scope is applied.
- Loading, saving, empty, partial, denied, validation-error, retryable and
  recovery-required states are represented using the existing accessible Workbench
  patterns.
- Product and Technical sibling projections expose the same canonical Knowledge
  identity plus the PostgreSQL authority/Qdrant-derived boundary and deterministic
  quality contract.
- Migration `0005` adds scoped, digest-bound persistence for import jobs, evaluation
  datasets/runs, retrieval configurations/metric facts, summaries, duplicate
  candidates and Human decisions.

## Validation evidence

- Focused Knowledge quality/security, PostgreSQL, pinned Qdrant `v1.15.4`, restart,
  Agent Definition and Skill/MCP preservation suite: `19 passed`.
- Clean PostgreSQL 15 migration chain: exact `0001 -> 0005` applied; startup,
  restart recovery and fail-closed checksum behavior passed.
- `make check`: `1084 passed, 0 skipped`; Ruff lint/format passed.
- Frontend `npm run lint`: passed.
- Frontend `npm run build`: passed.
- Real Chromium Playwright Knowledge journey: `1 passed`.
- Complete Agent, Knowledge and Skill/MCP Chromium regression: `3 passed`.
- `git diff --check`: passed.

The browser journey used real backend APIs, PostgreSQL authority and Qdrant, exercised
hybrid ranking/Citations, metadata filters, two-run metric comparison, deterministic
summary, partial import/Draft execution/idempotent retry and Human duplicate decision;
verified identical denied/absent disclosure; restarted the backend and recovered the
same identities; and exercised purge/recovery behavior.

## Skipped-test reconciliation

The earlier `make check` run skipped exactly:

1. `test_agent_definition_postgres.py::test_migration_checksum_and_optimistic_concurrency`;
2. `test_agent_definition_restart_recovery.py::test_postgres_restart_recovers_identity_revision_and_digest`;
3. `test_skill_mcp_postgres.py::test_real_postgres_migration_persistence_and_optimistic_concurrency`.

Each was an expected external-service gate: only the Knowledge PostgreSQL URL was set
in that run. The completion run set the Agent Definition, Skill/MCP and Knowledge test
database URLs to the isolated real PostgreSQL service. All three executed and passed;
the final `make check` contains zero skips. There is no unresolved validation gap.

## Limitations and next Gate

- No production-quality, release, certification, merge, deployment, REL allocation,
  Session-closure or v0.2.2 completion claim is made.

Next: push the validated source, require fresh exact-head CI and clean GitHub
mergeability, then route PR #103 as Ready for Human Durable Integration allocation and
merge decision. This Session does not merge the PR or allocate the REL identifier.
