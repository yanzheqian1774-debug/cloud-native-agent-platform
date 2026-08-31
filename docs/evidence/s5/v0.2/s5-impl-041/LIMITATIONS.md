# Known Limitations

- Problem, plan, approval and stream authority is process-local and is lost on
  restart; the API reports `PREVIEW_STATE_UNAVAILABLE_AFTER_RESTART`.
- Qdrant is local derived-index storage only and is not authoritative.
- Only sanitized seeded Supplier Quality documents are supported; there is no
  upload endpoint.
- The Model is controlled locally but not certified. Deterministic validation
  remains mandatory.
- Sparse retrieval is a bounded lexical scorer, not a production BM25 service.
- No resource publication, Task/Workflow execution, Agent Instance, Runtime
  Instance, general Tool call, public deployment, persistence, HA or SLA exists.
- Display codes and resource catalogs are stable only within the current
  process-local preview epoch and are presentation/search projections, never
  competing canonical authority.
- Human intervention can modify bounded business semantics and authorized
  selections only. It cannot edit canonical identity, authorization, provider,
  publication, runtime, or execution authority fields.
- The relationship view is a bounded projection of current canonical records;
  it is not a persistent enterprise graph database.
- Analysis streams and replay buffers are process-local and unavailable after
  restart. The API reports this explicitly and never fabricates restored events.
- User-facing streaming exposes structured summaries and artifacts only; hidden
  Model chain-of-thought, private reasoning tokens, prompts, and denied-resource
  information are never claimed or exposed.
