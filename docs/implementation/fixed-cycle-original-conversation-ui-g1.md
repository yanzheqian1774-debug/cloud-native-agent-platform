# Fixed cycle results in original conversation — G1 frontend

Baseline: frozen tree d610e9fca0e4383c9913e2135f6a0abdf03f4ddc. This isolated increment does not edit the running 45-file check or frozen inputs. No runtime, credential, model, grant or database operations.

## Exact ownership and data

Backend is authoritative for owned conversation + immutable BOUND source + committed per-event receipts. Frontend must not synthesize chat messages, infer a run from latest timestamps, or treat a Team activity URL as original-chat delivery. Use the agreed backend contract below; no fallback to guessed links or journal executions. Selected event must remain bound to conversation, work revision/digest, source binding, run and preparation digest. Late responses from a previous event, account, conversation or authorization epoch must not replace current display.

A narrowly scoped read preparation may run automatically only for backend-certified committed event receipts in the exact BOUND conversation. It may grant only existing bounded READ/READ_REFERENCE through the formal owner. It never starts work, calls a model, answers a question, edits an arrangement or retries UNKNOWN execution. Failed/ambiguous read preparation is shown as a read failure, not execution failure; do not loop POSTs on refresh.

## Product presentation

Retain existing F3 composer, unsent draft, scrolling, tabs, resource detail return and original assistant routing. TARGET_REVIEW_ONLY pauses the old manual plan only; it must coexist with periodic results. Add a compact event selector with real scheduled date, time zone and observed state. No invented schedule labels. New events produce a quiet notification and do not move focus, scroll, or change an explicitly selected old event.

Render resources, steps and results from the selected exact execution through existing prepared-execution and delivery components. Show queued/waiting, running, waiting for input, succeeded, failed and unknown distinctly. Execution success alone is not business acceptance. Main content and right-hand business progress refer to the same event. Keep technical identifiers in expandable evidence. Necessary questions without an authorized ANSWER owner show the actual restriction; ordinary follow-up stays with the primary assistant and never silently changes the routine.

## Planned controlled verification

- Two committed events retain separate run/source/artifact attribution; changing selection cannot leak stale responses.
- Original PLAN pause and periodic result coexist; bottom input, draft, tabs and return position retained.
- New event while reading old result does not steal selection/focus/scroll.
- Read preparation is bounded to certified receipts; mount/refresh has zero model/START/ANSWER requests, ambiguous preparation does not automatically repeat.
- Session invalidation clears current readable data; failed READ never displays stale success or implies no execution.
- Waiting/input/unknown/failure/success labels are factual; absent answer authority gives no answer action.

Browser results will be controlled UI evidence, not actual natural two-cycle acceptance. Full production-feature build and real original-chat acceptance remain root stages. Backend owner implementation and real acceptance remain separate from these controlled frontend checks.

## Prototype clarification received from root

Keep the existing fixed header/tabs and bottom composer. Show “已设为固定工作” only after authoritative BOUND, not merely handoff. The compact right-rail selector starts at newest readable discovered event; recording time must not be substituted for scheduled date. A new event never overrides an explicit old-event selection. Preserve per-event detail/tab/scroll state and original unsent input. Only show a future due time if actually observed; never fabricate pending steps. Service results use a system result section rather than fabricated user/assistant messages.

The existing fixed-review composer is disabled because its journal remains PLAN. Backend collaborator confirmed enabling the old C1 route blindly could enter manual planning. This increment will not bypass that gate; proper primary-assistant follow-up routing is a concrete dependency, not an ANSWER grant. It remains an explicitly incomplete end-to-end requirement until a safe owner route exists.

## Owner contract agreed during implementation

Capability `fixedWorkActivity` defaults false. Activity GET is scoped to original conversation and BOUND identity; each committed event supplies receipt, run/preparation, sourceSnapshot, real scheduled time and current readTargetDigest. Full result is read from the original prepared owner and must match run, preparation, problem and source exactly. Native steps/questions come from the original native-progress GET with the same run, never from guessed RUNNING semantics; no answer component or route is mounted.

Initial read command is stable across tabs for actor/scope/conversation/binding/receipt/readTargetDigest. Local intent is durably stored before dispatch. A sent intent is never automatically resent, including when a subsequent GET says NOT_PREPARED. Unknown stays read-only. On confirmed READ_READY plus owner-projected STRICT_SUPERSET, the new bounded read-set command records previousCommandId; backend rechecks the expansion. Explicit EXPIRED plus SAME permits user-requested read renewal only. Shrinking, incompatible or ambiguous sets do not produce a new command. At most the newest discovered receipt and selected receipt are prepared per refresh; old pages are not batch-granted.

Controlled browser r1 (5 cases) and r2 (6 cases including new read-target contract) passed before Native question presentation was added. These counts overlap and are not summed. Subsequent current-source verification is required before freezing. No actual natural DAILY cycle has been exercised by this UI work.


## Final contract additions and explicit limits

START-before-dispatch visibility is `phase=PLANNING`, derived only from a committed planning preparation. `RECORDED` means the request is saved, not that a provider is currently running. `PREPARED` and `REQUIRES_REVIEW` retain the owner meanings. Run, preparation, receipt and read-target identifiers must remain null; no READ preparation or prepared-result call is issued until the same event becomes EXECUTION. No future slot is fabricated.

Known immutable BOUND target confirmation remains displayed during a transient result-read failure; its current execution data and readable event choices are cleared. A changed bound-work/problem signature is held as an error until a fresh page identity is established, rather than silently redirecting an old event selection. Ordinary current-work tabs and per-event process/artifact state are preserved. The initial command hash excludes session expiry; session epochs still protect every read and send. Explicit renewal uses the same single-flight guard and a deterministic previous-command successor key.

Not complete: normal follow-up routing from the paused fixed target is still disabled because the original PLAN route can dispatch manual planning. The current text explicitly describes that limitation and preserves the draft; it does not claim the routine is disabled. Service-question ANSWER delegation is unavailable. Historical viewer scopes beyond their current expiry, real generation transition and two natural DAILY cycles require backend/actual validation. This frontend neither extends leases nor interprets READ as ANSWER.

## Verification and review boundary

Controlled browser scopes: 12-case r6 suite passed (30.5s), then final owner enum/BOUND drift two-case check passed (24.1s); two-case final visual/read-denial check passed (23.4s); one additional UNKNOWN-with-live-old-question check passed (30.5s). They overlap and are not additive. r6 used the earlier planning label, replaced by final RECORDED in the two-case check. Browser commands include TypeScript/Vite build under the controlled feature configuration, not root's actual production flags. Full frontend lint passed; latest modified files also receive targeted lint. No backend owner test is claimed here.

Independent static review found and then closed two bugs: initial command IDs originally included session expiry, and explicit renewal lacked a shared flight lock. Follow-up evidence records the fixes and the PLANNING/BOUND guards; it does not certify backend or actual deployment. The last static conformance change explicitly requires sourceSnapshot=null on planning items (already null in the positive fixture).
