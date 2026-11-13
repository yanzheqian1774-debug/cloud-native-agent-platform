# Fixed-work configuration frontend G1

Depends on fixed-work-authoring (0067) and nested persisted discovery owner. The
frozen F3 `team-routines` page remains the product entry; this increment replaces
its global placeholder with actual team selection and configuration read/write.
No execution, enable, timer, event delivery, implicit model parsing or grants.

Reuse existing team directory/exact digest verification, Workbench session/CSRF,
F3 team cards and scoped navigation. The new component is mounted by principal
and exact team revision. All reads verify current identity before/after, team and
configuration digests, and nonexecution flags. Mutation rechecks canSave from the
owner and submits via the existing trusted command client; owner remains final.
Signed cursor comes only from server. Persisted configuration discovery is never
inferred from sessionStorage; storage holds only unsent text and same-key pending
save intent. Unknown result keeps its exact key/body, explicit GET readback and
idempotent continuation; refresh never POSTs. Invalid local input stays editable.
Technical error codes collapse in details. Scope switch/late response epochs
prevent stale updates; no arbitrary return URL.

First package scope: true selected-team directory, save, revision, refresh,
READ-only display, permission-change preservation, unknown readback and same-team
return. Literal instruction+explicit time/event intent is configuration only.
Remaining complete-product scope: governed instruction interpretation/definition
validation, bound service identity and continuing execution policy, normal plan
instantiation, trustworthy trigger receipts, actual scheduled/event runs and their
results. These are not claimed complete by this frontend.

Validation: single-worker controlled browser uses server-backed fixture records,
clears browser storage and rediscovers records; tests read-only/revocation, loss
recovery, revision CAS payload, responsive layout, unchanged team navigation and
invalid-input correction. Full frontend lint and production tsc/Vite build.
Prototype and controlled-page screenshots are comparison evidence, not deployed
runtime acceptance. Root alone applies migrations/configuration and real writes.

Review follow-up: every asynchronous action captures a workspace epoch. Save
checks the epoch after preflight and carries an AbortSignal through the existing
command client's session check and POST; session invalidation/unmount aborts it.
A late preflight response cannot silently continue an old click, even if a new
session belongs to the same principal. Existing pending command identity remains.
