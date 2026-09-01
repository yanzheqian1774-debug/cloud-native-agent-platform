# S5-IMPL-057 — Native Runtime Manager Checkpoint A Evidence

## Scope and baseline

- Authorized baseline: `b077c6ec1172dbd6ec33cf08691212a98c8c6d22`.
- Baseline CI: `33474171843 / SUCCESS`.
- Binding Contract: PR #111, merged at the authorized baseline.
- Contract fixture digest:
  `0449066a6cba3eca8d2f79890f248f2c9c7688cbd76d1cb8222a6748f4a35d8c`.
- Branch: `codex/s5-impl-057-native-runtime-manager`.
- Human continuation authorized the exact compatibility allowlist path
  `core/tests/test_compatibility.py` for three named operator importers only.

No migration, CRD, API group, dependency, frontend, deployment manifest or OpenClaw
path is changed.

## G1 file plan

| Path | Bounded purpose |
| --- | --- |
| `core/src/agent_core/runtime_control.py` | Pure desired/observed reconciliation policy, generation, freshness and assignment admission |
| `operator/src/agent_operator/runtime_manager.py` | Persistence-first typed Native reconciliation and restart-safe observation |
| `operator/src/agent_operator/runtime_identity_translation.py` | Exact Placement/Product identity consumption without reminting |
| `operator/src/agent_operator/runtime_kubernetes_observer.py` | Allowlisted, sanitized Pod observation normalization |
| `runtime/src/agent_runtime/providers/native/provider.py` | Typed lifecycle delegation to an injected substrate driver |
| `runtime/src/agent_runtime/providers/native/models.py` | Provider-local lifecycle result, observation and driver types |
| Four authorized focused test paths | Identity, lifecycle, freshness, ambiguity, restart, replacement and disclosure coverage |
| `core/tests/test_compatibility.py` | Exact three-entry fail-closed importer allowlist update |

## Results

- Placement supplies the stable Product Runtime Instance ID. The translator never
  derives it from a Pod, provider handle, database sequence or Attempt.
- Desired intent is appended before any provider effect. Generations are monotonic;
  observations and reconciliation results are append-only facts.
- `UNKNOWN` represents missing trustworthy observation, `STALE` represents expired
  freshness, and ambiguous effects become `RECOVERY_REQUIRED` and are not reissued.
- Graceful stop blocks new assignment as soon as stopped intent is durable, before
  the external termination effect.
- Replacement changes only provider/Kubernetes correlation under the same Product
  Runtime Instance ID and creates no Attempt.
- A provider without an injected lifecycle driver returns `NOT_YET_PROVEN`; it does
  not manufacture workload existence or status.
- Kubernetes normalization includes only state, health, readiness and an opaque
  namespace/name/UID correlation. Pod phase is explicitly marked as not business
  success. Secret values, environment, Pod spec and raw logs are not projected.

## Real Kubernetes acceptance

Cluster: `kind-agentos-dev`. Existing controller-managed Native Deployment:
`agent-workloads/engineering-builder`.

The fixed lifecycle driver exercised scale down, scale up, re-observation after
manager recreation, and controller-owned Pod replacement. It restored one Ready
replica at completion.

```text
PRODUCT_ID=runtime-product-acceptance-1
FIRST_UID=d7a8e93e-d576-4a69-bda1-a59474f810f6
RESTART_UID=ae17e873-91c9-4cf6-b3bc-26b38c6f727f
REPLACEMENT_UID=64d17491-640c-45ce-adf7-47ff985301d4
STOP=OBSERVED
REOBSERVE=OBSERVED
STALE=STALE
DISCLOSURE=PASS
```

The installed Agent, Task and Workflow CRDs were observed unchanged. Their sanitized
combined digest before and after the earlier replacement check was:
`c84d09fad34fd91ed0526ca4a3283d1628b672999d5c10a8e402910fa62fe06b`.

## Validation

- Compatibility plus focused Runtime Manager/Native/Contract suites: passed.
- `make check`: `1150 passed, 13 skipped`; one existing Starlette/httpx warning.
- `pre-commit run --all-files`: passed after running outside the socket-restricted
  sandbox.
- Contract fixture compatibility: passed; digest unchanged.
- Exact-path, prohibited-scope and Secret audits: required before commit.

## Limitations and next gate

This is an internal Native-only Checkpoint A implementation. The in-memory repository
is a focused conformance adapter, not new Product authority; production persistence
remains Track A/PostgreSQL-owned. The lifecycle driver is injected and must be wired
by a separately authorized assembly path. No exactly-once, HA, failover, generalized
recovery, production readiness, certification or v0.2.3 completion is claimed.
OpenClaw remains unimplemented and unauthorized.

Next gate: Human Native Runtime Checkpoint A review.
