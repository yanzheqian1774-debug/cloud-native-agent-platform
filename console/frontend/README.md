# Workflow Execution Console frontend

This React, TypeScript, and Vite application is the browser frontend for the
current read-only Workflow Execution Console. Kubernetes remains the source of
truth through the Console backend; the frontend does not edit Agent, Task, or
Workflow resources.

## Prerequisites

Use Node 24, matching repository CI, or a compatible 20.19+/22.13+ release,
plus npm. Install the locked dependencies from this directory:

```bash
npm ci
```

## Development

Start the Console backend as described in the
[local installation guide](../../manifests/README.md#inspect-through-the-console),
then run:

```bash
npm run dev
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` and `/healthz` to the backend
at `http://127.0.0.1:8000`.

## Validation

```bash
npm run lint
npm run build
```

These frontend commands are separate from the root `make check` validation.
