# S5-SPIKE-005 — Runtime target and Compatibility Manifest evidence

## Session boundary

- Baseline and implementation commit: `e6a162ffa8c0b0294b9e5087462649fab6ef656d`
- Branch: `codex/s5-spike-005-runtime-target-manifest`
- Checkpoint: B, Human RTM01–RTM09 convergence and downstream handoff
- Production Provider implementation: **NO**
- Core/API/schema/CRD change: **NO**
- Compatibility Manifest: **CANDIDATE / EXPERIMENTAL / NOT FROZEN**
- Verified at: `2026-08-25T09:24:43+08:00` (`Asia/Shanghai`)

The Human-confirmed S5-REL-011 closure at the baseline above is accepted as
authoritative. Earlier repository governance state is metadata lag only and is
not changed here.

## Source review and evidence classification

`runtime/src/agent_runtime` is the **IMPLEMENTED** Native HTTP runtime. Its
health, readiness, information and invocation behavior is **TESTED** in
`runtime/tests`; the mock and OpenAI-compatible model integrations are also
**TESTED**. `runtime/Dockerfile` is a **DOCUMENTED/IMPLEMENTED** repository-owned
deployment artifact, but no immutable published image digest is present.

The accepted architecture identifies Native as `PRIMARY_GOLDEN_PATH`, OpenClaw
as a bounded external-path Candidate requiring live evidence, and Hermes as
`EXPERIMENTAL / NOT_CURRENTLY_CERTIFIABLE`. A production Runtime Provider,
Provider certification, managed OpenClaw Kubernetes lifecycle, and a frozen
Compatibility Manifest are **NOT_YET_PROVEN**. Broad version support and final
serialization are **DEFERRED**.

## Native exact target Candidate

| Field | Candidate |
| --- | --- |
| Target ID | `native:0.1.0+e6a162f:managed-kubernetes-deterministic-mock` |
| Implementation commit | `e6a162ffa8c0b0294b9e5087462649fab6ef656d` |
| Package identity | project `cloud-native-agent-platform==0.1.0`; module `agent_runtime`; FastAPI advertises `0.1.0` |
| Deployment profile | repository `runtime/Dockerfile`, Kubernetes-managed per-Agent realization, deterministic `MODEL_PROVIDER=mock` |
| Platform | Linux container; AMD64 release path documented; ARM64 remains not yet proven for this exact target |
| Features | `/healthz`, `/readyz`, `/v1/info`, `/v1/invoke`; mock and OpenAI-compatible model calls |
| Limitations | no immutable image digest, Provider package split, certification, semantic recovery, or v0.2 end-to-end Demo evidence |
| Test evidence | `runtime/tests/test_runtime.py`, `runtime/tests/test_providers.py`, full repository suite |
| Mismatch | exact manifest/package/Core/runtime mismatch rejects before invocation |
| Fallback | explicit reject; deterministic mode is explicitly labeled, never silent substitution |
| Conformance | `SUPPORTED_CANDIDATE`; `PRIMARY_GOLDEN_PATH`; not certified |

## OpenClaw Candidate inventory and selection

The plausible durable-main identity and the exact official target are the same
Candidate: `2026.7.1-2`. Unpinned `latest`, version ranges, and newer releases
were rejected because this Session has no compatibility evidence for them.

**Selection: `SELECTED_EXACT_VERSION_CANDIDATE`.**

| Field | Evidence |
| --- | --- |
| Version/tag | `2026.7.1-2` / `v2026.7.1-2` |
| Commit | `0790d9f593ad30c940ed93b5872a8cf6d6f3cf8c` (annotated tag object `be8b8a9e8838f832e4fa47cde8bea0a33aec71ba`) |
| Release | official GitHub release published `2026-08-04T00:41:26Z` |
| Package | npm `openclaw@2026.7.1-2`; integrity `sha512-ycF3yPcbjN6bUPeaUx6Mh6vze1hQWoD3CT/wWcmD7a8xaHHHRUaAlaq+lFxMHf1ssEgODVAwjlzYqp2twkYZ7g==`; signed registry metadata |
| Runtime requirements | Node `>=22.22.3 <23 || >=24.15.0 <25 || >=25.9.0` |
| Deployment profile | externally owned single Gateway with isolated agent config/state/workspace; adapter-managed normalization remains unimplemented |
| Platform | server/container feasibility is documented upstream; exact OS/architecture matrix for this profile is not yet proven |
| License | MIT at pinned upstream tag |
| Features | Gateway/session/deferred-run evidence is `OBSERVED` in durable S5 test evidence; Skills/workspace and Gateway surfaces are `DECLARED_BY_UPSTREAM` |
| Limitations | no new live execution, production adapter, managed Kubernetes lifecycle, recovery/cleanup proof, certification, or range support |
| Required adapter seams | package/version preflight; Gateway auth/config; submit/observe; opaque session/run correlation; health normalization; workspace isolation; cleanup/recovery; explicit fallback |
| Mismatch/fallback | reject unsupported versions before invocation; before invocation only, an explicit decision may select Native with honest labels and a distinct attempt identity; never auto-fallback after possible effects |
| Conformance | `SELECTED_EXACT_VERSION_CANDIDATE / SUPPORTED_EXTERNAL_RUNTIME_PATH_CANDIDATE / LIVE_MANAGED_PROFILE_EVIDENCE_REQUIRED / NOT_CERTIFIED`; platform support is not granted |

