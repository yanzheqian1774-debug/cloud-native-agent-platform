# ED-S5-001 — BOUNDED DIAGNOSTIC RESULT

## 1. Diagnostic Result

**PASS**

The exactly one authorized model submission established the failure boundary.
Hermes rejected the request at its local Gateway authentication layer with HTTP
401 before model routing. Diagnostic success does not close ED-S5-001.

## 2. Runtime Baseline

- Hermes: `v0.20.4`
- Image: `nousresearch/hermes-agent:v2026.8.18`
- Digest:
  `sha256:22e37bb4ed1b0f50cb6bd991dca7ecacd6c9f29df9b4a20fc989d32bc763ccf6`
- Architecture: Linux arm64 container on Docker Desktop/macOS arm64
- Intended provider: `kimi-coding-cn`
- Intended model: `kimi-k3`
- Baseline version, image, provider, model, endpoint and credential mapping were
  unchanged.

## 3. Preflight

- RuntimeAvailable: **TRUE**
- Configured provider: `kimi-coding-cn`
- Configured model: `kimi-k3`
- Credential source: **PRESENT**
- Credential projection: **PRESENT**
- In-process credential presence: **PRESENT**
- Runtime-resolved provider: `kimi-coding-cn`
- Runtime-resolved model: `kimi-k3`

The preflight helper initially encountered an import error before any model
submission because the pinned image no longer exports
`load_hermes_dotenv` from `hermes_cli.config`. Inspection found the image's
read-only `load_env` and `load_config_readonly` APIs. Using those APIs changed
no runtime configuration and allowed the required read-only preflight. This was
not a model request.

## 4. HTTP Evidence

- Status: **401 Unauthorized**
- Sanitized body:
  `{"error":{"message":"Invalid gateway API key (API_SERVER_KEY)","type":"gateway_auth_error","code":"gateway_auth_failed"}}`
- Latency: **13 ms**
- Destination: local Hermes
  `http://127.0.0.1:18680/v1/chat/completions`
- Authorization headers and credential values were not persisted.

## 5. Hermes Attribution

- Request parsed: **NO** for the model interaction; the Hermes HTTP layer
  parsed enough of the request to reject Gateway authentication, but the model
  request was not accepted for routing/execution.
- Resolved provider: `kimi-coding-cn`
- Resolved model: `kimi-k3`
- Native request/error ID: **UNKNOWN / unavailable**
- Hermes error type: `gateway_auth_error`
- Hermes error code: `gateway_auth_failed`

## 6. Upstream Attribution

- Destination: **NOT_APPLICABLE**; rejection occurred at the local Hermes
  Gateway authentication layer
- Kimi reached: **NO**
- Upstream status/error: **NOT_APPLICABLE**

The 401 body explicitly attributes rejection to `API_SERVER_KEY`, before any
model-provider or upstream Kimi error could occur.

## 7. Failure Classification

**HERMES_INTERACTION_SURFACE_FAILURE**

Evidence supports a local Gateway-authentication mismatch. It does not support
model configuration, model selection, Kimi credential, provider routing or
upstream failure classifications.

## 8. Failure Owner

**HERMES_PROVIDER**

The experimental Provider's request authentication did not satisfy the active
Hermes Gateway's `API_SERVER_KEY` check. This diagnostic does not determine the
corrected header/projection behavior and applies no fix.

## 9. DE01-DE10

| Evidence item | Result | Evidence |
| --- | --- | --- |
| DE01 HTTP status code | PASS | 401 |
| DE02 strictly sanitized response body | PASS | Gateway auth type/code/message captured; no credential material |
| DE03 Hermes accepted/parsed request | PASS | Model request not accepted; local auth rejection established |
| DE04 runtime-resolved provider | PASS | `kimi-coding-cn` |
| DE05 runtime-resolved model | PASS | `kimi-k3` |
| DE06 in-process credential presence | PASS | PRESENT boolean only |
| DE07 native request/error identifier | MISSING | Response contained no request/error ID |
| DE08 sanitized upstream attribution | PASS | Local Hermes Gateway; no upstream destination |
| DE09 whether Kimi was reached | PASS | NO |
| DE10 final failure classification | PASS | HERMES_INTERACTION_SURFACE_FAILURE |

## 10. Candidate v1 Impact

**NONE**

The failure is operational and Provider-specific. It does not contradict the
Candidate v1 Binding, observation, ownership or hybrid interaction semantics.

## 11. ED-S5-001

**OPEN**

No successful real Kimi completion, semantic SUCCESS or non-zero usage was
established.

## 12. Recommended Next Action

**MINIMAL_FIX_AND_NEW_VERIFICATION**

A separately authorized task may correct only the experimental Hermes Gateway
authentication behavior, then perform a new bounded verification. This
diagnostic run does not apply or validate that fix.

## 13. Validation

- Diagnostic harness tests: **4 passed**
- Ruff check and format check: **passed**
- New evidence whitespace check: **passed**
- Secret scan: **passed**
- Exactly one model submission: **verified by runner control flow and session
  execution**
- Second model request: **none**

## 14. Cleanup

- Temporary Hermes container: removed by Provider cleanup
- Temporary credential projection and `/opt/data`: removed
- Credential source Secret: read-only and unchanged
- Remaining listener/process/container: **none found**
- Remaining diagnostic temporary directory: **none found**

**STOP. No fix or additional model request was performed.**
