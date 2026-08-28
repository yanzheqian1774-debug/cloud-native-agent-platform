# S5-IMPL-032 — Checkpoint A Evidence

## Scope

Checkpoint A implements the bounded internal Package 4 Knowledge path authorized by
S5-PLAN-003, S5-ARCH-011, S5-ARCH-010, and the Human-accepted Checkpoint 0 Evidence.
It remains an in-memory, read-only Technical Preview slice.

## Implemented boundary

- one immutable, versioned and digest-bound Knowledge Pack;
- separate exact-scope authorization decisions validated before source reads;
- deterministic bounded retrieval with stable ordering and explicit failure states;
- immutable append-only in-memory `KnowledgeRetrievalEvidence`;
- citations bound to exact versions, digests, authorization, Evidence and provenance;
- two sanitized `DEMO_CONFIGURATION` assets with no production authority.

The implementation adds no public API, CRD, Workflow lifecycle, shared DTO, Canonical
Graph, persistence, dependency, CI, frontend, connector, MCP authority, ingestion,
publication, writeback, credential, or permission-grant surface.

## Security boundary

Missing, denied, expired, revoked, malformed, foreign-scope, purpose-mismatched,
version-mismatched, digest-mismatched, policy-mismatched, or replay-conflicting
authorization fails before the first Knowledge-source read. The denial response is
bounded and does not expose Pack or document existence, identity, version, title,
count, section, chunk, digest, rank, citation, content, or internal policy reason.

Timing equivalence is not claimed. Tests instead verify zero source reads, identical
bounded denial shape for absent and invalid authority, no source-derived fields, and a
bounded local execution time. Operational constant-time behavior remains outside this
Technical Preview claim.

## Limits

The enforced ceilings are: one configured Pack; 8 documents; 32 sections per
document; 128 chunks per document; 256 Pack chunks; 4 KiB normalized chunk content;
512 KiB Pack content; 16 KiB request; 2,000-character query; 16 allowlisted filters;
16 results/citations; 32 KiB returned content; and 32 reason/limitation codes.
Overflow rejects without truncation or partial retrieval. The minimum implementation
has no cache.

## Demo assets

`examples/s5-v0.2-supplier-quality/knowledge/knowledge-pack-v1.json` and
`examples/s5-v0.2-supplier-quality/knowledge/8d-procedure-v1.md` are sanitized,
immutable, exact-version supplier-quality Demo inputs. Repository presence does not
publish them or grant enterprise, credential, ingestion, or production authority.

## Validation

Checkpoint A validation covers exact accepted/rejected limits, identity and digest
mutation, NFC normalization, authorization failure classes with instrumented zero
reads, tenant/security-domain isolation, nondisclosure, deterministic ordering and
ties, complete status vocabulary, no synthetic fallback, Evidence replay and
allowlisting, exact citation binding, Demo asset checksum/provenance/version/ceiling,
and absence of write or connector ports.

Repository-wide validation and the final thirteen-path audit are recorded in the
Checkpoint A response. Changes remain uncommitted pending the Human Checkpoint C gate.

## Checkpoint C terminal handoff

Checkpoint C independently revalidated the unchanged Checkpoint A implementation:

- focused Ruff lint and format checks passed;
- the five focused test files passed with `38 passed`;
- `make check` passed with `828 passed` and one existing Starlette/httpx
  deprecation warning;
- `pre-commit run --all-files` passed;
- `git diff --check` passed;
- exact thirteen-path, shared-governance, Package 3, and prohibited-impact audits
  passed; and
- the two Demo assets passed JSON, version, provenance, checksum, canonical digest,
  sanitation, and size checks.

The implementation commit is `75f7e4dbaa3ac687f479118663b3ca93e0882204` with exact parent
`24525693464e3604d3d93619b606572317217cd9`. This Evidence file is the only path
reserved for the second and final terminal commit.

At terminal-Evidence commit time, normal push, Draft PR creation, and exact-head CI
observation are intentionally `PENDING`. They are recorded from GitHub-native evidence
in the final Checkpoint C response without amending this commit. The PR must remain
Draft/open/unmerged; no REL Session is allocated or started by this handoff.
