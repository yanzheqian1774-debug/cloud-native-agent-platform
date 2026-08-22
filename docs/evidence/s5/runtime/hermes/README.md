# S5-SPIKE-001 — Runtime Contract / Hermes

> Experimental, spike-only, non-production. This directory is evidence for
> Checkpoint A; it is not a Runtime Contract, SDK, production provider, or
> authorization to change the Agent Control Plane.

Checkpoint A tests whether Hermes-specific lifecycle and interaction details
can remain behind a provider boundary. Production source, CRDs, manifests, and
ADRs are intentionally untouched.

## Pin

- Hermes Agent release: `v0.20.4`
- Git tag: `v2026.8.18`
- Commit: `e624e9fde561e1add9388384012b295fde669ade`
- Image: `nousresearch/hermes-agent:v2026.8.18`
- RepoDigest: `sha256:22e37bb4ed1b0f50cb6bd991dca7ecacd6c9f29df9b4a20fc989d32bc763ccf6`
- Local image ID: `sha256:252a0f02e8bac72b0153d4854af1e42daea7fb99ef654fb7833e815b4bbde691`
- Platform: `linux/arm64`

The source pin is verified through the upstream GitHub tag. The image digest
was verified locally during Checkpoint A.2 and matches the human gate value.

## Harness

The harness deliberately has two layers:

- `harness/runtime_boundary.py` contains runtime-neutral request, result, and
  health types plus orchestration. It contains no Hermes paths, commands, or
  profile concepts.
- `provider/hermes.py` owns the Hermes image, gateway command, environment,
  ports, HTTP paths, authentication, and response translation.

Run unit tests:

```sh
uv run pytest experiments/s5-spike-001-runtime-hermes/tests
```

Run a live experiment only after exporting an ephemeral API key and confirming
the pinned image exists locally:

```sh
export HERMES_SPIKE_API_KEY='ephemeral-value-at-least-8-characters'
python experiments/s5-spike-001-runtime-hermes/scripts/checkpoint_a.py
```

The script creates a unique Docker container and temporary data directory,
records JSON evidence under `evidence/local/`, and cleans both up. Secret values
are never written to evidence.

## Checkpoint status

The initial registry blocker was resolved during Checkpoint A.2. Three clean
provisions and all five scoped health observations were performed. A real
gateway invocation was attempted, but no model credential was present; Hermes
returned HTTP 200 containing an authentication-failure assistant message and
zero token usage. See `evidence/checkpoint-a2-live.md`.

Checkpoint B failure, workload-recovery, persistence, and instance-boundary
evidence is recorded in `evidence/checkpoint-b-live.md`. ED-S5-001 remains open.

Checkpoint C synthesis and the Hermes-derived, non-frozen Runtime Contract
Candidate v0 are recorded in `evidence/checkpoint-c-synthesis.md`.

The ED-S5-001 real-model closure attempt is recorded in
`evidence/ed-s5-001-closure.md`. The debt remains open.
