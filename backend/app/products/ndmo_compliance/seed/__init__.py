"""NDMO Compliance — one-shot seed pipeline.

The 14 Reqs + the master Standards PDF + the xlsx template + the 13 Trackers
together fully specify the 14 domains / 77 controls / ~190 specifications.
This package reads them ONCE into the `ndmo` schema; runtime serving code
never touches the raw files again.

Stages (see runner.py for the orchestrator):
  A. parse_dms_pdf       — hierarchy + priorities + raw text from master PDF
  B. parse_xlsx_template — required_elements JSON per spec
  C. parse_req_pdfs      — maturity_levels + acceptance_criteria + search_query
  D. cross_validate_trackers — sanity-check assembled data against Tracker xlsx
  E. parse_ndi_formula   — verify the NDI formula encoded in scoring/formula.py
"""
