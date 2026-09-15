"""Phase 5 gate: citation verifiability — this project's real faithfulness metric,
replacing the Build Kit's generic RAG "faithfulness" eval (there is no retrieval step
here; see docs/DECISIONS.md row 4).

For every `page_ref` in every `document_analysis.result` (all three modules), two things
must hold:
  1. A `pages` row exists for that (document_id, page_ref).
  2. That page's `raw_text` plausibly supports the claim (not just "a page exists").

Directly operationalizes docs/SPEC.md §8's success criterion: "100% of
risk_finder.risks[].page_ref resolve to an existing pages row."

Expected to fail with ImportError until Phase 5 builds the reduce pass + citation_verify.py.
"""

import json
from pathlib import Path

import pytest

from app.pipeline.citation_verify import verify_citations  # noqa: F401
from app.services.pipeline_orchestrator import (
    run_pipeline_sync,  # noqa: F401  (test-only sync entrypoint)
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pdfs"
RISK_DATASET = Path(__file__).parent / "datasets" / "golden_risk_finder.jsonl"


def load_risk_rows() -> list[dict]:
    return [json.loads(line) for line in RISK_DATASET.open(encoding="utf-8")]


@pytest.mark.parametrize(
    "fixture_name",
    sorted({row["fixture"] for row in load_risk_rows()}),
)
def test_every_risk_page_ref_resolves_to_a_real_page(fixture_name: str, db_session) -> None:
    """Every risk_finder.risks[].page_ref must exist in the pages table for that document.

    `db_session` is a Phase 5 pytest fixture (real Postgres test DB, or an isolated
    transaction rolled back per test — decided when Phase 5 builds the test DB setup).
    Mocked LLM calls only, per CLAUDE.md hard rule 8: $0, deterministic.
    """
    document = run_pipeline_sync(FIXTURES_DIR / f"{fixture_name}.pdf", db_session)
    analysis = document.get_analysis("risk_finder")

    unresolved = []
    for risk in analysis.result["risks"]:
        page_ref = risk["page_ref"]
        page_exists = document.has_page(page_ref)
        if not page_exists:
            unresolved.append((fixture_name, page_ref))
            continue
        verified = verify_citations(document, page_ref, risk["clause_summary"])
        if not verified:
            unresolved.append((fixture_name, page_ref))

    assert not unresolved, f"Unverifiable citations: {unresolved}"
