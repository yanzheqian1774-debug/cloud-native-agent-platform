# Architecture Gates

## Purpose

Coding Agents may autonomously implement bounded engineering tasks.

They may not autonomously redefine product or architecture.

## G0 — Autonomous

Normally safe for autonomous implementation:

- bounded bug fixes;
- unit tests;
- documentation;
- examples;
- internal refactoring without behavior change;
- CI fixes;
- formatting;
- implementation behind an already approved interface.

Normal task Acceptance Criteria still apply.

## G1 — Plan Required

Create and review an implementation plan before coding when introducing:

- a new endpoint;
- new controller behavior;
- a new adapter;
- a new provider;
- a new Console capability;
- a new external dependency;
- meaningful cross-module behavior.

A G1 plan should identify:

- affected components;
- interfaces;
- test strategy;
- compatibility;
- risks.

## G2 — Architecture Decision Required

STOP implementation and request an architecture decision for:

- public CRD schema changes;
- Kubernetes API group changes;
- breaking public API changes;
- frozen Contract changes;
- Agent lifecycle semantic changes;
- Task lifecycle semantic changes;
- Workflow lifecycle semantic changes;
- Runtime lifecycle semantic changes;
- Agent Instance architecture;
- State architecture;
- Tenant architecture;
- authentication architecture;
- new persistent infrastructure;
- new database;
- Control Plane boundary changes;
- cross-plane ownership changes.

## Escalation Report

When a G2 condition is encountered, report:

1. requested change;
2. why current architecture blocks the task;
3. affected components;
4. compatibility impact;
5. alternatives;
6. recommendation.

Do not implement the architecture change until approved.
