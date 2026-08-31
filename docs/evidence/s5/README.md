# S5 Durable Evidence

This directory preserves selected experimental evidence integrated by
S5-REL-001. It does not contain Production runtime, provider, Capability, CRD,
API, schema, or frontend implementation.

## Evidence sets

- [S5-ARCH-018 architecture evidence](v0.2/s5-arch-018/README.md) records
  entry revalidation, the proposed bounded product-continuity persistence
  decision, implementation handoff and validation. It contains no implementation
  and awaits Human Architecture Review.
- [S5-GOV-003 governance evidence](v0.2/s5-gov-003/README.md) records the
  Human-confirmed v0.2.2–v0.2.4 definitions, bounded persistence direction,
  exact sequence and reserved/unreconciled S5-ARCH-014–017 debt. It grants no
  implementation or architecture implementation authority.
- [Hermes runtime evidence](runtime/hermes/README.md) preserves Runtime Contract
  falsification, configuration and credential findings, failure evidence, and
  certification debt. Hermes remains `EXPERIMENTAL / NOT CURRENTLY CERTIFIABLE`;
  ED-S5-001 remains open.
- [Capability Contract evidence](capability-contract/README.md) preserves the
  candidate contract, REST/MCP substitution, authorization, execution identity,
  failure normalization, and `INLINE_AND_DEFERRED_REQUIRED` findings. The
  Capability Contract remains `NOT FROZEN`.
- [Agent Instance and routing evidence](agent-instance-routing/README.md)
  preserves the logical identity, binding, routing, realization replacement,
  execution identity, and semantic recovery findings.

These evidence sets support the accepted architecture indexed in the
[S5 v0.2 architecture baseline](../../../architecture/s5/v0.2/README.md).
Exact source PR, branch, commit, classification, and disposition are recorded in
the [integration manifest](../../../S5-REL-001-INTEGRATION-MANIFEST.md).
