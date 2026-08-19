# Contributing

Thank you for contributing to the Enterprise Agent Platform. The project is
under active development toward `v0.1.0-alpha`; no release is currently
supported, and planned capabilities are not necessarily implemented.

## Choose the right path

- **Bug:** open a public issue using the bug-report template.
- **Feature request:** open a public issue using the feature-request template.
  A request does not imply roadmap acceptance or delivery.
- **Question:** open a public issue and clearly describe what you are trying to
  understand or accomplish.
- **Suspected security vulnerability:** do not open a public issue or pull
  request. Follow [SECURITY.md](SECURITY.md) and use GitHub Private
  Vulnerability Reporting.

Before proposing a change, review [README.md](README.md) and
[CURRENT_IMPLEMENTATION.md](docs/engineering/CURRENT_IMPLEMENTATION.md) to
distinguish current behavior from roadmap or conceptual direction. Source code
and tests remain the authority for implemented behavior.

## Set up the repository

Prerequisites:

- Python 3.12;
- `uv`; and
- Git.

Create a branch from `main`, then install the development dependencies and Git
hooks:

```bash
make setup
```

Use a short branch name that reflects the change, for example:

```text
fix/operator-reconcile
feat/workflow-diagnostics
docs/quick-start
chore/project-maintenance
```

## Make a focused change

- Keep the change within the issue or pull-request scope.
- Add or update tests when behavior changes.
- Update documentation when public behavior or usage changes.
- Do not present planned or conceptual capabilities as implemented.
- Do not change public CRDs, the Kubernetes API group, frozen contracts, or
  architecture-sensitive lifecycle semantics without explicit approval.
- Do not include secrets or sensitive report data.

Run the repository validation before opening a pull request:

```bash
make check
```

`make check` does not run the frontend validation. For frontend changes, also
run the supported scripts from `console/frontend`:

```bash
npm run lint
npm run build
```

## Commit and open a pull request

Use Conventional Commit messages consistent with the repository history, such
as:

```text
fix(operator): handle reconciliation failure
docs: clarify local setup
```

In the pull request, include:

- a concise summary and scope;
- related issue context, when available;
- validation performed and its results;
- architecture or API impact, including `None` when there is none; and
- known limitations or follow-up work.

Before submitting, inspect the diff and confirm that it contains no unrelated
or generated temporary files. Human review and the repository's required CI
checks must complete before merge.
