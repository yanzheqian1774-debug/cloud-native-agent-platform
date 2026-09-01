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

## Minimum-disclosure extraction

Acceptance Evidence is produced only through `minimum_disclosure.py`. Its
allowlist is limited to sanitized state, PID/start correlation, restart and
release-entry counts, manifest digests, schema version and completion timestamp.
Requests for any other field fail closed. URLs, environment values, source or
prompt text, vectors, Qdrant payloads, credentials and credential-shaped test or
placeholder values are not Evidence fields and are redacted by exclusion.

Backend and browser output are captured outside the release. Successful and
failed Playwright artifacts, including compressed traces, are scanned before
acceptance. A prohibited value fails the run without echoing that value. The
immutable frontend server suppresses request-path logging. Validation helpers
must use structured parsing or exact-field extraction; broad `sed`, `cat`,
`head`, or `tail` file dumps are prohibited for potentially sensitive files.
