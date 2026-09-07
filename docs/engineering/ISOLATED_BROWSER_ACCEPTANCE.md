# Isolated Browser Acceptance Contract

The serialized real-service browser suite must run through
`scripts/acceptance/isolated_browser_harness.py`. The launcher requires explicit
backend host/port, PostgreSQL URL, Qdrant URL, immutable release root, and an
external runtime directory. The release Python source path is also explicit. It
rejects an occupied backend port before starting.

The launcher is the sole owner of its Uvicorn child. Lifecycle requests use a
mode-0600 Unix control socket and a random ownership token. Before any signal it
validates the recorded PID, executable/command, working directory, expected
listener port, and token. Tests may stop, start, or restart only through
`console/frontend/tests/harness/ownedBackend.ts`. Process-name matching and
detached replacement processes are prohibited.

Release execution sets `PYTHONDONTWRITEBYTECODE=1` and places any interpreter
cache under `PYTHONPYCACHEPREFIX` in the external runtime directory. The release
must be mode-read-only before launch. Complete path/type/mode/content manifests
are written before and after acceptance. Any difference, or any `__pycache__`
directory or `.pyc` file in the release, fails acceptance; cleanup never removes
such evidence.

CI uses one Playwright worker, no retries, an explicitly selected frontend port,
and a separately selected backend port. Existing listeners are never reused.
PostgreSQL and Qdrant remain protected external services: their explicit
endpoints are passed to the owned backend and the harness never manages their
processes.

Before backend or browser startup, the harness verifies two external
preconditions. The immutable frontend build must have an external,
exact-content-digest-bound identity created only for the approved `LIVE_DEMO`
build mode; a missing, malformed, stale or non-live identity fails closed. The
PostgreSQL URL must authenticate as the explicitly named validation role. That
exact role must successfully exercise transactional schema/table migration and
insert, select, update and delete operations. Identity or privilege failure
stops acceptance before the browser command.

## Minimum-disclosure extraction

Acceptance Evidence is produced only through `minimum_disclosure.py`. Its
allowlist is limited to sanitized state, PID/start correlation, restart and
release-entry counts, manifest digests, journey ID, phase, assertion category,
status code, sanitized exception class, correlation digest, restart relation,
schema version and completion timestamp.
Requests for any other field fail closed. URLs, environment values, source or
prompt text, vectors, Qdrant payloads, credentials and credential-shaped test or
placeholder values are not Evidence fields and are redacted by exclusion.

Raw backend/browser output, Playwright traces, screenshots, videos and error
contexts are not retained. Playwright output is removed before the sanitized
diagnostic is scanned. The diagnostic remains useful through allowlisted
journey/phase/assertion/status/exception/correlation/restart fields. Recursive
plain-file and compressed-file negative controls cover request bodies, runtime
settings, test-key-shaped values, source/instruction content and internal paths;
a prohibited value fails scanning without echoing that value. The
immutable frontend server suppresses request-path logging. Validation helpers
must use structured parsing or exact-field extraction; broad `sed`, `cat`,
`head`, or `tail` file dumps are prohibited for potentially sensitive files.

## Sanitized first-failure evidence

For the primary responsive/focus and Wave 3B real-service scenarios, the log
envelope may additionally contain `stepDiagnostic`. Static Playwright
`test.step` titles identify an allowlisted route, viewport, step ID and action
class. Wave 3B keeps its first ten journey boundaries and splits restart/reload
and mobile Evidence focus handling into static top-level action boundaries. The
JSON reporter does not serialize nested steps, so these boundaries remain
top-level without changing the underlying operations, assertions or order. The
installed JSON serializer is exercised with synthetic primary and Wave 3B steps
before relying on these fields. Only exact allowlisted identities and bounded
structured durations are retained; raw step errors remain transient.
`failedStep` requires a structured step error and is separate from
`lastCompletedStep`; absent failure location remains null.
`elapsedMs` is reporter duration, not inferred wall-clock job time. A structured
test result of `timedOut` identifies the scenario timeout manager; other timeout
ownership remains `UNKNOWN` unless independently established. Existing summary
envelopes without steps remain valid. No timeout or test selection is changed.

`restartCountClass` in the failure summary is explicitly
`SUITE_CUMULATIVE`: the Harness counter starts when one serialized browser suite
starts and includes every owned restart requested by every selected test. It is
not a scenario restart count. Scenario-level restart totals remain unknown unless
a separately authorized structured source provides them; step position must not
be used to fabricate a count.

