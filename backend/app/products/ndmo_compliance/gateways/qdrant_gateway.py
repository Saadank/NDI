"""Qdrant wrapper with lazy per-tenant collection provisioning.

Per the Phase-1/Phase-2 decisions:
  * Two collections per tenant: ``{tenant_id}-chunks`` (search corpus) and
    ``{tenant_id}-files`` (file-level dedupe / similarity).
  * Collections are created on first ingestion for that tenant (lazy).
  * Hybrid vectors: BGE-M3 dense (1024-d cosine) + Qdrant native sparse
    BM25 — same as the cortex retrieval pattern.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels

logger = logging.getLogger(__name__)

# BGE-M3 dimensions — fixed by the model.  Stored as a constant so the
# embedding gateway and Qdrant gateway agree even if instantiated separately.
BGE_M3_DENSE_DIM: int = 1024

# Vector-store names inside one collection (Qdrant supports named vectors).
DENSE_VECTOR_NAME: str = "dense"
SPARSE_VECTOR_NAME: str = "bm25"


@dataclass(slots=True)
class ChunkPoint:
    """One row destined for the chunks collection."""

    id: str                          # uuid str
    text: str
    page_number: int
    source_file: str
    document_id: str                 # uuid str of the parent document
    dense: list[float]
    sparse_indices: list[int]
    sparse_values: list[float]
    extra: dict[str, Any] | None = None


@dataclass(slots=True)
class FilePoint:
    """One row destined for the files collection (one per document)."""

    id: str                          # uuid str
    text: str                        # concatenated document text
    document_id: str
    dense: list[float]
    sparse_indices: list[int]
    sparse_values: list[float]
    extra: dict[str, Any] | None = None


class QdrantGateway:
    """Async Qdrant client wrapper with lazy collection bootstrap."""

    def __init__(self, url: str | None = None) -> None:
        url = url or os.environ.get("QDRANT_URL") or "http://qdrant:6333"
        api_key = os.environ.get("QDRANT_API_KEY") or None
        self._client = AsyncQdrantClient(url=url, api_key=api_key)
        self._bootstrapped: set[str] = set()

    # ---- naming ----------------------------------------------------------

    @staticmethod
    def chunks_collection(tenant_id: int) -> str:
        return f"{tenant_id}-chunks"

    @staticmethod
    def files_collection(tenant_id: int) -> str:
        return f"{tenant_id}-files"

    # ---- bootstrap -------------------------------------------------------

    async def ensure_tenant_collections(self, tenant_id: int) -> None:
        """Lazy-create the two collections for a tenant.  Idempotent."""
        if tenant_id in self._bootstrapped:
            return
        for name in (self.chunks_collection(tenant_id), self.files_collection(tenant_id)):
            await self._ensure_collection(name)
        self._bootstrapped.add(tenant_id)

    async def _ensure_collection(self, name: str) -> None:
        if await self._client.collection_exists(name):
            return
        await self._client.create_collection(
            collection_name=name,
            vectors_config={
                DENSE_VECTOR_NAME: qmodels.VectorParams(
                    size=BGE_M3_DENSE_DIM,
                    distance=qmodels.Distance.COSINE,
                ),
            },
            sparse_vectors_config={
                SPARSE_VECTOR_NAME: qmodels.SparseVectorParams(
                    index=qmodels.SparseIndexParams(on_disk=False),
                ),
            },
        )
        logger.info("Created Qdrant collection: %s", name)

    # ---- writes ----------------------------------------------------------

    async def upsert_chunks(self, tenant_id: int, points: list[ChunkPoint]) -> None:
        if not points:
            return
        await self.ensure_tenant_collections(tenant_id)
        qpoints = [
            qmodels.PointStruct(
                id=p.id,
                vector={
                    DENSE_VECTOR_NAME: p.dense,
                    SPARSE_VECTOR_NAME: qmodels.SparseVector(
                        indices=p.sparse_indices,
                        values=p.sparse_values,
                    ),
                },
                payload={
                    "text": p.text,
                    "page_number": p.page_number,
                    "source_file": p.source_file,
                    "document_id": p.document_id,
                    **(p.extra or {}),
                },
            )
            for p in points
        ]
        await self._client.upsert(
            collection_name=self.chunks_collection(tenant_id),
            points=qpoints,
        )
        logger.info("Upserted %d chunk points into %s", len(qpoints),
                    self.chunks_collection(tenant_id))

    async def upsert_files(self, tenant_id: int, points: list[FilePoint]) -> None:
        if not points:
            return
        await self.ensure_tenant_collections(tenant_id)
        qpoints = [
            qmodels.PointStruct(
                id=p.id,
                vector={
                    DENSE_VECTOR_NAME: p.dense,
                    SPARSE_VECTOR_NAME: qmodels.SparseVector(
                        indices=p.sparse_indices,
                        values=p.sparse_values,
                    ),
                },
                payload={
                    "text": p.text[:8000],          # cap payload size
                    "document_id": p.document_id,
                    **(p.extra or {}),
                },
            )
            for p in points
        ]
        await self._client.upsert(
            collection_name=self.files_collection(tenant_id),
            points=qpoints,
        )

    # ---- reads (used by Phase 3 assessment engine) -----------------------

    async def hybrid_search_chunks(
        self,
        *,
        tenant_id: int,
        query_dense: list[float],
        query_sparse_indices: list[int],
        query_sparse_values: list[float],
        k: int = 5,
        filter_document_ids: list[str] | None = None,
    ) -> list[dict]:
        """RRF-fused hybrid search.  Returns ``[{id, score, payload}, ...]``."""
        await self.ensure_tenant_collections(tenant_id)
        flt = None
        if filter_document_ids:
            flt = qmodels.Filter(must=[
                qmodels.FieldCondition(
                    key="document_id",
                    match=qmodels.MatchAny(any=filter_document_ids),
                )
            ])
        res = await self._client.query_points(
            collection_name=self.chunks_collection(tenant_id),
            prefetch=[
                qmodels.Prefetch(query=query_dense, using=DENSE_VECTOR_NAME, limit=k * 4),
                qmodels.Prefetch(
                    query=qmodels.SparseVector(
                        indices=query_sparse_indices, values=query_sparse_values
                    ),
                    using=SPARSE_VECTOR_NAME, limit=k * 4,
                ),
            ],
            query=qmodels.FusionQuery(fusion=qmodels.Fusion.RRF),
            limit=k,
            query_filter=flt,
            with_payload=True,
        )
        return [
            {"id": str(pt.id), "score": pt.score, "payload": dict(pt.payload or {})}
            for pt in res.points
        ]
