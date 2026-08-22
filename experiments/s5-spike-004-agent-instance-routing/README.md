# S5-SPIKE-004 — Agent Instance & Routing — Checkpoint A

Experimental object-model evidence only. Nothing in this directory is a
production API, CRD, frozen Contract, or production scheduler.

Run the targeted Checkpoint A, B, and C experiments:

```bash
uv run pytest experiments/s5-spike-004-agent-instance-routing/tests
```

The model deliberately separates platform-owned Definition and Instance
identity, Provider-owned binding-to-realization mapping, and runtime-owned
native realization identity. The Checkpoint B router and Checkpoint C recovery
coordinator are deterministic, in-memory evidence harnesses, not production
scheduling or reconciliation controllers.

The Human Final Spike Gate and Human Close Confirmation passed after Checkpoint
C. See `S5-SPIKE-004-CLOSEOUT.md` for the accepted convergence inputs, evidence
debt, and final `CLOSED` state. Reopening this session is prohibited.
