"""Task -> model routing. This is the fast/cheap vs. accurate/expensive routing rule
called for in docs/DECISIONS.md #12/#28 and the GenAI Playbook's Model Strategy section
— one place to change which model handles which pipeline stage, without touching
map_pass.py/reduce_pass.py/extract_vision.py themselves.

Primary routing is Ollama Cloud (docs/DECISIONS.md #28 — single provider, free tier on
this account, no separate Gemini/Groq API keys needed for MVP):
  - "map"    -> gpt-oss:20b-cloud  (fast/cheap, per-chunk fact extraction)
  - "reduce" -> gpt-oss:120b-cloud (strongest reasoning, final per-module judgment)
  - "vision" -> gemma4:cloud (confirmed vision-capable and working)

Every task also has a genuinely local fallback (docs/DECISIONS.md #32) — used by
app.llm.client.complete_for_task when the cloud call fails after its own retries, so a
transient Ollama Cloud outage/rate-limit degrades the pipeline instead of stopping it:
  - "map"/"reduce" -> qwen2.5-coder:7b (a capable general 7B model already available
                       locally; not ideal for non-code reasoning, but "works" beats
                       "blocked" for a fallback path — see docs/DECISIONS.md #32)
  - "vision"        -> qwen2.5vl:7b (the model docs/SPEC.md §2.4 originally specified)

settings.use_local_vision forces the LOCAL vision model as primary too (fully
offline/air-gapped work) — in that mode there's no cloud call and therefore no
fallback to attempt.

All models use the "ollama_chat/" provider prefix, not "ollama/" — litellm's "ollama/"
provider (the legacy /api/generate endpoint) mishandles multi-turn-style prompts for
some of these models; "ollama_chat/" (the /api/chat endpoint) is the modern, correct
integration for chat-style Ollama models. See app/llm/client.py for the one exception
(image-bearing calls bypass litellm entirely due to a verified library bug).
"""

from typing import Literal

from app.core.config import settings

Task = Literal["map", "reduce", "vision"]

OLLAMA_MAP_MODEL = "ollama_chat/gpt-oss:20b-cloud"
OLLAMA_REDUCE_MODEL = "ollama_chat/gpt-oss:120b-cloud"
OLLAMA_CLOUD_VISION_MODEL = "ollama_chat/gemma4:cloud"
OLLAMA_LOCAL_VISION_MODEL = "ollama_chat/qwen2.5vl:7b"
OLLAMA_LOCAL_TEXT_MODEL = "ollama_chat/qwen2.5-coder:7b"


def route(task: Task) -> str:
    """The primary model for a task — Ollama Cloud, unless use_local_vision forces the
    local vision model as primary (not just as a fallback).
    """
    if task == "map":
        return OLLAMA_MAP_MODEL
    if task == "reduce":
        return OLLAMA_REDUCE_MODEL
    if task == "vision":
        return OLLAMA_LOCAL_VISION_MODEL if settings.use_local_vision else OLLAMA_CLOUD_VISION_MODEL
    raise ValueError(f"Unknown task: {task!r}")


def route_fallback(task: Task) -> str:
    """The local model to fall back to if the primary (cloud) call fails. Always local
    — the point of a fallback is not depending on the same cloud service that just
    failed. Returns the same model as route() when already local (use_local_vision),
    signaling to the caller there's nothing further to fall back to.
    """
    if task in ("map", "reduce"):
        return OLLAMA_LOCAL_TEXT_MODEL
    if task == "vision":
        return OLLAMA_LOCAL_VISION_MODEL
    raise ValueError(f"Unknown task: {task!r}")
