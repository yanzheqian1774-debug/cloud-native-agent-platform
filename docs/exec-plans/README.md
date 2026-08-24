# Execution Plan Conventions

Use `active/` for current plans and move completed records to `completed/`.
These records coordinate work; they do not replace Tasks, architecture
decisions, the [Governance Registry](../governance/REGISTRY.md), or Git/PR
evidence.

## Active portfolio plans

- [S5-PLAN-001 — v0.2 Implementation Portfolio and Release Execution Plan](active/S5-PLAN-001-V0.2-IMPLEMENTATION-PORTFOLIO.md)
  is an authorized planning handoff in `CLOSING`, ready for its Human
  Implementation Entry Gate. Its Tracks and future Sessions remain
  planned/recommended only and do not authorize implementation.

Do not create speculative daily records. Create a record only for an actual
working day or authorized coordination window.

## Day Start Plan template

```markdown
# Day Start — <DAY-ID>

- Date:
- Current Version:
- Durable Main SHA:
- Release Objective:
- Active Sessions:
- Planned Checkpoints:
- Codex Conversation Assignment:
- Branch:
- Worktree:
- PR:
- Write Scope:
- Dependencies:
- Conflict Risk:
- Human Gates:
- Expected Outputs:
- Release Impact:
```

## Day Closeout template

```markdown
# Day Closeout — <DAY-ID>

- Date:
- Starting Baseline:
- Ending Durable Main:
- Sessions Started:
- Sessions Advanced:
- Sessions Closed:
- PRs Created:
- PRs Merged:
- Validation:
- Decisions Accepted:
- Evidence Debt Added or Changed:
- Blockers:
- v0.2 Progress Change:
- Next-Day Priorities:
```

Use `NONE` when a field has no event; do not omit it silently. Link Session,
decision, and debt changes to the Registry and link PR/commit evidence.

## Parallel work rules

- One writable Project Session maps to one Codex conversation.
- One writable Project Session maps to one branch.
- One writable Project Session maps to one isolated worktree.
- One writable Project Session maps to one primary PR.
- Every Session declares its base SHA, write scope, dependencies, conflict
  scope, Human Gates, and expected result.
- Shared-file conflicts require sequencing or explicit ownership before edits.
- A `CLOSED` Session is never reused; follow-up work receives a new Session ID.
- Integration work uses a separate REL Session and records merge order.
- Merge requires a Human Merge Gate.
- Session close requires a Human Close Confirmation.

The default mapping is:

```text
Project Session
  -> Codex conversation
  -> branch
  -> isolated worktree
  -> primary PR
  -> Human Merge Gate
  -> integration Session when required
  -> Human Close Confirmation
```

Read-only review Sessions may use a clean detached environment and no PR, but
must still record their baseline and provenance.
