# Codex Engineering Workflow

## Objective

Use Coding Agents to increase implementation throughput without
delegating product and architecture ownership.

## Responsibility Model

Humans own:

- product direction;
- architecture;
- contract approval;
- scope;
- risk acceptance;
- merge decisions;
- release decisions.

Coding Agents may own bounded:

- planning;
- implementation;
- tests;
- debugging;
- refactoring;
- documentation;
- examples;
- CI fixes;
- integration work.

## Standard Flow

North Star
→ Product Architecture
→ Roadmap
→ Exec Plan
→ Task
→ Architecture Gate
→ Implementation
→ Validation
→ Review
→ Human Gate
→ Merge.

## Task Start

Before implementation:

1. read AGENTS.md;
2. read the task specification;
3. read relevant architecture documents;
4. inspect relevant source and tests;
5. determine the architecture gate;
6. create a plan when required.

## Contract-First Work

For extensible platform boundaries:

Research
→ Spike
→ Contract Proposal
→ Contract Tests
→ Human Approval
→ Contract Freeze
→ Parallel Implementations.

Do not implement multiple integrations against an unstable implicit
interface.

## Parallel Development

Parallelism should follow architectural boundaries.

Preferred tracks:

- CORE;
- ECO;
- PRODUCT;
- SOLUTION.

Each parallel task should use an isolated branch/worktree.

Avoid multiple agents editing the same high-conflict files unless the
tasks are explicitly coordinated.

## Solution-Driven Development

For roadmap features, start from a concrete end-to-end scenario.

Build only what is required by:

- the Contract;
- Acceptance Criteria;
- Release Gate;
- Golden Solution.

Avoid speculative platform breadth.

## Validation Loop

Implement
→ Test
→ Diagnose
→ Fix
→ Retest
→ Review Diff
→ Report.

Coding Agents should attempt to close ordinary implementation and test
failures autonomously.

Architecture conflicts must be escalated rather than silently solved
through scope expansion.

## Completion Report

Every completed task should report:

1. summary;
2. files changed;
3. architecture impact;
4. tests executed;
5. results;
6. known limitations;
7. follow-up work.
