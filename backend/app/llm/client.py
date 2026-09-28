"""Provider access layer — the ONLY file in this codebase allowed to name a provider or
call one directly (CLAUDE.md hard rule 1). Every retry/backoff/timeout policy for every
provider call lives here once (hard rule 10), not duplicated across map_pass.py,
reduce_pass.py, and extract_vision.py.

Two providers now (docs/DECISIONS.md #76): Gemini (primary, `gemini/` prefix) and
Ollama (fallback — cloud tag or local, `ollama/`/`ollama_chat/` prefix, see
app.llm.router). Both go through native REST via `requests`, NOT litellm/an SDK —
the Ollama path already had two confirmed litellm bugs (docs/DECISIONS.md #29 image
handling, #34 `timeout` not reliably enforced for large prompts — a real hard-rule-10
violation), so the same "call the provider's own REST API directly, hand-roll
timeout/retry" pattern is used for Gemini too, for consistency and because it avoids
introducing a new SDK dependency and its own unverified quirks. litellm stays a
dependency (imported, available) in case a genuinely different provider is ever added
— complete() still branches on provider prefix, it just happens that no current
traffic takes the litellm branch.
"""

import base64
import random
import time
from typing import Any

import requests

from app.core.config import settings
from app.core.exceptions import ProviderError
from app.core.logging import get_logger
from app.core.tracing import trace_llm_call
from app.llm import router

logger = get_logger(__name__)

DEFAULT_TIMEOUT_SECONDS = 180
DEFAULT_NUM_RETRIES = 1
# Vertex AI "Express Mode" (docs/DECISIONS.md #76) — this project's Gemini API key is
# an Express-mode key (the "AQ." prefix, confirmed by direct testing: it 403s against
# the AI Studio host generativelanguage.googleapis.com with API_KEY_SERVICE_BLOCKED,
# and only authenticates against aiplatform.googleapis.com). A plain AI-Studio key
# (the more commonly documented "AIzaSy..." format) would need the AI Studio host
# instead — this project's key is the Express-mode kind, so that's what's wired here.
GEMINI_API_BASE = "https://aiplatform.googleapis.com/v1/publishers/google/models"


def complete(
    model: str,
    prompt: str,
    *,
    image_bytes: bytes | None = None,
    response_format: dict | None = None,
    temperature: float = 0.0,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    num_retries: int = DEFAULT_NUM_RETRIES,
) -> str:
    """Calls the given model with a text prompt and an optional image.

    `model` is always resolved by app.llm.router, never hardcoded by a caller. Returns
    the raw text response; schema validation of that text happens in
    app.llm.structured, not here.

    Raises ProviderError (never a raw requests/provider exception) on failure, after
    bounded retry-with-backoff is exhausted.
    """
    if model.startswith("gemini/"):
        return _complete_gemini_native(
            model,
            prompt,
            image_bytes=image_bytes,
            response_format=response_format,
            temperature=temperature,
            timeout=timeout,
            num_retries=num_retries,
        )

    if model.startswith("ollama/") or model.startswith("ollama_chat/"):
        return _complete_ollama_native(
            model,
            prompt,
            image_bytes=image_bytes,
            response_format=response_format,
            temperature=temperature,
            timeout=timeout,
            num_retries=num_retries,
        )

    raise ProviderError(
        f"No provider configured for model={model!r}. Add a branch here (and its own "
        "retry/timeout handling) before routing to it."
    )


def complete_for_task(
    task: router.Task,
    prompt: str,
    *,
    image_bytes: bytes | None = None,
    response_format: dict | None = None,
    temperature: float = 0.0,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    num_retries: int = DEFAULT_NUM_RETRIES,
) -> tuple[str, str]:
    """Calls the primary (Ollama Cloud) model for `task`; on failure, automatically
    falls back to a genuinely local Ollama model for the same task (docs/DECISIONS.md
    #32) rather than letting a transient cloud outage/rate-limit stop the pipeline.

    Returns (response_text, model_that_actually_served_it) — callers that record
    provenance (e.g. extract_vision.py's extraction_method: vision_cloud vs
    vision_local) need to know which one actually ran, not just which was attempted
    first.

    This is what pipeline code (extract_vision.py, map_pass.py, and reduce_pass.py)
    should call — not complete() + router.route() directly — unless a caller
    specifically needs one exact model with no fallback (e.g. a test).

    Traced via app.core.tracing (docs/DECISIONS.md #52) — one Langfuse generation per
    call, tagged with `task` and whether the fallback path was used, regardless of
    outcome.
    """
    with trace_llm_call(task=task, prompt=prompt) as trace_result:
        primary = router.route(task)
        try:
            output = complete(
                primary,
                prompt,
                image_bytes=image_bytes,
                response_format=response_format,
                temperature=temperature,
                timeout=timeout,
                num_retries=num_retries,
            )
            trace_result["model"] = primary
            trace_result["output"] = output
            return output, primary
        except ProviderError as exc:
            fallback = router.route_fallback(task)
            if fallback == primary:
                # settings.use_local_vision already made the primary the local model —
                # nothing further to fall back to.
                trace_result["error"] = str(exc)
                raise
            logger.warning(
                "llm.falling_back_to_local",
                task=task,
                primary=primary,
                fallback=fallback,
                error=str(exc),
            )
            try:
                output = complete(
                    fallback,
                    prompt,
                    image_bytes=image_bytes,
                    response_format=response_format,
                    temperature=temperature,
                    timeout=timeout,
                    num_retries=num_retries,
                )
                trace_result["model"] = fallback
                trace_result["output"] = output
                trace_result["fallback_used"] = True
                return output, fallback
            except ProviderError as fallback_exc:
                trace_result["error"] = str(fallback_exc)
                trace_result["fallback_used"] = True
                raise


