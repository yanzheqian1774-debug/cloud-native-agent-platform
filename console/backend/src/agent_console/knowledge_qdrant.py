"""Qdrant v1.15 REST adapter for derived Knowledge vectors only."""

from __future__ import annotations

from typing import Any

import httpx


class QdrantKnowledgeError(RuntimeError):
    pass


class QdrantKnowledgeIndex:
    def __init__(
        self,
        base_url: str,
        *,
        client: httpx.Client | None = None,
        collection: str = "knowledge_v1",
    ) -> None:
        if not base_url:
            raise QdrantKnowledgeError("QDRANT_UNAVAILABLE")
        self.base_url = base_url.rstrip("/")
        self.collection = collection
        self.client = client or httpx.Client(timeout=5.0)

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self.client.request(method, f"{self.base_url}{path}", **kwargs)
            response.raise_for_status()
            body = response.json()
            if body.get("status") not in {"ok", "acknowledged"}:
                raise QdrantKnowledgeError("QDRANT_UNAVAILABLE")
            return body
        except (httpx.HTTPError, ValueError) as exc:
            raise QdrantKnowledgeError("QDRANT_UNAVAILABLE") from exc

    def ensure_collection(self, dimensions: int = 8) -> None:
        response = self.client.get(f"{self.base_url}/collections/{self.collection}")
        if response.status_code == 404:
            self._request(
                "PUT",
                f"/collections/{self.collection}",
                json={"vectors": {"size": dimensions, "distance": "Cosine"}},
            )
        elif response.is_error:
            raise QdrantKnowledgeError("QDRANT_UNAVAILABLE")

    def upsert(self, points: list[dict[str, Any]]) -> None:
        self._request(
            "PUT",
            f"/collections/{self.collection}/points",
            params={"wait": "true"},
            json={"points": points},
        )

    def delete_snapshot(
        self, namespace: str, security_domain: str, knowledge_id: str, snapshot_id: str
    ) -> None:
        must = [
            {"key": key, "match": {"value": value}}
            for key, value in (
                ("namespace", namespace),
                ("securityDomain", security_domain),
                ("knowledgeId", knowledge_id),
                ("snapshotId", snapshot_id),
            )
        ]
        self._request(
            "POST",
            f"/collections/{self.collection}/points/delete",
            params={"wait": "true"},
            json={"filter": {"must": must}},
        )

    def search(
        self,
        vector: list[float],
        *,
        namespace: str,
        security_domain: str,
        knowledge_id: str,
        snapshot_id: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        must = [
            {"key": key, "match": {"value": value}}
            for key, value in (
                ("namespace", namespace),
                ("securityDomain", security_domain),
                ("knowledgeId", knowledge_id),
                ("snapshotId", snapshot_id),
            )
        ]
        body = self._request(
            "POST",
            f"/collections/{self.collection}/points/query",
            json={
                "query": vector,
                "filter": {"must": must},
                "limit": min(max(limit, 1), 16),
                "with_payload": True,
            },
        )
        return list(body.get("result", {}).get("points", []))
