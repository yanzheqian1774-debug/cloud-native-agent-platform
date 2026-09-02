# S5-IMPL-090 Checkpoint A Evidence

## Boundary

This maintenance change is derived directly from v0.2.2 product source
`4a4ebd69eff5d9559fd723432b8b6b335291417f` (tree
`7840bca89c32c68c3de92b7e3a18129a52851258`). It adds test-only operation
instrumentation to the existing Knowledge Workbench journey and a structured
Playwright reporter. Application source, backend source, migrations, lockfiles,
runtime behavior, public APIs, and CRDs are unchanged.

The new successor is prospective only. Attempts 01–05 remain bound to their
original product provenance.

The first candidate, `bf9107ad5dd69fae2a941dc01ca3d10761860e03`, is
preserved in PR #125 but superseded because its exact ref could not dispatch
the repository CI workflow. The replacement remains a direct successor of the
same original source and adds only the existing-compatible `workflow_dispatch`
trigger required for exact-ref CI.

## Closed producer contract

The deterministic operation order is:

1. `KNOWLEDGE_GOVERNED_CREATE_PUBLISH`
2. `KNOWLEDGE_INDEX_RETRIEVE`
3. `KNOWLEDGE_UPDATE`
4. `KNOWLEDGE_RESTART_READBACK`
5. `KNOWLEDGE_PURGE_RECOVERY`

Each serialized operation contains exactly `operationId`, `resultState`, and,
when supplied by the operation as a typed integer from 100 through 599,
`structuredHttpStatus`. Result state is either `EXPECTED` or `UNEXPECTED`.
Canonical operation order defines the deterministic first unexpected operation.

The producer never derives operation identity or HTTP status from titles,
messages, selectors, URLs, routes, bodies, fixture/business content, process exit
codes, or assertion counts. The reporter retains no Playwright trace, screenshot,
video, error-context file, raw report, product state, or business payload.

## Validation record

- Frontend ESLint: passed.
- Frontend repository build (`tsc -b && vite build`): passed.
- Reporter contract/integration tests: 6 passed.
- Real isolated Knowledge journey against disposable PostgreSQL 15 and Qdrant
  1.15.4: 1 passed.
- Real journey reporter record: all five operations in canonical order, all
  `EXPECTED`; purge/recovery carried the actual structured HTTP status `202`.
- Repository `make check`: 1,156 passed, 13 environment-gated skips, one existing
  Starlette/httpx deprecation warning.
- `git diff --check` and pre-commit: passed.
- Exact-path, prohibited-scope, nondisclosure, Secret/private-key,
  generated-artifact, absolute-local-path, and conflict-marker audits: passed.

The exact successor commit/tree, blobs, Draft PR, and exact-head CI conclusion are
recorded in the Human Checkpoint A result because a commit cannot contain its own
identity.
