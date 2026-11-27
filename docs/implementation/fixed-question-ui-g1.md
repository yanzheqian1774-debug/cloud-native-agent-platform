# G1 — exact delegated question in the original F3 conversation

Dependency: frozen 0078 backend 42 (47d9de91), with frozen P1 R3 and the existing
66 conversation UI. This is an independent successor; frozen sources are not edited.

The existing cycle read identifies an unanswered question of the selected exact
run. When the explicit backend capability is enabled, the UI observes that exact
question and prepares its presentation through the original 0078 owner. The
presentation is not a client authorization. Only its saved focus link is attached
to the actual user message. The original C1 request is dispatched once, and only
a terminal saved CURRENT_QUESTION/NATIVE result bound to this presentation and
message can feed the exact 0078 answer endpoint. No Human native answer endpoint,
READ/START authority substitution, service-browser identity, or new model route.

Use the existing fixed bottom input and question text, no new approval workflow.
Show that the system run awaits this user's information, then that the answer is
saved and the system will continue. A separate-new-question choice keeps existing
natural chat routing and must not send to WAIT. Explicit selected-goal changes,
question expiry, run changes, session changes and ambiguous multiple questions
clear answer eligibility. Do not steal scroll position.

Durable client intents precede message/C1/answer writes. Unknown POST outcomes
recover only through original read endpoints and exact request keys; no automatic
repeat, replacement command or second model invocation. An unreadable or missing
receipt remains unverified. Restore never trusts browser storage as authority.

Validation: actual server shape aligned with the existing owner PG; controlled
browser positive one C1/one answer, wrong identity, expired/revoked, lost-response
recovery, independent-new-question and disabled legacy paths; complete frontend
lint/build. Controlled browser evidence is not actual deployment/model evidence.
No public lifecycle/CRD/authentication architecture change; G1 continuation of the
explicitly approved 0078 owner, default off.

R2 review correction: mount, question appearance and reload only observe the original presentation command with GET. They never create presentation or consume its bounded answer lease. The user's actual Send is the only entry that automatically prepares the exact presentation, then saves the actual message and performs one C1/answer sequence. No extra approval prompt. Previously sent uncertain preparation still recovers solely by original GET; no fresh command or automatic re-POST.

R2 explicit recovery continuation: checking a lost C1 outcome reads only the
original saved result and route. If the original terminal exact answer is proven
and its answer command was never sent, offer “按原请求继续”. This resumes the
already sent original message without new C1, keys, presentation, or retyping;
recheck current session, question and presentation permission before the first
answer POST. A sent/uncertain answer command remains GET-only recovery.

## R3 isolated readiness regression correction (2026-11-27)

Controlled delayed journey observation reproduced a product defect: text entered in the initially visible composer disappeared when the fixed-work routed composer replaced it. The correction synchronously preserves each initial draft edit in the same conversation's routed view and unsent recovery storage; it does not send a message, dispatch a model, or alter request keys. A deterministic delayed-GET regression requires the exact text to survive the swap, zero writes before explicit Send, and one message/model fixture request afterward. The original TASK/ANSWER/undefined adoption assertions remain unchanged. Original R2 bytes and its failed result remain frozen; R3 validation and FULL replacement are separate evidence.
