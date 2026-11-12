# Document rule Native integration candidate

Status: candidate implementation; not deployed and not real-model acceptance.

The existing ontology owner now accepts the additive `business-document-rules.v1`
content contract. It supports explicitly applicable required sections and single-value
fields, not a general business rule engine. Results distinguish SATISFIED, MISSING,
UNKNOWN and CONFLICT; SATISFIED is a textual rule match, not business approval.

`execution-preparation.v3` commits a `document-semantics-binding.v1` containing the
exact published rule revision, knowledge revision, mapping and scope. Existing v1/v2
preparations and executor revisions remain unchanged. Existing migration 0045 stores
immutable bindings; no migration file or infrastructure dependency changed.

An optional `documentRules` on an authorized document `ReadonlyWork` selects that
binding before execution-plan approval. Its mapping digest enters the approved plan.
The original continuation key still allows only one run per source plan. No policy is
automatically installed or extended. Existing policies retain their canonical digest
when this optional field is absent.

Native document executor revision 4 requires the rule binding and content. It reuses
the governed loop, user-scope clarification, employee context, journal and budget.
Every decision rechecks the exact rule USE grant and current publication state.
The tool adapter computes rule findings and the executor rejects an unbound or altered
report, including dependency reuse. Historic document executors retain their tools.

Result projection displays pinned rule version, document name, distinct outcomes and
original lines. Rule details, sample execution and definition publication are separate
states. The existing independent-review requirement remains in the ontology owner.
The new document binding never enters the sales evaluator.

Remaining delivery gates:

- Actual original-conversation document continuation with the new resource bundle,
  policy binding, real model and exact ordinary-account authorization.
- Live migration compatibility, model/budget readiness and controlled deployment.
- Main-site shared shell visual acceptance, per-action permission projection and
  current-published plus single-modification-draft aggregation.
- Review of actual source/rule semantics; the live candidate uses a production release
  handover where rollback and a single accountable owner are applicable.

OpenClaw remains isolated and disabled. Tests using model/transport doubles do not
establish real execution, real human review or business acceptance.
