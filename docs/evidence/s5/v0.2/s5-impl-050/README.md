# S5-IMPL-050 Checkpoint A Evidence

## Authority and baseline

- Authorized baseline: `b21888277de3f285bfb349a1e43901f69abf70bb`.
- Exact baseline CI: `33395352329 / SUCCESS` (Human supplied).
- Branch: `codex/s5-impl-050-knowledge-retrieval-quality-operations`.
- Gate: `G1`, bounded by v0.2-CONTROL-003 and accepted S5-ARCH-018.
- Status: `PRODUCT_COMPLETION_COMMITTED_CANDIDATE / EXTERNAL_MIGRATION_GATE`.

## Checkpoint 0 migration determination

The baseline has no repository-wide ordered migration runner. Each product-continuity
adapter directly applies one named migration and checksum-binds its own schema table.
Consequently `0005_knowledge_quality_operations.sql` can exist and be exercised in
this isolated branch while `0004` is absent. This is a runner gap, not evidence that
the mandatory `0001 -> 0002 -> 0003 -> 0004 -> 0005` chain has passed. No fake `0004`
and no relaxed contiguous-order validation were introduced.

Final migration-chain, PR-readiness and exact-head CI validation remain blocked until
S5-IMPL-049 has durably integrated migration `0004` and that main is merged normally
into this branch.

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

- Targeted deterministic/security suite: `25 passed`.
- Real PostgreSQL 15 + pinned Qdrant `v1.15.4`, import/comparison/duplicate and restart
  suite: `16 passed`.
- `make check`: `1083 passed, 0 skipped`; Ruff lint/format passed.
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

- Migration `0004` is absent by design; the complete ordered chain and final restart
  migration rehearsal are not claimable.
- No production-quality, release, certification, merge, deployment, REL allocation or
  Session-closure claim is made.

Next: wait for Human confirmation that S5-IMPL-049 and its Durable Integration Session
have completed. Durable integration still requires normal advanced-main merge, exact
changed-path and byte-identity revalidation, the real `0001 -> 0005` migration chain,
complete service/browser regression and fresh exact-head CI before converting the
Draft PR to Ready for Review.
