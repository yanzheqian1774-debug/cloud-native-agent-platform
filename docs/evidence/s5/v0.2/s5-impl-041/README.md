# S5-IMPL-041 Checkpoint A Evidence

Status: `ACTIVE / FINAL_CHECKPOINT_A_CORRECTIONS_COMPLETE / AWAITING_HUMAN_REVIEW`

This directory records the local controlled-Model, Qdrant, automated, and
Browser evidence for v0.2.1. It makes no production, persistence, execution,
Agent Instance, Runtime Instance, v0.2.2, or v0.2.3 claim.

## Local Qdrant

- Image: `qdrant/qdrant:v1.15.4`
- Resolved digest: `sha256:6ac4807063bbecddca0250bfbcff52acf18c22263b904d12919349e6d0a408f1`
- Container: `s5-impl-041-qdrant`
- Network: `s5-impl-041-qdrant`
- Replaceable volume: `s5-impl-041-qdrant-data`
- Exposure: `127.0.0.1:6333:6333` only

Reproducible lifecycle:

```sh
docker network create --driver bridge s5-impl-041-qdrant
docker volume create s5-impl-041-qdrant-data
docker run -d --name s5-impl-041-qdrant --network s5-impl-041-qdrant --mount source=s5-impl-041-qdrant-data,target=/qdrant/storage -p 127.0.0.1:6333:6333 qdrant/qdrant:v1.15.4
curl -fsS http://127.0.0.1:6333/healthz
docker restart s5-impl-041-qdrant
docker stop s5-impl-041-qdrant
docker start s5-impl-041-qdrant
docker rm -f s5-impl-041-qdrant
docker volume rm s5-impl-041-qdrant-data
docker network rm s5-impl-041-qdrant
```

Reset/rebuild uses `DELETE /collections/s5_impl_041_supplier_quality`, followed
by collection creation and exact manifest reindexing. Qdrant contains only a
replaceable derived vector index.

## Controlled providers

- Planning: `ollama-local / qwen3:8B`; actual JSON-schema call passed.
- Embedding: `ollama-local / shaw/dmeta-embedding-zh:latest`; actual Chinese and
  English batch produced two 768-dimensional vectors.
- The planning model proposed execution-oriented content during entry testing.
  The implementation therefore records it as untrusted and applies mandatory
  deterministic rule validation before any reviewable plan exists.

No credentials were used or recorded.

## Final production Browser review

- Frontend: production Vite bundle, live supplier-quality mode,
  `http://127.0.0.1:4181` (localhost only).
- Backend: `http://127.0.0.1:8011` (localhost only).
- Desktop and mobile relationship layouts both reported
  `clientWidth == scrollWidth` at 1280×720 and 390×844.
- Chinese-first and English UI modes were exercised. English product labels and
  known canonical task labels are translated; raw stable IDs remain collapsed
  or visibly technical.
- Final browser diagnostics contained no console errors.
- Qdrant remains behind the existing `VectorIndexPort`; no frontend or route
  treats it as lifecycle, authorization, approval, or Evidence authority.
