# S5-SPIKE-008 authoring and dual-view mock

This directory is a disposable, deterministic and non-authoritative UX
prototype. It is not the production Console, a public DTO, persistence, a
Runtime integration, or a Knowledge contract.

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

The UI deliberately presents one synthetic execution through two linked
projections. Product View uses business language. Technical View exposes the
same Platform Execution Identity, distinct logical identities, Runtime support
state, capability evidence, provider correlation and Knowledge evidence.