def _complete_ollama_native(
    model: str,
    prompt: str,
    *,
    image_bytes: bytes | None,
    response_format: dict | None,
    temperature: float,
    timeout: int,
    num_retries: int,
) -> str:
    """Calls Ollama's native /api/chat directly. Same api_base whether the model tag
    is a local model or an Ollama-cloud-hosted "...:cloud" one — Ollama's local daemon
    transparently proxies :cloud tags.
    """
    ollama_model = model.split("/", 1)[1]  # strip "ollama/" or "ollama_chat/" prefix

    message: dict[str, Any] = {"role": "user", "content": prompt}
    if image_bytes is not None:
        message["images"] = [base64.b64encode(image_bytes).decode("ascii")]

    payload: dict[str, Any] = {
        "model": ollama_model,
        "messages": [message],
        "stream": False,
        "options": {"temperature": temperature},
    }
    if response_format is not None and response_format.get("type") == "json_object":
        payload["format"] = "json"

    last_error: Exception | None = None
    for attempt in range(num_retries + 1):
        try:
            response = requests.post(
                f"{settings.ollama_base_url}/api/chat", json=payload, timeout=timeout
            )
            if response.status_code == 429 or response.status_code >= 500:
                raise requests.HTTPError(f"{response.status_code}: {response.text[:200]}")
            response.raise_for_status()
            return response.json()["message"]["content"]
        except (requests.RequestException, KeyError) as exc:
            last_error = exc
            if attempt < num_retries:
                backoff = (2**attempt) + random.uniform(0, 1)
                logger.warning(
                    "llm.ollama_retry",
                    model=model,
                    attempt=attempt + 1,
                    backoff_seconds=round(backoff, 2),
                    error=str(exc),
                )
                time.sleep(backoff)

    logger.error("llm.call_failed_after_retries", model=model, error=str(last_error))
    raise ProviderError(f"{model} unavailable after {num_retries} retries: {last_error}")


def _complete_gemini_native(
    model: str,
    prompt: str,
    *,
    image_bytes: bytes | None,
    response_format: dict | None,
    temperature: float,
    timeout: int,
    num_retries: int,
) -> str:
    """Calls the Gemini API's native generateContent endpoint directly (docs/
    DECISIONS.md #76) — same reasoning as _complete_ollama_native: hand-rolled
    timeout/retry via `requests`, not an SDK, for the same "verified enforcement,
    no library-layer surprises" property hard rule 10 requires.
    """
    gemini_model = model.split("/", 1)[1]  # strip "gemini/" prefix

    parts: list[dict[str, Any]] = []
    if image_bytes is not None:
        encoded_image = base64.b64encode(image_bytes).decode("ascii")
        parts.append({"inline_data": {"mime_type": "image/png", "data": encoded_image}})
    parts.append({"text": prompt})

    generation_config: dict[str, Any] = {"temperature": temperature}
    if response_format is not None and response_format.get("type") == "json_object":
        generation_config["responseMimeType"] = "application/json"

    payload: dict[str, Any] = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": generation_config,
    }
    headers = {"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"}
    url = f"{GEMINI_API_BASE}/{gemini_model}:generateContent"

    last_error: Exception | None = None
    for attempt in range(num_retries + 1):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            if response.status_code == 429 or response.status_code >= 500:
                raise requests.HTTPError(f"{response.status_code}: {response.text[:200]}")
            response.raise_for_status()
            body = response.json()
            candidates = body.get("candidates") or []
            if not candidates:
                # A real, non-transient case: the prompt or response tripped Gemini's
                # own safety filters (promptFeedback.blockReason) — never in this
                # project's control to retry away, so this raises immediately rather
                # than burning the retry budget on a KeyError/IndexError.
                block_reason = body.get("promptFeedback", {}).get("blockReason")
                raise ProviderError(
                    f"{model} returned no candidates (blockReason={block_reason!r})"
                )
            return candidates[0]["content"]["parts"][0]["text"]
        except (requests.RequestException, KeyError) as exc:
            last_error = exc
            if attempt < num_retries:
                backoff = (2**attempt) + random.uniform(0, 1)
                logger.warning(
                    "llm.gemini_retry",
                    model=model,
                    attempt=attempt + 1,
                    backoff_seconds=round(backoff, 2),
                    error=str(exc),
                )
                time.sleep(backoff)

    logger.error("llm.call_failed_after_retries", model=model, error=str(last_error))
    raise ProviderError(f"{model} unavailable after {num_retries} retries: {last_error}")
