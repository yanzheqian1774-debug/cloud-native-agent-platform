# Architecture Decision and Contract Status

## Purpose

This document defines how humans and Coding Agents interpret
architecture decisions and Contracts.

Architecture approval and implementation progress are separate
dimensions.

## ADR Status Model

Each ADR should be understood using two independent fields.

### Decision Status

Allowed values:

- Proposed
- Accepted
- Superseded
- Rejected

Meaning:

Proposed:
The architecture decision is under discussion and is not authoritative.

Accepted:
The architecture decision is approved and is architecture authority.

Superseded:
A newer ADR replaces this decision.

Rejected:
The proposal was considered and rejected.

### Implementation Status

Allowed values:

- Not Started
- Partial
- Implemented

Meaning:

Not Started:
The decision is approved but corresponding implementation has not
started.

Partial:
Some parts are implemented, but the complete decision is not reflected
in current source.

Implemented:
Current source is intended to conform to the accepted decision.

## Important Rule

Accepted does NOT mean Implemented.

Source and tests remain the authority for current runtime behavior.

Accepted ADRs remain the authority for approved architecture.

If source and an Accepted ADR disagree in an area relevant to the
assigned task:

STOP and report architecture/implementation drift.

Do not silently modify either side.

## Legacy ADRs

Older ADRs may not yet contain Implementation Status.

For those ADRs:

- do not assume Accepted means Implemented;
- inspect source and tests;
- inspect newer ADRs;
- report material ambiguity before architecture-sensitive changes.

The ADR index should progressively record implementation status for
legacy decisions.

## Contract Status Model

A Contract is considered frozen only when repository documentation
explicitly identifies:

- Contract name;
- Contract version;
- Status: Frozen;
- approving architecture decision or review;
- compatibility expectations.

A roadmap reference to a future Contract does NOT make that Contract
frozen.

An interface found only in implementation code is not automatically a
frozen public Contract.

## Frozen Contract Rule

Changing a frozen Contract requires explicit architecture approval.

If no authoritative Contract status can be found, do not invent one.

For architecture-sensitive work, report the ambiguity.

## Future Contract Registry

When formal platform Contracts are introduced, maintain an explicit
Contract index containing at least:

- name;
- version;
- status;
- owner;
- compatibility policy;
- governing ADR;
- implementation locations.

Until that registry exists, this document defines the interpretation
rules.
