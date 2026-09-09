# S5-V023-IMPL-312 Knowledge Document and Retrieval Experience

## Status and fixed baseline

- Gate: `G1`; Human-authorized bounded implementation.
- Base/source: `f189212232fc194859a695f0307e83b0c7b73c0f`.
- Base tree: `a8a9251d5d2e47605d18bb63e362164ec4c920d2`.
- Branch: `codex/s5-v023-impl-312-knowledge-document-retrieval-experience`.
- Delivery status remains `PARTIAL_DRAFT` until the formal entry, real PostgreSQL,
  Qdrant, HTTP, and browser evidence described below exists.

## Existing authority and bounded change

The existing Knowledge lifecycle service remains the sole owner of Knowledge,
source, document, revision, digest, publication, ingestion, snapshot, retrieval,
and citation identities. PostgreSQL remains authoritative and Qdrant remains a
derived index. Existing client-supplied `sourceId` and `documentId` inputs remain
accepted for compatibility; new document-management requests omit them so the
backend owner generates both identities. Historical identifiers, revisions,
digests, and citations are not rewritten.

This increment adds a bounded, transient document parsing preview for text-bearing
PDF and `.docx`. It does not persist the original binary and therefore is not a
complete file-management capability. Confirmation creates an ordinary Knowledge
Draft containing extracted text and truthful parser-provided locations, then uses
the existing validate, Human review, publish, and ingestion transitions.

## Affected components and interfaces

- `knowledge_document_parser.py`: content-signature detection, PDF/DOCX parsing,
  bounded file/zip/page/paragraph/extracted-text limits, timeout, and stable errors.
- `knowledge_api.py` and `knowledge_schemas.py`: one private parse-preview endpoint
  plus backwards-compatible optional generated identity/document metadata fields.
- `knowledge_ingestion.py` and `knowledge_lifecycle_service.py`: persist parsed
  segments and real locations without changing historical chunk/digest behavior.
- Knowledge frontend API/page/local CSS: upload/drop, preview, generated-ID draft,
  truthful processing stages, Chinese source/citation presentation, retrieval score
  explanation, page partitioning, and safe local-time formatting.
- Focused backend and browser tests plus task-owned synthetic PDF/DOCX fixtures.
- `pyproject.toml`/`uv.lock`: `pypdf` is the only new parser dependency. DOCX parsing
  uses bounded standard-library ZIP/XML processing and never executes macros,
  embedded programs, or external links.

No migration, shared BFF/authority/bootstrap, app route, global style, CRD, public
API, or Kubernetes authority change is included.

## Limits and failure behavior

- Upload body: at most 8 MiB; extracted normalized UTF-8 text: at most 512 KiB.
- PDF: signature-verified, text-bearing, unencrypted, at most 200 pages. OCR,
  scanned/image-only PDFs, forms, annotations, and image extraction are unsupported.
- DOCX: OOXML package signature/required members verified; at most 256 ZIP entries,
  16 MiB total expanded bytes, 100:1 per-entry expansion ratio, and 512 extracted
  paragraphs. Legacy `.doc`, macro-enabled packages, embedded objects/programs,
  images, and external-link fetching are unsupported.
- Parse wall time: at most 10 seconds in a terminated worker process.
- A declared extension or media type is corroborating metadata, never the sole type
  decision. Mismatch, corruption, encryption, empty extraction, limit, and timeout
  failures use distinct stable reason codes and Chinese UI explanations.
- Upload/parse success never implies validation, publication, indexing, or
  retrievability. Empty extraction cannot create a Draft.

## Test strategy

1. Parser unit tests use task-owned synthetic Chinese PDF/DOCX, corrupt/mismatched,
   empty, encrypted/macro/zip-limit fixtures, and truthful location assertions.
2. Lifecycle/API tests prove server-generated source/document identity, backwards
   compatibility for existing IDs, immutable successor/citation behavior, limits,
   and scoped backend filters.
