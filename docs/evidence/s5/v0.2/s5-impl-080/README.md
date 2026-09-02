# S5-IMPL-080 — Bounded OpenClaw Runtime Provider Adapter

## Checkpoint boundary

This package implements only the provider-local Track C adapter authorized by the
Human allocation. It consumes the integrated S5-IMPL-056 execution/Placement
identities and the S5-IMPL-057 desired/observed Runtime boundary without modifying
either shared contract. It creates no provider factory, bootstrap, dependency,
lockfile, migration, CRD, Kubernetes API, CI workflow, global route or deployment.

The Human continuation authorization grants one bounded Track C source-admission
exception in `core/tests/test_compatibility.py`: exactly the production OpenClaw
driver and its focused test are admitted as Core consumers. Existing Track A/B
entries and the exact fail-closed equality/unknown-importer negative control remain
unchanged. This exception transfers no general Track H ownership.

The exact selected target is OpenClaw `2026.7.1-2`, tag commit
`0790d9f593ad30c940ed93b5872a8cf6d6f3cf8c`, npm integrity
`sha512-ycF3yPcbjN6bUPeaUx6Mh6vze1hQWoD3CT/wWcmD7a8xaHHHRUaAlaq+lFxMHf1ssEgODVAwjlzYqp2twkYZ7g==`.
No container digest is selected or claimed.

## Implemented boundary

- multiple independent Platform Runtime Instance identities;
- opaque Gateway/session/run correlations that never become Platform authority;
- strict consumption of an accepted Placement and exact Workflow Run, Task Run,
  Attempt, Agent Instance, Runtime Instance and Placement linkage;
- exact-version/integrity preflight before start;
- accepted, running and terminal provider observations;
- separate health, readiness and freshness facts;
- monotonic desired/observed generations;
- graceful stop, bounded one-generation replacement and restart re-observation;
- explicit stateful/stateless and session-affinity facts;
- fail-closed missing, stale, unknown, conflicting and ambiguous observations;
- sanitized Evidence containing only Platform linkage, reason, generation and a
  digest of provider correlations.

The transport protocol exposes only fixed typed operations. It has no arbitrary
command, YAML, environment, log, Secret-value, shell, filesystem or unrestricted
provider-payload surface.

## Claim and limitations

This is a provider-local component candidate and deterministic protocol acceptance,
not live managed OpenClaw execution evidence. It grants no certification, production
readiness, deployment, complete A+B/OpenClaw assembly, HA, failover, elasticity,
state migration, rolling upgrade, public cutover or access to S5-DEPLOY-069.

Validation, exact head/tree, draft PR, CI and overlap evidence are recorded in the
Human Checkpoint A report after the evidence-bearing commit exists.

## Exact-version provider startup preflight

On 2026-09-02, the exact npm target was executed outside repository dependency
management on host Node `v22.23.1`. `openclaw --version` returned
`OpenClaw 2026.7.1-2 (0790d9f)`. An isolated temporary Gateway then started on
loopback port `19180`, reported `ready`, returned HTTP `200` with the allowlisted
payload `{"ok":true,"status":"live"}` from `/healthz`, and completed graceful
SIGINT shutdown. Its isolated temporary state was removed afterward. No credentials,
raw logs, environment values or provider configuration are retained in this package.

This startup/readiness proof establishes the exact package and local Gateway health
only. It does not establish real-model task completion, managed deployment,
certification, production readiness or complete Platform/OpenClaw assembly.

## Local validation

- compatibility allowlist: `2 passed`;
- focused Runtime/Operator/provider-local acceptance: `14 passed`;
- exact OpenClaw version/startup/readiness/graceful shutdown: passed twice;
- `make check`: `1232 passed, 22 skipped`, one existing Starlette/httpx warning;
- `pre-commit run --all-files`: passed;
- post-pre-commit `make check`: `1232 passed, 22 skipped`, same existing warning.

The skipped tests require optional PostgreSQL or Qdrant services and are unrelated
to this provider-local change. Exact-path, prohibited-scope, Secret/nondisclosure,
diff, open-PR overlap and S5-DEPLOY-069 isolation audits are required immediately
before commit and Draft PR creation.
