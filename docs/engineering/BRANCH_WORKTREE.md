# Branch and Worktree Conventions

## Principle

The unit of isolation is the engineering Task.

Preferred model:

Task
→ Branch
→ Worktree
→ Pull Request
→ CI
→ Review
→ Merge.

## Branch Naming

Recommended patterns:

    codex/<task-id>-<short-name>

or, when a conventional repository category is clearer:

    feat/<short-name>
    fix/<short-name>
    docs/<short-name>
    chore/<short-name>

Use the repository's established convention when one already applies.

## Worktrees

Parallel Coding Agent tasks should use isolated Git worktrees.

Example:

    ../worktrees/s5-runtime-contract
    ../worktrees/s5-hermes-adapter
    ../worktrees/s5-runtime-console

Avoid multiple agents modifying the same working tree concurrently.

## Scope

One worktree should normally correspond to one task.

Do not use a long-lived worktree as the permanent identity of one
Coding Agent.

## Before Work

Confirm:

    git status
    git branch --show-current

Ensure the task begins from the intended base commit.

## Before Review

Inspect:

    git status
    git diff
    git diff --stat

Run required validation.

## Merge

Do not merge merely because generated code appears plausible.

Merge requires:

- Acceptance Criteria pass;
- required CI pass;
- architecture gates satisfied;
- focused diff;
- human approval.

## Cleanup

After merge and verification:

- remove obsolete worktree;
- delete merged local branch when appropriate;
- delete merged remote branch when appropriate;
- verify main is synchronized and clean.
