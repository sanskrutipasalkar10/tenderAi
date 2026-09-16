"""Unit tests for extract_vision.py — LLM call mocked per CLAUDE.md hard rule 8 (a
test run must cost $0, be deterministic, and not depend on Ollama/any provider being
reachable). Real vision-extraction correctness against Ollama Cloud is validated
manually and via evals/test_extraction_completeness.py, not here.
"""

from pathlib import Path
from unittest.mock import patch

import fitz

from app.core.exceptions import ProviderError
from app.pipeline.extract_vision import extract_page_via_vision

FIXTURES_DIR = Path(__file__).parent.parent.parent / "evals" / "fixtures" / "pdfs"


@patch("app.pipeline.extract_vision.complete_for_task")
def test_successful_extraction(mock_complete_for_task) -> None:
    mock_complete_for_task.return_value = (
        "Transcribed clause text from the scanned page.",
        "ollama_chat/gemma4:cloud",
    )

    doc = fitz.open(FIXTURES_DIR / "fixture_01_nhai_road.pdf")
    result = extract_page_via_vision(doc[5])  # scanned signature page
    doc.close()

    assert result.raw_text == "Transcribed clause text from the scanned page."
    assert result.content_hash is not None
    assert result.confidence_score == 0.7
    assert result.extraction_method == "vision_cloud"
    mock_complete_for_task.assert_called_once()
    args, kwargs = mock_complete_for_task.call_args
    assert args[0] == "vision"
    assert kwargs["image_bytes"] is not None, "must actually pass rendered image bytes"


@patch("app.pipeline.extract_vision.complete_for_task")
def test_local_fallback_is_recorded_as_vision_local(mock_complete_for_task) -> None:
    """When complete_for_task falls back to a local model, extraction_method must
    reflect what actually served the request, not what was attempted first.
    """
    mock_complete_for_task.return_value = ("Locally transcribed text.", "ollama_chat/qwen2.5vl:7b")

    doc = fitz.open(FIXTURES_DIR / "fixture_01_nhai_road.pdf")
    result = extract_page_via_vision(doc[5])
    doc.close()

    assert result.raw_text == "Locally transcribed text."
    assert result.extraction_method == "vision_local"


@patch("app.pipeline.extract_vision.complete_for_task")
def test_no_text_found_sentinel_yields_empty_result(mock_complete_for_task) -> None:
    mock_complete_for_task.return_value = ("NO_TEXT_FOUND", "ollama_chat/gemma4:cloud")

    doc = fitz.open(FIXTURES_DIR / "fixture_01_nhai_road.pdf")
    result = extract_page_via_vision(doc[5])
    doc.close()

    assert result.raw_text is None
    assert result.content_hash is None
    assert result.confidence_score == 0.0


@patch("app.pipeline.extract_vision.complete_for_task")
def test_provider_failure_yields_low_confidence_result_not_a_crash(mock_complete_for_task) -> None:
    # Both primary and fallback exhausted — complete_for_task itself raises.
    mock_complete_for_task.side_effect = ProviderError("simulated 429 on both primary and fallback")

    doc = fitz.open(FIXTURES_DIR / "fixture_01_nhai_road.pdf")
    result = extract_page_via_vision(doc[5])
    doc.close()

    # zero-page-drop: a provider failure still returns a result, never raises out of
    # this function — the caller (ingestion.py) always gets a row to write.
    assert result.raw_text is None
    assert result.confidence_score == 0.0
    assert result.page_number == 5
