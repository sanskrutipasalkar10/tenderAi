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


def _format_chunk_content(pages: list[tuple[int, str]]) -> str:
    return "\n\n".join(f"[PAGE {page_number}]\n{text}" for page_number, text in pages)


def run_map_pass(db: Session, chunk: Chunk) -> ChunkExtraction:
    """Extracts structured facts from one chunk and persists them as a
    ChunkExtraction row. Always produces a row — a chunk with no extracted text
    (every page in its range failed extraction) gets an empty MapPassResult without an
    LLM call, rather than being silently skipped or wastefully calling the model on
    nothing.
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
