# Definition of Done

A Coding Agent reporting "done" does not by itself mean a task is
complete.

A task is complete only when its applicable acceptance gates pass.

## Code

- implementation is complete for the approved scope;
- no unrelated feature expansion;
- no dead temporary implementation remains.

## Tests

As applicable:

- unit tests pass;
- integration tests pass;
- regression tests pass;
- contract tests pass;
- required Golden E2E passes.

## Quality

Run applicable repository checks.

Baseline:

    make check

For targeted debugging, individual non-mutating checks may also be
run directly, for example:

    uv run ruff check .
    uv run ruff format --check .
    uv run pytest

`pre-commit run --all-files` is not treated as a read-only validation
gate because configured hooks may modify files. If it is run, inspect
the resulting diff and rerun the non-mutating validation afterward.

Frontend changes additionally require repository-defined lint and build
checks.

## Architecture

- no unauthorized architecture changes;
- no unauthorized CRD changes;
- no unauthorized Contract changes;
- no accidental roadmap implementation;
- architecture stop conditions were respected.

## Security

- no secrets committed;
- no unnecessary privileges introduced;
- new dependencies are justified;
- security-sensitive behavior is documented.

## Documentation

Where public behavior changes:

- documentation is updated;
- examples are updated;
- compatibility or migration impact is documented.

## Git

- diff is focused;
- no unrelated files changed;
- git status is understood;
- generated temporary files are not committed accidentally.

## Final Report

The implementation report includes:

- summary;
- changed files;
- validation executed;
- validation results;
- architecture impact;
- limitations;
- follow-up items.

## Human Gate

Human approval remains required for:

- architecture decisions;
- Contract freeze;
- breaking changes;
- merge;
- release.
