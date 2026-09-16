# Updated A01-A16 evidence index

Historical candidate: `aaa2b773c28a02d4fa16455704e8fe4034a5c585`.
Modified-source local run: r7, `sourceWorktreeDirty=true`.
Final deliverable head and actual CI checkouts are exported after automatic CI terminal.

| ID | Evidence | Status |
| --- | --- | --- |
| A01 | exact Kimi profile/mixed adapter contract tests | PASS |
| A02 | unchanged OpenAI adapter source and full OpenAI regression | PASS |
| A03 | exact Kimi request projection/enum/omitted field tests | PASS |
| A04 | strict response tests + new output/measurement assertions + PostgreSQL no-settlement/worst-case tests; ARCH-318 4.2/6.1/9.1/9.2 | PASS, separated output and measurement |
| A05 | follow-up matrix: config, actual certificate verification, connect branch, real read timeout, post-connect deadline, redirect/disconnect/no retry | PARTIAL; whole-lifecycle hard deadline NOT_PROVEN |
| A06 | exact fake private-file/no environment fallback tests | PASS, local only |
| A07 | inherited dispatch CAS/resource-use/credential-failure tests | PASS |
| A08 | authorization rejection/current admission and browser denial | PASS |
| A09 | same-key race/UNKNOWN observe/cancel no-redispatch | PASS |
| A10 | immutable cap and same-ledger restart tests | PASS |
| A11 | absent/partial/out-of-bound usage writes no settlement, retains worst-case cost | PASS |
| A12 | positive product clarification/edit/confirm/readback | PASS, r7 |
| A13 | denial + UNKNOWN + formal budget refusal; before/after/replay dispatch 10/10/10 | PASS, r7 modified source |
| A14 | fake/local only; dispatch/reservation 10/10 <= cap10; test-only quote | PASS; real calls0 |
| A15 | focused65; frontend lint/build; make check1796/199; browser4/4 | PASS |
| A16 | same Draft PR177; final new-head automated CI recorded in exported delivery bundle | Pending new-head automatic CI at commit time |

See [follow-up evidence](FOLLOWUP-A04-A05-A13.md) for failure history and exact limitations.
