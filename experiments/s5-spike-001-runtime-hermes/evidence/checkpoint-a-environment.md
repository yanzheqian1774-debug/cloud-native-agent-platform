# Checkpoint A environment evidence

Date: 2026-08-21 (Asia/Shanghai)

- Platform base commit: `3cd910f150a13e366c45cd6f83878f395a74efe8`
- Branch: `codex/s5-spike-001-checkpoint-a`
- Host: macOS arm64
- Docker client/server: 27.5.1 / 27.5.1
- Kubernetes client: v1.36.3 darwin/arm64
- kind: v0.32.0; cluster `agentos-dev` exists with three nodes
- Docker Hub connectivity: `registry-1.docker.io/v2/` and
  `index.docker.io/v2/` each timed out after 15 seconds
- Hermes image: unavailable locally; pull could not complete

Classification: environment-related blocker for live E1-E3. This is not a
Hermes runtime failure and does not support PASS/FAIL claims about H1-H6.

## Checkpoint A.2 update

The registry blocker was subsequently resolved by the human operator. Local
inspection verified the expected RepoDigest and enabled live E1-E3 execution.
This original record is retained as historical environment evidence; it is no
longer the current blocker.
