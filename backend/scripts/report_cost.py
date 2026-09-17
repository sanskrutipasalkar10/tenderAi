"""Per-document token/request volume report (Phase 7 gate: "$0 required spend verified
... documented cost-per-document"). Run: `python scripts/report_cost.py` from `backend/`,
with the venv active and DATABASE_URL pointing at a real Postgres.

There is no real dollar cost to report while Ollama Cloud's free tier is the only
configured provider (docs/DECISIONS.md #28) — no payment method is on the account, so
a run either completes for $0 or fails outright; there's no metered bill to reconcile.
What actually matters for "documented cost-per-document" here is token/request VOLUME:
it's the free-tier-quota risk proxy (rate limits are the real constraint, not money —
docs/DECISIONS.md #47) and the number that would matter if a paid tier ever became
necessary. Token counts reuse the exact chars/4 heuristic chunk.py sizes chunks with
(docs/DECISIONS.md #33), not a real provider tokenizer — consistent, not exact.

Two different things are reported, not conflated into one number:
- map_pass_tokens_projected/calls_projected: the FULL document's map-pass cost, known
  precisely from real page text the moment chunks are built (`chunks.token_count`),
  independent of how many chunks have actually been sent to the LLM yet.
- reduce_pass_tokens/calls "from completed chunks": necessarily partial — reduce-pass
  input is the map-pass's own extracted facts, so it can only be computed from chunks
  that have actually been map-passed, not projected ahead of time for an un-processed
  document.
"""

from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.chunk_extraction import ChunkExtraction
from app.models.document import Document
from app.pipeline.reduce_pass import (
    _aggregate_chunk_facts,
    _format_criteria_content,
    _format_risk_candidates_content,
    _format_synopsis_content,
)
from app.storage.db import SessionLocal

_CHARS_PER_TOKEN_ESTIMATE = 4  # matches app.pipeline.chunk._CHARS_PER_TOKEN_ESTIMATE


def _estimate_tokens(text: str) -> int:
    return len(text) // _CHARS_PER_TOKEN_ESTIMATE


def _reduce_pass_token_estimate(db: Session, document: Document) -> tuple[int, int]:
    """Returns (estimated_input_tokens, call_count) for the three reduce modules,
    computed from whatever chunk_extractions already exist for this document — a
    module with no relevant facts skips its LLM call entirely (reduce_pass.py's own
    empty-input short-circuit), so it costs nothing either way.
    """
    facts = _aggregate_chunk_facts(db, document)
    tokens = 0
    calls = 0
    if facts.criteria:
        tokens += _estimate_tokens(_format_criteria_content(facts.criteria))
        calls += 1
    if facts.risk_candidates:
        tokens += _estimate_tokens(_format_risk_candidates_content(facts.risk_candidates))
        calls += 1
    if facts.dates or facts.amounts or facts.criteria:
        tokens += _estimate_tokens(_format_synopsis_content(facts))
        calls += 1
    return tokens, calls


def report_for_document(db: Session, document: Document) -> dict:
    chunks = db.query(Chunk).filter(Chunk.document_id == document.id).all()
    chunk_ids = [c.id for c in chunks]
    extractions_done = (
        db.query(ChunkExtraction).filter(ChunkExtraction.chunk_id.in_(chunk_ids)).all()
        if chunk_ids
        else []
    )

    map_pass_tokens_projected = sum(c.token_count or 0 for c in chunks)
    map_pass_calls_projected = len(chunks)  # one call per chunk, once fully processed
    map_pass_calls_completed = len(extractions_done)

    reduce_tokens, reduce_calls = _reduce_pass_token_estimate(db, document)

    return {
        "document_id": str(document.id),
        "filename": document.filename,
        "total_pages": document.total_pages,
        "chunks": len(chunks),
        "map_pass_tokens_projected": map_pass_tokens_projected,
        "map_pass_calls_projected": map_pass_calls_projected,
        "map_pass_calls_completed": map_pass_calls_completed,
        "reduce_pass_tokens_from_completed_chunks": reduce_tokens,
        "reduce_pass_calls_from_completed_chunks": reduce_calls,
        "required_spend_usd": 0,  # Ollama Cloud free tier only, docs/DECISIONS.md #28
    }


def main() -> None:
    db = SessionLocal()
    try:
        documents = db.query(Document).all()
        rows = [report_for_document(db, d) for d in documents]
    finally:
        db.close()

    if not rows:
        print("No documents found.")
        return

    header = (
        f"{'filename':<50} {'pages':>6} {'chunks':>7} {'map calls':>10} "
        f"{'map tokens (full doc)':>22} {'reduce tokens (so far)':>23}"
    )
    print(header)
    print("-" * len(header))
    totals = {"map_calls": 0, "map_tokens": 0, "reduce_tokens": 0}
    for row in rows:
        totals["map_calls"] += row["map_pass_calls_projected"]
        totals["map_tokens"] += row["map_pass_tokens_projected"]
        totals["reduce_tokens"] += row["reduce_pass_tokens_from_completed_chunks"]
        print(
            f"{row['filename'][:50]:<50} {row['total_pages'] or 0:>6} {row['chunks']:>7} "
            f"{row['map_pass_calls_projected']:>10} "
            f"{row['map_pass_tokens_projected']:>22} "
            f"{row['reduce_pass_tokens_from_completed_chunks']:>23}"
        )
    print("-" * len(header))
    print(
        f"TOTAL across {len(rows)} document(s): {totals['map_calls']} projected map-pass "
        f"calls, {totals['map_tokens']} projected map-pass input tokens, "
        f"{totals['reduce_tokens']} reduce-pass input tokens (from completed chunks only). "
        f"$0 required spend (Ollama Cloud free tier)."
    )


if __name__ == "__main__":
    main()
