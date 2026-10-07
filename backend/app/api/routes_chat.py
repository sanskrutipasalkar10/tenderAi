"""Tender/procurement terminology + document-aware chat assistant (docs/DECISIONS.md).
Stateless: the client holds conversation history (no server-side persistence, a
deliberate product decision — this would otherwise be a new place real tender content
is stored) and resends it each turn. Document grounding reuses whatever this document's
own already-computed document_analysis rows already say (app.services.chat_context) —
no retrieval step, no re-reading the PDF, consistent with this project's
pipeline-not-agent architecture.

Two endpoints, same prompt assembly: POST / is a plain single-shot reply; POST /stream
renders the same answer incrementally (app.llm.client.stream_chat_completion) for the
chat widget, which otherwise made a user stare at a spinner for 5-10s per message. The
non-streaming endpoint is kept as-is, not replaced — simpler callers (tests, scripts)
don't need to deal with SSE framing.
"""

import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.exceptions import ProviderError
from app.llm.client import complete_for_task, stream_chat_completion
from app.models.schemas import ChatRequest, ChatResponse
from app.prompts.registry import load_prompt
from app.services.chat_context import build_document_context

router = APIRouter(prefix="/chat", tags=["chat"])

# Bounds prompt size, not a hard conversation-length limit — the client may hold more
# turns locally than it sends on any given request.
MAX_HISTORY_TURNS = 10


def _build_chat_prompt(db: Session, request: ChatRequest) -> str:
    """Shared by both endpoints below so a streamed answer and a single-shot one are
    always generated from the identical prompt."""
    document_context = (
        build_document_context(db, request.document_id) if request.document_id else None
    )
    history_text = "\n".join(
        f"{message.role}: {message.content}" for message in request.history[-MAX_HISTORY_TURNS:]
    )
    return (
        load_prompt("chat", "v1_tender_assistant")
        .replace(
            "{document_context}",
            document_context or "No document is currently open.",
        )
        .replace("{history}", history_text or "(no previous messages)")
        .replace("{message}", request.message)
    )


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    reply, _ = complete_for_task("chat", _build_chat_prompt(db, request))
    return ChatResponse(reply=reply.strip())


@router.post("/stream")
def chat_stream(request: ChatRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    """Wire format is app-defined (`{"delta"|"done"|"error"}` JSON lines, one per SSE
    frame), not either provider's native streaming shape — the whole point of
    app.llm.client being the only provider-aware file is that nothing downstream, this
    route included, needs to know whether Gemini or Ollama actually served the
    response. No response_model here (can't combine with StreamingResponse); the
    non-streaming POST / above keeps a normal typed response for callers that want one.
    """
    prompt = _build_chat_prompt(db, request)

    def event_stream() -> Iterator[str]:
        try:
            for delta in stream_chat_completion(prompt):
                yield f"data: {json.dumps({'delta': delta})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except ProviderError as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
