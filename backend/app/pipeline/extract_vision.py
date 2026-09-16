"""Vision-based extraction — for pages classified `scanned_image` (and, in a later
iteration, low-confidence `table` pages where native extraction found nothing useful).
The only pipeline stage that calls an LLM before the map/reduce phases (docs/SPEC.md
§2.1 stage 1) — routed through app.llm.router / app.llm.client, never a provider SDK
directly (CLAUDE.md hard rule 1).
"""

import hashlib

import fitz

from app.core.exceptions import ProviderError
from app.llm.client import complete
from app.llm.router import route
from app.models.schemas import PageExtractionResult
from app.prompts.registry import load_prompt

# 100 DPI keeps the base64-encoded PNG small enough to fit in context (150 DPI
# overflowed a 262K-token context on a real scanned tender page — see
# docs/DECISIONS.md #28) while staying legible for a vision model.
RENDER_DPI = 100
NO_TEXT_SENTINEL = "NO_TEXT_FOUND"

# Vision extraction is inherently less certain than reading a real text layer — this is
# a fixed, explainable confidence (not model-self-reported, which is unreliable), tuned
# against evals/ once real accuracy numbers exist for this pipeline stage.
VISION_CONFIDENCE = 0.7


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _content_hash(text: str) -> str:
    return hashlib.sha256(_normalize(text).encode("utf-8")).hexdigest()


def extract_page_via_vision(page: fitz.Page) -> PageExtractionResult:
    """Renders the page to an image and transcribes it via the vision-capable model
    app.llm.router routes to. Always returns a result, even on provider failure
    (confidence 0.0, extraction_method still recorded) — CLAUDE.md's zero-page-drop
    invariant: this stage failing is not the same as this page being skipped.
    """
    pixmap = page.get_pixmap(dpi=RENDER_DPI)
    image_bytes = pixmap.tobytes("png")

    model = route("vision")
    prompt = load_prompt("vision", "v1_vision_extract")

    try:
        raw_response = complete(model=model, prompt=prompt, image_bytes=image_bytes)
    except ProviderError:
        return PageExtractionResult(
            page_number=page.number,
            classification="scanned_image",
            extraction_method="vision_local" if "local" in model else "vision_cloud",
            raw_text=None,
            content_hash=None,
            confidence_score=0.0,
        )

    text = raw_response.strip()
    if not text or text == NO_TEXT_SENTINEL:
        return PageExtractionResult(
            page_number=page.number,
            classification="scanned_image",
            extraction_method="vision_local" if "local" in model else "vision_cloud",
            raw_text=None,
            content_hash=None,
            confidence_score=0.0,
        )

    return PageExtractionResult(
        page_number=page.number,
        classification="scanned_image",
        extraction_method="vision_local" if "local" in model else "vision_cloud",
        raw_text=text,
        content_hash=_content_hash(text),
        confidence_score=VISION_CONFIDENCE,
    )
