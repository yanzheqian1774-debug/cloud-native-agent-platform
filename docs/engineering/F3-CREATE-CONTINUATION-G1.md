# G1 — continue saved draft after business-scope refusal

Base c9442c6; same A–F delivery package and F3 conversation layout. Real latest
result is already SUCCEEDED/DRAFT_READY and adopted. Never call the model again,
replace its invocation/key, or treat the downstream CREATE refusal as execution
UNKNOWN. No actual platform operations in this isolated branch.

Known CREATE + create-problem + exact BUSINESS_SCOPE_DENIED displays saved draft
and downstream authorization pending. BODY_CONTEXT exact result/source permits
'资料正文已读取'; otherwise do not claim it. Fold technical reason into details.
Keep one fixed editable local draft using the existing routed-input storage key;
while current work is paused, disable send with a clear preservation explanation.
Do not require opening another conversation.

Recovery uses backend owner's read-only exact original draft/conversation/create
key observation. Existing CREATE resumes that exact revision. Exact absence plus
current owner/result/source authorization permits an explicit same-key CREATE;
other read/permission/network outcomes do not permit it. No clearing pending on
an arbitrary error, no automatic POST/retry, no new model invocation. Coordinate
owner contract with understanding agent before implementing recovery mutations.

Owner contract agreed: GET /conversations/{id}/create-status with original
requestKey and draftInvocationId returns state, draftInvocationId, requestKey,
journeyKey, journalVersion, aggregateVersion and optional real revision. The UI
matches all bindings. NOT_CREATED is observation, not permission: explicit click
persists a pending marker before same-key CREATE; normal owner rechecks authority.
A lost POST response no longer leaves the previous rejection as the latest fact.
CREATED consumes the exact returned revision without another CREATE. Permission,
unknown, mismatched or incomplete readback never dispatches. Final save resumes
CRITERION through existing owners, retaining original draft/model invocation.

Source-read wording requires current GET original invocation BODY_CONTEXT with
exact id/context/aggregate/source comparison; absent/mismatched proof only says
saved draft. No inference from DRAFT_READY or actual operator evidence files.
Controlled regression includes lost CREATE response/reload, existing CREATE,
exact absence, denial/unknown/mismatch, and editable draft preservation. No model
call or actual platform operations used. Backend owner patch is a dependency.
