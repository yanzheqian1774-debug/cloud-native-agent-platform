# F3 tools workspace — G1 implementation plan

Baseline: ae6b322, frozen V6.9-F3. This is part of the existing five-category
resource scope, not a replacement of Tools with Workflow or Runtime.

## Existing owners and first vertical slice

MCP service persists discovery snapshots with exact revision/digest and selected
tool names. Trusted directory currently exposes neither. Add an authenticated
read projection at `/resource-directory/mcp/{identity}/{revision}/tools` using
the existing exact MCP READ_RESOURCE grant and authorized database transaction.
Read the existing repository only. No discovery, connection, model, publication,
grant, new persistent object or new infrastructure is required by this read.

Project only discovery snapshots matching the requested revision and digest;
verify their stored catalog fingerprint before displaying operation names and
input/output declarations. Distinguish saved selection from invocation authority.
Legacy snapshots without exact provenance cannot be assigned to a revision.
Do not expose connection/credential configuration or invocation inputs/results.
The existing invocation record identifies a selection but not the revision used
by `_mcp_client`; selection ancestry alone is insufficient proof of an exact
version invocation. Keep actual invocation readback explicitly unsupported until
the owner can supply authoritative provenance, rather than relabeling it success.

Frontend sequence: `/tools` in the frozen resource navigation, scoped MCP source
list with explicit paging, selected-source fixed snapshot operations, exact
operation detail and return to the same MCP/source context. Preserve route and
session identity across asynchronous reads; bounded waits, manual retry only.
No eager per-source detail fanout, no latest-version substitution and no fake
published Tool aggregate. Installed UI must clearly call these saved MCP
operations and distinguish their source publication from independent tool state.

## Remaining full scope

This slice does not complete API/OpenAPI import, plugin import, code-tool editing,
governed tool lifecycle, execution tests, or task/employee binding of independent
tools. Those frozen requirements remain open and need their respective owner
contracts and implementation; a readonly MCP projection is not their substitute.
Ontology remains a separate resource category, not covered by this work.

## Validation and delivery

Backend: exact grant/session and cross-scope rejection; historical snapshots;
same-name operations in different sources/snapshots; digest corruption; missing
legacy provenance; bounded partial results; selection without execution; no
credential/output leakage or mutations. Use real PostgreSQL/BFF integration in
addition to deterministic projection tests.

Frontend: source/operation identity, return/paging context, unavailable versus
empty, identity change, late responses and unsupported actions. Lint/build and
actual isolated browser read of existing records are required. Compare frozen
Tools layout to actual settled page and submit to prototype reviewer before
installed acceptance. Keep tests, isolated records and installed evidence separate.

Compatibility: additive private read endpoint, unchanged lifecycle contracts,
existing owner/grants and PostgreSQL storage. No public CRD, authentication,
Control Plane, Runtime/Task lifecycle or cross-plane ownership change. Ordinary
implementation decisions remain authorized; any genuine G2 conflict is escalated.

Functional audit correction: the existing directory inline expansion called the
prepared-run usage projection actual usage records. Align its heading and
explanation with saved task references; the same endpoint remains unchanged.
This removes a false invocation claim without adding or removing owner facts.

Direction review: Tools must display operation cards, not duplicate the MCP
service directory. Source is a filter/provenance dimension loaded on demand.
Cards show operation name/purpose/source/discovery time; details show declared
inputs, outputs and side effects, with raw schemas folded. Missing declaration
means not provided, not safe. NO_EXACT_SNAPSHOT differs from an exact snapshot
containing zero tools; legacy provenance must never be silently assigned latest.
Keep source page/filter/snapshot/operation/scroll on return. Source publication,
saved selection and actual invocation remain separate. Reviewer direction is
not feature acceptance; real database/route and actual-page comparison remain.

Actual isolated candidate: existing MCP quality.lookup card/detail/source/return
and refresh/filter preservation verified with real backend, no response overlay.
Original business, budget and execution tables unchanged; login/audit rows change.
Reviewer requires known source archived/disabled states on both card and direct
detail, each derived from its own owner field. Added this correction and its
regression before installation; source filter height is a nonblocking visual gap.
