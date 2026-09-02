# S5-IMPL-092 — Successor Acceptance Tool Compatibility

## Authority and baseline

This bounded implementation is governed by
`V0_2_2_RELEASE_CONTRACT_G2_DECISION`: `SCHEMA_2_ACCEPTED` and
`EXACT_DUAL_PROVENANCE_ARCHITECTURE_APPROVED`.

- Authorized tool base: `9a515446f9f7baf551b6f3d5762fac9a70dac27a`
- Base tree: `b117eab25a107458840282aa771ebcd7dce8c8eb`
- Base CI: `33620228849`, attempt 1, `SUCCESS`
- Frozen product successor: `51fa5fcb266f1e58083c917dd4c99a02d9165c65`
- Product tree: `ddab80db6d82680d139bc97edac12f521d50a30f`
- Product CI: `33632966183`, attempt 1, `SUCCESS`

## Implemented boundary

Schema 1 remains byte-for-byte unchanged and keeps its historical
minimum-compatible-ancestor semantics for attempts 01–05 only. Schema 2 adds a
separate closed definition, restricted RFC 8785 canonicalizer, external atomic
generator, exact product/tool commit/tree/path/blob checks, authoritative CI
observation interfaces, domain-separated pairing, and a closed external
Evidence-envelope validator.

The compatibility test resolves the exact frozen Git objects, executes the
actual product-side TypeScript producer/reporter, serializes its output, and
feeds it to the current Harness parser. The parser accepts only the five closed
Knowledge operation IDs, chooses the deterministic first unexpected operation,
reduces only structured integer HTTP status to a category, and retains the
exact 22-field diagnostic schema without raw browser content.

## Checkpoint boundary

No production schema-2 instance or final Evidence envelope is generated here.
No rehearsal, attempt-06, release candidate, deployment, cutover, product
successor change, maintenance-ref change, or historical Evidence mutation is
authorized or performed.
