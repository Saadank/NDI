"""How a glossary term originally entered the system.

Matches ndmo.t_glossary_terms.source.  `db_extracted` terms are promoted
candidates (BRD §6.4); `llm_assisted` flags that AI drafting was used during
authoring (the content is still human-reviewed).
"""

from __future__ import annotations

from enum import StrEnum


class GlossaryTermSource(StrEnum):
    MANUAL = "manual"
    LLM_ASSISTED = "llm_assisted"
    DB_EXTRACTED = "db_extracted"