Primary provenance was retrieved at `2026-08-25` from the
[official release](https://github.com/openclaw/openclaw/releases/tag/v2026.7.1-2),
[official repository tag](https://github.com/openclaw/openclaw/tree/v2026.7.1-2),
and [official npm record](https://registry.npmjs.org/openclaw/2026.7.1-2).
The Git tag and npm integrity are immutable references; the GitHub release
record itself reports `immutable: false`, so the tag commit and package
integrity—not the mutable release prose—are the durable pins. No container
image is selected.

Upstream identity verification is not platform compatibility proof. Promotion
to a supported external Runtime path requires pinned installation/integrity and
Node/host checks; isolated Gateway config/state/workspace; version preflight;
authenticated start/health; bounded submit/observe; unchanged Platform
Execution Identity; normalized diagnostics/Outcome; Capability authorization
non-bypass; pre-invocation mismatch rejection; stop/cleanup/recovery; explicit
Native fallback; and proof that no silent substitution occurs. All-version,
production, certification, full native-feature, exactly-once, unrestricted
Skill/shell/filesystem/network, desktop-fleet, customer-managed, and Edge
production claims remain prohibited.

## Hermes boundary

Hermes remains `EXPERIMENTAL / NOT_CURRENTLY_CERTIFIABLE / NON_BLOCKING` at
v0.20.4, tag `v2026.8.18`, pinned image digest recorded in its durable evidence.
ED-S5-001 remains **OPEN**. The fixture demonstrates that failure evidence,
limitations, exact version, rejection, and not-certifiable state can be
represented; it does not select Hermes for v0.2.

## Compatibility Manifest Candidate

The experimental Python validator and JSON fixtures are a representation
experiment, not a Core resource, public API, CRD, schema, Contract, registry
service, or serialization decision. Required semantics cover the full
authorization list: format/schema markers; Provider/package/Core/runtime exact
identity; profile/platform/features/limitations/configuration/isolation;
identity/lifecycle/health/recovery/cleanup; failure, mismatch, degraded and
fallback policies; provenance; conformance/certification/deprecation; security,
license, and verification time.

Its classification is
`PROVIDER_PACKAGE_COMPATIBILITY_METADATA_CANDIDATE`. The authorized set is 32
semantic fields plus the non-semantic experimental format marker. It is not a
Core logical resource, sixth Core resource, CRD, public API, frozen schema,
certification grant, or release contract.

Evidence values distinguish `DECLARED_BY_UPSTREAM`, `OBSERVED`, `TESTED`,
`SUPPORTED_CANDIDATE`, `EXPERIMENTAL`, `NOT_SUPPORTED`, and
`NOT_YET_PROVEN`. JSON is used only because it is machine-checkable; field
names, nesting, encoding, and storage remain unfrozen.

Fixtures include Native supported, OpenClaw exact Candidate, OpenClaw
unsupported version, missing version, Provider-package mismatch, incompatible
Core, explicit degraded operation, Hermes Experimental/not-certifiable, and a
Future Runtime extension example.

## Match, rejection, diagnostics, and identity

Exact Runtime, Provider package, and Core matches pass for Native. An exact
OpenClaw identity match validates the selected target but remains non-invocable
until live managed-profile evidence exists. Missing or untested
versions and package/Core mismatches fail closed before invocation with stable,
actionable reason codes. Degraded operation requires both an explicit request
and manifest evidence. Experimental Hermes cannot be invoked. Every result
copies the caller's Platform Execution Identity unchanged; native identity is
never substituted as authority. Fallback is returned as policy evidence and is
never executed by this spike.

## Feature and limitation matrix

Every cell contains an evidence classification.

| Capability | Native | OpenClaw Candidate | Hermes | Future |
| --- | --- | --- | --- | --- |
| Managed deployment | TESTED: repo container shape; full v0.2 lifecycle NOT_YET_PROVEN | DECLARED_BY_UPSTREAM feasibility; NOT_YET_PROVEN managed profile | OBSERVED experimental container | NOT_SUPPORTED |
| Registration | NOT_YET_PROVEN Provider registry | NOT_YET_PROVEN | OBSERVED experimental Binding | NOT_SUPPORTED |
| Heartbeat/health | TESTED health/readiness | OBSERVED Gateway evidence; normalization NOT_YET_PROVEN | TESTED gateway health; task readiness NOT_YET_PROVEN | NOT_SUPPORTED |
| Start/stop | DOCUMENTED Kubernetes lifecycle | NOT_YET_PROVEN adapter seam | OBSERVED experimental lifecycle | NOT_SUPPORTED |
| Task execution | TESTED `/v1/invoke` | OBSERVED recorded deferred terminal evidence | TESTED failure only; success NOT_YET_PROVEN | NOT_SUPPORTED |
| Execution identity | NOT_YET_PROVEN end-to-end; validator TESTED | OBSERVED generic caller preservation | OBSERVED generic caller preservation | NOT_SUPPORTED |
| Native correlation | TESTED Agent/model response only | OBSERVED opaque Gateway/session/run IDs | OBSERVED opaque runtime facts | NOT_SUPPORTED |
| Skill/profile isolation | NOT_SUPPORTED as Native feature | DECLARED_BY_UPSTREAM; adapter isolation NOT_YET_PROVEN | OBSERVED profiles | NOT_SUPPORTED |
| Workspace isolation | DOCUMENTED per realization; NOT_YET_PROVEN v0.2 | DECLARED_BY_UPSTREAM; profile NOT_YET_PROVEN | OBSERVED isolated data | NOT_SUPPORTED |
| Secrets | IMPLEMENTED env model key; stronger binding DEFERRED | DECLARED_BY_UPSTREAM auth; adapter binding NOT_YET_PROVEN | TESTED safe reference handling | NOT_SUPPORTED |
| Capability invocation | NOT_YET_PROVEN v0.2 Capability path | NOT_YET_PROVEN | NOT_YET_PROVEN | NOT_SUPPORTED |
| Status normalization | TESTED experimental rejection only | OBSERVED experimental generic outcome | OBSERVED experimental generic outcome | NOT_SUPPORTED |
| Recovery | DOCUMENTED workload replacement; semantic recovery NOT_YET_PROVEN | NOT_YET_PROVEN | OBSERVED process recovery; semantic recovery NOT_YET_PROVEN | NOT_SUPPORTED |
| Cleanup | DOCUMENTED Kubernetes ownership | NOT_YET_PROVEN adapter seam | TESTED experimental cleanup | NOT_SUPPORTED |
| Version reporting | TESTED manifest fixture; runtime endpoint lacks version | TESTED exact manifest pin | TESTED exact manifest pin | TESTED extension expression |
| Mismatch rejection | TESTED | TESTED | TESTED Experimental rejection | TESTED NOT_SUPPORTED expression |
| Degraded operation | TESTED explicit deterministic policy | NOT_SUPPORTED before required live evidence | NOT_SUPPORTED | NOT_SUPPORTED |
| Platform | DOCUMENTED Linux; AMD64 target, ARM64 NOT_YET_PROVEN | DECLARED_BY_UPSTREAM Node bounds; OS/arch NOT_YET_PROVEN | OBSERVED linux/arm64 | NOT_SUPPORTED |
| Known limitations | TESTED manifest completeness | TESTED manifest completeness | TESTED manifest completeness | TESTED manifest completeness |

## Evidence debt and Human decisions

- **RTM01:** `ACCEPTED_WITH_EVIDENCE_DEBT` — Native is Primary Golden Path
  Supported Candidate only; not certified, production-ready, or release-accepted.
- **RTM02:** `ACCEPTED_AS_EXACT_VERSION_VALIDATION_TARGET` — OpenClaw
  2026.7.1-2; support not granted; live managed-profile evidence mandatory.
- **RTM03:** `ACCEPTED_FOR_EXPERIMENTAL_DOWNSTREAM_USE` — 32 fields.
- **RTM04:** `ACCEPTED` — JSON fixture only, representation unfrozen.
- **RTM05:** `ACCEPTED` — exact-match and fail-closed policy.
- **RTM06:** `ACCEPTED_WITH_CONSTRAINTS` — explicit, evidenced, diagnosable,
  auditable degraded mode; silent degradation prohibited.
- **RTM07:** `ACCEPTED` — Provider/Core compatibility, stable diagnostics, and
  unchanged Platform Execution Identity.
- **RTM08:** `ACCEPTED` — Hermes remains Experimental/non-blocking; ED-S5-001 open.
- **RTM09:** `CONDITIONALLY_GRANTED` — separate authorization required for
  `S5-IMPL-004`, the unique Portfolio Native managed Provider Session.

Open evidence debt includes published Native image digest/platform proof,
OpenClaw live managed-profile execution, upstream security notice review at
implementation time, lifecycle/recovery/cleanup proof, end-to-end identity,
Capability path, conformance, certification, serialization, migration, and
version-upgrade policy.

For any future fallback, the Technical View must expose requested Runtime,
effective Runtime, rejection/fallback reason, Platform Execution Identity, and
resulting Outcome. Product View may simplify presentation but cannot alter the
recorded decision. Root business correlation is preserved while the current
identity model supplies a distinct Task execution or attempt identity.

## Rollback and downstream recommendation

Rollback is deletion of
`experiments/s5-spike-005-runtime-target-manifest`, this evidence directory,
and the one `pyproject.toml` test-discovery entry. Production behavior and
dependencies remain unchanged.

After separate authorization, Portfolio Session `S5-IMPL-004` may build the
Native Provider against an approved internal interface.
OpenClaw implementation should additionally require a live exact-version
managed-profile preflight. This Session does not start either implementation.
