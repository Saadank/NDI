"""NDMO assessment engine.

For every specification in a tenant's active cycle:
  1. Build the RAG retrieval query (spec.search_query, or fallback).
  2. Hybrid-search the tenant's Qdrant collection for top-5 chunks.
  3. Build an Arabic Claude prompt with the spec context + chunks.
  4. Force-tool-call submit_assessment to get structured output.
  5. Persist to ndmo.t_ndmo_assessments + ndmo.t_ndmo_citations.
"""

from .engine import AssessmentEngine, get_assessment_engine
from .output_schema import AssessmentOutput, Citation

__all__ = ["AssessmentEngine", "get_assessment_engine", "AssessmentOutput", "Citation"]
