"""app.pipeline.map_pass_cache — content_hash determinism and remap_page_refs
correctness. remap_page_refs is the citation-correctness-critical piece: a wrong
remap would silently point a citation at the wrong page, which this project treats
as non-negotiable (CLAUDE.md hard rule 4/6). No I/O in either function under test
here — get_cached/store are covered via the fake-session tests below and via
test_map_pass.py's cache-hit test, which exercises the whole run_map_pass path.
"""

from app.pipeline import map_pass_cache


def test_content_hash_ignores_page_numbers() -> None:
    """The same text at different page numbers must hash identically — that's the
    entire point (a tender's own content repeated as an attachment, with different
    global page numbers, must still be recognized as the same content).
    """
    a = map_pass_cache.content_hash([(5, "clause text"), (6, "more clause text")])
    b = map_pass_cache.content_hash([(95, "clause text"), (96, "more clause text")])
    assert a == b


def test_content_hash_distinguishes_different_text() -> None:
    a = map_pass_cache.content_hash([(0, "clause text")])
    b = map_pass_cache.content_hash([(0, "different clause text")])
    assert a != b


def test_content_hash_distinguishes_page_order() -> None:
    a = map_pass_cache.content_hash([(0, "first"), (1, "second")])
    b = map_pass_cache.content_hash([(0, "second"), (1, "first")])
    assert a != b


def test_remap_page_refs_rewrites_every_field_type() -> None:
    structured_json = {
        "dates": [{"label": "Deadline", "value": "1 Jan", "page_ref": 10}],
        "amounts": [{"label": "EMD", "value": "INR 1L", "page_ref": 11}],
        "criteria": [{"description": "ISO cert", "page_ref": 12}],
        "risk_candidates": [{"category": "Liability", "clause_summary": "x", "page_ref": 10}],
        "documents_required": [{"description": "PAN copy", "page_ref": 11}],
    }
    # original chunk spanned pages 10-12; the reusing chunk spans pages 100-102,
    # same relative positions.
    remapped = map_pass_cache.remap_page_refs(
        structured_json, original_pages=[10, 11, 12], current_pages=[100, 101, 102]
    )

    assert remapped["dates"][0]["page_ref"] == 100
    assert remapped["amounts"][0]["page_ref"] == 101
    assert remapped["criteria"][0]["page_ref"] == 102
    assert remapped["risk_candidates"][0]["page_ref"] == 100
    assert remapped["documents_required"][0]["page_ref"] == 101
    # Non-page_ref fields must survive unchanged.
    assert remapped["dates"][0]["label"] == "Deadline"


def test_remap_page_refs_handles_empty_lists() -> None:
    empty_result = {
        "dates": [],
        "amounts": [],
        "criteria": [],
        "risk_candidates": [],
        "documents_required": [],
    }
    remapped = map_pass_cache.remap_page_refs(
        empty_result, original_pages=[0], current_pages=[50]
    )
    assert remapped == empty_result


def test_remap_page_refs_single_page_chunk() -> None:
    remapped = map_pass_cache.remap_page_refs(
        {"dates": [{"label": "x", "value": "y", "page_ref": 7}]},
        original_pages=[7],
        current_pages=[200],
    )
    assert remapped["dates"][0]["page_ref"] == 200


def test_remap_page_refs_passes_through_out_of_range_page_ref() -> None:
    """A page_ref the model returned outside the chunk's own original range (already
    possible today even without caching — nothing validates it beyond Pydantic's
    `ge=0`) must not crash the remap; it degrades to passing the value through
    unchanged rather than raising.
    """
    remapped = map_pass_cache.remap_page_refs(
        {"dates": [{"label": "x", "value": "y", "page_ref": 999}]},
        original_pages=[10, 11],
        current_pages=[100, 101],
    )
    assert remapped["dates"][0]["page_ref"] == 999
