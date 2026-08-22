# S5-SPIKE-003 Checkpoint A Plan

SESSION
ID: S5-SPIKE-003
TITLE: Capability Contract
PHASE: S5 / v0.2 CONNECT & MANAGE
TRACK: Capability
MODE: Spike / Experimental
STATUS: ACTIVE
CHECKPOINT: A

## Gate and boundary

G1 applies because the spike introduces experimental provider behavior. All
artifacts stay below `experiments/s5-spike-003-capability-contract/`. Production
source, CRDs, public APIs, frozen Contracts, and lifecycle semantics remain
unchanged.

## Components and interfaces

- immutable capability identity and input/output schema references;
- Agent Definition-like binding from capability identity to provider reference;
- separate discoverability and authorization inputs;
- provider-neutral request, invocation handle, and normalized result;
- REST provider translating to a public read-only HTTP API;
- MCP provider translating through an actual stdio JSON-RPC MCP exchange;
- generic caller containing no provider-kind branch.

Risk classification is tested as governance metadata referenced from a
capability, not part of stable identity. Permission is a binding/policy decision,
not a discoverability or provider property.

## Tests and evidence

- contract/identity and schema-reference tests;
- identical caller path for REST and MCP;
- provider leakage assertion;
- ALLOW and DENY tests proving denial occurs before provider invocation;
- live public REST read and local real MCP protocol run;
- Ruff, formatting, repository regression, diff, and secret checks.

## Compatibility and risks

There is no production compatibility impact. The public REST endpoint is a live
evidence dependency only; deterministic tests use an injected transport. The
MCP evidence server is local and deterministic. Findings are candidates pending
human review and must not be treated as a frozen Contract.
