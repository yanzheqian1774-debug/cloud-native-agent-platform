# S5-SPIKE-004 — Agent Instance & Routing — Checkpoint A

Experimental object-model evidence only. Nothing in this directory is a
production API, CRD, frozen Contract, or production scheduler.

Run the targeted Checkpoint A and B experiments:

```bash
uv run pytest experiments/s5-spike-004-agent-instance-routing/tests
```

The model deliberately separates platform-owned Definition and Instance
identity, Provider-owned binding-to-realization mapping, and runtime-owned
native realization identity. The Checkpoint B router is a deterministic,
in-memory evidence harness, not a production scheduler. Checkpoint C recovery
is not implemented.
