"""Stage 4: chunk + embed + write to Qdrant.

PORTED FROM:
  cortex-backend-main/tasks/content_embedding_task.py

PORTING DIFF:
  cortex                                          -> NDMO
  ───────────────────────────────────────────     ──────────────────────────
  one Chunk per TextContent (no chunker)           our chunk_pages
                                                   (500-word / 50-overlap)
  ChunkRepository.create_many                      no SQL chunk table —
                                                   chunks live in Qdrant
                                                   only; payload carries
                                                   page_number + source_file
                                                   + document_id
  retrieval_engine.Qdrant + OpenAI dense           BGE-M3 dense + BM25 sparse
  + fastembed sparse                               via our QdrantGateway +
                                                   EmbeddingGateway
  collection names: f"{tenant_id}-chunks"          same scheme; lazy-provisioned
                    f"{tenant_id}-files"           by QdrantGateway on first write
  IDs (cortex: chunk_repository PK)                we mint UUIDv5 from
                                                   (document_id, chunk_index)
                                                   so re-runs are idempotent
"""

from __future__ import annotations

import logging
from uuid import NAMESPACE_DNS, uuid5

from restate import WorkflowSharedContext

from app.products.ndmo_compliance.dependencies import current_tenant_id
from app.products.ndmo_compliance.enums.document_status import DocumentStatus
from app.products.ndmo_compliance.extraction import chunk_pages
from app.products.ndmo_compliance.extraction.models import PageText
from app.products.ndmo_compliance.gateways.embedding_gateway import EmbeddingGateway
from app.products.ndmo_compliance.gateways.qdrant_gateway import (
    ChunkPoint,
    FilePoint,
    QdrantGateway,
)
from app.products.ndmo_compliance.repositories.document_repository import DocumentRepository
from app.products.ndmo_compliance.workflows.restate_workflows import (
    ndmo_document_ingestion_workflow,
)

logger = logging.getLogger(__name__)


@ndmo_document_ingestion_workflow.handler("Embed")
async def embed_content_task(ctx: WorkflowSharedContext, data: dict) -> dict:
    """Chunk the extracted pages, embed, and write to Qdrant.

    Args:
      data["pages"]: list[dict] — output of the Extract stage
      data["document_id"], data["tenant_id"]
    """
    pages_dict: list[dict] = data["pages"]
    document_id: str = str(data["document_id"])
    tenant_id: int = data["tenant_id"]
    current_tenant_id.set(tenant_id)

    documents = DocumentRepository()
    await ctx.run_typed(
        "mark embedding",
        documents.update_status,
        document_id=document_id, tenant_id=tenant_id, status=DocumentStatus.EMBEDDING,
    )

    # Re-hydrate PageText.
    pages: list[PageText] = [
        PageText(
            text=p["text"],
            page_number=p["page_number"],
            source_file=p["source_file"],
            metadata=p.get("metadata") or {},
        )
        for p in pages_dict
    ]

    # Chunk via our pure-Python chunker (500 words / 50 overlap, page-aware).
    chunks = chunk_pages(pages)
    if not chunks:
        logger.warning("Document %s produced zero chunks — empty after extraction.", document_id)
        await ctx.run_typed(
            "mark ready (empty)",
            documents.mark_processed,
            document_id=document_id, tenant_id=tenant_id,
        )
        return {"chunks": 0, "document_id": document_id}

    # Embed in batch (BGE-M3 dense + BM25 sparse).
    embedder = EmbeddingGateway()
    chunk_texts = [c.text for c in chunks]

    def _embed_chunks() -> list:
        return embedder.embed_batch(chunk_texts)

    embeddings = await ctx.run_typed("embed chunks", _embed_chunks)

    # File-level embedding (one per document — concatenated, capped to ~8 KB).
    file_text = "\n\n".join(p.text for p in pages)
    file_embedding = await ctx.run_typed(
        "embed file-level text",
        lambda: embedder.embed_query(file_text[:8000]),
    )

    qdrant = QdrantGateway()

    # Mint deterministic UUIDs so re-runs UPSERT in place.
    chunk_points = [
        ChunkPoint(
            id=str(uuid5(NAMESPACE_DNS, f"ndmo-chunk:{document_id}:{c.chunk_index}")),
            text=c.text,
            page_number=c.page_number,
            source_file=c.source_file,
            document_id=document_id,
            dense=emb.dense,
            sparse_indices=emb.sparse.indices,
            sparse_values=emb.sparse.values,
            extra={
                "chunk_index": c.chunk_index,
                "word_count": c.word_count,
                "spans_pages": c.spans_pages,
            },
        )
        for c, emb in zip(chunks, embeddings)
    ]

    file_point = FilePoint(
        id=str(uuid5(NAMESPACE_DNS, f"ndmo-file:{document_id}")),
        text=file_text,
        document_id=document_id,
        dense=file_embedding.dense,
        sparse_indices=file_embedding.sparse.indices,
        sparse_values=file_embedding.sparse.values,
    )

    await ctx.run_typed(
        "upsert chunks to qdrant",
        qdrant.upsert_chunks, tenant_id=tenant_id, points=chunk_points,
    )
    await ctx.run_typed(
        "upsert file-level point",
        qdrant.upsert_files, tenant_id=tenant_id, points=[file_point],
    )

    await ctx.run_typed(
        "mark ready",
        documents.mark_processed,
        document_id=document_id, tenant_id=tenant_id,
    )

    logger.info("Document %s embedded: %d chunks (tenant %d)",
                document_id, len(chunks), tenant_id)
    return {"chunks": len(chunks), "document_id": document_id}