The CI log also emits one bounded `BROWSER_FAILURE_SUMMARY_V1` JSON line before
cleanup. This independent log envelope does not change first-failure schemas
v1/v2 or the frozen release contract. Its scenario and repository-relative spec
come from the static 19-scenario mapping, never a dynamically echoed title/path.
Unknown scenarios use `NOT_RETAINED` and a null spec/location. `sourceLine`, when
available, is explicitly `TEST_DECLARATION`, not a claimed failing assertion line.
Action is `UNKNOWN`; raw locators, expected/observed values, messages, stacks,
snippets, attachments and their hashes are omitted.

The closed envelope includes validated build mode/manifest digest, failure enums,
and selected/executed/passed/failed/skipped/flaky test counts. Counts are per test,
not per assertion: passed means Playwright's expected outcome (including an
expected failure), executed requires a non-skipped result, and flaky is separate.
Counts are cross-checked against reporter stats; incomplete/inconsistent reports
produce null counts rather than fabricated zeroes. The entire log line is limited
to 4096 bytes. Generation/output failure emits only fixed `DIAGNOSTIC_GAP` and
does not change the browser exit code. Existing first-failure artifact scanning,
cleanup, immutable validation and final evidence scanning remain mandatory and
outside this best-effort log boundary. A zero browser code with an invalid report
continues to fail closed. No raw browser output is forwarded to CI logs.

On a browser-command failure the Harness writes exactly one
`browser-first-failure.json` record before it stops its owned backend and removes
raw Playwright output. A successful command writes no first-failure record.

Schema version 1 remains recognized only with its original exact 20-field set.
Schema version 2 contains exactly 22 closed fields: `schemaVersion`, `journeyId`,
`runnerPhase`, `harnessPhase`, `firstFailureAssertionId`,
`firstFailureOperationId`,
`expectedResultClass`, `observedResultClass`, `failureCategory`,
`failureSubtype`, `exceptionClass`, `httpStatusCategory`,
`httpStatusSourceClass`, `correlationDigest`,
the three bounded completion counts, the backend/frontend/listener state
classes, `restartCountClass`, and `completionState`.

Assertion identities are opaque identifiers from the versioned Harness mapping;
test titles and Playwright error text are used only transiently and are never
written or hashed. Failure categories are `BROWSER_ASSERTION`,
`BROWSER_TIMEOUT`, `BROWSER_HTTP_ERROR`, `BROWSER_NAVIGATION_ERROR`,
`BROWSER_PROCESS_ERROR`, and `BROWSER_DIAGNOSTIC_GAP`. Unsafe, absent, or
unmapped identities fail closed to `NOT_RETAINED` and
`BROWSER_DIAGNOSTIC_GAP`. Knowledge lifecycle operations use only
`KNOWLEDGE_GOVERNED_CREATE_PUBLISH`, `KNOWLEDGE_INDEX_RETRIEVE`,
`KNOWLEDGE_UPDATE`, `KNOWLEDGE_RESTART_READBACK`, and
`KNOWLEDGE_PURGE_RECOVERY`. Their order in the structured result is authoritative;
only the first unexpected operation is retained. Missing or unmapped operation
identity becomes `NOT_RETAINED` and `BROWSER_DIAGNOSTIC_GAP`.

For the frozen v0.2.2 successor, the actual product reporter writes one closed
array of `operationId`, `resultState`, and optional integer
`structuredHttpStatus` values. The Harness reads that file only transiently,
validates the exact field set and five-value operation vocabulary, sorts by the
versioned lifecycle order, and selects the first `UNEXPECTED` operation. The
file is removed with browser output before final disclosure scanning. Reporter
messages, URLs, selectors, payloads, exit codes, assertion counts, and raw
artifacts are neither parser inputs nor retained Evidence.

HTTP categories `HTTP_1XX` through `HTTP_5XX` are reduced only from an explicitly
typed integer `structuredHttpStatus` in the range 100–599 supplied by the selected
structured Browser result or operation. The exact number is never retained.
`httpStatusSourceClass` is limited to `STRUCTURED_RESPONSE_STATUS`,
`NO_STRUCTURED_HTTP_STATUS`, and `NOT_RETAINED`. Without structured status the
HTTP category is `NONE` or `UNKNOWN`; messages, exit codes, and assertion counts
are never inspected for HTTP classification. The closed validator rejects extra fields,
unversioned identifiers, invalid enums, unbounded counts, paths, URLs,
credential-shaped values, raw-artifact references, unsupported or mixed schema
versions, invalid structured status types/ranges, and contradictory HTTP
source/category pairs.
