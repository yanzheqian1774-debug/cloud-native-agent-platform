# S5-IMPL-045 — Configurable Bounded Planning Provider Timeout

## Scope

This change replaces the fixed 30-second timeout used by the Console-local
OpenAI-compatible Planning Provider with the server-side environment variable
`S5_PLANNING_TIMEOUT_SECONDS`.

It does not change Provider routing, retry, fallback, credentials, endpoints,
models, strict JSON-schema requests, Embedding, Ollama, Qdrant, deployment, or
public activation.

## Configuration contract

| Input | Result |
| --- | --- |
| variable missing | `30.0` seconds |
| `45` | `45.0` seconds; supported Demo value |
| `60` | `60.0` seconds; accepted maximum |
| finite decimal in `(0, 60]` | accepted deterministically as seconds |
| blank, whitespace-only, malformed, non-finite, zero, negative, or above `60` | fail closed with `PROVIDER_CONFIGURATION_INVALID` and HTTP status `503` |

The effective value is used only when the OpenAI-compatible Planning Provider
constructs its HTTP client. The variable is non-secret and remains server-side.

## Preserved behavior

- Planning endpoint, model, Bearer authentication, TLS verification, and strict
  JSON-schema payload are unchanged.
- Provider timeout and HTTP failures remain
  `CONTROLLED_PROVIDER_UNAVAILABLE`/`503` without credential disclosure.
- A timeout performs one request only; there is no retry or fallback.
- OpenAI-compatible Embedding and both Ollama adapters retain their existing
  30-second client timeout and ignore this Planning-only variable.

## Validation evidence

Baseline: `474b19e7bf32a342d93b4b891f6c7a799b9261b6`

Branch: `codex/s5-impl-045-configurable-planning-timeout`

- `uv run pytest console/backend/tests/test_problem_model_providers.py -q`:
  `38 passed`.
- `uv run pytest console/backend/tests/test_problem_planning_v021.py console/backend/tests/test_app.py -q`:
  `18 passed`, with one pre-existing Starlette/httpx deprecation warning.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: `174 files already formatted`.
- `make check`: `1046 passed`, with the same pre-existing deprecation warning;
  all local quality checks passed.

- `uv run pre-commit run --all-files`: Ruff lint, Ruff format, and pytest hooks
  passed.
- `git diff --check`: passed.
- Exact changed-path audit: only the four paths authorized by S5-IMPL-045.
- Bounded secret/private-key scan: no private key or credential value found;
  only explicit synthetic `*-secret-marker` test fixtures matched.

## Deployment handoff

No deployment or protected environment change was performed. After durable
integration, the separately authorized S5-DEPLOY-003 session may set
`S5_PLANNING_TIMEOUT_SECONDS=45` in the existing protected server-side
environment, rebuild from the exact durable `main`, and rerun the complete
private journey.
