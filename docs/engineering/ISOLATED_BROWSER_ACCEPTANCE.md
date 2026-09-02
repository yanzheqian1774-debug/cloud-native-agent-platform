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

On a browser-command failure the Harness writes exactly one
`browser-first-failure.json` record before it stops its owned backend and removes
raw Playwright output. A successful command writes no first-failure record.

Schema version 1 contains only the 20 closed fields `schemaVersion`, `journeyId`,
`runnerPhase`, `harnessPhase`, `firstFailureAssertionId`,
`expectedResultClass`, `observedResultClass`, `failureCategory`,
`failureSubtype`, `exceptionClass`, `httpStatusCategory`, `correlationDigest`,
the three bounded completion counts, the backend/frontend/listener state
classes, `restartCountClass`, and `completionState`.

Assertion identities are opaque identifiers from the versioned Harness mapping;
test titles and Playwright error text are used only transiently and are never
written or hashed. Failure categories are `BROWSER_ASSERTION`,
`BROWSER_TIMEOUT`, `BROWSER_HTTP_ERROR`, `BROWSER_NAVIGATION_ERROR`,
`BROWSER_PROCESS_ERROR`, and `BROWSER_DIAGNOSTIC_GAP`. Unsafe, absent, or
unmapped identities fail closed to `NOT_RETAINED` and
`BROWSER_DIAGNOSTIC_GAP`. HTTP results retain only an HTTP class, connection,
timeout, none, or unknown category. The closed validator rejects extra fields,
unversioned identifiers, invalid enums, unbounded counts, paths, URLs,
credential-shaped values, and raw-artifact references.
