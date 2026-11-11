# F3 MCP invocation source integrity — G1

## Finding and scope

The private MCP test invocation uses the current draft (or published fallback)
endpoint while a governed selection can refer to an older discovery snapshot.
It also omits the actual source revision from its receipt. Before exposing tool
execution in the F3 management surface, reject a stale/missing/corrupt selection
provenance before network dispatch and bind new receipts to the exact validated
runtime revision. Disabled or archived sources must not execute. Historical
receipts remain unchanged and must not be inferred from selection ancestry.

## Implementation

Within SkillMcpService, resolve the current runtime revision once. Check the
selection and its discovery snapshot identify that same revision and digest,
validate the saved catalog digest and selected tool presence. Instantiate the
transport from the validated revision, not a second implicit lookup. Record
source revision/digest and snapshot identity/digest on new receipts; dispatch
state distinguishes cancellation, initialization, call attempt and response.
Authorization string, existing owner transaction/version checks and no automatic
retry remain unchanged. A transport failure after dispatch is not proof that
no external effect occurred. No new execution button or grant is introduced.

## Compatibility and gates

Private workbench owner bug fix, additive receipt fields, no schema migration,
public CRD/contract change, new persistence, or Task/Runtime lifecycle change.
Existing exact selections still work. Old records without provenance can be read
but cannot be used for new calls; a fresh discovery/selection is required.
No retrospective rewrite, invocation replay, model or Native budget renewal.

## Validation

Use a real local HTTP MCP server with request counting: matching source executes
once and carries provenance; cancellation dispatches nothing; changed endpoint,
missing provenance, corrupt catalog and disabled/archived source dispatch nothing.
Verify owner records unchanged on rejected attempts and existing redaction.
Retain integration and current professional-experience regression. Separate these
local transport checks from installed UI/general execution acceptance.

Result integrity: an MCP tool error returned inside a successful HTTP response
must be recorded as a tool failure, not SUCCEEDED. Preserve the redacted result
and RESPONSE_RECEIVED evidence; no retry or claim that side effects were absent.

## Readback and F3 presentation

Extend the existing exact MCP READ_RESOURCE projection with bounded receipt
metadata only: no inputs, outputs, credentials or arbitrary error text. Match
receipt source revision/digest, discovery snapshot/digest, selection and tool;
never infer old receipts from selection ancestry. Group exact metadata by tool
and snapshot. Expose a separate source-level count for legacy unattributed
records, explicitly not assigned to the current tool/version. Latest 1000 source
receipts and 20 matching receipts per tool are bounded with partial flags.

In existing tool detail, distinguish tool response, reported tool error,
pre-dispatch cancellation/failure, and result unknown after call attempt. Unknown
never says not executed or offers retry. Identity/scope changes use existing
withdrawal controls. Source versions remain in the expandable technical details.
No new mutation, grant, invocation control or model call is added.
