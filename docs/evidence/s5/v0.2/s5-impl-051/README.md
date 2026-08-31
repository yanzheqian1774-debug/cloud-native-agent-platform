# S5-IMPL-051 — Agent Builder and Governed Resource Bindings Evidence

## Entry revalidation

- Human-authorized baseline: `6c3b72e416fa21dc77be94d9be4bb054b39caef4`.
- Fetched `origin`; `origin/main` and initial `HEAD` exactly matched the baseline.
- Worktree was clean, detached and isolated before branch creation.
- Branch: `codex/s5-impl-051-agent-builder-governed-bindings`.
- Repository, branches, worktrees, PRs, issues and visible Codex allocations showed no S5-IMPL-051 collision or concurrent Agent-domain writer.
- S5-IMPL-042 remained inactive and unowned. S5-IMPL-046 was already merged and inactive.
- Architecture gate: G1. No CRD, Kubernetes API group, public Contract, Agent Instance, Runtime lifecycle, Model Governance, or persistent-infrastructure change.

## Result

The existing PostgreSQL-backed Agent Definition lifecycle now carries bounded typed bindings inside canonical immutable revision bytes:

- exact published Skill revision identity and digest;
- exact MCP resource revision, digest and governed tool name, with optional discovery snapshot;
- exact Knowledge revision/digest and optional snapshot;
- opaque bounded Model reference, explicitly `UNVERIFIED_OPAQUE_REFERENCE`;
- optional typed Workflow Definition and Runtime Profile references.

Validation is storage-independent and fail closed. Missing, unpublished, disabled, deprecated, incompatible, wrong-revision, wrong-digest, absent-tool and absent-snapshot targets reject validation. Omitted Workflow/Runtime references validate; supplied references reject when no authoritative resolver proves their exact identity, revision, digest, publication and compatibility. Publication revalidates exact bindings and grants no execution, invocation, credential, Knowledge-access, Workflow, Runtime, or Model authority.

The browser Workbench includes a guided Builder, non-execution preview disclosure, immutable digest review/publication, successor cloning, revision comparison, relationships/consumers, and bounded manifest export. Capability rematch remains deterministic and returns either `CAPABILITY_GAP` or an exact published definition/revision/digest with `executionAuthorityGranted: false`.

Product and Technical projections retain the same canonical definition identity and published revision. The Technical projection exposes exact governed bindings and explicitly reports no execution authority.

## Migration 0006

- Path: `console/backend/migrations/0006_agent_governed_bindings.sql`.
- SHA-256: `8865d0977d1e028ec711dfe0022adc3454b869b30aac3869c87f138d7b66442d`.
- Additive tables: `agent_definition.revision_bindings` and `agent_definition.binding_facts`.
- Typed binding kinds are constrained to Skill, MCP, Knowledge, Model, Workflow and Runtime Profile.
- Exact revisions/digests/tool/snapshot values contain no secret values or Runtime observations.
- Migration fails if exact prerequisite tables from migrations 0001–0005 are absent.
- Adapter stores and verifies the version-6 checksum and rejects newer Agent Definition schema versions.
- Migrations 0001–0005 were not modified.

## Validation

- Focused backend/API/service/repository tests: `12 passed` (one existing Starlette/httpx deprecation warning).
- PostgreSQL 15 clean chain/checksum/newer-schema/restart tests: `3 passed`.
- Frontend `npm run lint`: passed.
- Frontend `npm run build`: passed.
- Real PostgreSQL-backed Chromium Agent journey: `2 passed`.
- Full real-service Playwright suite with PostgreSQL 15 and Qdrant: `4 passed`.
- `make check`: `1084 passed, 8 skipped`, passed. The eight skips are explicit external-service gates; the three Agent PostgreSQL skips were separately executed against PostgreSQL 15 and passed.
- `git diff --check`: passed.
- Migration checksum, exact-path, secret and prohibited-path audits: passed.

## TRACK_B_SHARED_ASSEMBLY_REQUEST

Consumer: production Agent Definition service construction in `console/backend/src/agent_console/app.py`.

Required shared assembly:

1. pass migration 0006 to `PostgresAgentDefinitionRepository` after migrations 0001–0005 are composed;
2. adapt the already authoritative Skill/MCP and Knowledge repositories to the storage-independent `BindingResolver` port;
3. inject that resolver into `AgentDefinitionService`;
4. later inject authoritative Workflow Definition and Runtime Profile resolvers when Track B creates those authorities.

Until this assembly is integrated, the deployed app continues to use migration 0001 only and supplied governed bindings fail closed with resolver-unavailable. No fake records, silent acceptance, or prohibited `app.py` edit was introduced.

## Limitations and routing

- Model references are opaque and unverified; there is no Model Catalog, discovery, routing, pricing or execution.
- Workflow Definition and Runtime Profile authorities do not exist on this baseline.
- Publication and rematch are advisory/governed discovery outcomes only and never execution authority.
- PostgreSQL validation is single-node continuity evidence, not HA, distributed recovery or production readiness.
- Integration should route next to Track B shared assembly, then exact-head CI and Human review. This evidence does not authorize merge, deploy, REL allocation, Session closure, or a v0.2.2 completion claim.
