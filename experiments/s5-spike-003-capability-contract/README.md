# S5-SPIKE-003 Capability Contract

Experimental Checkpoint A artifacts for falsifying a minimum Capability
Contract. Nothing in this directory is a production API, frozen Contract, MCP
integration, registry, or policy engine.

Run the deterministic tests:

```bash
uv run pytest experiments/s5-spike-003-capability-contract/tests
```

Run the live REST and local MCP evidence path:

```bash
uv run python experiments/s5-spike-003-capability-contract/run_checkpoint_a.py
```

The generic caller knows capability identity, binding, authorization, request,
and normalized result semantics. REST and MCP translation remain behind their
provider boundaries.
