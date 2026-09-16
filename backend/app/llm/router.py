"""Task -> model routing. This is the fast/cheap vs. accurate/expensive routing rule
called for in docs/DECISIONS.md #12/#28 and the GenAI Playbook's Model Strategy section
— one place to change which model handles which pipeline stage, without touching
map_pass.py/reduce_pass.py/extract_vision.py themselves.

Routed entirely through Ollama Cloud (docs/DECISIONS.md #28 — single provider, free tier
on this account, no separate Gemini/Groq API keys needed for MVP):
  - "map"    -> gpt-oss:20b-cloud  (fast/cheap, per-chunk fact extraction)
  - "reduce" -> gpt-oss:120b-cloud (strongest reasoning, final per-module judgment)
  - "vision" -> gemma4:cloud by default (confirmed vision-capable and working); routed
                to a genuinely local Ollama model instead when settings.use_local_vision
                is set (offline/air-gapped work, or Ollama Cloud free-tier exhaustion —
                that model isn't pulled by default, see docs/SPEC.md §2.4)

All three use the "ollama_chat/" provider prefix, not "ollama/" — litellm's "ollama/"
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


def route(task: Task) -> str:
    if task == "map":
        return OLLAMA_MAP_MODEL
    if task == "reduce":
        return OLLAMA_REDUCE_MODEL
    if task == "vision":
        return OLLAMA_LOCAL_VISION_MODEL if settings.use_local_vision else OLLAMA_CLOUD_VISION_MODEL
    raise ValueError(f"Unknown task: {task!r}")
