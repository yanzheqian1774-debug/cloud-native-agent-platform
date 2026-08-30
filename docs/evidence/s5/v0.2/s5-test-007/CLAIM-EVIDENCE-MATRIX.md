# Claim–Evidence Matrix

| Exact claim | Class | Evidence/assertion | Identity/reference | Result | Limitation |
|---|---|---|---|---|---|
| Approved canonical digest is exact | Supported | Package 8 live start and existing planning tests | canonical revision/digest, approval ID | PASS | bounded scenario |
| Published-role matching is deterministic | Supported | matching regression slice | published role/definition IDs | PASS | curated roles only |
| Knowledge retrieval is authorized and cited | Supported | Knowledge authorization/evidence/citation suites | Evidence and citation IDs | PASS | one read-only Pack |
| Compatible Native target is placed and executed | Supported | placement, execution and bridge suites | placement decision and Platform Execution Identity | PASS | Native only |
| Correction creates immutable freshly approved successor | Supported | live journey and bridge suites | predecessor/successor revision/digest/approval | PASS | process-local |
| Outcomes are comparable | Supported | live journey and intervention suites | predecessor/successor Outcome IDs | PASS | bounded metrics |
| Intervention is append-only and feedback supersedes explicitly | Supported | intervention/feedback suites | event and feedback identity tuples | PASS | process-local |
| SSE is ordered and progressive | Supported | journey-event.v1 SSE suites | event ID and sequence | PASS | no durable replay |
| Product and Technical identities are equal | Supported | Package 8 and bridge assertions; Browser QA | complete shared identity spine | PASS | current snapshot |
| English and zh-CN translate presentation only | Supported | frontend source assertion and Browser QA | IDs/enums unchanged | PASS | two locales |
| ROLE_GAP has no generated fallback | Failure | matching negative suite | reason code `ROLE_GAP` | PASS | curated catalog |
| Unavailable/unsupported target makes zero Provider calls | Failure | placement negative suite | placement reason/call count | PASS | Native boundary |
| Knowledge stale/expired/denied/not-found/unavailable/error are distinct | Failure | Knowledge regression suites | state/reason codes | PASS | bounded Pack |
| Live authority/network unavailable has no fixture fallback | Failure | frontend live API and Browser unavailable state | `DEMO_START_NETWORK_UNAVAILABLE` | PASS | no offline live mode |
| Stale/mismatched identities are rejected | Failure | planning/journey/bridge suites | revision/digest/execution bindings | PASS | fail closed |
| SSE resume/gap/order/duplicate/terminal/limit failures are rejected | Failure | stream suites | event/sequence state | PASS | process-local buffer |
| Preapproval denial has zero downstream calls | Denial | planning/Package 8 negative tests | denial reason/call counts | PASS | internal authority |
| Knowledge DENY performs zero reads and discloses no metadata | Denial | Knowledge disclosure suite | constant-shaped denial | PASS | timing residual documented |
| Placement/Provider DENY makes zero Provider calls | Denial | placement suite | denial/call count | PASS | bounded provider |
| Foreign tenant/domain denial is nondisclosing | Denial | Knowledge/journey/intervention suites | tenant/security domain | PASS | internal preview |
| Unauthorized intervention/feedback has no side effect | Denial | intervention/feedback suite | event/feedback tuple | PASS | in-memory store |
| Synthetic provenance cannot be presented as live | Denial | Package 8/bridge/frontend assertions | provenance enum | PASS | sanitized history only |
