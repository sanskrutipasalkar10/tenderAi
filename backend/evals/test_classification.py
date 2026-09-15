"""Phase 2 gate: page-classification accuracy, measured alone, with NO LLM call —
classify.py is rule-based code. This is this project's replacement for the Build Kit's
generic "retrieval measured alone" gate (see docs/DECISIONS.md row 4 / SPEC.md §10).

Target: >=95% agreement with golden_pages.jsonl (docs/SPEC.md §8 — tunable).

Expected to fail with ImportError until Phase 2 builds app/pipeline/classify.py — that's
the correct state for Phase 1 (Build Kit: "it will fail — there's nothing to test yet").
"""

import json
from pathlib import Path

import fitz
import pytest

from app.pipeline.classify import classify_page  # noqa: F401  (Phase 2)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pdfs"
DATASET = Path(__file__).parent / "datasets" / "golden_pages.jsonl"

ACCURACY_TARGET = 0.95


def load_golden_pages() -> list[dict]:
    return [json.loads(line) for line in DATASET.open(encoding="utf-8")]


@pytest.fixture(scope="module")
def golden_pages() -> list[dict]:
    return load_golden_pages()


def test_golden_dataset_has_minimum_examples(golden_pages: list[dict]) -> None:
    assert len(golden_pages) >= 100, (
        f"Tier 2 requires 100+ golden examples for page classification, "
        f"found {len(golden_pages)}"
    )


def test_classification_accuracy(golden_pages: list[dict]) -> None:
    correct = 0
    mismatches = []

    for row in golden_pages:
        doc = fitz.open(FIXTURES_DIR / f"{row['fixture']}.pdf")
        page = doc[row["page_number"]]
        predicted = classify_page(page)
        doc.close()

        if predicted == row["expected_classification"]:
            correct += 1
        else:
            mismatches.append(
                f"{row['fixture']} p{row['page_number']}: "
                f"expected {row['expected_classification']}, got {predicted}"
            )

    accuracy = correct / len(golden_pages)
    print(f"\nClassification accuracy: {accuracy:.1%} ({correct}/{len(golden_pages)})")
    if mismatches:
        print("Mismatches:\n  " + "\n  ".join(mismatches[:20]))

    assert accuracy >= ACCURACY_TARGET, (
        f"Classification accuracy {accuracy:.1%} below target {ACCURACY_TARGET:.0%}"
    )
