"""Task -> model routing. This is the fast/cheap vs. accurate/expensive routing rule
called for in docs/DECISIONS.md #12/#28/#76 and the GenAI Playbook's Model Strategy
section — one place to change which model handles which pipeline stage, without
touching map_pass.py/reduce_pass.py/extract_vision.py themselves.

Primary routing is the Gemini API (docs/DECISIONS.md #76 — superseding Ollama Cloud as
primary; Ollama Cloud's free-tier throughput could not meet the pipeline's own latency
target, docs/DECISIONS.md #50, and Gemini's real per-document unit cost is negligible,
see the cost analysis this decision references):
  - "map"    -> gemini-3.8-flash        (fast/cheap, per-chunk fact extraction; also
                                          handles vision — Gemini 3.8 Flash accepts
                                          images directly, no separate vision model)
  - "reduce" -> gemini-3.1-pro-preview  (strongest reasoning, final per-module judgment)
  - "vision" -> gemini-3.8-flash        (multimodal — same model as "map")

Every task also has a genuinely local Ollama fallback (docs/DECISIONS.md #32/#76) —
used by app.llm.client.complete_for_task when the Gemini call fails after its own
retries, so a transient Gemini outage/rate-limit degrades the pipeline instead of
stopping it. This preserves the resilience design Ollama Cloud originally had as
primary — only WHICH provider is primary changed, the "always have a local escape
hatch" principle (hard rule 10) did not:
  - "map"/"reduce" -> qwen2.5-coder:7b (a capable general 7B model already available
                       locally; not ideal for non-code reasoning, but "works" beats
                       "blocked" for a fallback path — see docs/DECISIONS.md #32)
  - "vision"        -> qwen2.5vl:7b (the model docs/SPEC.md §2.4 originally specified)

settings.use_local_vision forces the LOCAL vision model as primary too (fully
offline/air-gapped work) — in that mode there's no cloud call and therefore no
fallback to attempt, exactly as before this change.
"""

from typing import Literal

from app.core.config import settings

Task = Literal["map", "reduce", "vision"]

GEMINI_MAP_MODEL = "gemini/gemini-3.8-flash"
GEMINI_REDUCE_MODEL = "gemini/gemini-3.1-pro-preview"
GEMINI_VISION_MODEL = "gemini/gemini-3.8-flash"
OLLAMA_LOCAL_VISION_MODEL = "ollama_chat/qwen2.5vl:7b"
OLLAMA_LOCAL_TEXT_MODEL = "ollama_chat/qwen2.5-coder:7b"


def route(task: Task) -> str:
    """The primary model for a task — the Gemini API, unless use_local_vision forces
    the local Ollama vision model as primary (not just as a fallback).
    """
    if task == "map":
        return GEMINI_MAP_MODEL
    if task == "reduce":
        return GEMINI_REDUCE_MODEL
    if task == "vision":
        return OLLAMA_LOCAL_VISION_MODEL if settings.use_local_vision else GEMINI_VISION_MODEL
    raise ValueError(f"Unknown task: {task!r}")


def route_fallback(task: Task) -> str:
    """The local Ollama model to fall back to if the primary (Gemini) call fails.
    Always local — the point of a fallback is not depending on the same cloud service
    that just failed. Returns the same model as route() when already local
    (use_local_vision), signaling to the caller there's nothing further to fall back
    to.
    """
    if task in ("map", "reduce"):
        return OLLAMA_LOCAL_TEXT_MODEL
    if task == "vision":
        return OLLAMA_LOCAL_VISION_MODEL
    raise ValueError(f"Unknown task: {task!r}")
