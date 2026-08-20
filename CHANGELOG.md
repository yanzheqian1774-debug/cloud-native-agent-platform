# Changelog

Notable project changes are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project does not yet promise semantic-versioning compatibility.

## [Unreleased]

## [0.1.0-alpha]

### Added

- Kubernetes `Agent`, `Task`, and `Workflow` custom resources in the
  `agentos.io/v1alpha1` API group.
- A Kubernetes operator that reconciles agent workloads, executes tasks, and
  schedules workflow DAGs with dependency propagation, retries, failure
  handling, and dependency skips.
- A replaceable Python agent runtime with deterministic mock and
  OpenAI-compatible model-provider adapters.
- A read-only Workflow Execution Console for inspecting current Kubernetes
  workflow and task state.
- Source-based local Kubernetes installation, an ownership-safe Quick Start,
  and a Golden Engineering Demo.
- Contributor, security-reporting, troubleshooting, and Alpha architecture
  documentation.

### Changed

- Hardened Python and frontend validation and documented the currently
  qualified macOS ARM64 and Ubuntu 24.04 Linux AMD64 development journeys.
- Clarified current-versus-planned capability boundaries and known divergence
  from accepted architecture decisions.

### Known limitations

- This is an Alpha release and is not production-ready. It provides no support,
  availability, compatibility, or upgrade guarantees.
- Distribution is source-only. No operator or runtime container images, Python
  package, Helm chart, CLI binary, or standalone installer are published.
- Local image builds require access to external container registries and Python
  package artifacts. Base-image tags are not digest-pinned, so rebuilding a tag
  is not guaranteed to produce byte-for-byte identical images.
- Qualification is bounded to the environments documented in the
  [release notes](docs/releases/v0.1.0-alpha.md); broader platform compatibility
  is not claimed.
- The Console is read-only and does not provide authentication, authorization,
  multi-tenancy, durable history, distributed tracing, or cost governance.
- Known implementation drift remains for accepted ADR-0003, ADR-0004, and
  ADR-0005.

[Unreleased]: https://github.com/yanzheqian1774-debug/cloud-native-agent-platform/compare/v0.1.0-alpha...HEAD
[0.1.0-alpha]: https://github.com/yanzheqian1774-debug/cloud-native-agent-platform/releases/tag/v0.1.0-alpha
