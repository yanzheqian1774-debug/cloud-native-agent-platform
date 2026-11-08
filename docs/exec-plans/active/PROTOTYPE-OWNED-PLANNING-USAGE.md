# Package 05: owned planning usage read journey

User authorizes continuation of all six original packages, including package 05. This task starts a bounded read-only usage journey; it does not close organization budgets, provider invoice reconciliation, or the entire package.

Gate: G1. Existing private-conversation GET locators and separately authorized planning invocation usage GET remain the only authorities. No endpoint, schema, ledger, pricing, authorization or lifecycle changes. No new model calls, settlement writes or business replay.

Implementation: replace the enabled trusted /usage placeholder with current-account conversation-linked planning receipts, bounded to 20 conversations/100 unique invocation IDs. Resolve only readable PLANNING source references; read each original receipt directly via /planning-v2/invocations/{id}/usage. Reauthorize through existing owner on every request. Validate identity before/after reads, limit snapshot lifetime to session expiration or 30 seconds, abort and withdraw on identity loss, focus, route change or late response. Display known local estimated settlements separately from pending reservations; never call local estimates provider bills. Exact safe integer amounts only; absent/denied/malformed receipts are incomplete, never zero. No manual copying of internal IDs.

UI: searchable scoped list, settlement state filter, original receipt details and same-conversation return; existing shell and responsive table styling. No enterprise totals or fabricated timestamps. Known subtotal is explicitly only successfully read local estimates, excluding unresolved/unreadable costs.

Tests: valid settled and pending receipts; duplicate locators; denied/malformed/missing usage; actor switch, late response, session expiry; bounded partial scan; desktop/mobile and zero non-GET calls. Lint, legacy/trusted builds, normal repository checks, actual authenticated platform GET journey after installation. Preserve prior release evidence and all original UNKNOWN/ledger rows.

Completion requires actual installation and real read/return evidence. Isolated tests alone remain candidate evidence. Package 03/04 and global visual gates remain open independently.

Source inspection found conversation planning projection invoked the settlement-capable reader. Route that existing projection through its already supported settle_receipt=False option before actual usage browsing. This prevents a read-only management visit from performing budget reconciliation; explicit original recovery routes remain unchanged. Test the adapter forwarding flag.
