# S5-ARCH-012 — Intervention, Preference, Feedback, and Optimization Evidence

## Scope

| Field | Value |
| --- | --- |
| Session | `S5-ARCH-012` |
| Type | `ARCH` |
| Checkpoint | `B — INDEPENDENT_ARCHITECTURE_PRIVACY_SAFETY_AND_MERGE_READINESS` |
| Baseline | `0ea21ab628561f2e1e5e1a08651e9ef5a9b8fc79` |
| Architecture | [Governed Successor and Cold Optimization Boundary](../../../../../architecture/s5/v0.2/S5-ARCH-012-USER-INTERVENTION-PREFERENCE-FEEDBACK-GOVERNED-OPTIMIZATION-BOUNDARY-V1.md) |
| Implementation | `NOT_STARTED / NOT_AUTHORIZED_BY_THIS_ARTIFACT` |

## Architecture evidence

The decision separates correction, canonical patches and successors, intervention
facts, Outcome assessments, preference values and consent, candidates and their input
sets, evaluations, publication decisions, published versions, application decisions,
and rollback records into typed authorities. It preserves S5-ARCH-010 Execution
Evidence, S5-ARCH-011 correction/successor semantics, Knowledge non-writeback,
Canonical Graph authority, sibling projection authority, current APIs/CRDs, and the
Runtime boundary.

v0.2 requires correction, successor, intervention, feedback, consent, isolation, and
Knowledge non-writeback contracts. Preference and candidate behavior is preview-only.
Evaluation/publication/application and governed cross-task optimization are future
v0.3 boundaries.

Checkpoint B independently reviewed architecture consistency, typed authority
separation, hot/cold isolation, consent and deletion, candidate poisoning resistance,
evaluation/publication/application, rollback, projections, metrics, and privacy and
security threats. One bounded linear correction makes stable deduplication,
stale/revoked-input exclusion, consent replay prevention, count/timing suppression,
projection deletion safety, evaluator/publisher separation, template-supersession
rollback, and synthetic-production metric isolation explicit. It also forward-records
the supplied Human-confirmed S5-ARCH-011 closure. These are architecture-only safety
clarifications and create no implementation authority.

This evidence does not establish implemented preference/intervention storage,
optimization, learning, evaluation, publication, Demo behavior, Knowledge writeback,
Runtime Manager, Provider certification, production readiness, or Release acceptance.

## Authorized path inventory

1. `architecture/s5/v0.2/S5-ARCH-012-USER-INTERVENTION-PREFERENCE-FEEDBACK-GOVERNED-OPTIMIZATION-BOUNDARY-V1.md`
2. `docs/evidence/s5/v0.2/s5-arch-012/README.md`
3. `architecture/s5/v0.2/README.md`
4. `docs/governance/REGISTRY.md`
5. `PROJECT_STATE.md`

Rollback of this architecture candidate is a Git revert of these five paths. It does
not delete data, preferences, Evidence, policy, or external effects. Future
implementations require independent migration, deletion, and rollback gates.
