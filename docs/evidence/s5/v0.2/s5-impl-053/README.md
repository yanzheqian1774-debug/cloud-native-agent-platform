# S5-IMPL-053 — Unified Product Assembly Browser Evidence Correction

## Scope and defect correction

The corrected acceptance uses a per-Playwright-process trusted tenant scope and
creates every durable fact through its existing private API. It does not write
the database directly. The browser drives the mandatory Agent validation, exact
Human review, publication, problem rematch, navigation, filters, deep links and
all product assertions.

The first clean real-service run exposed `BOUND_RESOURCE_NOT_FOUND` when an Agent
draft supplied exact Skill, MCP and Knowledge bindings. `_WorkbenchBindingResolver`
composed only the existing Workflow and Runtime Profile adapters. The bounded fix
now reads Skill/MCP and Knowledge through their existing scoped services and
repositories, returning only `BindingResolution` facts. No authority or resource
data is copied into `app.py`; existing binding validation remains the fail-closed
decision point.

Browser-visible defects corrected with conditionally authorized frontend paths:

- Resource Catalog lacked a lifecycle-status control and omitted Knowledge's
  durable `AVAILABLE` state.
- Digital Employee templates reported only a binding count, not exact composition.
- Relationship rows did not expose the target digest or a related-resource link.

## Deterministic setup and browser actions

Setup APIs create and publish one Skill, one governed MCP resource with a real
local Streamable HTTP discovery snapshot/tool selection, one Knowledge resource
with an active index snapshot, one Runtime Profile and one Workflow. They create
the Agent as a draft and create the question while that Agent is ineligible, so
the initial `supplier-quality-analysis` gap is durable and real. A bounded local
OpenAI-compatible planning/embedding fixture supplies deterministic provider
responses; it is not resource, binding or execution authority.

The browser then:

1. reads the exact initial question/gap record;
2. follows the Agent Attention link into its owning Workbench;
3. validates, reviews and publishes the exact composed Agent revision;
4. invokes the real rematch action and reads the resulting exact match;
5. filters and searches all six catalog kinds by real lifecycle state and identity;
6. follows the Agent-to-Skill relationship and verifies its revision and digest;
7. verifies Product/Technical Agent identity, revision and digest parity;
8. verifies the Digital Employee template's five exact bindings;
9. restarts the backend and reopens Dashboard, Catalog, Relationships, Attention
   and Digital Employees from reconstructed durable facts.

## Exact browser facts from the complete regression run

| Kind | Canonical identity |
| --- | --- |
| Agent | `agent-definition:519c244e-a09e-4d47-9aef-f6e35941964f` |
| Skill | `skill-definition:3ae99a3f-102c-4f83-8337-24b8c85256ea` |
| MCP | `mcp-definition:6789e9b5-0b58-48a0-aef3-ba625550698b` |
| Knowledge | `knowledge:3921ed83-1720-4c4a-a426-6bb428252794` |
| Workflow | `workflow-definition:cd2d58e5-2f02-484e-87e7-cf277781e558` |
| Runtime Profile | `runtime-profile:1aeba81d-84d1-4156-9d48-e7c6ee7fc608` |

The canonical relationship checked is the published Agent `BINDS` edge to the
exact Skill identity/revision/digest. The Attention link targets the exact Agent
draft before publication. The question changes from a real `GAP` for
`supplier-quality-analysis` to `MATCHED` with the published Agent identity,
revision and digest; `executionAuthority` remains `NOT_GRANTED`.

Product and Technical projections display the same Agent identity, published
revision and digest. The Digital Employee template is unconditionally asserted
to be `MATCHABLE` and to contain exact Skill, MCP, Knowledge snapshot-bound,
Workflow and Runtime Profile bindings.

## Preserved boundaries

Before and after publication/rematch, browser assertions preserve `PREVIEW`,
`NOT_CERTIFIED`, `NON_PRODUCTION_READY`, `TEMPLATE_ONLY`,
`UNVERIFIED_MODEL_REFERENCE` and `NO_EXECUTION_AUTHORITY`. MCP remains bounded to
governed discovery/selection and grants no invocation authority. Knowledge binding
does not grant retrieval authority. Workflow and Runtime Profile references grant
no execution or placement authority. The denial test returns only
`PRODUCT_ASSEMBLY_ACCESS_DENIED` and does not disclose scoped identities.

Missing and foreign-scope resolver reads both return no resolution. Existing
binding validation rejects unpublished, disabled, deprecated, incompatible,
stale-revision, stale-digest, ungoverned-tool and absent-snapshot references.

## Validation

- `uv run pytest console/backend/tests/test_unified_product_assembly.py console/backend/tests/test_agent_binding_validation.py console/backend/tests/test_agent_definition_api.py console/backend/tests/test_agent_definition_service.py`
  — 16 passed, one existing Starlette/httpx deprecation warning.
- `npx playwright test tests/e2e/unified-product-assembly.spec.ts`
  — 2 passed against PostgreSQL, Qdrant and bounded local provider/MCP fixtures.
- `npx playwright test`
  — 9 passed, zero skipped, using the complete real-service Chromium suite.
- `npm run lint && npm run build` — passed; Vite production bundle completed.
- `make check` — passed: Ruff lint, Ruff format and 1,106 tests passed. Thirteen
  infrastructure tests reported their explicit existing "real PostgreSQL/Qdrant
  required" skips; the complete real-service Chromium suite separately exercised
  those configured services with zero skips.
- `uv run pre-commit run --all-files` — Ruff lint, Ruff format and pytest passed.
- `git diff --check` — passed.
- Fresh exact-head CI is recorded in the final routing result after push.

No migration, dependency, public contract, CRD, Kubernetes, deployment or
execution-authority change is included.
