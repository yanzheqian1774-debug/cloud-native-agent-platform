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
