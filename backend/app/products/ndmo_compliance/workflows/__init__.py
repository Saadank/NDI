"""Restate workflow + per-stage tasks for NDMO document ingestion.

Pipeline (in order):

   presigned PUT to MinIO
        |
        v
   MinIO bucket-notify -> webhook -> ctx.workflow_send(...)
        |
        v
   Restate "NdmoDocumentIngestionWorkflow":
     1. ValidateAndScan      (this iteration's worked example)
     2. Store                (move from ndmo-unscanned -> ndmo-clean)
     3. Extract              (Arabic OCR / PyMuPDF text)
     4. Embed                (chunk + BGE-M3 dense + Qdrant BM25 sparse)
        |
        v
   ndmo.t_ndmo_documents.status = 'ready'
"""
