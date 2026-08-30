# Browser QA Evidence

Browser QA uses the genuine backend-started Package 7 journey through the
integrated start contract. No direct coordinator seed or fixture substitution
is permitted.

## Matrix

| Viewport | Locale | Product | Technical | Identity | Overflow | Console/network |
|---|---|---|---|---|---|---|
| 1280×720 | English + zh-CN | PASS | PASS | exact equality | none | no unexpected errors |
| 390×844 | English + zh-CN | PASS | PASS | exact equality | none | no unexpected errors |

The journey displayed progressive `journey-event.v1` state before terminal
completion, then correction, fresh approval, rerun, comparable Outcome,
intervention and feedback. Denial and backend-unavailable states remained
fail-closed with no synthetic fallback. Provenance and limitations were visible.
Navigation, focusable controls, wrapping and responsive layout were checked.

Terminal completion produced sequences `1..6` ending in
`EXECUTION_SUCCEEDED`. The stream closed normally, neither view reconnected,
both retained the completed journey, and no false `JOURNEY_STREAM_UNAVAILABLE`
appeared. The Product view captured one append-only intervention and two
feedback versions: the first became `SUPERSEDED`, and the second remained
`RECORDED`. Browser warning/error logs were empty during the successful run.
Measured document widths equalled viewport widths at both sizes (`1280=1280`,
`390=390`).

Sanitized captures:

- `desktop-1280x720.png` — Product live intervention/feedback view, English,
  1280×720.
- `mobile-390x844.png` — Technical live view, zh-CN, 390×844.

Exact IDs remain machine values and are not translated. Screenshots contain
only the deterministic sanitized Package 7 scenario.
