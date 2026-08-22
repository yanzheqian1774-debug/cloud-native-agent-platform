# Checkpoint A.2 live evidence

Date: 2026-08-21. All timestamps are UTC. Credentials were generated for local
API authentication only, were never printed, and were destroyed with the
containers. No inference-provider credential was present.

## Image

- Tag: `nousresearch/hermes-agent:v2026.8.18`
- RepoDigest: `sha256:22e37bb4ed1b0f50cb6bd991dca7ecacd6c9f29df9b4a20fc989d32bc763ccf6`
- Image ID: `sha256:252a0f02e8bac72b0153d4854af1e42daea7fb99ef654fb7833e815b4bbde691`
- Architecture/OS: `arm64` / `linux`
- Created: `2026-08-18T07:29:09.892816359Z`
- Entrypoint: `/opt/hermes/docker/entrypoint-dispatch.sh`
- Working directory/user: `/opt/hermes` / `root`

## E1 — three clean provisions

Each run used the immutable digest, a unique container, a fresh Docker volume,
a loopback-only published port, and a generated ephemeral API key. READY below
means runtime interaction surface reachable plus detailed readiness `ok`; it
does not mean model/task ready.

| Event | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Start | 12:36:01 UTC | 12:37:04.596441 | 12:37:42.181123 |
| Container created | 12:36:01.567826 | 12:37:04.785190 | 12:37:42.341092 |
| Container running | 12:36:01.892769 | 12:37:04.944514 | 12:37:42.433130 |
| Gateway-start banner observed | ~12:36:09 | 12:37:10.999627 | 12:37:48.317093 |
| Gateway/liveness reachable | ~12:36:15 | 12:37:13.613823 | 12:37:50.928711 |
| Detailed readiness sampled | ~12:36:16 | 12:37:14.320113 | 12:37:51.650766 |
| Time to runtime READY | 16.116 s | 10.557 s | 10.245 s |
| Container restarts | 0 | 0 | 0 |
| Cleanup | complete | complete | complete |

Minimum 10.245 s; average 12.306 s; maximum 16.116 s.

Each detailed payload reported overall/readiness `ok`, gateway `running`, API
server `connected`, and config, disk, gateway, model, state DB, and background
queues `ok`.

## E2 — invocation

The real Hermes gateway accepted `POST /v1/chat/completions` through its actual
API server. With no inference provider configured, it returned HTTP 200 after
2.497 s. The response used normal assistant-message structure but its content
reported provider authentication failure; usage was zero input/output tokens.

Result: real Hermes interaction, but no real model execution. Generic boundary
is still isolated; Hermes path/payload/error interpretation remains in the
provider. The provider must not map HTTP 200 alone to successful task result.

## E3 — health cases

| Case | Infrastructure | Native signal | Provider/platform observation | Invocation/task |
|---|---|---|---|---|
| H-01 nominal runtime | Container running | Gateway running; detailed checks all `ok` | Runtime surface READY; dependency/task UNKNOWN | Invocation accepted but real task failed without provider |
| H-02 gateway stopped | Container remained running | `Gateway is not running` | `/health` unavailable in 0.426 s | Impossible |
| H-03 model unavailable | Container/gateway/API available | Detailed `model.status=ok`; gateway log recorded provider auth failure | Must map dependency/task not ready despite HTTP 200 | Not executable; zero tokens |
| H-04 invalid API key | Container and gateway reported running | No clear error in inspected gateway/error logs | API/liveness unavailable after full startup wait | Impossible through API |
| H-05 container absent | Docker inspect absent | No Hermes process/signal | Connection refused in 0.442 s | Impossible |

The H-04 trigger was an API key shorter than the documented minimum. It was a
non-secret test value. The absence of a clear native error is itself evidence
of health ambiguity.

## READY finding

READY is not safely represented by a single raw Hermes probe. Evidence supports
a projection across at least:

- InfrastructureAvailable: container exists/runs.
- RuntimeAvailable: gateway interaction surface is reachable.
- DependencyReady: not proven by current detailed `model` health.
- TaskReady: requires a realistic invocation outcome, not HTTP status alone.

The first two can be true while the latter two are false or unknown.
