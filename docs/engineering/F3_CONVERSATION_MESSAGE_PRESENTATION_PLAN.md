# F3 conversation message presentation (G1)

Scope: approved F3 incremental message presentation, candidate only. Preserve frozen prototype, authorizations, budgets, audit, command owners, original content and installation boundary. Do not implement task-directory query proposal here.

Current evidence: private_conversation.read returns author_id/created_at, omitted by frontend type. conversation_actions.insert uses the initiating principal even for SOURCE/ACTION_INTENT/RECEIPT; these are not assistant-authored replies. ConversationJourney aggregates assistant processing/result separately, with execution events carrying true recorded times; UI journey messages have no timestamp.

Changes: reusable identity row; historical users use returned author_id (fallback 用户), no current-viewer substitution. User groups right aligned, paragraphs remain left aligned, short bubbles intrinsic width. Action records identify the real actor and remain inspectable, not attributed to assistant. Assistant aggregate uses 工作助手 and explicitly labels latest persisted execution-event time as 执行更新, not message creation; missing time remains 时间未记录. No inferred digital person from participants. Compact acknowledgement details replace repeated large receipt cards. Keep fixed composer, independent scroll, source links and stored views intact.

Validation: real-author vs viewer, missing/invalid time, short/multiline text, consecutive messages, action records, exact content, desktop/390 overflow/alignment, persisted input/reload; existing clarification/stream/native Markdown/detail focus and scroll checks. Frontend lint/build and scoped browser suites. Candidate real-history screenshots/video without business commands or model calls, same-size reference comparison, then send evidence to prototype reviewer. Functional tests, visual review and installation remain separate gates.

Risks: inherited style specificity, misleading actor or timestamp, collapsing actionable records, streaming scroll regression. Use exact fields only, explicit update label, keep action controls reachable in details, reuse existing scroll owner. No backend/schema/lifecycle changes; rollback frontend files only.
