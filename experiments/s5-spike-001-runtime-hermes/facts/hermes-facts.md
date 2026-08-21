# Hermes facts — Checkpoint A

Snapshot date: 2026-08-21.

## Verified facts

- Upstream release `v0.20.4`, tag `v2026.8.18`, resolves to commit
  `e624e9fde561e1add9388384012b295fde669ade`.
- Upstream documents `hermes gateway run` as the container gateway command.
- The API server is opt-in with `API_SERVER_ENABLED=true`; non-loopback binding
  uses `API_SERVER_HOST=0.0.0.0` and requires `API_SERVER_KEY` of at least eight
  characters.
- The API server uses port `8642` by default and exposes OpenAI-compatible
  `POST /v1/chat/completions`.
- `GET /health` and `GET /v1/health` are cheap liveness checks returning
  `{"status":"ok"}`. They do not establish dependency or task readiness.
- Authenticated `GET /health/detailed` reports bounded readiness dimensions;
  degraded readiness still uses HTTP 200, so callers must inspect its payload.
- Mutable container state is rooted at `/opt/data`, including `.env`,
  `config.yaml`, sessions, memories, skills, profiles, and logs.
- The pinned release documentation describes s6 supervision: the gateway is a
  supervised child and the container command can remain alive while s6 restarts
  it. Container-running and gateway-running are therefore distinct signals.
- Upstream warns against two gateway containers concurrently writing the same
  data directory.
- Profiles isolate configuration, memory, sessions, skills, credentials, and
  gateway service state. Multiple profiles in one container require distinct
  API ports.

Sources are the tagged upstream release, Docker guide, API Server guide,
environment-variable reference, and pinned source tree:

- https://github.com/NousResearch/hermes-agent/releases/tag/v2026.8.18
- https://github.com/NousResearch/hermes-agent/blob/v2026.8.18/website/docs/user-guide/docker.md
- https://github.com/NousResearch/hermes-agent/blob/v2026.8.18/website/docs/user-guide/features/api-server.md
- https://github.com/NousResearch/hermes-agent/blob/v2026.8.18/website/docs/reference/environment-variables.md

## Observed behavior

- Host architecture was `arm64`; Docker Engine 27.5.1 and a three-node kind
  cluster were running.
- The initial registry timeout was resolved before Checkpoint A.2. Local image
  inspection verified the release RepoDigest, Linux OS, and arm64 architecture.
- Three fresh named-volume provisions reached liveness and detailed health in
  16.116 s, 10.557 s, and 10.245 s.
- `/health` returned HTTP 200 with platform/version identity. Authenticated
  `/health/detailed` reported gateway, config, disk, state DB, queues, and model
  checks as `ok`.
- With no inference provider configured, detailed health still reported
  `model.status: ok`; invocation returned HTTP 200 with a provider-authentication
  failure as assistant content and zero token usage.
- Explicitly stopping the gateway left the container running while native
  gateway status reported not running and HTTP liveness became unavailable.
- A deliberately short API-server key left native gateway status running but
  the API surface unavailable; inspected native logs did not clearly surface
  the invalid API configuration.

## Assumptions

- `nousresearch/hermes-agent:v2026.8.18` is the intended release image naming
  convention. Registry evidence is required before using it.
- A single default-profile container is sufficient for the smallest E1-E3
  probe once a model credential and image are available.
- The OpenAI-compatible non-streaming endpoint is a realistic minimal
  interaction surface for E2.

## Unknowns

- Cold-pull time-to-ready distribution; the three measurements used a locally
  available image.
- Whether detailed health can reliably test configured-model usability using a
  provider-specific configuration not available in this environment.
- Model credential/provider available for a safe real invocation.
- Whether one platform Agent Instance should map to a container, a profile, a
  gateway process, or a different Hermes unit.
- Practical concurrency and scaling limits beyond the documented shared-data
  writer restriction.

## Documentation/runtime conflicts

Live evidence conflicts with a natural reading of detailed readiness:
`readiness.status` and `model.status` were `ok` even though no inference
provider was configured and a task could not complete. HTTP 200 invocation
also represented provider failure as normal assistant content.
