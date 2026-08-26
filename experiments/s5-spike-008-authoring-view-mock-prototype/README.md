# S5-SPIKE-008 authoring and dual-view mock

This directory is a disposable, deterministic and non-authoritative UX
prototype. It is not the production Console, a public DTO, persistence, a
Runtime integration, or a Knowledge contract.

The initial dual-language preview supports `zh-CN` and `en-US`. It uses
message-key catalogs with selected-locale → `en-US` → Message Key fallback.
The prototype selects `zh-CN` for the demo without changing the production
default-locale contract. Locale changes affect display projections only; stable
identities, enums, reason codes, evidence and call counts are unchanged.

Serve the repository root and open the mock:

```bash
python -m http.server 8000
```

Then visit
`http://localhost:8000/experiments/s5-spike-008-authoring-view-mock-prototype/web/`.

Run the isolated tests with:

```bash
uv run pytest experiments/s5-spike-008-authoring-view-mock-prototype/tests
```

The same tests are exposed to unchanged repository pytest discovery through
the Human-authorized prototype-only shim at
`tests/test_s5_spike_008_prototype.py`. The shim delegates normal collection;
it contains no duplicate assertions and runs no nested pytest process.

The UI deliberately presents one synthetic execution through two linked
projections. Product View uses business language. Technical View exposes the
same Platform Execution Identity, distinct logical identities, Runtime support
state, capability evidence, provider correlation and Knowledge evidence.
