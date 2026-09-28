"""_dedupe_document_requirements — pure code, no LLM, no DB. Chunk overlap
(docs/DECISIONS.md #35) means the same required document (e.g. "PAN card copy") often
gets extracted from more than one chunk; same reasoning as _dedupe_facts (#42).
"""

from app.models.schemas import MapPassDocumentRequirement
from app.pipeline import reduce_pass


def test_exact_duplicate_descriptions_collapse_to_first_page_ref() -> None:
    items = [
        MapPassDocumentRequirement(description="PAN card copy", page_ref=3),
        MapPassDocumentRequirement(description="PAN card copy", page_ref=9),
    ]

    result = reduce_pass._dedupe_document_requirements(items)

    assert len(result) == 1
    assert result[0].page_ref == 3


def test_distinct_descriptions_are_both_kept() -> None:
    items = [
        MapPassDocumentRequirement(description="PAN card copy", page_ref=3),
        MapPassDocumentRequirement(description="GST certificate", page_ref=5),
    ]

    result = reduce_pass._dedupe_document_requirements(items)

    assert len(result) == 2


def test_empty_list_returns_empty_list() -> None:
    assert reduce_pass._dedupe_document_requirements([]) == []
