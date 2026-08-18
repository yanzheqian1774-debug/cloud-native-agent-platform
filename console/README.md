# Workflow Execution Console

The Workflow Execution Console provides a read-only view of AgentOS workflow
execution.

## Responsibilities

The Console will provide:

- Workflow Runs
- Workflow Detail
- DAG visualization
- Node Inspector
- execution input and result inspection
- execution timing and attempts
- failure reason and message inspection
- en-US and zh-CN user-interface localization

## Architecture

Browser
  |
  v
Console Frontend
  |
  v
Console Backend
  |
  v
Kubernetes API
  |
  +-- Workflow
  +-- Task
  +-- Agent

Kubernetes resources are the source of truth.

The Console Backend is a stateless, read-only projection layer.

## Source Layout

The implementation will use:

console/
├── backend/
│   ├── src/
│   └── tests/
└── frontend/

Backend and frontend are separate source-code responsibilities but do not need
to be independently deployed services in the initial release.

## Internationalization

The initial frontend supports:

- English (`en-US`)
- Simplified Chinese (`zh-CN`)

Machine-readable API values remain language-neutral.

Agent prompts, task inputs, model responses, and execution results are shown in
their original form and are not automatically translated.

## Initial Scope

The initial Console is read-only.

It does not provide:

- Workflow editing
- Agent editing
- authentication or RBAC
- multi-tenancy
- token or cost dashboards
- distributed tracing
- provider management
- secret management
