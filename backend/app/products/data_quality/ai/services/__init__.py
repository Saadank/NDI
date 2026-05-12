"""Service layer for LLM-touching workflows.

Sub-step landings:
- Step 6.2 — ``pii_anonymizer.py`` (pass-through stub today; real impl later)
- Step 6.3 — ``concept_draft_service.py`` (Approach 2 NL → concept)
- Step 6.4 — ``excel_parser.py`` + ``glossary_ingest.py`` (Table 11)
- Step 6.5 — ``column_rule_ingest.py``           (Table 13)
- Step 6.6 — ``business_rule_ingest.py``         (Table 12)
- Step 6.7 — ``proposal_service.py``             (apply / reject / rollback)
"""
