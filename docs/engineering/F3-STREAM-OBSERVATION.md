# F3 stream observation correction

G1 bounded correction: distinguish progress validation, progress reader availability,
service failure and transport loss without adding calls or retries. Preserve all
live authorization checks, cancellation cleanup, UNKNOWN and budget semantics.

Only fixed public reason codes are sent. No exception text or resource identity
is copied. Existing provider deadline diagnostics may record a white-listed
cancellation_source only when cancelled; absent sources and historical receipts
remain compatible. ASGI cancellation is a delivery category, never an assertion
that the user clicked cancel. No actual provider/runtime/configuration changes.

Validate SSE error redaction, single dispatch, cancelled worker source capture,
ordinary timeout/cancellation compatibility, frontend messages and successful result.

Verified: 8 new subprocess/SSE tests; 33 existing streaming/deadline tests;
2 isolated PostgreSQL receipt save/restart cases; 7 frontend Response tests;
frontend lint and production build. Test fixture identity omissions were corrected
before these final passes; production invocation identity routing is unchanged.
No end-to-end provider or deployed-page verification is claimed by this package.
