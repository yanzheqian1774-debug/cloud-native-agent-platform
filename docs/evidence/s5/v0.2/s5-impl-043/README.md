# S5-IMPL-043 Checkpoint A Evidence

## Entry revalidation

- Authorized baseline, fetched `origin/main`, branch HEAD: `7f4e9b5f6f8cd6e28bcd6b294fcf349e18c48c1c`.
- Authorized branch: `codex/s5-impl-043-public-model-provider-adapter`.
- Dedicated worktree was clean before editing and has no competing writer.
- Repository, worktree, branch, issue, and pull-request searches found no
  S5-IMPL-043 collision. S5-IMPL-042 remains separate and was not reused.
- G1 remained sufficient: no public Contract, CRD, Kubernetes API, Runtime,
  persistence, Control Plane, or cross-plane boundary changed.

## Provider architecture

The Console planning service now consumes independent internal Planning and
Embedding ports. `ollama` remains an explicitly selected local-development
adapter. `openai-compatible` uses server-side Bearer authentication and a base
URL that includes the compatibility root (normally `/v1`); the adapters append
`/chat/completions` and `/embeddings` after removing one trailing slash.

There is no routing, fallback, retry, fabricated response, Runtime integration,
Model Gateway, Model Registry, provider SDK, or public deployment in this task.
Qdrant and all deterministic Problem, canonical Task/DAG, correction,
successor, exact-revision approval, Evidence/Citation, SSE, and inert-dispatch
authority remain unchanged.

## Model usage manifest

| Product function | Provider type | Model identifier | Deployment mode | Required | Configuration variables | Controlled failure | External data categories |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Console structured Planning proposal | `ollama` or `openai-compatible` | `S5_PLANNING_MODEL` or explicit-Ollama legacy model | Public/cloud or explicit local development | Yes for Planning | `S5_PLANNING_PROVIDER`, `S5_PLANNING_BASE_URL`, `S5_PLANNING_API_KEY`, `S5_PLANNING_MODEL`; local-only legacy variables | Credential-free 503 reason code; no fallback | Problem description and authorized knowledge excerpts |
| Console document/query embeddings | `ollama` or `openai-compatible` | `S5_EMBEDDING_MODEL` or explicit-Ollama legacy model | Public/cloud or explicit local development | Yes for retrieval | `S5_EMBEDDING_PROVIDER`, `S5_EMBEDDING_BASE_URL`, `S5_EMBEDDING_API_KEY`, `S5_EMBEDDING_MODEL`; local-only legacy variables | Credential-free 503 reason code; no fallback | Authorized knowledge excerpts and the Problem query text |

Planning provenance records only the selected Provider type and configured
Planning model identifier. It never records a base URL, header, API key, or
secret value. This table is a bounded v0.2.1 usage manifest, not v0.2.4 Model
Management.

## Failure and credential boundary

- Missing/invalid Provider selection and missing public base URL, API key, or
  model fail with controlled 503-class errors.
- 401, 403, 429, 5xx, timeout, malformed JSON, malformed Planning content,
  malformed embeddings, count mismatch, duplicate/invalid index, empty vector,
  non-numeric value, and inconsistent dimensions fail closed.
- Exception chaining from provider HTTP/response content is suppressed. API
  responses expose only stable reason codes.
- Tests use deterministic fake markers and mock transports; no live Provider,
  real credential, or billable request is used.

## Validation

- Focused Provider, Planning, and API tests: `40 passed`, one existing
  Starlette/httpx deprecation warning.
- `make check`: Ruff lint passed, Ruff format check passed, `1011 passed`, the
  same one existing warning.
- `uv run pre-commit run --all-files`: Ruff lint, Ruff format, and pytest hooks
  passed.
- `git diff --check`: passed.
- Credential-pattern scan of the bounded diff: passed; no real credential or
  private key found.

## Limitations and deployment handoff

- The provider adapters remain Console-local and process-local; they do not
  implement enterprise model governance, routing, cost controls, retries, or
  Provider certification.
- OpenAI-compatible endpoints must support the requested strict JSON-schema
  response format and the documented Chat/Embedding response shapes.
- Public activation is intentionally not performed. S5-DEPLOY-003 must supply
  server-side values for `S5_PLANNING_PROVIDER`, `S5_PLANNING_BASE_URL`,
  `S5_PLANNING_API_KEY`, `S5_PLANNING_MODEL`, `S5_EMBEDDING_PROVIDER`,
  `S5_EMBEDDING_BASE_URL`, `S5_EMBEDDING_API_KEY`, `S5_EMBEDDING_MODEL`, and
  `S5_IMPL_041_QDRANT_URL`; both Provider selectors must explicitly be
  `openai-compatible` for the public Demo.
