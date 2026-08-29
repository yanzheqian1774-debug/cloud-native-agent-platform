# S5-IMPL-033 — Product View Live Planning and Correction Journey

## Checkpoint A boundary

This uncommitted Checkpoint A candidate implements the internal Product View live
planning and correction journey authorized by the Human
`S5-IMPL-033 Package 5 Allocation and Checkpoint A Implementation Gate`.
It remains an internal Technical Preview and grants no public compatibility,
Golden Demo, release, production-readiness, or certification claim.

The candidate consumes the accepted S5-ARCH-010/011/012 boundaries and the
durably integrated Package 1–4 planning, matching, Native placement, Knowledge,
Evidence, Graph, snapshot, and execution seams. It changes none of those
authorities. Kubernetes remains current execution-state authority; the Canonical
Graph remains relationship authority; backend-issued records remain identity,
Evidence, citation, approval, and revision authority.

## G1 implementation plan

1. Add strict internal journey DTOs and an in-memory coordinator over existing
   authoritative identities.
2. Add server-scoped exact-digest correction, approval, and rerun endpoints.
3. Add strict frontend live adapters and equal Product/Technical sibling
   projections with explicit failure/provenance states.
4. Validate immutable succession, isolation, nondisclosure, live/synthetic
   separation, localization, responsive rendering, and repository gates.

No G2 trigger was found. A public API/CRD/Graph/shared-DTO/lifecycle/persistence or
authority change remains a stop condition.

## Implemented behavior

- one live journey is registered only from backend-issued `LIVE_EXECUTION`
  Package 1–4 identities;
- Product and Technical projections carry an identical tenant/security-domain,
  canonical revision/digest, approval, snapshot, Graph, execution, placement,
  Evidence, and citation identity bundle;
- a semantic correction is bound to the exact predecessor revision and digest,
  creates a deterministic new candidate digest, and leaves the predecessor
  immutable and queryable;
- the successor requires a fresh exact-digest Human approval; replay mismatch and
  stale/mismatched digests fail closed;
- rerun delegates to the existing execution authority and accepts only its issued
  execution/snapshot/Evidence/citation/Outcome result;
- predecessor and successor Outcomes expose the same stable comparable metric;
- tenant/security-domain scope comes only from trusted server configuration;
- denied requests use a constant-shaped nondisclosing error;
- live registration and the frontend adapter reject synthetic provenance, and
  live network/authority failure never selects the existing synthetic fixture;
- Knowledge failure cannot produce a successful answer or citation;
- English and Simplified Chinese localize labels only. IDs, digests, enums, states,
  and reason codes remain unchanged.

## Scope and impact

- Public API: none; new endpoints are `/api/internal/preview/v1/...` only.
- CRD/Kubernetes API group/schema: none.
- Workflow, Task, Runtime, Provider, Capability, or execution lifecycle: none.
- Shared DTO and Canonical Graph semantics: none.
- Persistence, dependency, lockfile, and CI workflow: none.
- Package 6A `InterventionEvent` / `OutcomeFeedback`: not implemented.
- Governance files: unchanged.

## Validation record

Checkpoint A completed with the following current evidence:

- focused backend/API/security/equality/provenance tests: 11 passed;
- frontend ESLint, TypeScript and production Vite build: passed;
- desktop `1280×720` and mobile `390×844` browser QA: passed;
- direct historical Product ownership compatibility test: passed;
- full `make check`: Ruff lint, Ruff format and 872 tests passed;
- all-files pre-commit: Ruff lint, Ruff format and pytest passed without mutation;
- post-hook `make check`: Ruff lint, Ruff format and 872 tests passed;
- `git diff --check` and exact sixteen-path audits: passed.

The known Starlette/httpx deprecation warning remains unrelated to Package 5.

## Checkpoint C terminal handoff

Checkpoint C starts from corrected baseline
`7fce5fcd67475811bfcfc922ce3475e2b1d1b7da98`. This candidate is ready for
normal commit, Draft PR publication and exact-head CI under the separately granted
Human gate. This record does not claim merge, Durable Integration, Human closure,
REL allocation, Golden Demo acceptance, release readiness or production readiness.

## Rollback and limitations

Rollback disables the live journey endpoint/adapter. Existing execution,
planning, matching, placement, Knowledge, Evidence, Graph, and synthetic preview
behavior remains independently available. The coordinator is intentionally
in-memory and requires explicit live authority registration after process start;
no persistence or silent fixture bootstrap exists. Checkpoint C, commit, push, PR,
merge, Package 6A, Golden Demo, and Release work require separate Human gates.
