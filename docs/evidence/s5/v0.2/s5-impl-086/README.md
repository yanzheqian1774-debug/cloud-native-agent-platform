# S5-IMPL-086 — Minimum-Disclosure Browser First-Failure Evidence

## Authority and scope

Human authorization allocated S5-IMPL-086 after a fresh global numeric-suffix
reconciliation. The task is a G1, diagnostic-only change to the versioned
Browser Harness and Release Runner. It does not authorize a product correction,
deployment, rehearsal, attempt-06, release-contract schema change, promotion,
or merge.

Durable baseline:

- commit: `f65ce76db64b3c0ab48381674944ec7fbcead7dc`
- tree: `21fa5051e1f78680da390217ec4411074e127cdc`
- exact-main CI: `33606658144 / attempt 1 / SUCCESS`
- Release Runner blob: `27995b3eccb2e0df98ea703178d2785d1df2f733`
- Release Contract blob: `f0fa75bac8222e2f084015069aca17cba0062c5d`
- Release Contract schema: `1` (unchanged)

## Implemented diagnostic boundary

The Harness deterministically walks Playwright JSON suites, specs, and tests in
reported order and retains only the first unexpected result. The stable
assertion identity comes from a versioned, closed mapping of acceptance spec and
test identity to an opaque identifier. Raw titles and errors are transient
classification inputs and are neither persisted nor included in the
correlation digest.

The closed schema and enum identities are documented in
`docs/engineering/ISOLATED_BROWSER_ACCEPTANCE.md`. Missing or unsafe identity
normalization yields `NOT_RETAINED / BROWSER_DIAGNOSTIC_GAP`. The Runner
validates and persists the record before owned cleanup and preserves
`browser-harness` as the first failing stage.

## Checkpoint A evidence

Focused tests cover success without a record, stable assertion identity,
multiple-failure ordering, timeout, HTTP class, navigation, selector-state and
unknown classification, missing and malformed identity, extra fields, paths,
URLs/query strings, credential-shaped content, raw messages and artifact
references, bounded counts, pre-cleanup persistence, and success/failure cleanup
semantics. Exact validation results, commit/tree identities, Draft PR, and
exact-head CI conclusions are reported at Checkpoint A after they exist.

No raw browser artifact, request/response body, internal path, selector, source
text, prompt, runtime configuration value, credential, token, database
identifier, user-entered content, or server-returned content is retained.