3. Frontend tests cover drop/select, Chinese filenames/content/errors, preview,
   exact stages, retrieval rank/source/score meaning, empty versus failure, late
   responses, CAS input preservation, keyboard flow, local time, and 390px layout.
4. Real task-owned PostgreSQL/Qdrant and formal HTTP/browser validation proves the
   persisted text, generated identities, real indexing, expected/no-answer queries,
   denial behavior, and restart readback. Mocks and unit tests are reported
   separately.
5. Run frontend lint/build, focused tests, then `make check`; inspect diff/status.

## Architecture boundaries deferred for Human decision

Original-file storage/lifecycle and artificial-QA lifecycle/authority are absent.
They are specified as minimal candidates in the task implementation record, remain
unimplemented, and require Human architecture acceptance before any persistence,
migration, retrieval blending, or permission semantics are added.

### Candidate A: original-file lifecycle

- Authority: a future Knowledge-owned binary object record; PostgreSQL would own
  metadata/lifecycle and an explicitly selected replaceable blob provider would own
  bytes. Extracted text must not become the binary authority.
- Identity and versioning: immutable `fileId` plus content digest, media type, byte
  length, storage-provider reference, retention state, and exact association to the
  Knowledge document revision produced from that file.
- Operations: upload, authorized metadata/read/download, retention or legal hold,
  and governed purge with auditable partial-failure recovery. Download authorization
  must be evaluated independently from extracted-text retrieval authorization.
- Compatibility: existing text-only revisions and citations remain valid and do not
  acquire invented file references. No migration or provider selection is proposed
  by this task.

### Candidate B: artificial-QA lifecycle and combined retrieval

- Authority: a future Knowledge-owned, versioned QA record with immutable identity,
  state, question/synonyms, answer, author, and exact source
  `knowledgeId/revisionId/documentId/chunkId/chunkDigest` evidence.
- Governance: draft, validate, Human review, publish, supersede/disable, and purge;
  source revision changes or loss of authorization make a QA record stale or
  unavailable rather than silently rebinding it.
- Retrieval: source chunks and published QA entries remain distinguishable result
  classes. Any combined ranking policy, weights, evaluation vocabulary, and Qdrant
  payload shape require an accepted versioned contract. A QA hit must preserve the
  original evidence reference and cannot widen source visibility.
- Compatibility: current Knowledge retrieval and citations remain unchanged. No
  QA persistence, migration, index blend, or permission semantics are implemented
  by this task.

## Recovery validation evidence (2026-09-09)

- Previous-session focused backend run: 61 tests passed; frontend lint/build passed;
  two Playwright transport/browser cases passed. The two browser cases use explicit
  `page.route` fixtures and are not real-service acceptance.
- Task assets: `s5-v023-impl-312-postgres` on `127.0.0.1:55412` and
  `s5-v023-impl-312-qdrant` on `127.0.0.1:56312`, with task labels, exclusive
  volumes/network, and runtime root `/private/tmp/s5-v023-impl-312`.
- Formal immutable harness attempt passed build-identity and PostgreSQL-role
  preflight, then failed before backend health and before every target browser
  assertion. Exit code was 2; diagnostics are retained under
  `/private/tmp/s5-v023-impl-312/runtime-real-1`.
- Cold candidate initialization took 72.02 seconds while creating the existing 66
  schema tables. A warm import still took 28.33 seconds. A Knowledge-only retry then
  failed its existing five-second PostgreSQL pool deadline with
  `KNOWLEDGE_STORAGE_UNAVAILABLE`.
- Twelve direct task-database connection probes produced five successes and seven
  three-second timeouts; successful samples took 1.688 to 6.786 seconds. Therefore
  the fixed 20-second backend health deadline was not extended and the real browser
  journey was not rerun without new readiness evidence. Delivery remains
  `PARTIAL_DRAFT`; no mock result substitutes for this failure.

