"""BGE-M3 dense + BM25 sparse embedding gateway.

Self-hosted via the ``fastembed`` package (which ships ONNX runtime + the
quantised BGE-M3 weights ~ 1 GB, downloaded on first construction and
cached in ``$FASTEMBED_CACHE_DIR``).  No outbound API calls at query
time — Saudi government data stays on-prem per the Phase-1 decision.

  * Dense:  ``BAAI/bge-m3`` (1024-d, strong on Arabic, MIT licensed)
  * Sparse: ``Qdrant/bm25`` (Qdrant's BM25 implementation as a fastembed
            sparse model — matches the sparse index inside Qdrant)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_DENSE_MODEL = "BAAI/bge-m3"
_SPARSE_MODEL = "Qdrant/bm25"


@dataclass(slots=True)
class SparseEmbedding:
    indices: list[int]
    values: list[float]


@dataclass(slots=True)
class HybridEmbedding:
    dense: list[float]
    sparse: SparseEmbedding


class EmbeddingGateway:
    """Lazy-loaded singletons of the BGE-M3 dense + BM25 sparse models."""

    _dense_model = None
    _sparse_model = None

    @classmethod
    def _get_dense(cls):
        if cls._dense_model is None:
            from fastembed import TextEmbedding  # noqa: PLC0415

            logger.info("Loading BGE-M3 dense model (%s)…", _DENSE_MODEL)
            cls._dense_model = TextEmbedding(model_name=_DENSE_MODEL)
        return cls._dense_model

    @classmethod
    def _get_sparse(cls):
        if cls._sparse_model is None:
            from fastembed import SparseTextEmbedding  # noqa: PLC0415

            logger.info("Loading BM25 sparse model (%s)…", _SPARSE_MODEL)
            cls._sparse_model = SparseTextEmbedding(model_name=_SPARSE_MODEL)
        return cls._sparse_model

    def embed_batch(self, texts: list[str]) -> list[HybridEmbedding]:
        """Embed a batch of texts.  Returns one HybridEmbedding per input."""
        if not texts:
            return []
        dense_iter = self._get_dense().embed(texts)
        sparse_iter = self._get_sparse().embed(texts)
        out: list[HybridEmbedding] = []
        for d, s in zip(dense_iter, sparse_iter):
            out.append(
                HybridEmbedding(
                    dense=d.tolist() if hasattr(d, "tolist") else list(d),
                    sparse=SparseEmbedding(
                        indices=s.indices.tolist() if hasattr(s.indices, "tolist") else list(s.indices),
                        values=s.values.tolist() if hasattr(s.values, "tolist") else list(s.values),
                    ),
                )
            )
        return out

    def embed_query(self, text: str) -> HybridEmbedding:
        """Embed a single query (uses the same models, no instruction prefix)."""
        return self.embed_batch([text])[0]
