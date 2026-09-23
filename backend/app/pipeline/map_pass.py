"""Map pass — per-chunk fact extraction (docs/SPEC.md §2.1 stage 3), the cheap/fast
half of the two-pass map-reduce design. Routed through app.llm.structured (which
itself routes through app.llm.client/router), never a provider SDK directly (CLAUDE.md
hard rule 1). Prompt is a versioned file (hard rule 2), never inline.
"""

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.llm.structured import complete_structured
from app.models.chunk import Chunk
from app.models.chunk_extraction import ChunkExtraction
from app.models.schemas import MapPassResult
from app.pipeline.chunk import chunk_page_text
from app.prompts.registry import load_prompt

logger = get_logger(__name__)

# A chunk with this much real text returning a totally empty MapPassResult is
# suspicious, not a legitimate "this chunk has nothing extractable" outcome — found
# for real (docs/DECISIONS.md): a cloud timeout fell back to the local model
# (qwen2.5-coder:7b, docs/DECISIONS.md #32), which silently returned nothing for a
# 285-line chunk of real catering-tender clauses instead of erroring, so nothing
# downstream had reason to distrust it.
_MIN_CONTENT_LENGTH_FOR_NONEMPTY_RESULT = 500


def _format_chunk_content(pages: list[tuple[int, str]]) -> str:
    return "\n\n".join(f"[PAGE {page_number}]\n{text}" for page_number, text in pages)


def _is_empty(result: MapPassResult) -> bool:
    return not (result.dates or result.amounts or result.criteria or result.risk_candidates)


def run_map_pass(db: Session, chunk: Chunk) -> ChunkExtraction:
    """Extracts structured facts from one chunk and persists them as a
    ChunkExtraction row. Always produces a row — a chunk with no extracted text
    (every page in its range failed extraction) gets an empty MapPassResult without an
    LLM call, rather than being silently skipped or wastefully calling the model on
    nothing.

    A chunk WITH substantial real text that still comes back with a totally empty
    result gets one retry (fresh call, same content — gives the cloud model, which
    complete_for_task always tries first, another chance rather than assuming the
    prior fallback-to-local result was representative). If the retry is also empty,
    that's persisted as-is (still never silently dropped), but both attempts are
    logged so the gap is visible rather than indistinguishable from "this chunk
    genuinely has nothing extractable."
    """
    pages = chunk_page_text(db, chunk)

    if not pages:
        result = MapPassResult()
        model_used = None
        logger.warning(
            "map_pass.empty_chunk_no_text",
            chunk_id=str(chunk.id),
            start_page=chunk.start_page,
            end_page=chunk.end_page,
        )
    else:
        content = _format_chunk_content(pages)
        # .replace(), not .format() — the prompt file's own JSON example is full of
        # literal {braces} that .format() would misinterpret as placeholders.
        prompt = load_prompt("map_pass", "v1_map_pass").replace("{content}", content)
        result, model_used = complete_structured("map", prompt, MapPassResult)

        if len(content) > _MIN_CONTENT_LENGTH_FOR_NONEMPTY_RESULT and _is_empty(result):
            logger.warning(
                "map_pass.suspiciously_empty_result",
                chunk_id=str(chunk.id),
                content_length=len(content),
                model_used=model_used,
            )
            result, model_used = complete_structured("map", prompt, MapPassResult)
            if _is_empty(result):
                logger.warning(
                    "map_pass.empty_after_retry",
                    chunk_id=str(chunk.id),
                    content_length=len(content),
                    model_used=model_used,
                )

    extraction = ChunkExtraction(
        chunk_id=chunk.id,
        structured_json=result.model_dump(),
        model_used=model_used,
    )
    db.add(extraction)
    db.commit()
    db.refresh(extraction)
    return extraction


def run_map_pass_for_document(db: Session, chunks: list[Chunk]) -> list[ChunkExtraction]:
    """Runs the map pass over every chunk of a document. Each chunk is processed (and
    retried, per CLAUDE.md hard rule 10 living inside complete_structured/client)
    independently — one chunk's failure doesn't block the others; a chunk-level
    failure surfaces as a ProviderError to the caller (Celery task), which per-chunk
    retries at the task level (Phase 4 gate: "per-chunk, not per-document, retry").
    """
    return [run_map_pass(db, chunk) for chunk in chunks]