## Browser diagnostic evidence supplement (2026-09-10)

The Human-authorized diagnostic supplement adds no product behavior and changes no
browser assertion, selection, retry, skip, timeout, worker count, or success gate.
The real Knowledge journey now attaches five closed operation identities through a
dedicated reporter. The reporter retains only validated repository-relative test
paths, allowlisted scenario identity or `UNKNOWN`, closed operation identity or
`UNKNOWN`, final test status, closed static error classification, and
selected/executed/passed/failed/skipped/flaky counts.
It never serializes test titles, error text, request/response data, document content,
environment variables, screenshots, traces, videos, or the raw Playwright report.

The reporter continues to provide the harness-owned transient operation file, while
also writing a separate sanitized aggregate to
`$RUNNER_TEMP/s5-v023-impl-312-browser-diagnostics/browser-diagnostics.v1.json`.
The harness may delete its transient file without affecting the aggregate. The
Browser CI job invokes both JSON and structured reporters, then uses an unconditional
artifact step to retain only the sanitized aggregate for seven days. Missing output
fails that artifact step independently; reporter attachment or file-write failure
does not swallow or replace the original test result.

Focused validation before push:

- synthetic reporter success, two-failure, absent-stage, sanitization, attachment
  failure, and diagnostic-write failure cases: 3 passed;
- reporter compatibility and release-contract tests: 37 passed;
- frontend ESLint and production build: passed;
- CI YAML parse and `git diff --check`: passed.

Automatic CI checkout identity, counts, retained artifact readability, and any new
failure stage remain pending the ordinary non-force push. A new result will not be
used to infer or backfill the two unknown failures from run `34370621442`.

## Recovery continuation checkpoint (2026-09-10)

- Recovery confirmed branch HEAD `fb0fe3b85882c86f247c13b46e43bb8abc6c546b`
  and tree `d73510f875bf75ecadaf0b1a63b35af56e40ea4f`; no prior edit, test,
  commit, push, or CI-observer process remained active in the mounted worktree.
- The Knowledge real-service lifecycle now exposes closed steps for index submit
  and readiness, authority readback, retrieval submit/render/citation, search,
  evaluation, summary, import preview/execute/retry, duplicate review, and scoped
  denial readback. Existing assertions and the five compatibility operation
  attachments remain unchanged.
- The Wave 3B real-service journey now exposes closed setup and journey steps. Its
  backend start and health readiness share the existing 20-second deadline measured
  before the owned start/restart control request; health polling does not add a new
  timeout budget or relax the 200 success condition.
- The sanitized reporter records the last completed closed step and the first
  failed or, when interruption leaves no explicit failing step, first incomplete
  closed step. An explicit coarse Knowledge operation failure remains authoritative,
  while an already observed finer completed step is not discarded. Unknown paths,
  scenarios, or stages still fail closed to `UNKNOWN`, and raw failures remain absent.
- Continuation validation: task reporter plus producer/release compatibility tests
  `40 passed`; affected frontend ESLint passed; TypeScript and production build
  passed; `make check` passed with `1597 passed, 133 skipped`; `git diff --check`
  passed. The local formal harness was not rerun.

Ordinary commit, non-force push, and automatic CI observation remain pending this
checkpoint review. PR #167 remains Draft.

## Risks and compatibility

- Parser resource exhaustion is bounded by byte, archive, count, and time limits.
- Extracted text can differ from visual layout; preview is mandatory and locations
  are emitted only when the parser actually supplies them.
- The private create API remains compatible with existing callers that supply
  internal IDs. New callers receive backend-generated IDs.
- Adding optional display metadata and location fields changes only new revision
  content; the existing canonical digest function/domain and historical records are
  unchanged.
- Trusted ordinary-browser routing remains dependent on S5-V023-IMPL-305. This
  branch does not substitute its own authentication or BFF.
