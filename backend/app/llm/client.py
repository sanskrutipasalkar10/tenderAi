"""LiteLLM wrapper — the ONLY file in this codebase allowed to import litellm, `requests`
for a raw provider HTTP call, or otherwise name a provider (CLAUDE.md hard rule 1). Every
retry/backoff/timeout policy for every provider call lives here once (hard rule 10), not
duplicated across map_pass.py, reduce_pass.py, and extract_vision.py.
"""

import base64
import random
import time
from typing import Any

import litellm
import requests
from litellm.exceptions import (
    APIConnectionError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)

from app.core.config import settings
from app.core.exceptions import ProviderError
from app.core.logging import get_logger
from app.llm import router

logger = get_logger(__name__)

DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_NUM_RETRIES = 3

# litellm retries these by default too, but being explicit here documents the actual
# 429/connectivity contract this project relies on (CLAUDE.md hard rule 10).
RETRYABLE_EXCEPTIONS = (RateLimitError, APIConnectionError, ServiceUnavailableError, Timeout)


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

    `model` is a LiteLLM model string (e.g. "groq/llama-3.1-70b-versatile",
    "gemini/gemini-2.0-flash", "ollama_chat/gemma4:cloud") — always resolved by
    app.llm.router, never hardcoded by a caller. Returns the raw text response;
    schema validation of that text happens in app.llm.structured, not here.

    Raises ProviderError (never a raw litellm/provider exception) on failure, after
    bounded retry-with-backoff is exhausted.
    """
    if image_bytes is not None and (
        model.startswith("ollama/") or model.startswith("ollama_chat/")
    ):
        # Verified bug in litellm 1.56.5 (docs/DECISIONS.md #28): both the "ollama/"
        # and "ollama_chat/" providers fail to translate OpenAI-style image_url
        # content into Ollama's native request shape — "ollama/" silently stringifies
        # the whole content list into the prompt (model sees garbled text, not an
        # image); "ollama_chat/" sends the content list as-is and Ollama's API 400s on
        # it (it requires `content` to be a plain string with images in a separate
        # top-level `images` array). Confirmed Ollama's native /api/chat endpoint and
        # the model itself both work correctly with the right request shape — this
        # calls that endpoint directly, still centralized here as the only place that
        # talks to a provider. Revisit when a litellm upgrade fixes this AND is
        # compatible with this project's pinned pydantic version.
        return _complete_ollama_vision_native(
            model, prompt, image_bytes, timeout=timeout, num_retries=num_retries
        )

    content: str | list[dict] = prompt
    if image_bytes is not None:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]

    kwargs: dict = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "temperature": temperature,
        "timeout": timeout,
        "num_retries": num_retries,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format
    if model.startswith("ollama/") or model.startswith("ollama_chat/"):
        kwargs["api_base"] = settings.ollama_base_url

    try:
        response = litellm.completion(**kwargs)
    except RETRYABLE_EXCEPTIONS as exc:
        logger.error("llm.call_failed_after_retries", model=model, error=str(exc))
        raise ProviderError(
            f"{model} unavailable after {num_retries} retries: {exc}"
        ) from exc
    except Exception as exc:  # noqa: BLE001 - any other provider failure still maps to ProviderError
        logger.error("llm.call_failed", model=model, error=str(exc))
        raise ProviderError(f"{model} call failed: {exc}") from exc

    return response.choices[0].message.content


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

    This is what pipeline code (extract_vision.py, and map_pass.py/reduce_pass.py in
    later phases) should call — not complete() + router.route() directly — unless a
    caller specifically needs one exact model with no fallback (e.g. a test).
    """
    primary = router.route(task)
    try:
        return complete(
            primary,
            prompt,
            image_bytes=image_bytes,
            response_format=response_format,
            temperature=temperature,
            timeout=timeout,
            num_retries=num_retries,
        ), primary
    except ProviderError as exc:
        fallback = router.route_fallback(task)
        if fallback == primary:
            # settings.use_local_vision already made the primary the local model —
            # nothing further to fall back to.
            raise
        logger.warning(
            "llm.falling_back_to_local",
            task=task,
            primary=primary,
            fallback=fallback,
            error=str(exc),
        )
        return complete(
            fallback,
            prompt,
            image_bytes=image_bytes,
            response_format=response_format,
            temperature=temperature,
            timeout=timeout,
            num_retries=num_retries,
        ), fallback


def _complete_ollama_vision_native(
    model: str,
    prompt: str,
    image_bytes: bytes,
    *,
    timeout: int,
    num_retries: int,
) -> str:
    """Calls Ollama's native /api/chat directly, bypassing litellm, for image-bearing
    Ollama calls only (see the comment in complete() for why). Same api_base whether
    the model tag is a local model or a Ollama-cloud-hosted "...:cloud" one — Ollama's
    local daemon transparently proxies :cloud tags.
    """
    ollama_model = model.split("/", 1)[1]  # strip "ollama/" or "ollama_chat/" prefix
    b64 = base64.b64encode(image_bytes).decode("ascii")
    payload: dict[str, Any] = {
        "model": ollama_model,
        "messages": [{"role": "user", "content": prompt, "images": [b64]}],
        "stream": False,
    }

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
                    "llm.ollama_vision_retry",
                    model=model,
                    attempt=attempt + 1,
                    backoff_seconds=round(backoff, 2),
                    error=str(exc),
                )
                time.sleep(backoff)

    logger.error("llm.call_failed_after_retries", model=model, error=str(last_error))
    raise ProviderError(f"{model} unavailable after {num_retries} retries: {last_error}")
